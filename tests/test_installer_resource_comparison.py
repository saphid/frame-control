"""Installer payload comparison catches same-size byte corruption."""

import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'app/build/check-resources.js'


@unittest.skipUnless(shutil.which('node'), 'Node is needed for resource comparison')
class InstallerResourceComparison(unittest.TestCase):
    def test_same_size_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference'
            installed = Path(directory) / 'installed'
            (reference / 'nested').mkdir(parents=True)
            (installed / 'nested').mkdir(parents=True)
            (reference / 'nested/data.bin').write_bytes(b'expected')
            (installed / 'nested/data.bin').write_bytes(b'expected')
            script = ('const guard=require(process.argv[1]); '
                      'process.stdout.write(JSON.stringify(guard.differences(process.argv[2],process.argv[3])))')

            def compare():
                result = subprocess.run(['node', '-e', script, str(CHECKER),
                                         str(installed), str(reference)],
                                        capture_output=True, text=True, check=True)
                return json.loads(result.stdout)

            self.assertEqual(compare(), [])
            (installed / 'nested/data.bin').write_bytes(b'altered!')
            self.assertEqual(compare(), ['nested/data.bin'])
            (installed / 'nested/data.bin').unlink()
            self.assertEqual(compare(), ['nested/data.bin'])


if __name__ == '__main__':
    unittest.main()
