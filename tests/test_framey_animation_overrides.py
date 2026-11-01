"""Exact managed archive with disposable movie overrides; no Steam or network."""
import sandbox  # noqa: F401
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import ssl
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

import framey_official
import test_frame_decky_store as transactions

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == 'nt', 'managed plugin and symlink transaction requires POSIX')
class AnimationOverrides(unittest.TestCase):
    def setUp(self):
        self.tx = transactions.StoreTransaction()
        self.tx.setUp()
        self.addCleanup(self.tx.doCleanups)
        self.pin = next(p for p in framey_official.PLUGINS if p['id'] == 23)
        self.data = framey_official.archive(self.pin)
        result = self.tx.apply('install', self.data, plugin_id=23,
                               folder=self.pin['folder'], version=self.pin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.folder = self.tx.folder.parent/self.pin['folder']
        temp = tempfile.TemporaryDirectory(prefix='framey-animation-')
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.movies = self.home/'movies'
        self.movies.mkdir()
        self.a = self.home/'a.webm'
        self.b = self.home/'b.webm'
        self.a.write_bytes(b'private selected A')
        self.b.write_bytes(b'private selected B')
        helper = types.ModuleType('framey_animation_overrides')
        exec(compile((self.folder/'py_modules/framey_animation_overrides.py').read_bytes(),
                     'managed-animation-helper.py', 'exec'), helper.__dict__)
        self.helper = helper
        self.module = types.ModuleType('private_animation')
        decky = types.SimpleNamespace(DECKY_PLUGIN_SETTINGS_DIR=str(self.home/'settings'),
            DECKY_PLUGIN_RUNTIME_DIR=str(self.home/'runtime'), logger=logging.getLogger('animation-fixture'))
        def blocked(*args, **kwargs):
            raise AssertionError('No network or migration allowed in this fixture')
        for name in ['migrate_logs', 'migrate_settings', 'migrate_any']:
            setattr(decky, name, blocked)
        stubs = {'decky_plugin': decky, 'framey_animation_overrides': helper,
                 'aiohttp': types.SimpleNamespace(ClientSession=blocked, TCPConnector=blocked),
                 'certifi': types.SimpleNamespace(where=lambda: ssl.get_default_verify_paths().cafile)}
        # Change only the HOME expansion for the private module's constant.
        with patch.dict(sys.modules, stubs), patch('os.path.expanduser',
                side_effect=lambda p: str(self.movies) if p.endswith('/uioverrides/movies') else p):
            exec(compile((self.folder/'main.py').read_bytes(), 'managed-animation.py', 'exec'), self.module.__dict__)
        self.module.config = dict(downloads=[], custom_animations=[
            dict(id='a', path=str(self.a)), dict(id='b', path=str(self.b))])
        self.video = helper.VIDEOS[0]
        self.target = self.movies/self.video
        self.backups = self.movies/'.frame-control-animation-backups'

    def apply(self, selection='a', video=None):
        return self.module.apply_animation(video or self.video, selection)

    def original(self, value=b'original override'):
        self.target.write_bytes(value)
        return self.helper.identity(self.target)

    def test_empty_default_preserves_all_three_existing_movies_without_state(self):
        expected = {}
        for video in self.helper.VIDEOS:
            path = self.movies/video
            path.write_bytes(('original '+video).encode())
            expected[video] = (path.read_bytes(), self.helper.identity(path))
            self.apply('', video)
        self.assertFalse(self.backups.exists())
        self.assertEqual(expected, {v: ((self.movies/v).read_bytes(), self.helper.identity(self.movies/v))
                                    for v in self.helper.VIDEOS})

    def test_empty_default_preserves_external_and_broken_symlinks(self):
        for source in [str(self.a), str(self.home/'missing')]:
            os.symlink(source, self.target)
            before = self.helper.identity(self.target)
            self.apply('')
            self.assertEqual(os.readlink(self.target), source)
            self.assertEqual(self.helper.identity(self.target), before)
            self.target.unlink()
        self.assertEqual(self.a.read_bytes(), b'private selected A')

    def test_apply_switch_repeat_and_clear_restore_exact_original_inode(self):
        before = self.original()
        for selected, source in [('a', self.a), ('a', self.a), ('b', self.b)]:
            self.apply(selected)
            self.assertEqual(os.readlink(self.target), str(source))
            backup = self.backups/self.video/'original'
            self.assertEqual(backup.read_bytes(), b'original override')
            self.assertEqual(self.helper.identity(backup), before)
        self.apply('')
        self.assertFalse(self.target.is_symlink())
        self.assertEqual(self.target.read_bytes(), b'original override')
        self.assertEqual(self.helper.identity(self.target), before)
        self.apply('')
        self.assertEqual(self.target.read_bytes(), b'original override')

    def test_clear_without_prior_movie_removes_only_owned_link(self):
        self.apply()
        self.apply('')
        self.assertFalse(os.path.lexists(self.target))
        self.assertEqual(self.a.read_bytes(), b'private selected A')

    def test_broken_prior_link_restored_verbatim(self):
        link = '../missing-original.webm'
        os.symlink(link, self.target)
        before = self.helper.identity(self.target)
        self.apply()
        self.apply('')
        self.assertEqual(os.readlink(self.target), link)
        self.assertEqual(self.helper.identity(self.target), before)

    def test_recreated_helper_uses_persistent_ownership_to_restore(self):
        before = self.original()
        self.apply()
        self.helper.install(self.module.__dict__)
        self.apply('b')
        self.helper.install(self.module.__dict__)
        self.apply('')
        self.assertEqual(self.helper.identity(self.target), before)

    def test_missing_or_unknown_selection_keeps_current_movie_and_state(self):
        before = self.original()
        for value in ['unknown', 'a']:
            if value == 'a':
                self.a.unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                self.apply(value)
            self.assertEqual(self.helper.identity(self.target), before)
            self.assertFalse(self.backups.exists())

    def test_invalid_selection_preserves_an_already_managed_link(self):
        self.original()
        self.apply()
        marker = self.backups/self.video/'owner.json'
        before = marker.read_bytes()
        with self.assertRaises(ValueError):
            self.apply('unknown')
        self.assertEqual(marker.read_bytes(), before)
        self.assertEqual(os.readlink(self.target), str(self.a))
        self.apply('')

    def test_manual_replacement_refuses_clear_and_switch_without_overwrite(self):
        self.original()
        self.apply()
        self.target.unlink()
        self.target.write_bytes(b'manual replacement')
        for selection in ['', 'b']:
            with self.assertRaisesRegex(RuntimeError, 'changed outside'):
                self.apply(selection)
            self.assertEqual(self.target.read_bytes(), b'manual replacement')
            self.assertEqual((self.backups/self.video/'original').read_bytes(), b'original override')

    def test_removed_backup_refuses_reset_and_preserves_owned_link(self):
        self.original()
        self.apply()
        (self.backups/self.video/'original').rename(self.home/'retained-original')
        with self.assertRaisesRegex(RuntimeError, 'backup is missing'):
            self.apply('')
        self.assertEqual(os.readlink(self.target), str(self.a))
        self.assertEqual((self.home/'retained-original').read_bytes(), b'original override')

    def test_first_ownership_write_failure_restores_prior_inode(self):
        before = self.original()
        with patch.object(self.helper.Overrides, 'write', side_effect=OSError('fixture write failed')):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(self.helper.identity(self.target), before)
        self.assertEqual(self.target.read_bytes(), b'original override')
        self.apply()
        self.apply('')
        self.assertEqual(self.helper.identity(self.target), before)

    def test_switch_ownership_write_failure_restores_old_owned_link_and_marker(self):
        self.original()
        self.apply()
        before = self.helper.identity(self.target)
        marker = self.backups/self.video/'owner.json'
        raw = marker.read_bytes()
        with patch.object(self.helper.Overrides, 'write', side_effect=OSError('fixture write failed')):
            with self.assertRaises(OSError):
                self.apply('b')
        self.assertEqual(self.helper.identity(self.target), before)
        self.assertEqual(marker.read_bytes(), raw)
        self.apply('')
        self.assertEqual(self.target.read_bytes(), b'original override')

    def test_unknown_movie_cannot_write_outside_override_directory(self):
        outside = self.home/'outside.webm'
        outside.write_bytes(b'outside sentinel')
        with self.assertRaises(ValueError):
            self.apply('a', '../outside.webm')
        self.assertEqual(outside.read_bytes(), b'outside sentinel')
        self.assertFalse(self.backups.exists())

    def test_backup_directory_symlink_is_refused(self):
        outside = self.home/'outside'
        outside.mkdir()
        self.backups.symlink_to(outside, target_is_directory=True)
        before = self.original()
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(self.helper.identity(self.target), before)
        self.assertEqual(list(outside.iterdir()), [])

    def test_directory_target_and_self_reference_are_refused(self):
        self.target.mkdir()
        with self.assertRaises(RuntimeError):
            self.apply()
        self.target.rmdir()
        self.original()
        self.module.config['custom_animations'].append(dict(id='self', path=str(self.target)))
        with self.assertRaises(ValueError):
            self.apply('self')
        self.assertEqual(self.target.read_bytes(), b'original override')

    def test_archive_source_preserved_and_helper_scoped_to_exact_pin(self):
        with zipfile.ZipFile(io.BytesIO(self.data)) as bundle:
            original = bundle.read(self.pin['folder']+'/main.py')
            self.assertTrue((self.folder/'main.py').read_bytes().startswith(original))
            for entry in bundle.infolist():
                if not entry.is_dir() and not entry.filename.endswith('/main.py'):
                    relative = entry.filename.split('/', 1)[1]
                    self.assertEqual((self.folder/relative).read_bytes(), bundle.read(entry))
        receipt = json.loads((self.folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['animation-preserve-overrides'])
        import frame_decky_store
        self.assertTrue(frame_decky_store.apply_script(23, self.pin['sha256']).startswith('FRAMEY_ANIMATION_OVERRIDES_SOURCE = '))
        self.assertFalse(frame_decky_store.apply_script(24, self.pin['sha256']).startswith('FRAMEY_ANIMATION_OVERRIDES_SOURCE = '))
        self.assertFalse(frame_decky_store.apply_script(23, '0'*64).startswith('FRAMEY_ANIMATION_OVERRIDES_SOURCE = '))
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         '11a96a6f3108021b096e0aeb60c7d3ee3c6b2e237cf235c02f5753cf9d3382b8')
