"""Local headset actions keep writes scoped to the opt-in VR server."""
import sandbox  # noqa: F401
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_clips
import server


class HeadsetActions(unittest.TestCase):
    def test_quick_actions_are_unavailable_outside_headset_runtime(self):
        with patch.object(server, 'HEADSET_RUNTIME', False):
            with self.assertRaisesRegex(server.Failure, 'local VR panel'):
                server.headset_quick({'action':'game-mode'})

    def test_game_mode_targets_steamvr_main_dashboard(self):
        with patch.object(server, 'HEADSET_RUNTIME', True), patch.object(server.frame_panels, 'focus') as focus:
            response = server.headset_quick({'action':'game-mode'})
        focus.assert_called_once_with('valve.steam.gamepadui.main')
        self.assertIn('Game Mode', response['message'])

    def test_screenshot_is_saved_only_in_user_pictures(self):
        with tempfile.TemporaryDirectory() as home, patch.object(server.Path, 'home', return_value=Path(home)), \
                patch.object(server, 'HEADSET_RUNTIME', True), patch.object(server, 'headset_view', return_value=b'PNG data'):
            result = server.headset_quick({'action':'screenshot'})
            file = Path(result['file'])
            self.assertEqual(file.parent, Path(home) / 'Pictures/FrameControl')
            self.assertEqual(file.read_bytes(), b'PNG data')
            if os.name != 'nt':  # Windows reports emulated mode bits for user files.
                self.assertEqual(file.stat().st_mode & 0o777, 0o600)

    def test_local_recording_uses_separate_work_folder(self):
        recorder = frame_clips.Recorder(Mock(), Mock(), Mock(), Mock(),
                                        work='.cache/frame-control/headset-video',
                                        destination_label='~/Videos/FrameControl')
        self.assertIn('headset-video', frame_clips.probe_command(recorder.work))
        self.assertIn('headset-video', frame_clips.record_command('rec-20261025-030000', False, work=recorder.work))
        self.assertNotIn('headset-video', frame_clips.probe_command())


if __name__ == '__main__':
    unittest.main()
