#!/usr/bin/env python3
"""Serve exact official frontends to a local Chromium audit, with all actions denied.

Open the printed loopback URL with T3's collaborative browser. Run `runAudit()`
in the page, then inspect `results` or download its JSON. This is initialization
evidence only. No official Python/native backend is imported or executed.
"""
import argparse
import hashlib
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ui'))
import framey_panel

PRELUDE = '''<script>
const report=(kind,message)=>parent.postMessage({type:'audit:log',kind,message:String(message)},'*');
addEventListener('error',event=>report('error',event.message));
addEventListener('unhandledrejection',event=>report('rejection',event.reason?.stack||event.reason));
for(const key of ['error','warn']){const original=console[key];console[key]=(...args)=>{
  report(key,args.map(String).join(' '));original(...args);};}
window.fetch=()=>Promise.reject(Error('Audit blocks plugin network'));
window.WebSocket=class{constructor(){throw Error('Audit blocks WebSocket');}};
addEventListener('message', event=>{
  if(event.source!==parent||event.data?.type!=='audit:inspect')return;
  parent.postMessage({type:'audit:snapshot',text:(document.getElementById('framey-root')?.innerText||'').slice(0,2000)},'*');
});
</script>'''

# Opt-in replay for the exact Speed Test frontend. Fetch is replaced before the
# official bundle loads; CSP still denies every network connection. Keep the
# ordinary 116-plugin audit network-denied by default.
SPEED_TEST_FETCH = r'''window.__speedTestMock={trace:0,down:0,up:0,other:0};
window.fetch=async(input,options={})=>{
  const url=new URL(String(input));
  if(url.origin!=='https://speed.cloudflare.com'){
    window.__speedTestMock.other++;
    throw Error('Mock rejects external request');
  }
  if(options.signal?.aborted)throw new DOMException('Aborted','AbortError');
  await new Promise(resolve=>setTimeout(resolve,12));
  if(url.pathname==='/cdn-cgi/trace'){
    window.__speedTestMock.trace++;
    return new Response('colo=SYD\\n',{status:200});
  }
  if(url.pathname==='/__down'){
    window.__speedTestMock.down++;
    const bytes=Math.max(0,Math.min(Number(url.searchParams.get('bytes'))||0,100000));
    return new Response(new Uint8Array(bytes),{status:200});
  }
  if(url.pathname==='/__up'&&options.method==='POST'){
    window.__speedTestMock.up++;
    return new Response('ok',{status:200});
  }
  window.__speedTestMock.other++;
  throw Error('Mock rejects unknown Speed Test request');
};'''


def audit_prelude(speed_test_mock=False):
    if not speed_test_mock:
        return PRELUDE
    return PRELUDE.replace(
        "window.fetch=()=>Promise.reject(Error('Audit blocks plugin network'));",
        SPEED_TEST_FETCH)


def render_panel(record, data, speed_test_mock=False):
    if hashlib.sha256(data).hexdigest() != record['sha256']:
        raise ValueError('Archive hash mismatch')
    if speed_test_mock and record['id'] != 118:
        raise ValueError('Speed Test mock requires plugin 118')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        bundle = archive.read(record['folder']+'/dist/index.js')
    # The audit supplies only digest-checked archive bytes, not an installed
    # receipt. Stub the receipt-bound lookup while using the shipped renderer.
    with patch.object(framey_panel, '_owned_dist', return_value=(None, bundle, record['sha256'])):
        return framey_panel.panel(record['id']).replace(
            b'<script id="framey-bundle"', audit_prelude(speed_test_mock).encode()+b'<script id="framey-bundle"')


def read_module_asset(path, records, cache):
    """Serve the same receipt-bound module URL shape as the installed panel."""
    prefix = '/framey/module/'
    if not path.startswith(prefix):
        raise ValueError('Invalid module path')
    parts = path[len(prefix):].split('/', 2)
    if len(parts) != 3 or not re.fullmatch(r'[1-9][0-9]*', parts[0]):
        raise ValueError('Invalid plugin ID')
    plugin_id, receipt, name = parts
    if not framey_panel.RECEIPT.fullmatch(receipt) or not framey_panel.MODULE_PATH.fullmatch(name):
        raise ValueError('Invalid module receipt or path')
    record = records[int(plugin_id)]
    if receipt != record['sha256']:
        raise ValueError('Plugin receipt changed')
    data = (cache/(receipt+'.zip')).read_bytes()
    if hashlib.sha256(data).hexdigest() != receipt:
        raise ValueError('Archive hash mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read(record['folder']+'/dist/'+name)

PAGE = '''<!doctype html><meta charset=utf-8><title>Framey catalog frontend audit</title>
<h1>Framey catalog frontend audit</h1>
<p>Exact archived frontend code runs in an opaque iframe. All backend calls and network requests are denied.
Ready means initializer completion, not useful plugin behavior. No plugin backend executes.</p>
<button id=run>Run catalog</button> <button id=download>Download observations</button><p id=progress></p>
<iframe id=panel sandbox="allow-scripts" style="width:1100px;height:740px"></iframe>
<script>
const plugins=CATALOG_DATA, librarySnapshot=LIBRARY_DATA, runningSnapshot=RUNNING_DATA;
const batteryFixture=BATTERY_FIXTURE, networkFixture=NETWORK_FIXTURE,
  notificationsFixture=NOTIFICATIONS_FIXTURE;
window.batteryFixtureCalls=[];window.networkFixtureCalls=[];
window.notificationsFixtureCalls=[];window.notificationsFixtureDenied=[];
window.results=[];let active=null,running=false;
addEventListener('message',event=>{
  if(event.source!==panel.contentWindow||!active)return;
  const data=event.data;
  if(data.type==='audit:log'&&active.logs.length<8)active.logs.push({kind:data.kind,message:data.message.split('\\n')[0].slice(0,400)});
  if(data.type==='audit:snapshot')active.rootText=String(data.text).slice(0,2000);
  if(data.type==='framey:error')active.error=String(data.message).slice(0,500);
  if(data.type==='framey:ready')active.ready=true;
  if(data.type==='framey:events')event.source.postMessage({type:'framey:reply',id:data.id,result:{events:[],cursor:0}},'*');
  if(data.type==='framey:running')event.source.postMessage({type:'framey:reply',id:data.id,
    ...(runningSnapshot?{result:runningSnapshot}:{error:'Read-only compatibility audit: live running context blocked'})},'*');
  if(data.type==='framey:steam')event.source.postMessage({type:'framey:reply',id:data.id,
    ...(data.method==='GetLibrarySnapshot'&&librarySnapshot?
      {result:librarySnapshot}:{error:'Read-only compatibility audit: live Steam API blocked'})},'*');
  if(data.type==='framey:call'){
    if(!active.methods.includes(data.method))active.methods.push(data.method);
    if(batteryFixture&&active.id===67&&data.legacy){
      const lookback=data.args?.[0]?.lookback;
      if(window.batteryFixtureCalls.length<20)
        window.batteryFixtureCalls.push({method:data.method,lookback:lookback??null});
      const result=data.method==='get_recent_data'&&Number.isInteger(lookback)&&lookback>=1&&lookback<=7?
        {success:true,result:{x:[0.2,0.8],cap:[0.89,0.88],
          power_data:[{name:'Framey private',average_power:1.5}]}}:
        data.method==='set_app'?{success:true,result:true}:null;
      event.source.postMessage({type:'framey:reply',id:data.id,
        ...(result?{result}:{error:'Private Battery Tracker fixture rejects backend method'})},'*');
    }else if(networkFixture&&active.id===114&&!data.legacy){
      if(window.networkFixtureCalls.length<30)window.networkFixtureCalls.push(data.method);
      const fixtures={
        get_network_status:{quality:{quality:'good',score:80,avg_latency:18,
          avg_packet_loss:0,jitter:1},monitoring:false,data_points:0,
          bandwidth:{download_bps:0,upload_bps:0},dns_status:null},
        get_live_ping:18,
        get_settings:{auto_monitor:false,ping_interval:0.5,speed_unit:'mbps'},
        get_connection_info:{hostname:'framey-fixture',local_ip:'192.0.2.1',connection_type:'wifi'},
        get_network_history:[]};
      event.source.postMessage({type:'framey:reply',id:data.id,
        ...(Object.hasOwn(fixtures,data.method)?{result:fixtures[data.method]}:
          {error:'Private Network Sentinel fixture rejects backend method'})},'*');
    }else if(notificationsFixture&&active.id===79&&data.legacy){
      if(window.notificationsFixtureCalls.length<30)window.notificationsFixtureCalls.push(data.method);
      const fixtures={
        device_list:[{deviceId:'fixture-phone',name:'Private test phone',type:'phone',is_trusted:1}],
        notification_list:[{id:'fixture-note',title:'Private test alert',body:'Local fixture body',
          appName:'Framey fixture',silent:true,icon:null}],
        get_event:null};
      if(!Object.hasOwn(fixtures,data.method)&&window.notificationsFixtureDenied.length<20)
        window.notificationsFixtureDenied.push(data.method);
      event.source.postMessage({type:'framey:reply',id:data.id,
        ...(Object.hasOwn(fixtures,data.method)?{result:{success:true,result:fixtures[data.method]}}:
          {error:'Private Decky Notifications fixture rejects backend method'})},'*');
    }else event.source.postMessage({type:'framey:reply',id:data.id,
      error:'Read-only compatibility audit: backend method blocked'},'*');}
  if(data.type==='framey:cache:init')event.source.postMessage({type:'framey:cache:seed',session:data.session,entries:{}},'*');
});
window.runAudit=async(ids,settleMs=1200)=>{
  if(!Number.isInteger(settleMs)||settleMs<1200||settleMs>10000)throw Error('Invalid audit settle time');
  if(running)throw Error('Audit already running');running=true;run.disabled=true;
  try{for(const plugin of plugins.filter(plugin=>!ids||ids.includes(plugin.id))){
    active={id:plugin.id,name:plugin.name,ready:false,error:null,logs:[],methods:[],rootText:'',
      library:librarySnapshot?'snapshot replay':'unavailable',running:runningSnapshot?'snapshot replay':'unavailable'};
    progress.textContent=plugin.id+' '+plugin.name;panel.src='/panel/'+plugin.id;
    await new Promise(resolve=>setTimeout(resolve,settleMs));
    // Detached Steam snapshots may contain personal library data. Keep text
    // observations out of reports that replay either snapshot.
    if(!librarySnapshot&&!runningSnapshot)panel.contentWindow.postMessage({type:'audit:inspect'},'*');
    await new Promise(resolve=>setTimeout(resolve,80));
    results.push(active);
    if(!batteryFixture&&!networkFixture&&!notificationsFixture){active=null;panel.src='about:blank';await new Promise(resolve=>setTimeout(resolve,30));}
  }}finally{running=false;run.disabled=false;progress.textContent='Done: '+results.length;}
  return results;
};
run.onclick=()=>runAudit();
download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(results,null,2)],{type:'application/json'}));
  const anchor=document.createElement('a');anchor.href=url;anchor.download='framey-browser-audit.json';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
</script>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, default=ROOT/'ui/framey-compatibility.json')
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--speed-test-mock', action='store_true',
                        help='Replay only plugin 118 with bounded in-memory Cloudflare responses')
    parser.add_argument('--battery-tracker-fixture', action='store_true',
                        help='Replay only plugin 67 with private in-memory battery history')
    parser.add_argument('--network-sentinel-fixture', action='store_true',
                        help='Replay only plugin 114 with bounded synthetic read-only network status')
    parser.add_argument('--decky-notifications-fixture', action='store_true',
                        help='Replay only plugin 79 with private in-memory notification and device data')
    parser.add_argument('--library-snapshot', type=Path,
                        help='Optional detached Steam library JSON; replay only, not live Steam/backend evidence')
    parser.add_argument('--running-snapshot', type=Path,
                        help='Optional detached running-app JSON; replay only, not live Steam/backend evidence')
    args = parser.parse_args()
    if sum((args.speed_test_mock, args.battery_tracker_fixture,
            args.network_sentinel_fixture, args.decky_notifications_fixture)) > 1:
        parser.error('Choose one frontend fixture')
    plugins = json.loads(args.catalog.read_text())['plugins']
    if args.speed_test_mock:
        plugins = [plugin for plugin in plugins if plugin['id'] == 118]
        if len(plugins) != 1:
            parser.error('Speed Test 118 missing from catalog')
    if args.battery_tracker_fixture:
        plugins = [plugin for plugin in plugins if plugin['id'] == 67]
        if (len(plugins) != 1 or plugins[0]['sha256'] !=
                '91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94'):
            parser.error('Battery Tracker 0.2.0 fixture requires its pinned archive digest')
    if args.network_sentinel_fixture:
        plugins = [plugin for plugin in plugins if plugin['id'] == 114]
        if (len(plugins) != 1 or plugins[0]['sha256'] !=
                'd3e07f40a0c800e72d15594e03c8c61e9bf3092524a578a0260520e735b971a5'):
            parser.error('Network Sentinel 1.0.4 fixture requires its pinned archive digest')
    if args.decky_notifications_fixture:
        plugins = [plugin for plugin in plugins if plugin['id'] == 79]
        if (len(plugins) != 1 or plugins[0]['sha256'] !=
                '3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312'):
            parser.error('Decky Notifications 1.0.1 fixture requires its pinned archive digest')
    records = {p['id']: p for p in plugins}
    library = None
    if args.library_snapshot:
        raw = args.library_snapshot.read_bytes()
        if len(raw) > 2*1024*1024:
            parser.error('library snapshot exceeds 2 MiB')
        library = json.loads(raw)
    running = None
    if args.running_snapshot:
        raw = args.running_snapshot.read_bytes()
        if len(raw) > 256*1024:
            parser.error('running snapshot exceeds 256 KiB')
        running = json.loads(raw)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            path = self.path.split('?')[0]
            content_type = 'text/html; charset=utf-8'
            module_asset = False
            if path == '/':
                # Only names/IDs are needed by the UI; never embed raw executable source.
                catalog = json.dumps([{'id': p['id'], 'name': p['name']} for p in plugins]).replace('<', '\\u003c')
                page = PAGE.replace('CATALOG_DATA', catalog)
                if args.speed_test_mock:
                    page = page.replace('All backend calls and network requests are denied.',
                                        'Backend calls are denied. Speed Test uses bounded in-memory fixtures; CSP blocks network.')
                if args.battery_tracker_fixture:
                    page = page.replace('All backend calls and network requests are denied.',
                                        'Battery Tracker uses private in-memory history; CSP blocks network. The panel stays open for slider checks.')
                if args.network_sentinel_fixture:
                    page = page.replace('All backend calls and network requests are denied.',
                                        'Network Sentinel uses synthetic read-only status; CSP blocks network and all writes. The panel stays open for navigation checks.')
                if args.decky_notifications_fixture:
                    page = page.replace('All backend calls and network requests are denied.',
                                        'Decky Notifications uses private in-memory data; CSP blocks network and backend writes. The panel stays open for display checks.')
                page = page.replace('BATTERY_FIXTURE', 'true' if args.battery_tracker_fixture else 'false')
                page = page.replace('NETWORK_FIXTURE', 'true' if args.network_sentinel_fixture else 'false')
                page = page.replace('NOTIFICATIONS_FIXTURE', 'true' if args.decky_notifications_fixture else 'false')
                body = page.replace(
                    'LIBRARY_DATA', json.dumps(library).replace('<', '\\u003c')).replace(
                    'RUNNING_DATA', json.dumps(running).replace('<', '\\u003c')).encode()
            elif path.startswith('/panel/'):
                try:
                    record = records[int(path.split('/')[-1])]
                    data = (args.cache/(record['sha256']+'.zip')).read_bytes()
                    body = render_panel(record, data, args.speed_test_mock)
                except (KeyError, ValueError, OSError, zipfile.BadZipFile):
                    self.send_error(404, 'Verified frontend archive unavailable')
                    return
            elif path.startswith('/framey/module/'):
                try:
                    body = read_module_asset(path, records, args.cache)
                    content_type = 'text/javascript; charset=utf-8'
                    module_asset = True
                except (KeyError, ValueError, OSError, zipfile.BadZipFile):
                    self.send_error(404, 'Verified frontend module unavailable')
                    return
            else:
                files = {'/framey-runtime/react.js': 'ui/vendor/react-18.3.1.min.js',
                         '/framey-runtime/react-dom.js': 'ui/vendor/react-dom-18.3.1.min.js',
                         '/framey-runtime/host.js': 'ui/framey-host.js'}
                if path not in files:
                    self.send_error(404)
                    return
                body = (ROOT/files[path]).read_bytes()
                content_type = 'text/javascript'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            if module_asset:
                self.send_header('Access-Control-Allow-Origin', 'null')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline' blob:; style-src 'unsafe-inline'; img-src data:; frame-src 'self'; connect-src 'none'")
            self.end_headers()
            self.wfile.write(body)

    print(f'Frontend audit: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
