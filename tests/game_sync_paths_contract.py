"""Private read-only path selection contracts for the installed Game Sync utility."""
import importlib.util
import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest

folder = Path(sys.argv.pop(1))
sys.modules['decky'] = types.ModuleType('decky')
common = types.ModuleType('common_defs')
common.logger = logging.getLogger('game-sync-path-contract')
sys.modules['common_defs'] = common
config = types.ModuleType('config')
config.Config = type('Config', (), {'get_config_item': staticmethod(lambda key: sync_root)})
sys.modules['config'] = config
spec = importlib.util.spec_from_file_location('game_sync_utils', folder/'py_modules/utils.py')
utility = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utility)
sync_root = None


class Selection(unittest.TestCase):
    def setUp(self):
        global sync_root
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base/'saves'
        self.root.mkdir()
        sync_root = str(self.root)
        self.outside = self.base/'saves-other'
        self.outside.mkdir()
        (self.outside/'private.bin').write_bytes(b'untouched private fixture')

    def tearDown(self):
        self.assertEqual((self.outside/'private.bin').read_bytes(), b'untouched private fixture')

    def test_regular_file_missing_and_shallow_recursive_counts(self):
        (self.root/'save.bin').write_bytes(b'private save')
        (self.root/'nested').mkdir()
        (self.root/'nested/save2.bin').write_bytes(b'private nested save')
        self.assertEqual(utility.test_syncpath(str(self.root/'save.bin')), 1)
        self.assertEqual(utility.test_syncpath(str(self.root/'missing.bin')), 0)
        self.assertEqual(utility.test_syncpath(str(self.root)+'/*'), 1)
        self.assertEqual(utility.test_syncpath(str(self.root)+'/**'), 2)

    def test_sibling_prefix_and_parent_escape_are_refused(self):
        for path in (self.outside/'private.bin', self.root/'../saves-other/private.bin'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                utility.test_syncpath(str(path))

    def test_direct_outside_symlink_is_refused(self):
        (self.root/'linked.bin').symlink_to(self.outside/'private.bin')
        with self.assertRaises(ValueError):
            utility.test_syncpath(str(self.root/'linked.bin'))

    def test_walked_outside_file_and_directory_links_are_refused(self):
        for name, target in (('linked.bin', self.outside/'private.bin'), ('linked-dir', self.outside)):
            link = self.root/name
            link.symlink_to(target)
            try:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    utility.test_syncpath(str(self.root)+'/**')
            finally:
                link.unlink()

    def test_in_root_links_still_work_and_directory_cycles_are_refused(self):
        (self.root/'actual').mkdir()
        (self.root/'actual/save.bin').write_bytes(b'private save')
        (self.root/'alias').symlink_to(self.root/'actual')
        self.assertEqual(utility.test_syncpath(str(self.root/'alias/save.bin')), 1)
        self.assertEqual(utility.test_syncpath(str(self.root/'alias')+'/**'), 1)
        (self.root/'actual/cycle').symlink_to(self.root)
        with self.assertRaises(ValueError):
            utility.test_syncpath(str(self.root)+'/**')

    def test_file_count_remains_capped(self):
        for index in range(9001):
            (self.root/str(index)).touch()
        self.assertEqual(utility.test_syncpath(str(self.root)+'/**'), -1)


if __name__ == '__main__':
    unittest.main()
