"""Private-home Shotty copy contracts; never start its global screenshot watcher."""
import asyncio
import importlib.util
import logging
import sys
import types
import unittest
from pathlib import Path

folder = Path(sys.argv.pop(1))
sys.path.insert(0, str(folder/'py_modules'))
decky = types.ModuleType('decky_plugin')
decky.logger = logging.getLogger('shotty-contract')
decky.DECKY_PLUGIN_DIR = str(folder)
sys.modules['decky_plugin'] = decky
# Copy contracts isolate filesystem behavior; published Decky IPC is tested natively.
ipc = types.ModuleType('framey_decky_ipc')
ipc.install = lambda: None
sys.modules['framey_decky_ipc'] = ipc
spec = importlib.util.spec_from_file_location('shotty', folder/'main.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HOME = Path.home()


class Copies(unittest.TestCase):
    def setUp(self):
        self.plugin = module.Plugin()
        self.name = self._testMethodName
        self.appid = 4270 + list(sorted(n for n in dir(self) if n.startswith('test_'))).index(self.name)
        self.source = HOME/f'.local/share/Steam/userdata/9002/760/remote/{self.appid}/screenshots/{self.name}.jpg'
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b'private screenshot '+self.name.encode())
        self.call(self.plugin.set_id_map_fronend([[self.appid, self.name]]))

    @staticmethod
    def call(value):
        return asyncio.run(value)

    def copy(self, appid=None, filename=None):
        return self.call(self.plugin.copy_screenshot(self.appid if appid is None else appid,
                                                    'https://localhost/'+(filename or self.source.name)))

    def test_repeat_is_successful_and_source_is_independent(self):
        self.assertTrue(self.copy())
        self.assertTrue(self.copy())
        dest = HOME/'Pictures/Screenshots'/self.name/self.source.name
        self.assertEqual(dest.read_bytes(), self.source.read_bytes())
        self.assertNotEqual(dest.stat().st_ino, self.source.stat().st_ino)
        original = dest.read_bytes()
        self.source.write_bytes(b'changed source')
        self.assertEqual(dest.read_bytes(), original)
        self.assertFalse(self.copy(), 'a different existing image must never be overwritten')
        self.assertEqual(dest.read_bytes(), original)

    def test_app_name_cannot_escape_pictures(self):
        self.call(self.plugin.set_id_map_fronend([[self.appid, '../../escaped']]))
        self.assertTrue(self.copy())
        self.assertFalse((HOME/'escaped'/self.source.name).exists())
        self.assertTrue(any(p.read_bytes() == self.source.read_bytes()
                            for p in (HOME/'Pictures/Screenshots').glob('*/*.jpg')))

    def test_invalid_app_ids_do_not_expand_globs(self):
        for appid in ('*', '../*', True, -1):
            with self.subTest(appid=appid): self.assertFalse(self.copy(appid))

    def test_source_and_destination_links_are_refused(self):
        external = HOME/(self.name+'-external.jpg')
        external.write_bytes(b'private external marker')
        self.source.unlink()
        self.source.symlink_to(external)
        self.assertFalse(self.copy())
        self.source.unlink()
        self.source.write_bytes(b'private source')
        destdir = HOME/'Pictures/Screenshots'/self.name
        destdir.mkdir(parents=True)
        (destdir/self.source.name).symlink_to(external)
        self.assertFalse(self.copy())
        self.assertEqual(external.read_bytes(), b'private external marker')

    def test_selected_png_keeps_its_extension(self):
        png = self.source.with_suffix('.png')
        self.source.rename(png)
        self.assertTrue(self.copy(filename=png.name))
        self.assertEqual((HOME/'Pictures/Screenshots'/self.name/png.name).read_bytes(), png.read_bytes())

    def test_parent_symlink_is_not_followed(self):
        other = HOME/(self.name+'-outside')
        other.mkdir()
        target = HOME/'Pictures/Screenshots'/self.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(other, target_is_directory=True)
        self.assertFalse(self.copy())
        self.assertEqual(list(other.iterdir()), [])

    def test_oversized_and_special_sources_are_refused(self):
        with self.source.open('wb') as stream: stream.truncate(64*1024*1024+1)
        self.assertFalse(self.copy())
        self.source.unlink()
        import os
        os.mkfifo(self.source)
        self.assertFalse(self.copy())

    def test_unload_cancels_only_the_owned_rescuer_task(self):
        async def check():
            owned = asyncio.create_task(asyncio.sleep(60))
            unrelated = asyncio.create_task(asyncio.sleep(60))
            module.Plugin._rescuer_task = owned
            await self.plugin._unload()
            self.assertTrue(owned.cancelled())
            self.assertFalse(unrelated.done())
            unrelated.cancel()
            await asyncio.gather(unrelated, return_exceptions=True)
        self.call(check())

    def test_ambiguous_accounts_are_refused_before_copy(self):
        other = HOME/f'.local/share/Steam/userdata/9003/760/remote/{self.appid}/screenshots/{self.source.name}'
        other.parent.mkdir(parents=True)
        other.write_bytes(b'another account')
        self.assertFalse(self.copy())
        self.assertFalse((HOME/'Pictures/Screenshots'/self.name/self.source.name).exists())


if __name__ == '__main__': unittest.main()
