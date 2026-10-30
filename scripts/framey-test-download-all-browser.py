#!/usr/bin/env python3
"""Render the managed official panel against private Steam queue fixtures.

No Frame, real Steam, downloads or plugin backend is contacted. CSP blocks plugin network calls.
Requires a local Chromium-compatible browser; uses an owned temporary profile.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'ui')]
from test_frame_decky_store import StoreTransaction
from framey_official import PLUGINS, archive
import framey_panel
import frame_steam

PROBE = r'''
addEventListener('message',async event=>{
  if(event.source!==parent||event.data?.type!=='test:run')return;
  const wait=async read=>{const deadline=Date.now()+8000;while(Date.now()<deadline){
    if(read())return;await new Promise(resolve=>setTimeout(resolve,25));}throw Error('DOM condition timed out');};
  const button=name=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===name);
  const click=async name=>{await wait(()=>button(name)&&!button(name).disabled);button(name).click();};
  try{
    await click('Queue 2 Downloads');
    await wait(()=>document.getElementById('framey-toasts').textContent.includes('Submitted 2 downloads'));
    document.querySelector('#framey-toasts button').click();
    await click('All');await click('Queue 1 Download');
    await wait(()=>document.getElementById('framey-toasts').textContent.includes('Submitted 1 downloads'));
    document.querySelector('#framey-toasts button').click();
    parent.postMessage({type:'test:reset'},'*');
    await wait(()=>button('Queue 3 Downloads'));
    await click('Scheduled With Size Limit');
    await click('Queue 1 Download');
    await wait(()=>document.getElementById('framey-toasts').textContent.includes('Download queue stopped'));
    const last=document.querySelector('#framey-toasts section:last-child').textContent;
    if(!last.includes('Private SetQueueIndex failure'))throw Error('Missing partial-failure detail');
    parent.postMessage({type:'test:done',passed:true,scheduled:true,all:true,sizeLimit:true,partialFailure:true},'*');
  }catch(error){parent.postMessage({type:'test:done',passed:false,error:error.message},'*');}
});
'''

PARENT = r'''
const calls=[],listeners=new Set(),seen=[],failures=[];let failIndex=false,complete=false;
const row=(appid,size,queue_index=-1,deferred_time=10,completed=false)=>({appid,queue_index,deferred_time,completed,
  update_type_info:[{has_update:true,completed_update:false,progress:[{bytes_total:size}]}]});
const fresh=()=>[row(1,100*1024**2),row(2,6000*1024**2),row(3,5,0),row(4,1,-1,10,true),row(5,1*1024**2,-1,0)];
let rows=fresh();
const emit=()=>{for(const fn of listeners)fn(true,[{remote_client_id:'0',item_data:rows}]);};
window.SteamClient={Downloads:{
  RegisterForDownloadItems(fn){listeners.add(fn);emit();return {unregister:()=>listeners.delete(fn)};},
  QueueAppUpdate(id,remote){calls.push(['queue',id,remote]);rows.find(row=>row.appid===id).queue_index=99;emit();},
  SetQueueIndex(id,index,remote){calls.push(['index',id,index,remote]);if(failIndex)throw Error('Private SetQueueIndex failure');
    rows.find(row=>row.appid===id).queue_index=index;emit();},
  ResumeAppUpdate(id,remote){calls.push(['resume',id,remote]);},
}};
const bridge=BRIDGE_SOURCE;
addEventListener('message',async event=>{
  const target=document.getElementById('panel').contentWindow;
  if(event.source!==target)return;
  const req=event.data||{};
  seen.push([req.type,req.method??null]);
  if(!complete)document.getElementById('result').textContent=JSON.stringify({passed:false,state:'pending',seen,failures,calls});
  if(req.type==='framey:cache:init'){target.postMessage({type:'framey:cache:seed',session:req.session,entries:{}},'*');return;}
  if(req.type==='framey:ready'){target.postMessage({type:'test:run'},'*');return;}
  if(req.type==='framey:error'){document.getElementById('result').textContent=JSON.stringify({passed:false,error:req.message});return;}
  if(req.type==='test:reset'){rows=fresh();failIndex=true;emit();return;}
  if(req.type==='test:done'){
    complete=true;
    const expected=[['queue',1,'0'],['index',1,1,'0'],['queue',2,'0'],['index',2,2,'0'],['resume',3,'0'],
      ['queue',5,'0'],['index',5,3,'0'],['resume',3,'0'],['queue',1,'0'],['index',1,1,'0']];
    const exact=JSON.stringify(calls)===JSON.stringify(expected);
    document.getElementById('result').textContent=JSON.stringify({...req,passed:req.passed&&exact,calls,
      exactNativeCalls:exact,syntheticInput:true,realSteam:false});
    return;
  }
  if(req.type==='framey:downloads:close'){await bridge({session:req.session,action:'close'});return;}
  if(!['framey:call','framey:steam','framey:downloads'].includes(req.type))return;
  const reply={type:'framey:reply',id:req.id};
  try{
    if(req.type==='framey:downloads')reply.result=await bridge({session:req.session,action:req.method,
      appids:req.args[0]??null,revision:req.args[1]??null});
    else if(req.type==='framey:steam'&&req.method==='GetLibrarySnapshot')reply.result={apps:[],gameIds:[],steamId:null};
    else if(req.type==='framey:call'&&req.method==='log_from_ui')reply.result={success:true};
    else throw Error('Private fixture refuses other calls');
  }catch(error){reply.error=error.message;failures.push(error.message);}
  target.postMessage(reply,'*');
});
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    record = next(row for row in PLUGINS if row['id'] == 131)
    transaction = StoreTransaction()
    transaction.setUp()
    try:
        result = transaction.apply('install', archive(record), plugin_id=131,
                                   folder=record['folder'], version=record['version'])
        if result.returncode: raise RuntimeError(result.stderr)
        bundle = (transaction.folder.parent/record['folder']/'dist/index.js').read_bytes()
    finally:
        transaction.doCleanups()
    with patch.object(framey_panel, '_owned_dist', return_value=(None,bundle,record['sha256'])):
        panel = framey_panel.panel(131).decode()
    for route, name in [('react.js','vendor/react-18.3.1.min.js'),
                        ('react-dom.js','vendor/react-dom-18.3.1.min.js'), ('host.js','framey-host.js')]:
        data = base64.b64encode((ROOT/'ui'/name).read_bytes()).decode()
        panel = panel.replace(f'src="/framey-runtime/{route}"',f'src="data:text/javascript;base64,{data}"')
    panel = panel.replace('</html>','<script>'+PROBE+'</script></html>')
    parent = PARENT.replace('BRIDGE_SOURCE',(ROOT/'ui/framey-downloads.js').read_text())
    page = '''<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy"
content="default-src 'none'; script-src 'unsafe-inline' data: blob:; frame-src data:; style-src 'unsafe-inline'; img-src data:">
<title>Private Download All fixture</title><style>body{margin:0;background:#0d1925;color:white}iframe{width:1200px;height:950px;border:0}pre{white-space:pre-wrap}</style>
<iframe id="panel" sandbox="allow-scripts" src="data:text/html;base64,''' + base64.b64encode(panel.encode()).decode() + '''#fixture"></iframe>
<pre id="result">Pending</pre><script>''' + parent + '</script>'
    with tempfile.TemporaryDirectory(prefix='framey-download-browser-run-') as temporary:
        folder = Path(temporary)
        source = folder/'fixture.html'
        source.write_text(page)
        command = [str(args.browser.resolve()),'--headless','--disable-gpu','--no-first-run',
                   '--no-default-browser-check','--disable-background-networking','--user-data-dir='+str(folder/'profile'),
                   '--window-size=1240,1200','--remote-debugging-address=127.0.0.1',
                   '--remote-debugging-port=0',source.as_uri()]
        page = None
        with (folder/'browser.log').open('w+') as log:
            browser = subprocess.Popen(command,stdout=log,stderr=log)
            try:
                deadline = time.monotonic()+30
                report = {'passed':False,'error':'Browser fixture did not finish'}
                while time.monotonic() < deadline:
                    if browser.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read()[-1500:])
                    port = folder/'profile/DevToolsActivePort'
                    if page is None and port.is_file():
                        frame_steam.CDP = 'http://127.0.0.1:'+port.read_text().splitlines()[0]+'/json'
                        try: page = frame_steam.Page('Private Download All fixture')
                        except (OSError,frame_steam.Fail): pass
                    if page:
                        value = page.eval('document.getElementById("result")?.textContent')
                        if value and value != 'Pending':
                            report = json.loads(value)
                            if report.get('state') != 'pending': break
                    time.sleep(.1)
                if page:
                    page.next_id += 1
                    page._send(json.dumps({'id':page.next_id,'method':'Page.captureScreenshot','params':{'format':'png'}}))
                    while True:
                        shot = json.loads(page._recv())
                        if shot.get('id') == page.next_id: break
                    (args.output/'panel.png').write_bytes(base64.b64decode(shot['result']['data']))
            finally:
                if page: page.sock.close()
                browser.terminate()
                try: browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    browser.kill(); browser.wait(timeout=5)
        report.update({'plugin':record,'managedFrontendSha256':hashlib.sha256(bundle).hexdigest(),
                       'browser':subprocess.check_output([str(args.browser.resolve()),'--version'],text=True).strip()})
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
        if not report['passed']: raise SystemExit(1)


if __name__ == '__main__':
    main()
