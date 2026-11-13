"""Type on the headset: entry points, the T key and the clipboard copy, without a browser or headset."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node exercises the page code')
class TypingUi(unittest.TestCase):
    def test_behavior(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', '--test', str(root / 'tests/typing_ui.cjs')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
