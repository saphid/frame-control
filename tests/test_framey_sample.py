"""The author example stores settings as a normal Decky user plugin."""
import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/framey-settings/main.py'


def backend(settings_dir):
    decky = types.ModuleType('decky')
    decky.DECKY_PLUGIN_SETTINGS_DIR = settings_dir
    spec = importlib.util.spec_from_file_location('framey_sample', EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'decky': decky}):
        spec.loader.exec_module(module)
    return module.Plugin()


class SamplePlugin(unittest.TestCase):
    def test_frontend_bundle_loads_in_framey_host(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_sample.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setting_survives_backend_instance_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            first = backend(folder)
            self.assertFalse(asyncio.run(first.get_setting('enabled', False)))
            self.assertTrue(asyncio.run(first.set_setting('enabled', True)))
            second = backend(folder)
            self.assertTrue(asyncio.run(second.get_setting('enabled', False)))
            self.assertEqual(json.loads((Path(folder) / 'settings.json').read_text()),
                             {'schema': 1, 'enabled': True})

    def test_backend_rejects_unknown_keys_and_non_boolean_values(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = backend(folder)
            with self.assertRaises(ValueError): asyncio.run(plugin.get_setting('other'))
            with self.assertRaises(ValueError): asyncio.run(plugin.set_setting('enabled', 'yes'))
            self.assertFalse((Path(folder) / 'settings.json').exists())

    def test_corrupt_or_old_setting_uses_default_and_can_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = backend(folder)
            path = Path(folder) / 'settings.json'
            for data in ('broken JSON', '[]', '{"enabled": "yes"}'):
                with self.subTest(data=data):
                    path.write_text(data)
                    self.assertFalse(asyncio.run(plugin.get_setting('enabled', False)))
                    self.assertTrue(asyncio.run(plugin.get_setting('enabled', True)))
            self.assertTrue(asyncio.run(plugin.set_setting('enabled', True)))
            self.assertTrue(asyncio.run(backend(folder).get_setting('enabled', False)))

    def test_legacy_boolean_survives_restart_and_migrates_on_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text('{"enabled": true}\n')
            self.assertTrue(asyncio.run(backend(folder).get_setting('enabled', False)))
            self.assertEqual(json.loads(path.read_text()), {'enabled': True},
                             'Reading must not rewrite a user setting')
            self.assertTrue(asyncio.run(backend(folder).set_setting('enabled', False)))
            self.assertEqual(json.loads(path.read_text()), {'schema': 1, 'enabled': False})
            self.assertFalse(asyncio.run(backend(folder).get_setting('enabled', True)))

    def test_newer_schema_is_preserved_on_read_and_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            original = '{"schema": 2, "enabled": true, "future": "keep"}\n'
            path.write_text(original)
            plugin = backend(folder)
            with self.assertRaisesRegex(ValueError, 'unsupported sample version'):
                asyncio.run(plugin.get_setting('enabled', False))
            with self.assertRaisesRegex(ValueError, 'unsupported sample version'):
                asyncio.run(plugin.set_setting('enabled', False))
            self.assertEqual(path.read_text(), original)
            self.assertEqual(list(Path(folder).glob('.settings-*')), [])

    def test_failed_atomic_replace_keeps_previous_setting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            plugin = backend(folder)
            self.assertTrue(asyncio.run(plugin.set_setting('enabled', True)))
            previous = path.read_bytes()
            with patch('os.replace', side_effect=OSError('storage unavailable')):
                with self.assertRaisesRegex(OSError, 'storage unavailable'):
                    asyncio.run(plugin.set_setting('enabled', False))
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(Path(folder).glob('.settings-*')), [])
            self.assertTrue(asyncio.run(backend(folder).get_setting('enabled', False)))


if __name__ == '__main__':
    unittest.main()
