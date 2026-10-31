"""A compatibility claim must never transfer to a different published archive."""
import sandbox  # noqa: F401
import json
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import framey_compatibility as compatibility
import frame_decky_store
import frame_decky


class Compatibility(unittest.TestCase):
    def test_previous_deckyparty_receipt_requires_ipc_repair(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 117)
        old = dict(storeId=117, version=plugin['version'], sha256=plugin['sha256'],
                   compatShims=['deckyparty-user-lifecycle'])
        updated = dict(old, compatShims=['deckyparty-user-lifecycle', 'deckyparty-ipc-eof'])
        results = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertIn('Update or reinstall', results[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall', results[1]['compatibility']['reason'])
        self.assertEqual(results[1]['compatibility']['status'], 'partial')

    def test_table_matches_store_data_and_complete_browser_and_fake_evidence(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable, str(root/'scripts/framey-compatibility-doc.py'), '--check'], check=True)
        records = json.loads(compatibility.DATA.read_text())['plugins']
        self.assertEqual(len({p['id'] for p in records}), len(records))
        for record in records:
            self.assertEqual(record['browser']['id'], record['id'])
            self.assertEqual(record['fakeFrame']['sha256'], record['sha256'])
            self.assertIn(record['status'], ('works', 'partial', 'broken', 'na'))

    def test_claims_require_exact_id_version_and_digest(self):
        records = json.loads(compatibility.DATA.read_text())['plugins']
        for plugin in records:
            with self.subTest(plugin=plugin['name']):
                expected = compatibility.lookup(plugin['id'], plugin['sha256'], plugin['version'])
                self.assertEqual(expected['status'], plugin['status'])
                for plugin_id, digest, version in (
                    (plugin['id'], '0'*64, plugin['version']),
                    (plugin['id'], plugin['sha256'], plugin['version']+'-new'),
                    (99999, plugin['sha256'], plugin['version']),
                ):
                    result = compatibility.lookup(plugin_id, digest, version)
                    self.assertEqual(result['status'], 'unverified')
                    self.assertFalse(result['blockInstall'])

    def test_installed_receipt_uses_its_digest_not_current_store_version(self):
        record = json.loads(compatibility.DATA.read_text())['plugins'][0]
        installed = {'plugins': [{'storeId': record['id'], 'version': record['version'],
                                 'sha256': record['sha256']},
                                {'storeId': record['id'], 'version': record['version'], 'sha256': '0'*64}]}
        result = frame_decky.status(lambda *a, **k: json.dumps(installed))
        self.assertEqual(result['plugins'][0]['compatibility']['status'], record['status'])
        self.assertEqual(result['plugins'][1]['compatibility']['status'], 'unverified')

    def test_hardware_block_precedes_any_download_or_ssh_mutation(self):
        with patch.object(frame_decky, 'status', return_value={'managed': True, 'running': True, 'plugins': []}), \
             patch.object(frame_decky_store, 'catalog', return_value=[{'id': 42, 'name': 'Hardware only',
                 'sha256': 'a'*64, 'root': False, 'compatibility': {'blockInstall': True, 'reason': 'Not supported on Frame'}}]), \
             patch.object(frame_decky_store.urllib.request, 'urlopen') as download:
            def no_ssh(*a, **k):
                self.fail('must not mutate headset for known hardware blocker')
            with self.assertRaisesRegex(ValueError, 'Not supported on Frame'):
                frame_decky_store.change(no_ssh, 'install', 42)
            download.assert_not_called()

    def test_old_deckyspy_copy_does_not_inherit_fixed_install_status(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 89)
        installed = {'plugins': [dict(storeId=89, version=plugin['version'], sha256=plugin['sha256']),
                                  dict(storeId=89, version=plugin['version'], sha256=plugin['sha256'],
                                       compatShims=['deckyspy-psutil-and-battery'])]}
        result = frame_decky.status(lambda *a, **k: json.dumps(installed))['plugins']
        self.assertEqual(result[0]['compatibility']['status'], 'partial')
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertEqual(result[1]['compatibility']['status'], 'works')
        self.assertEqual(compatibility.lookup(89, plugin['sha256'], plugin['version'])['status'], 'works')

    def test_old_tabmaster_copy_requires_restore_and_ipc_fixes(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 61)
        old = dict(storeId=61, version=plugin['version'], sha256=plugin['sha256'])
        restore_only = dict(old, compatShims=['tabmaster-json-file-restore'])
        updated = dict(old, compatShims=['tabmaster-json-file-restore', 'tabmaster-ipc-eof'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, restore_only, updated]}))['plugins']
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial']*3)
        self.assertTrue(result[0]['compatibility']['reason'].startswith('Update or reinstall'))
        self.assertTrue(result[1]['compatibility']['reason'].startswith('Update or reinstall'))
        self.assertFalse(result[2]['compatibility']['reason'].startswith('Update or reinstall'))

    def test_old_prefix_manager_copy_requires_user_service_adaptation(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 130)
        old = dict(storeId=130, version=plugin['version'], sha256=plugin['sha256'])
        updated = dict(old, compatShims=['prefix-manager-user-paths'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertEqual([p['compatibility']['status'] for p in result], ['broken', 'partial'])
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])

    def test_unpublished_prefix_manager_102_has_no_store_compatibility_claim(self):
        from framey_official import PREFIX_MANAGER_102
        release = PREFIX_MANAGER_102
        result = compatibility.lookup(release['id'], release['sha256'], release['version'])
        self.assertEqual(result['status'], 'unverified')

    def test_steamback_old_receipt_requires_current_ipc_repair(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 46)
        base = dict(storeId=46, version=plugin['version'], sha256=plugin['sha256'])
        installed = {'plugins': [base, dict(base, compatShims=['steamback-ipc-eof'])]}
        result = frame_decky.status(lambda *a, **k: json.dumps(installed))['plugins']
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial'] * 2)
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall', result[1]['compatibility']['reason'])

    def test_free_loader_old_receipt_requires_current_ipc_repair(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 63)
        base = dict(storeId=63, version=plugin['version'], sha256=plugin['sha256'])
        installed = {'plugins': [base, dict(base, compatShims=['free-loader-ipc-eof'])]}
        result = frame_decky.status(lambda *a, **k: json.dumps(installed))['plugins']
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial'] * 2)
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall', result[1]['compatibility']['reason'])

    def test_old_simple_timer_copy_requires_current_ipc_reinstall(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 96)
        base = dict(storeId=96, version=plugin['version'], sha256=plugin['sha256'])
        installed = {'plugins': [base, dict(base, compatShims=['simple-timer-lifecycle']),
            dict(base, compatShims=['simple-timer-lifecycle', 'simple-timer-ipc-eof'])]}
        result = frame_decky.status(lambda *a, **k: json.dumps(installed))['plugins']
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial'] * 3)
        for old in result[:2]:
            self.assertIn('Update or reinstall', old['compatibility']['reason'])
        self.assertNotIn('Update or reinstall', result[2]['compatibility']['reason'])
        self.assertIn('worn VR unverified', result[2]['compatibility']['reason'])

    def test_fileserver_old_copy_requires_current_panel_update(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 60)
        old = dict(storeId=60, version=plugin['version'], sha256=plugin['sha256'],
                   compatShims=['deckyfileserver-user-native'])
        previous = dict(old, compatShims=['deckyfileserver-user-native', 'deckyfileserver-https-address'])
        updated = dict(old, compatShims=['deckyfileserver-user-native', 'deckyfileserver-https-address',
                                         'deckyfileserver-directory-entry'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, previous, updated]}))['plugins']
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertIn('Update or reinstall', result[1]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall this managed plugin', result[2]['compatibility']['reason'])
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial'] * 3)

    def test_suggestme_old_copy_exposes_tls_update_requirement(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 132)
        old = dict(storeId=132, version=plugin['version'], sha256=plugin['sha256'])
        updated = dict(old, compatShims=['suggestme-verified-tls'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertIn('may disable TLS verification', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall this managed plugin', result[1]['compatibility']['reason'])
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial', 'partial'])

    def test_deck_settings_old_copy_exposes_upload_tls_update_requirement(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 93)
        old = dict(storeId=93, version=plugin['version'], sha256=plugin['sha256'])
        updated = dict(old, compatShims=['deck-settings-verified-tls', 'deck-settings-ipc-eof'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertIn('certificate and hostname checks', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall this managed plugin', result[1]['compatibility']['reason'])
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial', 'partial'])

    def test_deck_settings_tls_only_receipt_still_needs_ipc_update(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 93)
        old = dict(storeId=93, version=plugin['version'], sha256=plugin['sha256'],
                   compatShims=['deck-settings-verified-tls'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old]}))['plugins'][0]
        self.assertEqual(result['compatibility']['status'], 'partial')
        self.assertIn('Update or reinstall', result['compatibility']['reason'])
        self.assertIn('IPC', result['compatibility']['reason'])

    def test_steam_status_old_copy_exposes_diagnostic_tls_update_requirement(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 123)
        old = dict(storeId=123, version=plugin['version'], sha256=plugin['sha256'])
        updated = dict(old, compatShims=['steam-status-verified-tls'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertIn('certificate and hostname verification', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall this managed plugin', result[1]['compatibility']['reason'])
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial', 'partial'])

    def test_notifications_old_copy_exposes_logging_update_requirement(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 79)
        old = dict(storeId=79, version=plugin['version'], sha256=plugin['sha256'])
        updated = dict(old, compatShims=['notifications-private-logs'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertIn('environment dump', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall this managed plugin', result[1]['compatibility']['reason'])
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial', 'partial'])

    def test_game_sync_old_copy_requires_selection_fix(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 104)
        old = dict(storeId=104, version=plugin['version'], sha256=plugin['sha256'])
        updated = dict(old, compatShims=['game-sync-bounded-selection'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall this managed plugin', result[1]['compatibility']['reason'])
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial', 'partial'])

    def test_shotty_previous_copy_requires_unload_repair(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 53)
        old = dict(storeId=53, version=plugin['version'], sha256=plugin['sha256'],
                   compatShims=['shotty-click-app-dir', 'shotty-bounded-copies'])
        updated = dict(old, compatShims=old['compatShims']+['shotty-ipc-eof'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertIn('Update or reinstall this managed plugin', result[0]['compatibility']['reason'])
        self.assertNotIn('Update or reinstall this managed plugin', result[1]['compatibility']['reason'])
        self.assertEqual([p['compatibility']['status'] for p in result], ['partial', 'partial'])

    def test_emuchievements_old_x86_helper_is_still_blocked(self):
        plugin = next(p for p in json.loads(compatibility.DATA.read_text())['plugins'] if p['id'] == 28)
        old = dict(storeId=28, version=plugin['version'], sha256=plugin['sha256'])
        updated = dict(old, compatShims=['emuchievements-safe-arm64'])
        result = frame_decky.status(lambda *a, **k: json.dumps({'plugins': [old, updated]}))['plugins']
        self.assertEqual([p['compatibility']['status'] for p in result], ['broken', 'partial'])
        self.assertIn('Update or reinstall', result[0]['compatibility']['reason'])

    def test_missing_audit_data_is_unverified(self):
        with patch.object(compatibility, 'DATA', Path('/nonexistent/framey-audit.json')):
            self.assertEqual(compatibility.lookup(12, 'a'*64, '1.0')['status'], 'unverified')
