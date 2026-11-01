"""Exact archive and disposable shared shader files; no host display access."""
import sandbox  # noqa: F401
import asyncio
import hashlib
import io
import logging
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch
import zipfile

import framey_official
import test_frame_decky_store as transactions
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import framey_reshadeck

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == 'nt', 'managed transaction and shader ownership require POSIX')
class Reshadeck(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tx=transactions.StoreTransaction();self.tx.setUp();self.addCleanup(self.tx.doCleanups)
        self.pin=next(p for p in framey_official.PLUGINS if p['id']==75)
        self.data=framey_official.archive(self.pin)
        result=self.tx.apply('install',self.data,plugin_id=75,folder=self.pin['folder'],version=self.pin['version'])
        self.assertEqual(result.returncode,0,result.stderr)
        self.folder=self.tx.folder.parent/self.pin['folder']
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
        self.module=self.imported(True);self.plugin=self.module.Plugin();self.runtime=self.module._framey_reshadeck_runtime

    def imported(self,managed):
        decky=types.SimpleNamespace(logger=logging.getLogger('private-reshadeck'),
            DECKY_USER_HOME=str(self.home),DECKY_PLUGIN_DIR=str(self.folder))
        stubs=dict(decky_plugin=decky,click=types.SimpleNamespace(get_app_dir=lambda: None),
            framey_decky_ipc=types.SimpleNamespace(install=lambda: None),framey_reshadeck=framey_reshadeck)
        with zipfile.ZipFile(io.BytesIO(self.data))as z:
            source=(self.folder/'main.py').read_bytes()if managed else z.read('reshadeck/main.py')
        module=types.ModuleType('private_reshadeck')
        with patch.dict(sys.modules,stubs):exec(compile(source,'private-reshadeck.py','exec'),module.__dict__)
        return module

    def test_archive_preserved_and_helpers_exact(self):
        with zipfile.ZipFile(io.BytesIO(self.data))as z:
            for m in z.infolist():
                if m.is_dir():continue
                installed=(self.folder/m.filename.split('/',1)[1]).read_bytes()
                if m.filename=='reshadeck/main.py':self.assertIn(z.read(m),installed)
                else:self.assertEqual(installed,z.read(m))
        for name in ['framey_reshadeck','framey_decky_ipc']:
            self.assertEqual((self.folder/('py_modules/'+name+'.py')).read_bytes(),(ROOT/('ui/'+name+'.py')).read_bytes())

    async def test_original_overwrite_reproduced_and_managed_start_preserves_file(self):
        dest=self.runtime.destination;dest.mkdir(parents=True);name='RD_MattiasCRT.fx';target=dest/name
        original=self.imported(False);target.write_bytes(b'preexisting private shader')
        with patch.object(original.subprocess,'run'):
            await original.Plugin()._main()
        self.assertEqual(target.read_bytes(),(self.folder/'shaders'/name).read_bytes())
        target.write_bytes(b'preexisting private shader');before=target.stat()
        with patch('framey_reshadeck.asyncio.create_subprocess_exec',AsyncMock())as spawn:
            await self.plugin._main();spawn.assert_not_called()
        self.assertEqual(target.read_bytes(),b'preexisting private shader')
        self.assertEqual((target.stat().st_ino,target.stat().st_mtime_ns,target.stat().st_mode),
                         (before.st_ino,before.st_mtime_ns,before.st_mode))

    async def test_all_missing_fx_and_includes_publish_complete_and_repeat_without_rewrite(self):
        await self.plugin._main();files=list(self.runtime.destination.iterdir());self.assertEqual(len(files),5)
        before={p.name:(p.read_bytes(),p.stat().st_ino,p.stat().st_mtime_ns)for p in files}
        for p in files:self.assertEqual(p.read_bytes(),(self.folder/'shaders'/p.name).read_bytes())
        await self.plugin._main();self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_ino,p.stat().st_mtime_ns)for p in files})
        self.assertFalse(list(self.runtime.destination.glob('.frame-control-shader-*')))

    async def test_preexisting_symlink_and_custom_shader_are_not_replaced(self):
        dest=self.runtime.destination;dest.mkdir(parents=True);other=self.home/'original.fx';other.write_bytes(b'keep')
        link=dest/'RD_MattiasCRT.fx';link.symlink_to(other);custom=dest/'User shader.fx';custom.write_bytes(b'custom')
        await self.plugin._main();self.assertTrue(link.is_symlink());self.assertEqual(other.read_bytes(),b'keep')
        self.assertEqual(custom.read_bytes(),b'custom')
        self.assertFalse(await self.plugin.set_shader(link.name))

    async def test_symlink_directory_is_refused(self):
        other=self.home/'other';other.mkdir();self.runtime.destination.parent.mkdir(parents=True)
        self.runtime.destination.symlink_to(other)
        with self.assertRaises(ValueError):await self.plugin._main()
        self.assertEqual(list(other.iterdir()),[])

    async def test_explicit_selection_is_one_argument_and_state_changes_only_after_success(self):
        await self.plugin._main();name='User shader.fx';(self.runtime.destination/name).write_bytes(b'custom')
        child=types.SimpleNamespace(returncode=0,communicate=AsyncMock(return_value=(b'',b'')),wait=AsyncMock(return_value=0))
        with patch.dict(os.environ,DISPLAY=':private'),patch('framey_reshadeck.asyncio.create_subprocess_exec',AsyncMock(return_value=child))as spawn:
            self.assertTrue(await self.plugin.set_shader(name))
            self.assertEqual(spawn.await_args.args,('xprop','-root','-f','GAMESCOPE_RESHADE_EFFECT','8u','-set','GAMESCOPE_RESHADE_EFFECT',name))
            self.assertEqual(await self.plugin.get_current_shader(),name)
            child.returncode=1;self.assertFalse(await self.plugin.set_shader('0'))
            self.assertEqual(await self.plugin.get_current_shader(),name)
        with patch.dict(os.environ,{},clear=True),patch('framey_reshadeck.asyncio.create_subprocess_exec',AsyncMock())as spawn:
            self.assertFalse(await self.plugin.set_shader('0'));spawn.assert_not_called()

    async def test_invalid_selection_never_spawns_and_screensaver_is_only_applied_explicitly(self):
        await self.plugin._main()
        with patch('framey_reshadeck.asyncio.create_subprocess_exec',AsyncMock())as spawn:
            for name in ['../outside.fx','/tmp/outside.fx','missing.fx','bad\n.fx',True]:
                self.assertFalse(await self.plugin.set_shader(name))
                self.assertFalse(await self.plugin.set_screensaver(name))
            self.assertTrue(await self.plugin.set_screensaver('SS_ScreenOff.fx'));spawn.assert_not_called()
        with patch.object(self.runtime,'apply',AsyncMock(return_value=True))as apply:
            self.assertTrue(await self.plugin.apply_shader(True));apply.assert_awaited_once_with('SS_ScreenOff.fx')
            self.assertFalse(await self.plugin.apply_shader('yes'))

    async def test_command_timeout_reaps_only_its_child_and_retains_current(self):
        await self.plugin._main()
        child=types.SimpleNamespace(returncode=None,communicate=AsyncMock(side_effect=asyncio.TimeoutError),wait=AsyncMock(return_value=-15))
        child.terminate=lambda:setattr(child,'returncode',-15)
        with patch.dict(os.environ,DISPLAY=':private'),patch('framey_reshadeck.asyncio.create_subprocess_exec',AsyncMock(return_value=child)):
            self.assertFalse(await self.plugin.set_shader('RD_VHS_RA.fx'))
        child.wait.assert_awaited_once();self.assertIsNone(self.runtime.process)
        self.assertEqual(await self.plugin.get_current_shader(),'0')

    async def test_unload_keeps_files_and_stops_future_commands(self):
        await self.plugin._main();before={p:p.read_bytes()for p in self.runtime.destination.iterdir()}
        await self.plugin._unload()
        with patch.dict(os.environ,DISPLAY=':private'),patch('framey_reshadeck.asyncio.create_subprocess_exec',AsyncMock())as spawn:
            self.assertFalse(await self.plugin.set_shader('0'));spawn.assert_not_called()
        self.assertEqual(before,{p:p.read_bytes()for p in self.runtime.destination.iterdir()})
