"""Production navigation and app actions, without a browser or headset."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node exercises shared page behavior')
class Workspace(unittest.TestCase):
    def test_behavior(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', '--test', str(root / 'tests/ui_workspace.cjs')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
