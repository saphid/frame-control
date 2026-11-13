"""Sample packaging uses real installer admission and preserves prior artifacts."""
import sandbox  # noqa: F401
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKER = ROOT / 'scripts/framey-pack-sample.py'
CHECKER = ROOT / 'scripts/framey-check-archive.py'
SAMPLE = ROOT / 'examples/framey-settings'
FILES = ('plugin.json', 'main.py', 'dist/index.js')


class SamplePackaging(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'sample'
        shutil.copytree(SAMPLE, self.source, ignore=shutil.ignore_patterns('node_modules'))
        self.output = self.root / 'sample.zip'

    def pack(self, output=None, *options):
        run = subprocess.run([sys.executable, str(PACKER), str(output or self.output),
                              '--source', str(self.source), *options],
                             cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.stderr, '')
        self.assertEqual(list(self.root.glob('.framey-pack-*')), [])
        return run.returncode, json.loads(run.stdout)

    def test_reproducible_contents_and_real_checker_admission(self):
        # Local build files and metadata must never leak into the release ZIP.
        (self.source / '.private').write_text('not a release file')
        self.output.write_bytes(b'old release')
        code, report = self.pack()
        self.assertEqual(code, 0, report)
        original = self.output.read_bytes()
        self.assertEqual(report['sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(report['output'], str(self.output.resolve()))
        self.assertTrue(report['installerAccepted'])
        self.assertTrue(report['panelCandidate'])
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), ['framey-settings/' + name for name in FILES])
            for name, info in zip(FILES, archive.infolist()):
                self.assertEqual(archive.read(info), (self.source / name).read_bytes())
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.create_system, 3)
                self.assertEqual(info.external_attr >> 16, stat.S_IFREG | 0o644)
        for name in FILES:
            os.utime(self.source / name, (1_700_000_000, 1_700_000_000))
        code, report = self.pack(self.root / 'second.zip')
        self.assertEqual(code, 0, report)
        self.assertEqual((self.root / 'second.zip').read_bytes(), original)
        run = subprocess.run([sys.executable, str(CHECKER), str(self.output),
                              '--name', 'Framey Settings Sample'],
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout), {k: v for k, v in report.items() if k != 'output'})

    def test_invalid_sources_preserve_existing_output(self):
        manifest = json.loads((self.source / 'plugin.json').read_text())
        cases = [
            ('plugin.json', b'{broken', 'JSON'),
            ('plugin.json', json.dumps(dict(manifest, flags=['root'])).encode(), 'needs root'),
            ('plugin.json', json.dumps(dict(manifest, api_version=99)).encode(), 'cannot open'),
            ('plugin.json', json.dumps(dict(manifest, name='Wrong name')).encode(), 'name differs'),
            ('dist/index.js', b'', 'cannot open'),
            ('main.py', None, 'main.py'),
            ('dist/index.js', None, 'index.js'),
        ]
        for member, replacement, message in cases:
            with self.subTest(member=member, message=message):
                path = self.source / member
                original = path.read_bytes()
                try:
                    self.output.write_bytes(b'previous valid release')
                    if replacement is None:
                        path.unlink()
                    else:
                        path.write_bytes(replacement)
                    code, report = self.pack()
                    self.assertEqual(code, 1, report)
                    self.assertFalse(report['ok'])
                    self.assertIn(message.lower(), report['error'].lower())
                    self.assertEqual(self.output.read_bytes(), b'previous valid release')
                finally:
                    path.write_bytes(original)

    def test_failed_first_package_leaves_no_output(self):
        (self.source / 'dist/index.js').unlink()
        code, report = self.pack()
        self.assertEqual(code, 1, report)
        self.assertFalse(self.output.exists())

    def test_failed_replacement_cleans_staging(self):
        self.output.mkdir()
        marker = self.output / 'keep.txt'
        marker.write_text('keep')
        code, report = self.pack()
        self.assertEqual(code, 1, report)
        self.assertEqual(marker.read_text(), 'keep')

    def test_output_cannot_overwrite_source(self):
        for member in FILES:
            with self.subTest(member=member):
                path = self.source / member
                original = path.read_bytes()
                code, report = self.pack(path)
                self.assertEqual(code, 1, report)
                self.assertIn('source file', report['error'])
                self.assertEqual(path.read_bytes(), original)

    def test_fork_name_must_be_explicit(self):
        manifest = self.source / 'plugin.json'
        value = json.loads(manifest.read_text())
        value['name'] = 'Forked Sample'
        manifest.write_text(json.dumps(value))
        code, report = self.pack(None, '--name', 'Forked Sample')
        self.assertEqual(code, 0, report)
        self.assertTrue(report['panelCandidate'])

    def test_default_sample_works_outside_repository(self):
        run = subprocess.run([sys.executable, str(PACKER), str(self.output)],
                             cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue(json.loads(run.stdout)['panelCandidate'])


if __name__ == '__main__':
    unittest.main()
