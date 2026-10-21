"""Local Android bundles and companion files, using synthetic APK/OBB payloads."""
import sandbox  # noqa: F401
import io
from pathlib import Path
import sys
import tempfile
import unittest
import threading
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_android_import as imports
from test_quest import apk_bytes, PKG
import server
from test_install_queue import wait


class AndroidImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def file(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def bundle(self, name, files):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            for entry, data in files.items():
                archive.writestr(entry, data)
        return self.file(name, buf.getvalue())

    def prepare(self, paths):
        work = Path(tempfile.mkdtemp(dir=self.root))
        return imports.prepare(paths, work)

    def test_xapk_keeps_apk_obb_and_external_data_together(self):
        obb = 'main.7.' + PKG + '.obb'
        path = self.bundle('game.xapk', {
            'game.apk': apk_bytes(version_code=7), 'manifest.json': b'{}', 'icon.png': b'png',
            'Android/obb/' + PKG + '/' + obb: b'owned assets',
            'Android/data/' + PKG + '/files/levels.pak': b'owned levels',
        })
        plan, = self.prepare([path])
        self.assertEqual(plan['package'], PKG)
        self.assertEqual(plan['obb'][0].name, obb)
        self.assertEqual((plan['data'] / 'files/levels.pak').read_bytes(), b'owned levels')
        self.assertEqual(plan['checked']['version_code'], 7)

    def test_wrapped_archives_and_package_obb_folders(self):
        obb = 'main.7.' + PKG + '.obb'
        for prefix in ('', 'Game/'):
            for folder in ('', PKG + '/', 'Android/obb/' + PKG + '/'):
                with self.subTest(prefix=prefix, folder=folder):
                    path = self.bundle('game.zip', {
                        prefix + 'base.apk': apk_bytes(version_code=7),
                        prefix + folder + obb: b'assets',
                        prefix + 'Android/data/' + PKG + '/files/setup.sh': b'opaque data',
                    })
                    self.assertTrue(imports.is_bundle(path))
                    plan, = self.prepare([path])
                    self.assertEqual(plan['obb'][0].name, obb)
                    self.assertEqual((plan['data'] / 'files/setup.sh').read_bytes(), b'opaque data')

    def test_finder_and_sai_metadata_do_not_become_payloads(self):
        path = self.bundle('game.apks', {
            'Game/base.apk': apk_bytes(version_code=7),
            'Game/meta.sai_v2.json': b'{}', 'Game/meta.sai_v1.json': b'{}',
            'Game/icon.png': b'icon', 'Game/.DS_Store': b'finder',
            '__MACOSX/Game/._base.apk': b'not an APK',
            'Game/._base.apk': b'inline AppleDouble',
            'Game/Android/data/' + PKG + '/files/.DS_Store': b'finder',
            'Game/Android/data/' + PKG + '/files/._level': b'inline AppleDouble',
            'Game/Android/data/' + PKG + '/files/level': b'data',
        })
        self.assertTrue(imports.is_bundle(path))
        plan, = self.prepare([path])
        self.assertEqual([p.name for p in plan['data'].rglob('*') if p.is_file()], ['level'])
        self.assertFalse(imports.is_bundle(self.bundle('metadata.zip', {
            '__MACOSX/._base.apk': b'finder', '._base.apk': b'finder', '.DS_Store': b'finder'})))
        self.assertFalse(imports.is_bundle(self.bundle('pc-with-metadata.zip', {
            'Game/game': b'\x7fELF binary', '__MACOSX/._base.apk': b'finder'})))

    def test_ignored_metadata_still_obeys_archive_safety_and_budget(self):
        for name in ('__MACOSX/../escape.apk', '__MACOSX/CON', 'Game/../.DS_Store', 'Game/../._base.apk'):
            with self.subTest(name=name), self.assertRaises(imports.android.FrameError):
                self.prepare([self.bundle('bad.zip', {'base.apk': apk_bytes(), name: b'x'})])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            archive.writestr('base.apk', apk_bytes())
            member = zipfile.ZipInfo('__MACOSX/._base.apk')
            member.external_attr = 0o120777 << 16
            archive.writestr(member, b'/etc/passwd')
        with self.assertRaises(imports.android.FrameError):
            self.prepare([self.file('link.zip', buf.getvalue())])
        path = self.bundle('large.zip', {'base.apk': apk_bytes(), '.DS_Store': b'x' * 4096})
        with patch.object(imports, 'MAX_BYTES', 2048), self.assertRaises(imports.android.FrameError):
            self.prepare([path])
        path = self.bundle('large-sidecar.zip', {'base.apk': apk_bytes(), '._base.apk': b'x' * 4096})
        with patch.object(imports, 'MAX_BYTES', 2048), self.assertRaises(imports.android.FrameError):
            self.prepare([path])

    def test_apks_apkm_zip_and_loose_splits_use_manifest_not_filename_order(self):
        for extension in ('apks', 'apkm', 'zip'):
            with self.subTest(extension=extension):
                path = self.bundle('game.' + extension, {
                    'splits/aaa.apk': apk_bytes(split='config.arm64_v8a', version_code=7,
                                                files={'lib/arm64-v8a/libgame.so': b'native'}),
                    'splits/zzz.apk': apk_bytes(split_required=True, version_code=7), 'toc.pb': b'metadata'})
                plan, = self.prepare([path])
                self.assertEqual(plan['base'].name, 'zzz.apk')
                self.assertEqual(len(plan['splits']), 1)
        base = self.file('base.apk', apk_bytes(version_code=7))
        split = self.file('split.apk', apk_bytes(split='assets', version_code=7, files={'assets/a': b'a'}))
        plan, = self.prepare([split, base])
        self.assertEqual(plan['base'], base)

    def test_resource_code_and_mismatched_version_splits_fail_before_install(self):
        base = self.file('base.apk', apk_bytes(version_code=7))
        for version, files in ((8, {'assets/a': b'a'}), (7, {'classes.dex': b'code'}),
                               (7, {'res/drawable/a.xml': b'resource'})):
            with self.subTest(version=version, files=files):
                split = self.file('split.apk', apk_bytes(split='config', version_code=version, files=files))
                with self.assertRaises(imports.android.FrameError):
                    self.prepare([base, split])

    def test_missing_or_multiple_bases_and_mismatched_obb_are_refused(self):
        for files in (
            {'split.apk': apk_bytes(split='config', version_code=7)},
            {'a.apk': apk_bytes(version_code=7), 'b.apk': apk_bytes(version_code=7)},
            {'a.apk': apk_bytes(version_code=7), 'main.7.org.other.game.obb': b'assets'},
        ):
            with self.subTest(files=list(files)):
                with self.assertRaises(imports.android.FrameError):
                    self.prepare([self.bundle('bad.xapk', files)])

    def test_traversal_duplicate_symlink_unknown_and_bomb_archives_are_refused(self):
        for entry in ('../escape.apk', '/escape.apk', 'Android/../escape.apk', 'a\\b.apk', 'extra.pak',
                      'CON.apk', 'Android/data/' + PKG + '/files/NUL'):
            with self.subTest(entry=entry):
                with self.assertRaises(imports.android.FrameError):
                    self.prepare([self.bundle('bad.xapk', {'base.apk': apk_bytes(version_code=7), entry: b'x'})])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            member = zipfile.ZipInfo('base.apk')
            member.create_system = 3
            member.external_attr = 0o120777 << 16
            z.writestr(member, b'/etc/passwd')
        with self.assertRaises(imports.android.FrameError):
            self.prepare([self.file('link.apks', buf.getvalue())])
        for duplicate in ('base.apk', 'BASE.APK'):
            with self.subTest(duplicate=duplicate):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w') as z:
                    z.writestr('base.apk', apk_bytes(version_code=7))
                    # Avoid zipfile's duplicate-name warning while testing exact duplicates too.
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore', UserWarning)
                        z.writestr(duplicate, apk_bytes(version_code=7))
                with self.assertRaisesRegex(imports.android.FrameError, 'duplicate paths'):
                    self.prepare([self.file('duplicate.apkm', buf.getvalue())])
        with patch.object(imports, 'MAX_BYTES', 16):
            with self.assertRaises(imports.android.FrameError):
                self.prepare([self.bundle('big.xapk', {'base.apk': b'x' * 100})])

    def test_loose_obb_is_associated_by_package_and_plain_pc_zip_is_not_android(self):
        name = 'main.7.' + PKG + '.obb'
        plan, = self.prepare([self.file(name, b'assets')])
        self.assertIsNone(plan['base'])
        self.assertEqual(plan['package'], PKG)
        self.assertFalse(imports.is_bundle(self.bundle('pc.zip', {'game.exe': b'MZ'})))
        self.assertFalse(imports.is_bundle(self.bundle('mixed.zip', {'game.exe': b'MZ', 'android.apk': apk_bytes()})))
        self.assertFalse(imports.is_bundle(self.bundle('linux.zip', {'game': b'\x7fELF binary', 'android.apk': apk_bytes()})))
        self.assertTrue(imports.is_bundle(self.bundle('android.zip', {'base.apk': apk_bytes()})))
        self.assertTrue(imports.is_bundle(self.bundle('data.zip', {'base.apk': apk_bytes(),
            'Android/data/' + PKG + '/files/setup.sh': b'opaque game data'})))

    def test_required_splits_and_wrong_abi_return_actionable_errors(self):
        with self.assertRaisesRegex(imports.android.FrameError, 'requires splits'):
            self.prepare([self.file('base.apk', apk_bytes(version_code=7, split_required=True))])
        # Rebuild ZIP CRCs: only the binary manifest's attribute name is stripped.
        with zipfile.ZipFile(io.BytesIO(apk_bytes(version_code=7, split_required=True, resmap=True))) as z:
            manifest = z.read('AndroidManifest.xml').replace(
                'isSplitRequired'.encode('utf-16-le'), ('x' * len('isSplitRequired')).encode('utf-16-le'))
        with self.assertRaisesRegex(imports.android.FrameError, 'requires splits'):
            self.prepare([self.file('shrunk.apk', self._manifest_apk(manifest))])
        path = self.file('wrong.apk', apk_bytes(version_code=7, files={'lib/armeabi-v7a/libgame.so': b'arm32'}))
        with self.assertRaises(imports.android.FrameError) as failure:
            self.prepare([path])
        self.assertEqual(failure.exception.apk['package'], PKG)
        self.assertIn('no arm64-v8a build', failure.exception.apk['blocker'])

    def test_refused_apks_keep_install_reporting(self):
        unreadable = self.file('bad.apk', b'not an APK')
        with patch.object(imports.android, '_after_install') as report:
            with self.assertRaises(imports.android.FrameError):
                self.prepare([unreadable])
            self.assertIsNone(report.call_args.args[0])
            self.assertIsInstance(report.call_args.args[2], imports.android.FrameError)
        wrong = self.file('wrong.apk', apk_bytes(version_code=7, files={'lib/armeabi-v7a/lib.so': b'32bit'}))
        with patch.object(imports.android, '_after_install') as report:
            with self.assertRaises(imports.android.FrameError):
                self.prepare([wrong])
            self.assertEqual(report.call_args.args[0]['package'], PKG)
            self.assertIn('no arm64-v8a build', str(report.call_args.args[2]))

    def test_non_arm64_apk_error_matches_compatibility_report(self):
        for abi in ('x86_64', 'x86', 'armeabi-v7a'):
            with self.subTest(abi=abi):
                wrong = self.file('wrong.apk', apk_bytes(version_code=7, files={'lib/' + abi + '/lib.so': b'native'}))
                with patch.object(imports.android, '_after_install') as report:
                    with self.assertRaises(imports.android.FrameError) as failed:
                        self.prepare([wrong])
                message = str(failed.exception)
                self.assertIn('download the APK marked arm64-v8a', message)
                self.assertNotIn('older Quest games', message)
                self.assertEqual(str(report.call_args.args[2]), message)
                self.assertEqual(failed.exception.apk['blocker'], message)

    def test_single_apk_keeps_filename_and_can_replace_an_older_build(self):
        path = self.file('Older Game.apk', apk_bytes(version_code=7))
        meta = {'package': PKG, 'label': 'Game', 'version_code': 8, 'flatscreen': True}
        with patch.object(imports.android, 'read_meta', return_value=meta), \
                patch.object(imports.quest, '_running', return_value=False), \
                patch.object(imports.android, 'install', return_value=meta) as install:
            imports.import_files([path])
            self.assertEqual(install.call_args.kwargs['source'], 'Older Game.apk')
            bundle = self.bundle('older.zip', {'base.apk': apk_bytes(version_code=7),
                                               'main.7.' + PKG + '.obb': b'assets'})
            install.reset_mock()
            with self.assertRaisesRegex(imports.android.FrameError, 'older or unknown'):
                imports.import_files([bundle])
            install.assert_not_called()

    def _manifest_apk(self, manifest):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            archive.writestr('AndroidManifest.xml', manifest)
        return buf.getvalue()

    def test_asset_apk_in_android_data_is_copied_as_data_not_installed(self):
        path = self.bundle('game.xapk', {'base.apk': apk_bytes(version_code=7),
            'Android/data/' + PKG + '/files/extension.apk': b'opaque game data'})
        plan, = self.prepare([path])
        self.assertEqual((plan['data'] / 'files/extension.apk').read_bytes(), b'opaque game data')
        self.assertFalse(plan['splits'])

    def test_archive_import_reaches_real_split_merge_and_signer(self):
        path = self.bundle('game.apks', {
            'base.apk': apk_bytes(version_code=7, split_required=True),
            'config.apk': apk_bytes(split='config.arm64', version_code=7,
                                    files={'lib/arm64-v8a/libgame.so': b'arm64 payload'})})
        def installed(apk, info, package, flatscreen, name, source, artwork):
            with zipfile.ZipFile(apk) as merged:
                self.assertEqual(merged.read('lib/arm64-v8a/libgame.so'), b'arm64 payload')
                self.assertIn(b'APK Sig Block 42', Path(apk).read_bytes())
            return {'package': package, 'label': 'Game', 'version_code': 7, 'flatscreen': True}
        with patch.object(imports.quest, '_running', return_value=False), \
                patch.object(imports.android, 'read_meta', return_value=None), \
                patch.object(imports.android, '_install', side_effect=installed) as install, \
                patch.object(imports.android, '_after_install'):
            result = imports.import_files([path])
            self.assertFalse(result['needs_game_data'])
            install.assert_called_once()

    def test_two_step_bundle_import_reuses_existing_installer_and_data_copy(self):
        path = self.bundle('game.xapk', {'base.apk': apk_bytes(version_code=7),
                                       'main.7.' + PKG + '.obb': b'assets'})
        meta = {'package': PKG, 'label': 'Game', 'version': '7', 'version_code': 7,
                'instance': imports.android.instance_id(PKG), 'flatscreen': False}
        with patch.object(imports.quest, '_running', return_value=False), \
                patch.object(imports.android, 'read_meta', return_value=None), \
                patch.object(imports.android, 'install', return_value=meta) as install, \
                patch.object(imports.quest, 'add_game_data') as copy:
            result = imports.import_files([path], display='vr')
            self.assertTrue(result['needs_game_data'])
            self.assertIn('drop', result['message'])
            self.assertFalse(install.call_args.kwargs['flatscreen'])
            copy.assert_not_called()
        with patch.object(imports.quest, '_running', return_value=True), \
                patch.object(imports.android, 'read_meta', return_value=meta), \
                patch.object(imports.android, 'install') as install, \
                patch.object(imports.quest, 'add_game_data', return_value={
                    'message': 'Added data; game closed', 'app': meta}) as copy:
            result = imports.import_files([path])
            self.assertFalse(result['needs_game_data'])
            self.assertEqual(copy.call_args.args[0], PKG)
            self.assertEqual(copy.call_args.kwargs['source'], 'your files')
            install.assert_not_called()

    def test_data_only_requires_existing_install_and_mismatch_never_writes(self):
        path = self.file('main.7.' + PKG + '.obb', b'assets')
        with patch.object(imports.android, 'read_meta', return_value=None), \
                patch.object(imports.android, 'install') as install:
            with self.assertRaisesRegex(imports.android.FrameError, 'APK first'):
                imports.import_files([path])
            install.assert_not_called()
        path = self.bundle('game.xapk', {'base.apk': apk_bytes(version_code=7),
                                       'main.7.' + PKG + '.obb': b'assets'})
        meta = {'package': PKG, 'label': 'Game', 'version_code': 8, 'instance': imports.android.instance_id(PKG)}
        with patch.object(imports.android, 'read_meta', return_value=meta), \
                patch.object(imports.quest, '_running', return_value=True), \
                patch.object(imports.quest, 'add_game_data') as copy:
            with self.assertRaises(imports.android.FrameError):
                imports.import_files([path])
            copy.assert_not_called()


class StagedImports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(server._purge_android_uploads, float('inf'))
        self.master = patch.object(server, 'ensure_master').start()
        self.link = patch.object(server, 'LINK', None).start()
        self.addCleanup(patch.stopall)

    def stage(self, name='base.apk'):
        directory = Path(tempfile.mkdtemp(dir=self.tmp.name))
        path = directory / name
        path.write_bytes(apk_bytes(version_code=7))
        return server.stage_android_file(path, str(directory)), directory

    def test_one_use_tokens_pass_all_files_to_queued_import_and_clean_up(self):
        a, da = self.stage()
        b, db = self.stage('split.apk')
        with patch.object(imports, 'import_files', return_value={'message': 'ok'}) as run:
            job = server.android_import({'action': 'import', 'tokens': [a['token'], b['token']], 'display': 'flat'})
            self.assertEqual(wait(job['job'])['message'], 'ok')
            self.assertEqual(len(run.call_args.args[0]), 2)
            self.assertEqual(run.call_args.kwargs['display'], 'flat')
        # Queue completion publishes just before its cleanup callback.
        import time
        for _ in range(100):
            if not da.exists() and not db.exists():
                break
            time.sleep(.01)
        self.assertFalse(da.exists() or db.exists())
        with self.assertRaisesRegex(server.Failure, 'already used'):
            server.android_import({'action': 'import', 'tokens': [a['token']]})

    def test_remove_queued_import_cleans_its_uploads(self):
        release, started = threading.Event(), threading.Event()
        first = server.queue_job('Block', lambda: (started.set(), release.wait(5), {'message': 'ok'})[-1])
        self.addCleanup(release.set)
        self.assertTrue(started.wait(5))
        staged, directory = self.stage()
        job = server.android_import({'action': 'import', 'tokens': [staged['token']]})
        server.queue_action({'action': 'remove', 'job': job['job']})
        self.assertFalse(directory.exists())
        release.set()
        wait(first['job'])

    def test_headset_switch_and_bad_token_list_never_queue_an_import(self):
        selected = ['frame-a']
        with patch.object(server, 'LINK', SimpleNamespace(active_device=lambda: {'id': selected[0]})):
            staged, directory = self.stage()
            selected[0] = 'frame-b'
            with self.assertRaises(server.Failure) as error:
                server.android_import({'action': 'import', 'tokens': [staged['token']]})
            self.assertEqual(error.exception.status, 409)
            self.assertTrue(directory.exists())
            server.android_import({'action': 'discard', 'tokens': [staged['token']]})
            self.assertFalse(directory.exists())
            selected[0] = 'frame-a'
            staged, directory = self.stage()
            with self.assertRaises(server.Failure):
                server.android_import({'action': 'import', 'tokens': [staged['token'], staged['token']]})
            server.android_import({'action': 'discard', 'tokens': [staged['token']]})
            self.assertFalse(directory.exists())

    def test_zip_detection_routes_android_bundles_and_preserves_local_original(self):
        path = Path(self.tmp.name) / 'game.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('base.apk', apk_bytes(version_code=7))
        staged = server.stage_title(str(path))
        self.assertTrue(staged['android'])
        server.android_import({'action': 'discard', 'tokens': [staged['token']]})
        self.assertTrue(path.is_file())

    def test_expired_uploads_are_deleted(self):
        staged, directory = self.stage()
        server._purge_android_uploads(float('inf'))
        self.assertFalse(directory.exists())
        with self.assertRaisesRegex(server.Failure, 'expired'):
            server.android_import({'action': 'import', 'tokens': [staged['token']]})
