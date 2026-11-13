"""Exact archive, configured user environment, and connection ownership."""
import sandbox  # noqa: F401
import ast
import asyncio
import io
import logging
import os
from pathlib import Path
import queue
import sys
import types
import unittest
from unittest.mock import patch
import zipfile

import framey_official
import test_frame_decky_store as transactions
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import framey_screensaver

ROOT = Path(__file__).resolve().parents[1]


class FakeBus:
    instances = []
    busy = None
    fail_connect = False

    def __init__(self, *, bus_address):
        self.address=bus_address;self.connected=False;self.exports=[];self.requests=[];self.disconnected=False
        self.instances.append(self)

    async def connect(self):
        if self.fail_connect: raise asyncio.TimeoutError()
        self.connected=True
        return self

    def export(self, path, interface): self.exports.append(path)

    async def request_name(self, name, flags):
        self.requests.append((name,flags))
        return 3 if name==self.busy else 1

    def disconnect(self): self.connected=False;self.disconnected=True
    async def wait_for_disconnect(self): assert self.disconnected


@unittest.skipIf(os.name=='nt', 'remote plugin transaction and user bus ownership require POSIX')
class ScreenSaver(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeBus.instances=[];FakeBus.busy=None;FakeBus.fail_connect=False
        self.tx=transactions.StoreTransaction();self.tx.setUp();self.addCleanup(self.tx.doCleanups)
        self.pin=next(p for p in framey_official.PLUGINS if p['id']==87);self.data=framey_official.archive(self.pin)
        result=self.tx.apply('install',self.data,plugin_id=87,folder=self.pin['folder'],version=self.pin['version'])
        self.assertEqual(result.returncode,0,result.stderr)
        self.folder=self.tx.folder.parent/self.pin['folder']
        self.namespace=self.imported();self.plugin=self.namespace.Plugin()

    def imported(self):
        class Interface:
            last_msg=types.SimpleNamespace(sender=':private')
            def __init__(self,name): pass
        class Settings:
            def __init__(self,**kwargs): self.data={}
            def getSetting(self,key,default=None): return self.data.get(key,default)
            def setSetting(self,key,value): self.data[key]=value
        decorate=lambda *args,**kwargs:lambda fn:fn
        decky=types.SimpleNamespace(logger=logging.getLogger('screensaver-private'),
            DECKY_PLUGIN_SETTINGS_DIR=str(self.folder/'settings'))
        stubs={'decky_plugin':decky,'settings':types.SimpleNamespace(SettingsManager=Settings),
            'framey_decky_ipc':types.SimpleNamespace(install=lambda:None),
            'framey_screensaver':framey_screensaver,'dbus_next':types.SimpleNamespace(Message=lambda **kwargs:kwargs,MessageType=types.SimpleNamespace(ERROR=3)),
            'dbus_next.aio':types.SimpleNamespace(MessageBus=FakeBus),
            'dbus_next.service':types.SimpleNamespace(ServiceInterface=Interface,method=decorate,dbus_property=decorate,signal=decorate),
            'dbus_next.constants':types.SimpleNamespace(NameFlag=types.SimpleNamespace(DO_NOT_QUEUE=4),
                RequestNameReply=types.SimpleNamespace(PRIMARY_OWNER=1,ALREADY_OWNER=4))}
        module=types.ModuleType('private_screensaver');module.__file__=str(self.folder/'main.py')
        before=dict(os.environ)
        with patch.dict(sys.modules,stubs),patch.object(sys,'path',list(sys.path)):
            exec(compile((self.folder/'main.py').read_bytes(),module.__file__,'exec'),module.__dict__)
        self.assertEqual(dict(os.environ),before,'managed import must preserve the whole configured environment')
        return module

    def test_original_wrong_user_environment_reproduced_without_changing_host(self):
        with zipfile.ZipFile(io.BytesIO(self.data))as z:tree=ast.parse(z.read(self.pin['folder']+'/main.py'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='setup_environ_vars')
        imports=[n for n in function.body if isinstance(n,ast.Import)];self.assertEqual(len(imports),1)
        function.body=[n for n in function.body if not isinstance(n,ast.Import)]
        env={'HOME':'/private/user','XDG_RUNTIME_DIR':'/private/runtime','DBUS_SESSION_BUS_ADDRESS':'unix:path=/private/bus'}
        namespace={'os':types.SimpleNamespace(environ=env)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'private-original-env','exec'),namespace)
        namespace['setup_environ_vars']()
        self.assertEqual(env,dict(HOME='/home/deck',XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus'))

    def test_exact_archive_members_and_both_helpers(self):
        with zipfile.ZipFile(io.BytesIO(self.data))as z:
            for member in z.infolist():
                if member.is_dir()or member.filename.endswith('/main.py'):continue
                self.assertEqual((self.folder/member.filename.split('/',1)[1]).read_bytes(),z.read(member))
        for name in ['framey_screensaver','framey_decky_ipc']:
            self.assertEqual((self.folder/('py_modules/'+name+'.py')).read_bytes(),(ROOT/('ui/'+name+'.py')).read_bytes())

    async def test_configured_bus_and_non_replacing_non_queued_names(self):
        with patch.dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/private/actual-user-bus'):
            self.assertTrue(await self.plugin.start_backend())
        bus,=FakeBus.instances
        self.assertEqual(bus.address,'unix:path=/private/actual-user-bus')
        self.assertEqual(bus.requests,[(name,4)for name in framey_screensaver.NAMES])
        self.assertEqual(len(bus.exports),4);self.assertTrue(await self.plugin.is_running())
        await self.plugin.stop_backend();self.assertTrue(bus.disconnected);self.assertFalse(await self.plugin.is_running())

    async def test_busy_name_closes_partial_connection_without_queueing(self):
        FakeBus.busy=framey_screensaver.NAMES[1]
        with patch.dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/private/bus'):
            self.assertFalse(await self.plugin.start_backend())
        bus,=FakeBus.instances;self.assertTrue(bus.disconnected)
        self.assertEqual(bus.requests,[(name,4)for name in framey_screensaver.NAMES[:2]])
        self.assertIsNone(self.namespace.bus);self.assertFalse(await self.plugin.is_running())

    async def test_missing_bus_and_failed_connect_do_not_report_running(self):
        with patch.dict(os.environ,{},clear=True):self.assertFalse(await self.plugin.start_backend())
        self.assertFalse(FakeBus.instances)
        FakeBus.fail_connect=True
        with patch.dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/private/bus'):
            self.assertFalse(await self.plugin.start_backend())
        self.assertTrue(FakeBus.instances[0].disconnected);self.assertFalse(await self.plugin.is_running())

    async def test_restart_closes_only_owned_connection_and_clears_stale_events(self):
        with patch.dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/private/bus'):
            self.assertTrue(await self.plugin.start_backend());first=FakeBus.instances[-1]
            self.namespace.event_queue.put({'type':'Inhibit'});self.namespace.BaseInterface.request_map[99]=object()
            self.assertTrue(await self.plugin.start_backend())
        self.assertTrue(first.disconnected);self.assertFalse(FakeBus.instances[-1].disconnected)
        self.assertEqual(self.namespace.BaseInterface.request_map,{})
        self.assertEqual(await self.plugin.get_event(),[])
        await self.plugin.stop_backend()

    async def test_unload_closes_bus_and_rejects_later_start(self):
        with patch.dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/private/bus'):
            self.assertTrue(await self.plugin.start_backend());await self.plugin._unload()
            self.assertFalse(await self.plugin.start_backend())
        self.assertTrue(FakeBus.instances[0].disconnected);self.assertEqual(len(FakeBus.instances),1)

    async def test_settings_and_queued_event_contract_stay_compatible(self):
        await self.plugin.set_settings('private_label','Private setting')
        self.assertEqual(await self.plugin.get_settings('private_label',None),'Private setting')
        with patch.dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/private/bus'):
            self.assertTrue(await self.plugin.start_backend())
        self.namespace.event_queue.put({'type':'Inhibit'})
        self.assertEqual(await self.plugin.get_event(),[{'type':'Inhibit'}])
        await self.plugin.stop_backend();self.assertEqual(await self.plugin.get_event(),[])
