"""Recordings of the headset view and Steam clip exports (ui/frame_clips.py), without a headset.

Steam's recordings are fixture trees in the layout frame_clips.py describes. The
recording's shell runs for real under bash with a stand-in ffmpeg, so Stop, the time
limit and the clean-up are the real script's behaviour. With ffmpeg installed here, a
65-second DASH recording is made in Steam's file naming and exported for real.
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
import frame_clips as clips  # noqa: E402

POSIX = os.name != "nt" and shutil.which("bash")


def write(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def session(folder, streams=(0, 1), chunks=3, mpd=None, first=1, pad=5):
    """A session folder as Steam writes it: init + numbered chunks per stream."""
    for n in streams:
        write(folder / f"init-stream{n}.m4s", f"init{n};".encode())
        for c in range(first, first + chunks):
            write(folder / f"chunk-stream{n}-{c:0{pad}d}.m4s", f"s{n}c{c};".encode())
    if mpd is not None:
        write(folder / "session.mpd", mpd.encode())
    return folder


class Ids(unittest.TestCase):
    def test_good_ids(self):
        for cid in ("123/video/bg_620_20261020_201950",
                    "123/clips/clip_620_20261020_202134/video/bg_620_20261020_201950",
                    "9/clips/a/b/c/d"):
            self.assertEqual(clips.parse_id(cid)[0], cid.split("/")[0])
        self.assertEqual(clips.export_name("123/clips/clip_620_20261020_202134/video/bg_620_1"),
                         "clip_620_20261020_202134.mp4")

    def test_no_traversal_or_shell_from_ids(self):
        for cid in ("", None, 5, "123", "123/video", "123/other/bg", "abc/video/bg", "/123/video/bg",
                    "123/video/..", "123/video/.", "123/video/bg/../../../../.ssh", "123/video/.hidden",
                    "123/video/bg;rm -rf ~", "123/video/bg$(id)", "123/video/bg name", "123/video/bg\n",
                    "123/video/%2e%2e", "123\\video\\bg", "123/video//bg", "123/clips/a/b/c/d/e",
                    "123/video/" + "a" * 101, "1234567890123/video/bg"):
            with self.subTest(cid=cid), self.assertRaises(ValueError):
                clips.parse_id(cid)
            with self.subTest(cid=cid), self.assertRaises(ValueError):
                clips.export_name(cid)

    def test_export_paths_checked_before_delete(self):
        good = f"{clips.WORK}/export-0123456789abcdef/clip_620.mp4"
        self.assertEqual(clips.remove_command(good), f'rm -rf "$HOME"/{clips.WORK}/export-0123456789abcdef')
        for bad in (None, "", "/etc/passwd", f"{clips.WORK}/export-0123456789abcdef/../../x.mp4",
                    f"{clips.WORK}/export-xyz/clip.mp4", f"{clips.WORK}/../export-0123456789abcdef/a.mp4",
                    f"{clips.WORK}/export-0123456789abcdef/a.mp4; rm -rf ~", ".ssh/export-0123456789abcdef/a.mp4"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                clips.remove_command(bad)

    def test_recording_names_checked(self):
        for fn in (clips.finish_command, clips.cleanup_command, lambda n: clips.record_command(n, True)):
            for bad in ("rec-1", "rec-20261020-201950; rm -rf ~", "../rec-20261020-201950", "*"):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    fn(bad)


class Sessions(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_chunks_in_number_order_whatever_the_padding(self):
        s = self.dir / "s"
        write(s / "init-stream0.m4s")
        for c in (10, 2, 1, 100, 9):
            write(s / f"chunk-stream0-{c}.m4s")
        write(s / "chunk-stream0-00003.m4s")
        got = clips.read_session(s)
        self.assertEqual([os.path.basename(p) for p in got[0]],
                         ["init-stream0.m4s", "chunk-stream0-1.m4s", "chunk-stream0-2.m4s", "chunk-stream0-00003.m4s",
                          "chunk-stream0-9.m4s", "chunk-stream0-10.m4s", "chunk-stream0-100.m4s"])
        self.assertEqual(clips.chunk_gaps(got[0]), 100 - 6)

    def test_unplayable_streams_and_strangers_left_out(self):
        s = self.dir / "s"
        session(s, streams=(0,), chunks=2)
        write(s / "init-stream1.m4s")                 # no chunks
        write(s / "chunk-stream2-00001.m4s")          # no init
        write(s / "chunk-stream0-00001.m4s.part")     # not a chunk
        write(s / "thumbnail.jpg")
        (s / "chunk-stream0-00009.m4s").mkdir()       # a folder, not a file
        if POSIX:
            os.symlink("/etc/passwd", s / "chunk-stream0-00005.m4s")  # links aren't followed
        got = clips.read_session(s)
        self.assertEqual(list(got), [0])
        self.assertEqual(len(got[0]), 3)

    def test_manifest_duration(self):
        for text, want in (('mediaPresentationDuration="PT1M23.4S"', 83.4), ('mediaPresentationDuration="PT2H"', 7200),
                           ('mediaPresentationDuration="PT0H3M0.000S"', 180), ('mediaPresentationDuration="P1DT1S"', 86401),
                           ('mediaPresentationDuration="PT"', None), ('nothing here', None), (None, None)):
            self.assertEqual(clips.mpd_duration(text), want, text)

    def test_listing_a_fixture_tree(self):
        ud = self.dir / "userdata"
        gr = ud / "123" / "gamerecordings"
        session(gr / "clips" / "clip_620_20261020_202134" / "video" / "bg_620_20261020_201950", chunks=40,
                mpd='<MPD mediaPresentationDuration="PT1M20.0S">')
        write(gr / "clips" / "clip_620_20261020_202134" / "thumbnail.jpg")
        session(gr / "video" / "bg_1172470_20261021_090000", streams=(0,), chunks=2)
        session(gr / "video" / "odd-name", chunks=1)                   # no stamp: time from the files
        (gr / "video" / "empty").mkdir()
        session(gr / "video" / ".hidden", chunks=1)                    # not a name an id can carry
        session(gr / "timelines" / "x", chunks=1)                      # not clips/ or video/
        session(ud / "notanaccount" / "gamerecordings" / "video" / "bg_1_20260101_000000", chunks=1)
        session(gr / "video" / "a" / "b" / "c" / "d" / "e", chunks=1)  # deeper than ids go
        if POSIX:
            os.symlink(gr, gr / "video" / "loop")                      # links aren't followed
        for f in (gr / "video" / "odd-name").iterdir():
            os.utime(f, (1e9, 1e9))  # 2001: older than the others
        got = clips.list_recordings(ud)
        self.assertEqual([c["id"] for c in got], ["123/video/bg_1172470_20261021_090000",
                                                  "123/clips/clip_620_20261020_202134/video/bg_620_20261020_201950",
                                                  "123/video/odd-name"])  # newest first
        self.assertEqual(got[-1]["time"], 1e9)
        by = {c["id"]: c for c in got}
        clip = by["123/clips/clip_620_20261020_202134/video/bg_620_20261020_201950"]
        self.assertEqual((clip["kind"], clip["appid"], clip["streams"], clip["chunks"], clip["gaps"], clip["duration"]),
                         ("clip", "620", 2, 80, 0, 80.0))
        self.assertEqual(clip["file"], "clip_620_20261020_202134.mp4")
        self.assertEqual(clip["time"], time.mktime((2026, 10, 20, 20, 21, 34, 0, 0, -1)))
        self.assertEqual(clip["size"], sum(f.stat().st_size for f in
                                           (gr / "clips" / "clip_620_20261020_202134" / "video" / "bg_620_20261020_201950").iterdir()
                                           if f.suffix == ".m4s"))
        bg = by["123/video/bg_1172470_20261021_090000"]
        self.assertEqual((bg["kind"], bg["appid"], bg["streams"], bg["duration"]), ("background", "1172470", 1, None))
        self.assertIsNone(by["123/video/odd-name"]["appid"])
        # How long since Steam last wrote to it: auto-sync waits for a clip still being recorded.
        self.assertLess(clip["idle"], 60)
        self.assertGreater(by["123/video/odd-name"]["idle"], 10**8)
        self.assertEqual(clips.list_recordings(self.dir / "missing"), [])

    def test_listing_marks_what_is_already_here(self):
        here = self.dir / "here"
        write(here / "clip_620_20261020_202134.mp4")
        frame = lambda args, timeout: {"clips": [{"id": "1/clips/clip_620_20261020_202134/video/bg"},
                                                 {"id": "1/video/bg_620_20261020_201950"}]}
        got = clips.list_clips(frame, folder=here)
        self.assertEqual([c["saved"] for c in got["clips"]], [True, False])
        self.assertEqual(got["folder"], str(here))


class Export(unittest.TestCase):
    """The Frame's half of an export, against a fixture tree, with ffmpeg stood in."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.ud = self.dir / "home" / clips.STEAM_USERDATA
        self.home = self.dir / "home"
        self.cid = "123/clips/clip_620_20261020_202134/video/bg_620_20261020_201950"
        session(self.ud / "123" / "gamerecordings" / "clips" / "clip_620_20261020_202134" / "video" /
                "bg_620_20261020_201950", chunks=12)

    def fake_ffmpeg(self, seen, rc=0):
        def run(cmd, **kw):
            ins = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-i"]
            seen.append({"cmd": cmd, "inputs": {Path(i).name: Path(i).read_bytes() for i in ins}})
            if rc == 0:
                Path(cmd[-1]).write_bytes(b"mp4")
            return subprocess.CompletedProcess(cmd, rc, "", "Invalid data found" if rc else "")
        return run

    def test_streams_stitched_in_order_and_copied_not_reencoded(self):
        seen = []
        with mock.patch.object(clips.subprocess, "run", self.fake_ffmpeg(seen)):
            got = clips.export(self.ud, self.cid, home=self.home)
        self.assertRegex(got["path"], clips.EXPORT_PATH)
        self.assertTrue(got["path"].endswith("/clip_620_20261020_202134.mp4"))
        self.assertEqual(got["size"], 3)
        cmd = seen[0]["cmd"]
        self.assertEqual(cmd[cmd.index("-c") + 1], "copy")
        self.assertEqual([cmd[i + 1] for i, a in enumerate(cmd) if a == "-map"], ["0", "1"])
        for n in (0, 1):
            self.assertEqual(seen[0]["inputs"][f"stream{n}.mp4"],
                             f"init{n};".encode() + b"".join(f"s{n}c{c};".encode() for c in range(1, 13)))
        out = self.home / got["path"]
        self.assertEqual(sorted(p.name for p in out.parent.iterdir()), [out.name])  # stream files gone

    def test_failed_join_leaves_nothing_behind(self):
        with mock.patch.object(clips.subprocess, "run", self.fake_ffmpeg([], rc=1)):
            with self.assertRaisesRegex(clips.ClipError, "Invalid data"):
                clips.export(self.ud, self.cid, home=self.home)
        self.assertEqual(list((self.home / clips.WORK).glob("export-*")), [])

    def test_bad_or_missing_ids(self):
        with self.assertRaises(ValueError):
            clips.export(self.ud, "123/video/../../../../etc", home=self.home)
        with self.assertRaises(ClipErrorOrOSError):
            clips.export(self.ud, "123/video/nothing_here", home=self.home)

    @unittest.skipUnless(POSIX, "symlinks")
    def test_a_linked_account_cannot_reach_outside_userdata(self):
        outside = session(self.dir / "elsewhere" / "gamerecordings" / "video" / "bg_1_20260101_000000", chunks=1)
        os.symlink(self.dir / "elsewhere", self.ud / "456")
        self.assertIsNotNone(outside)
        with self.assertRaises(ValueError):
            clips.export(self.ud, "456/video/bg_1_20260101_000000", home=self.home)

    def test_no_space_on_the_frame(self):
        full = mock.Mock(free=10)
        with mock.patch.object(clips.shutil, "disk_usage", return_value=full):
            with self.assertRaisesRegex(clips.ClipError, "Not enough free space on the Frame"):
                clips.export(self.ud, self.cid, home=self.home)

    def test_old_exports_swept(self):
        work = self.home / clips.WORK
        old, new = work / "export-aaaaaaaaaaaaaaaa", work / "export-bbbbbbbbbbbbbbbb"
        write(old / "x.mp4"), write(new / "y.mp4")
        os.utime(old, (time.time() - 7 * 3600,) * 2)
        with mock.patch.object(clips.subprocess, "run", self.fake_ffmpeg([])):
            clips.export(self.ud, self.cid, home=self.home)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_main_prints_json(self):
        with mock.patch.object(clips.Path, "home", return_value=self.home), \
                mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as out:
            self.assertEqual(clips.main(["list"]), 0)
            self.assertEqual(json.loads(out.getvalue())["clips"][0]["id"], self.cid)
        with mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as out:
            self.assertEqual(clips.main(["export", "../../x"]), 1)
            self.assertEqual(json.loads(out.getvalue()), {"error": "bad clip id"})


ClipErrorOrOSError = (clips.ClipError, OSError)


class ComputerSide(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_export_copies_then_deletes_on_the_frame(self):
        path = f"{clips.WORK}/export-0123456789abcdef/clip_620.mp4"
        calls = []
        frame = lambda args, timeout: calls.append(("frame", args)) or {"path": path, "size": 3}
        run = lambda cmd, timeout: calls.append(("run", cmd))
        fetch = lambda remote, local: calls.append(("fetch", remote)) or Path(local).write_bytes(b"mp4")
        got = clips.export_clip("1/clips/clip_620/video/bg", frame, run, fetch, folder=self.dir)
        self.assertEqual(got["message"], "Saved clip_620.mp4 to ~/Videos/SteamFrame")
        self.assertEqual((self.dir / "clip_620.mp4").read_bytes(), b"mp4")
        self.assertEqual([c[0] for c in calls], ["frame", "fetch", "run"])
        self.assertEqual(calls[2][1], clips.remove_command(path))
        self.assertEqual([p.name for p in self.dir.iterdir()], ["clip_620.mp4"])

    def test_failed_copy_leaves_no_partial_file_and_still_cleans_up(self):
        path = f"{clips.WORK}/export-0123456789abcdef/clip_620.mp4"
        ran = []

        def fetch(remote, local):
            Path(local).write_bytes(b"half")
            raise RuntimeError("connection lost")
        with self.assertRaisesRegex(RuntimeError, "connection lost"):
            clips.export_clip("1/clips/clip_620/video/bg", lambda a, t: {"path": path, "size": 4},
                              lambda cmd, timeout: ran.append(cmd), fetch, folder=self.dir)
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertEqual(ran, [clips.remove_command(path)])

    def test_bad_id_never_reaches_the_frame(self):
        never = mock.Mock(side_effect=AssertionError("reached the Frame"))
        with self.assertRaises(ValueError):
            clips.export_clip("1/video/../../.ssh", never, never, never, folder=self.dir)

    def test_unexpected_path_from_the_frame_refused(self):
        never = mock.Mock(side_effect=AssertionError("deleted or copied"))
        with self.assertRaises(ValueError):
            clips.export_clip("1/video/bg", lambda a, t: {"path": ".ssh/id_ed25519", "size": 1}, never, never,
                              folder=self.dir)


class Commands(unittest.TestCase):
    def test_record_command_with_and_without_sound(self):
        with_sound = shlex.split(clips.record_command("rec-20261020-201950", True))
        self.assertEqual(with_sound[:2], ["bash", "-c"])
        script = with_sound[2]
        self.assertIn(f"-f v4l2 -video_size 1920x1080 -i {clips.STREAM_DEVICE}", script)
        self.assertIn("-c:v libx264", script)
        self.assertNotIn("v4l2m2m", script)  # the hardware encoder crashes ffmpeg
        self.assertIn(f"-f pulse -i {clips.AUDIO_SOURCE}", script)
        self.assertIn("-map 1:a:0", script)
        self.assertIn("-c:a aac", script)
        self.assertIn(f"-t {clips.MAX_SECONDS} ", script)
        self.assertIn('"$d/rec-20261020-201950.mkv"', script)
        self.assertEqual(script.count("-use_wallclock_as_timestamps 1"), 2)
        quiet = shlex.split(clips.record_command("rec-20261020-201950", False))[2]
        self.assertNotIn("pulse", quiet)
        self.assertNotIn("-c:a", quiet)
        self.assertEqual(quiet.count("-use_wallclock_as_timestamps 1"), 1)
        with self.assertRaises(ValueError):
            clips.record_command("rec-20261020-201950", True, max_seconds=clips.MAX_SECONDS + 1)

    def test_probe_checks_device_space_and_sound(self):
        probe = clips.probe_command()
        self.assertIn(f"[ -e {clips.STREAM_DEVICE} ]", probe)
        self.assertIn(f"-ge {clips.NEED_KB} ]", probe)
        self.assertIn(f"timeout 5 ffmpeg -hide_banner -loglevel error -nostdin -f pulse -i {clips.AUDIO_SOURCE}", probe)
        self.assertIn("echo audio=1; else echo audio=0", probe)
        self.assertIn(f'd="$HOME/{clips.WORK}"', probe)

    def test_finish_remuxes_without_reencoding(self):
        cmd = clips.finish_command("rec-20261020-201950")
        self.assertIn("-i rec-20261020-201950.mkv -map 0 -c copy -movflags +faststart rec-20261020-201950.mp4", cmd)
        self.assertNotIn("libx264", cmd)
        self.assertEqual(clips.cleanup_command("rec-20261020-201950"), f'rm -f "$HOME/{clips.WORK}/rec-20261020-201950".*')

    def test_stitch_command(self):
        self.assertEqual(clips.stitch_command(["a.mp4", "b.mp4"], "out.mp4"),
                         ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", "a.mp4", "-i", "b.mp4",
                          "-map", "0", "-map", "1", "-c", "copy", "-movflags", "+faststart", "out.mp4"])


# A stand-in for ffmpeg on the Frame: records how it was run, writes its output file,
# and finishes the file when q arrives on stdin. Like SteamOS's ffmpeg n7.0 (seen on a
# Frame), it catches SIGTERM and SIGINT and carries on, exiting only after more than
# three. FAKE_FFMPEG_RUN makes the recording end by itself after that many seconds (the
# time limit); FAKE_FFMPEG_DEAF makes it ignore q too, so only SIGKILL ends it.
FAKE_FFMPEG = r'''#!/usr/bin/env python3
import json, os, signal, sys, time
home = os.environ["HOME"]
with open(os.path.join(home, "ffmpeg-calls.jsonl"), "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
out = sys.argv[-1]
if "-c" in sys.argv and sys.argv[sys.argv.index("-c") + 1] == "copy":   # the remux after a recording
    src = sys.argv[sys.argv.index("-i") + 1]
    open(out, "wb").write(open(src, "rb").read() + b"+mp4")
    sys.exit(0)
import threading
stop, signals = [], []
def caught(*a):
    signals.append(1)
    if len(signals) > 3:
        os._exit(255)  # "Received > 3 system signals, hard exiting"
signal.signal(signal.SIGTERM, caught)
signal.signal(signal.SIGINT, caught)
def keys():
    while True:
        ch = os.read(0, 1)
        if not ch:
            return
        if ch == b"q" and not os.environ.get("FAKE_FFMPEG_DEAF"):
            stop.append("q")
threading.Thread(target=keys, daemon=True).start()
f = open(out, "wb")
f.write(b"v"); f.flush()
with open(os.path.join(home, "ffmpeg.pid.tmp"), "w") as p:
    p.write(str(os.getpid()))
os.replace(os.path.join(home, "ffmpeg.pid.tmp"), os.path.join(home, "ffmpeg.pid"))
end = time.time() + float(os.environ.get("FAKE_FFMPEG_RUN", "60"))
while not stop and time.time() < end:
    f.write(b"v"); f.flush(); time.sleep(0.05)
f.close()
open(os.path.join(home, "ffmpeg-ended"), "w").write(stop[0] if stop else "limit")
sys.exit(255 if stop else 0)
'''


@unittest.skipUnless(POSIX, "the recording's shell is bash on the Frame")
class Recording(unittest.TestCase):
    """The Recorder with the real record/finish/cleanup shell, run locally under bash."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.frame = self.dir / "frame"           # the Frame's home
        (self.frame / clips.WORK).mkdir(parents=True)
        bin_dir = self.dir / "bin"
        write(bin_dir / "ffmpeg", FAKE_FFMPEG.encode()).chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.frame), "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        self.here = self.dir / "Videos"
        self.channels, self.released, self.ran = [], [], []
        self.audio = "audio=1"

    def open_channel(self, command, stderr):
        proc = subprocess.Popen(shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                                env=self.env)
        self.channels.append(proc)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        return proc

    def run_cmd(self, command, timeout):
        self.ran.append(command)
        if command == clips.probe_command():
            return self.audio + "\n"  # needs /dev/video99, so answered here
        r = subprocess.run(["bash", "-c", command], capture_output=True, text=True, env=self.env, timeout=timeout)
        if r.returncode:
            raise RuntimeError(r.stderr.strip() or f"exit {r.returncode}")
        return r.stdout

    def fetch(self, remote, local):
        shutil.copyfile(self.frame / remote, local)

    def recorder(self):
        rec = clips.Recorder(self.open_channel, self.run_cmd, self.fetch,
                             lambda fn: threading.Thread(target=fn, daemon=True).start(),
                             release=self.released.append, folder=self.here)
        start = rec.start

        def started():
            # "started" means ffmpeg was launched; wait until it's running, as it would be by a person's Stop.
            pid = self.frame / "ffmpeg.pid"
            for f in (pid, self.frame / "ffmpeg-ended"):
                f.unlink(missing_ok=True)
            got = start()
            for _ in range(200):
                if pid.exists() or (self.frame / "ffmpeg-ended").exists():
                    break
                time.sleep(0.02)
            return got
        rec.start = started
        return rec

    def wait_for(self, rec, states, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            s = rec.status()
            if s["state"] in states:
                return s
            time.sleep(0.05)
        self.fail(f"still {rec.status()}")

    def ffmpeg_calls(self):
        return [json.loads(line) for line in (self.frame / "ffmpeg-calls.jsonl").read_text().splitlines()]

    def test_stop_finishes_the_file_and_copies_it_here(self):
        rec = self.recorder()
        started = rec.start()
        self.assertEqual((started["state"], started["audio"], started["message"]), ("recording", True, "Recording"))
        self.assertIn("pulse", self.ffmpeg_calls()[0])
        time.sleep(0.3)
        self.assertEqual(rec.stop()["state"], "stopping")
        done = self.wait_for(rec, ("saved", "failed"))
        self.assertEqual(done["state"], "saved", done)
        self.assertEqual((self.frame / "ffmpeg-ended").read_text(), "q")  # asked to finish, not killed
        saved = Path(done["file"])
        self.assertEqual(saved.parent, self.here)
        self.assertRegex(saved.name, r"^rec-\d{8}-\d{6}\.mp4$")
        self.assertTrue(saved.read_bytes().endswith(b"+mp4"))
        self.assertEqual([p.name for p in self.here.iterdir()], [saved.name])          # no .incoming- left
        self.assertEqual(list((self.frame / clips.WORK).iterdir()), [])                 # cleaned on the Frame
        self.assertIsNotNone(self.channels[0].poll())                                   # the channel has gone
        self.assertEqual(self.released, self.channels)
        self.assertEqual(self.ran[-1], clips.cleanup_command(saved.stem))

    def test_channel_closing_stops_ffmpeg_on_the_frame(self):
        # The computer's ssh going away closes the channel just as Stop does.
        rec = self.recorder()
        rec.start()
        pid = int((self.frame / "ffmpeg.pid").read_text())
        self.channels[0].stdin.close()
        self.wait_for(rec, ("saved", "failed"))
        self.assertEqual((self.frame / "ffmpeg-ended").read_text(), "q")
        with self.assertRaises(ProcessLookupError):
            for _ in range(100):
                os.kill(pid, 0)
                time.sleep(0.05)

    def test_an_ffmpeg_that_ignores_q_is_killed_not_left_recording(self):
        self.env["FAKE_FFMPEG_DEAF"] = "1"
        rec = self.recorder()
        rec.start()
        pid = int((self.frame / "ffmpeg.pid").read_text())
        rec.stop()
        self.wait_for(rec, ("saved", "failed"), timeout=30)
        self.assertFalse((self.frame / "ffmpeg-ended").exists())  # it never finished by itself
        with self.assertRaises(ProcessLookupError):
            for _ in range(100):
                os.kill(pid, 0)
                time.sleep(0.05)

    def test_time_limit_saves_on_its_own(self):
        self.env["FAKE_FFMPEG_RUN"] = "0.3"
        rec = self.recorder()
        rec.start()
        done = self.wait_for(rec, ("saved", "failed"))
        self.assertEqual(done["state"], "saved", done)
        self.assertEqual((self.frame / "ffmpeg-ended").read_text(), "limit")
        with self.assertRaisesRegex(clips.ClipError, "Not recording"):
            rec.stop()

    def test_no_sound_records_video_and_says_so(self):
        self.audio = "audio=0"
        rec = self.recorder()
        started = rec.start()
        self.assertFalse(started["audio"])
        self.assertIn("without sound", started["message"])
        self.assertNotIn("pulse", self.ffmpeg_calls()[0])
        rec.stop()
        done = self.wait_for(rec, ("saved", "failed"))
        self.assertIn("(no sound)", done["message"])

    def test_one_at_a_time(self):
        rec = self.recorder()
        with self.assertRaisesRegex(clips.ClipError, "Not recording"):
            rec.stop()
        rec.start()
        with self.assertRaises(clips.ClipError) as e:
            rec.start()
        self.assertEqual(e.exception.status, 409)
        rec.stop()
        self.wait_for(rec, ("saved",))
        rec.start()  # a new one once the last is saved
        rec.stop()
        self.wait_for(rec, ("saved",))

    def test_failed_start_reports_why(self):
        rec = clips.Recorder(lambda cmd, err: subprocess.Popen(["bash", "-c", "echo 'no v4l2 here' >&2; exit 1"],
                                                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err),
                             lambda cmd, t: "audio=1", self.fetch, lambda fn: fn(), release=self.released.append,
                             folder=self.here)
        with self.assertRaisesRegex(clips.ClipError, "no v4l2 here"):
            rec.start()
        self.assertEqual(rec.status()["state"], "failed")
        self.assertEqual(len(self.released), 1)

    def test_failed_probe_reports_why(self):
        def run(cmd, timeout):
            raise clips.ClipError("No headset view device (/dev/video99). Is SteamVR running?")
        rec = clips.Recorder(mock.Mock(side_effect=AssertionError("recorded anyway")), run, self.fetch,
                             lambda fn: fn(), folder=self.here)
        with self.assertRaisesRegex(clips.ClipError, "Is SteamVR running"):
            rec.start()
        self.assertEqual(rec.status()["state"], "failed")

    def test_empty_recording_is_an_error_not_a_file(self):
        self.env["FAKE_FFMPEG_RUN"] = "0"
        rec = self.recorder()
        with mock.patch.object(clips, "finish_command", lambda name: f"echo 'The recording is empty' >&2; exit 1"):
            rec.start()
            done = self.wait_for(rec, ("saved", "failed"))
        self.assertEqual(done["state"], "failed")
        self.assertIn("The recording is empty", done["error"])
        self.assertFalse(self.here.exists() and any(self.here.iterdir()))
        self.assertEqual(list((self.frame / clips.WORK).iterdir()), [])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg and ffprobe")
class RealFfmpeg(unittest.TestCase):
    """A 65 s recording in Steam's DASH naming (ffmpeg's own dash muxer names files the same
    way), stitched by the real ffmpeg: longer than the 60 s Steam's own export manages."""

    def test_export_of_a_long_recording(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        ud = d / "home" / clips.STEAM_USERDATA
        folder = ud / "123" / "gamerecordings" / "video" / "bg_620_20261020_201950"
        folder.mkdir(parents=True)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000", "-t", "65",
                            "-c:v", "libx264", "-preset", "ultrafast", "-g", "20", "-c:a", "aac",
                            "-seg_duration", "2", "-use_template", "1", "-use_timeline", "0",
                            "-f", "dash", str(folder / "session.mpd")], capture_output=True, text=True)
        if r.returncode != 0 or not (folder / "chunk-stream0-00001.m4s").exists():
            self.skipTest("this ffmpeg can't write DASH with libx264: " + r.stderr[-300:])
        listed = clips.list_recordings(ud)
        self.assertEqual(len(listed), 1)
        self.assertGreater(listed[0]["chunks"], 30)
        got = clips.export(ud, listed[0]["id"], home=d / "home")
        out = d / "home" / got["path"]
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)],
                                          capture_output=True, text=True, check=True).stdout)
        self.assertEqual(sorted(s["codec_type"] for s in probe["streams"]), ["audio", "video"])
        self.assertGreater(float(probe["format"]["duration"]), 64)


if __name__ == "__main__":
    unittest.main()
