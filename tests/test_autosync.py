"""Copying new screenshots and clips to the computer on their own (ui/frame_autosync.py).

The headset is a fake: lists of shots and clips, and save/export functions that
record what they were asked to copy. No SSH, no headset.
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import errno
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
import frame_autosync as fa  # noqa: E402

NOW = 1_800_000_000.0
GB = 1024**3


def shot(n, t, saved=False):
    return {"id": f"1/620/20261020{n:06d}_1.jpg", "time": t, "saved": saved}


def clip(n, t, idle=600, kind="clip", saved=False):
    return {"id": f"1/clips/clip_620_{n}/video/bg", "kind": kind, "time": t, "idle": idle, "saved": saved}


class FakeFrame:
    def __init__(self):
        self.shots, self.clips = [], []
        self.saved, self.exported, self.calls = [], [], []
        self.device, self.busy, self.down = "frame-a", False, False
        self.save_error = self.export_error = None

    def list_shots(self, device):
        assert device == self.device
        self.calls.append("list_shots")
        if self.down:
            raise RuntimeError("ssh: connect to host frame port 22: Connection timed out")
        return {"shots": list(self.shots)}

    def list_clips(self, device):
        assert device == self.device
        self.calls.append("list_clips")
        if self.down:
            raise RuntimeError("ssh: connect to host frame port 22: Connection timed out")
        return {"clips": list(self.clips)}

    def save_shots(self, device, ids):
        self.calls.append("save_shots")
        if self.save_error:
            raise self.save_error
        self.saved.append((device, list(ids)))
        for s in self.shots:
            if s["id"] in ids:
                s["saved"] = True

    def export_clip(self, device, clip_id):
        self.calls.append("export_clip")
        if self.export_error:
            raise self.export_error
        self.exported.append((device, clip_id))
        for c in self.clips:
            if c["id"] == clip_id:
                c["saved"] = True


class AutoSyncTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.frame = FakeFrame()
        self.now = [NOW]
        self.free = [100 * GB]
        self.sync = self.make()

    def make(self):
        f = self.frame
        return fa.AutoSync(f.list_shots, f.save_shots, f.list_clips, f.export_clip,
                           lambda: f.device, lambda: f.busy,
                           offline=lambda e: "The Frame isn't answering." if "timed out" in str(e) else None,
                           shots_folder=self.dir / "Pictures", clips_folder=self.dir / "Videos",
                           path=self.dir / "auto-sync.json", clock=lambda: self.now[0],
                           space=lambda folder: self.free[0])

    def test_off_by_default_and_does_nothing(self):
        self.frame.shots = [shot(1, NOW + 10)]
        self.frame.clips = [clip(1, NOW + 10)]
        s = self.sync.state()
        self.assertFalse(s["screenshots"] or s["clips"])
        self.assertEqual(self.sync.tick(), fa.INTERVAL)
        self.assertEqual(self.frame.calls, [])  # not even a listing
        self.assertFalse((self.dir / "auto-sync.json").exists())

    def test_settings_persist(self):
        self.sync.update({"screenshots": True})
        again = self.make().state()
        self.assertTrue(again["screenshots"])
        self.assertFalse(again["clips"])
        self.assertEqual(again["since"], NOW)
        saved = json.loads((self.dir / "auto-sync.json").read_text())
        self.assertEqual((saved["screenshots"], saved["clips"]), (True, False))

    def test_only_what_is_newer_than_turning_it_on(self):
        self.frame.shots = [shot(1, NOW - 3600), shot(2, NOW + 5), shot(3, NOW + 50, saved=True)]
        self.frame.clips = [clip(1, NOW - 3600), clip(2, NOW + 5)]
        self.sync.update({"screenshots": True, "clips": True})
        self.assertEqual(self.sync.tick(), fa.INTERVAL)
        self.assertEqual(self.frame.saved, [("frame-a", [shot(2, 0)["id"]])])
        self.assertEqual(self.frame.exported, [("frame-a", clip(2, 0)["id"])])
        s = self.sync.state()
        self.assertEqual((s["copied"], s["copied_time"], s["checked"], s["error"]), (2, NOW, NOW, None))

    def test_watermark_moves_when_turned_off_and_on_again(self):
        self.sync.update({"screenshots": True})
        self.now[0] += 1000
        self.sync.update({"clips": True})  # already on: the watermark stays
        self.assertEqual(self.sync.state()["since"], NOW)
        self.sync.update({"screenshots": False, "clips": False})
        self.sync.update({"screenshots": True})
        self.assertEqual(self.sync.state()["since"], NOW + 1000)

    def test_copy_everything_now_once(self):
        self.frame.shots = [shot(1, NOW - 3600), shot(2, NOW - 60)]
        self.frame.clips = [clip(1, NOW - 3600), clip(2, NOW - 60, kind="background")]
        self.sync.copy_all()  # works with the toggles off too
        self.assertTrue(self.sync.state()["pending"])
        self.sync.tick()
        self.assertEqual(self.frame.saved, [("frame-a", [shot(1, 0)["id"], shot(2, 0)["id"]])])
        self.assertEqual(self.frame.exported, [("frame-a", clip(1, 0)["id"])])  # never the background recording
        self.assertFalse(self.sync.state()["pending"])
        self.frame.calls.clear()
        self.sync.tick()
        self.assertEqual(self.frame.calls, [])  # off again afterwards

    def test_not_copied_again_after_deleting_it_here(self):
        self.sync.update({"screenshots": True, "clips": True})
        self.frame.shots = [shot(1, NOW + 5)]
        self.frame.clips = [clip(1, NOW + 5)]
        self.sync.tick()
        for s in self.frame.shots + self.frame.clips:
            s["saved"] = False  # the person deleted the files
        self.frame.saved.clear()
        self.frame.exported.clear()
        self.make().tick()  # remembered across restarts too
        self.assertEqual((self.frame.saved, self.frame.exported), ([], []))

    def test_saved_by_hand_counts_as_copied(self):
        self.sync.update({"screenshots": True})
        self.frame.shots = [shot(1, NOW + 5, saved=True)]
        self.sync.tick()
        self.frame.shots[0]["saved"] = False
        self.sync.tick()
        self.assertEqual(self.frame.saved, [])

    def test_remembered_per_headset(self):
        self.sync.update({"screenshots": True})
        self.frame.shots = [shot(1, NOW + 5)]
        self.sync.tick()
        self.frame.device = "frame-b"
        self.frame.shots = [shot(1, NOW + 5)]  # the same name on another headset
        self.sync.tick()
        self.assertEqual([d for d, _ in self.frame.saved], ["frame-a", "frame-b"])

    def test_clip_still_being_recorded_waits(self):
        self.sync.update({"clips": True})
        self.frame.clips = [clip(1, NOW + 5, idle=4), clip(2, NOW + 6, idle=None)]
        self.sync.tick()
        self.assertEqual(self.frame.exported, [])
        self.assertEqual(self.sync.state()["waiting"], 2)
        self.frame.clips[0]["idle"] = fa.SETTLE + 1
        self.sync.tick()
        self.assertEqual(self.frame.exported, [("frame-a", clip(1, 0)["id"])])
        self.assertEqual(self.sync.state()["waiting"], 1)

    def test_no_headset_no_work(self):
        self.sync.update({"screenshots": True, "clips": True})
        self.frame.device = None
        self.assertEqual(self.sync.tick(), fa.INTERVAL)
        self.assertEqual(self.frame.calls, [])

    def test_waits_for_other_work(self):
        self.sync.update({"screenshots": True, "clips": True})
        self.frame.shots = [shot(1, NOW + 5)]
        self.frame.busy = True
        self.assertEqual(self.sync.tick(), fa.BUSY_WAIT)
        self.assertEqual(self.frame.calls, [])
        self.frame.busy = False
        self.sync.tick()
        self.assertEqual(len(self.frame.saved), 1)

    def test_stops_between_items_when_other_work_starts(self):
        self.sync.update({"clips": True})
        self.frame.clips = [clip(1, NOW + 5), clip(2, NOW + 6)]
        export = self.frame.export_clip

        def then_busy(device, clip_id):
            export(device, clip_id)
            self.frame.busy = True  # an install started meanwhile
        self.frame.export_clip = then_busy
        sync = self.make()
        self.assertEqual(sync.tick(), fa.BUSY_WAIT)
        self.assertEqual(len(self.frame.exported), 1)

    def test_backs_off_while_unreachable(self):
        self.sync.update({"screenshots": True})
        self.frame.down = True
        waits = [self.sync.tick() for _ in range(6)]
        self.assertEqual(waits[:4], [120, 240, 480, 900])
        self.assertEqual(waits[-1], fa.MAX_BACKOFF)
        self.assertEqual(self.sync.state()["error"], "The Frame isn't answering.")
        self.frame.down = False
        self.assertEqual(self.sync.tick(), fa.INTERVAL)
        self.assertIsNone(self.sync.state()["error"])
        self.frame.down = True
        self.assertEqual(self.sync.tick(), 120)  # starts over after a good look

    def test_pauses_when_this_computer_is_nearly_full(self):
        self.sync.update({"screenshots": True})
        self.frame.shots = [shot(1, NOW + 5)]
        self.free[0] = 10 * 1024**2
        self.sync.tick()
        s = self.sync.state()
        self.assertIn("out of space", s["paused"])
        self.assertEqual(self.frame.saved, [])
        self.free[0] = 100 * GB
        self.frame.calls.clear()
        self.sync.tick()
        self.assertEqual(self.frame.calls, [])  # stays paused, also after a restart
        self.assertTrue(self.make().state()["paused"])
        self.sync.resume()
        self.sync.tick()
        self.assertEqual(len(self.frame.saved), 1)
        self.assertIsNone(self.sync.state()["paused"])

    def test_pauses_when_a_copy_runs_out_of_space(self):
        self.sync.update({"screenshots": True, "clips": True})
        self.frame.clips = [clip(1, NOW + 5)]
        self.frame.export_error = RuntimeError("Not enough free space on this computer: it needs 900 MB")
        self.sync.tick()
        self.assertIn("ran out of space", self.sync.state()["paused"])
        self.sync.resume()
        self.frame.export_error = None
        self.frame.shots = [shot(1, NOW + 5)]
        self.frame.save_error = OSError(errno.ENOSPC, "No space left on device")
        self.sync.tick()
        self.assertTrue(self.sync.state()["paused"])

    def test_space_on_the_frame_is_not_a_pause(self):
        self.sync.update({"clips": True})
        self.frame.clips = [clip(1, NOW + 5)]
        self.frame.export_error = RuntimeError("Not enough free space on the Frame to export it: it needs 900 MB")
        self.sync.tick()
        s = self.sync.state()
        self.assertIsNone(s["paused"])
        self.assertIn("Not enough free space on the Frame", s["error"])

    def test_an_item_that_keeps_failing_is_left_alone(self):
        self.sync.update({"clips": True})
        self.frame.clips = [clip(1, NOW + 5)]
        self.frame.export_error = RuntimeError("ffmpeg couldn't join the recording")
        for _ in range(fa.TRIES + 2):
            self.sync.tick()
        self.assertEqual(self.frame.calls.count("export_clip"), fa.TRIES)
        self.assertIn("ffmpeg couldn't join", self.sync.state()["error"] or "")
        self.assertIn("Resume", self.sync.state()["error"] or "")

    def test_explicit_retry_recovers_without_recopying_successful_items(self):
        for kind in ("shots", "clips"):
            for action in ("resume", "copy_all"):
                with self.subTest(kind=kind, action=action):
                    self.frame = FakeFrame()
                    f = self.frame
                    sync = self.make()
                    sync.update({"screenshots": True, "clips": True})
                    f.shots, f.clips = [shot(1, NOW + 5)], [clip(1, NOW + 5)]
                    error_attr = "save_error" if kind == "shots" else "export_error"
                    copy_call = "save_shots" if kind == "shots" else "export_clip"
                    setattr(f, error_attr, RuntimeError("source not ready"))
                    for _ in range(fa.TRIES + 2):
                        sync.tick()
                    self.assertEqual(f.calls.count(copy_call), fa.TRIES)
                    self.assertIn("source not ready", sync.state()["error"] or "")
                    setattr(f, error_attr, None)
                    sync.tick()  # recovery alone must not create unlimited automatic retries
                    self.assertEqual(f.calls.count(copy_call), fa.TRIES)
                    getattr(sync, action)()
                    sync.tick()
                    self.assertEqual(f.saved, [("frame-a", [shot(1, 0)["id"]])])
                    self.assertEqual(f.exported, [("frame-a", clip(1, 0)["id"])])
                    self.assertIsNone(sync.state()["error"])
                    # Resume preserves the per-headset ledger even if a local file was deleted.
                    for item in f.shots + f.clips:
                        item["saved"] = False
                    sync.resume()
                    sync.tick()
                    self.assertEqual((len(f.saved), len(f.exported)), (1, 1))
                    self.sync.path.unlink(missing_ok=True)

    def test_explicit_retry_is_still_bounded(self):
        self.sync.update({"clips": True})
        self.frame.clips = [clip(1, NOW + 5)]
        self.frame.export_error = RuntimeError("bad source")
        for action in ("resume", "copy_all"):
            for _ in range(fa.TRIES + 2):
                self.sync.tick()
            before = self.frame.calls.count("export_clip")
            getattr(self.sync, action)()
            for _ in range(fa.TRIES + 2):
                self.sync.tick()
            self.assertEqual(self.frame.calls.count("export_clip") - before, fa.TRIES)
            self.assertIn("bad source", self.sync.state()["error"] or "")

    def test_failed_item_saved_by_hand_clears_error(self):
        self.sync.update({"clips": True})
        self.frame.clips = [clip(1, NOW + 5)]
        self.frame.export_error = RuntimeError("bad source")
        for _ in range(fa.TRIES + 1):
            self.sync.tick()
        self.frame.clips[0]["saved"] = True
        self.sync.tick()
        self.assertIsNone(self.sync.state()["error"])
        self.assertIn(clip(1, 0)["id"], self.sync._synced("frame-a", "clips"))

    def test_switch_after_capture_does_not_list_the_new_headset(self):
        self.sync.update({"screenshots": True, "clips": True})
        def switched():
            self.frame.device = "frame-b"
            return False
        self.sync.busy = switched  # tick has already captured frame-a
        self.assertEqual(self.sync.tick(), fa.BUSY_WAIT)
        self.assertEqual(self.frame.calls, [])

    def test_list_callbacks_receive_the_captured_device(self):
        self.sync.update({"screenshots": True, "clips": True})
        self.sync.list_shots = mock.Mock(return_value={"shots": []})
        self.sync.list_clips = mock.Mock(return_value={"clips": []})
        self.sync.tick()
        self.sync.list_shots.assert_called_once_with("frame-a")
        self.sync.list_clips.assert_called_once_with("frame-a")

    def test_switch_during_listing_does_not_mark_or_copy_its_results(self):
        for kind, item in (("shots", shot(1, NOW + 5)), ("clips", clip(1, NOW + 5))):
            with self.subTest(kind=kind):
                self.frame.device = "frame-a"
                self.sync.update({"screenshots": kind == "shots", "clips": kind == "clips"})
                def listing(*_args):
                    self.frame.device = "frame-b"
                    return {kind: [dict(item, saved=True), dict(item, id="uncopied", saved=False)]}
                setattr(self.sync, "list_" + kind, listing)
                self.assertEqual(self.sync.tick(), fa.BUSY_WAIT)
                self.assertEqual(self.sync._synced("frame-a", kind), set())
                self.assertEqual(self.sync._synced("frame-b", kind), set())
                self.assertEqual((self.frame.saved, self.frame.exported), ([], []))

    def test_switch_between_kinds_does_not_read_clips_or_mark_transfer(self):
        self.sync.update({"screenshots": True, "clips": True})
        self.frame.shots = [shot(1, NOW + 5)]
        self.frame.clips = [clip(1, NOW + 5, saved=True)]
        save = self.sync.save_shots
        def then_switch(device, ids):
            save(device, ids)
            self.frame.device = "frame-b"
        self.sync.save_shots = then_switch
        self.assertEqual(self.sync.tick(), fa.BUSY_WAIT)
        self.assertNotIn("list_clips", self.frame.calls)
        self.assertEqual(self.sync._synced("frame-a", "clips"), set())
        self.assertEqual(self.sync._synced("frame-a", "shots"), set())

    def test_switch_after_bookkeeping_stops_before_next_kind(self):
        self.sync.update({"screenshots": True, "clips": True})
        self.frame.shots = [shot(1, NOW + 5, saved=True)]
        mark = self.sync._mark
        def then_switch(device, kind, ids):
            mark(device, kind, ids)
            self.frame.device = "frame-b"
        self.sync._mark = then_switch
        self.assertEqual(self.sync.tick(), fa.BUSY_WAIT)
        self.assertNotIn("list_clips", self.frame.calls)

    def test_switch_before_transfer_does_not_copy(self):
        for kind, item in (("shots", shot(1, NOW + 5)), ("clips", clip(1, NOW + 5))):
            with self.subTest(kind=kind):
                self.frame.device = "frame-a"
                self.sync.update({"screenshots": kind == "shots", "clips": kind == "clips"})
                setattr(self.frame, kind, [item])
                def switched_space(_folder):
                    self.frame.device = "frame-b"
                    return 100 * GB
                self.sync.space = switched_space
                self.assertEqual(self.sync.tick(), fa.BUSY_WAIT)
                self.assertEqual((self.frame.saved, self.frame.exported), ([], []))

    def test_worker_stops(self):
        stop = threading.Event()
        t = threading.Thread(target=self.sync.run, args=(stop,), daemon=True)
        t.start()
        stop.set()
        self.sync.update({})  # wakes it
        t.join(5)
        self.assertFalse(t.is_alive())


class Server(unittest.TestCase):
    def test_switch_at_list_callback_entry_does_not_read_or_mark_the_new_headset(self):
        import server
        with tempfile.TemporaryDirectory() as folder:
            for kind in ("shots", "clips"):
                with self.subTest(kind=kind):
                    active = {"id": "frame-a"}
                    link = mock.Mock()
                    link.active_device.side_effect = lambda: dict(active)
                    listing = mock.Mock(return_value={kind: [
                        shot(1, NOW + 5, saved=True) if kind == "shots" else clip(1, NOW + 5, saved=True)]})
                    def switch_then_list(device):
                        active["id"] = "frame-b"
                        return server._sync_list(listing)(device)
                    with mock.patch.object(server, "LINK", link), mock.patch.object(server, "_work", [0]):
                        sync = fa.AutoSync(switch_then_list, mock.Mock(), switch_then_list, mock.Mock(),
                                           lambda: active["id"], lambda: False,
                                           path=Path(folder) / (kind + ".json"), clock=lambda: NOW)
                        sync.update({"screenshots": kind == "shots", "clips": kind == "clips"})
                        sync.tick()
                        listing.assert_not_called()
                        sync.save_shots.assert_not_called()
                        sync.export_clip.assert_not_called()
                        self.assertEqual(sync._synced("frame-a", kind), set())
                        self.assertEqual(sync._synced("frame-b", kind), set())
                        self.assertIn("switched headsets", sync.state()["error"])
                        self.assertEqual(server._work[0], 0)

    def test_listing_rejects_switch_before_reserving_work(self):
        import server
        link = mock.Mock()
        link.active_device.return_value = {"id": "frame-b"}
        listing = mock.Mock(return_value={"shots": [shot(1, NOW, saved=True)]})
        with mock.patch.object(server, "LINK", link), mock.patch.object(server, "_work", [0]):
            with self.assertRaisesRegex(server.Failure, "switched headsets"):
                server._sync_list(listing)("frame-a")
            listing.assert_not_called()
            self.assertEqual(server._work[0], 0)

    def test_listing_reserves_work_on_the_captured_device(self):
        import server
        link = mock.Mock()
        link.active_device.return_value = {"id": "frame-a", "name": "Frame A"}
        def listing():
            self.assertGreater(server._work[0], 0)
            with self.assertRaises(server.Failure):
                server.devices_post({"action": "use", "id": "frame-b"})
            return {"shots": []}
        with mock.patch.object(server, "LINK", link), \
                mock.patch.object(server, "PRIVATE", False), mock.patch.object(server, "_work", [0]):
            self.assertEqual(server._sync_list(listing)("frame-a"), {"shots": []})
            self.assertEqual(server._work[0], 0)

    def test_copy_rejects_switch_after_listing(self):
        import server
        link = mock.Mock()
        link.active_device.return_value = {"id": "frame-a"}
        with mock.patch.object(server, "LINK", link), mock.patch.object(server, "_work", [0]), \
                mock.patch.object(server, "save_shots") as save, \
                mock.patch.object(server.frame_clips, "export_clip") as export:
            server._sync_list(lambda: {"shots": []})("frame-a")
            link.active_device.return_value = {"id": "frame-b"}
            for copy in (lambda: server._sync_shots("frame-a", [shot(1, NOW)["id"]]),
                         lambda: server._sync_clip("frame-a", clip(1, NOW)["id"])):
                with self.assertRaisesRegex(server.Failure, "switched headsets"):
                    copy()
            save.assert_not_called()
            export.assert_not_called()
            self.assertEqual(server._work[0], 0)

    def test_route_and_settings(self):
        import server
        self.assertIn("/api/autosync", server.POST)
        with self.assertRaises(server.Failure):
            server.auto_sync({"action": "explode"})
        state = server.auto_sync({"action": "settings", "screenshots": "yes"})  # not a bool: ignored
        self.assertFalse(state["screenshots"])
        if server.LINK is None:
            with self.assertRaises(server.Failure):
                server.auto_sync({"action": "now"})  # nothing connected


@unittest.skipUnless(shutil.which("node"), "Node exercises the Settings renderer")
class Settings(unittest.TestCase):
    def test_resume_is_available_after_a_copy_error(self):
        page = (Path(__file__).resolve().parents[1] / "ui/index.html").read_text(encoding="utf-8")
        script = page.split("const autoSync =", 1)[1].split("async function loadAutoSync", 1)[0]
        harness = r'''
const assert = require('node:assert/strict');
const nodes = {};
const $ = id => nodes[id] ||= {};
const HOST = {mobile: false};
const esc = value => value;
'''
        checks = r'''
for (const state of [{error: 'Could not copy clip'}, {paused: 'Disk full'}, {}]) {
  renderAutoSync(state);
  assert.equal($('syncResume').hidden, !(state.error || state.paused));
  if (state.error) assert.match($('syncStatus').textContent, /Could not copy clip/);
}
'''
        result = subprocess.run(["node", "-e", harness + "const autoSync =" + script + checks],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
