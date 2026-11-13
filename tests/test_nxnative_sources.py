"""Private game sources, portable bundles and validation before device mutation."""
import sandbox  # noqa: F401
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_nxnative as nx
from apk_fixtures import apk, manifest

TITLE = '010093801237C000'
PACKAGE = 'com.nxnative.t' + TITLE.lower()


class SourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.data = self.root / 'settings'
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(nx, '_settings', return_value=self.data / 'sources.json').start()
        patch.object(nx, '_cache', return_value=self.cache).start()
        patch.object(nx, 'RESERVE', 0).start()

    def build(self, modules=('main', 'subsdk0', 'sdk')):
        root = self.root / 'build'
        root.mkdir()
        (root / 'game.apk').write_bytes(apk({'AndroidManifest.xml': manifest(PACKAGE, 0, 0, 30),
                                           'lib/arm64-v8a/libdmhost.so': b'fixture host'}))
        files = {'font/standard.ttf': b'font', 'font/nintendo_ext.ttf': b'extra',
                 'shader/vk/a.spv': b'shader', 'shader/vk/a.vk.txt': b'reflection',
                 'extract/v1/RomFS/textures/some long name.bin': b'rom data'}
        for module in modules:
            files['patched_android/' + module + '.patched.bin'] = b'code'
            files['patched_android/' + module + '.fixups.tsv'] = b'fixups'
        for path, data in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return root

    def bundle(self):
        output = self.root / 'game.nxnative.zip'
        receipt = nx.export_bundle(self.build(), output, TITLE, 'My game', '2.1.0')
        self.assertEqual(receipt['sha256'], nx._hash(output))
        return output

    def catalog(self, games, name='catalog.json'):
        path = self.root / name
        path.write_text(json.dumps({'format': nx.FORMAT, 'games': games}), encoding='utf-8')
        return path

    def serve(self):
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        handler = functools.partial(Quiet, directory=str(self.root))
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return 'http://127.0.0.1:' + str(server.server_port)

    def test_empty_state_and_private_sources_without_defaults(self):
        self.assertEqual(nx.status()['sources'], [])
        self.assertEqual(nx.status()['games'], [])
        p = self.catalog([{'path': 'own.nsp', 'name': 'My copy'}])
        status = nx.add_source(str(p), 'Private share')
        self.assertEqual(status['sources'][0]['name'], 'Private share')
        self.assertFalse(status['games'][0]['installable'])
        self.assertEqual(status['games'][0]['kind'], 'rom')
        self.assertNotIn('_location', status['games'][0])
        self.assertIn('--bundle', status['preparation']['command'])
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE((self.data / 'sources.json').stat().st_mode), 0o600)
        nx.remove_source(status['sources'][0]['id'])
        self.assertEqual(nx.status()['games'], [])

    def test_gamelist_url_list_and_mounted_folder(self):
        p = self.root / 'gamelist.xml'
        p.write_text('<gameList><game><path>./my copy.nsp</path><name>My game</name></game></gameList>')
        result = nx.add_source(str(p))
        self.assertEqual(result['games'][0]['name'], 'My game')
        p = self.root / 'urls.txt'
        p.write_text('# My library\nhttps://example.invalid/own.xci\n')
        result = nx.add_source(str(p))
        self.assertEqual(len(result['games']), 2)
        folder = self.root / 'share'
        folder.mkdir()
        (folder / 'owned.nsp').write_bytes(b'user file')
        result = nx.add_source(str(folder))
        self.assertEqual(len(result['games']), 3)
        with self.assertRaisesRegex(nx.NxNativeError, 'Mount'):
            nx.add_source('smb://nas/my-games')

    def test_bad_source_does_not_hide_healthy_sources_or_keep_stale_install(self):
        healthy = self.catalog([{'path': 'own.nsp'}], 'healthy.json')
        broken = self.catalog([{'bundle': 'game.nxnative.zip'}], 'broken.json')
        nx.add_source(str(healthy))
        added = nx.add_source(str(broken))
        target = next(s for s in added['sources'] if s['location'] == str(broken))
        self.assertEqual(len(added['games']), 2)
        broken.write_text('{bad')
        result = nx.refresh(target['id'])
        self.assertEqual(len(result['games']), 1)
        self.assertTrue(next(s for s in result['sources'] if s['id'] == target['id'])['error'])

    def test_online_catalog_checksums_and_no_local_references(self):
        self.catalog([{'bundle': 'game.nxnative.zip', 'name': 'My game'}])
        origin = self.serve()
        result = nx.add_source(origin + '/catalog.json')
        self.assertFalse(result['games'][0]['installable'])
        self.catalog([{'bundle': 'game.nxnative.zip', 'sha256': 'a' * 64}])
        self.assertTrue(nx.refresh()['games'][0]['installable'])
        self.catalog([{'path': 'file:///private/user-file'}])
        self.assertTrue(nx.refresh()['sources'][0]['error'])
        with self.assertRaises(nx.NxNativeError):
            nx.add_source('https://user:password@example.invalid/catalog.json')

    def test_bundle_roundtrip_and_local_prepared_build(self):
        output = self.bundle()
        unpack = self.root / 'unpack'
        unpack.mkdir()
        meta, host, files = nx._unpack(output, unpack)
        self.assertEqual(meta['title_id'], TITLE)
        self.assertEqual(nx.frame_android.apk_info(host)['package'], PACKAGE)
        self.assertIn('romfs/textures/some long name.bin', [n for n, _, _, _ in files])
        source = nx.add_source(str(self.root / 'build'))
        self.assertTrue(source['games'][0]['installable'])
        with self.assertRaisesRegex(nx.NxNativeError, 'already exists'):
            nx.export_bundle(self.root / 'build', output, TITLE, 'My game')

    def test_two_module_game_exports_and_imports_without_dread_subsdk(self):
        build = self.build(modules=('main', 'sdk'))
        output = self.root / 'two-modules.nxnative.zip'
        nx.export_bundle(build, output, TITLE, 'Two module game')
        unpack = self.root / 'unpack'
        unpack.mkdir()
        _, _, files = nx._unpack(output, unpack)
        modules = {name for name, *_ in files if name.startswith('dm/')}
        self.assertEqual(modules, {'dm/main.patched.bin', 'dm/main.fixups.tsv',
                                   'dm/sdk.patched.bin', 'dm/sdk.fixups.tsv'})

    def test_each_present_module_requires_both_code_and_fixups(self):
        build = self.build()
        original = {p.name: p.read_bytes() for p in (build / 'patched_android').iterdir()}
        for missing in ('main.patched.bin', 'sdk.fixups.tsv', 'subsdk0.patched.bin', 'subsdk0.fixups.tsv'):
            with self.subTest(missing=missing):
                path = build / 'patched_android' / missing
                path.unlink()
                with self.assertRaisesRegex(ValueError, 'incomplete modules'):
                    nx._helper().source_files(build)
                path.write_bytes(original[missing])

    def rewrite(self, original, transform=None, extra=None):
        output = self.root / 'tampered.nxnative.zip'
        with zipfile.ZipFile(original) as src, zipfile.ZipFile(output, 'w') as dst:
            for item in src.infolist():
                data = src.read(item)
                if transform:
                    data = transform(item.filename, data)
                dst.writestr(item, data)
            if extra:
                dst.writestr(*extra)
        return output

    def test_corrupt_payload_and_unsafe_extra_paths_fail_before_install(self):
        original = self.bundle()
        corrupt = self.rewrite(original, lambda name, data: b'changed' if name.endswith('main.patched.bin') else data)
        for path in (corrupt, self.rewrite(original, extra=('../escape', b'no'))):
            with self.subTest(path=path):
                p = self.catalog([{'bundle': str(path)}])
                result = nx.add_source(str(p))
                entry = result['games'][0]
                with patch.object(nx.frame_android, 'install') as install:
                    with self.assertRaises(nx.NxNativeError):
                        nx.install(entry['source_id'], entry['id'])
                    install.assert_not_called()
        self.assertFalse((self.root / 'escape').exists())

    def test_duplicate_and_symlink_members_are_rejected(self):
        original = self.bundle()
        duplicated = self.rewrite(original, extra=('DATA/dm/main.patched.bin', b'no'))
        out = self.root / 'out'
        out.mkdir()
        with self.assertRaises(nx.NxNativeError):
            nx._unpack(duplicated, out)
        link = zipfile.ZipInfo('data/romfs/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        modified = self.rewrite(original, extra=(link, '../somewhere'))
        with self.assertRaises(nx.NxNativeError):
            nx._unpack(modified, out)

    def test_online_hash_mismatch_does_not_install(self):
        self.bundle()
        self.catalog([{'bundle': 'game.nxnative.zip', 'sha256': '0' * 64}])
        origin = self.serve()
        result = nx.add_source(origin + '/catalog.json')
        entry = result['games'][0]
        with patch.object(nx.frame_android, 'install') as install:
            with self.assertRaisesRegex(nx.NxNativeError, 'checksum'):
                nx.install(entry['source_id'], entry['id'])
            install.assert_not_called()
        self.assertEqual(list(self.cache.glob('.download-*')), [])

    def test_online_bundle_installs_only_after_content_and_apk_identity_validation(self):
        bundle = self.bundle()
        self.catalog([{'bundle': 'game.nxnative.zip', 'sha256': nx._hash(bundle), 'title_id': TITLE, 'name': 'My game'}])
        origin = self.serve()
        result = nx.add_source(origin + '/catalog.json')
        entry = result['games'][0]
        order = []
        def host(path, **kwargs):
            order.append('host')
            self.assertEqual(nx.frame_android.apk_info(path)['package'], PACKAGE)
            self.assertTrue(kwargs['flatscreen'])
            return {'instance': 123}
        def stage(title, files, meta, report):
            order.append('data')
            self.assertEqual(title, TITLE)
            self.assertEqual(len(files), 11)
            self.assertTrue(all(nx._hash(path) == digest for _, path, _, digest in files))
            return 'dataset'
        with patch.object(nx.frame_android, 'install', side_effect=host), patch.object(nx, '_stage', side_effect=stage):
            installed = nx.install(entry['source_id'], entry['id'])
        self.assertEqual(order, ['host', 'data'])
        self.assertEqual(installed['package'], PACKAGE)
        self.assertEqual(installed['dataset'], 'dataset')

    def test_low_disk_space_fails_before_creating_export(self):
        build = self.build()
        output = self.root / 'no-space.nxnative.zip'
        with patch.object(nx.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100, 100, 0)):
            with self.assertRaisesRegex(nx.NxNativeError, 'free space'):
                nx.export_bundle(build, output, TITLE, 'My game')
        self.assertFalse(output.exists())

    def test_title_mismatch_prevents_device_mutation(self):
        original = self.bundle()
        modified = self.rewrite(original, lambda name, data: json.dumps(dict(json.loads(data), title_id='0000000000000001')).encode() if name == 'nxnative.json' else data)
        result = nx.add_source(str(self.catalog([{'bundle': str(modified)}])))
        entry = result['games'][0]
        with patch.object(nx.frame_android, 'install') as install:
            with self.assertRaisesRegex(nx.NxNativeError, 'does not match'):
                nx.install(entry['source_id'], entry['id'])
            install.assert_not_called()

    def test_staging_uses_selected_headset_and_stops_game_before_publishing(self):
        build = self.build()
        files = nx._helper().source_files(build)
        helper = nx._helper()
        calls = []
        def ssh(command, **kwargs):
            calls.append(command)
            return ''
        with patch.object(nx.frame_android, 'FRAME', 'selected-headset'), \
                patch.object(nx.frame_android, 'SSH_OPTS', ['-o', 'HostKeyAlias=selected-key']), \
                patch.object(nx.frame_android, 'stop') as stop, patch.object(nx.frame_android, 'launch') as launch, \
                patch.object(nx.frame_android, 'ssh', side_effect=ssh), patch.object(nx, '_helper', return_value=helper), \
                patch.object(helper, 'send_archive') as send:
            digest = nx._stage(TITLE, files, {'instance': 123}, lambda *a: None)
        stop.assert_called_once_with(PACKAGE)
        launch.assert_called_once_with(PACKAGE)
        self.assertIn('getprop sys.boot_completed', calls[0])
        self.assertIn('test -d /sdcard/Android', calls[0])
        self.assertIn('pm path ' + PACKAGE, calls[0])
        self.assertIn('am force-stop', calls[1])
        self.assertEqual(send.call_args.args[0], ['ssh', '-o', 'HostKeyAlias=selected-key', 'selected-headset'])
        self.assertIn('lepton-steamlaunch-123', send.call_args.args[1])
        self.assertIn(digest, send.call_args.args[1])
        self.assertIn('am start', calls[-1])

    def test_staging_waits_for_android_storage_before_sending_data(self):
        helper = nx._helper()
        boot_checks = []
        def ssh(command, **kwargs):
            if 'getprop sys.boot_completed' in command:
                boot_checks.append(command)
                if len(boot_checks) < 3:
                    raise nx.frame_android.FrameError('Android storage is not mounted yet')
            return ''
        with patch.object(nx.frame_android, 'stop'), patch.object(nx.frame_android, 'launch'), \
                patch.object(nx.frame_android, 'ssh', side_effect=ssh), \
                patch.object(nx.time, 'sleep'), patch.object(nx, '_helper', return_value=helper), \
                patch.object(helper, 'send_archive') as send:
            nx._stage(TITLE, [], {'instance': 123}, lambda *a: None)
        self.assertEqual(len(boot_checks), 3)
        self.assertIn('test -d /sdcard/Android', boot_checks[-1])
        self.assertIn('pm path ' + PACKAGE, boot_checks[-1])
        send.assert_called_once()

    def test_android_boot_failure_never_publishes_data(self):
        helper = nx._helper()
        with patch.object(nx.frame_android, 'stop'), patch.object(nx.frame_android, 'launch'), \
                patch.object(nx.frame_android, 'ssh', side_effect=nx.frame_android.FrameError('not ready')), \
                patch.object(nx.time, 'sleep'), patch.object(nx, '_helper', return_value=helper), \
                patch.object(helper, 'send_archive') as send:
            with self.assertRaisesRegex(nx.NxNativeError, 'did not start'):
                nx._stage(TITLE, [], {'instance': 123}, lambda *a: None)
        send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
