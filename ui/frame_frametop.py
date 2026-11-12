"""Frametop screens on the Frame: live view, input and recordings.

Frametop (github.com/xafnirus/frametop) is a multi-screen KDE Plasma desktop that runs
on the Frame itself, next to Steam's gamescope session. Frame Control's Frametop view
shows one of its screens and lets the page point and type into it. This file is the
half of that which runs on the Frame: the server sends it over ssh like frame_touch.py
(`python3 -u -c ...`, so stdin stays free for events, and nothing has to be installed).

With Frametop's Remote Access on (REMOTE=1, kept in ~/.config/frametop.conf; the
session leaves /run/user/<uid>/frametop/remote-capable behind), its nested KWin
advertises two privileged globals:

  org.kde.KWin.ScreenShot2       one screen as pixels, cursor included if asked
  org_kde_kwin_fake_input        pointer, buttons, scroll, keyboard and text

Neither exists without Remote Access, so the view can only show a "turn it on" note
then; that's why every mode below says so clearly. The desktop's own environment (its
dbus bus, Wayland socket and X authority) is read from the processes of its systemd
unit, because KWin's /proc/<pid>/environ isn't readable but its siblings' are.

The command line (one process per use; all output that isn't the picture goes to stderr):

  status                         one JSON line: {"desktop", "remote", "why", "screens"}
  shot <screen> [--no-cursor]    PNG of one screen on stdout
  stream <screen> [--height 720] [--fps 30]
                                 raw H.264 Annex B on stdout until our stdin closes
  input                          an event loop on stdin (also the mode when no argument)
  record <screen> --name NAME [--fps 30]
                                 an .mp4 in ~/.cache/frame-control/frametop-video,

`status` lists only connected and enabled outputs as {name, width, height, x, y} (the
Frametop session also has disabled 640x480 float slots, which aren't screens to show).
`shot`, `stream` and `record` name one of those.

The input loop prints {"state": "ready"} once, then reads one JSON batch per line:
{"events": [...]} or a bare list. Each batch moves the pointer to a fraction of a named
screen ({"screen": "WL-0", "fx": .5, "fy": .5}), moves it by pixels ({"dx", "dy"}),
presses a button ({"button": "left"|"right"|"middle", "down": bool}), scrolls
({"scroll": [dx, dy]}), holds a key ({"key": <Linux evdev code>, "down": bool}) or types
ASCII ({"text": "hello"}). After each batch it answers {"sent": N}, or {"error": "..."}
when the batch was bad. On EOF it lets go of everything still held and exits: nothing
may stay pressed in the desktop.

The .mp4 name is checked here as well as by the server: it becomes a file name under
the cache folder, so only [A-Za-z0-9._-] is allowed, starting with a letter or digit.
"""
import collections
import ctypes
import json
import os
import re
import stat
import subprocess
import sys
import threading
import time

# ---- what the Frame has ------------------------------------------------------------

FFMPEG = "/usr/bin/ffmpeg" if os.path.exists("/usr/bin/ffmpeg") else "ffmpeg"
FRAMETOP_UNIT = "frametop-desktop"  # the user unit that runs the desktop
REMOTE_MARKER = "remote-capable"  # in Frametop's runtime dir while Remote Access is on
FAKE_INPUT_INTERFACE = "org_kde_kwin_fake_input"
RECORD_WORK = os.path.join(".cache", "frame-control", "frametop-video")
CACHE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")

REMOTE_OFF = ("Frametop Remote Access is off. Turn it on in Frametop's settings, on the "
              "Frame, to see and control its screens.")


class FrametopError(RuntimeError):
    """A problem worth a sentence on stderr (the page shows it), not a traceback."""


# ---- finding Frametop's session ----------------------------------------------------

def runtime_dir():
    """Our runtime dir, where Frametop's own one lives beside it."""
    return f"/run/user/{os.getuid()}"


def frametop_dir():
    """Frametop's runtime dir (/run/user/<uid>/frametop), or '' if it isn't there."""
    folder = os.path.join(runtime_dir(), "frametop")
    return folder if os.path.isdir(folder) else ""


def _read_environ(pid):
    """A process's environment, or {} when /proc doesn't let us read it."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as handle:
            raw = handle.read()
    except OSError:
        return {}
    found = {}
    for item in raw.split(b"\0"):
        key, equals, value = item.partition(b"=")
        if equals:
            found[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return found


def _read_text(path):
    try:
        with open(path, "r", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def _process_ids():
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            yield int(entry)


def frametop_processes():
    """(pid, env, cgroup) for the readable processes in Frametop's runtime dir."""
    folder = frametop_dir()
    if not folder:
        return []
    found = []
    for pid in _process_ids():
        environment = _read_environ(pid)
        if environment.get("XDG_RUNTIME_DIR") != folder:
            continue
        found.append((pid, environment, _read_text(f"/proc/{pid}/cgroup")))
    return found


def _systemctl_active():
    """Whether systemd says Frametop's unit is active ('' when it can't tell)."""
    environment = dict(os.environ, XDG_RUNTIME_DIR=runtime_dir())
    environment.pop("DBUS_SESSION_BUS_ADDRESS", None)  # the host user bus, not Frametop's
    try:
        result = subprocess.run(["systemctl", "--user", "show", FRAMETOP_UNIT, "-p", "ActiveState"],
                                env=environment, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    line = result.stdout.strip()
    return line.partition("=")[2] if line.startswith("ActiveState=") else ""


def desktop_running():
    """Whether the Frametop desktop is up: its unit is active or its own processes are."""
    if _systemctl_active() == "active":
        return True
    for pid, _environment, _cgroup in frametop_processes():
        if _read_text(f"/proc/{pid}/comm").strip() in ("ft-screens", "kwin_wayland", "plasmashell"):
            return True
    return False


def _bus_path(address):
    """The socket path in a dbus address ("unix:path=/tmp/dbus-x,guid=..."), or ''."""
    marker = "unix:path="
    if marker not in address:
        return ""
    return address.split(marker, 1)[1].split(",", 1)[0].split(";", 1)[0]


def _bus_sockets():
    """/tmp dbus sockets of ours, newest first: the desktop's bus lands in /tmp."""
    found = []
    try:
        names = os.listdir("/tmp")
    except OSError:
        return []
    for name in names:
        if not name.startswith("dbus-"):
            continue
        path = os.path.join("/tmp", name)
        try:
            info = os.stat(path)
        except OSError:
            continue
        if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid():
            found.append((info.st_mtime, path))
    return [path for _mtime, path in sorted(found, reverse=True)]


def _bus_has_kwin(path):
    """Whether this bus is Frametop's: a KWin owns a name on it."""
    try:
        import dbus
        bus = dbus.bus.BusConnection("unix:path=" + path)
        return bool(bus.name_has_owner("org.kde.KWin"))
    except Exception:
        return False


def session_env():
    """The Frametop desktop's environment: its bus, Wayland socket, X display and authority.

    Read from the processes in its runtime dir, preferring the ones systemd put in its
    unit (and whose bus socket is real), because older processes can share the runtime
    dir. Anything missing is filled in from the runtime dir's files.
    """
    folder = frametop_dir()
    if not folder:
        raise FrametopError("Frametop isn't running on the Frame.")
    candidates = []
    for pid, environment, cgroup in frametop_processes():
        if not (environment.get("DBUS_SESSION_BUS_ADDRESS") or environment.get("WAYLAND_DISPLAY")):
            continue
        score = 0
        if FRAMETOP_UNIT in cgroup:
            score += 8
        if os.path.exists(_bus_path(environment.get("DBUS_SESSION_BUS_ADDRESS", ""))):
            score += 4
        if environment.get("WAYLAND_DISPLAY"):
            score += 2
        authority = environment.get("XAUTHORITY", "")
        if authority and os.path.exists(authority):
            score += 1
        if environment.get("DISPLAY"):
            score += 1
        candidates.append((score, pid, environment))
    if not candidates:
        raise FrametopError("Couldn't find the Frametop desktop's session on the Frame.")
    candidates.sort(key=lambda item: item[0], reverse=True)
    session = dict(candidates[0][2])

    environment = dict(os.environ)
    for key in ("XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS"):
        if session.get(key):
            environment[key] = session[key]

    environment["XDG_RUNTIME_DIR"] = folder
    wayland = environment.get("WAYLAND_DISPLAY", "")
    if not wayland or not os.path.exists(os.path.join(folder, wayland)):
        sockets = sorted(name for name in os.listdir(folder)
                         if name.startswith("wayland-") and not name.endswith(".lock"))
        environment["WAYLAND_DISPLAY"] = sockets[0] if sockets else "wayland-0"
    environment.setdefault("DISPLAY", ":3")
    authority = environment.get("XAUTHORITY", "")
    if not authority or not os.path.exists(authority):
        files = [os.path.join(folder, name) for name in os.listdir(folder) if name.startswith("xauth_")]
        if files:
            environment["XAUTHORITY"] = max(files, key=os.path.getmtime)
    if not os.path.exists(_bus_path(environment.get("DBUS_SESSION_BUS_ADDRESS", ""))):
        for path in _bus_sockets():
            if _bus_has_kwin(path):
                environment["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + path
                break
    environment.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    return environment


def ready_env():
    """The desktop's environment, once it is clear there is a desktop we may use."""
    folder = frametop_dir()
    if not folder:
        raise FrametopError("Frametop isn't running on the Frame.")
    if not os.path.exists(os.path.join(folder, REMOTE_MARKER)):
        raise FrametopError(REMOTE_OFF)
    return session_env()


# ---- its screens -------------------------------------------------------------------

def screens(environment):
    """Connected, enabled Frametop outputs, with the size of their current mode.

    kscreen-doctor describes a mode by id and the output by its current mode id, and
    also lists the disabled float-slot outputs (WL-2..WL-9, 640x480); only real screens
    are returned, in the desktop's order.
    """
    try:
        result = subprocess.run(["kscreen-doctor", "-j"], env=environment,
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as error:
        raise FrametopError(f"Couldn't read Frametop's screens ({error}).")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise FrametopError("Couldn't read Frametop's screens"
                            + (f": {detail[-1]}" if detail else "."))
    try:
        report = json.loads(result.stdout)
    except ValueError:
        raise FrametopError("Couldn't read Frametop's screens (kscreen-doctor gave no JSON).")
    found = []
    for output in report.get("outputs") or []:
        if not isinstance(output, dict) or not output.get("connected") or not output.get("enabled"):
            continue
        name = str(output.get("name") or "")
        if not name:
            continue
        modes = {str(mode.get("id")): mode for mode in output.get("modes") or []
                 if isinstance(mode, dict)}
        mode = modes.get(str(output.get("currentModeId")))
        size = (mode or {}).get("size") or {}
        try:
            width, height = int(size["width"]), int(size["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue
        position = output.get("pos") or {}
        try:
            x, y = int(position.get("x") or 0), int(position.get("y") or 0)
        except (TypeError, ValueError):
            x, y = 0, 0
        found.append({"name": name, "width": width, "height": height, "x": x, "y": y})
    return found


def screen_or_error(name, environment):
    """The named screen's geometry, or a sentence listing the ones there are."""
    found = screens(environment)
    for screen in found:
        if screen["name"] == name:
            return screen
    names = ", ".join(screen["name"] for screen in found) or "none"
    raise FrametopError(f"Frametop has no screen {name!r} (screens: {names}).")


def status():
    """What the page needs to know: is the desktop up, is Remote Access on, which screens."""
    folder = frametop_dir()
    remote = bool(folder) and os.path.exists(os.path.join(folder, REMOTE_MARKER))
    answer = {"desktop": desktop_running(), "remote": remote, "why": "", "screens": []}
    if not answer["desktop"]:
        answer["why"] = "Frametop isn't running on the Frame."
        return answer
    if not remote:
        answer["why"] = REMOTE_OFF
        return answer
    try:
        environment = session_env()
        answer["screens"] = screens(environment)
        if not answer["screens"]:
            answer["why"] = "The Frametop desktop has no screens turned on."
    except FrametopError as error:
        answer["why"] = str(error)
    return answer


# ---- one frame from KWin's own screenshot interface --------------------------------

class Capture:
    """org.kde.KWin.ScreenShot2 on the Frametop desktop's own bus.

    KWin writes one screen's pixels into a pipe while we read the other end on a
    thread, then the method returns a dict describing them: width, height, stride and
    "raw" BGRA (format 5) at native resolution. The pipe is read to EOF, so a whole
    frame is always there when the thread joins.
    """

    BGRA = 5

    def __init__(self, environment, screen):
        try:
            import dbus
        except ImportError:
            raise FrametopError("Frametop capture needs python3-dbus on the Frame.")
        self.dbus = dbus
        self.screen = screen
        address = environment.get("DBUS_SESSION_BUS_ADDRESS", "")
        if not address:
            raise FrametopError("Couldn't find Frametop's DBus session bus.")
        try:
            self.bus = dbus.bus.BusConnection(address)
            self.interface = dbus.Interface(
                self.bus.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2"),
                "org.kde.KWin.ScreenShot2")
        except dbus.exceptions.DBusException as error:
            raise FrametopError(f"Couldn't reach Frametop's screen capture: {_dbus_message(error)}")

    def frame(self, include_cursor=True):
        """(BGRA bytes, width, height) of one frame, cursor included unless told not to."""
        dbus = self.dbus
        read_fd, write_fd = os.pipe()
        chunks = []

        def read_all():
            with os.fdopen(read_fd, "rb", buffering=0) as pipe:
                while True:
                    chunk = pipe.read(1 << 20)
                    if not chunk:
                        break
                    chunks.append(chunk)

        reader = threading.Thread(target=read_all, name="frametop-capture", daemon=True)
        reader.start()
        options = dbus.Dictionary({"include-cursor": bool(include_cursor),
                                   "native-resolution": True}, signature="sv")
        try:
            meta = self.interface.CaptureScreen(self.screen, options,
                                                dbus.types.UnixFd(write_fd))
        except dbus.exceptions.DBusException as error:
            name = _dbus_name(error)
            if "NoAuthorized" in name:
                raise FrametopError(REMOTE_OFF)
            if "NoSuchScreen" in name:
                raise FrametopError(f"Frametop has no screen {self.screen!r} any more.")
            raise FrametopError(f"Frametop's screen capture failed: {_dbus_message(error)}")
        finally:
            try:
                os.close(write_fd)
            except OSError:
                pass
        reader.join(timeout=30)
        if reader.is_alive():
            raise FrametopError("Frametop's screen capture didn't finish.")
        width, height = int(meta["width"]), int(meta["height"])
        stride, pixel_format = int(meta["stride"]), int(meta.get("format", self.BGRA))
        data = b"".join(chunks)
        if pixel_format != self.BGRA:
            raise FrametopError(f"Frametop's screen capture came in pixel format {pixel_format},"
                                " not raw BGRA.")
        if len(data) < stride * height:
            raise FrametopError("Frametop's screen capture came back short"
                                f" ({len(data)} of {stride * height} bytes).")
        if stride != width * 4:
            # ffmpeg's rawvideo has no stride: drop each row's padding.
            data = b"".join(data[row * stride:row * stride + width * 4] for row in range(height))
        else:
            data = data[:stride * height]
        return data, width, height


def _dbus_name(error):
    try:
        return error.get_dbus_name() or ""
    except AttributeError:
        return ""


def _dbus_message(error):
    """The useful half of a dbus error: its name or its text."""
    name = _dbus_name(error)
    try:
        text = str(error)
    except Exception:
        text = ""
    return name or text or "unknown error"


# ---- ffmpeg ------------------------------------------------------------------------

class Tail:
    """A thread keeping the last few lines ffmpeg said, for error messages."""

    def __init__(self, stream, keep=12):
        self.lines = collections.deque(maxlen=keep)
        self.thread = threading.Thread(target=self._read, args=(stream,), name="frametop-stderr",
                                       daemon=True)
        self.thread.start()

    def _read(self, stream):
        for line in stream:
            self.lines.append(line.decode("utf-8", "replace").rstrip())

    def text(self):
        return " ".join(line for line in self.lines if line).strip()

    def join(self):
        self.thread.join(timeout=2)


def _suffix(tail):
    text = tail.text()
    return f": {text}" if text else "."


def _start_ffmpeg(command, environment, capture_stdout=False):
    """Start ffmpeg; its stderr is ours to read, its stdout only when asked for."""
    try:
        return subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE if capture_stdout else None,
                                env=environment)
    except OSError:
        raise FrametopError("ffmpeg isn't installed on the Frame.")


def _stop_ffmpeg(process):
    """End ffmpeg: close what it reads (so it finishes), then terminate it if it lingers."""
    try:
        if process.stdin:
            process.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _png(data, width, height, environment):
    """PNG bytes for one raw BGRA frame."""
    command = [FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
               "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-i", "-",
               "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"]
    process = _start_ffmpeg(command, environment, capture_stdout=True)
    try:
        png, error = process.communicate(data, timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise FrametopError("ffmpeg took too long to make the screenshot.")
    if process.returncode != 0 or not png.startswith(b"\x89PNG"):
        detail = (error or b"").decode("utf-8", "replace").strip()
        raise FrametopError("ffmpeg couldn't make the screenshot"
                            + (f": {detail}" if detail else "."))
    return png


def stream_command(width, height, limit, fps):
    """The encoder for live video: like ui/server.py's panel stream, size 720 by default.

    The picture is fitted to `limit` (never enlarged past the screen) and padded to an
    even size, H.264 Annex B with an access unit delimiter per frame; the page splits
    the stream on those.
    """
    rate = 3 if limit <= 720 else 6  # Mbit/s
    scale = f"scale=-2:'trunc(min({limit},ih)/2)*2',format=yuv420p"
    return [FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-r", str(fps),
            "-i", "-", "-vf", scale, "-c:v", "libx264", "-preset", "ultrafast",
            "-tune", "zerolatency", "-g", str(fps * 2), "-bf", "0",
            "-b:v", f"{rate}M", "-maxrate", f"{rate}M", "-bufsize", f"{rate // 2 or 1}M",
            "-x264-params", "aud=1:repeat-headers=1", "-f", "h264", "-"]


def record_command(width, height, fps, output):
    """The encoder for a recording: an .mp4 the page can play, at the screen's own size."""
    return [FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-r", str(fps),
            "-i", "-", "-vf", f"scale={width}:{height},format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "8M", "-maxrate", "8M",
            "-bufsize", "16M", "-g", str(fps * 2), "-movflags", "+faststart", str(output)]


def _watch_stdin(stop):
    """Set `stop` when the ssh channel closes (our stdin reaches EOF)."""
    def watch():
        while True:
            try:
                chunk = os.read(0, 65536)
            except OSError:
                break
            if not chunk:
                break
        stop.set()

    threading.Thread(target=watch, name="frametop-stdin", daemon=True).start()


def _pump(capture, process, fps, stop, data):
    """Feed one frame per 1/fps of wall time to ffmpeg, until `stop` or its pipe closes.

    ScreenShot2 takes about 30 ms a frame, so at 30 fps capture can't always keep up.
    Both the page (which counts every access unit as 1/fps of time) and a recording
    (whose length should match the wall clock) need a steady rate, so a late frame is
    sent again for the slots that were missed rather than the timeline being shortened.
    """
    interval = 1.0 / fps
    started = time.monotonic()
    written = 0
    while not stop.is_set():
        try:
            process.stdin.write(data)
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            return
        written += 1
        due = int((time.monotonic() - started) / interval) + 1
        while written < due:  # capture fell behind: repeat this frame for those slots
            try:
                process.stdin.write(data)
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                return
            written += 1
        wait = started + written * interval - time.monotonic()
        if wait > 0:  # capture is faster than fps: hold back the next frame
            time.sleep(wait)
        data = capture.frame()[0]


# ---- modes -------------------------------------------------------------------------

def shot(name, include_cursor, environment):
    """Write one PNG of the screen to stdout."""
    screen_or_error(name, environment)
    data, width, height = Capture(environment, name).frame(include_cursor)
    png = _png(data, width, height, environment)
    sys.stdout.buffer.write(png)
    sys.stdout.buffer.flush()


def stream(name, limit, fps, environment):
    """Raw H.264 Annex B of the screen on stdout, until our stdin closes."""
    screen = screen_or_error(name, environment)
    capture = Capture(environment, name)
    data, width, height = capture.frame()
    process = _start_ffmpeg(stream_command(width, height, min(limit, height), fps), environment)
    tail = Tail(process.stderr)
    stop = threading.Event()
    _watch_stdin(stop)
    try:
        _pump(capture, process, fps, stop, data)
    finally:
        _stop_ffmpeg(process)
        tail.join()
    if process.returncode not in (0, -15, -9) and not stop.is_set():
        raise FrametopError("ffmpeg stopped early" + _suffix(tail))


def record(screen, name, fps, environment):
    """Record one screen to ~/.cache/frame-control/frametop-video/<name>.mp4.

    Prints "started" (flushed) as soon as ffmpeg is up, then captures at `fps` paced by
    the wall clock. On stdin EOF ffmpeg is finished and this prints "exit N", which is
    what ui/server.py waits for before it copies the file. `name` is only the file name
    (ui/frame_clips.py's rec-...), the screen is separate.
    """
    if not CACHE_NAME.fullmatch(name):
        raise FrametopError("recording name may only use letters, digits, dots, dashes and"
                            " underscores.")
    folder = os.path.join(os.path.expanduser("~"), RECORD_WORK)
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as error:
        raise FrametopError(f"Couldn't make {folder}: {error}")
    output = os.path.join(folder, name + ".mp4")
    screen_or_error(screen, environment)
    capture = Capture(environment, screen)
    data, width, height = capture.frame()
    process = _start_ffmpeg(record_command(width, height, fps, output), environment)
    tail = Tail(process.stderr)
    print("started", flush=True)
    stop = threading.Event()
    _watch_stdin(stop)
    try:
        _pump(capture, process, fps, stop, data)
    finally:
        _stop_ffmpeg(process)
        tail.join()
    print(f"exit {process.returncode}", flush=True)
    if process.returncode != 0 and not stop.is_set():
        raise FrametopError("ffmpeg couldn't record the Frametop screen" + _suffix(tail))


# ---- input through org_kde_kwin_fake_input -----------------------------------------

# libwayland does not export its registry helpers (they are static inline in the
# header), so the registry proxy and the global are made through
# wl_proxy_marshal_flags and a hand-built wl_interface. Every pointer argument must be
# a ctypes.c_void_p: a plain Python int is truncated to 32 bits and segfaults.
REQUESTS = [("authenticate", "ss"), ("pointer_motion", "ff"), ("button", "uu"),
            ("axis", "uf"), ("touch_down", "uff"), ("touch_motion", "uff"), ("touch_up", "u"),
            ("touch_cancel", ""), ("touch_frame", ""), ("pointer_motion_absolute", "ff"),
            ("keyboard_key", "uu"), ("destroy", "")]
OPCODES = {name: index for index, (name, _signature) in enumerate(REQUESTS)}
GLOBAL_FN = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                             ctypes.c_char_p, ctypes.c_uint32)
REMOVE_FN = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32)
_KEEP = []  # ctypes arrays and interfaces must outlive the proxy that points at them
_WAYLAND = None


class WlMessage(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("signature", ctypes.c_char_p),
                ("types", ctypes.POINTER(ctypes.c_void_p))]


class WlInterface(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("version", ctypes.c_int),
                ("method_count", ctypes.c_int), ("methods", ctypes.POINTER(WlMessage)),
                ("event_count", ctypes.c_int), ("events", ctypes.POINTER(WlMessage))]


class Listener(ctypes.Structure):
    _fields_ = [("global", GLOBAL_FN), ("global_remove", REMOVE_FN)]


def wayland():
    """libwayland-client and libc, with the prototypes used below (loaded once)."""
    global _WAYLAND
    if _WAYLAND is not None:
        return _WAYLAND
    try:
        lib = ctypes.CDLL("libwayland-client.so.0")
        libc = ctypes.CDLL(None)
    except OSError:
        raise FrametopError("Couldn't load libwayland-client on the Frame.")
    libc.dlsym.restype = ctypes.c_void_p
    libc.dlsym.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.wl_display_connect.restype = ctypes.c_void_p
    lib.wl_display_connect.argtypes = [ctypes.c_char_p]
    lib.wl_display_roundtrip.restype = ctypes.c_int
    lib.wl_display_roundtrip.argtypes = [ctypes.c_void_p]
    lib.wl_display_flush.restype = ctypes.c_int
    lib.wl_display_flush.argtypes = [ctypes.c_void_p]
    lib.wl_display_disconnect.restype = None
    lib.wl_display_disconnect.argtypes = [ctypes.c_void_p]
    lib.wl_proxy_marshal_flags.restype = ctypes.c_void_p
    lib.wl_proxy_add_listener.restype = ctypes.c_int
    lib.wl_proxy_add_listener.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    lib.wl_proxy_get_version.restype = ctypes.c_uint32
    lib.wl_proxy_get_version.argtypes = [ctypes.c_void_p]
    _WAYLAND = (lib, libc)
    return _WAYLAND


def _interface():
    """A wl_interface (and its method table) for org_kde_kwin_fake_input, kept alive."""
    messages = (WlMessage * len(REQUESTS))()
    keep = []
    for index, (name, signature) in enumerate(REQUESTS):
        types = (ctypes.c_void_p * max(1, len(signature)))()  # every argument is a primitive
        keep.append(types)
        messages[index].name = name.encode()
        messages[index].signature = signature.encode()
        messages[index].types = ctypes.cast(types, ctypes.POINTER(ctypes.c_void_p))
    interface = WlInterface(name=FAKE_INPUT_INTERFACE.encode(), version=5,
                            method_count=len(REQUESTS), methods=messages,
                            event_count=0, events=None)
    keep.extend((messages, interface))
    _KEEP.extend(keep)
    return interface


def fixed(value):
    """Wayland's 24.8 fixed point."""
    return int(round(float(value) * 256.0))


# Linux evdev codes, as the page sends them.
BUTTONS = {"left": 0x110, "right": 0x111, "middle": 0x112}
SHIFT = 42
ROW_KEYS = [("1234567890-=", "!@#$%^&*()_+", 2), ("qwertyuiop[]", "QWERTYUIOP{}", 16),
            ("asdfghjkl;'`", 'ASDFGHJKL:"~', 30), ("\\zxcvbnm,./", "|ZXCVBNM<>?", 43)]
ASCII = {" ": (57, False), "\n": (28, False), "\t": (15, False)}
for _plain, _shifted, _first in ROW_KEYS:
    for _index, (_lower, _upper) in enumerate(zip(_plain, _shifted)):
        ASCII[_lower] = (_first + _index, False)
        ASCII[_upper] = (_first + _index, True)


class FakeInput:
    """org_kde_kwin_fake_input bound on the Frametop desktop's Wayland display.

    Requests are marshalled and then flushed once per batch; the interface's own
    version is used for the proxy (5, the newest request we call is in it).
    """

    def __init__(self, environment):
        lib, libc = wayland()
        self.lib = lib
        self.display = None
        self.registry = None
        self.proxy = None
        self.keys = set()
        self.buttons = set()
        # wl_display_connect reads these from the environment, not from an argument.
        for key in ("XDG_RUNTIME_DIR", "WAYLAND_DISPLAY"):
            if environment.get(key):
                os.environ[key] = environment[key]
        try:
            self._connect(lib, libc)
        except FrametopError:
            self.close()
            raise

    def _connect(self, lib, libc):
        self.display = lib.wl_display_connect(None)
        if not self.display:
            raise FrametopError("Couldn't connect to Frametop's Wayland display."
                                " Is the desktop running?")
        registry_interface = libc.dlsym(lib._handle, b"wl_registry_interface")
        if not registry_interface:
            raise FrametopError("libwayland didn't have wl_registry_interface.")
        self.registry = lib.wl_proxy_marshal_flags(
            ctypes.c_void_p(self.display), 1, ctypes.c_void_p(registry_interface), 1, 0,
            ctypes.c_void_p(None))
        if not self.registry:
            raise FrametopError("Couldn't get Frametop's Wayland registry.")
        self.globals = []
        self.listener = Listener(GLOBAL_FN(self._global), REMOVE_FN(self._remove))
        if lib.wl_proxy_add_listener(ctypes.c_void_p(self.registry),
                                     ctypes.addressof(self.listener),
                                     ctypes.c_void_p(None)) != 0:
            raise FrametopError("Couldn't listen to Frametop's Wayland registry.")
        if lib.wl_display_roundtrip(self.display) < 0:
            raise FrametopError("Frametop's Wayland display didn't answer.")
        matches = [item for item in self.globals if item[1] == FAKE_INPUT_INTERFACE]
        if not matches:
            raise FrametopError(REMOTE_OFF)
        name, version = matches[0][0], min(matches[0][2], 5)
        interface = _interface()
        self.proxy = lib.wl_proxy_marshal_flags(
            ctypes.c_void_p(self.registry), 0, ctypes.c_void_p(ctypes.addressof(interface)),
            version, 0, name, FAKE_INPUT_INTERFACE.encode(), version, ctypes.c_void_p(None))
        if not self.proxy:
            raise FrametopError(f"Couldn't bind {FAKE_INPUT_INTERFACE}.")
        self.version = lib.wl_proxy_get_version(self.proxy)
        self.request("authenticate", b"Frame Control", b"view and control the Frametop desktop")

    def _global(self, _data, _registry, name, interface, version):
        self.globals.append((name, interface.decode() if interface else "", version))

    def _remove(self, _data, _registry, _name):
        pass

    def request(self, name, *arguments):
        self.lib.wl_proxy_marshal_flags(ctypes.c_void_p(self.proxy), OPCODES[name],
                                        ctypes.c_void_p(None), self.version, 0, *arguments)

    def flush(self):
        if self.lib.wl_display_flush(self.display) < 0:
            raise FrametopError("Frametop closed the input connection.")

    def pointer_absolute(self, x, y):
        self.request("pointer_motion_absolute", fixed(x), fixed(y))

    def pointer_motion(self, dx, dy):
        self.request("pointer_motion", fixed(dx), fixed(dy))

    def button(self, code, down):
        self.request("button", code, 1 if down else 0)
        if down:
            self.buttons.add(code)
        else:
            self.buttons.discard(code)

    def axis(self, which, amount):
        self.request("axis", which, fixed(amount))

    def key(self, code, down):
        self.request("keyboard_key", code, 1 if down else 0)
        if down:
            self.keys.add(code)
        else:
            self.keys.discard(code)

    def text(self, message):
        # Characters that a US layout can't produce are skipped, as fv_fake2.py does.
        for character in message:
            typed = ASCII.get(character)
            if typed is None:
                continue
            code, shift = typed
            if shift:
                self.request("keyboard_key", SHIFT, 1)
            self.request("keyboard_key", code, 1)
            self.request("keyboard_key", code, 0)
            if shift:
                self.request("keyboard_key", SHIFT, 0)

    def release_all(self):
        """Let go of every key and button still down, so nothing stays pressed."""
        for code in sorted(self.keys):
            self.request("keyboard_key", code, 0)
        for code in sorted(self.buttons):
            self.request("button", code, 0)
        self.keys.clear()
        self.buttons.clear()
        try:
            self.flush()
        except FrametopError:
            pass

    def close(self):
        if self.proxy:
            try:
                self.request("destroy")
                self.lib.wl_display_flush(self.display)
            except FrametopError:
                pass
            self.proxy = None
        if self.display:
            self.lib.wl_display_disconnect(self.display)
            self.display = None


# ---- events from the server --------------------------------------------------------

def number(value, name, limit=100000.0):
    """A finite number from the server, clamped to +-limit."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise FrametopError(f"{name} must be a number.")
    return max(-limit, min(limit, float(value)))


def fraction(value, name):
    """A position on a screen, clamped to its edges."""
    return max(0.0, min(1.0, number(value, name, 1.0)))


def apply_event(fake, found, event):
    """Send one event from the page; raises FrametopError for anything malformed."""
    if not isinstance(event, dict):
        raise FrametopError("an event must be an object.")
    handled = False
    if "fx" in event or "fy" in event:
        if "fx" not in event or "fy" not in event:
            raise FrametopError("a position needs both fx and fy.")
        name = event.get("screen") or found[0]["name"]
        screen = next((item for item in found if item["name"] == name), None)
        if screen is None:
            names = ", ".join(item["name"] for item in found) or "none"
            raise FrametopError(f"no screen {name!r} (screens: {names}).")
        fake.pointer_absolute(screen["x"] + fraction(event["fx"], "fx") * screen["width"],
                              screen["y"] + fraction(event["fy"], "fy") * screen["height"])
        handled = True
    if "dx" in event or "dy" in event:
        fake.pointer_motion(number(event.get("dx", 0), "dx", 2000),
                            number(event.get("dy", 0), "dy", 2000))
        handled = True
    if "button" in event:
        button = event["button"]
        if button not in BUTTONS:
            raise FrametopError("button must be left, right or middle.")
        fake.button(BUTTONS[button], event.get("down") is not False)
        handled = True
    if "scroll" in event:
        scroll = event["scroll"]
        if not isinstance(scroll, (list, tuple)) or len(scroll) != 2:
            raise FrametopError("scroll must be [dx, dy].")
        horizontal = number(scroll[0], "scroll x", 5000)
        vertical = number(scroll[1], "scroll y", 5000)
        if horizontal:
            fake.axis(1, horizontal)  # 1 = horizontal
        if vertical:
            fake.axis(0, vertical)  # 0 = vertical
        handled = True
    if "key" in event:
        code = event["key"]
        if isinstance(code, bool) or not isinstance(code, int) or not 0 < code < 768:
            raise FrametopError("key must be a Linux key code.")
        fake.key(code, event.get("down") is not False)
        handled = True
    if "text" in event:
        text = event["text"]
        if not isinstance(text, str):
            raise FrametopError("text must be a string.")
        fake.text(text[:500])
        handled = True
    if not handled:
        raise FrametopError("the event has nothing to do.")
    return handled


def reply(payload):
    print(json.dumps(payload), flush=True)


def apply_batch(fake, found, line):
    """Apply one line of events and answer it; never lets a bad batch end the loop."""
    line = line.strip()
    if not line:
        return
    try:
        batch = json.loads(line.decode("utf-8", "replace"))
    except ValueError:
        reply({"error": "that line wasn't JSON."})
        return
    events = batch.get("events") if isinstance(batch, dict) else batch
    if not isinstance(events, list):
        reply({"error": "a batch must be a list of events."})
        return
    sent = 0
    for index, event in enumerate(events):
        try:
            apply_event(fake, found, event)
        except (FrametopError, ValueError, KeyError, TypeError) as error:
            reply({"error": f"event {index + 1}: {error}", "sent": sent})
            break
        sent += 1
    else:
        reply({"sent": sent})
    try:
        fake.flush()
    except FrametopError:
        pass


def input_loop():
    """The long-lived event loop the page feeds; prints ready, then sent/error lines."""
    try:
        environment = ready_env()
        found = screens(environment)
        if not found:
            raise FrametopError("The Frametop desktop has no screens turned on.")
    except FrametopError as error:
        print(json.dumps({"state": "error", "message": str(error)}), flush=True)
        return 1
    try:
        fake = FakeInput(environment)
    except FrametopError as error:
        print(json.dumps({"state": "error", "message": str(error)}), flush=True)
        return 1
    try:
        print(json.dumps({"state": "ready"}), flush=True)
        pending = b""
        while True:
            chunk = os.read(0, 65536)
            if not chunk:
                return 0  # the server closed the channel
            *lines, pending = (pending + chunk).split(b"\n")
            for line in lines:
                apply_batch(fake, found, line)
    except FrametopError as error:
        print(json.dumps({"state": "error", "message": str(error)}), flush=True)
        return 1
    finally:
        fake.release_all()
        fake.close()


# ---- the command line --------------------------------------------------------------

def parse_options(arguments, boolean=(), valued=()):
    """(rest, options) from --name value / --name=value / --flag arguments."""
    rest, options, index = [], {}, 0
    while index < len(arguments):
        argument = arguments[index]
        if argument.startswith("--"):
            name, equals, inline = argument[2:].partition("=")
            name = name.replace("-", "_")
            if name in boolean:
                if equals:
                    raise FrametopError(f"--{name} takes no value.")
                options[name] = True
            elif name in valued:
                if equals:
                    options[name] = inline
                elif index + 1 < len(arguments):
                    index += 1
                    options[name] = arguments[index]
                else:
                    raise FrametopError(f"--{name} needs a value.")
            else:
                raise FrametopError(f"unknown option {argument}.")
        else:
            rest.append(argument)
        index += 1
    return rest, options


def whole_number(value, name, low, high, default):
    """An integer option within range (or the default when it wasn't given)."""
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise FrametopError(f"{name} must be a whole number.")
    if not low <= number <= high:
        raise FrametopError(f"{name} must be between {low} and {high}.")
    return number


def main(arguments):
    mode = arguments[0] if arguments else "input"
    if mode == "status":
        print(json.dumps(status()), flush=True)
        return 0
    if mode == "input":
        return input_loop()
    if mode == "shot":
        rest, options = parse_options(arguments[1:], boolean=("no_cursor",))
        if len(rest) != 1:
            raise FrametopError("usage: shot <screen> [--no-cursor]")
        shot(rest[0], not options.get("no_cursor", False), ready_env())
        return 0
    if mode == "stream":
        rest, options = parse_options(arguments[1:], valued=("height", "fps"))
        if len(rest) != 1:
            raise FrametopError("usage: stream <screen> [--height 720] [--fps 30]")
        limit = whole_number(options.get("height"), "height", 2, 4320, 720)
        fps = whole_number(options.get("fps"), "fps", 1, 60, 30)
        stream(rest[0], limit, fps, ready_env())
        return 0
    if mode == "record":
        rest, options = parse_options(arguments[1:], valued=("name", "fps"))
        if len(rest) != 1 or not options.get("name"):
            raise FrametopError("usage: record <screen> --name NAME [--fps 30]")
        fps = whole_number(options.get("fps"), "fps", 1, 60, 30)
        record(rest[0], options["name"], fps, ready_env())
        return 0
    raise FrametopError(f"unknown mode {mode!r} (expected status, shot, stream, input or record).")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except FrametopError as error:
        print(error, file=sys.stderr, flush=True)
        sys.exit(1)
