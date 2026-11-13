"""Copy new screenshots and Steam clips from the headset to this computer on their own.

Off until it's turned on in Settings. Then a worker in the server looks about once a
minute, while a headset is connected and nothing else is running on it, and copies
what's new with the same code as Save and Export: screenshots to ~/Pictures/SteamFrame,
saved Steam clips to ~/Videos/SteamFrame.

- Only what's newer than the moment it was turned on, so turning it on doesn't copy
  the whole back-catalogue; Copy everything now does that, once.
- What it has copied is remembered per headset (auto-sync.json in the app's data
  folder), so a file deleted from this computer isn't copied again.
- A clip Steam is still writing (a chunk changed in the last SETTLE seconds) waits
  for the next look. Steam's background recording is never copied: it's a rolling
  buffer, not something anyone chose to keep.
- When this computer runs out of space it pauses and says so, until Resume.
- When the headset can't be reached it waits longer each time, up to MAX_BACKOFF.

The server supplies how to reach the headset, so this can be tested without one:
  list_shots(device) -> {"shots": [{"id", "time", "saved"}...]}
  save_shots(device, ids) copies those screenshots here
  list_clips(device) -> {"clips": [{"id", "kind", "time", "idle", "saved"}...]}
  export_clip(device, id) exports one clip here
  device() -> the connected headset's id, or None
  busy() -> True while other work runs on the headset (installs, jobs, a recording)
  offline(error) -> a plain message if the error means the headset couldn't be reached
"""
import errno
import json
import os
import shutil
import threading
import time
from pathlib import Path

import frame_host

INTERVAL = 60  # seconds between looks
BUSY_WAIT = 15  # something else is running: look again soon
MAX_BACKOFF = 15 * 60  # the longest wait while the headset can't be reached
SETTLE = 30  # a clip written to within this many seconds is still being recorded
MIN_FREE = 512 * 1024**2  # pause below this much free space on this computer
KEEP = 5000  # copied ids remembered per headset and kind
BATCH = 100  # screenshots per copy
TRIES = 3  # failed attempts per item until Resume, Copy everything now, or restart
KINDS = ("shots", "clips")


class DiskFull(Exception):
    pass


def free_space(folder):
    """Free bytes on the disk `folder` is (or will be) on."""
    p = Path(folder)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(p).free


def disk_full(error):
    """Whether an error means this computer ran out of space (not the headset)."""
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return True
    text = str(error)
    return "No space left on device" in text or "free space on this computer" in text


def _defaults():
    return {"screenshots": False, "clips": False, "since": None, "synced": {}, "paused": None,
            "checked": None, "copied": 0, "copied_time": None, "error": None, "waiting": 0}


class AutoSync:
    def __init__(self, list_shots, save_shots, list_clips, export_clip, device, busy, offline=lambda e: None,
                 shots_folder=None, clips_folder=None, path=None, clock=time.time, space=free_space):
        self.list_shots, self.save_shots = list_shots, save_shots
        self.list_clips, self.export_clip = list_clips, export_clip
        self.device, self.busy, self.offline = device, busy, offline
        self.shots_folder = Path(shots_folder or Path.home() / "Pictures" / "SteamFrame")
        self.clips_folder = Path(clips_folder or Path.home() / "Videos" / "SteamFrame")
        self.path = Path(path or frame_host.data_dir("auto-sync.json"))
        self.clock, self.space = clock, space
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._all = False  # Copy everything now, waiting for the next pass
        self._running = False
        self._backoff = 0
        self._tries = {}  # (device, id) -> failed attempts this run
        self._failures = {}  # last error for each failed item, including exhausted retries
        self._errors = []  # this pass's, for the page
        self._s = self._load()

    # ---- settings and what the page shows ----
    def _load(self):
        s = _defaults()
        try:
            saved = json.loads(self.path.read_text())
            if isinstance(saved, dict):
                s.update({k: v for k, v in saved.items() if k in s})
        except (OSError, ValueError):
            pass
        s["screenshots"], s["clips"] = bool(s["screenshots"]), bool(s["clips"])
        if not isinstance(s["synced"], dict):
            s["synced"] = {}
        return s

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._s, indent=1))
            os.replace(tmp, self.path)
        except OSError:
            pass  # the settings still apply until the app restarts

    def enabled(self):
        with self._lock:
            return self._s["screenshots"] or self._s["clips"]

    def state(self):
        with self._lock:
            s = self._s
            return {k: s[k] for k in ("screenshots", "clips", "since", "paused", "checked", "copied",
                                      "copied_time", "error", "waiting")} | {
                "pending": self._all, "running": self._running,
                "folders": {"shots": str(self.shots_folder), "clips": str(self.clips_folder)}}

    def update(self, changes):
        """{"screenshots": bool, "clips": bool}: turning it on starts the watermark now."""
        with self._lock:
            was = self.enabled()
            for key in ("screenshots", "clips"):
                if key in changes:
                    self._s[key] = bool(changes[key])
            if self.enabled() and (not was or self._s["since"] is None):
                self._s["since"] = self.clock()
            if not self.enabled():
                self._s["error"], self._s["waiting"] = None, 0
            self._save()
        self._wake.set()
        return self.state()

    def copy_all(self):
        """Copy everything on the headset that isn't on this computer, once (also resumes)."""
        with self._lock:
            self._all, self._s["paused"] = True, None
            self._tries.clear()
            self._failures.clear()
            self._s["error"] = None
            self._save()
        self._backoff = 0
        self._wake.set()
        return self.state()

    def resume(self):
        with self._lock:
            self._s["paused"], self._s["error"] = None, None
            self._tries.clear()
            self._failures.clear()
            self._save()
        self._backoff = 0
        self._wake.set()
        return self.state()

    # ---- the worker ----
    def run(self, stop):
        """Until `stop` (a threading.Event) is set."""
        while not stop.is_set():
            delay = self.tick()
            self._wake.wait(delay)
            self._wake.clear()

    def tick(self):
        """One look. -> seconds until the next."""
        with self._lock:
            want_all = self._all
            shots = self._s["screenshots"] or want_all
            clips = self._s["clips"] or want_all
            if not (shots or clips) or self._s["paused"]:
                return INTERVAL
            since = None if want_all else self._s["since"] or 0
        device = self.device()
        if not device:
            return INTERVAL  # nothing connected: nothing to ask
        if self.busy():
            return BUSY_WAIT
        with self._lock:
            self._running = True
        self._errors = []
        try:
            copied, waiting, done = self._pass(device, shots, clips, since)
        except DiskFull as e:
            with self._lock:
                self._s.update(paused=str(e), error=str(e))
                self._save()
            return INTERVAL
        except Exception as e:
            friendly = self.offline(e)
            self._backoff = min(max(self._backoff * 2, INTERVAL * 2), MAX_BACKOFF)
            with self._lock:
                self._s["error"] = friendly or str(e)
                self._save()
            return self._backoff
        finally:
            with self._lock:
                self._running = False
        self._backoff = 0
        with self._lock:
            if copied:
                self._s.update(copied=copied, copied_time=self.clock())
            self._s.update(checked=self.clock(), waiting=waiting)
            if done:
                self._s["error"] = self._errors[0] if self._errors else None
                if want_all:
                    self._all = False
            self._save()
        return INTERVAL if done else BUSY_WAIT

    def _synced(self, device, kind):
        with self._lock:
            return set(self._s["synced"].get(device, {}).get(kind, []))

    def _mark(self, device, kind, ids):
        with self._lock:
            for item in ids:
                self._tries.pop((device, item), None)
                self._failures.pop((device, item), None)
            per = self._s["synced"].setdefault(device, {})
            have = per.get(kind, [])
            new = [i for i in ids if i not in set(have)]
            if new:
                per[kind] = (have + new)[-KEEP:]
                self._save()

    def _room(self, folder):
        if self.space(folder) < MIN_FREE:
            raise DiskFull(f"Paused: this computer is nearly out of space ({folder} has under "
                           f"{MIN_FREE // 1024**2} MB free). Free some space, then press Resume.")

    def _failed(self, device, item, error):
        if disk_full(error):
            raise DiskFull("Paused: this computer ran out of space while copying. Free some space, "
                           "then press Resume.")
        if self.offline(error):
            raise error
        with self._lock:
            key = (device, item)
            self._tries[key] = self._tries.get(key, 0) + 1
            message = f"Couldn't copy {item.rsplit('/', 1)[-1]}: {error}"
            if self._tries[key] >= TRIES:
                message += ". Automatic retries stopped. Press Resume to try again."
            self._failures[key] = message
            self._errors.append(message)

    def _retry_allowed(self, device, item):
        with self._lock:
            key = (device, item)
            if self._tries.get(key, 0) < TRIES:
                return True
            self._errors.append(self._failures[key])
            return False

    def _interrupted(self, device):
        return self.busy() or self.device() != device

    def _pass(self, device, shots, clips, since):
        """-> (copied, clips still being written, finished without stopping for other work)."""
        copied = waiting = 0
        if shots:
            if self._interrupted(device):
                return copied, waiting, False
            listing = self.list_shots(device)["shots"]
            if self._interrupted(device):
                return copied, waiting, False
            done = self._synced(device, "shots")
            self._mark(device, "shots", [s["id"] for s in listing if s.get("saved")])
            todo = [s["id"] for s in sorted(listing, key=lambda s: s["time"])
                    if not s.get("saved") and (since is None or (s["time"] >= since and s["id"] not in done))
                    and self._retry_allowed(device, s["id"])]
            for i in range(0, len(todo), BATCH):
                if self._interrupted(device):
                    return copied, waiting, False
                self._room(self.shots_folder)
                if self._interrupted(device):
                    return copied, waiting, False
                batch = todo[i:i + BATCH]
                try:
                    self.save_shots(device, batch)
                except Exception as e:
                    for item in batch:
                        self._failed(device, item, e)
                    continue
                if self.device() != device:
                    return copied, waiting, False
                self._mark(device, "shots", batch)
                copied += len(batch)
        if clips:
            if self._interrupted(device):
                return copied, waiting, False
            listing = [c for c in self.list_clips(device)["clips"] if c.get("kind") == "clip"]
            if self._interrupted(device):
                return copied, waiting, False
            done = self._synced(device, "clips")
            self._mark(device, "clips", [c["id"] for c in listing if c.get("saved")])
            for c in sorted(listing, key=lambda c: c["time"]):
                if c.get("saved"):
                    continue
                if since is not None and (c["time"] < since or c["id"] in done):
                    continue
                if not self._retry_allowed(device, c["id"]):
                    continue
                if c.get("idle") is None or c["idle"] < SETTLE:
                    waiting += 1  # still being written: copied on a later look
                    continue
                if self._interrupted(device):
                    return copied, waiting, False
                self._room(self.clips_folder)
                if self._interrupted(device):
                    return copied, waiting, False
                try:
                    self.export_clip(device, c["id"])
                except Exception as e:
                    self._failed(device, c["id"], e)
                    continue
                if self.device() != device:
                    return copied, waiting, False
                self._mark(device, "clips", [c["id"]])
                copied += 1
        return copied, waiting, True
