"""The author ZIP checker uses the actual installer validator without installing."""
import sandbox  # noqa: F401
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'scripts/framey-check-archive.py'
SAMPLE = ROOT / 'examples/framey-settings'


class ArchiveChecker(unittest.TestCase):
    def run_check(self, manifest=None, extra=None, frontend=True, name='Framey Settings Sample'):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'plugin.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('framey-settings/plugin.json',
                                json.dumps(manifest or json.loads((SAMPLE / 'plugin.json').read_text())))
                if frontend:
                    output.write(SAMPLE / 'dist/index.js', 'framey-settings/dist/index.js')
                if extra:
                    output.writestr(extra[0], extra[1])
            run = subprocess.run([sys.executable, str(CHECKER), str(archive), '--name', name],
                                 capture_output=True, text=True, timeout=15)
            return run.returncode, json.loads(run.stdout)

    def test_sample_has_an_accepted_panel_candidate(self):
        code, result = self.run_check()
        self.assertEqual(code, 0, result)
        self.assertTrue(result['installerAccepted'])
        self.assertTrue(result['panelCandidate'])
        self.assertEqual(result['folder'], 'framey-settings')
        self.assertEqual(len(result['sha256']), 64)
        self.assertIn('runtime tests', result['note'])

    def test_backend_only_archive_is_not_a_panel_candidate(self):
        code, result = self.run_check(frontend=False, extra=('framey-settings/README.txt', 'x' * 2048))
        self.assertEqual(code, 0, result)
        self.assertTrue(result['installerAccepted'])
        self.assertFalse(result['panelCandidate'])

    def test_large_manifest_passes_installer_but_not_panel_admission(self):
        manifest = json.loads((SAMPLE / 'plugin.json').read_text())
        manifest['description'] = 'x' * 17_000
        code, result = self.run_check(manifest=manifest)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['installerAccepted'])
        self.assertFalse(result['panelCandidate'])

    def test_root_x86_and_wrong_store_name_are_rejected(self):
        cases = [
            ({'name': 'Framey Settings Sample', 'api_version': 2, 'flags': ['root']}, None,
             'Framey Settings Sample', 'needs root'),
            (None, ('framey-settings/bin/helper', b'\x7fELF' + b'\0' * 14 + b'\x3e\0' + b'\0' * 32),
             'Framey Settings Sample', 'non-ARM64'),
            (None, None, 'Different Store Name', 'name differs'),
        ]
        for manifest, extra, name, message in cases:
            with self.subTest(message=message):
                code, result = self.run_check(manifest=manifest, extra=extra, name=name)
                self.assertEqual(code, 1)
                self.assertFalse(result['ok'])
                self.assertIn(message, result['error'])


if __name__ == '__main__':
    unittest.main()
