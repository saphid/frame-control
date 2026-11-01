"""Exact managed Volume Mixer install, archive preservation and user environment."""
import sandbox  # noqa: F401
import ast
import io
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import zipfile

import framey_official
import test_frame_decky_store as transactions
import frame_decky_store

ROOT=Path(__file__).resolve().parents[1]
OLD=(b"    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1000'\n"
     b"    os.environ['HOME'] = '/home/deck'")
PREFIX=(b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
        b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')


@unittest.skipIf(os.name=='nt','remote plugin transaction requires POSIX')
class VolumeMixer(unittest.TestCase):
    def setUp(self):
        self.tx=transactions.StoreTransaction();self.tx.setUp();self.addCleanup(self.tx.doCleanups)
        self.pin=next(p for p in framey_official.PLUGINS if p['id']==38)
        self.data=framey_official.archive(self.pin)
        self.folder=self.tx.folder.parent/self.pin['folder']

    def install(self,**kwargs):
        return self.tx.apply('install',self.data,plugin_id=38,folder=self.pin['folder'],version=self.pin['version'],**kwargs)

    def environment(self,source):
        # Compile just the function: published Bluetooth match/case needs Python
        # 3.10+, while this source-preservation unit suite also runs on 3.9.
        function=source.decode().split('def setup_environ_vars():\n',1)[1].split('\nadd_plugin_to_path()',1)[0]
        source='def setup_environ_vars():\n'+function
        env={'HOME':'/private/person','XDG_RUNTIME_DIR':'/private/runtime','DBUS_SESSION_BUS_ADDRESS':'unix:path=/private/bus','UNCHANGED':'yes'}
        namespace={'os':types.SimpleNamespace(environ=env)}
        exec(compile(ast.parse(source),'private-volume-environment','exec'),namespace)
        namespace['setup_environ_vars']()
        return env

    def test_original_overwrites_actual_user_but_managed_install_preserves_environment(self):
        with zipfile.ZipFile(io.BytesIO(self.data))as z:original=z.read(self.pin['folder']+'/main.py')
        self.assertEqual(self.environment(original)['HOME'],'/home/deck')
        self.assertEqual(self.environment(original)['XDG_RUNTIME_DIR'],'/run/user/1000')
        result=self.install();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.environment((self.folder/'main.py').read_bytes()),dict(HOME='/private/person',XDG_RUNTIME_DIR='/private/runtime',DBUS_SESSION_BUS_ADDRESS='unix:path=/private/bus',UNCHANGED='yes'))

    def test_only_environment_block_and_ipc_adapter_change(self):
        result=self.install();self.assertEqual(result.returncode,0,result.stderr)
        with zipfile.ZipFile(io.BytesIO(self.data))as z:
            for member in z.infolist():
                if member.is_dir():continue
                relative=member.filename.split('/',1)[1];expected=z.read(member)
                if relative=='main.py':expected=PREFIX+expected.replace(OLD,b'    pass  # Preserve configured user HOME and Pulse runtime.')
                self.assertEqual((self.folder/relative).read_bytes(),expected,relative)
        self.assertEqual((self.folder/'py_modules/framey_decky_ipc.py').read_bytes(),(ROOT/'ui/framey_decky_ipc.py').read_bytes())
        receipt=json.loads((self.folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'],['volume-mixer-user-audio','volume-mixer-ipc-eof'])

    def test_missing_adapter_fails_before_publishing(self):
        with patch.object(frame_decky_store,'apply_script',return_value=frame_decky_store.APPLY):result=self.install()
        self.assertNotEqual(result.returncode,0);self.assertIn('Missing Volume Mixer IPC helper',result.stderr)
        self.assertFalse(self.folder.exists())

    def test_other_identity_or_digest_gets_no_helper(self):
        self.assertEqual(frame_decky_store.apply_script(38,'0'*64),frame_decky_store.APPLY)
        self.assertEqual(frame_decky_store.apply_script(39,self.pin['sha256']),frame_decky_store.APPLY)

    def test_wrong_folder_is_rejected(self):
        result=self.tx.apply('install',self.data,plugin_id=38,folder='OtherVolume',version=self.pin['version'])
        self.assertNotEqual(result.returncode,0);self.assertFalse(self.folder.exists())

    def test_old_receipt_does_not_inherit_the_user_path_and_eof_repairs(self):
        import framey_compatibility
        old=framey_compatibility.lookup(38,self.pin['sha256'],self.pin['version'],installed_shims=[])
        fixed=framey_compatibility.lookup(38,self.pin['sha256'],self.pin['version'],installed_shims=['volume-mixer-user-audio','volume-mixer-ipc-eof'])
        self.assertEqual(old['status'],'partial');self.assertIn('Update or reinstall',old['reason'])
        self.assertEqual(fixed['status'],'works')
