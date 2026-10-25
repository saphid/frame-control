"""The author example stores settings as a normal Decky user plugin."""
import asyncio
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/framey-settings/main.py'


class SamplePlugin(unittest.TestCase):
    def test_frontend_bundle_loads_in_framey_host(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_sample.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setting_survives_backend_instance_restart(self):
        spec = importlib.util.spec_from_file_location('framey_sample', EXAMPLE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'DECKY_PLUGIN_SETTINGS_DIR': folder}):
            first = module.Plugin()
            self.assertFalse(asyncio.run(first.get_setting('enabled', False)))
            self.assertTrue(asyncio.run(first.set_setting('enabled', True)))
            second = module.Plugin()
            self.assertTrue(asyncio.run(second.get_setting('enabled', False)))
            self.assertTrue((Path(folder) / 'settings.json').is_file())

    def test_backend_rejects_unknown_keys_and_non_boolean_values(self):
        spec = importlib.util.spec_from_file_location('framey_sample', EXAMPLE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'DECKY_PLUGIN_SETTINGS_DIR': folder}):
            plugin = module.Plugin()
            with self.assertRaises(ValueError): asyncio.run(plugin.get_setting('other'))
            with self.assertRaises(ValueError): asyncio.run(plugin.set_setting('enabled', 'yes'))
            self.assertFalse((Path(folder) / 'settings.json').exists())


if __name__ == '__main__':
    unittest.main()
