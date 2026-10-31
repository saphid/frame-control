"""Framey hosts store-owned modern Decky frontends and scopes backend calls."""
import sandbox  # noqa: F401
import gzip
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import framey_panel
import frame_headset
import server

RECEIPT = 'a' * 64


class Panel(unittest.TestCase):
    def test_syncthing_http_facade_uses_receipt_bound_legacy_rpc(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_syncthing_http.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_syncthing_http_calls_require_exact_receipt_shim_and_legacy_envelope(self):
        digest = framey_panel.frame_decky_store.SYNCTHING_DIGEST
        installed = {'storeId':64, 'name':'Syncthing', 'sha256':digest,
                     'compatShims':['syncthing-owned-native-http']}
        args = [{'method':'GET', 'path':'/rest/system/status', 'headers':{}}]
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={'plugins':[installed]}):
            self.assertEqual(framey_panel.call_method(lambda *_a, **_k:'{"success":true,"result":{}}',
                64,'framey_http_fetch',args,True,digest), {'success':True,'result':{}})
            for method,legacy in [('framey_http_escape',True),('framey_http_fetch',False)]:
                with self.assertRaisesRegex(framey_panel.PanelError,'HTTP bridge'):
                    framey_panel.call_method(lambda *_a, **_k:self.fail('Unapproved bridge reached SSH'),
                        64,method,args,legacy,digest)
            installed['compatShims'] = []
            with self.assertRaisesRegex(framey_panel.PanelError,'HTTP bridge'):
                framey_panel.call_method(lambda *_a, **_k:self.fail('Old receipt reached SSH'),
                    64,'framey_http_fetch',args,True,digest)
            installed.update(storeId=81,compatShims=['syncthing-owned-native-http'])
            with self.assertRaisesRegex(framey_panel.PanelError,'HTTP bridge'):
                framey_panel.call_method(lambda *_a, **_k:self.fail('Wrong plugin reached SSH'),
                    81,'framey_http_fetch',args,True,digest)

    def test_only_exact_syncthing_panel_loads_http_facade(self):
        digest = framey_panel.frame_decky_store.SYNCTHING_DIGEST
        with patch.object(framey_panel,'_owned_dist',return_value=(None,b'export default () => null;',digest)):
            self.assertIn(b'data-syncthing-http="1"',framey_panel.panel(64))
            self.assertNotIn(b'data-syncthing-http',framey_panel.panel(81))
        with patch.object(framey_panel,'_owned_dist',return_value=(None,b'export default () => null;','a'*64)):
            self.assertNotIn(b'data-syncthing-http',framey_panel.panel(64))

    def test_running_queue_and_host_contract(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_running.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_running_bridge_is_installed_scoped_bounded_and_headset_only(self):
        def fake_ssh(command, stdin, **_):
            self.assertEqual(command, 'python3 -')
            compile(stdin, '<running read>', 'exec')
            self.assertIn('RegisterForAppLifetimeNotifications', stdin)
            self.assertIn('262144', stdin)
            self.assertNotIn('__FRAMEY_STEAM_', stdin)
            return '{"result":{"apps":[],"events":[],"cursor":0}}'
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={'plugins':[{'storeId':13,'sha256':'a'*64}]}):
            self.assertEqual(framey_panel.poll_running(fake_ssh,13,'test-1',True,receipt='a'*64)['result']['cursor'],0)
            for plugin_id,session,active,cursor in [(True,'test',True,0),(0,'test',True,0),
                    (14,'test',True,0),(13,'bad session',True,0),(13,'test',1,0),
                    (13,'test',True,True),(13,'test',True,-1),(13,'test',True,2**53)]:
                with self.subTest(args=(plugin_id,session,active,cursor)):
                    with self.assertRaises(framey_panel.PanelError):
                        framey_panel.poll_running(lambda *a,**k:self.fail('Unexpected SSH'),
                                                  plugin_id,session,active,cursor,receipt='a'*64)
        with patch.object(server, 'HEADSET_RUNTIME', False), patch.dict(server.os.environ, {'FRAME_E2E_CONTAINER':'0'}):
            with self.assertRaises(server.Failure):
                server.framey_running_action({'id':13,'session':'test','active':True})
        with patch.object(server, 'HEADSET_RUNTIME', True), patch.object(framey_panel, 'poll_running',return_value={'result':None}) as poll:
            self.assertEqual(server.framey_running_action({'id':13,'session':'test','active':False,'receipt':'a'*64}),{'result':None})
            poll.assert_called_once_with(server.ssh,13,'test',False,0,'a'*64)

    def test_running_rejects_stale_or_missing_receipt_after_plugin_replacement(self):
        installed = {'storeId':13,'sha256':'a'*64}
        def safe_ssh(command, stdin, **_):
            self.assertEqual(command,'python3 -')
            compile(stdin,'<running read>','exec')
            return '{"result":null}'
        with patch.object(framey_panel.frame_decky,'plugin_status',side_effect=lambda _: {'plugins':[installed]}):
            framey_panel.poll_running(safe_ssh,13,'old-panel',True,receipt='a'*64)
            installed['sha256'] = 'b'*64  # Another manager replaces the installed plugin.
            for active in (True,False):
                for receipt in (None,'','bad','a'*64):
                    with self.subTest(active=active,receipt=receipt):
                        with self.assertRaisesRegex(framey_panel.PanelError,'receipt|changed'):
                            framey_panel.poll_running(lambda *a,**k:self.fail('Stale running request reached CEF'),
                                                      13,'old-panel',active,receipt=receipt)
            # A reopened panel uses the new receipt for both polling and cleanup.
            framey_panel.poll_running(safe_ssh,13,'new-panel',True,receipt='b'*64)
            framey_panel.poll_running(safe_ssh,13,'new-panel',False,receipt='b'*64)

    def test_steam_reads_are_allowlisted_and_installed_only(self):
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={
                'plugins':[{'storeId':81,'name':'IsThereAnyDeal for Deck','sha256':RECEIPT}]}):
            for method, expression in framey_panel.STEAM_READS.items():
                if method == 'GetGlobalCompatTools':
                    continue  # This additional read is scoped to exact Wine Cellar 0.2.1.
                def fake_ssh(command, stdin, **_):
                    self.assertEqual(command, 'python3 -')
                    compile(stdin, '<Steam read>', 'exec')
                    self.assertIn(expression.replace('\n', r'\n'), stdin)
                    self.assertNotIn('__FRAMEY_STEAM_READ__', stdin)
                    return '{"result":"actual read"}'
                self.assertEqual(framey_panel.read_steam(fake_ssh,81,method,RECEIPT)['result'], 'actual read')
            for plugin_id, method in [(True,'GetIPCountry'), (0,'GetIPCountry'),
                    (82,'GetIPCountry'), (81,'ShutdownPC'), (81,'User.GetIPCountry'),
                    (81,[]), (81,'GetIPCountry();alert(1)')]:
                with self.subTest(plugin_id=plugin_id, method=method):
                    with self.assertRaises(framey_panel.PanelError):
                        framey_panel.read_steam(lambda *a,**k:self.fail('Unexpected SSH'),plugin_id,method,RECEIPT)
            with self.assertRaisesRegex(framey_panel.PanelError, 'changed'):
                framey_panel.read_steam(lambda *a,**k:self.fail('Stale read reached SSH'),
                                        81,'GetIPCountry','b'*64)

    def test_wine_cellar_steam_tool_read_is_exact_receipt_scoped(self):
        digest = framey_panel.frame_decky_store.WINE_CELLAR_DIGEST
        installed = {'storeId':68, 'name':'Wine Cellar', 'sha256':digest,
                     'compatShims':['wine-cellar-native-bridge']}
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={'plugins':[
                installed, {'storeId':81, 'name':'Other', 'sha256':digest}]}):
            self.assertEqual(framey_panel.read_steam(lambda *_a, **_k:'{"result":[]}',
                                                     68,'GetGlobalCompatTools',digest), {'result':[]})
            with self.assertRaisesRegex(framey_panel.PanelError, 'only available'):
                framey_panel.read_steam(lambda *_a, **_k:self.fail('Wrong plugin reached CEF'),
                                        81,'GetGlobalCompatTools',digest)
            with self.assertRaisesRegex(framey_panel.PanelError, 'changed'):
                framey_panel.read_steam(lambda *_a, **_k:self.fail('Stale read reached CEF'),
                                        68,'GetGlobalCompatTools','b'*64)

    def test_wine_cellar_socket_methods_require_exact_managed_receipt(self):
        digest = framey_panel.frame_decky_store.WINE_CELLAR_DIGEST
        installed = {'storeId':68, 'name':'Wine Cellar', 'sha256':digest,
                     'compatShims':['wine-cellar-native-bridge']}
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={'plugins':[installed]}):
            self.assertEqual(framey_panel.call_method(lambda *_a, **_k:'{"result":"token"}',
                                                      68,'framey_ws_open',[],receipt=digest), {'result':'token'})
            for method in ('framey_ws_escape', 'framey_ws_open_other'):
                with self.assertRaisesRegex(framey_panel.PanelError, 'socket bridge'):
                    framey_panel.call_method(lambda *_a, **_k:self.fail('Unapproved socket method reached CEF'),
                                             68,method,[],receipt=digest)
            installed['compatShims'] = []
            with self.assertRaisesRegex(framey_panel.PanelError, 'socket bridge'):
                framey_panel.call_method(lambda *_a, **_k:self.fail('Old install reached CEF'),
                                         68,'framey_ws_open',[],receipt=digest)

    def test_only_exact_wine_cellar_panel_loads_the_socket_facade(self):
        digest = framey_panel.frame_decky_store.WINE_CELLAR_DIGEST
        bundle = b'export default () => null;'
        with patch.object(framey_panel, '_owned_dist', return_value=(None,bundle,digest)):
            self.assertIn(b'data-wine-socket="1"', framey_panel.panel(68))
            self.assertNotIn(b'data-wine-socket', framey_panel.panel(14))
        with patch.object(framey_panel, '_owned_dist', return_value=(None,bundle,'a'*64)):
            self.assertNotIn(b'data-wine-socket', framey_panel.panel(68))

    def test_steam_read_response_limit_and_socket_cleanup(self):
        from types import SimpleNamespace
        for value, oversized in [('AU',False), ('x'*(256*1024),True)]:
            closed=[]
            page=SimpleNamespace(eval=lambda _:value,sock=SimpleNamespace(close=lambda:closed.append(True)))
            fake_module=SimpleNamespace(Page=lambda:page)
            script=framey_panel.STEAM_READ_SCRIPT.replace('__FRAMEY_STEAM_READ__',repr('safe()')).replace(
                '__FRAMEY_STEAM_LIMIT__',str(256*1024))
            with patch.dict(sys.modules, {'frame_steam':fake_module}), patch('builtins.print') as output:
                if oversized:
                    with self.assertRaisesRegex(ValueError,'too large'):exec(script,{})
                else:
                    exec(script,{})
                    self.assertEqual(json.loads(output.call_args.args[0]),{'result':'AU'})
            self.assertEqual(closed,[True])

    def test_library_snapshot_copies_only_bounded_scalar_fields(self):
        expression = framey_panel.STEAM_READS['GetLibrarySnapshot']
        script = '''const assert=require('node:assert/strict');
const app={appid:10,display_name:'Game',sort_as:'game',app_type:1,gameid:'10',
minutes_playtime_forever:60,minutes_playtime_last_two_weeks:20,rt_last_time_played:123,
owner_account_id:'PRIVATE',per_client_data:{path:'PRIVATE'},
local_per_client_data:{installed:true,clientid:'PRIVATE',install_path:'PRIVATE'}};
global.window=global;global.appStore={allApps:[app]};
global.App={m_CurrentUser:{strSteamID:'76561198000000001',strAccountBalance:'PRIVATE'}};
global.collectionStore={allGamesCollection:{allApps:[app]}};
const value=eval(EXPRESSION);
assert.deepEqual(value,{apps:[[10,'Game','game',1,'10',60,20,123,true]],gameIds:[10],steamId:'76561198000000001'});
assert.equal(JSON.stringify(value).includes('PRIVATE'),false);
app.local_per_client_data.installed=false;
assert.equal(eval(EXPRESSION).apps[0][8],false);
delete app.local_per_client_data.installed;
assert.equal(eval(EXPRESSION).apps[0][8],null);
app.local_per_client_data=undefined;
assert.equal(eval(EXPRESSION).apps[0][8],null);
app.local_per_client_data={installed:'true'};
assert.equal(eval(EXPRESSION).apps[0][8],null);
appStore.allApps=Array(10001).fill(app);
assert.throws(()=>eval(EXPRESSION),/snapshot limit/);
appStore=undefined;
assert.throws(()=>eval(EXPRESSION),/library is unavailable/);
'''.replace('EXPRESSION',json.dumps(expression))
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_library_sized_plugin_arguments_remain_bounded(self):
        # Shotty sends appid/name pairs at startup; a normal library exceeds 8K.
        args=[{'allapps':[[id,'Game '+str(id)] for id in range(7000)]}]
        self.assertGreater(len(json.dumps(args)),128*1024)
        def fake_ssh(command, stdin, **_):
            import ast
            self.assertEqual(command,'python3 -')
            compile(stdin,'<large method>','exec')
            assignment=next(n for n in ast.parse(stdin).body if isinstance(n,ast.Assign) and
                any(isinstance(t,ast.Name) and t.id=='payload' for t in n.targets))
            self.assertEqual(json.loads(ast.literal_eval(assignment.value.args[0]))['args'],args)
            return '{"result":null}'
        with patch.object(framey_panel.frame_decky,'plugin_status',return_value={
                'plugins':[{'storeId':53,'name':'Shotty','sha256':RECEIPT}]}):
            self.assertEqual(framey_panel.call_method(fake_ssh,
                53,'set_id_map_fronend',args,True,RECEIPT),{'result':None})
        with self.assertRaisesRegex(framey_panel.PanelError,'too large'):
            framey_panel.call_method(lambda *a,**k:self.fail('Unexpected SSH'),
                53,'set_id_map_fronend',[{'allapps':'x'*(256*1024)}],True,RECEIPT)

    def test_steam_reads_have_the_headset_service_boundary(self):
        with patch.object(server,'HEADSET_RUNTIME',False), patch.dict(server.os.environ,{'FRAME_E2E_CONTAINER':'0'}):
            with self.assertRaises(server.Failure):server.framey_steam_action({'id':81,'method':'GetIPCountry'})
        with patch.object(server,'HEADSET_RUNTIME',True), patch.object(framey_panel,'read_steam',return_value={'result':'AU'}) as read:
            self.assertEqual(server.framey_steam_action({'id':81,'method':'GetIPCountry','receipt':RECEIPT}),{'result':'AU'})
            read.assert_called_once_with(server.ssh,81,'GetIPCountry',RECEIPT)

    def test_decky_event_queue_scope_bounds_expiry_and_reconnect(self):
        for name in ('framey_events.mjs', 'framey_event_parent.mjs', 'framey_terminal_events.mjs'):
            with self.subTest(script=name):
                result = subprocess.run(['node', str(Path(__file__).parent/'page'/name)],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_events_validate_before_ssh_and_resolve_name_from_store_receipt(self):
        def fake_ssh(command, stdin=None, **_):
            import shlex
            payload = json.loads(shlex.split(command)[2])
            self.assertEqual(payload, {'name':'Simple Timer', 'session':'test-123.45',
                                      'events':['timer:tick'], 'cursor':5})
            compile(stdin, '<event poll>', 'exec')
            self.assertIn('loader/plugin_event', stdin)
            return json.dumps({'events':[{'event':'timer:tick', 'args':[42]}], 'cursor':6})
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={
            'plugins':[{'storeId':96,'name':'Simple Timer','sha256':RECEIPT}]}):
            self.assertEqual(framey_panel.poll_events(fake_ssh, 96, 'test-123.45', ['timer:tick'], 5, RECEIPT)['cursor'], 6)
            with self.assertRaisesRegex(framey_panel.PanelError, 'changed'):
                framey_panel.poll_events(lambda *a,**k:self.fail('Stale poll reached SSH'),
                                         96,'test-123.45',['timer:tick'],5,'b'*64)
            for plugin_id, session, events, cursor in [
                (True,'test',['tick'],0), (96,'bad session',['tick'],0),
                (96,'test',['a']*33,0), (96,'test',['bad event'],0),
                (96,'test',[None],0), (96,'test',['tick'],-1),
                (96,'test',['tick'],True), (96,'test',['tick'],2**53),
                (19,'test',['tick'],0),
            ]:
                with self.subTest(plugin_id=plugin_id, session=session, events=events, cursor=cursor):
                    with self.assertRaises(framey_panel.PanelError):
                        framey_panel.poll_events(lambda *a, **k:self.fail('Unexpected SSH'),
                                                plugin_id, session, events, cursor, RECEIPT)

    def test_terminal_output_event_keeps_exact_name_and_receipt_owned_plugin(self):
        event = 'terminal_output#private-pty'
        def fake_ssh(command, stdin=None, **_):
            import shlex
            payload = json.loads(shlex.split(command)[2])
            self.assertEqual(payload, dict(name='Decky Terminal', session='private-session',
                                          events=[event], cursor=0))
            return json.dumps(dict(events=[dict(event=event, args=['private output'])], cursor=1))
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={
                'plugins':[dict(storeId=65, name='Decky Terminal', sha256=RECEIPT)]}):
            result = framey_panel.poll_events(fake_ssh, 65, 'private-session', [event], 0, RECEIPT)
        self.assertEqual(result['events'], [dict(event=event, args=['private output'])])

    def test_event_action_has_same_headset_boundary_as_methods(self):
        with patch.object(server, 'HEADSET_RUNTIME', False), patch.dict(server.os.environ, {'FRAME_E2E_CONTAINER':'0'}):
            with self.assertRaises(server.Failure):
                server.framey_events_action({'id':96,'session':'test','events':['tick']})
        with patch.object(server, 'HEADSET_RUNTIME', True), \
             patch.object(framey_panel, 'poll_events', return_value={'events':[], 'cursor':0}) as poll:
            self.assertEqual(server.framey_events_action({'id':96,'session':'test','events':['tick'],'receipt':RECEIPT})['events'], [])
            poll.assert_called_once_with(server.ssh, 96, 'test', ['tick'], 0, RECEIPT)

    def test_opaque_origin_plugin_cache_is_scoped_and_bounded(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_cache.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vr_store_browsing_and_search(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_store.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_plugin_quick_actions_and_settings(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_actions.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wine_cellar_socket_facade_uses_only_receipt_bound_calls(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_wine_socket.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.plugins = Path(tmp.name)/'plugins'
        self.folder = self.plugins/'protondb-decky'
        (self.folder/'dist').mkdir(parents=True)
        (self.folder/'.frame-control-store.json').write_text(json.dumps({'storeId':14,'version':'1.3.4','sha256':RECEIPT}))
        (self.folder/'plugin.json').write_text(json.dumps({'name':'ProtonDB Badges','api_version':2,'flags':[]}))
        (self.folder/'dist/index.js').write_text("export default () => ({content: SP_REACT.createElement('p', null, 'OK')});")
        home = patch.object(framey_panel, 'PLUGINS', self.plugins)
        home.start()
        self.addCleanup(home.stop)

    def test_owned_api_v2_bundle_is_embedded_without_ui_key(self):
        page = framey_panel.panel(14).decode()
        self.assertIn('framey-bundle', page)
        self.assertIn('/framey-runtime/host.js', page)
        self.assertIn('framey-toasts', page)
        self.assertNotIn('X-Frame-UI', page)
        self.assertNotIn('SP_REACT.createElement', page)  # bundled code is base64, not executable HTML.
        with self.assertRaises(FileNotFoundError):
            framey_panel.panel(15)

    def test_legacy_iife_is_admitted_without_api_manifest(self):
        (self.folder/'plugin.json').write_text(json.dumps({'name':'Legacy', 'flags':[]}))
        (self.folder/'dist/index.js').write_text(
            '(function(DFL, React){return DFL.definePlugin(serverAPI=>({content:React.createElement("p",null,"Legacy")}));})(DFL, SP_REACT);')
        self.assertIn('framey-bundle', framey_panel.panel(14).decode())
        (self.folder/'dist/index.js').write_text('window.unrecognized = true;')
        with self.assertRaises(FileNotFoundError):
            framey_panel.panel(14)

    def test_chunked_frontend_serves_only_owned_javascript(self):
        (self.folder/'dist/index.js').write_text(
            "import './chunks/view.js'; export default () => ({content: 'OK'});")
        chunks = self.folder/'dist/chunks'
        chunks.mkdir()
        (chunks/'view.js').write_text('export const title = "Settings";')
        page = framey_panel.panel(14).decode()
        self.assertIn(f'data-module="/framey/module/14/{RECEIPT}/index.js"', page)
        self.assertEqual(framey_panel.local_module(14, RECEIPT, 'chunks/view.js'),
                         b'export const title = "Settings";')
        for name in ('../plugin.json', 'chunks/../../plugin.json',
                     'chunks/view.js.map', 'other.js', 'chunks/%2e%2e/view.js'):
            with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                framey_panel.local_module(14, RECEIPT, name)
        (chunks/'linked.js').symlink_to(chunks/'view.js')
        with self.assertRaises(FileNotFoundError):
            framey_panel.local_module(14, RECEIPT, 'chunks/linked.js')
        with self.assertRaises(FileNotFoundError):
            framey_panel.local_module(15, RECEIPT, 'chunks/view.js')

    def test_chunked_panel_rejects_modules_from_a_replaced_store_receipt(self):
        (self.folder/'dist/index.js').write_text("import './chunks/view.js'; export default () => ({});")
        chunks = self.folder/'dist/chunks'
        chunks.mkdir()
        (chunks/'view.js').write_text('export const version = 1;')
        old_url = f'/framey/module/14/{RECEIPT}/chunks/view.js'
        self.assertIn(f'/framey/module/14/{RECEIPT}/index.js', framey_panel.panel(14).decode())
        self.assertEqual(framey_panel.local_module(14, RECEIPT, 'chunks/view.js'), b'export const version = 1;')
        (self.folder/'.frame-control-store.json').write_text(json.dumps({
            'storeId':14,'version':'2.0','sha256':'b'*64}))
        (chunks/'view.js').write_text('export const version = 2;')
        with self.assertRaisesRegex(FileNotFoundError, 'changed'):
            framey_panel.local_module(14, RECEIPT, 'chunks/view.js')
        self.assertEqual(framey_panel.local_module(14, 'b'*64, 'chunks/view.js'), b'export const version = 2;')
        self.assertNotIn(old_url, framey_panel.panel(14).decode())
        with self.assertRaises(FileNotFoundError):
            framey_panel.local_module(14, 'invalid', 'chunks/view.js')

    def test_legacy_keyword_rpc_is_scoped_and_validated(self):
        import shlex
        def fake_ssh(command, stdin=None, **_):
            import ast
            self.assertEqual(command,'python3 -')
            assignment=next(node for node in ast.parse(stdin).body if isinstance(node,ast.Assign) and
                any(isinstance(target,ast.Name) and target.id=='payload' for target in node.targets))
            payload=json.loads(ast.literal_eval(assignment.value.args[0]))
            self.assertEqual(payload, {'name':'Legacy', 'method':'read_setting',
                                      'args':[{'key':'mode'}], 'legacy':True})
            self.assertIn('loader/call_legacy_plugin_method', stdin)
            return json.dumps({'result':{'success':True, 'result':'dark'}})
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={
            'plugins':[{'storeId':14,'name':'Legacy','sha256':RECEIPT}]}):
            self.assertEqual(framey_panel.call_method(fake_ssh, 14, 'read_setting', [{'key':'mode'}], True, RECEIPT),
                             {'result':{'success':True, 'result':'dark'}})
            for args, legacy in [([],True), ([[]],True), ([{},{}],True), ([{}],'true')]:
                with self.assertRaises(framey_panel.PanelError):
                    framey_panel.call_method(fake_ssh, 14, 'read_setting', args, legacy, RECEIPT)

    def test_unsupported_root_symlink_and_unmanaged_are_refused(self):
        manifest = self.folder/'plugin.json'
        manifest.write_text(json.dumps({'name':'ProtonDB Badges','api_version':0}))
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)
        manifest.write_text(json.dumps({'name':'ProtonDB Badges','api_version':1}))
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)
        (self.folder/'dist/index.js').write_text(
            '// __DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit\n'
            "export default () => ({content: SP_REACT.createElement('p', null, 'OK')});")
        self.assertIn('framey-bundle', framey_panel.panel(14).decode())
        manifest.write_text(json.dumps({'name':'ProtonDB Badges','api_version':2,'flags':['root']}))
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)
        manifest.write_text(json.dumps({'name':'ProtonDB Badges','api_version':2,'flags':[]}))
        dist = self.folder/'dist'
        dist.rename(self.folder/'saved-dist')
        dist.symlink_to(self.folder/'saved-dist')
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)
        dist.unlink()
        (self.folder/'.frame-control-store.json').unlink()
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)

    def test_backend_method_is_scoped_to_store_receipt(self):
        def fake_ssh(command, stdin=None, **_):
            self.assertEqual(command, 'python3 -')
            compile(stdin, '<remote method>', 'exec')
            self.assertNotIn('__FRAMEY_METHOD_PAYLOAD__',stdin)
            return json.dumps({'result':{'theme':'dark'}})
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={
            'plugins':[{'storeId':14,'name':'ProtonDB Badges','sha256':RECEIPT}]}):
            self.assertEqual(framey_panel.call_method(fake_ssh,14,'get_setting',['theme','dark'],receipt=RECEIPT),
                             {'result':{'theme':'dark'}})
            with self.assertRaises(framey_panel.PanelError): framey_panel.call_method(fake_ssh,15,'get_setting',[],receipt=RECEIPT)
            with self.assertRaises(framey_panel.PanelError): framey_panel.call_method(fake_ssh,14,'x;alert(1)',[],receipt=RECEIPT)
            for stale in (None, 'b' * 64, 'invalid'):
                with self.subTest(stale=stale), self.assertRaisesRegex(framey_panel.PanelError, 'receipt|changed'):
                    framey_panel.call_method(lambda *a, **k:self.fail('Stale receipt reached SSH'),
                                             14,'get_setting',[],receipt=stale)
        compile(framey_panel.METHOD_SCRIPT.replace('__FRAMEY_METHOD_PAYLOAD__',repr('{}')), '<remote method>', 'exec')

    def test_headset_bundle_contains_runtime_and_licenses(self):
        packed = frame_headset.bundle()
        self.assertGreater(len(packed), 100_000)
        self.assertLess(len(packed), frame_headset.MAX_ARCHIVE)
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as archive:
            names = set(archive.getnames())
        self.assertTrue({'ui/framey_panel.py','ui/framey-host.js',
                         'ui/framey-events.js','ui/framey-running.js','ui/framey-downloads.js',
                         'ui/vendor/react-18.3.1.min.js','ui/vendor/react-dom-18.3.1.min.js',
                         'ui/vendor/REACT-LICENSE.txt','ui/vendor/REACT-DOM-LICENSE.txt'} <= names)

    def test_http_panel_is_sandboxable_and_missing_plugin_is_404(self):
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        def get(path):
            conn = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=5)
            try:
                conn.request('GET', path)
                reply = conn.getresponse()
                return reply.status, dict(reply.getheaders()), reply.read()
            finally:
                conn.close()
        status, headers, body = get('/framey/panel/14')
        self.assertEqual(status, 200)
        self.assertIn('blob:', headers['Content-Security-Policy'])
        self.assertIn(b'framey-bundle', body)
        self.assertEqual(get('/framey/panel/15')[0], 404)

        (self.folder/'dist/chunks').mkdir()
        (self.folder/'dist/chunks/view.js').write_text('export const value = 1;')
        status, headers, body = get(f'/framey/module/14/{RECEIPT}/chunks/view.js')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'null')
        self.assertEqual(body, b'export const value = 1;')
        self.assertEqual(get(f'/framey/module/14/{RECEIPT}/chunks/../plugin.json')[0], 404)
        self.assertEqual(get(f'/framey/module/15/{RECEIPT}/chunks/view.js')[0], 404)
        (self.folder/'.frame-control-store.json').write_text(json.dumps({
            'storeId':14,'version':'2.0','sha256':'b'*64}))
        self.assertEqual(get(f'/framey/module/14/{RECEIPT}/chunks/view.js')[0], 404)
        self.assertEqual(get(f'/framey/module/14/{"b"*64}/chunks/view.js')[0], 200)


if __name__ == '__main__':
    unittest.main()
