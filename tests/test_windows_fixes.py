"""Windows-only paths, faked on any OS: ~/.ssh/config's ACL and link-local IPv6 zones.

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ui"))

import frame_host  # noqa: E402
import frame_devices as fd  # noqa: E402

REFUSED = ("Bad permissions. Try removing permissions for user: UNKNOWN\\UNKNOWN (S-1-5-21-1-2-3-1000) "
           "on file C:/Users/bob/.ssh/config.\r\nBad owner or permissions on C:\\Users\\bob/.ssh/config\r\n")


def ran(*results):
    """subprocess.run stand-in answering whoami, then icacls."""
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return results[len(calls) - 1]
    return run, calls


class MakePrivate(unittest.TestCase):
    def test_windows_sets_owner_only_acl_by_sid(self):
        run, calls = ran(subprocess.CompletedProcess([], 0, '"desktop\\björn","S-1-5-21-9-8-7-1001"\r\n'.encode("cp850")),
                         subprocess.CompletedProcess([], 0))
        with mock.patch.object(frame_host, "WINDOWS", True), mock.patch.object(frame_host.subprocess, "run", run):
            self.assertTrue(frame_host.make_private(Path("C:/x/config")))
        self.assertEqual(calls[1][1:], [str(Path("C:/x/config")), "/inheritance:r", "/grant:r",
                                        "*S-1-5-21-9-8-7-1001:F", "*S-1-5-18:F", "*S-1-5-32-544:F"])

    def test_windows_falls_back_to_username_and_reports_failure(self):
        run, calls = ran(subprocess.CompletedProcess([], 1, b""), subprocess.CompletedProcess([], 5))
        with mock.patch.object(frame_host, "WINDOWS", True), mock.patch.object(frame_host.subprocess, "run", run), \
                mock.patch.dict(os.environ, {"USERNAME": "bob"}):
            self.assertFalse(frame_host.make_private(Path("config")))
        self.assertIn("bob:F", calls[1])

    @unittest.skipIf(os.name == "nt", "POSIX modes")
    def test_posix_chmods_600(self):
        with tempfile.NamedTemporaryFile() as f:
            os.chmod(f.name, 0o644)
            self.assertTrue(frame_host.make_private(f.name))
            self.assertEqual(os.stat(f.name).st_mode & 0o777, 0o600)


class ConfigWrites(unittest.TestCase):
    def setUp(self):
        self.ssh = Path(tempfile.mkdtemp(prefix="frame-acl-"))
        self.addCleanup(shutil.rmtree, self.ssh, ignore_errors=True)
        self.config = self.ssh / "config"

    def test_devices_and_connect_writes_make_the_file_private(self):
        import frame_connect as fc
        self.config.write_text("Host other\n  User me\n", encoding="utf-8")
        with mock.patch.object(frame_host, "make_private", return_value=True) as private, \
                mock.patch.object(fc, "SSH_DIR", self.ssh), mock.patch.object(fc, "CONFIG", self.config):
            fc.write_config("10.0.0.5")
            self.assertTrue(fd.repair_permissions(self.config))
            fd.rewrite_block("frame", path=self.config, user="deck")
        self.assertEqual(private.call_count, 3)
        self.assertIn("User deck", self.config.read_text(encoding="utf-8"))
        self.assertTrue(all(Path(c.args[0]).parent == self.ssh for c in private.call_args_list))
        self.assertIn("Host other", self.config.read_text(encoding="utf-8"))

    def test_setup_runs_isolated_as_the_app_starts_it(self):
        r = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "ui" / "frame_connect.py"), "--help"],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
        self.assertNotIn("ModuleNotFoundError", r.stderr)
        self.assertIn("frame_connect.py", r.stdout + r.stderr)

    def test_repair_keeps_the_bytes_and_skips_a_missing_file(self):
        self.assertFalse(fd.repair_permissions(self.config))
        data = "# caf\xe9 (ANSI, not UTF-8)\r\nHost a\r\n".encode("cp1252")
        self.config.write_bytes(data)
        with mock.patch.object(frame_host, "make_private", return_value=True):
            self.assertTrue(fd.repair_permissions(self.config))
        self.assertEqual(self.config.read_bytes(), data)

    def test_repair_fails_without_the_acl_and_leaves_the_file(self):
        self.config.write_bytes(b"Host a\n")
        before = self.config.stat().st_ino
        with mock.patch.object(frame_host, "make_private", return_value=False):
            self.assertFalse(fd.repair_permissions(self.config))
        self.assertEqual((self.config.read_bytes(), self.config.stat().st_ino), (b"Host a\n", before))
        self.assertEqual(sorted(f.name for f in self.ssh.iterdir()), ["config", fd.LOCK_NAME])


class ServerRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server = server

    def setUp(self):
        self.ssh = Path(tempfile.mkdtemp(prefix="frame-acl-"))
        self.addCleanup(shutil.rmtree, self.ssh, ignore_errors=True)
        (self.ssh / "config").write_text("Host a\n", encoding="utf-8")
        patches = [mock.patch.dict(os.environ, {"FRAME_CONTROL_SSH_DIR": str(self.ssh)}),
                   mock.patch.object(frame_host, "WINDOWS", True),
                   mock.patch.object(self.server, "_config_repaired", False)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_repairs_the_refused_config_once(self):
        with mock.patch.object(fd, "repair_permissions", return_value=True) as repair:
            self.assertTrue(self.server.repair_ssh_config(REFUSED))
            self.assertFalse(self.server.repair_ssh_config(REFUSED))
        repair.assert_called_once()

    def test_leaves_other_files_and_errors_alone(self):
        key = REFUSED.replace(".ssh/config", ".ssh/id_ed25519_frame")
        with mock.patch.object(fd, "repair_permissions") as repair:
            self.assertFalse(self.server.repair_ssh_config(key))
            self.assertFalse(self.server.repair_ssh_config("ssh: connect to host frame port 22: timed out"))
            with mock.patch.object(frame_host, "WINDOWS", False):
                self.assertFalse(self.server.repair_ssh_config(REFUSED))
        repair.assert_not_called()

    def test_ssh_retries_after_repairing(self):
        results = iter([subprocess.CompletedProcess([], 255, "", REFUSED), subprocess.CompletedProcess([], 0, "ok", "")])
        with mock.patch.object(frame_host, "run_ssh", lambda *a, **k: next(results)), \
                mock.patch.object(fd, "repair_permissions", return_value=True), \
                mock.patch.object(self.server, "LINK", None):
            self.assertEqual(self.server.ssh("true"), "ok")


class LinkLocalZone(unittest.TestCase):
    """A .local name answering on fe80::: Windows' ssh needs fe80::1%12, not %wireless_32768."""

    def probe(self, windows):
        import frame_link as fl
        info = [(fl.socket.AF_INET6, fl.socket.SOCK_STREAM, 6, "", ("fe80::1", 22, 0, 12))]
        sock = mock.MagicMock()
        with mock.patch.object(frame_host, "WINDOWS", windows), \
                mock.patch.object(fl.socket, "getaddrinfo", return_value=info), \
                mock.patch.object(fl.socket, "socket", return_value=sock), \
                mock.patch.object(fl.socket, "if_indextoname", return_value="wireless_32768", create=True):
            return fl.probe("frame.local", 22)["ip"]

    def test_windows_uses_the_numeric_zone(self):
        self.assertEqual(self.probe(True), "fe80::1%12")

    def test_elsewhere_uses_the_interface_name(self):
        self.assertEqual(self.probe(False), "fe80::1%wireless_32768")


if __name__ == "__main__":
    unittest.main()
