"""Local APK/OBB backups: inspect as a unit, verify the target, and finish setup."""
import sandbox  # noqa: F401
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_android_import as backup
import server
from apk_fixtures import apk, manifest

PKG = 'com.Armature.VR4'
META = {'package': PKG, 'label': PKG, 'version': '', 'version_code': 210,
        'instance': 2800000001, 'shortcut': 123, 'game_id': 456}


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.apk = self.root / 'VR4-Android-Shipping-arm64.apk'
        self.apk.write_bytes(apk({'AndroidManifest.xml': manifest(PKG, 0x7f010000, 0x7f010001, 26)}))
        self.obb = [self.root / f'{kind}.203.{PKG}.obb' for kind in ('main', 'patch')]
        for p in self.obb:
            p.write_bytes(b'game data')

    def test_desktop_apk_finds_matching_siblings_but_browser_requires_selection(self):
        (self.root / 'main.1.org.other.game.obb').write_bytes(b'other game')
        with patch.object(backup.android, 'ssh') as ssh:
            desktop = backup.inspect([str(self.apk)], discover=True)
            browser = backup.inspect([str(self.apk)])
            selected = backup.inspect([str(self.apk), *map(str, self.obb)])
        ssh.assert_not_called()
        self.assertEqual(desktop['obb'], self.obb)
        self.assertEqual(browser['obb'], [])
        self.assertEqual(backup.public(selected)['obb'][0]['name'], self.obb[0].name)
        self.assertEqual(backup.public(selected)['package'], PKG)
        self.assertNotIn(str(self.root), str(backup.public(selected)))

    def test_wrong_data_empty_data_duplicate_names_and_multiple_apks_fail_before_install(self):
        other = self.root / 'main.203.org.other.game.obb'
        other.write_bytes(b'other game')
        with self.assertRaisesRegex(backup.android.FrameError, 'does not belong'):
            backup.inspect([str(self.apk), str(other)])
        self.obb[0].write_bytes(b'')
        with self.assertRaisesRegex(backup.android.FrameError, 'nonempty'):
            backup.inspect([str(self.apk), str(self.obb[0])])
        second = self.root / 'another.apk'
        second.write_bytes(self.apk.read_bytes())
        with self.assertRaisesRegex(backup.android.FrameError, 'one game at a time'):
            backup.inspect([str(self.apk), str(second)])
        self.obb[0].write_bytes(b'data')
        folder = self.root / 'copy'
        folder.mkdir()
        duplicate = folder / self.obb[0].name
        duplicate.write_bytes(b'data')
        with self.assertRaisesRegex(backup.android.FrameError, 'unique names'):
            backup.inspect([str(self.apk), str(self.obb[0]), str(duplicate)])

    def test_obb_only_repairs_existing_game_and_requests_apk_when_not_installed(self):
        with patch.object(backup.android, 'read_meta', return_value=None):
            with self.assertRaisesRegex(backup.android.FrameError, 'Add its APK'):
                backup.inspect(list(map(str, self.obb)))
        with patch.object(backup.android, 'read_meta', return_value=META):
            plan = backup.inspect(list(map(str, self.obb)))
        self.assertIsNone(plan['apk'])
        self.assertEqual(plan['checked']['version_code'], 210)

    def test_apk_and_both_data_files_install_launch_verify_copy_close_in_order(self):
        plan = backup.inspect([str(self.apk), *map(str, self.obb)])
        order = []
        def added(pkg, checked, files, *args, **kwargs):
            order.append('copy-close')
            self.assertEqual(pkg, PKG)
            self.assertEqual(files, self.obb)
            return {'closed': True, 'message': 'copied', 'app': META, 'needs_game_data': False}
        with patch.object(backup.quest, '_running', side_effect=[False, False, True]), \
                patch.object(backup.android, 'read_meta', return_value=None), \
                patch.object(backup.android, 'install', side_effect=lambda *a, **k: order.append('install') or META), \
                patch.object(backup.android, 'launch', side_effect=lambda *a: order.append('launch')), \
                patch.object(backup.quest, '_wait_ready', side_effect=lambda *a: order.append('ready')), \
                patch.object(backup.quest, '_check_android_package', side_effect=lambda *a: order.append('verify')), \
                patch.object(backup.quest, 'add_game_data', side_effect=added):
            result = backup.install(plan)
        self.assertEqual(order, ['install', 'launch', 'ready', 'verify', 'copy-close'])
        self.assertIn('2 game-data files', result['message'])
        self.assertIn('Ready to open', result['message'])

    def test_copy_failure_closes_game_and_keeps_retry_instruction(self):
        plan = backup.inspect([str(self.apk), *map(str, self.obb)])
        with patch.object(backup.quest, '_running', side_effect=[False, True]), \
                patch.object(backup.android, 'read_meta', return_value=None), \
                patch.object(backup.android, 'install', return_value=META), \
                patch.object(backup.quest, '_wait_ready'), patch.object(backup.quest, '_check_android_package'), \
                patch.object(backup.quest, 'add_game_data', side_effect=backup.android.FrameError('transfer failed')), \
                patch.object(backup.quest, '_close', return_value=(True, None)) as close:
            with self.assertRaisesRegex(backup.android.FrameError, 'installed, but.*Import the same backup again'):
                backup.install(plan)
        close.assert_called_once_with(PKG)

    def test_changed_files_are_rejected_before_frame_access(self):
        plan = backup.inspect([str(self.apk), *map(str, self.obb)])
        self.obb[0].write_bytes(b'changed contents')
        with patch.object(backup.android, 'ssh') as ssh:
            with self.assertRaisesRegex(backup.android.FrameError, 'backup changed'):
                backup.install(plan)
        ssh.assert_not_called()

    def test_running_game_and_newer_installed_version_are_not_replaced(self):
        plan = backup.inspect([str(self.apk), *map(str, self.obb)])
        newer = {**META, 'version_code': plan['checked']['version_code'] + 1}
        for running, existing, message in [(True, None, 'Close'), (False, newer, 'newer')]:
            with self.subTest(running=running), \
                    patch.object(backup.quest, '_running', return_value=running), \
                    patch.object(backup.android, 'read_meta', return_value=existing), \
                    patch.object(backup.android, 'install') as install:
                with self.assertRaisesRegex(backup.android.FrameError, message):
                    backup.install(plan)
                install.assert_not_called()

    def test_apk_without_data_installs_without_launching(self):
        plan = backup.inspect([str(self.apk)])
        with patch.object(backup.quest, '_running', return_value=False), \
                patch.object(backup.android, 'read_meta', return_value=None), \
                patch.object(backup.android, 'install', return_value=META), \
                patch.object(backup.android, 'launch') as launch:
            result = backup.install(plan)
        launch.assert_not_called()
        self.assertFalse(result['needs_game_data'])


class StagingTests(unittest.TestCase):
    setUp = BackupTests.setUp
    def tearDown(self):
        for entry in server._android_backups.values():
            server._discard_android_backup(entry)
        server._android_backups.clear()

    def test_uploaded_batch_is_inspected_together_and_cancel_removes_all_uploads(self):
        token = server.android_backup({'action': 'begin'})['token']
        for path in [self.apk, *self.obb]:
            class Request:
                headers = {'X-Filename': path.name, 'X-Mode': 'android-backup',
                           'X-Android-Backup': token, 'Content-Length': str(path.stat().st_size)}
                rfile = io.BytesIO(path.read_bytes())
            server.Handler.upload(Request())
        read = server.android_backup({'action': 'inspect', 'token': token})
        self.assertEqual(len(read['plan']['obb']), 2)
        folders = list(server._android_backups[token]['dirs'])
        server.android_backup({'action': 'discard', 'token': token})
        self.assertTrue(all(not Path(p).exists() for p in folders))
        self.assertTrue(self.apk.exists())

    def test_headset_change_refuses_import_and_pc_folder_is_left_to_title_importer(self):
        class Link:
            device = 'a'
            def active_device(self):
                return {'id': self.device}
        link = Link()
        with patch.object(server, 'LINK', link):
            read = server.android_backup({'action': 'inspect', 'paths': [str(self.apk)]})
            link.device = 'b'
            with self.assertRaisesRegex(server.Failure, 'headset changed'):
                server.android_backup({'action': 'install', 'token': read['token']})
        pc = self.root / 'pc'
        pc.mkdir()
        (pc / 'game.exe').write_bytes(b'program')
        self.assertEqual(server.android_backup({'action': 'inspect', 'paths': [str(pc)], 'probe': True}),
                         {'android': False})


if __name__ == '__main__':
    unittest.main()
