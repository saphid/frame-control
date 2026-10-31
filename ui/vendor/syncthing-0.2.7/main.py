import asyncio
import json
import os
import fcntl
import http.client
import signal
import socket
import subprocess
import tempfile
from urllib.parse import urlsplit, unquote
from pathlib import Path
from typing import TypedDict, Literal, Union, Optional

from decky_plugin import (
    logger,
    DECKY_PLUGIN_SETTINGS_DIR,
    DECKY_PLUGIN_RUNTIME_DIR,
    DECKY_PLUGIN_LOG_DIR,
    DECKY_PLUGIN_DIR,
)

# File that should contain settings.
SETTINGS_PATH = Path(DECKY_PLUGIN_SETTINGS_DIR) / "decky-syncthing.json"
# File that should contain settings.
WATCHDOG_BIN_PATH = Path(DECKY_PLUGIN_DIR) / "bin" / "decky-syncthing-watchdog"
# Path to the watchdog PID file.
# File that should contain settings.
WATCHDOG_PID_PATH = Path(DECKY_PLUGIN_RUNTIME_DIR) / "watchdog.pid"


# Old configs:
class SettingsV1(TypedDict):
    config_version: Literal[1]
    autostart: bool
    flatpak_name: str
    port: int
    api_key: str
    basic_auth_user: str
    basic_auth_pass: str
    keep_running_on_desktop: bool


# See `backend/decky-syncthing-watchdog/src/settings.rs` for details.
class SettingsV2(TypedDict):
    config_version: Literal[2]
    mode: Union[Literal["systemd"], Literal["systemd_system"], Literal["flatpak"]]
    # Mode: systemd OR systemd_system
    service_name: str
    # Mode: flatpak
    flatpak_name: str
    flatpak_binary: str
    # General:
    autostart: Union[Literal["no"], Literal["boot"], Literal["gamescope"]]
    keep_running_on_desktop: bool
    port: int
    api_key: str
    basic_auth_user: str
    basic_auth_pass: str
    # if not True, show wizard and do not run any services.
    # If "migrating" the UI will be optimized for migrating to V2:
    is_setup: Union[bool, Literal["migratingV2"]]
    # Only for the wizard - if set force looking for the Syncthing configuration XML
    # in a Flatpak settings directory, even if the `flatpak` mode is not enabled. The value
    # is the name of the Flatpak
    _wizard_force_flatpak_config_for: Optional[str]


# noinspection PyAttributeOutsideInit
class Plugin:
    settings: SettingsV2

    async def get_settings_json(self) -> str:
        return json.dumps(self.settings)

    async def restart_watchdog(self):
        await reset_all_processes()
        start_watchdog()

    async def set_setting(self, setting: str, value: any):
        # TODO: Could do this nicer with some typing magic.
        if setting not in self.settings and setting != "_wizard_force_flatpak_config_for":
            logger.error(f"Unknown setting: {setting}")
            raise KeyError(f"Unknown setting: {setting}")
        # Sometimes the frontend lib doesn't properly convert the data types, make sure it's correct
        if setting == "port":
            value = int(value)
        if value == "true":
            value = True
        if value == "false":
            value = False
        self.settings[setting] = value  # type: ignore
        with open(SETTINGS_PATH, "w") as f:
            json.dump(self.settings, f)
        logger.info("Updated settings.")

    async def _main(self):
        logger.info("Loaded.")
        self.log_file = None
        self.syncthing = None
        self.settings = await load_settings()
        start_watchdog()

    async def _unload(self):
        watchdog.closed = True
        watchdog.stop()

    async def framey_http_fetch(self, method: str, path: str, headers: dict):
        if watchdog.http_inflight >= 4:
            raise ValueError("Too many Syncthing requests")
        watchdog.http_inflight += 1
        worker = asyncio.create_task(asyncio.to_thread(watchdog.fetch, method, path, headers))
        def finished(task):
            watchdog.http_inflight -= 1
            # A cancelled RPC must retain its slot until the socket worker ends.
            # Retrieve errors even when that RPC no longer awaits the result.
            if not task.cancelled():
                task.exception()
        worker.add_done_callback(finished)
        return await asyncio.shield(worker)


class OwnedWatchdog:
    """Own a child session until it is reaped; never find processes by name/PID file."""

    def __init__(self):
        self.process = None
        self.closed = False
        self.runtime = None
        self.http_inflight = 0

    def start(self):
        if self.closed:
            raise RuntimeError("Syncthing plugin is unloaded")
        if self.process is not None:
            if self.process.poll() is None:
                return
            self.stop()
        env = patch_env(dict(os.environ))
        env['FRAMEY_SYNCTHING_OWNER_PID'] = str(os.getpid())
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
        self.runtime = tempfile.TemporaryDirectory(prefix='framey-syncthing-')
        env['FRAMEY_SYNCTHING_SOCKET'] = str(Path(self.runtime.name)/'watchdog.sock')
        try:
            self.process = subprocess.Popen(
                [WATCHDOG_BIN_PATH, SETTINGS_PATH, WATCHDOG_PID_PATH, DECKY_PLUGIN_LOG_DIR],
                env=env, start_new_session=True,
            )
        except BaseException:
            self.runtime.cleanup()
            self.runtime = None
            raise

    def stop(self):
        process = self.process
        if process is None:
            if self.runtime is not None:
                self.runtime.cleanup()
                self.runtime = None
            return
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=1)
        else:
            process.wait(timeout=1)
        # Keep the handle if wait fails. Never pretend a live child was reaped.
        self.process = None
        self.clean_pid(process.pid)
        if self.runtime is not None:
            self.runtime.cleanup()
            self.runtime = None

    def fetch(self, method, path, headers):
        # Match the exact frontend's routes. Never accept a host, port or socket
        # path from it, and never fall back to the possibly foreign TCP listener.
        if method not in ('GET', 'POST') or not isinstance(path, str) or len(path) > 8192:
            raise ValueError("Invalid Syncthing HTTP request")
        if any(ord(c) < 33 or ord(c) > 126 for c in path) or '\\' in path:
            raise ValueError("Invalid Syncthing HTTP path")
        parsed = urlsplit(path)
        if (not path.startswith('/') or path.startswith('//') or parsed.scheme or parsed.netloc
                or parsed.fragment or unquote(parsed.path) != parsed.path):
            raise ValueError("Syncthing HTTP origin is fixed")
        reads = {'/', '/__decky-watchdog/state', '/rest/system/status', '/rest/system/version',
                 '/rest/config/options', '/rest/config/devices', '/rest/stats/device',
                 '/rest/db/completion', '/rest/config/folders', '/rest/stats/folder',
                 '/rest/db/status', '/rest/system/connections'}
        writes = {'/', '/__decky-watchdog/reload-config', '/__decky-watchdog/start',
                  '/__decky-watchdog/stop', '/__decky-watchdog/check/start',
                  '/__decky-watchdog/check/scan_port', '/__decky-watchdog/check/scan_api_key',
                  '/__decky-watchdog/check/scan_basic_auth'}
        if parsed.path not in (reads if method == 'GET' else writes):
            raise ValueError("Syncthing HTTP route is unavailable")
        if not isinstance(headers, dict) or len(headers) > 4:
            raise ValueError("Invalid Syncthing HTTP headers")
        normalized = {}
        for name, value in headers.items():
            if (not isinstance(name, str) or name.lower() not in
                    {'accept', 'content-type', 'authorization', 'x-api-key'}
                    or name.lower() in normalized or not isinstance(value, str) or len(value) > 4096
                    or any(ord(c) < 32 or ord(c) > 126 for c in value)):
                raise ValueError("Invalid Syncthing HTTP headers")
            normalized[name.lower()] = value
        process, runtime = self.process, self.runtime
        if self.closed or process is None or process.poll() is not None or runtime is None:
            raise RuntimeError("Owned Syncthing watchdog is unavailable")
        # Setup waits up to eleven seconds; service transitions can also wait
        # for a real Syncthing shutdown. Stay within the host's 25-second RPC
        # budget while retaining the short timeout for reads and scan probes.
        lifecycle = {'/__decky-watchdog/check/start', '/__decky-watchdog/start',
                     '/__decky-watchdog/stop', '/__decky-watchdog/reload-config'}
        timeout = 20 if method == 'POST' and parsed.path in lifecycle else 5
        connection = http.client.HTTPConnection('localhost', timeout=timeout)
        stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stream.settimeout(timeout)
        try:
            stream.connect(str(Path(runtime.name)/'watchdog.sock'))
            connection.sock = stream
            connection.request(method, path, headers=normalized)
            response = connection.getresponse()
            data = response.read(256*1024+1)
            if len(data) > 256*1024:
                raise ValueError("Syncthing HTTP response is too large")
            if response.length not in (0, None):
                raise ValueError("Syncthing HTTP response was truncated")
            # Preserve HTTP errors, but never follow Location to another origin.
            return {'status':response.status, 'body':data.decode('utf-8'),
                    'headers':{'content-type':response.getheader('Content-Type', '')[:256]}}
        finally:
            connection.close()
            stream.close()

    @staticmethod
    def clean_pid(pid):
        # The Rust helper holds this same flock for its lifetime. Retain the lock
        # inode: unlinking it could let two later helpers acquire different locks.
        lock_path = WATCHDOG_PID_PATH.with_suffix('.framey-lock')
        try:
            with lock_path.open('r+b') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                if not WATCHDOG_PID_PATH.is_symlink() and WATCHDOG_PID_PATH.read_text().strip() == str(pid):
                    WATCHDOG_PID_PATH.unlink()
        except (OSError, ValueError):
            pass


watchdog = OwnedWatchdog()


def start_watchdog():
    watchdog.start()


async def load_settings() -> SettingsV2:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "rb") as f:
                settings = json.load(f)
        except Exception as ex:
            logger.error(
                f"Failed reading config, using default. Exception: {ex}",
            )
            return default_settings(save=True)
        if "config_version" not in settings:
            logger.error(f"Unsupported settings version, using default.")
            return default_settings(save=True)
        if settings["config_version"] == 1:
            logger.error(f"Running settings migration to V2.")
            return await migrate_settings_v2(settings)
        return settings
    return default_settings(save=True)


def default_settings(*, save=False) -> SettingsV2:
    defaults = SettingsV2(
        config_version=2,
        mode="systemd",
        service_name="",
        flatpak_name="",
        flatpak_binary="syncthing",
        autostart="no",
        keep_running_on_desktop=False,
        port=8384,
        api_key="",
        basic_auth_user="",
        basic_auth_pass="",
        is_setup=False,
    )
    if save:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(defaults, f)
    return defaults


async def migrate_settings_v2(old: SettingsV1) -> SettingsV2:
    settings = SettingsV2(
        config_version=2,
        mode="flatpak",
        service_name="",
        flatpak_name=old["flatpak_name"],
        flatpak_binary="syncthing",
        autostart="gamescope" if old["autostart"] else "no",
        keep_running_on_desktop=old["keep_running_on_desktop"],
        port=old["port"],
        api_key=old["api_key"],
        basic_auth_user=old["basic_auth_user"],
        basic_auth_pass=old["basic_auth_pass"],
        is_setup="migratingV2"
    )

    await reset_all_processes()
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)
    return settings


async def reset_all_processes():
    # Migration/restart may stop only this module's retained child session.
    watchdog.stop()


def patch_env(env):
    # Empty LD_LIBRARY_PATH mandatory for compatibility reasons. At the time of writing sadly only documented on Discord:
    # https://discord.com/channels/960281551428522045/960284327445418044/1399778816670437568
    env["LD_LIBRARY_PATH"] = ""
    return env
