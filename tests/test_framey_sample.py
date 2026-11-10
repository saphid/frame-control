"""The author example stores settings as a normal Decky user plugin."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import stat
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
    def test_failed_file_flush_keeps_previous_or_absent_setting(self):
        for previous in (None, b'{"schema": 1, "enabled": true}\n'):
            with self.subTest(previous=previous), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'settings.json'
                if previous is not None:
                    path.write_bytes(previous)
                with patch('os.fsync', side_effect=OSError('file flush unavailable')):
                    with self.assertRaisesRegex(OSError, 'file flush unavailable'):
                        asyncio.run(backend(folder).set_setting('enabled', False))
                self.assertEqual(path.read_bytes() if path.exists() else None, previous)
                self.assertEqual(list(Path(folder).glob('.settings-*')), [])

    @unittest.skipUnless(hasattr(os, 'O_DIRECTORY'), 'Directory flush requires POSIX directory descriptors')
    def test_failed_directory_flush_reports_uncertain_save_and_fresh_read_reconciles(self):
        real_fsync = os.fsync

        def failed_directory_flush(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError('directory flush unavailable')
            return real_fsync(descriptor)

        with tempfile.TemporaryDirectory() as folder:
            plugin = backend(folder)
            self.assertTrue(asyncio.run(plugin.set_setting('enabled', True)))
            with patch('os.fsync', side_effect=failed_directory_flush):
                with self.assertRaisesRegex(OSError, 'directory flush unavailable'):
                    asyncio.run(plugin.set_setting('enabled', False))
            # Replacement already happened. A rejection must not be described
            # as a rollback; the frontend's existing reload guard reconciles it.
            self.assertFalse(asyncio.run(backend(folder).get_setting('enabled', True)))
            self.assertEqual(list(Path(folder).glob('.settings-*')), [])
            self.assertTrue(asyncio.run(plugin.set_setting('enabled', True)))

    def test_acknowledged_save_survives_backend_process_exit(self):
        code = '''
import asyncio, importlib.util, os, sys, types
decky = types.ModuleType('decky')
decky.DECKY_PLUGIN_SETTINGS_DIR = sys.argv[2]
sys.modules['decky'] = decky
spec = importlib.util.spec_from_file_location('sample_backend', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
saved = asyncio.run(module.Plugin().set_setting('enabled', True))
# Do not rely on interpreter shutdown to flush Python buffers.
os._exit(0 if saved is True else 2)
'''
        with tempfile.TemporaryDirectory() as folder:
            run = subprocess.run([sys.executable, '-c', code, str(EXAMPLE), folder],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(asyncio.run(backend(folder).get_setting('enabled', False)))
            self.assertEqual(list(Path(folder).glob('.settings-*')), [])

    def test_retired_settings_views_cannot_update_ui_or_issue_requests(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_sample_lifecycle.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_read_or_save_requires_reconciliation_before_another_write(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_sample_read_guard.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_unreadable_or_invalid_saved_settings_are_preserved_on_read_and_save(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = backend(folder)
            path = Path(folder) / 'settings.json'
            for data in (b'broken JSON', b'\xff', b'[]', b'null', b'"text"',
                         b'{"enabled": "yes"}', b'{"schema": 1, "enabled": null}',
                         b'{"schema": 1, "enabled": 1}'):
                with self.subTest(data=data):
                    path.write_bytes(data)
                    for fallback in (False, True):
                        with self.assertRaisesRegex(ValueError, 'repair or restore settings.json'):
                            asyncio.run(plugin.get_setting('enabled', fallback))
                    with self.assertRaisesRegex(ValueError, 'repair or restore settings.json'):
                        asyncio.run(plugin.set_setting('enabled', False))
                    self.assertEqual(path.read_bytes(), data)
                    self.assertEqual(list(Path(folder).glob('.settings-*')), [])
            # A deliberate repair can be re-read by a fresh backend instance.
            path.write_text('{"schema": 1, "enabled": true}\n')
            self.assertTrue(asyncio.run(backend(folder).get_setting('enabled', False)))
            self.assertTrue(asyncio.run(plugin.set_setting('enabled', False)))
            self.assertFalse(asyncio.run(backend(folder).get_setting('enabled', True)))

    def test_absent_or_valid_empty_settings_use_defaults_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = backend(folder)
            path = Path(folder) / 'settings.json'
            self.assertFalse(asyncio.run(plugin.get_setting('enabled', False)))
            self.assertTrue(asyncio.run(plugin.get_setting('enabled', True)))
            self.assertFalse(path.exists())
            for data in ('{}\n', '{"schema": 1}\n'):
                path.write_text(data)
                self.assertFalse(asyncio.run(plugin.get_setting('enabled', False)))
                self.assertTrue(asyncio.run(plugin.get_setting('enabled', True)))
                self.assertEqual(path.read_text(), data)
            self.assertTrue(asyncio.run(plugin.set_setting('enabled', True)))
            self.assertTrue(asyncio.run(backend(folder).get_setting('enabled', False)))

    def test_storage_read_error_never_overwrites_saved_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = backend(folder)
            path = Path(folder) / 'settings.json'
            saved = b'{"schema": 1, "enabled": true}\n'
            path.write_bytes(saved)
            with patch.object(Path, 'read_text', side_effect=PermissionError('storage denied')):
                with self.assertRaisesRegex(PermissionError, 'storage denied'):
                    asyncio.run(plugin.get_setting('enabled', False))
                with self.assertRaisesRegex(PermissionError, 'storage denied'):
                    asyncio.run(plugin.set_setting('enabled', False))
            self.assertEqual(path.read_bytes(), saved)
            self.assertEqual(list(Path(folder).glob('.settings-*')), [])

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
