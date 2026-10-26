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
</script>'''


def render_panel(record, data):
    if hashlib.sha256(data).hexdigest() != record['sha256']:
        raise ValueError('Archive hash mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        bundle = archive.read(record['folder']+'/dist/index.js')
    # The audit supplies only digest-checked archive bytes, not an installed
    # receipt. Stub the receipt-bound lookup while using the shipped renderer.
    with patch.object(framey_panel, '_owned_dist', return_value=(None, bundle, record['sha256'])):
        return framey_panel.panel(record['id']).replace(
            b'<script id="framey-bundle"', PRELUDE.encode()+b'<script id="framey-bundle"')

PAGE = '''<!doctype html><meta charset=utf-8><title>Framey catalog frontend audit</title>
<h1>Framey catalog frontend audit</h1>
<p>Exact archived frontend code runs in an opaque iframe. All backend calls and network requests are denied.
Ready means initializer completion, not useful plugin behavior. No plugin backend executes.</p>
<button id=run>Run catalog</button> <button id=download>Download observations</button><p id=progress></p>
<iframe id=panel sandbox="allow-scripts" style="width:1100px;height:740px"></iframe>
<script>
const plugins=CATALOG_DATA, librarySnapshot=LIBRARY_DATA, runningSnapshot=RUNNING_DATA;
window.results=[];let active=null,running=false;
addEventListener('message',event=>{
  if(event.source!==panel.contentWindow||!active)return;
  const data=event.data;
  if(data.type==='audit:log'&&active.logs.length<8)active.logs.push({kind:data.kind,message:data.message.split('\\n')[0].slice(0,400)});
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
    event.source.postMessage({type:'framey:reply',id:data.id,error:'Read-only compatibility audit: backend method blocked'},'*');}
  if(data.type==='framey:cache:init')event.source.postMessage({type:'framey:cache:seed',session:data.session,entries:{}},'*');
});
window.runAudit=async(ids,settleMs=1200)=>{
  if(!Number.isInteger(settleMs)||settleMs<1200||settleMs>10000)throw Error('Invalid audit settle time');
  if(running)throw Error('Audit already running');running=true;run.disabled=true;
  try{for(const plugin of plugins.filter(plugin=>!ids||ids.includes(plugin.id))){
    active={id:plugin.id,name:plugin.name,ready:false,error:null,logs:[],methods:[],
      library:librarySnapshot?'snapshot replay':'unavailable',running:runningSnapshot?'snapshot replay':'unavailable'};
    progress.textContent=plugin.id+' '+plugin.name;panel.src='/panel/'+plugin.id;
    await new Promise(resolve=>setTimeout(resolve,settleMs));results.push(active);active=null;
    panel.src='about:blank';await new Promise(resolve=>setTimeout(resolve,30));
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
    parser.add_argument('--library-snapshot', type=Path,
                        help='Optional detached Steam library JSON; replay only, not live Steam/backend evidence')
    parser.add_argument('--running-snapshot', type=Path,
                        help='Optional detached running-app JSON; replay only, not live Steam/backend evidence')
    args = parser.parse_args()
    plugins = json.loads(args.catalog.read_text())['plugins']
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
                body = PAGE.replace('CATALOG_DATA', catalog).replace(
                    'LIBRARY_DATA', json.dumps(library).replace('<', '\\u003c')).replace(
                    'RUNNING_DATA', json.dumps(running).replace('<', '\\u003c')).encode()
            elif path.startswith('/panel/'):
                try:
                    record = records[int(path.split('/')[-1])]
                    data = (args.cache/(record['sha256']+'.zip')).read_bytes()
                    body = render_panel(record, data)
                except (KeyError, ValueError, OSError, zipfile.BadZipFile):
                    self.send_error(404, 'Verified frontend archive unavailable')
                    return
            elif path.startswith('/framey/module/'):
                try:
                    plugin_id, name = path.removeprefix('/framey/module/').split('/', 1)
                    if not framey_panel.MODULE_PATH.fullmatch(name):
                        raise ValueError('Invalid module path')
                    record = records[int(plugin_id)]
                    data = (args.cache/(record['sha256']+'.zip')).read_bytes()
                    if hashlib.sha256(data).hexdigest() != record['sha256']:
                        raise ValueError('Archive hash mismatch')
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        body = archive.read(record['folder']+'/dist/'+name)
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
