"""Official Decky store transport and owned plugin transaction."""
import sandbox  # noqa: F401
import ast
import hashlib
import asyncio
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.request
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


def duplicate_archive(second=b'#!/bin/sh\nexit 0\n', second_mode=0o100755):
    stream = io.BytesIO()
    with warnings.catch_warnings(), zipfile.ZipFile(stream, 'w') as bundle:
        warnings.simplefilter('ignore', UserWarning)
        bundle.writestr('Example/plugin.json', json.dumps({'name': 'Example', 'flags': []}))
        bundle.writestr('Example/dist/index.js', 'export default {};' + ' ' * 1200)
        for mode, payload in ((0o100644, b'#!/bin/sh\nexit 0\n'), (second_mode, second)):
            info = zipfile.ZipInfo('Example/bin/helper')
            info.create_system = 3
            info.external_attr = mode << 16
            bundle.writestr(info, payload)
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

    def test_only_exact_fileserver_adaptation_clears_store_root(self):
        records = [{'id': 60, 'name': 'DeckyFileServer', 'tags': ['root'],
                    'versions': [{'name': '1.2.0', 'hash': frame_decky_store.FILESERVER_DIGEST}]}]
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertFalse(frame_decky_store.catalog()[0]['root'])
        records[0]['versions'][0]['hash'] = 'a'*64
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertTrue(frame_decky_store.catalog()[0]['root'])

    def test_only_exact_network_sentinel_adaptation_clears_store_root(self):
        records = [{'id': 114, 'name': 'Network Sentinel', 'tags': ['_root'],
                    'versions': [{'name': '1.0.4', 'hash': frame_decky_store.NETWORK_SENTINEL_DIGEST}]}]
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertFalse(frame_decky_store.catalog()[0]['root'])
        records[0]['versions'][0]['hash'] = 'a'*64
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertTrue(frame_decky_store.catalog()[0]['root'])

    def test_only_exact_battery_tracker_adaptation_clears_store_root(self):
        records = [{'id': 67, 'name': 'Battery Tracker', 'tags': ['_root'],
                    'versions': [{'name': '0.2.0', 'hash': frame_decky_store.BATTERY_TRACKER_DIGEST}]}]
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertFalse(frame_decky_store.catalog()[0]['root'])
        records[0]['versions'][0]['hash'] = 'a'*64
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertTrue(frame_decky_store.catalog()[0]['root'])

    def test_only_exact_prefix_manager_adaptation_clears_store_root(self):
        records = [{'id': 130, 'name': 'Games Prefix Manager', 'tags': ['root'],
                    'versions': [{'name': '1.0.1', 'hash': frame_decky_store.PREFIX_MANAGER_DIGEST}]}]
        for version, digest in (('1.0.1', frame_decky_store.PREFIX_MANAGER_DIGEST),
                                ('1.0.2', frame_decky_store.PREFIX_MANAGER_102_DIGEST)):
            records[0]['versions'][0].update(name=version, hash=digest)
            with self.subTest(version=version), patch.object(frame_decky_store.urllib.request, 'urlopen',
                    return_value=io.BytesIO(json.dumps(records).encode())):
                self.assertFalse(frame_decky_store.catalog()[0]['root'])
        records[0]['versions'][0]['hash'] = 'a'*64
        with patch.object(frame_decky_store.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(records).encode())):
            self.assertTrue(frame_decky_store.catalog()[0]['root'])

    def test_accepts_hashed_non_root_archive(self):
        data, digest = archive()
        self.assertEqual(frame_decky_store.archive_info(data, digest, 'Example'), 'Example')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            frame_decky_store.archive_info(data, '0' * 64, 'Example')

    def test_archive_size_limit_has_a_distinct_error(self):
        data, digest = archive()
        with patch.object(frame_decky_store, 'MAX_ZIP', len(data) - 1):
            with self.assertRaisesRegex(ValueError, 'download limit'):
                frame_decky_store.archive_info(data, digest, 'Example')

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

    def test_only_identical_duplicate_payloads_with_execute_bit_difference_are_accepted(self):
        data, digest = duplicate_archive()
        self.assertEqual(frame_decky_store.archive_info(data, digest, 'Example'), 'Example')
        for data, digest in (duplicate_archive(second=b'#!/bin/sh\nexit 1\n'),
                             duplicate_archive(second_mode=0o100666)):
            with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'Unsafe'):
                frame_decky_store.archive_info(data, digest, 'Example')

    def test_exact_steamback_archive_duplicate_members_are_unchanged(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(plugin for plugin in PLUGINS if plugin['id'] == 46)
        data = official_archive(record)
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']),
                         record['folder'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            duplicates = {}
            for entry in bundle.infolist():
                duplicates.setdefault(entry.filename, []).append(entry)
            duplicates = [entries for entries in duplicates.values() if len(entries) > 1]
            self.assertTrue(duplicates)
            for entries in duplicates:
                self.assertEqual([bundle.read(entry) for entry in entries][1:],
                                 [bundle.read(entries[0])] * (len(entries) - 1))


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

    def apply(self, action, data=None, expected='-', plugin_id=42, folder='Example', version='1.0'):
        token = secrets.token_hex(12)
        source = Path('/tmp/frame-control-decky-plugin-' + token)
        if data is not None:
            source.write_bytes(data)
        digest = hashlib.sha256(data or b'').hexdigest()
        try:
            return subprocess.run([sys.executable, '-', action, token, str(plugin_id), digest, folder, version, expected],
                                  input=frame_decky_store.apply_script(plugin_id, digest), text=True, capture_output=True,
                                  env=self.env, timeout=15)
        finally:
            source.unlink(missing_ok=True)

    def test_ludusavi_dependency_discovery_is_exact_archive_scoped(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 103)
        data = official_archive(record)
        result = self.apply('install', data, plugin_id=103, folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/record['folder']
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text())['compatShims'],
                         ['ludusavi-dependency-discovery'])
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            for item in original.infolist():
                if item.is_dir():
                    continue
                relative = item.filename.split('/', 1)[1]
                if relative != 'py_modules/ludusavi.py':
                    self.assertEqual((folder/relative).read_bytes(), original.read(item), relative)
        module = types.ModuleType('private_ludusavi_dependency')
        logger = logging.getLogger('private-ludusavi-dependency')
        with patch.dict(sys.modules, decky=types.SimpleNamespace(logger=logger)):
            # Published plugin annotations require Python 3.10 at evaluation
            # time. This host-side probe also runs on 3.9; Decky's native
            # runtime separately executes the unchanged annotation syntax.
            source = 'from __future__ import annotations\n' + (folder/'py_modules/ludusavi.py').read_text()
            exec(compile(source, 'managed-ludusavi.py', 'exec'), module.__dict__)
        with patch.object(module.subprocess, 'check_output', side_effect=FileNotFoundError):
            missing = module.Ludusavi(['not-present'])
        self.assertIsNone(missing.bin_path)
        self.assertEqual(missing.version, '')
        with patch.object(module.subprocess, 'check_output', side_effect=[
                subprocess.TimeoutExpired(['slow'], 5), 'private version\n']) as launch:
            found = module.Ludusavi(['slow', 'fixture'])
        self.assertEqual(found.bin_path, ('fixture',))
        self.assertEqual(found.version, 'private version\n')
        self.assertTrue(all(call.kwargs['timeout'] == 5 for call in launch.call_args_list))
        with patch.object(module.subprocess, 'check_output', side_effect=FileNotFoundError):
            found.__init__(['no-longer-present'])
        self.assertIsNone(found.bin_path)
        self.assertEqual(found.version, '')
        self.assertEqual(self.apply('remove', plugin_id=103, folder=record['folder']).returncode, 0)
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr(record['folder']+'/changed.txt', 'different archive')
        result = self.apply('install', changed.getvalue(), plugin_id=103, folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text()).get('compatShims', []), [])
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            self.assertEqual((folder/'py_modules/ludusavi.py').read_bytes(),
                             original.read(record['folder']+'/py_modules/ludusavi.py'))
        self.assertEqual(self.apply('remove', plugin_id=103, folder=record['folder']).returncode, 0)

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

    def test_prefix_manager_is_user_scoped_with_legacy_api_and_original_license(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 130)
        data = official_archive(record)
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']), record['folder'])
        result = self.apply('install', data, plugin_id=130, folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/record['folder']
        manifest = json.loads((folder/'plugin.json').read_text())
        self.assertEqual(manifest['flags'], [])
        self.assertNotIn('api_version', manifest)
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text())['compatShims'],
                         ['prefix-manager-user-paths'])
        compile((folder/'main.py').read_bytes(), str(folder/'main.py'), 'exec')
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            self.assertEqual((folder/'LICENSE').read_bytes(), original.read(record['folder']+'/LICENSE'))
        if shutil.which('node'):
            frontend = subprocess.run(['node', str(Path(__file__).parent/'page/framey_prefix_manager.mjs'),
                                       str(folder/'dist/index.js')], capture_output=True, text=True, timeout=10)
            self.assertEqual(frontend.returncode, 0, frontend.stderr)
        self.assertEqual(self.apply('remove', plugin_id=130, folder=record['folder']).returncode, 0)
        self.assertFalse(folder.exists())

    def test_deck_progress_eof_repair_is_scoped_to_exact_archive(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 134)
        data = official_archive(record)
        result = self.apply('install', data, plugin_id=134, folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/record['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['deck-progress-ipc-eof'])
        self.assertEqual((folder/'py_modules/framey_decky_ipc.py').read_bytes(),
                         (Path(frame_decky_store.__file__).parent/'framey_decky_ipc.py').read_bytes())
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            for member in original.infolist():
                if member.is_dir():
                    continue
                name = member.filename.split('/', 1)[1]
                actual = (folder/name).read_bytes()
                if name == 'main.py':
                    self.assertTrue(actual.endswith(original.read(member)))
                    compile(actual, str(folder/name), 'exec')
                else:
                    self.assertEqual(actual, original.read(member), name)
        self.assertEqual(self.apply('remove', plugin_id=134, folder=record['folder']).returncode, 0)
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr(record['folder']+'/new-version.txt', 'changed')
        result = self.apply('install', changed.getvalue(), plugin_id=134,
                            folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((folder/'py_modules/framey_decky_ipc.py').exists())
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text()).get('compatShims', []), [])
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            self.assertEqual((folder/'main.py').read_bytes(), original.read(record['folder']+'/main.py'))
        self.assertEqual(self.apply('remove', plugin_id=134, folder=record['folder']).returncode, 0)

    def test_download_all_awaits_the_scoped_batch_and_reports_failures(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 131)
        result = self.apply('install', official_archive(record), plugin_id=131,
                            folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/record['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['download-all-local-queue'])
        with zipfile.ZipFile(io.BytesIO(official_archive(record))) as original:
            for name in ('main.py', 'LICENSE'):
                self.assertEqual((folder/name).read_bytes(), original.read(record['folder']+'/'+name))
        frontend = folder/'dist/index.js'
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_download_all.mjs'),
                                 str(frontend)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.apply('remove', plugin_id=131, folder=record['folder']).returncode, 0)
        self.assertFalse(folder.exists())

    def test_prefix_manager_102_release_asset_disables_game_data_delete(self):
        from framey_official import PREFIX_MANAGER_102, archive as official_archive
        record = PREFIX_MANAGER_102
        data = official_archive(record)
        self.assertEqual(hashlib.sha256(data).hexdigest(), record['sha256'])
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']), record['folder'])
        result = self.apply('install', data, plugin_id=130, folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / record['folder']
        self.assertEqual(json.loads((folder/'plugin.json').read_text())['flags'], [])
        source = (folder/'main.py').read_text()
        compile(source, str(folder/'main.py'), 'exec')
        self.assertIn('if delete_game_folder:\n        return False, "Game data deletion is unavailable on Frame; no files changed"', source)
        frontend = (folder/'dist/index.js').read_text()
        self.assertNotIn('showDeleteGameFolder: true', frontend)
        self.assertNotIn('showDeleteGameFolder: game.install_path !== "-"', frontend)
        self.assertEqual(frontend.count('showDeleteGameFolder: false'), 2)
        if shutil.which('node'):
            checked = subprocess.run(['node', str(Path(__file__).parent/'page/framey_prefix_manager.mjs'),
                                      str(folder/'dist/index.js')], capture_output=True, text=True, timeout=10)
            self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(self.apply('remove', plugin_id=130, folder=record['folder']).returncode, 0)
        self.assertFalse(folder.exists())
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr(record['folder']+'/unrecognized.txt', 'changed')
        altered = changed.getvalue()
        with self.assertRaisesRegex(ValueError, 'root'):
            frame_decky_store.archive_info(altered, hashlib.sha256(altered).hexdigest(), record['name'])
        rejected = self.apply('install', altered, plugin_id=130, folder=record['folder'], version=record['version'])
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(folder.exists())

    def test_exact_steamback_duplicate_archive_installs_and_removes(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(record for record in PLUGINS if record['id'] == 46)
        data = official_archive(plugin)
        folder = plugin['folder']
        installed = self.folder.parent / folder
        result = self.apply('install', data, plugin_id=plugin['id'],
                            folder=folder, version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((installed / '.frame-control-store.json').read_text())
        self.assertEqual((receipt['storeId'], receipt['sha256']),
                         (plugin['id'], plugin['sha256']))
        self.assertTrue((installed / 'py_modules/steamback/__init__.py').is_file())
        result = self.apply('remove', plugin_id=plugin['id'],
                            folder=folder, version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(installed.exists())

    def test_exact_deck_shelves_keeps_published_files_with_child_ipc_repair(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 135)
        data = official_archive(plugin)
        result = self.apply('install', data, plugin_id=135, folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text())['compatShims'],
                         ['deck-shelves-ipc-eof'])
        prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                  b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            for item in bundle.infolist():
                if item.is_dir():
                    continue
                relative = item.filename.split('/', 1)[1]
                expected = bundle.read(item)
                if relative == 'main.py':
                    expected = prefix+expected
                self.assertEqual((folder/relative).read_bytes(), expected, relative)
        self.assertEqual((folder/'py_modules/framey_decky_ipc.py').read_bytes(),
                         Path(frame_decky_store.__file__).with_name('framey_decky_ipc.py').read_bytes())
        self.assertEqual(self.apply('remove', plugin_id=135, folder=plugin['folder']).returncode, 0)
        self.assertFalse(folder.exists())

    def test_changed_deck_shelves_archive_gets_no_pinned_ipc_repair(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 135)
        data = io.BytesIO(official_archive(plugin))
        with zipfile.ZipFile(data, 'a') as bundle:
            original = bundle.read('Deck-Shelves/main.py')
            bundle.writestr('Deck-Shelves/unrecognized.txt', 'different archive')
        result = self.apply('install', data.getvalue(), plugin_id=135,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        self.assertEqual((folder/'main.py').read_bytes(), original)
        self.assertFalse((folder/'py_modules/framey_decky_ipc.py').exists())
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text()).get('compatShims', []), [])

    def test_deck_shelves_missing_ipc_payload_refuses_incomplete_install(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 135)
        with patch.object(frame_decky_store, 'apply_script', return_value=frame_decky_store.APPLY):
            result = self.apply('install', official_archive(plugin), plugin_id=135,
                                folder=plugin['folder'], version=plugin['version'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing Deck Shelves child IPC EOF repair', result.stderr)
        self.assertFalse((self.folder.parent/plugin['folder']).exists())

    def test_exact_free_loader_keeps_published_files_with_child_ipc_repair(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 63)
        data = official_archive(plugin)
        result = self.apply('install', data, plugin_id=63, folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text())['compatShims'],
                         ['free-loader-ipc-eof'])
        prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                  b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            for item in bundle.infolist():
                if item.is_dir():
                    continue
                relative = item.filename.split('/', 1)[1]
                expected = bundle.read(item)
                if relative == 'main.py':
                    expected = prefix+expected
                self.assertEqual((folder/relative).read_bytes(), expected, relative)
        self.assertEqual((folder/'py_modules/framey_decky_ipc.py').read_bytes(),
                         Path(frame_decky_store.__file__).with_name('framey_decky_ipc.py').read_bytes())
        self.assertEqual(self.apply('remove', plugin_id=63, folder=plugin['folder']).returncode, 0)
        self.assertFalse(folder.exists())

    def test_changed_free_loader_archive_gets_no_pinned_ipc_repair(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 63)
        data = io.BytesIO(official_archive(plugin))
        with zipfile.ZipFile(data, 'a') as bundle:
            original = bundle.read('free-loader/main.py')
            bundle.writestr('free-loader/unrecognized.txt', 'different archive')
        result = self.apply('install', data.getvalue(), plugin_id=63,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        self.assertEqual((folder/'main.py').read_bytes(), original)
        self.assertFalse((folder/'py_modules/framey_decky_ipc.py').exists())
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text()).get('compatShims', []), [])

    def test_free_loader_missing_ipc_payload_refuses_incomplete_install(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 63)
        with patch.object(frame_decky_store, 'apply_script', return_value=frame_decky_store.APPLY):
            result = self.apply('install', official_archive(plugin), plugin_id=63,
                                folder=plugin['folder'], version=plugin['version'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing Free Loader child IPC EOF repair', result.stderr)
        self.assertFalse((self.folder.parent/plugin['folder']).exists())

    def test_exact_radiyo_managed_copy_restores_tls_verification(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 24)
        data = official_archive(plugin)
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        result = self.apply('install', data, plugin_id=24,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        source = (folder/'main.py').read_text(encoding='utf-8')
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['radiyo-verified-tls'])
        self.assertEqual(source.count('ctx = ssl.create_default_context()'), 2)
        self.assertNotIn('ssl.CERT_NONE', source)
        self.assertNotIn('ctx.check_hostname = False', source)
        self.assertEqual(source.count("'URL Error: ' + str(error.reason)"), 2)
        result = self.apply('remove', plugin_id=24, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    def test_exact_deck_settings_managed_copy_verifies_upload_tls(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 93)
        data = official_archive(plugin)
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        result = self.apply('install', data, plugin_id=93,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        source = (folder/'main.py').read_text(encoding='utf-8')
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['deck-settings-verified-tls'])
        self.assertEqual(source.count('ctx = ssl.create_default_context()'), 1)
        self.assertNotIn('ssl.CERT_NONE', source)
        self.assertNotIn('ctx.check_hostname = False', source)
        plugin_class = next(node for node in ast.parse(source).body
                            if isinstance(node, ast.ClassDef) and node.name == 'Plugin')
        method = next(node for node in plugin_class.body
                      if isinstance(node, ast.FunctionDef) and node.name == '_http_request')
        namespace = {'ssl': ssl, 'urllib': urllib, 'RuntimeError': RuntimeError}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<managed-deck-settings>', 'exec'), namespace)
        context = ssl.create_default_context()
        with patch.object(ssl, 'create_default_context', return_value=context), \
                patch.object(urllib.request, 'build_opener', side_effect=OSError('network denied')):
            with self.assertRaisesRegex(OSError, 'network denied'):
                namespace['_http_request'](None, 'https://asset-upload.deckverified.games/',
                                           'POST', {'Authorization': 'Bearer private-fixture'}, b'fixture')
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        result = self.apply('remove', plugin_id=93, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    def test_exact_steam_status_managed_copy_verifies_public_diagnostics_tls(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 123)
        data = official_archive(plugin)
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        result = self.apply('install', data, plugin_id=123,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        source = (folder/'main.py').read_text(encoding='utf-8')
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['steam-status-verified-tls'])
        self.assertEqual(source.count('ssl.create_default_context()'), 2)
        self.assertNotIn('ssl.CERT_NONE', source)
        self.assertNotIn('ssl_context.check_hostname = False', source)

        plugin_class = next(node for node in ast.parse(source).body
                            if isinstance(node, ast.ClassDef) and node.name == 'Plugin')
        nested = {}
        for method_name, function_name in (('test_steam_latency', 'fetch_and_test_cms'),
                                           ('test_internet_speed', 'test_download')):
            method = next(node for node in plugin_class.body if getattr(node, 'name', None) == method_name)
            nested[function_name] = next(node for node in ast.walk(method)
                                         if isinstance(node, ast.FunctionDef) and node.name == function_name)
        logger = types.SimpleNamespace(info=lambda *_: None, error=lambda *_: None)
        namespace = {'ssl': ssl, 'urllib': urllib, 'time': types.SimpleNamespace(time=lambda: 1),
                     'decky_plugin': types.SimpleNamespace(logger=logger),
                     'test_url': 'https://private.invalid/fixture'}
        exec(compile(ast.Module(body=list(nested.values()), type_ignores=[]),
                     '<managed-steam-status>', 'exec'), namespace)
        context = ssl.create_default_context()
        with patch.object(ssl, 'create_default_context', return_value=context), \
                patch.object(urllib.request, 'urlopen', side_effect=OSError('network denied')):
            with self.assertRaisesRegex(OSError, 'network denied'):
                namespace['fetch_and_test_cms']()
            self.assertEqual(namespace['test_download'](), 0)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        result = self.apply('remove', plugin_id=123, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    def test_exact_suggestme_fallback_keeps_certificate_verification(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 132)
        data = official_archive(plugin)
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        result = self.apply('install', data, plugin_id=132,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        source = (folder/'main.py').read_text(encoding='utf-8')
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['suggestme-verified-tls'])
        self.assertNotIn('ssl.CERT_NONE', source)
        self.assertNotIn('ctx.check_hostname = False', source)
        method = next(node for node in ast.parse(source).body
                      if isinstance(node, ast.FunctionDef) and node.name == '_create_ssl_context')
        namespace = {'ssl': ssl, 'certifi': types.SimpleNamespace(where=lambda: '/missing-ca')}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<managed-suggestme>', 'exec'), namespace)
        verified = ssl.create_default_context()
        with patch.object(ssl, 'create_default_context', side_effect=[OSError('certifi CA failed'), verified]):
            fallback = namespace['_create_ssl_context']()
        self.assertIs(fallback, verified)
        self.assertTrue(fallback.check_hostname)
        self.assertEqual(fallback.verify_mode, ssl.CERT_REQUIRED)
        result = self.apply('remove', plugin_id=132, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    def test_exact_notifications_uses_private_decky_logging(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 79)
        data = official_archive(plugin)
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        result = self.apply('install', data, plugin_id=79,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['notifications-private-logs'])
        main = (folder/'main.py').read_text()
        crypto = (folder/'py_modules/connector/crypto.py').read_text()
        self.assertNotIn('filename="/tmp/notifications.log"', main)
        self.assertNotIn('=== ENVIRON ===', crypto)
        self.assertNotIn('clear_env.items()', crypto)
        result = self.apply('remove', plugin_id=79, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    def test_exact_storage_cleaner_deletes_only_private_cache_fixture(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 50)
        data = official_archive(plugin)
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        result = self.apply('install', data, plugin_id=50,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['storage-cleaner-bounded-delete'])
        source = (folder/'main.py').read_text(encoding='utf-8')
        self.assertNotIn('await shutil.rmtree', source)
        frontend = subprocess.run(['node', str(Path(__file__).parent/'page/framey_storage_cleaner.mjs'),
                                   str(folder/'dist/index.js')], capture_output=True, text=True, timeout=10)
        self.assertEqual(frontend.returncode, 0, frontend.stderr)
        steamapps = Path(self.tmp.name)/'.steam/steam/steamapps'
        selected = steamapps/'shadercache/424242'
        selected.mkdir(parents=True)
        (selected/'marker').write_text('private fixture')
        outside = Path(self.tmp.name)/'outside'
        outside.mkdir()
        (outside/'marker').write_text('must survive')
        namespace = {'__name__': 'storage_cleaner_fixture'}
        fake_decky = types.SimpleNamespace(DECKY_USER_HOME=self.tmp.name,
                                           DECKY_PLUGIN_DIR=str(folder))
        with patch.dict(sys.modules, {'decky': fake_decky}):
            exec(compile(source, str(folder/'main.py'), 'exec'), namespace)
        plugin_class = namespace['Plugin']
        for name in ('../outside', 'shadercache/../outside', 'compatdata/../../outside',
                     'shadercache/not-an-app', '/tmp/outside'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Invalid cache path'):
                asyncio.run(plugin_class.delete_cache(name))
        (steamapps/'compatdata').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            asyncio.run(plugin_class.delete_cache('compatdata'))
        self.assertTrue((outside/'marker').is_file())
        self.assertIsNone(asyncio.run(plugin_class.delete_cache('shadercache/424242')))
        self.assertFalse(selected.exists())
        self.assertTrue((outside/'marker').is_file())
        result = self.apply('remove', plugin_id=50, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_modified_fileserver_archive_does_not_inherit_exception(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 60)
        original = official_archive(record)
        with zipfile.ZipFile(io.BytesIO(original)) as source:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as target:
                for entry in source.infolist():
                    target.writestr(entry, source.read(entry))
                target.writestr(record['folder']+'/changed.txt', b'new version')
        data = stream.getvalue()
        with self.assertRaisesRegex(ValueError, 'non-ARM64'):
            frame_decky_store.archive_info(data, hashlib.sha256(data).hexdigest(), record['name'])
        result = self.apply('install', data, plugin_id=60, folder=record['folder'], version=record['version'])
        # Remote defence rejects root even when the desktop validation is bypassed.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Root', result.stderr)

    def test_corrupt_fileserver_offline_helper_is_rejected(self):
        with patch.object(frame_decky_store, 'FILESERVER_BINARIES', {'x86_64': '0'*64}):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                frame_decky_store.apply_script(60, frame_decky_store.FILESERVER_DIGEST)
        self.assertEqual(frame_decky_store.apply_script(60, '0'*64), frame_decky_store.APPLY)

    @unittest.skipUnless(__import__('platform').machine() in ('x86_64', 'aarch64'), 'native Linux helper architecture')
    def test_exact_wine_cellar_archive_gets_only_the_pinned_native_helper(self):
        from framey_official import PLUGINS, archive as official_archive
        import platform
        record = next(p for p in PLUGINS if p['id'] == 68)
        data = official_archive(record)
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']), record['folder'])
        result = self.apply('install', data, plugin_id=68, folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/record['folder']
        helper = folder/'bin/backend'
        expected = (frame_decky_store.WINE_CELLAR_AARCH64 if platform.machine() == 'aarch64'
                    else frame_decky_store.WINE_CELLAR_ORIGINAL)
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(), expected)
        self.assertEqual(helper.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads((folder/'.frame-control-store.json').read_text())['compatShims'],
                         ['wine-cellar-native-bridge', 'wine-cellar-ipc-eof'])
        self.assertEqual(hashlib.sha256((folder/'main.py').read_bytes()).hexdigest(),
                         frame_decky_store.WINE_CELLAR_MANAGED_MAIN)
        self.assertEqual((folder/'py_modules/framey_decky_ipc.py').read_bytes(),
                         (Path(frame_decky_store.__file__).parent/'framey_decky_ipc.py').read_bytes())
        self.assertEqual(hashlib.sha256((folder/'dist/index.js').read_bytes()).hexdigest(),
                         frame_decky_store.WINE_CELLAR_FRONTEND)

    def test_corrupt_wine_cellar_offline_helper_is_rejected(self):
        with patch.object(frame_decky_store, 'WINE_CELLAR_AARCH64', '0'*64):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                frame_decky_store.apply_script(68, frame_decky_store.WINE_CELLAR_DIGEST)
        self.assertEqual(frame_decky_store.apply_script(68, '0'*64), frame_decky_store.APPLY)

    def test_exact_fileserver_gets_native_user_helper(self):
        from framey_official import PLUGINS, archive as official_archive
        import platform
        if platform.machine() not in frame_decky_store.FILESERVER_BINARIES:
            self.skipTest('native Linux helper architecture')
        record = next(p for p in PLUGINS if p['id'] == 60)
        data = official_archive(record)
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']), record['folder'])
        result = self.apply('install', data, plugin_id=60, folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        plugin = self.folder.parent/record['folder']
        self.assertEqual(json.loads((plugin/'plugin.json').read_text())['flags'], [])
        self.assertEqual(json.loads((plugin/'.frame-control-store.json').read_text())['compatShims'],
                         ['deckyfileserver-user-native', 'deckyfileserver-https-address',
                          'deckyfileserver-directory-entry'])
        helper = plugin/'bin/backend'
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(), frame_decky_store.FILESERVER_BINARIES[platform.machine()])
        self.assertEqual(helper.stat().st_mode & 0o777, 0o700)
        compile((plugin/'main.py').read_text(), str(plugin/'main.py'), 'exec')
        self.assertIn('if arg]', (plugin/'main.py').read_text())
        self.assertIn('Choose an existing absolute directory', (plugin/'main.py').read_text())
        rendered = subprocess.run(['node', str(Path(__file__).parent/'page/framey_fileserver_url.mjs'),
                                   str(plugin/'dist/index.js')], capture_output=True, text=True, timeout=20)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)

    @unittest.skipUnless(__import__('platform').machine() in ('x86_64', 'aarch64'), 'native Linux helper architecture')
    def test_exact_localsend_gets_verified_native_helper_and_preserves_source(self):
        from framey_official import PLUGINS, archive as official_archive
        import platform
        plugin = next(p for p in PLUGINS if p['id'] == 125)
        data = official_archive(plugin)
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        result = self.apply('install', data, plugin_id=125, folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['localsend-digest-native'])
        self.assertEqual(json.loads((folder/'plugin.json').read_text())['flags'], [])
        expected = (frame_decky_store.LOCALSEND_AARCH64 if platform.machine() == 'aarch64'
                    else frame_decky_store.LOCALSEND_ORIGINAL)
        self.assertEqual(hashlib.sha256((folder/'bin/localsend-core').read_bytes()).hexdigest(), expected)
        self.assertEqual((folder/'bin/localsend-core').stat().st_mode & 0o777, 0o700)
        with zipfile.ZipFile(io.BytesIO(data)) as source:
            for name in ('main.py', 'LICENSE'):
                self.assertEqual((folder/name).read_bytes(), source.read(plugin['folder']+'/'+name))
        result = self.apply('remove', plugin_id=125, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    @unittest.skipUnless(__import__('platform').machine() in ('x86_64', 'aarch64'), 'native Linux helper architecture')
    def test_exact_emuchievements_gets_verified_managed_helper_and_source(self):
        from framey_official import PLUGINS, archive as official_archive
        import platform
        record = next(p for p in PLUGINS if p['id'] == 28)
        data = official_archive(record)
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']), record['folder'])
        result = self.apply('install', data, plugin_id=28,
                            folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/record['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['emuchievements-safe-arm64'])
        helper = folder/'bin/hash'
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(),
                         frame_decky_store.EMU_BINARIES[platform.machine()])
        self.assertEqual(helper.stat().st_mode & 0o777, 0o700)
        source = folder/'main.py'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), frame_decky_store.EMU_MANAGED_MAIN)
        self.assertIn('asyncio.create_subprocess_exec', source.read_text())
        self.assertNotIn('os.popen', source.read_text())
        self.assertEqual(self.apply('remove', plugin_id=28, folder=record['folder']).returncode, 0)
        self.assertFalse(folder.exists())

    def test_emuchievements_exception_rejects_changed_archive_or_assets(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 28)
        changed = io.BytesIO(official_archive(record))
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr('Emuchievements/changed.txt', 'changed')
        altered = changed.getvalue()
        with self.assertRaisesRegex(ValueError, 'non-ARM64'):
            frame_decky_store.archive_info(altered, hashlib.sha256(altered).hexdigest(), record['name'])
        self.assertEqual(frame_decky_store.apply_script(28, '0'*64), frame_decky_store.APPLY)
        with patch.object(frame_decky_store, 'EMU_BINARIES', {'x86_64': '0'*64, 'aarch64': '0'*64}):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                frame_decky_store.apply_script(28, record['sha256'])
        with patch.object(frame_decky_store, 'EMU_MANAGED_MAIN', '0'*64):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                frame_decky_store.apply_script(28, record['sha256'])

    def test_localsend_exception_does_not_accept_another_archive_or_corrupt_helper(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 125)
        with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as source:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as target:
                for entry in source.infolist():
                    target.writestr(entry, source.read(entry))
                target.writestr(plugin['folder']+'/changed.txt', b'new version')
        changed = stream.getvalue()
        with self.assertRaisesRegex(ValueError, 'non-ARM64'):
            frame_decky_store.archive_info(changed, hashlib.sha256(changed).hexdigest(), plugin['name'])
        self.assertEqual(frame_decky_store.apply_script(125, '0'*64), frame_decky_store.APPLY)
        with patch.object(frame_decky_store, 'LOCALSEND_AARCH64', '0'*64):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                frame_decky_store.apply_script(125, frame_decky_store.LOCALSEND_DIGEST)

    def test_localsend_arm64_transaction_checks_written_helper(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 125)
        # The local x86 host only writes the ELF; native ARM execution is gated
        # separately by the published Decky runtime runner.
        with patch.object(frame_decky_store, 'APPLY',
                          "import platform\nplatform.machine=lambda:'aarch64'\n"+frame_decky_store.APPLY):
            result = self.apply('install', official_archive(plugin), plugin_id=125,
                                folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        helper = self.folder.parent/plugin['folder']/'bin/localsend-core'
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(),
                         frame_decky_store.LOCALSEND_AARCH64)
        self.assertEqual(int.from_bytes(helper.read_bytes()[18:20], 'little'), 183)
    @unittest.skipUnless(__import__('platform').machine() in ('x86_64', 'aarch64'), 'native Linux wheel architecture')
    def test_exact_battery_tracker_uses_user_battery_supply_and_preserves_license(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 67)
        data = official_archive(record)
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']), record['folder'])
        result = self.apply('install', data, plugin_id=67,
                            folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / record['folder']
        receipt = json.loads((folder / '.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['battery-tracker-user-supply'])
        self.assertEqual(json.loads((folder / 'plugin.json').read_text())['flags'], [])
        source = (folder / 'main.py').read_text()
        self.assertNotIn('/sys/class/power_supply/BAT1/', source)
        self.assertIn("root / 'BAT1'", source)
        compile(source, str(folder / 'main.py'), 'exec')
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            self.assertEqual((folder / 'LICENSE').read_bytes(), original.read(record['folder']+'/LICENSE'))
        self.assertEqual(self.apply('remove', plugin_id=67, folder=record['folder']).returncode, 0)
        self.assertFalse(folder.exists())
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as archive:
            archive.writestr(record['folder']+'/changed.txt', 'changed')
        altered = changed.getvalue()
        with self.assertRaisesRegex(ValueError, 'root'):
            frame_decky_store.archive_info(altered, hashlib.sha256(altered).hexdigest(), record['name'])
        result = self.apply('install', altered, plugin_id=67,
                            folder=record['folder'], version=record['version'])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(folder.exists())

    def test_adapted_battery_tracker_empty_history_and_unload_flush(self):
        from framey_official import PLUGINS, archive as official_archive
        record = next(p for p in PLUGINS if p['id'] == 67)
        result = self.apply('install', official_archive(record), plugin_id=67,
                            folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / record['folder']
        runtime = Path(self.tmp.name) / 'battery-runtime'
        runtime.mkdir()
        supply = Path(self.tmp.name) / 'battery-supply' / 'frame-battery'
        supply.mkdir(parents=True)
        for name, value in {'type': 'Battery', 'capacity': '89', 'status': 'Charging',
                            'voltage_now': '8746718', 'current_now': '1030625'}.items():
            (supply / name).write_text(value + '\n')
        decky = types.ModuleType('decky_plugin')
        decky.logger = logging.getLogger('battery-tracker-test')
        decky.DECKY_PLUGIN_RUNTIME_DIR = str(runtime)
        with patch.dict(sys.modules, {'decky_plugin': decky}), patch.dict(os.environ, {'FRAMEY_BATTERY_ROOT': str(supply.parent)}):
            spec = importlib.util.spec_from_file_location('framey_battery_tracker_test', folder / 'main.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            async def exercise():
                plugin = module.Plugin()
                await plugin._main()
                self.assertEqual(await plugin.get_recent_data(), {'x': [], 'cap': [], 'power_data': []})
                # The first sample is still pending when Decky unloads the plugin.
                await asyncio.sleep(0)
                self.assertEqual(len(plugin._pending_samples), 1)
                self.assertEqual((await plugin.get_recent_data())['cap'], [.89])
                await plugin._unload()
                self.assertEqual(plugin._pending_samples, [])

            asyncio.run(exercise())
        import sqlite3
        with sqlite3.connect(runtime / 'battery.db') as db:
            self.assertEqual(db.execute('select capacity from battery').fetchall(), [(89,)])

    @unittest.skipUnless(__import__('platform').machine() in ('x86_64', 'aarch64'), 'native Linux wheel architecture')
    def test_exact_network_sentinel_is_user_scoped_and_digest_guarded(self):
        from framey_official import PLUGINS, archive as official_archive
        import platform
        record = next(p for p in PLUGINS if p['id'] == 114)
        data = official_archive(record)
        self.assertEqual(frame_decky_store.archive_info(data, record['sha256'], record['name']), record['folder'])
        result = self.apply('install', data, plugin_id=114,
                            folder=record['folder'], version=record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / record['folder']
        receipt = json.loads((folder / '.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['network-sentinel-user-psutil'])
        self.assertEqual(json.loads((folder / 'plugin.json').read_text())['flags'], ['debug'])
        source = (folder / 'main.py').read_text()
        self.assertNotIn('decky.DECKY_SETTINGS_DIR', source)
        self.assertIn('decky.DECKY_PLUGIN_SETTINGS_DIR', source)
        self.assertIn("            jitter = 0\n            cmd = ['ping'", source)
        compile(source, str(folder / 'main.py'), 'exec')
        native = (folder / 'py_modules/psutil/_psutil_linux.abi3.so').read_bytes()
        self.assertEqual(int.from_bytes(native[18:20], 'little'),
                         {'x86_64': 62, 'aarch64': 183}[platform.machine()])
        self.assertIn('BSD 3-Clause', (folder / 'py_modules/psutil-7.2.2.dist-info/LICENSE').read_text())
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            self.assertEqual((folder / 'LICENSE').read_bytes(), original.read(record['folder']+'/LICENSE'))
        self.assertEqual(self.apply('remove', plugin_id=114, folder=record['folder']).returncode, 0)
        self.assertFalse(folder.exists())
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as archive:
            archive.writestr(record['folder']+'/changed.txt', 'changed')
        altered = changed.getvalue()
        with self.assertRaisesRegex(ValueError, 'root'):
            frame_decky_store.archive_info(altered, hashlib.sha256(altered).hexdigest(), record['name'])
        result = self.apply('install', altered, plugin_id=114,
                            folder=record['folder'], version=record['version'])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(folder.exists())

    @unittest.skipUnless(__import__('platform').machine() in ('x86_64', 'aarch64'), 'native Linux wheel architecture')
    def test_exact_deckyspy_gets_native_dependency_and_license_only_in_its_folder(self):
        from framey_official import PLUGINS, archive as official_archive
        import platform
        plugin = next(p for p in PLUGINS if p['id'] == 89)
        result = self.apply('install', official_archive(plugin), plugin_id=89,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / plugin['folder']
        receipt = json.loads((folder / '.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['deckyspy-psutil-and-battery'])
        modules = folder / 'py_modules'
        native = (modules / 'psutil/_psutil_linux.abi3.so').read_bytes()
        self.assertEqual(native[:4], b'\x7fELF')
        self.assertEqual(int.from_bytes(native[18:20], 'little'),
                         {'x86_64': 62, 'aarch64': 183}[platform.machine()])
        self.assertIn('BSD 3-Clause', (modules / 'psutil-7.2.2.dist-info/LICENSE').read_text())
        result = self.apply('remove', plugin_id=89, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    @unittest.skipUnless(__import__('platform').machine() in ('x86_64', 'aarch64'), 'native Linux wheel architecture')
    def test_deckyspy_missing_or_corrupt_payload_leaves_no_installed_copy(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 89)
        for prefix, error in [('', 'Missing native psutil'),
                              ("FRAMEY_BACKEND_WHEELS = {'x86_64':'AAAA','aarch64':'AAAA'}\n",
                               'SHA-256 mismatch')]:
            with patch.object(frame_decky_store, 'apply_script', return_value=prefix+frame_decky_store.APPLY):
                result = self.apply('install', official_archive(plugin), plugin_id=89,
                                    folder=plugin['folder'], version=plugin['version'])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(error, result.stderr)
            self.assertFalse((self.folder.parent / plugin['folder']).exists())
    def test_tabmaster_restore_repair_preserves_other_bytes_and_rejects_changed_archive(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 61)
        data = official_archive(plugin)
        args = dict(plugin_id=61, folder=plugin['folder'], version=plugin['version'])
        result = self.apply('install', data, **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / plugin['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['tabmaster-json-file-restore'])
        old = b'        data = json.loads(settings_file)\n'
        new = (b'        data = json.load(settings_file)\n'
               b'        if not isinstance(data, dict):\n          return False\n')
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            original_main = bundle.read(plugin['folder']+'/main.py')
            for name in bundle.namelist():
                if name.endswith('/'):
                    continue
                original = bundle.read(name)
                expected = original.replace(old, new) if name.endswith('/main.py') else original
                self.assertEqual((folder/Path(name).relative_to(plugin['folder'])).read_bytes(), expected, name)
        self.assertEqual(json.loads((folder/'plugin.json').read_text())['api_version'], 1)
        self.assertEqual(self.apply('remove', **args).returncode, 0)
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr(plugin['folder']+'/different-version.txt', 'changed archive')
        result = self.apply('install', changed.getvalue(), **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((folder/'main.py').read_bytes(), original_main)
        self.assertNotIn('compatShims', json.loads((folder/'.frame-control-store.json').read_text()))

    def test_exact_simple_timer_gets_lifecycle_repair_and_keeps_api1_and_license(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 96)
        result = self.apply('install', official_archive(plugin), plugin_id=96,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / plugin['folder']
        self.assertEqual(json.loads((folder / '.frame-control-store.json').read_text())['compatShims'],
                         ['simple-timer-lifecycle'])
        self.assertEqual(json.loads((folder / 'plugin.json').read_text())['api_version'], 1)
        with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as original:
            self.assertEqual((folder / 'LICENSE').read_bytes(), original.read('simple-timer/LICENSE'))
        # Backend behavior is verified separately by the real Decky lifecycle gate.
        result = self.apply('remove', plugin_id=96, folder=plugin['folder'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

    def test_changed_simple_timer_digest_does_not_get_pinned_repair(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 96)
        data = io.BytesIO(official_archive(plugin))
        with zipfile.ZipFile(data, 'a') as changed:
            original_main = changed.read('simple-timer/main.py')
            changed.writestr('simple-timer/new-version.txt', 'unrecognized new payload')
        result = self.apply('install', data.getvalue(), plugin_id=96,
                            folder=plugin['folder'], version=plugin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent / plugin['folder']
        self.assertEqual((folder / 'main.py').read_bytes(), original_main)
        self.assertEqual(json.loads((folder / '.frame-control-store.json').read_text()).get('compatShims', []), [])

    def test_exact_game_sync_archive_bounds_read_only_path_selection(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 104)
        data = official_archive(plugin)
        args = {'plugin_id':104, 'folder':plugin['folder'], 'version':plugin['version']}
        result = self.apply('install', data, **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['game-sync-bounded-selection'])
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            for name in ('LICENSE', 'plugin.json', 'dist/index.js', 'main.py',
                         'py_modules/rclone_manager.py', 'py_modules/sync_target.py'):
                self.assertEqual((folder/name).read_bytes(), original.read(plugin['folder']+'/'+name))
        contracts = subprocess.run([sys.executable, str(Path(__file__).parent/'game_sync_paths_contract.py'), str(folder)],
                                  capture_output=True, text=True, env=self.env, timeout=15)
        self.assertEqual(contracts.returncode, 0, contracts.stderr)
        self.assertEqual(self.apply('remove', expected=plugin['sha256'], **args).returncode, 0)
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr(plugin['folder']+'/unrecognized-version.txt', 'changed payload')
        result = self.apply('install', changed.getvalue(), **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('compatShims', json.loads((folder/'.frame-control-store.json').read_text()))

    def test_exact_deckyparty_archive_owns_user_process_lifecycle(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 117)
        data = official_archive(plugin)
        args = {'plugin_id':117, 'folder':plugin['folder'], 'version':plugin['version']}
        result = self.apply('install', data, **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.folder.parent/plugin['folder']
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['deckyparty-user-lifecycle'])
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            for name in ('LICENSE', 'plugin.json', 'dist/index.js', 'bin/copyparty-sfx.py'):
                self.assertEqual((folder/name).read_bytes(), original.read('Decky-CP/'+name))
        contracts = subprocess.run([sys.executable, str(Path(__file__).parent/'deckyparty_contract.py'), str(folder)],
                                  capture_output=True, text=True, env=self.env, timeout=15)
        self.assertEqual(contracts.returncode, 0, contracts.stderr)
        self.assertEqual(self.apply('remove', expected=plugin['sha256'], **args).returncode, 0)
        changed = io.BytesIO(data)
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr('Decky-CP/unrecognized-version.txt', 'changed payload')
        result = self.apply('install', changed.getvalue(), **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('compatShims', json.loads((folder/'.frame-control-store.json').read_text()))

    def test_exact_shotty_archive_gets_isolated_click_import(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 53)
        data = official_archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        shotty = self.folder.parent / plugin['folder']
        args = {'plugin_id': plugin['id'], 'folder': plugin['folder'], 'version': plugin['version']}
        result = self.apply('install', data, **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((shotty / '.frame-control-store.json').read_text())
        self.assertEqual(receipt['sha256'], plugin['sha256'])
        self.assertEqual(receipt['compatShims'], ['shotty-click-app-dir', 'shotty-bounded-copies', 'shotty-ipc-eof'])
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            self.assertEqual((shotty/'LICENSE').read_bytes(), original.read('Shotty/LICENSE'))
        self.assertEqual((shotty/'py_modules/framey_decky_ipc.py').read_bytes(),
                         (Path(__file__).resolve().parents[1]/'ui/framey_decky_ipc.py').read_bytes())
        compat = shotty / 'py_modules/click.py'
        self.assertTrue(compat.is_file())
        source = '''import asyncio, importlib.util, logging, sys, types
from pathlib import Path
folder = Path(sys.argv[1])
sys.path.insert(0, str(folder/'py_modules'))
decky = types.ModuleType('decky_plugin')
decky.logger = logging.getLogger('shotty-test')
decky.DECKY_PLUGIN_DIR = str(folder)
sys.modules['decky_plugin'] = decky
# These are filesystem-only contracts; the native job exercises real Decky IPC.
ipc = types.ModuleType('framey_decky_ipc')
ipc.install = lambda: None
sys.modules['framey_decky_ipc'] = ipc
spec = importlib.util.spec_from_file_location('shotty', folder/'main.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.Plugin.__name__ == 'Plugin'
from click import get_app_dir
assert get_app_dir('Shotty') == str(Path.home()/'.config/Shotty')
photo = Path.home()/'.local/share/Steam/userdata/100/760/remote/42/screenshots/test.jpg'
photo.parent.mkdir(parents=True)
photo.write_bytes(b'local screenshot fixture')
plugin = module.Plugin()
assert asyncio.run(plugin.aggregate_all([[42, 'Local Test Game']])) == 1
copied = Path.home()/'Pictures/Screenshots/Local Test Game/test.jpg'
assert copied.read_bytes() == b'local screenshot fixture'
'''
        imported = subprocess.run([sys.executable, '-c', source, str(shotty)],
                                  capture_output=True, text=True,
                                  env={**self.env, 'XDG_CONFIG_HOME': str(Path(self.tmp.name)/'.config')}, timeout=10)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        contracts = subprocess.run([sys.executable, str(Path(__file__).parent/'shotty_contract.py'), str(shotty)],
                                   capture_output=True, text=True, env=self.env, timeout=15)
        self.assertEqual(contracts.returncode, 0, contracts.stderr)
        result = self.apply('remove', expected=plugin['sha256'], **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(shotty.exists())
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as bundle:
            bundle.writestr('Shotty/plugin.json', json.dumps({'name': 'Shotty', 'flags': []}))
            bundle.writestr('Shotty/dist/index.js', 'export default {};' + ' ' * 1200)
        other = stream.getvalue()
        result = self.apply('install', other, **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((shotty / 'py_modules/click.py').exists())
        self.assertNotIn('compatShims', json.loads((shotty / '.frame-control-store.json').read_text()))

    def test_legacy_music_control_keeps_decky_class_calling_convention(self):
        from framey_official import PLUGINS, archive as official_archive
        plugin = next(p for p in PLUGINS if p['id'] == 111)
        data = official_archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        folder = self.folder.parent / plugin['folder']
        args = {'plugin_id': plugin['id'], 'folder': plugin['folder'], 'version': plugin['version']}
        result = self.apply('install', data, **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((folder / '.frame-control-store.json').read_text())
        self.assertEqual(receipt['sha256'], plugin['sha256'])
        self.assertEqual(receipt['compatShims'], ['music-control-system-dbus-env'])
        self.assertNotIn('api_version', json.loads((folder / 'plugin.json').read_text()))
        self.assertIn('self._get_dbus_env(self)', (folder / 'main.py').read_text())

        dbus = Path(self.tmp.name) / 'dbus-send'
        dbus.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
args = ' '.join(sys.argv[1:])
assert os.environ['LD_LIBRARY_PATH'] == os.environ.get('LD_LIBRARY_PATH_ORIG', '')
with Path(os.environ['MPRIS_CALLS']).open('a') as log: log.write(args + '\\n')
if 'ListNames' in args:
    print('method return\\n array [\\n string "org.freedesktop.DBus"\\n string "org.mpris.MediaPlayer2.fixture"\\n ]')
elif 'string:PlaybackStatus' in args:
    print('method return\\n variant string "Paused"')
else:
    print('method return')
''')
        dbus.chmod(0o700)
        calls = Path(self.tmp.name) / 'mpris-calls'
        source = '''import asyncio, importlib.util, os, sys, types
from pathlib import Path
decky = types.ModuleType('decky_plugin')
sys.modules['decky_plugin'] = decky
spec = importlib.util.spec_from_file_location('music_control', Path(sys.argv[1])/'main.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# Decky 3.3 uses the class for manifests with no api_version.
plugin = module.Plugin
async def check():
    assert await plugin.sp_list_media_players(plugin) == 'org.mpris.MediaPlayer2.fixture'
    await plugin.sp_set_media_player(plugin, 'org.mpris.MediaPlayer2.fixture')
    assert await plugin.sp_get_media_player(plugin) == 'org.mpris.MediaPlayer2.fixture'
    await plugin.sp_play(plugin)
    await plugin.sp_pause(plugin)
    await plugin.sp_next(plugin)
    await plugin.sp_previous(plugin)
    await plugin.sp_set_volume(plugin, 0.25)
    assert await plugin.sp_track_status(plugin) == 'Paused'
asyncio.run(check())
assert os.environ['LD_LIBRARY_PATH'] == 'FrameyBundledLibraries'
'''
        called = subprocess.run([sys.executable, '-c', source, str(folder)],
                                capture_output=True, text=True,
                                env={**self.env, 'MPRIS_CALLS': str(calls), 'LD_LIBRARY_PATH': 'FrameyBundledLibraries',
                                     'LD_LIBRARY_PATH_ORIG': 'FrameySystemLibraries'}, timeout=10)
        self.assertEqual(called.returncode, 0, called.stderr)
        logged = calls.read_text()
        self.assertIn('org.freedesktop.DBus.ListNames', logged)
        self.assertIn('org.mpris.MediaPlayer2.Player.PlayPause', logged)
        self.assertIn('org.mpris.MediaPlayer2.Player.Pause', logged)
        self.assertIn('string:Volume variant:double:0.25', logged)
        self.assertIn('org.mpris.MediaPlayer2.fixture', logged)
        # An explicit same-version update replaces the previously shipped bad shim.
        main = folder / 'main.py'
        main.write_text(main.read_text().replace('self._get_dbus_env(self)', 'self._get_dbus_env()'))
        receipt['compatShims'] = ['music-control-bound-methods']
        (folder / '.frame-control-store.json').write_text(json.dumps(receipt))
        result = self.apply('update', data, expected=plugin['sha256'], **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        called = subprocess.run([sys.executable, '-c', source, str(folder)],
                                capture_output=True, text=True,
                                env={**self.env, 'MPRIS_CALLS': str(calls),
                                     'LD_LIBRARY_PATH': 'FrameyBundledLibraries'}, timeout=10)
        self.assertEqual(called.returncode, 0, called.stderr)
        result = self.apply('remove', expected=plugin['sha256'], **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(folder.exists())

        older = next(p for p in PLUGINS if p['id'] == 12)
        old_data = official_archive(older)
        old_args = {'plugin_id': older['id'], 'folder': older['folder'], 'version': older['version']}
        result = self.apply('install', old_data, **old_args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((folder / '.frame-control-store.json').read_text())['compatShims'],
                         ['music-control-system-dbus-env'])
        self.assertNotIn('api_version', json.loads((folder / 'plugin.json').read_text()))
        self.assertIn('self._get_dbus_env(self)', (folder / 'main.py').read_text())
        old_env = {**self.env, 'MPRIS_CALLS': str(calls), 'LD_LIBRARY_PATH': 'FrameyBundledLibraries'}
        old_env.pop('LD_LIBRARY_PATH_ORIG', None)
        called = subprocess.run([sys.executable, '-c', source, str(folder)],
                                capture_output=True, text=True, env=old_env, timeout=10)
        self.assertEqual(called.returncode, 0, called.stderr)
        result = self.apply('remove', expected=older['sha256'], **old_args)
        self.assertEqual(result.returncode, 0, result.stderr)

        # A future archive at the same store ID must retain its own source.
        other = io.BytesIO()
        untouched = 'class Plugin: pass\n'
        with zipfile.ZipFile(other, 'w') as bundle:
            bundle.writestr('MusicControl/plugin.json', json.dumps({'name': 'Music Control', 'flags': []}))
            bundle.writestr('MusicControl/dist/index.js', 'export default {};' + ' ' * 1200)
            bundle.writestr('MusicControl/main.py', untouched)
        result = self.apply('install', other.getvalue(), **args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((folder / 'main.py').read_text(), untouched)
        self.assertNotIn('compatShims', json.loads((folder / '.frame-control-store.json').read_text()))

    def test_installed_script_entrypoints_execute_without_zip_exec_bits(self):
        data, _ = archive(extra=('Example/scripts/start.py',
                                 b'#!/bin/sh\nprintf "Framey script: %s\\n" "$1"\n'))
        result = self.apply('install', data)
        self.assertEqual(result.returncode, 0, result.stderr)
        script = self.folder / 'scripts/start.py'
        self.assertTrue(script.stat().st_mode & 0o100)
        self.assertFalse(script.stat().st_mode & 0o6111 & ~0o100)
        ran = subprocess.run([str(script), 'ready'], text=True, capture_output=True, timeout=5)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, 'Framey script: ready\n')
        self.assertFalse((self.folder / 'plugin.json').stat().st_mode & 0o111)
        self.assertFalse((self.folder / 'dist/index.js').stat().st_mode & 0o111)

    def test_identical_duplicate_archive_installs_without_widening_permissions(self):
        data, _ = duplicate_archive()
        result = self.apply('install', data)
        self.assertEqual(result.returncode, 0, result.stderr)
        helper = self.folder / 'bin/helper'
        self.assertEqual(helper.read_bytes(), b'#!/bin/sh\nexit 0\n')
        self.assertTrue(helper.stat().st_mode & 0o100)
        self.assertFalse(helper.stat().st_mode & 0o6000)
        self.assertEqual(self.apply('remove').returncode, 0)

    def test_declared_executable_is_owner_only_without_privilege_bits(self):
        info = zipfile.ZipInfo('Example/bin/entrypoint')
        info.create_system = 3
        info.external_attr = 0o104777 << 16
        data, _ = archive(extra=(info, b'entrypoint payload'))
        result = self.apply('install', data)
        self.assertEqual(result.returncode, 0, result.stderr)
        executable = self.folder / 'bin/entrypoint'
        self.assertEqual(executable.stat().st_mode & 0o6111, 0o100)
        self.assertEqual(executable.read_bytes(), b'entrypoint payload')

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

    def test_update_and_remove_reject_stale_installed_receipt(self):
        first, first_hash = archive()
        second, _ = archive(extra=('Example/data.txt', 'new'))
        self.assertEqual(self.apply('install', first).returncode, 0)
        marker = self.folder / '.frame-control-store.json'
        self.assertEqual(json.loads(marker.read_text())['sha256'], first_hash)

        # A newer store operation wins before the caller reaches the lock.
        current = json.loads(marker.read_text())
        current['sha256'] = 'b' * 64
        marker.write_text(json.dumps(current))
        for action, data in [('update', second), ('remove', None)]:
            with self.subTest(action=action):
                result = self.apply(action, data, expected=first_hash)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Installed plugin changed', result.stderr)
                self.assertTrue(self.folder.exists())
                self.assertEqual(json.loads(marker.read_text())['sha256'], 'b' * 64)
        self.assertEqual(list(self.folder.parent.glob('.frame-control-stage-*')), [])
        self.assertEqual(list(self.folder.parent.glob('.frame-control-old-*')), [])
        self.assertEqual(self.apply('remove', expected='b' * 64).returncode, 0)
        self.assertFalse(self.folder.exists())


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
                 [{'storeId': 42, 'folder': 'Example', 'name': 'Example', 'version': '1.0',
                   'sha256': 'a' * 64}]}
        calls = []
        with patch.object(frame_decky_store.frame_decky, 'status', return_value=state), \
             patch.object(frame_decky_store, 'catalog') as network:
            result = frame_decky_store.change(lambda command, **kwargs: calls.append(command) or '{}',
                                               'remove', 42)
        self.assertEqual(result, {})
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].endswith(' ' + 'a' * 64))
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
            {'storeId': 42, 'folder': 'Example', 'name': 'Example', 'version': '1.0',
             'sha256': 'a' * 64}]}
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
        self.assertTrue(calls[1].endswith(' ' + 'a' * 64))

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
