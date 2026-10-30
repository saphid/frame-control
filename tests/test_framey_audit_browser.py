"""The local frontend audit still renders receipt-bound Framey panels."""
import sandbox  # noqa: F401
import base64
import hashlib
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


MODULE = Path(__file__).resolve().parents[1]/'scripts/framey-audit-browser.py'
spec = importlib.util.spec_from_file_location('framey_audit_browser', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ReceiptBoundAudit(unittest.TestCase):
    def test_speed_test_replay_is_opt_in_and_network_denied(self):
        default = audit.audit_prelude()
        self.assertIn("window.fetch=()=>Promise.reject(Error('Audit blocks plugin network'));", default)
        self.assertNotIn('speed.cloudflare.com', default)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the mock fetch check')
    def test_speed_test_replay_accepts_only_bounded_fixture_requests(self):
        script = r'''
const mark=stage=>console.error(`${performance.now().toFixed(1)}ms ${stage}`);
mark('node started');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const window={};
const source=fs.readFileSync(0,'utf8');
mark('fixture input read');
const context={window,URL,Response,DOMException,Uint8Array,setTimeout,Error,Number,Math,Promise};
mark('Response initialized');
vm.runInNewContext(source,context);
mark('fetch fixture installed');
(async()=>{
  assert.equal(await (await window.fetch('https://speed.cloudflare.com/cdn-cgi/trace')).text(),
    'colo=SYD\\n');
  mark('trace body read');
  const response=await window.fetch('https://speed.cloudflare.com/__down?bytes=999999999');
  assert.equal((await response.arrayBuffer()).byteLength,100000);
  mark('bounded download body read');
  assert.equal(await (await window.fetch('https://speed.cloudflare.com/__up',
    {method:'POST'})).text(),'ok');
  mark('upload body read');
  for(const [url,options] of [
    ['https://speed.cloudflare.com.evil/__down?bytes=10',{}],
    ['https://speed.cloudflare.com/unknown',{}],
    ['https://speed.cloudflare.com/__up',{method:'GET'}],
    ['https://example.com/__down?bytes=10',{}]]){
    await assert.rejects(window.fetch(url,options));
  }
  assert.deepEqual(JSON.parse(JSON.stringify(window.__speedTestMock)),
    {trace:1,down:1,up:1,other:4});
  mark('all assertions passed; resources='+JSON.stringify(process.getActiveResourcesInfo()));
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        try:
            result = subprocess.run(['node', '-e', script], input=audit.SPEED_TEST_FETCH,
                                    capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired as error:
            # Keep the deadline and expose the last completed boundary;
            # a timeout alone cannot identify startup, body reads, or shutdown.
            self.fail(f'Speed Test fixture exceeded {error.timeout}s; '
                      f'stdout={error.stdout!r}; stages={error.stderr!r}')
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browser reply check')
    def test_battery_tracker_fixture_uses_legacy_envelopes_and_rejects_other_calls(self):
        page_script = audit.PAGE.split('<script>', 1)[1].split('</script>', 1)[0]
        for old, new in [('CATALOG_DATA', '[{"id":67,"name":"Battery Tracker"}]'),
                         ('LIBRARY_DATA', 'null'), ('RUNNING_DATA', 'null'),
                         ('BATTERY_FIXTURE', 'true'), ('NETWORK_FIXTURE', 'false'),
                         ('NOTIFICATIONS_FIXTURE', 'false'), ('THEME_MUSIC_FIXTURE', 'false'),
                         ('WINE_FIXTURE', 'false'), ('WINE_STATE', 'null')]:
            page_script = page_script.replace(old, new)
        script = r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const messages=[],handlers={};
const context={
  panel:{src:'',contentWindow:{postMessage:(data)=>messages.push(data)}},
  run:{disabled:false},download:{},progress:{textContent:''},
  addEventListener:(type,handler)=>{handlers[type]=handler},
  setTimeout:(callback)=>{callback();return 1},
  URL,Blob,Number,Promise,JSON,Error,
};
context.window=context;
vm.runInNewContext(fs.readFileSync(0,'utf8'),context);
(async()=>{
  await context.runAudit([67],1200);
  assert.equal(context.panel.src,'/panel/67');
  function call(id,method,args,legacy=true){
    messages.length=0;
    handlers.message({source:context.panel.contentWindow,
      data:{type:'framey:call',id,method,args,legacy}});
    return messages.at(-1);
  }
  const history=call(1,'get_recent_data',[{lookback:5}]);
  assert.equal(history.result.success,true);
  assert.deepEqual(JSON.parse(JSON.stringify(history.result.result)),
    {x:[0.2,0.8],cap:[0.89,0.88],power_data:[{name:'Framey private',average_power:1.5}]});
  assert.equal(call(2,'set_app',[{app:'Framey private'}]).result.result,true);
  assert.match(call(3,'get_recent_data',[{lookback:8}]).error,/rejects backend method/);
  assert.match(call(4,'delete_all',[{}]).error,/rejects backend method/);
  assert.match(call(5,'get_recent_data',[{lookback:1}],false).error,/backend method blocked/);
  assert.deepEqual(JSON.parse(JSON.stringify(context.batteryFixtureCalls)),[
    {method:'get_recent_data',lookback:5},
    {method:'set_app',lookback:null},
    {method:'get_recent_data',lookback:8},
    {method:'delete_all',lookback:null},
  ]);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', script], input=page_script,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browser reply check')
    def test_network_sentinel_fixture_is_read_only_and_exact_plugin_scoped(self):
        page_script = audit.PAGE.split('<script>', 1)[1].split('</script>', 1)[0]
        for old, new in [('CATALOG_DATA', '[{"id":114,"name":"Network Sentinel"}]'),
                         ('LIBRARY_DATA', 'null'), ('RUNNING_DATA', 'null'),
                         ('BATTERY_FIXTURE', 'false'), ('NETWORK_FIXTURE', 'true'),
                         ('NOTIFICATIONS_FIXTURE', 'false'), ('THEME_MUSIC_FIXTURE', 'false'),
                         ('WINE_FIXTURE', 'false'), ('WINE_STATE', 'null')]:
            page_script = page_script.replace(old, new)
        script = r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const messages=[],handlers={};
const context={panel:{src:'',contentWindow:{postMessage:data=>messages.push(data)}},
  run:{disabled:false},download:{},progress:{textContent:''},
  addEventListener:(type,handler)=>{handlers[type]=handler},
  setTimeout:callback=>{callback();return 1},
  URL,Blob,Number,Promise,JSON,Error,Object};
context.window=context;
vm.runInNewContext(fs.readFileSync(0,'utf8'),context);
(async()=>{
  await context.runAudit([114],1200);
  assert.equal(context.panel.src,'/panel/114');
  function call(method,legacy=false){
    messages.length=0;
    handlers.message({source:context.panel.contentWindow,
      data:{type:'framey:call',id:1,method,args:[],legacy}});
    return messages.at(-1);
  }
  for(const method of ['get_network_status','get_live_ping','get_settings',
    'get_connection_info','get_network_history']){
    assert.ok(Object.hasOwn(call(method),'result'),method);
  }
  assert.equal(call('get_settings').result.auto_monitor,false);
  for(const method of ['start_monitoring','stop_monitoring','update_settings',
    'clear_history','test_single_ping','test_dns','scan_wifi_networks']){
    assert.match(call(method).error,/rejects backend method/,method);
  }
  assert.match(call('get_network_status',true).error,/backend method blocked/);
  assert.equal(context.networkFixtureCalls.length,13);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', script], input=page_script,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browser reply check')
    def test_decky_notifications_fixture_denies_trust_and_clear(self):
        page_script = audit.PAGE.split('<script>', 1)[1].split('</script>', 1)[0]
        for old, new in [('CATALOG_DATA', '[{"id":79,"name":"Decky Notifications"}]'),
                         ('LIBRARY_DATA', 'null'), ('RUNNING_DATA', 'null'),
                         ('BATTERY_FIXTURE', 'false'), ('NETWORK_FIXTURE', 'false'),
                         ('NOTIFICATIONS_FIXTURE', 'true'), ('THEME_MUSIC_FIXTURE', 'false'),
                         ('WINE_FIXTURE', 'false'), ('WINE_STATE', 'null')]:
            page_script = page_script.replace(old, new)
        script = r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const messages=[],handlers={};
const context={panel:{src:'',contentWindow:{postMessage:data=>messages.push(data)}},
  run:{disabled:false},download:{},progress:{textContent:''},
  addEventListener:(type,handler)=>{handlers[type]=handler},
  setTimeout:callback=>{callback();return 1},
  URL,Blob,Number,Promise,JSON,Error,Object};
context.window=context;
vm.runInNewContext(fs.readFileSync(0,'utf8'),context);
(async()=>{
  await context.runAudit([79],1200);
  assert.equal(context.panel.src,'/panel/79');
  function call(method,legacy=true){
    messages.length=0;
    handlers.message({source:context.panel.contentWindow,
      data:{type:'framey:call',id:1,method,args:[{}],legacy}});
    return messages.at(-1);
  }
  assert.equal(call('device_list').result.result[0].name,'Private test phone');
  assert.equal(call('notification_list').result.result[0].body,'Local fixture body');
  assert.equal(call('get_event').result.result,null);
  for(const method of ['trust_device','notifications_clear','unknown']){
    assert.match(call(method).error,/rejects backend method/,method);
  }
  assert.match(call('notification_list',false).error,/backend method blocked/);
  assert.deepEqual(JSON.parse(JSON.stringify(context.notificationsFixtureCalls)),
    ['device_list','notification_list','get_event','trust_device','notifications_clear','unknown']);
  assert.deepEqual(JSON.parse(JSON.stringify(context.notificationsFixtureDenied)),
    ['trust_device','notifications_clear','unknown']);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', script], input=page_script,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browser reply check')
    def test_theme_music_fixture_saves_only_private_settings(self):
        page_script = audit.PAGE.split('<script>', 1)[1].split('</script>', 1)[0]
        for old, new in [('CATALOG_DATA', '[{"id":52,"name":"Game Theme Music"}]'),
                         ('LIBRARY_DATA', 'null'), ('RUNNING_DATA', 'null'),
                         ('BATTERY_FIXTURE', 'false'), ('NETWORK_FIXTURE', 'false'),
                         ('NOTIFICATIONS_FIXTURE', 'false'), ('THEME_MUSIC_FIXTURE', 'true'),
                         ('WINE_FIXTURE', 'false'), ('WINE_STATE', 'null')]:
            page_script = page_script.replace(old, new)
        script = r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const messages=[],handlers={};
const context={panel:{src:'',contentWindow:{postMessage:data=>messages.push(data)}},
  run:{disabled:false},download:{},progress:{textContent:''},
  addEventListener:(type,handler)=>{handlers[type]=handler},
  setTimeout:callback=>{callback();return 1},
  URL,Blob,Number,Promise,JSON,Error,Object,Array,structuredClone};
context.window=context;
vm.runInNewContext(fs.readFileSync(0,'utf8'),context);
(async()=>{
  await context.runAudit([52],1200);
  assert.equal(context.panel.src,'/panel/52');
  function call(method,args,legacy=false){
    messages.length=0;
    handlers.message({source:context.panel.contentWindow,
      data:{type:'framey:call',id:1,method,args,legacy}});
    return messages.at(-1);
  }
  const initial={defaultMuted:false,useYtDlp:false,downloadAudio:false,
    invidiousInstance:'https://inv.tux.pizza',volume:1};
  assert.deepEqual(call('get_setting',['settings',initial]).result,initial);
  const changed={...initial,volume:0.4,defaultMuted:true};
  assert.equal(call('set_setting',['settings',changed]).result,null);
  changed.volume=0.9; // Fixture must retain a detached copy.
  assert.equal(call('get_setting',['settings',initial]).result.volume,0.4);
  for(const [method,args,legacy] of [
    ['set_setting',['settings',{...initial,volume:2}],false],
    ['set_setting',['other',initial],false],
    ['get_setting',['settings',initial],true],
    ['download_audio',[],false],
    ['search',[],false]])
    assert.match(call(method,args,legacy).error,/blocked|rejects backend method/);
  assert.equal(context.themeMusicFixtureState.volume,0.4);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', script], input=page_script,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_digest_checked_archive_renders_without_installed_plugin(self):
        bundle = b"import './chunks/frontend.js';"
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('Example/dist/index.js', bundle)
            archive.writestr('Example/dist/chunks/frontend.js', b'export const ready = true;')
        data = stream.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        record = {'id':42, 'folder':'Example', 'sha256':digest}
        page = audit.render_panel(record, data)
        self.assertIn(base64.b64encode(bundle), page)
        self.assertIn(f'/framey/module/42/{digest}/index.js'.encode(), page)
        self.assertIn(b'const report=(kind,message)', page)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit.render_panel({**record, 'sha256':'0'*64}, data)
        with self.assertRaisesRegex(ValueError, 'requires plugin 118'):
            audit.render_panel(record, data, speed_test_mock=True)

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache/(digest+'.zip')).write_bytes(data)
            records = {42:record}
            route = f'/framey/module/42/{digest}/'
            self.assertEqual(audit.read_module_asset(route+'index.js', records, cache), bundle)
            self.assertEqual(audit.read_module_asset(route+'chunks/frontend.js', records, cache),
                             b'export const ready = true;')
            for bad in (f'/framey/module/42/{"0"*64}/index.js',
                        route+'chunks/../frontend.js', route+'other.json',
                        f'/framey/module/042/{digest}/index.js'):
                with self.subTest(bad=bad), self.assertRaises((ValueError, KeyError)):
                    audit.read_module_asset(bad, records, cache)
            (cache/(digest+'.zip')).write_bytes(data+b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                audit.read_module_asset(route+'index.js', records, cache)
