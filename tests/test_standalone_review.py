"""Standalone page regressions with production JavaScript and no live services."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node exercises the standalone page scripts')
class StandaloneReview(unittest.TestCase):
    def test_behavior(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', '--test', str(root / 'tests/standalone_review.cjs')],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
