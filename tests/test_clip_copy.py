"""Clip destinations through the server and automatic copying, without a headset."""
import sandbox  # noqa: F401
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
import frame_autosync
import frame_clips
import server


IDS = ["1/clips/clip_620/video/bg", "2/clips/clip_620/video/bg",
       "1/clips/clip_620/video/other", "1/clips/other/video/bg"]
NOW = 1800000000


class ClipCopyTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="frame-clip-copy-"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.device = "frame-a"
        self.link = mock.Mock()
        self.link.active_device.side_effect = lambda: {"id": self.device, "name": self.device}
        self.link.snapshot.return_value = {"phase": "connected"}
        self.exports = []
        self.payload = None
        for name, value in (("LINK", self.link), ("LOCAL", False)):
            patch = mock.patch.object(server, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(frame_clips, "VIDEOS_DIR", self.folder)
        patch.start()
        self.addCleanup(patch.stop)
        for name, fn in (("_clips_frame", self.frame), ("fetch_file", self.fetch),
                         ("ssh", lambda *a, **k: "")):
            patch = mock.patch.object(server, name, side_effect=fn)
            patch.start()
            self.addCleanup(patch.stop)
        (self.folder / "clip_620.mp4").write_bytes(b"legacy export")

    def frame(self, args, timeout):
        if args == ["list"]:
            return {"clips": [{"id": cid, "kind": "clip", "time": NOW + 5, "idle": 60} for cid in IDS]}
        self.exports.append((self.device, args[1]))
        self.payload = f"{self.device}: {args[1]}".encode()
        return {"path": f"{frame_clips.WORK}/export-0123456789abcdef/clip_620.mp4",
                "size": len(self.payload)}

    def fetch(self, remote, target):
        target.write_bytes(self.payload)

    def test_manual_export_lists_only_matching_identity_and_keeps_job_shape(self):
        with mock.patch.object(server, "start_job", side_effect=lambda label, work: work()) as job:
            for device in ("frame-a", "frame-b"):
                self.device = device
                self.assertFalse(any(c["saved"] for c in server.list_clips()["clips"]))
                result = server.export_clip({"id": IDS[0]})
                self.assertEqual(set(result), {"message", "file"})
                self.assertEqual(Path(result["file"]).read_bytes(), f"{device}: {IDS[0]}".encode())
                self.assertEqual([c["saved"] for c in server.list_clips()["clips"]], [True, False, False, False])
            self.assertEqual(job.call_args.args[0], "Export clip_620.mp4")
        first = frame_clips.clip_local_path(IDS[0], "frame-a", self.folder)
        self.assertEqual(first.read_bytes(), f"frame-a: {IDS[0]}".encode())
        self.assertEqual((self.folder / "clip_620.mp4").read_bytes(), b"legacy export")

    def test_auto_sync_uses_same_identity_as_manual_exports(self):
        with mock.patch.object(server, "start_job", side_effect=lambda label, work: work()):
            server.export_clip({"id": IDS[0]})
        sync = frame_autosync.AutoSync(
            server._sync_list(server.list_shots), server._sync_shots,
            server._sync_list(server.list_clips), server._sync_clip,
            server._sync_device, lambda: False, shots_folder=self.folder / "shots",
            clips_folder=self.folder, path=self.folder / "auto-sync.json", clock=lambda: NOW,
            space=lambda folder: 100 * 1024**3)
        sync.update({"clips": True})
        sync.tick()
        self.assertEqual(self.exports, [("frame-a", cid) for cid in IDS])
        self.device = "frame-b"
        sync.tick()
        self.assertEqual(self.exports, [(device, cid) for device in ("frame-a", "frame-b") for cid in IDS])
        sync.tick()
        self.assertEqual(len(self.exports), 8)
        for device in ("frame-a", "frame-b"):
            for cid in IDS:
                target = frame_clips.clip_local_path(cid, device, self.folder)
                self.assertEqual(target.read_bytes(), f"{device}: {cid}".encode())
        self.assertEqual((self.folder / "clip_620.mp4").read_bytes(), b"legacy export")

    def test_delayed_job_refuses_a_different_headset(self):
        with mock.patch.object(server, "start_job", return_value={"job": "queued"}) as job:
            self.assertEqual(server.export_clip({"id": IDS[0]}), {"job": "queued"})
        self.device = "frame-b"
        with self.assertRaises(server.Failure) as error:
            job.call_args.args[1]()
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.exports, [])

    def test_local_and_headset_modes_reject_steam_clip_exports(self):
        for headset in (False, True):
            with self.subTest(headset=headset), mock.patch.object(server, "LOCAL", True), \
                    mock.patch.object(server, "HEADSET_RUNTIME", headset):
                for action in (server.list_clips, lambda: server.export_clip({"id": IDS[0]}),
                               lambda: server.auto_sync({"action": "now"})):
                    with self.assertRaises(server.Failure) as error:
                        action()
                    self.assertEqual(error.exception.status, 400)
        self.assertEqual(self.exports, [])


if __name__ == "__main__":
    unittest.main()
