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
from framey_official import PLUGINS, archive


class OfficialBundles(unittest.TestCase):
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
                        self.assertEqual(manifest['api_version'], plugin['api_version'])
                        z.extractall(plugins)
                    folder = plugins / plugin['folder']
                    (folder / '.frame-control-store.json').write_text(json.dumps({'storeId': plugin['id']}))
                    with patch.object(framey_panel, 'PLUGINS', plugins):
                        page = framey_panel.panel(plugin['id']).decode()
                    encoded = re.search(r'<script id="framey-bundle" type="application/json">([^<]+)</script>', page)
                    self.assertIsNotNone(encoded)
                    self.assertEqual(base64.b64decode(encoded.group(1)), (folder / 'dist/index.js').read_bytes())


if __name__ == '__main__':
    unittest.main()
