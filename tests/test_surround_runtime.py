"""Exact installed surround archive, confined HRIRs and owned process contracts."""
import asyncio
import hashlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, AsyncMock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import framey_surround
from framey_official import PLUGINS, archive
import test_frame_decky_store as store_tests
import frame_decky_store

PIN = next(p for p in PLUGINS if p['id'] == 100)


class Surround(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.transaction = store_tests.StoreTransaction()
        self.transaction.setUp()
        self.addCleanup(self.transaction.doCleanups)
        result = self.transaction.apply('install', archive(PIN), plugin_id=100,
            folder=PIN['folder'], version=PIN['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.folder = self.transaction.folder.parent / PIN['folder']
        self.temp = tempfile.TemporaryDirectory(prefix='framey-surround-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.environment = patch.dict(os.environ, DECKY_PLUGIN_RUNTIME_DIR=str(self.home / 'runtime'))
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.settings = {}
        self.ns = dict(script_directory=str(self.folder),
            subprocess_exec_env=lambda: dict(os.environ),
            settings=types.SimpleNamespace(getSetting=lambda k,d: self.settings.get(k,d),
                setSetting=lambda k,v: self.settings.update({k:v})),
            default_hrir_file='HRTF from Aureal Vortex 2 - WIP v2.wav',
            decky=types.SimpleNamespace(logger=logging.getLogger('surround-test')))
        self.runtime = framey_surround.Runtime(self.ns)
        self.source = self.runtime.presets / self.ns['default_hrir_file']

    def test_install_is_exact_and_preserves_published_members(self):
        with zipfile.ZipFile(io.BytesIO(archive(PIN))) as z:
            original = z.read(PIN['folder'] + '/main.py')
            self.assertIn(original, (self.folder / 'main.py').read_bytes())
            for m in z.infolist():
                if m.is_dir() or m.filename.endswith('/main.py'): continue
                self.assertEqual((self.folder / m.filename.split('/',1)[1]).read_bytes(), z.read(m))
        for name in ('framey_surround.py', 'framey_decky_ipc.py'):
            self.assertEqual((self.folder/'py_modules'/name).read_bytes(),
                (Path(__file__).resolve().parents[1]/'ui'/name).read_bytes())
        self.assertEqual(json.loads((self.folder/'.frame-control-store.json').read_text())['compatShims'],
                         ['surround-owned-runtime', 'surround-ipc-eof'])

    def test_every_published_preset_has_confined_graph_and_repeatable_copy(self):
        for source in self.runtime.presets.glob('*.wav'):
            with self.subTest(source=source.name):
                target, count = self.runtime.preset(str(source))
                self.assertIn(count, (6,8))
                self.assertEqual(target.read_bytes(), source.read_bytes())
                inode = target.stat().st_ino
                self.assertEqual(self.runtime.preset(str(source)), (target,count))
                self.assertEqual(target.stat().st_ino, inode)
                self.assertEqual(target.name, hashlib.sha256(source.read_bytes()).hexdigest()+'.wav')
                graph = self.runtime.graph(target,count)
                self.assertIn(json.dumps(str(target)),graph)
                self.assertNotIn('/home/deck/',graph)
                self.assertNotIn('node.linger": true',graph)
                self.assertNotIn('$',graph)

    def test_arbitrary_source_or_modified_private_copy_is_refused(self):
        outside = self.home/'outside.wav'
        outside.write_bytes(self.source.read_bytes())
        with self.assertRaises(ValueError): self.runtime.preset(str(outside))
        target,_ = self.runtime.preset(str(self.source))
        target.write_bytes(b'user-edited-copy')
        with self.assertRaises(ValueError): self.runtime.preset(str(self.source))
        self.assertEqual(target.read_bytes(),b'user-edited-copy')

    def test_source_destination_and_runtime_symlinks_are_not_followed(self):
        outside = self.home/'outside.wav';outside.write_bytes(b'keep')
        source = self.runtime.presets/'link.wav';source.symlink_to(outside)
        with self.assertRaises(OSError): self.runtime.preset(str(source))
        target,_ = self.runtime.preset(str(self.source));target.unlink();target.symlink_to(outside)
        with self.assertRaises(OSError): self.runtime.preset(str(self.source))
        self.assertEqual(outside.read_bytes(),b'keep')
        other=self.home/'other';other.mkdir();(self.home/'linked').symlink_to(other)
        with patch.dict(os.environ,DECKY_PLUGIN_RUNTIME_DIR=str(self.home/'linked')):
            with self.assertRaises(ValueError): self.runtime.preset(str(self.source))
        self.assertEqual(list(other.iterdir()),[])

    async def test_existing_sink_is_not_stopped_or_replaced(self):
        with patch.object(self.runtime,'command',AsyncMock(return_value='node.name = "input.virtual-surround-sound"')), \
             patch('framey_surround.asyncio.create_subprocess_exec',AsyncMock()) as spawn:
            with self.assertRaisesRegex(RuntimeError,'left untouched'):
                await self.runtime.start(str(self.source))
            spawn.assert_not_called()

    async def test_all_owned_children_are_awaited_before_stop_returns(self):
        children=[]
        for _ in range(2):
            child=types.SimpleNamespace(returncode=None,wait=AsyncMock(return_value=0))
            child.terminate=lambda c=child: setattr(c,'returncode',0)
            children.append(child)
        # Subprocess objects are hashable; these small stand-ins use identity.
        class Child:
            def __init__(self):
                self.returncode=None
                self.wait=AsyncMock(return_value=0)
            def terminate(self): self.returncode=0
        child=Child();self.runtime.children.add(child)
        self.runtime.process=children[0]
        await self.runtime.stop()
        child.wait.assert_awaited_once()
        children[0].wait.assert_awaited_once()

    def imported(self, managed):
        decky=types.ModuleType('decky');decky.logger=logging.getLogger('surround-import')
        settings=types.ModuleType('settings')
        class Settings:
            def __init__(self,**kwargs): self.data={}
            def read(self): pass
            def getSetting(self,k,d=None): return self.data.get(k,d)
            def setSetting(self,k,v): self.data[k]=v
        settings.SettingsManager=Settings
        ipc=types.ModuleType('framey_decky_ipc');ipc.install=lambda: None
        module=types.ModuleType('private_surround');module.__file__=str(self.folder/'main.py')
        with zipfile.ZipFile(io.BytesIO(archive(PIN)))as z:
            data=(self.folder/'main.py').read_bytes()if managed else z.read(PIN['folder']+'/main.py')
        with patch.dict(sys.modules,decky=decky,settings=settings,framey_decky_ipc=ipc), \
             patch.dict(os.environ,DECKY_PLUGIN_LOG_DIR=str(self.home),DECKY_PLUGIN_SETTINGS_DIR=str(self.home)):
            exec(compile(data,module.__file__,'exec'),module.__dict__)
        return module

    async def test_original_uninstall_loss_and_actual_managed_preservation(self):
        shared=self.home/'shared-hrir.wav';shared.write_bytes(b'private preexisting HRIR')
        original=self.imported(False);original.hrir_dest_path=str(shared)
        with patch.object(original.os,'spawnle',return_value=123):
            await original.Plugin()._uninstall()
        self.assertFalse(shared.exists(),'published backend reproduces deletion in this disposable path')
        shared.write_bytes(b'private preexisting HRIR');before=shared.stat()
        managed=self.imported(True);managed.hrir_dest_path=str(shared)
        with patch.object(managed.os,'spawnle',side_effect=AssertionError('unowned shell spawn')):
            await managed.Plugin()._uninstall()
        self.assertEqual(shared.read_bytes(),b'private preexisting HRIR')
        self.assertEqual((shared.stat().st_ino,shared.stat().st_mtime_ns),(before.st_ino,before.st_mtime_ns))

    def test_missing_helper_cannot_publish_managed_copy(self):
        # A fresh transaction exercises payload validation before publication.
        other=store_tests.StoreTransaction();other.setUp()
        try:
            with patch.object(frame_decky_store,'apply_script',return_value=frame_decky_store.APPLY):
                result=other.apply('install',archive(PIN),plugin_id=100,folder=PIN['folder'],version=PIN['version'])
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Missing owned surround runtime helper',result.stderr)
            self.assertFalse((other.folder.parent/PIN['folder']).exists())
        finally:other.doCleanups()

    async def test_unload_and_uninstall_preserve_shared_files(self):
        shared=self.home/'.config/pipewire/hrir.wav';shared.parent.mkdir(parents=True)
        shared.write_bytes(b'original HRIR');unit=self.home/'.config/systemd/user/virtual-surround-sound.service'
        unit.parent.mkdir(parents=True);unit.write_bytes(b'original unit')
        before={p:(p.read_bytes(),p.stat().st_ino,p.stat().st_mode,p.stat().st_mtime_ns)for p in [shared,unit]}
        class Plugin:
            async def _unload(self): self.unloaded=True
            async def check_state(self): pass
        self.ns['Plugin']=Plugin;framey_surround.install(self.ns);plugin=Plugin()
        owned=types.SimpleNamespace(returncode=None,terminate=lambda: setattr(owned,'returncode',0),wait=AsyncMock(return_value=0))
        self.ns['_framey_surround_runtime'].process=owned
        await plugin._uninstall()
        self.assertTrue(plugin.unloaded);owned.wait.assert_awaited_once()
        self.assertIsNone(self.ns['_framey_surround_runtime'].process)
        self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_ino,p.stat().st_mode,p.stat().st_mtime_ns)for p in before})
