"""The OBS relay must preserve transport packets and keep its output local."""
import importlib.util
import io
from pathlib import Path
import unittest


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


if __name__ == '__main__':
    unittest.main()
