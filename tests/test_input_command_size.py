"""Real helper transport stays within Windows' command limit, without input devices."""
import sandbox  # noqa: F401
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import server


class InputCommandSize(unittest.TestCase):
    def test_shipped_helpers_leave_windows_command_headroom(self):
        for agent in (server.InputAgent(), server.TouchAgent()):
            with self.subTest(helper=agent.source.name):
                command = agent.command()
                wire = subprocess.list2cmdline([
                    r'C:\Program Files\Frame Control\resources\ssh.exe',
                    '-o', 'BatchMode=yes', 'frame.example.test', command,
                ])
                # Keep half the CreateProcessW limit available for the app's
                # real install path, SSH options and pairing arguments.
                self.assertLess(len(wire.encode('utf-16-le')) // 2, 16384)

    def test_real_payload_and_arguments_round_trip_without_consuming_events(self):
        # Execute the production bootstrap, replacing only the final helper
        # compilation with an inert recorder. No helper contacts devices.
        recorder = '''import builtins, hashlib, json, sys
def compile(source, filename, mode):
    print(json.dumps(dict(sha256=hashlib.sha256(source).hexdigest(),
                         filename=filename, argv=sys.argv[1:],
                         event=json.loads(sys.stdin.buffer.readline()))))
    return builtins.compile('pass', filename, mode)
'''
        event = {'key': 'æøé', 'singleclick': True}
        with patch.dict(server.os.environ, {'FRAME_CLIENT': 'client-quoted'}), \
                patch.object(server, 'INPUT_NAME', "Alex's Danish computer"):
            for agent in (server.InputAgent(), server.TouchAgent()):
                with self.subTest(helper=agent.source.name):
                    parts = shlex.split(agent.command('~/copied packages'))
                    self.assertEqual(parts[:3], ['python3', '-u', '-c'])
                    result = subprocess.run(
                        [sys.executable, '-u', '-c', recorder + parts[3], *parts[4:]],
                        input=json.dumps(event).encode() + b'\n',
                        capture_output=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                    got = json.loads(result.stdout)
                    self.assertEqual(got['sha256'], hashlib.sha256(agent.source.read_bytes()).hexdigest())
                    self.assertEqual(got['filename'], agent.source.stem)
                    self.assertEqual(got['event'], event)
                    if isinstance(agent, server.TouchAgent):
                        self.assertEqual(got['argv'], [])
                    else:
                        self.assertEqual(got['argv'][:3], [
                            'client-quoted', "Alex's Danish computer", '~/copied packages',
                        ])
                        self.assertEqual(json.loads(got['argv'][3]), [list(p) for p in agent.packages])


if __name__ == '__main__':
    unittest.main()
