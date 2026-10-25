"""The OBS relay must preserve transport packets and keep its output local."""
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'obs-headset-source.py'
spec = importlib.util.spec_from_file_location('obs_headset_source', SCRIPT)
obs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(obs)


class Receiver:
    def __init__(self):
        self.chunks = []

    def send(self, data):
        self.chunks.append(data)


class ObsSourceTests(unittest.TestCase):
    def test_desktop_packages_the_helper_as_a_required_resource(self):
        root = SCRIPT.parents[1]
        build = json.loads((root / 'app' / 'package.json').read_text())['build']
        scripts = next(item for item in build['extraResources'] if item['to'] == 'scripts')
        self.assertIn(SCRIPT.name, scripts['filter'])
        self.assertIn('scripts/' + SCRIPT.name, (root / 'app' / 'build' / 'check-resources.js').read_text())

    def test_relay_keeps_whole_transport_packets(self):
        stream = bytes(range(188)) * 101
        receiver = Receiver()
        self.assertEqual(obs.relay(io.BytesIO(stream), receiver), len(stream))
        self.assertEqual(b''.join(receiver.chunks), stream)
        self.assertTrue(all(len(chunk) % 188 == 0 and len(chunk) <= 1316
                            for chunk in receiver.chunks))

    def test_incomplete_packet_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            obs.relay(io.BytesIO(b'x' * 189), Receiver())

    def test_remote_command_uses_recording_sources(self):
        with_audio = obs.remote_command()
        self.assertIn('/dev/video99', with_audio)
        self.assertIn('@DEFAULT_MONITOR@', with_audio)
        self.assertIn('-map 1:a:0', with_audio)
        self.assertIn('-f mpegts', with_audio)
        self.assertNotIn('@DEFAULT_MONITOR@', obs.remote_command(audio=False))

    def test_watchdog_ends_a_stalled_child_on_every_host_platform(self):
        class Child:
            def __init__(self):
                self.stopped = threading.Event()

            def poll(self):
                return 255 if self.stopped.is_set() else None

            def terminate(self):
                self.stopped.set()

        for ready in (False, True):
            with self.subTest(ready=ready):
                child = Child()
                watchdog = obs.StreamWatchdog(child, startup=0.1, stall=0.1)
                if ready:
                    watchdog.packet()
                try:
                    self.assertTrue(child.stopped.wait(1), 'a stalled SSH child was not terminated')
                    self.assertIn('stopped' if ready else 'no OBS video', watchdog.reason)
                finally:
                    watchdog.close()

    @unittest.skipIf(sys.platform == 'win32', 'the packaged Start/Stop control is Linux/macOS only')
    def test_relay_stops_its_ssh_child_on_app_signal_or_control_pipe(self):
        for mode in ('signal', 'control-pipe'):
            with self.subTest(mode=mode):
                self._check_stop_mode(mode)

    def _check_stop_mode(self, mode):
        with tempfile.TemporaryDirectory() as folder, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            directory = Path(folder)
            stopped = directory / 'stopped'
            fake = directory / 'ssh'
            fake.write_text("#!/usr/bin/env python3\n"
                            "import os, signal, sys, time\n"
                            "def stop(*_):\n"
                            "    open(os.environ['FAKE_SSH_STOPPED'], 'w').close()\n"
                            "    sys.exit(255)\n"
                            "signal.signal(signal.SIGTERM, stop)\n"
                            "sys.stdout.buffer.write(b'G' * 1316)\n"
                            "sys.stdout.buffer.flush()\n"
                            "while True: time.sleep(1)\n")
            fake.chmod(0o755)
            receiver.bind(('127.0.0.1', 0))
            receiver.settimeout(8)
            env = {**os.environ, 'PATH': str(directory) + os.pathsep + os.environ.get('PATH', ''),
                   'FAKE_SSH_STOPPED': str(stopped)}
            arguments = [sys.executable, str(SCRIPT), '--frame', 'fake-frame',
                         '--port', str(receiver.getsockname()[1])]
            if mode == 'control-pipe':
                arguments.append('--control-stdin')
            process = subprocess.Popen(arguments,
                                       stdin=subprocess.PIPE if mode == 'control-pipe' else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=env)
            try:
                packet, _ = receiver.recvfrom(1500)
                self.assertEqual(packet, b'G' * 1316)
                if mode == 'control-pipe':
                    process.stdin.close()
                    process.wait(timeout=8)
                    errors = process.stderr.read()
                else:
                    process.send_signal(signal.SIGTERM)
                    _, errors = process.communicate(timeout=8)
                self.assertEqual(process.returncode, 0, errors.decode())
                self.assertIn(b'Frame Control OBS stream is ready', errors)
                for _ in range(30):
                    if stopped.exists():
                        break
                    time.sleep(0.1)
                self.assertTrue(stopped.exists(), 'the SSH child survived relay shutdown')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                process.stdout.close()
                process.stderr.close()

    @unittest.skipIf(sys.platform == 'win32', 'the stand-in SSH script uses a POSIX shebang')
    def test_startup_and_stream_stalls_end_ssh_with_a_clear_error(self):
        for mode in ('startup', 'stream'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                fake = directory / 'ssh'
                fake.write_text("#!/usr/bin/env python3\n"
                                "import os, signal, sys, time\n"
                                "def stop(*_):\n"
                                "    open(os.environ['FAKE_SSH_STOPPED'], 'w').close()\n"
                                "    sys.exit(255)\n"
                                "signal.signal(signal.SIGTERM, stop)\n"
                                "if os.environ['FAKE_SSH_MODE'] == 'stream':\n"
                                "    sys.stdout.buffer.write(b'G' * 1316)\n"
                                "    sys.stdout.buffer.flush()\n"
                                "while True: time.sleep(1)\n")
                fake.chmod(0o755)
                stopped = directory / 'stopped'
                env = {'PATH': str(directory) + os.pathsep + os.environ.get('PATH', ''),
                       'FAKE_SSH_STOPPED': str(stopped), 'FAKE_SSH_MODE': mode}
                with mock.patch.dict(os.environ, env), \
                     mock.patch.object(obs, 'STARTUP_TIMEOUT', 0.3), \
                     mock.patch.object(obs, 'STREAM_STALL', 0.3):
                    with self.assertRaisesRegex(RuntimeError, 'no OBS video' if mode == 'startup' else 'video stopped'):
                        obs.main(['--frame', 'fake-frame'])
                self.assertTrue(stopped.exists(), 'SSH survived the relay timeout')


if __name__ == '__main__':
    unittest.main()
