"""Screenshot copies retain the headset, Steam account and game identity."""
import sandbox  # noqa: F401
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui"))
import server  # noqa: E402


NAME = "20261025020000_1.jpg"
FIRST = f"1/620/{NAME}"
SECOND = f"1/730/{NAME}"


class ShotCopyTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="frame-shot-copy-"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        patch = mock.patch.object(server, "SHOTS_DIR", self.folder)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(server, "LINK", None)
        patch.start()
        self.addCleanup(patch.stop)
        self.payloads = {
            server.shot_path(FIRST): b"first game",
            server.shot_path(SECOND): b"second game",
        }

    def scp(self, argv, **_kwargs):
        target = Path(argv[-1])
        for source in argv[1:-1]:
            if not source.startswith("frame-a:") and not source.startswith("frame-b:"):
                continue
            remote = source.split(":", 1)[1]
            (target / Path(remote).name).write_bytes(self.payloads[remote])
        return subprocess.CompletedProcess(argv, 0, "", "")

    def test_equal_names_survive_across_games_and_headsets(self):
        # A pre-upgrade flat file has no provable source identity. Leave it alone.
        legacy = self.folder / NAME
        legacy.write_bytes(b"older screenshot")
        with mock.patch.object(server, "FRAME", "frame-a"), \
             mock.patch.object(server, "ensure_master"), \
             mock.patch.object(server.frame_host, "run_ssh", side_effect=self.scp) as copy:
            self.assertEqual(server.save_shots({"ids": [FIRST, SECOND]})["saved"], 2)
            self.assertEqual(copy.call_count, 2)  # scp cannot flatten equal names together
            first = server.shot_local_path(FIRST)
            second = server.shot_local_path(SECOND)
            self.assertEqual(first.read_bytes(), b"first game")
            self.assertEqual(second.read_bytes(), b"second game")
            self.assertNotEqual(first, second)
            self.assertEqual(legacy.read_bytes(), b"older screenshot")
            listing = "\n".join([
                f"1/760/remote/620/screenshots/{NAME}\t10\t1792893600",
                f"1/760/remote/730/screenshots/{NAME}\t11\t1792893601",
            ])
            with mock.patch.object(server, "ssh", return_value=listing):
                self.assertTrue(all(s["saved"] for s in server.list_shots()["shots"]))
            with mock.patch.object(server.frame_host, "reveal_path") as reveal:
                server.open_thing({"what": "shot", "id": SECOND})
                reveal.assert_called_once_with(second)

        self.payloads[server.shot_path(FIRST)] = b"another headset"
        with mock.patch.object(server, "FRAME", "frame-b"), \
             mock.patch.object(server, "ensure_master"), \
             mock.patch.object(server.frame_host, "run_ssh", side_effect=self.scp):
            self.assertEqual(server.save_shots({"ids": [FIRST]})["saved"], 1)
            other = server.shot_local_path(FIRST)
            self.assertNotEqual(other, first)
            self.assertEqual(other.read_bytes(), b"another headset")
            self.assertEqual(first.read_bytes(), b"first game")

    def test_missing_staged_file_does_not_claim_saved(self):
        with mock.patch.object(server, "FRAME", "frame-a"), \
             mock.patch.object(server, "ensure_master"), \
             mock.patch.object(server.frame_host, "run_ssh",
                               return_value=subprocess.CompletedProcess([], 0, "", "")):
            with self.assertRaisesRegex(server.Failure, "did not contain every"):
                server.save_shots({"ids": [FIRST]})
            self.assertFalse(server.shot_local_path(FIRST).exists())
            self.assertFalse(list(self.folder.glob(".incoming-*")))


if __name__ == "__main__":
    unittest.main()
