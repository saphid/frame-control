#!/usr/bin/env python3
"""Launch a built Linux AppImage on Xvfb and check its bundled server.

This checks the packaged app without a headset or a desktop login session.
The profile and display are temporary, and every process started by this check
is stopped before it exits.
"""

import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def server_port(profile):
    for log in (profile / "config").rglob("server.log"):
        ports = re.findall(r"--port (\d+)", log.read_text(errors="replace"))
        if ports:
            return int(ports[-1])
    return None


def port_closed(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return False
    except OSError:
        return True


def check(appimage):
    if not appimage.is_file() or not os.access(appimage, os.X_OK):
        raise RuntimeError(f"AppImage is missing or cannot run: {appimage}")
    if not shutil.which("xvfb-run"):
        raise RuntimeError("xvfb-run is required for the AppImage smoke check")
    digest = hashlib.sha256(appimage.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="frame-appimage-smoke-") as directory:
        profile = Path(directory)
        (profile / "tmp").mkdir()
        env = dict(os.environ)
        env.update(
            APPIMAGE_EXTRACT_AND_RUN="1", ELECTRON_DISABLE_SANDBOX="1",
            TMPDIR=str(profile / "tmp"),
            XDG_CONFIG_HOME=str(profile / "config"),
            XDG_CACHE_HOME=str(profile / "cache"),
            XDG_DATA_HOME=str(profile / "data"),
            FRAME_ALIAS="frame-control-appimage-smoke-no-headset",
            FRAME_CONTROL_TELEMETRY="0", FRAME_CONTROL_NO_UPDATE_CHECK="1",
            DO_NOT_TRACK="1",
        )
        output = profile / "app.log"
        port = None
        passed = False
        with output.open("w") as log:
            proc = subprocess.Popen(
                ["xvfb-run", "-a", "-s", "-screen 0 1280x800x24 -nolisten tcp",
                 str(appimage), "--no-sandbox"],
                cwd=profile, env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError(f"AppImage exited {proc.returncode} before its server answered")
                    port = server_port(profile)
                    if port is not None:
                        try:
                            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                                if response.status == 200 and response.headers.get("Server", "").startswith("FrameControl/1"):
                                    passed = True
                                    break
                        except (OSError, urllib.error.URLError):
                            pass
                    time.sleep(0.5)
                if not passed:
                    raise RuntimeError("AppImage server did not answer within 60 seconds")
            except BaseException:
                log.flush()
                print(output.read_text(errors="replace")[-1500:], file=sys.stderr)
                raise
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)
        if port is not None:
            for _ in range(20):
                if port_closed(port):
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError(f"AppImage server stayed on port {port} after shutdown")
    print(f"AppImage SHA-256 {digest}: HTTP 200, FrameControl/1, server stopped")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check-appimage-launch.py path/to/AppImage")
    check(Path(sys.argv[1]).resolve())
