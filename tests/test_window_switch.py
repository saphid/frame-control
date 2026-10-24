"""The viewer sends one explicit native window-switch chord per click."""
from pathlib import Path
import shutil
import subprocess
import unittest


class WindowSwitch(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the viewer script check')
    def test_host_chords_and_display_only_guard(self):
        script = Path(__file__).parent / 'page' / 'window_switch.mjs'
        result = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
