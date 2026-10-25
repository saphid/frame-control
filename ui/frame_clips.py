#!/usr/bin/env python3
"""Video from the headset: recordings of what it shows, with its sound, and Steam's own clips.

Two halves share this file.

On the computer, server.py builds the shell commands below, runs them over SSH and
copies the finished .mp4 to ~/Videos/SteamFrame (Recorder does a recording from Start
to the copy; export_clip does a Steam clip). Nothing here needs ffmpeg on the computer.

On the Frame, this file runs as `python3 - list` or `python3 - export ID` (sent on
stdin, like frame_steam.py, so stdlib only): it lists Steam's game recordings and
stitches one into a single .mp4 with SteamOS's ffmpeg, copying the streams as they are.
It prints one JSON object, or {"error": ...}.

Steam's game recording keeps DASH segments, one folder per recording session:

    ~/.local/share/Steam/userdata/<account>/gamerecordings/
        video/bg_<appid>_<YYYYMMDD>_<HHMMSS>/            background recording
        clips/clip_<appid>_<YYYYMMDD>_<HHMMSS>/video/bg_<appid>_<...>/   a saved clip
            session.mpd
            init-stream0.m4s  chunk-stream0-00001.m4s  chunk-stream0-00002.m4s ...
            init-stream1.m4s  chunk-stream1-00001.m4s ...

Each stream's init segment followed by its chunks, in order, is a fragmented MP4 of
that stream. The folder names are as users and Steam's own files describe them; the
listing doesn't depend on them: any folder under clips/ or video/ (up to four levels)
holding init-stream*.m4s counts as a session.
"""
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# ---- where things go ---------------------------------------------------------

VIDEOS_DIR = Path.home() / "Videos" / "SteamFrame"  # on the computer, beside ~/Pictures/SteamFrame
# On the Frame, relative to its home: recordings in progress and stitched exports.
# Not /tmp: it's a RAM disk there, and a recording can be over a gigabyte.
WORK = ".cache/frame-control/video"

# ---- recording what the headset shows ------------------------------------------
#
# The same picture the live view streams: SteamVR's copy of the headset view in the
# v4l2loopback device, encoded with x264 (the hardware encoder crashes ffmpeg). The
# sound is the monitor of PipeWire's default output, read through its PulseAudio
# server: SteamOS's ffmpeg has the pulse device (the media player writes to it, see
# docs/vr-video.md). If it can't be read, the recording goes ahead without sound and
# says so. Both inputs are stamped with the wall clock: the camera device and the
# audio server would otherwise count from different clocks.

STREAM_DEVICE = "/dev/video99"
AUDIO_SOURCE = "@DEFAULT_MONITOR@"  # PulseAudio's name for the default output's monitor
MAX_SECONDS = 20 * 60
FPS = 30
VIDEO_RATE = 8  # Mbit/s at 1080p
AUDIO_RATE = 160  # kbit/s AAC
# Room for a full-length recording twice over (the .mkv, then the .mp4 made from it).
NEED_KB = (VIDEO_RATE * 1000 + AUDIO_RATE) * MAX_SECONDS // 8 * 2 + 512 * 1024
REC_NAME = re.compile(r"rec-\d{8}-\d{6}")


class ClipError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def recording_name(now=None):
    return time.strftime("rec-%Y%m%d-%H%M%S", time.localtime(now))


def probe_command(work=WORK):
    """Checks before a recording, run on the Frame: prints audio=1 or audio=0.

    One recording runs at a time, so anything left in the folder is from one that was
    cut off (the app quit, or the copy failed); it's removed to free the space."""
    return (f"set -u; export XDG_RUNTIME_DIR=${{XDG_RUNTIME_DIR:-/run/user/$(id -u)}}; "
            f"[ -e {STREAM_DEVICE} ] || {{ echo 'No headset view device ({STREAM_DEVICE}). Is SteamVR running?' >&2; exit 3; }}; "
            f"command -v ffmpeg >/dev/null || {{ echo 'ffmpeg is missing on the Frame' >&2; exit 3; }}; "
            f"d=\"$HOME/{work}\"; mkdir -p \"$d\" && rm -f \"$d\"/rec-*; "
            f"free=$(df -Pk \"$d\" | awk 'NR==2 {{print $4}}'); "
            f"[ \"${{free:-0}}\" -ge {NEED_KB} ] || {{ echo 'Not enough free space on the Frame to record: "
            f"it needs {NEED_KB // 1024 // 1024 + 1} GB' >&2; exit 4; }}; "
            f"if timeout 5 ffmpeg -hide_banner -loglevel error -nostdin -f pulse -i {AUDIO_SOURCE} -t 0.2 -f null - "
            f">/dev/null 2>&1; then echo audio=1; else echo audio=0; fi")


def record_command(name, audio, max_seconds=MAX_SECONDS, work=WORK):
    """The recording, run on the Frame through `bash -c`.

    ffmpeg runs in the background while the shell watches its stdin, which is the SSH
    channel: when that closes (Stop closed it, or the computer's ssh went away) the
    shell types q into ffmpeg's stdin, a FIFO, which makes it finish the file properly.
    Not a signal: SteamOS's ffmpeg (n7.0) catches SIGTERM and SIGINT and records on
    (seen on a Frame, build 20261015.6141207). If it's still there 10 s later it's
    killed. A recording that ends by itself (the time limit, an error) ends the wait
    too. The shell prints "started" once ffmpeg is running and "exit N" when it has gone."""
    if not REC_NAME.fullmatch(name):
        raise ValueError(f"bad recording name {name!r}")
    if not 1 <= max_seconds <= MAX_SECONDS:
        raise ValueError("max_seconds out of range")
    clock = "-thread_queue_size 1024 -use_wallclock_as_timestamps 1"
    inputs = f"{clock} -f v4l2 -video_size 1920x1080 -i {STREAM_DEVICE}"
    maps = "-map 0:v:0"
    codecs = (f"-vf fps={FPS},scale=-2:1080,format=yuv420p -c:v libx264 -preset ultrafast "
              f"-b:v {VIDEO_RATE}M -maxrate {VIDEO_RATE}M -bufsize {VIDEO_RATE * 2}M -g {FPS * 2}")
    if audio:
        inputs += f" {clock} -f pulse -i {AUDIO_SOURCE}"
        maps += " -map 1:a:0"
        codecs += f" -af aresample=async=1 -c:a aac -b:a {AUDIO_RATE}k"
    # ffmpeg's stdin is a FIFO the shell holds open on fd 3 (opening it waits for both
    # ends, so ffmpeg is started first); it's unlinked once both ends are open.
    script = (f"export XDG_RUNTIME_DIR=${{XDG_RUNTIME_DIR:-/run/user/$(id -u)}}; d=\"$HOME/{work}\"; "
              f"trap '' PIPE; c=\"$d/{name}.ctl\"; rm -f \"$c\"; mkfifo \"$c\" || exit 1; "
              f"ffmpeg -hide_banner -loglevel error -y {inputs} {maps} {codecs} -t {max_seconds} "
              f"\"$d/{name}.mkv\" <\"$c\" >/dev/null 2>\"$d/{name}.log\" & p=$!; "
              f"exec 3>\"$c\"; rm -f \"$c\"; "
              f"echo started; "
              f"while kill -0 $p 2>/dev/null; do read -r -t 1 _; r=$?; [ $r -eq 0 ] || [ $r -gt 128 ] || break; done; "
              f"kill -0 $p 2>/dev/null && printf q >&3 2>/dev/null; exec 3>&-; "
              f"i=0; while kill -0 $p 2>/dev/null && [ $i -lt 40 ]; do sleep 0.25; i=$((i+1)); done; "
              f"kill -0 $p 2>/dev/null && kill -KILL $p 2>/dev/null; wait $p; echo \"exit $?\"")
    return "bash -c " + shlex.quote(script)


def finish_command(name, work=WORK):
    """After the recording: make the .mp4 the computer gets (no re-encode), on the Frame."""
    if not REC_NAME.fullmatch(name):
        raise ValueError(f"bad recording name {name!r}")
    return (f"cd \"$HOME/{work}\" || exit 1; "
            f"[ -s {name}.mkv ] || {{ tail -c 2000 {name}.log >&2 2>/dev/null; echo 'The recording is empty' >&2; exit 1; }}; "
            f"ffmpeg -hide_banner -loglevel error -nostdin -y -i {name}.mkv -map 0 -c copy -movflags +faststart {name}.mp4 "
            f"&& rm -f {name}.mkv && wc -c < {name}.mp4")


def cleanup_command(name, work=WORK):
    if not REC_NAME.fullmatch(name):
        raise ValueError(f"bad recording name {name!r}")
    return f"rm -f \"$HOME/{work}/{name}\".*"


class Recorder:
    """One recording at a time, from Start to the .mp4 on this computer.

    The server supplies how to reach the Frame, so this can be tested without one:
      open_channel(command, stderr) -> Popen of `command` on the Frame, stdin and stdout pipes
      run(command, timeout) -> its stdout; raises on failure
      fetch(remote, local) copies a file from the Frame (a path relative to its home)
      start_thread(fn) starts fn in a thread that counts as headset work
      release(proc) forgets a channel once it has closed
    """

    def __init__(self, open_channel, run, fetch, start_thread, release=lambda proc: None, folder=None,
                 work=WORK, destination_label='~/Videos/SteamFrame'):
        self.open_channel, self.run, self.fetch = open_channel, run, fetch
        self.start_thread, self.release = start_thread, release
        self.folder = Path(folder) if folder else VIDEOS_DIR
        self.work, self.destination_label = work, destination_label
        self._lock = threading.Lock()
        self._state = {"state": "idle"}
        self._proc = None

    def status(self):
        with self._lock:
            s = dict(self._state)
        if s["state"] == "recording":
            s["elapsed"] = round(time.time() - s["started"], 1)
        return s

    def start(self):
        with self._lock:
            if self._state["state"] in ("starting", "recording", "stopping", "saving"):
                raise ClipError("Already recording, or still saving the last recording", 409)
            self._state = {"state": "starting"}
        try:
            out = self.run(probe_command() if self.work == WORK else probe_command(self.work), 30)
            audio = "audio=1" in out
            name = recording_name()
            errors = tempfile.TemporaryFile()
            proc = self.open_channel(record_command(name, audio) if self.work == WORK else
                                     record_command(name, audio, work=self.work), errors)
            lines = _line_reader(proc.stdout)
            first = _next_line(lines, 20)
            if first != "started":
                _end(proc)
                errors.seek(0)
                err = errors.read().decode(errors="replace").strip()
                errors.close()
                self.release(proc)
                raise ClipError(err or "The Frame didn't start recording")
        except BaseException as e:
            with self._lock:
                self._state = {"state": "failed", "error": str(e)}
            raise
        with self._lock:
            self._proc = proc
            self._state = {"state": "recording", "name": name, "audio": audio, "started": time.time(),
                           "limit": MAX_SECONDS}
        try:
            self.start_thread(lambda: self._watch(proc, name, audio, lines, errors))
        except BaseException:
            _end(proc)
            self.release(proc)
            with self._lock:
                self._state, self._proc = {"state": "failed", "error": "Couldn't follow the recording"}, None
            raise
        return dict(self.status(), message="Recording" + ("" if audio else
                    " without sound: the Frame's audio couldn't be read"))

    def stop(self):
        """Ends the recording; the copy to this computer carries on in the background."""
        with self._lock:
            if self._state["state"] != "recording":
                raise ClipError("Not recording", 409)
            self._state = dict(self._state, state="stopping")
            proc = self._proc
        _close(proc.stdin)  # the shell on the Frame sees EOF and stops ffmpeg
        return {"state": "stopping", "message": "Stopping the recording…"}

    def shutdown(self, timeout=30):
        """Finish an owned recording before a headset user service exits."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.status()['state']
            if state == 'recording':
                self.stop()
            elif state not in ('starting', 'stopping', 'saving'):
                break
            time.sleep(.2)
        return self.status()

    def _watch(self, proc, name, audio, lines, errors):
        # Waits for ffmpeg to finish: after Stop, or at the time limit (a margin
        # past it, so a stuck channel can't hold the recording open forever).
        deadline = time.time() + MAX_SECONDS + 60
        while True:
            stopping = self.status()["state"] == "stopping"
            line = _next_line(lines, 30 if stopping else 5)
            if line is None or line.startswith("exit "):
                break  # ffmpeg has gone and the file is finished
            if line == "" and (stopping or time.time() > deadline):
                break  # no answer within 30 s of Stop, or well past the limit: close the channel
        _end(proc)
        errors.close()
        self.release(proc)
        with self._lock:
            self._proc = None
            seconds = round(time.time() - self._state["started"])
            self._state = dict(self._state, state="saving")
        try:
            self.save(name)
            msg = f"Saved {name}.mp4 to {self.destination_label}" + ("" if audio else " (no sound)")
            state = {"state": "saved", "file": str(self.folder / f"{name}.mp4"), "audio": audio,
                     "seconds": seconds, "message": msg}
        except Exception as e:
            state = {"state": "failed", "error": f"Couldn't save the recording: {e}"}
        finally:
            try:
                self.run(cleanup_command(name) if self.work == WORK else cleanup_command(name, self.work), 20)
            except Exception:
                pass  # the next recording's checks remove it
        with self._lock:
            self._state = state

    def save(self, name):
        """Make the .mp4 on the Frame and copy it here, never leaving a partial file in the folder."""
        out = self.run(finish_command(name) if self.work == WORK else finish_command(name, self.work), 600)
        size = int(out.strip().splitlines()[-1]) if out.strip() else 0
        _make_room(self.folder, size)
        incoming = Path(tempfile.mkdtemp(prefix=".incoming-", dir=self.folder))
        try:
            self.fetch(f"{self.work}/{name}.mp4", incoming / f"{name}.mp4")
            os.replace(incoming / f"{name}.mp4", self.folder / f"{name}.mp4")
        finally:
            shutil.rmtree(incoming, ignore_errors=True)


def _make_room(folder, size):
    folder.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(folder).free
    if size and free < size + 256 * 1024**2:
        raise ClipError(f"Not enough free space on this computer: it needs {size // 1024**2 + 256} MB", 507)


def _close(f):
    try:
        f.close()
    except OSError:
        pass


def _end(proc):
    """Close our end of the channel and make sure the local ssh has gone."""
    _close(proc.stdin)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    _close(proc.stdout)


def _line_reader(pipe):
    """Lines from a pipe via a thread (select() can't wait on pipes on Windows); None at EOF."""
    import queue
    lines = queue.Queue()

    def pump():
        try:
            for raw in iter(pipe.readline, b""):
                lines.put(raw.decode(errors="replace").strip())
        except (OSError, ValueError):
            pass
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    return lines


def _next_line(lines, timeout):
    """The next line, None at EOF, or "" after `timeout` seconds of silence."""
    import queue
    try:
        return lines.get(timeout=timeout)
    except queue.Empty:
        return ""


# ---- Steam's game recordings ---------------------------------------------------

STEAM_USERDATA = ".local/share/Steam/userdata"
KINDS = {"clips": "clip", "video": "background"}
MAX_DEPTH = 4  # folders below clips/ or video/
PART = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}")  # no leading dot, so never "." or ".."
INIT = re.compile(r"init-stream(\d{1,3})\.m4s")
CHUNK = re.compile(r"chunk-stream(\d{1,3})-(\d{1,9})\.m4s")
STAMP = re.compile(r"(?:^|_)(\d{1,10})_(\d{8})_(\d{6})$")
EXPORT_PATH = re.compile(re.escape(WORK) + r"/export-[0-9a-f]{16}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}\.mp4")


def parse_id(clip_id):
    """A recording's id, "<account>/<clips|video>/<folder>[/<folder>...]", as path parts.

    Checked before it goes near a path or a shell: plain names only, no "." or "..",
    at most MAX_DEPTH folders. Raises ValueError."""
    parts = clip_id.split("/") if isinstance(clip_id, str) and len(clip_id) <= 600 else []
    if (len(parts) < 3 or len(parts) > 2 + MAX_DEPTH or not re.fullmatch(r"\d{1,12}", parts[0])
            or parts[1] not in KINDS or not all(PART.fullmatch(p) for p in parts[2:])):
        raise ValueError("bad clip id")
    return parts


def export_name(clip_id):
    """The .mp4's basename; it alone does not identify a saved export."""
    return parse_id(clip_id)[2] + ".mp4"


def clip_local_path(clip_id, device_id, folder=None):
    """Keep the headset, account and full Steam session identity in the destination."""
    parts = parse_id(clip_id)
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("missing clip headset identity")
    headset = hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:12]
    folder = Path(folder) if folder else VIDEOS_DIR
    return folder / f"headset-{headset}" / Path(*parts) / export_name(clip_id)


def read_session(folder):
    """{stream number: [init, chunk, chunk...]} for one session folder, chunks in number
    order. A stream without its init segment or without chunks can't be played, so it's left out."""
    inits, chunks = {}, {}
    for entry in os.scandir(folder):
        if not entry.is_file(follow_symlinks=False):
            continue
        m = INIT.fullmatch(entry.name)
        if m:
            inits[int(m[1])] = entry.path
            continue
        m = CHUNK.fullmatch(entry.name)
        if m:
            chunks.setdefault(int(m[1]), []).append((int(m[2]), entry.path))
    return {n: [inits[n], *(p for _, p in sorted(chunks[n]))] for n in sorted(inits) if chunks.get(n)}


def chunk_gaps(files):
    """How many chunk numbers are missing between the first and last (Steam deleted or lost them)."""
    nums = sorted(int(CHUNK.fullmatch(os.path.basename(f))[2]) for f in files[1:])
    return nums[-1] - nums[0] + 1 - len(nums) if nums else 0


def mpd_duration(text):
    """Seconds from the manifest's mediaPresentationDuration ("PT1M23.4S"), or None."""
    m = re.search(r'mediaPresentationDuration="P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?"', text or "")
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = m.groups()
    try:
        return int(d or 0) * 86400 + int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)
    except ValueError:
        return None


def _sessions(base, depth=0):
    """Folders under base (clips/ or video/) that hold init segments, without following links."""
    try:
        entries = list(os.scandir(base))
    except OSError:
        return
    if any(e.is_file(follow_symlinks=False) and INIT.fullmatch(e.name) for e in entries):
        yield base
        return
    if depth < MAX_DEPTH:
        for e in sorted(entries, key=lambda e: e.name):
            if e.is_dir(follow_symlinks=False) and PART.fullmatch(e.name):
                yield from _sessions(e.path, depth + 1)


def describe(userdata, clip_id):
    """What the list shows about one recording, or None if it holds nothing playable."""
    parts = parse_id(clip_id)
    folder = os.path.join(userdata, parts[0], "gamerecordings", *parts[1:])
    streams = read_session(folder)
    if not streams:
        return None
    files = [f for s in streams.values() for f in s]
    stats = [os.stat(f) for f in files]
    duration = None
    for mpd in sorted(p for p in os.listdir(folder) if p.endswith(".mpd")):
        try:
            duration = mpd_duration(Path(folder, mpd).read_text(errors="replace")[:20000])
        except OSError:
            pass
        if duration is not None:
            break
    newest = max(s.st_mtime for s in stats)
    appid, when = None, newest
    for p in parts[2:]:
        m = STAMP.search(p)
        if m:
            appid = m[1]
            try:
                when = time.mktime(time.strptime(m[2] + m[3], "%Y%m%d%H%M%S"))
            except ValueError:
                pass
            break
    return {"id": clip_id, "kind": KINDS[parts[1]], "appid": appid, "time": when,
            "size": sum(s.st_size for s in stats), "streams": len(streams),
            "chunks": sum(len(s) - 1 for s in streams.values()),
            "gaps": sum(chunk_gaps(s) for s in streams.values()), "duration": duration,
            "file": export_name(clip_id),
            # Seconds since Steam last wrote to it, by the Frame's clock: still recording if small.
            "idle": round(max(0.0, time.time() - newest), 1)}


def list_recordings(userdata):
    """Every Steam recording session on this Frame, newest first (runs on the Frame)."""
    found = []
    try:
        accounts = sorted(e.name for e in os.scandir(userdata) if e.is_dir(follow_symlinks=False)
                          and re.fullmatch(r"\d{1,12}", e.name))
    except OSError:
        return []
    for account in accounts:
        root = os.path.join(userdata, account, "gamerecordings")
        for kind in KINDS:
            for folder in _sessions(os.path.join(root, kind)):
                clip_id = "/".join([account, *os.path.relpath(folder, root).split(os.sep)])
                try:
                    info = describe(userdata, clip_id)
                except (OSError, ValueError):
                    continue  # changed while we looked, or a name we don't take
                if info:
                    found.append(info)
    found.sort(key=lambda c: c["time"], reverse=True)
    return found


def stitch_command(inputs, out):
    """ffmpeg that puts each stream file in one .mp4, copying the streams as they are."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for f in inputs:
        cmd += ["-i", str(f)]
    for i in range(len(inputs)):
        cmd += ["-map", str(i)]
    return cmd + ["-c", "copy", "-movflags", "+faststart", str(out)]


def export(userdata, clip_id, home=None):
    """Stitch one recording into an .mp4 under WORK (runs on the Frame). -> its path
    relative to home and its size. The computer copies it, then deletes it with
    remove_command."""
    home = Path(home or Path.home())
    parts = parse_id(clip_id)
    folder = Path(userdata, parts[0], "gamerecordings", *parts[1:])
    real = os.path.realpath(folder)
    if os.path.commonpath([real, os.path.realpath(userdata)]) != os.path.realpath(userdata):
        raise ValueError("bad clip id")
    streams = read_session(real)
    if not streams:
        raise ClipError("That recording has no complete streams on the Frame", 404)
    size = sum(os.path.getsize(f) for s in streams.values() for f in s)
    work = home / WORK
    work.mkdir(parents=True, exist_ok=True)
    _sweep(work)
    # The stream files and the .mp4 made from them are each about the recording's size.
    if shutil.disk_usage(work).free < size * 2 + 64 * 1024**2:
        raise ClipError(f"Not enough free space on the Frame to export it: it needs {(size * 2) // 1024**2 + 64} MB", 507)
    out_dir = work / f"export-{secrets.token_hex(8)}"
    out_dir.mkdir()
    try:
        inputs = []
        for n, files in streams.items():
            path = out_dir / f"stream{n}.mp4"
            with open(path, "wb") as dst:
                for f in files:
                    with open(f, "rb") as src:
                        shutil.copyfileobj(src, dst, 1 << 20)
            inputs.append(path)
        out = out_dir / export_name(clip_id)
        r = subprocess.run(stitch_command(inputs, out), capture_output=True, text=True, errors="replace", timeout=1800)
        if r.returncode != 0 or not out.exists():
            raise ClipError("ffmpeg couldn't join the recording: " + (r.stderr.strip()[-1500:] or f"exit {r.returncode}"))
        for f in inputs:
            f.unlink()
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    return {"path": out.relative_to(home).as_posix(), "size": out.stat().st_size}


def _sweep(work, older=6 * 3600):
    """Exports left behind by a copy that never finished."""
    for d in work.glob("export-*"):
        try:
            if time.time() - d.stat().st_mtime > older:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def remove_command(path):
    """Delete an export on the Frame once it's been copied (path as export returned it)."""
    if not EXPORT_PATH.fullmatch(path or ""):
        raise ValueError(f"unexpected export path {path!r}")
    return f"rm -rf \"$HOME\"/{shlex.quote(path.rsplit('/', 1)[0])}"


# ---- the computer's side of Steam clips -------------------------------------------
#
# run_frame(args, timeout) runs this file on the Frame with `args` and returns its JSON;
# run(command, timeout) and fetch(remote, local) as for Recorder.

def list_clips(run_frame, folder=None, *, device_id):
    """Steam's recordings on the Frame, each marked saved if its .mp4 is already here."""
    folder = Path(folder) if folder else VIDEOS_DIR
    clips = run_frame(["list"], 60)["clips"]
    for c in clips:
        c["saved"] = clip_local_path(c["id"], device_id, folder).is_file()
    return {"clips": clips, "folder": str(folder)}


def export_clip(clip_id, run_frame, run, fetch, folder=None, *, device_id):
    """Stitch a Steam recording on the Frame and copy the .mp4 here. -> {"message", "file"}."""
    folder = Path(folder) if folder else VIDEOS_DIR
    target = clip_local_path(clip_id, device_id, folder)  # validate before reaching the Frame
    name = target.name
    made = run_frame(["export", clip_id], 1900)
    path = made.get("path")
    remove = remove_command(path)  # refuses a path that isn't one of our exports
    try:
        _make_room(folder, int(made.get("size") or 0))
        incoming = Path(tempfile.mkdtemp(prefix=".incoming-", dir=folder))
        try:
            fetch(path, incoming / name)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(incoming / name, target)
        finally:
            shutil.rmtree(incoming, ignore_errors=True)
    finally:
        try:
            run(remove, 30)
        except Exception:
            pass  # the next export sweeps it
    return {"message": f"Saved {name} to ~/Videos/SteamFrame", "file": str(target)}


# ---- on the Frame -----------------------------------------------------------------

def main(argv):
    userdata = Path.home() / STEAM_USERDATA
    try:
        if argv[:1] == ["list"]:
            result = {"clips": list_recordings(userdata)}
        elif len(argv) == 2 and argv[0] == "export":
            result = export(userdata, argv[1])
        else:
            result = {"error": "usage: frame_clips.py list | export ID"}
    except (ClipError, ValueError, OSError, subprocess.TimeoutExpired) as e:
        result = {"error": str(e)}
    print(json.dumps(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
