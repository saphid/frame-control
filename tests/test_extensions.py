"""Extension compatibility and filesystem boundaries, without running plugin code."""
import sandbox  # noqa: F401
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_extensions


class ExtensionFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'extensions'
        self.root.mkdir()
        self.patch = patch.object(frame_extensions, 'root', return_value=self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def extension(self, name='test-panel', **fields):
        folder = self.root / name
        folder.mkdir(exist_ok=True)
        manifest = {'id': name, 'name': 'Test panel', 'version': '1.0.0',
                    'description': 'A read-only panel', 'entry': 'index.html', **fields}
        (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        (folder / 'index.html').write_text('<script src="main.js"></script>', encoding='utf-8')
        (folder / 'main.js').write_text('/* extension code */', encoding='utf-8')
        return folder

    def test_existing_and_explicit_v1_manifests_are_compatible(self):
        self.extension('legacy')
        self.extension('explicit', apiVersion=1)
        result = frame_extensions.list_extensions()
        self.assertEqual(result['errors'], [])
        self.assertEqual([(x['id'], x['apiVersion']) for x in result['extensions']],
                         [('explicit', 1), ('legacy', 1)])
        self.assertEqual(frame_extensions.asset('explicit', 'main.js'),
                         (b'/* extension code */', 'text/javascript; charset=utf-8'))

    def test_unsupported_or_malformed_api_cannot_be_loaded_directly(self):
        for version in (2, 0, -1, '1', None, True, 1.0, [], {}):
            with self.subTest(apiVersion=version):
                self.extension(apiVersion=version)
                result = frame_extensions.list_extensions()
                self.assertEqual(result['extensions'], [])
                self.assertIn('unsupported apiVersion', result['errors'][0]['error'])
                with self.assertRaisesRegex(ValueError, 'unsupported apiVersion'):
                    frame_extensions.asset('test-panel', 'index.html')

    def test_one_incompatible_extension_does_not_hide_compatible_panels(self):
        self.extension('future', apiVersion=2)
        self.extension('working', apiVersion=1)
        result = frame_extensions.list_extensions()
        self.assertEqual([x['id'] for x in result['extensions']], ['working'])
        self.assertEqual(result['errors'][0]['folder'], 'future')

    def test_sample_is_discoverable_and_its_assets_are_served(self):
        source = Path(__file__).resolve().parents[1] / 'examples/extensions/headset-glance'
        shutil.copytree(source, self.root / source.name)
        result = frame_extensions.list_extensions()
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['extensions'][0]['id'], source.name)
        for asset in ('index.html', 'main.js', 'style.css'):
            self.assertEqual(frame_extensions.asset(source.name, asset)[0],
                             (source / asset).read_bytes())

    def test_private_nested_and_traversal_paths_are_rejected(self):
        self.extension()
        for name in ('manifest.json', '../outside.js', 'sub/main.js', '.hidden.js'):
            with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                frame_extensions.asset('test-panel', name)
        with self.assertRaises(FileNotFoundError):
            frame_extensions.asset('../test-panel', 'main.js')

    def test_oversized_assets_are_not_read(self):
        folder = self.extension()
        with (folder / 'large.js').open('wb') as output:
            output.truncate(5 * 1024 * 1024 + 1)
        with self.assertRaises(FileNotFoundError):
            frame_extensions.asset('test-panel', 'large.js')

    def test_symlinks_cannot_expose_files_outside_a_panel(self):
        folder = self.extension()
        outside = Path(self.tmp.name) / 'outside.js'
        outside.write_text('private file', encoding='utf-8')
        try:
            (folder / 'escape.js').symlink_to(outside)
            (self.root / 'alias').symlink_to(folder, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable for this user')
        with self.assertRaises(FileNotFoundError):
            frame_extensions.asset('test-panel', 'escape.js')
        with self.assertRaises(ValueError):
            frame_extensions.asset('alias', 'main.js')
        (folder / 'manifest.json').unlink()
        (folder / 'manifest.json').symlink_to(outside)
        with self.assertRaises(ValueError):
            frame_extensions.asset('test-panel', 'main.js')


if __name__ == '__main__':
    unittest.main()
