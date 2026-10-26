"""Official Decky store transport and owned plugin transaction."""
import sandbox  # noqa: F401
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ui'))
import frame_decky_store
import frame_decky


def archive(flags=(), extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as bundle:
        bundle.writestr('Example/plugin.json', json.dumps({'name': 'Example', 'flags': list(flags)}))
        bundle.writestr('Example/dist/index.js', 'export default {};' + ' ' * 1200)
        if extra:
            bundle.writestr(*extra)
    data = stream.getvalue()
    return data, hashlib.sha256(data).hexdigest()


class ArchiveTests(unittest.TestCase):
    def test_catalog_selects_valid_visible_latest_versions(self):
        records = [{'id': 42, 'name': 'Example', 'author': 'Panel Author', 'visible': True, 'versions':
                    [{'name': '1.0', 'hash': 'a' * 64}], 'tags': []},
                   {'id': 43, 'name': 'Hidden', 'visible': False, 'versions':
                    [{'name': '1.0', 'hash': 'b' * 64}]},
                   {'id': 44, 'name': 'Unsafe', 'visible': True, 'versions':
                    [{'name': '1.0; touch /tmp/bad', 'hash': 'c' * 64}]}]
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertEqual([(p['id'], p['author']) for p in frame_decky_store.catalog()], [(42, 'Panel Author')])

    def test_catalog_marks_underscore_root_and_omits_ambiguous_store_ids(self):
        records = [{'id': 42, 'name': 'Needs root', 'tags': ['_root'],
                    'versions': [{'name': '1.0', 'hash': 'a' * 64}]},
                   {'id': 43, 'name': 'First', 'versions': [{'name': '1.0', 'hash': 'b' * 64}]},
                   {'id': 43, 'name': 'Second', 'versions': [{'name': '2.0', 'hash': 'c' * 64}]}]
        with patch.object(frame_decky_store.urllib.request, 'urlopen',
                          return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertEqual([(p['id'], p['root']) for p in frame_decky_store.catalog()], [(42, True)])

    def test_accepts_hashed_non_root_archive(self):
        data, digest = archive()
        self.assertEqual(frame_decky_store.archive_info(data, digest, 'Example'), 'Example')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            frame_decky_store.archive_info(data, '0' * 64, 'Example')

    def test_rejects_root_x86_and_escape(self):
        for data in (archive(flags=['root'])[0],
                     archive(extra=('Example/bin/helper', b'\x7fELF' + b'\x00' * 14 + (62).to_bytes(2, 'little')))[0],
                     archive(extra=('../outside', b'oops'))[0]):
            with self.subTest(data=hashlib.sha256(data).hexdigest()[:8]):
                with self.assertRaises(ValueError):
                    frame_decky_store.archive_info(data, hashlib.sha256(data).hexdigest(), 'Example')

    def test_rejects_zip_path_collisions_and_non_object_manifest(self):
        for name in ('Example/dist/index.js', 'Example/./dist/index.js',
                     'Example//dist/index.js'):
            with self.subTest(name=name), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                data, digest = archive(extra=(name, 'replacement'))
                with self.assertRaisesRegex(ValueError, 'Unsafe|duplicate'):
                    frame_decky_store.archive_info(data, digest, 'Example')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as bundle:
            bundle.writestr('Example/plugin.json', '[]')
            bundle.writestr('Example/dist/index.js', ' ' * 1200)
        data = stream.getvalue()
        with self.assertRaisesRegex(ValueError, 'manifest'):
            frame_decky_store.archive_info(data, hashlib.sha256(data).hexdigest(), 'Example')


@unittest.skipIf(os.name == 'nt', 'remote plugin transaction runs on Linux')
class StoreTransaction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name)
        unit = home / '.config/systemd/user/frame-control-decky.service'
        unit.parent.mkdir(parents=True)
        unit.write_text('[Service]\n')
        fake = home / 'systemctl'
        fake.write_text('#!/bin/sh\nif [ "$2" = is-active ]; then exit 0; fi\nexit 0\n')
        fake.chmod(0o700)
        self.env = {**os.environ, 'HOME': self.tmp.name,
                    'PATH': self.tmp.name + os.pathsep + os.environ['PATH']}
        self.folder = home / '.local/share/frame-control/decky/plugins/Example'
        self.folder.parent.mkdir(parents=True)

    def apply(self, action, data=None):
        token = secrets.token_hex(12)
        source = Path('/tmp/frame-control-decky-plugin-' + token)
        if data is not None:
            source.write_bytes(data)
        digest = hashlib.sha256(data or b'').hexdigest()
        try:
            return subprocess.run([sys.executable, '-', action, token, '42', digest, 'Example', '1.0'],
                                  input=frame_decky_store.APPLY, text=True, capture_output=True,
                                  env=self.env, timeout=15)
        finally:
            source.unlink(missing_ok=True)

    def test_install_update_remove_only_owned_folder(self):
        first, _ = archive()
        result = self.apply('install', first)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.folder / '.frame-control-store.json').read_text())['storeId'], 42)
        second, _ = archive(extra=('Example/data.txt', 'new'))
        result = self.apply('update', second)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.folder / 'data.txt').read_text(), 'new')
        result = self.apply('remove')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.folder.exists())
        self.folder.mkdir()
        (self.folder / 'plugin.json').write_text('{}')
        result = self.apply('remove')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.folder.exists())
        external = Path(self.tmp.name) / 'other-plugin'
        external.mkdir()
        (external / '.frame-control-store.json').write_text('{"storeId":42}')
        for item in self.folder.iterdir(): item.unlink()
        self.folder.rmdir()
        self.folder.symlink_to(external, target_is_directory=True)
        result = self.apply('remove')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(external.exists())

    def test_remove_while_service_is_stopped_does_not_restart_it(self):
        data, _ = archive()
        self.assertEqual(self.apply('install', data).returncode, 0)
        fake = Path(self.tmp.name) / 'systemctl'
        fake.write_text('#!/bin/sh\nif [ "$2" = is-active ]; then exit 1; fi\n'
                        'echo "$*" >> "$HOME/service-calls"\nexit 0\n')
        result = self.apply('remove')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.folder.exists())
        self.assertEqual((Path(self.tmp.name) / 'service-calls').read_text().splitlines(),
                         ['--user stop frame-control-decky.service'])

    def test_shared_lock_rejects_plugin_and_loader_changes(self):
        import fcntl

        lock_path = Path(self.tmp.name) / '.local/share/frame-control/decky-transaction.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        data, _ = archive()
        with lock_path.open('w+b') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            plugin = self.apply('install', data)
            loader = subprocess.run([sys.executable, '-', 'remove', 'none', 'none', 'none'],
                                    input=frame_decky.APPLY, text=True, capture_output=True,
                                    env=self.env, timeout=15)
            self.assertNotEqual(plugin.returncode, 0)
            self.assertNotEqual(loader.returncode, 0)
            self.assertIn('Another Decky change is in progress', plugin.stderr)
            self.assertIn('Another Decky change is in progress', loader.stderr)
            self.assertFalse(self.folder.exists())

        installed = self.apply('install', data)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertEqual(self.apply('remove').returncode, 0)

    def test_remote_apply_rejects_colliding_zip_paths(self):
        for name in ('Example/dist/index.js', 'Example/./dist/index.js'):
            with self.subTest(name=name), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                data, _ = archive(extra=(name, 'replacement'))
                result = self.apply('install', data)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.folder.exists())

    def test_remote_apply_rechecks_plugin_name_under_transaction_lock(self):
        data, _ = archive()
        other = self.folder.parent / 'Other'
        other.mkdir()
        (other / 'plugin.json').write_text('{"name":"Example"}')
        result = self.apply('install', data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('different plugin with this name', result.stderr)
        self.assertFalse(self.folder.exists())
        self.assertEqual((other / 'plugin.json').read_text(), '{"name":"Example"}')
        self.assertEqual(list(self.folder.parent.glob('.frame-control-stage-*')), [])

        (other / 'plugin.json').write_text('{"name":"Distinct"}')
        self.assertEqual(self.apply('install', data).returncode, 0)
        (other / 'plugin.json').write_text('{"name":"Example"}')
        result = self.apply('update', data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('different plugin with this name', result.stderr)
        self.assertTrue(self.folder.exists())
        self.assertEqual(list(self.folder.parent.glob('.frame-control-stage-*')), [])


class StoreHost(unittest.TestCase):
    def test_reviewed_archive_changed_before_install_does_not_download(self):
        state = {'managed': True, 'running': True, 'plugins': []}
        catalog = [{'id': 42, 'name': 'Example', 'root': False,
                    'sha256': 'b' * 64, 'version': '2.0'}]
        with patch.object(frame_decky_store.frame_decky, 'status', return_value=state), \
             patch.object(frame_decky_store, 'catalog', return_value=catalog), \
             patch.object(frame_decky_store.urllib.request, 'urlopen',
                          side_effect=AssertionError('No download expected')):
            with self.assertRaisesRegex(ValueError, 'version changed'):
                frame_decky_store.change(lambda *args, **kwargs: self.fail('No headset write expected'),
                                         'install', 42, reviewed_hash='a' * 64)

    def test_stopped_managed_service_allows_removing_owned_plugin(self):
        state = {'managed': True, 'running': False, 'plugins':
                 [{'storeId': 42, 'folder': 'Example', 'name': 'Example', 'version': '1.0'}]}
        calls = []
        with patch.object(frame_decky_store.frame_decky, 'status', return_value=state), \
             patch.object(frame_decky_store, 'catalog') as network:
            result = frame_decky_store.change(lambda command, **kwargs: calls.append(command) or '{}',
                                               'remove', 42)
        self.assertEqual(result, {})
        self.assertEqual(len(calls), 1)
        network.assert_not_called()

    def test_renamed_store_plugin_cannot_be_installed_twice(self):
        state = {'managed': True, 'running': True, 'plugins':
                 [{'storeId': 42, 'folder': 'OldFolder', 'name': 'Old Name', 'version': '1.0'}]}
        catalog = [{'id': 42, 'name': 'New Name', 'root': False, 'sha256': 'a' * 64, 'version': '2.0'}]
        with patch.object(frame_decky_store.frame_decky, 'status', return_value=state), \
             patch.object(frame_decky_store, 'catalog', return_value=catalog) as network, \
             patch.object(frame_decky_store.urllib.request, 'urlopen', side_effect=AssertionError('No download expected')):
            with self.assertRaisesRegex(ValueError, 'already installed'):
                frame_decky_store.change(lambda *args, **kwargs: self.fail('No headset write expected'),
                                         'install', 42)
            network.assert_not_called()

    def test_update_rejects_name_taken_by_another_plugin_before_download(self):
        state = {'managed': True, 'running': True, 'plugins': [
            {'storeId': 42, 'folder': 'Example', 'name': 'Old Name', 'version': '1.0'},
            {'storeId': 43, 'folder': 'Other', 'name': 'Example', 'version': '1.0'}]}
        catalog = [{'id': 42, 'name': 'Example', 'root': False,
                    'sha256': 'a' * 64, 'version': '2.0'}]
        with patch.object(frame_decky_store.frame_decky, 'status', return_value=state), \
             patch.object(frame_decky_store, 'catalog', return_value=catalog), \
             patch.object(frame_decky_store.urllib.request, 'urlopen',
                          side_effect=AssertionError('No download expected')):
            with self.assertRaisesRegex(ValueError, 'different plugin with this name'):
                frame_decky_store.change(lambda *args, **kwargs: self.fail('No headset write expected'),
                                         'update', 42)

    def test_update_allows_its_own_existing_name(self):
        data, digest = archive()
        state = {'managed': True, 'running': True, 'plugins': [
            {'storeId': 42, 'folder': 'Example', 'name': 'Example', 'version': '1.0'}]}
        catalog = [{'id': 42, 'name': 'Example', 'root': False,
                    'sha256': digest, 'version': '2.0'}]
        calls = []
        with patch.object(frame_decky_store.frame_decky, 'status', return_value=state), \
             patch.object(frame_decky_store, 'catalog', return_value=catalog), \
             patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(data)):
            result = frame_decky_store.change(lambda command, **kwargs: calls.append(command) or '{}',
                                               'update', 42)
        self.assertEqual(result, {})
        self.assertEqual(len(calls), 3)  # Upload, apply, and temporary archive cleanup.
        self.assertIn('update', calls[1])

    def test_owned_plugin_can_be_removed_without_store_network(self):
        state = {'managed': True, 'running': True, 'plugins':
                 [{'storeId': 42, 'folder': 'Example', 'name': 'Example', 'version': '1.0'}]}
        def ssh(command, **kwargs):
            return '{}'
        progress = []
        with patch.object(frame_decky_store.frame_decky, 'status', return_value=state), \
             patch.object(frame_decky_store, 'catalog') as network:
            frame_decky_store.change(ssh, 'remove', 42, lambda stage, percent: progress.append((stage, percent)))
            network.assert_not_called()
        self.assertEqual(progress, [('Checking installed plugins', 5), ('Removing plugin on Frame', 80)])


if __name__ == '__main__':
    unittest.main()
