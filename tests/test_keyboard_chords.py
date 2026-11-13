"""PC browser handlers -> input validation -> gamescope -> libei key calls.

HTTP/SSH transport and the final libei device are replaced; no socket is opened.
Expected evdev sequences in pad_keyboard.cjs are independent Linux constants.
"""
import sandbox  # noqa: F401
import json
from pathlib import Path
import shutil
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import server
import frame_touch


@unittest.skipUnless(shutil.which('node'), 'Node runs the production browser handlers')
class KeyboardChords(unittest.TestCase):
    def test_browser_key_chord_and_focus_loss_sequences_reach_libei(self):
        result = subprocess.run(['node', str(ROOT/'tests/page/pad_keyboard.cjs'), '--vectors'],
                                capture_output=True, text=True, check=True, timeout=20)
        vectors = json.loads(result.stdout)
        self.assertGreaterEqual(len(vectors), 60)
        for vector in vectors:
            with self.subTest(vector=vector['name']):
                received = []
                gs = frame_touch.Gamescope.__new__(frame_touch.Gamescope)
                gs.keys, gs.held, gs.device = set(), set(), object()
                gs.frame = lambda: None
                gs.L = types.SimpleNamespace(ei_device_keyboard_key=lambda device, code, down:
                                             received.append([code, down]))

                class Agent:
                    def send(self, events):
                        for event in events:
                            frame_touch.apply(gs, event, None)
                        return {'state': 'ready', 'sent': bool(events)}

                with patch.object(server, '_touch', Agent()), \
                     patch.object(server, 'typed_in_kde', return_value=False), \
                     patch.object(server, '_note_typed'), patch.object(server, 'pad_status', side_effect=lambda status, **kw: status), \
                     patch.object(frame_touch.time, 'sleep'):
                    reply = server.remote_input({'events': vector['events']})
                self.assertTrue(reply['sent'])
                self.assertEqual(received, vector['expected'])
                self.assertEqual(gs.keys, set(), 'no key or modifier may stay held')

    def test_browser_ui_behaviors(self):
        result = subprocess.run(['node', '--test', str(ROOT/'tests/page/pad_keyboard.cjs')],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


class PhysicalKeyValidation(unittest.TestCase):
    def test_accepted_unicode_remains_pending_until_its_typing_estimate_settles(self):
        with patch.object(server, '_kde_queue', []), patch.object(server, '_kde_error', None), \
             patch.object(server, '_kde_until', 100), patch.object(server.time, 'time', return_value=99):
            self.assertEqual(server.pad_status({'state':'ready'}), {'state':'ready','queued':1})
            with patch.object(server.time, 'time', return_value=101):
                self.assertEqual(server.pad_status({'state':'ready'}), {'state':'ready'})

    def test_invalid_or_ambiguous_physical_input_is_refused(self):
        for event in ({'keyCode': True, 'down': True}, {'keyCode': 0, 'down': True},
                      {'keyCode': 768, 'down': True}, {'keyCode': 29}, {'keyCode': 29, 'down': 1},
                      {'keyCode': 29, 'down': True, 'ctrl': True},
                      {'keyCode': 29, 'down': True, 'key': 'c'},
                      {'keyCode': 29, 'down': True, 'specialKey': 2}):
            with self.subTest(event=event), self.assertRaises(server.Failure):
                server.input_event(event)

    def test_physical_releases_never_go_to_kde_text_transport(self):
        events = [server.input_event({'keyCode': 29, 'down': down}) for down in (True, False)]
        touch, kde = server.pad_events(events, kde=True)
        self.assertEqual(touch, [{'key': 29, 'down': True}, {'key': 29, 'down': False}])
        self.assertEqual(kde, [])
