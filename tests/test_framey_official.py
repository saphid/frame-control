"""Pinned official Decky bundles remain valid Framey panel inputs."""
import sandbox  # noqa: F401
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_decky_store
import framey_panel
from framey_official import LEGACY_PLUGINS, PLUGINS, archive


class OfficialBundles(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_game_sync_sidebar_separators_do_not_open_blank_pages(self):
        plugin = next(p for p in PLUGINS if p['id'] == 104)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        navigation = re.search(r'class SyncTargetConfigPage extends RoutePage \{[\s\S]*?'
                               r'(?=\nconst syncTargetConfigPage)', frontend)
        self.assertIsNotNone(navigation)
        self.assertIn('"separator"', navigation.group())
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_sidebar.mjs')],
                                input=navigation.group(), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_emuchievements_old_settings_keep_values_through_tree_lookup(self):
        plugin = next(p for p in PLUGINS if p['id'] == 28)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        settings = re.search(r'  const CONFIG_VERSION = "1\.1\.0";[\s\S]*?(?=\n  class EmuchievementsState)', frontend)
        self.assertIsNotNone(settings)
        self.assertIn('deckyFrontendLib.findInTree(config', settings.group())
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_settings_tree.mjs')],
                                input=settings.group(), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_radiyo_text_dialog_can_submit_through_modal_root(self):
        plugin = next(p for p in PLUGINS if p['id'] == 24)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        component = re.search(r'const TextFieldModal = \(\{ closeModal, onClosed, label, placeholder \}\) => \{'
                              r'[\s\S]*?\n  \};', frontend)
        self.assertIsNotNone(component)
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_modal_root.mjs')],
                                input=component.group(), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_wine_cellar_search_preserves_its_accessible_name(self):
        plugin = next(p for p in PLUGINS if p['id'] == 68)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        control = re.search(r'window\.SP_REACT\.createElement\(DFL\.TextField, '
                            r'\{ "aria-label": "Search installed Steam games[^\n]+? \}\)', frontend)
        self.assertIsNotNone(control)
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_textfield_label.mjs')],
                                input=control.group(), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_wine_cellar_dropdown_waits_for_published_option_loader(self):
        plugin = next(p for p in PLUGINS if p['id'] == 68)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        callback = re.search(r'const openToolMenu = SP_REACT\.useCallback\([\s\S]+?\}, \[toolOptions\]\);', frontend)
        self.assertIsNotNone(callback)
        self.assertIn('void openToolMenu(application, showMenu);', frontend)
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_dropdown_load.mjs')],
                                input=json.dumps({'callback': callback.group()}),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_game_sync_text_dialog_commits_the_edited_value_on_blur(self):
        plugin = next(p for p in PLUGINS if p['id'] == 104)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle, tempfile.TemporaryDirectory() as root:
            frontend = Path(root) / 'index.js'
            frontend.write_bytes(bundle.read(plugin['folder'] + '/dist/index.js'))
            result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_textfield.mjs'), str(frontend)],
                                    capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_pause_games_toggle_renders_saved_value_and_dispatches_settings_only(self):
        plugin = next(p for p in PLUGINS if p['id'] == 13)
        with zipfile.ZipFile(io.BytesIO(archive(plugin))) as bundle, tempfile.TemporaryDirectory() as root:
            frontend = Path(root)/'index.js'
            frontend.write_bytes(bundle.read(plugin['folder']+'/dist/index.js'))
            result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_toggle.mjs'), str(frontend)],
                                    capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_css_loader_store_archive_has_unversioned_frontend(self):
        plugin = LEGACY_PLUGINS[0]
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']), plugin['folder'])
        with tempfile.TemporaryDirectory() as root, zipfile.ZipFile(io.BytesIO(data)) as bundle:
            manifest = json.loads(bundle.read(plugin['folder'] + '/plugin.json'))
            self.assertNotIn('api_version', manifest)
            frontend = bundle.read(plugin['folder'] + '/dist/index.js')
            self.assertIn(b'deckyFrontendLib.definePlugin', frontend)
            bundle.extractall(root)
            folder = Path(root) / plugin['folder']
            (folder / '.frame-control-store.json').write_text(json.dumps({
                'storeId': plugin['id'], 'sha256': plugin['sha256']}))
            with patch.object(framey_panel, 'PLUGINS', Path(root)):
                page = framey_panel.panel(plugin['id']).decode()
            encoded = re.search(r'<script id="framey-bundle" type="application/json">([^<]+)</script>', page)
            self.assertIsNotNone(encoded)
            self.assertEqual(base64.b64decode(encoded.group(1)), frontend)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_bluetooth_initial_panel_uses_safe_token_fallback(self):
        with zipfile.ZipFile(io.BytesIO(archive(next(p for p in PLUGINS if p['id'] == 18)))) as bundle:
            with tempfile.TemporaryDirectory() as folder:
                frontend = Path(folder) / 'index.js'
                frontend.write_bytes(bundle.read('Bluetooth/dist/index.js'))
                script = Path(__file__).parent / 'page/framey_bluetooth.mjs'
                result = subprocess.run(['node', str(script), str(frontend)],
                                        capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_hltb_frontend_starts_with_framey_module_stub(self):
        script = Path(__file__).parent / 'page/framey_hltb.mjs'
        result = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pinned_store_archives_install_and_pack_into_framey_panel(self):
        with tempfile.TemporaryDirectory() as root:
            plugins = Path(root)
            for plugin in PLUGINS:
                with self.subTest(plugin=plugin['name']):
                    data = archive(plugin)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
                    self.assertEqual(frame_decky_store.archive_info(data, plugin['sha256'], plugin['name']),
                                     plugin['folder'])
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        manifest = json.loads(z.read(plugin['folder'] + '/plugin.json'))
                        self.assertEqual(manifest.get('api_version', 'legacy'), plugin['api_version'])
                        z.extractall(plugins)
                    folder = plugins / plugin['folder']
                    (folder / '.frame-control-store.json').write_text(json.dumps({
                        'storeId': plugin['id'], 'sha256': plugin['sha256']}))
                    if plugin['id'] in (60, 67, 114, 130):
                        # This renderer fixture extracts the original root ZIP.
                        # Transaction and Decky tests cover managed adaptation;
                        # an unadapted root copy must fail here.
                        with patch.object(framey_panel, 'PLUGINS', plugins), self.assertRaises(FileNotFoundError):
                            framey_panel.panel(plugin['id'])
                        manifest['flags'] = []
                        (folder/'plugin.json').write_text(json.dumps(manifest))
                    with patch.object(framey_panel, 'PLUGINS', plugins):
                        page = framey_panel.panel(plugin['id']).decode()
                    encoded = re.search(r'<script id="framey-bundle" type="application/json"[^>]*>([^<]+)</script>', page)
                    self.assertIsNotNone(encoded)
                    self.assertEqual(base64.b64decode(encoded.group(1)), (folder / 'dist/index.js').read_bytes())
                    if plugin['id'] == 135:
                        self.assertIn(f'data-module="/framey/module/135/{plugin["sha256"]}/index.js"', page)
                        with patch.object(framey_panel, 'PLUGINS', plugins):
                            self.assertEqual(framey_panel.local_module(135, plugin['sha256'], 'chunks/pluginApi-B8sV7970.js'),
                                             (folder/'dist/chunks/pluginApi-B8sV7970.js').read_bytes())


    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the official frontend check')
    def test_tabmaster_published_list_reorders_only_on_save(self):
        plugin = next(p for p in PLUGINS if p['id'] == 61)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        control = re.search(r'window\.SP_REACT\.createElement\(DFL\.ReorderableList, '
                            r'\{ entries: entries, interactables: TabEntryInteractables, '
                            r'onSave: \(entries\) => \{[\s\S]*?\} \}\)', frontend)
        self.assertIsNotNone(control)
        self.assertIn('tabMasterManager.reorderTabs(entries.map(entry => entry.data.id))', control.group())
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_reorderable.mjs')],
                                input=control.group(), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
