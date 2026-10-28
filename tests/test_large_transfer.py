"""Large desktop file copies use the selected local path, not an 8 GiB HTTP upload."""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import http.client
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
import server


class LargeTransfer(unittest.TestCase):
    def test_desktop_http_copy_stays_on_selected_headset(self):
        with tempfile.TemporaryDirectory() as tmp, server.LoopbackServer(("127.0.0.1", 0), server.Handler) as httpd:
            source = Path(tmp) / "usb-file.bin"
            source.write_bytes(b"a small stand-in for a large file")
            worker = threading.Thread(target=httpd.serve_forever, daemon=True)
            worker.start()
            link = mock.Mock()
            link.active_device.return_value = {"id": "frame-a"}
            body = json.dumps({"action": "copy-local", "path": str(source)})

            def copy(device):
                conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
                try:
                    conn.request("POST", "/api/transfer", body, {"X-Frame-UI": server.UI_KEY,
                                 "X-Frame-Device": device, "Content-Type": "application/json"})
                    response = conn.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    conn.close()

            try:
                with mock.patch.dict(os.environ, {"FRAME_CONTROL_APP": "1"}), \
                     mock.patch.object(server, "LINK", link), \
                     mock.patch.object(server, "push_file", return_value="Sent usb-file.bin to ~/Downloads/") as push:
                    self.assertEqual(copy("frame-b")[0], 409)
                    push.assert_not_called()
                    self.assertEqual(copy("frame-a"), (200, {"message": "Sent usb-file.bin to ~/Downloads/"}))
                    push.assert_called_once_with(source)
            finally:
                httpd.shutdown()
                worker.join(timeout=5)

    def test_27_gib_local_file_reaches_direct_copy(self):
        source = Path(os.path.abspath("large-file.bin"))
        size = 27 * 1024 ** 3
        info = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_size=size)
        with mock.patch.dict(os.environ, {"FRAME_CONTROL_APP": "1"}), \
             mock.patch.object(Path, "stat", return_value=info), \
             mock.patch.object(server, "push_file", return_value="Sent large-file.bin to ~/Downloads/") as push:
            self.assertEqual(server.transfer_local({"action": "copy-local", "path": str(source)}),
                             {"message": "Sent large-file.bin to ~/Downloads/"})
        push.assert_called_once_with(source)

    def test_direct_copy_validates_desktop_file_before_ssh(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"FRAME_CONTROL_APP": "1"}), \
             mock.patch.object(server, "push_file") as push:
            empty = Path(tmp) / "empty.bin"
            empty.touch()
            hidden = Path(tmp) / ".hidden"
            hidden.write_bytes(b"x")
            for path in ("relative.bin", str(Path(tmp) / "missing.bin"), tmp,
                         str(empty), str(hidden)):
                with self.subTest(path=path), self.assertRaises(server.Failure):
                    server.transfer_local({"action": "copy-local", "path": path})
        push.assert_not_called()

    def test_large_copy_gets_more_than_one_hour_without_loading_file(self):
        info = SimpleNamespace(st_size=27 * 1024 ** 3)
        result = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(Path, "stat", return_value=info), \
             mock.patch.object(server.shutil, "which", return_value=None), \
             mock.patch.object(server.frame_host, "run_ssh", return_value=result) as run:
            self.assertEqual(server.push_file("/tmp/large-file.bin"),
                             "Sent large-file.bin to ~/Downloads/")
        self.assertGreater(run.call_args.kwargs["timeout"], 3600)
