"""The clipboard both ways: the headset's read script, the server's answers, and the
writer for this computer's clipboard on each platform. No headset: SSH and every
clipboard program are mocked, and the read script runs against stub pgrep and qdbus6."""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import base64
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
import server  # noqa: E402

TEXT = "héllo, 世界 🎧\nsecond line\n\n"  # accents, CJK, an emoji outside the BMP, trailing newlines


def b64(text):
    return base64.b64encode(text.encode()).decode()


class ReadCommand(unittest.TestCase):
    def test_reads_klipper_on_the_desktop_bus(self):
        self.assertIn("org.kde.klipper.klipper.getClipboardContents", server.COPY)
        self.assertIn("DBUS_SESSION_BUS_ADDRESS=$bus qdbus6 org.kde.klipper /klipper", server.COPY)
        self.assertIn(server.DESKTOP_CLOSED, server.COPY)
        self.assertIn(server.CLIPBOARD_TOO_BIG, server.COPY)
        self.assertIn(f"-gt {server.CLIPBOARD_LIMIT + 1} ]", server.COPY)  # the limit, plus qdbus6's newline
        self.assertIn("base64 -w 0", server.COPY)

    def test_command_carries_the_script_intact(self):
        encoded = server.COPY_CMD.split("echo ", 1)[1].split(" |", 1)[0]
        self.assertEqual(base64.b64decode(encoded).decode(), server.COPY)
        self.assertNotIn("'", server.COPY_CMD)

    def test_send_still_uses_the_same_bus(self):
        self.assertIn(server.DESKTOP_BUS, server.PASTE)
        self.assertIn(server.DESKTOP_BUS, server.COPY)
        self.assertIn("setClipboardContents", server.PASTE)


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash") and shutil.which("base64"),
                     "the script reads /proc, as on the Frame")
class ReadScript(unittest.TestCase):
    """server.COPY for real, with plasmashell's pid and Klipper stubbed."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="frame-clip-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.clip = self.dir / "clip"
        # A process whose environment holds the desktop's bus address, standing in for plasmashell.
        self.plasma = subprocess.Popen(["sleep", "60"], env={**os.environ, "DBUS_SESSION_BUS_ADDRESS": "unix:path=/fake"})
        self.addCleanup(self.plasma.wait)
        self.addCleanup(self.plasma.kill)
        (self.dir / "pgrep").write_text(f'#!/bin/sh\n[ -e "{self.dir}/closed" ] || echo {self.plasma.pid}\n')
        (self.dir / "qdbus6").write_text(
            '#!/bin/sh\n[ "$DBUS_SESSION_BUS_ADDRESS" = unix:path=/fake ] || exit 1\n'
            f'[ "$3" = org.kde.klipper.klipper.getClipboardContents ] || exit 1\ncat "{self.clip}"; echo\n')
        for name in ("pgrep", "qdbus6"):
            (self.dir / name).chmod(0o755)

    def run_script(self):
        def local_ssh(remote, **kw):
            r = subprocess.run(["bash", "-c", server.COPY], capture_output=True, text=True,
                               env={**os.environ, "PATH": f"{self.dir}:{os.environ['PATH']}"})
            if r.returncode:
                raise server.Failure(r.stderr.strip())
            return r.stdout
        with mock.patch.object(server, "ssh", local_ssh):
            return server.headset_clipboard()

    def test_unicode_and_newlines_come_back_exactly(self):
        self.clip.write_bytes(TEXT.encode())
        self.assertEqual(self.run_script(), TEXT)

    def test_empty(self):
        self.clip.write_bytes(b"")
        with self.assertRaises(server.Failure) as cm:
            self.run_script()
        self.assertEqual(cm.exception.status, 400)
        self.assertIn("empty", str(cm.exception))

    def test_too_big_is_refused_on_the_headset(self):
        self.clip.write_bytes(b"x" * (server.CLIPBOARD_LIMIT + 1))
        with self.assertRaises(server.Failure) as cm:
            self.run_script()
        self.assertEqual(cm.exception.status, 413)
        self.assertIn("1 MB", str(cm.exception))
        self.clip.write_bytes(b"x" * server.CLIPBOARD_LIMIT)
        self.assertEqual(len(self.run_script()), server.CLIPBOARD_LIMIT)

    def test_desktop_closed(self):
        (self.dir / "closed").touch()
        with self.assertRaises(server.Failure) as cm:
            self.run_script()
        self.assertEqual(cm.exception.status, 409)


class HeadsetClipboard(unittest.TestCase):
    def read(self, out=None, error=None):
        def fake_ssh(remote, **kw):
            self.assertEqual(remote, server.COPY_CMD)
            self.assertNotIn("stdin", kw)
            if error:
                raise server.Failure(error)
            return out
        with mock.patch.object(server, "ssh", fake_ssh):
            return server.headset_clipboard()

    def test_drops_only_qdbus6s_newline(self):
        self.assertEqual(self.read(b64(TEXT + "\n") + "\n"), TEXT)
        self.assertEqual(self.read(b64("one line\n")), "one line")

    def test_empty_and_images_say_so(self):
        for out, words in ((b64("\n"), "empty"), ("", "empty"), (b64("▨ 640x480 32bpp\n"), "image")):
            with self.assertRaises(server.Failure) as cm:
                self.read(out)
            self.assertEqual(cm.exception.status, 400)
            self.assertIn(words, str(cm.exception))

    def test_unreadable_output_is_a_fault(self):
        for out in ("not base64!", base64.b64encode(b"\xff\xfe\n").decode()):
            with self.assertRaises(server.Failure) as cm:
                self.read(out)
            self.assertEqual(cm.exception.status, 502)

    def test_failures(self):
        for error, status in (("The headset's desktop isn't open (plasmashell is not running).", 409),
                              ("The headset's clipboard holds too much to copy (over 1 MB).", 413),
                              ("Klipper call failed (bus: none)", 502)):
            with self.assertRaises(server.Failure) as cm:
                self.read(error=error)
            self.assertEqual(cm.exception.status, status, error)


class ClipboardRequests(unittest.TestCase):
    def test_read_returns_the_text_for_the_page(self):
        with mock.patch.object(server, "headset_clipboard", return_value=TEXT):
            out = server.clipboard({"read": True})
        self.assertEqual(out["text"], TEXT)
        self.assertNotIn(TEXT, out["message"])

    def test_to_computer_sets_this_computers_clipboard(self):
        with mock.patch.object(server, "headset_clipboard", return_value=TEXT), \
                mock.patch.object(frame_host, "set_clipboard_text") as put:
            out = server.clipboard({"toComputer": True})
        put.assert_called_once_with(TEXT)
        self.assertNotIn("text", out)
        self.assertEqual(out["message"], f"Copied {len(TEXT)} characters from the headset to this computer's clipboard")

    def test_to_computer_without_a_clipboard_program(self):
        with mock.patch.object(server, "headset_clipboard", return_value=TEXT), \
                mock.patch.object(frame_host, "set_clipboard_text", side_effect=frame_host.HostError("Can't set the clipboard")):
            with self.assertRaises(server.Failure) as cm:
                server.clipboard({"toComputer": True})
        self.assertEqual(cm.exception.status, 500)

    def test_to_computer_refused_when_the_server_runs_on_the_headset(self):
        with mock.patch.object(server, "LOCAL", True), mock.patch.object(server, "headset_clipboard") as read:
            with self.assertRaises(server.Failure) as cm:
                server.clipboard({"toComputer": True})
        self.assertEqual(cm.exception.status, 400)
        read.assert_not_called()

    def test_flags_must_be_true(self):
        # Anything else is a send, and an empty one is refused before SSH.
        with mock.patch.object(server, "ssh") as ssh:
            for body in ({"read": "yes"}, {"toComputer": 1}):
                with self.assertRaises(server.Failure):
                    server.clipboard(body)
        ssh.assert_not_called()


class SetClipboardText(unittest.TestCase):
    def put(self, platform, have, text=TEXT, fail=()):
        runs = []

        def run(cmd, **kw):
            runs.append((cmd, kw))
            if cmd[0] in fail:
                if fail[cmd[0]] == "timeout":
                    raise subprocess.TimeoutExpired(cmd, 10)
                return subprocess.CompletedProcess(cmd, 1)
            return subprocess.CompletedProcess(cmd, 0)
        flags = {"MAC": platform == "mac", "WINDOWS": platform == "windows", "LINUX": platform == "linux"}
        with mock.patch.multiple(frame_host, **flags), \
                mock.patch.object(frame_host.shutil, "which", lambda name: f"/bin/{name}" if name in have else None), \
                mock.patch.object(frame_host.subprocess, "run", run):
            frame_host.set_clipboard_text(text)
        for _, kw in runs:
            # Nothing captured or logged, and no pipes left for a clipboard daemon to hold open.
            self.assertEqual((kw["stdout"], kw["stderr"]), (subprocess.DEVNULL, subprocess.DEVNULL))
        return runs

    def test_mac_pbcopy_in_utf8(self):
        [(cmd, kw)] = self.put("mac", {"pbcopy"})
        self.assertEqual(cmd, ["pbcopy"])
        self.assertEqual(kw["input"], TEXT.encode("utf-8"))
        self.assertEqual(kw["env"]["LC_CTYPE"], "UTF-8")

    def test_windows_powershell_gets_base64_utf8(self):
        [(cmd, kw)] = self.put("windows", {"powershell.exe", "clip.exe"})
        self.assertEqual(cmd[0], "powershell.exe")
        self.assertIn("Set-Clipboard", cmd[-1])
        self.assertIn("FromBase64String", cmd[-1])
        self.assertEqual(base64.b64decode(kw["input"]).decode("utf-8"), TEXT)

    def test_windows_clip_fallback_gets_utf16_with_a_bom(self):
        runs = self.put("windows", {"powershell.exe", "clip.exe"}, fail={"powershell.exe": 1})
        self.assertEqual([c[0] for c, _ in runs], ["powershell.exe", "clip.exe"])
        data = runs[1][1]["input"]
        self.assertEqual(data[:2], b"\xff\xfe")
        self.assertEqual(data[2:].decode("utf-16-le"), TEXT)

    def test_linux_tries_wayland_then_x11(self):
        [(cmd, kw)] = self.put("linux", {"wl-copy", "xclip", "xsel"})
        self.assertEqual(cmd, ["wl-copy"])
        self.assertEqual(kw["input"], TEXT.encode())
        runs = self.put("linux", {"wl-copy", "xclip", "xsel"}, fail={"wl-copy": 1, "xclip": "timeout"})
        self.assertEqual([c for c, _ in runs], [["wl-copy"], ["xclip", "-selection", "clipboard", "-in"],
                                                ["xsel", "--clipboard", "--input"]])
        [(cmd, _)] = self.put("linux", {"xsel"})
        self.assertEqual(cmd[0], "xsel")

    def test_nothing_to_set_it_with(self):
        with self.assertRaises(frame_host.HostError) as cm:
            self.put("linux", set())
        self.assertIn("wl-clipboard", str(cm.exception))
        with self.assertRaises(frame_host.HostError):
            self.put("linux", {"wl-copy"}, fail={"wl-copy": 1})
        with self.assertRaises(frame_host.HostError):
            self.put("mac", set())


if __name__ == "__main__":
    unittest.main()
