"""Private browser -> actual native Terminal RPC/events in an owned VM only."""
import asyncio
import base64
from collections import deque
import hashlib
import http.server
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import websockets

sys.path.insert(0, '/repo/ui')
import frame_steam

COMMAND = "printf 'framey-browser-terminal\\n' > framey-browser-terminal-marker; stty size; printf 'framey-browser-output\\n'\n"
PROBE = r'''
const errors=[];
addEventListener('error',e=>errors.push(e.message));
addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
addEventListener('securitypolicyviolation',e=>errors.push('CSP '+e.violatedDirective));
const wait=async fn=>{const end=Date.now()+60000;while(Date.now()<end){if(fn())return;
 await new Promise(resolve=>setTimeout(resolve,100));}throw Error('Terminal DOM timed out');};
const text=()=>document.getElementById('framey-root').innerText;
const stage=name=>parent.postMessage({type:'test:stage',stage:name,text:text().slice(0,3000),errors},'*');
let busy=false;
addEventListener('message',async e=>{
 if(e.source!==parent||e.data?.type!=='test:advance'||busy)return;busy=true;
 try{
  if(e.data.action==='create'){
   await wait(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Add Terminal')));
   [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Add Terminal')).click();
   await wait(()=>document.querySelector('section button'));
   document.querySelector('section button').click();
   await wait(()=>document.querySelector('.xterm-helper-textarea'));
   await new Promise(resolve=>setTimeout(resolve,1500));stage('terminal');
  }else if(e.data.action==='input'){
   const field=document.querySelector('.xterm-helper-textarea');if(!field)throw Error('No xterm textarea');
   field.focus();const data=new DataTransfer();data.setData('text/plain',e.data.command);
   field.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));
   await new Promise(resolve=>setTimeout(resolve,2500));stage('output');
  }else if(e.data.action==='close'){
   const back=[...document.querySelectorAll('button')].find(b=>b.textContent==='Back to plugin');
   if(!back)throw Error('No route back button');back.click();
   await wait(()=>document.querySelectorAll('section button').length===2);
   document.querySelectorAll('section button')[1].click();
   await wait(()=>document.querySelectorAll('section button').length===0);stage('removed');
  }
 }catch(error){parent.postMessage({type:'test:failure',error:String(error)},'*');}
 finally{busy=false;}
});
'''
PARENT = r'''
let ready=false;window.stage=null;window.errors=[];
const child=()=>document.getElementById('panel').contentWindow;
addEventListener('error',e=>errors.push(e.message));
addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
addEventListener('message',async e=>{
 if(e.source!==child())return;const r=e.data||{};
 if(r.type==='framey:ready'){ready=true;return;}
 if(r.type==='framey:error'){window.failure=String(r.message).slice(0,1000);return;}
 if(r.type==='test:stage'){window.stage=r;return;}
 if(r.type==='test:failure'){window.failure=r.error;return;}
 if(r.type==='framey:cache:init'){child().postMessage({type:'framey:cache:seed',session:r.session,entries:{}},'*');return;}
 if(!['framey:call','framey:events'].includes(r.type))return;
 try{
  const response=await fetch(r.type==='framey:call'?'/rpc':'/events',{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(r)});
  if(!response.ok)throw Error('Private bridge status '+response.status);
  const value=await response.json();child().postMessage({type:'framey:reply',id:r.id,result:value},'*');
 }catch(error){window.failure=String(error);}
});
window.advance=(action,command)=>{window.stage=null;child().postMessage({type:'test:advance',action,command},'*');};
'''


class Bridge:
    def __init__(self, name):
        self.name = name
        self.sequence = self.cursor = 0
        self.pending, self.events, self.calls, self.delivered = {}, deque(maxlen=64), [], []
        self.failures = []
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        assert self.ready.wait(15), 'Decky event connection timed out'
        assert self.error is None, self.error

    def run(self):
        try:
            asyncio.run(self.connect())
        except BaseException as error:
            self.error = str(error)
            self.ready.set()

    async def connect(self):
        self.loop = asyncio.get_running_loop()
        token = urllib.request.urlopen('http://127.0.0.1:1337/auth/token', timeout=2).read().decode()
        # Browser WebSocket has no application-initiated automatic ping loop.
        async with websockets.connect('ws://127.0.0.1:1337/ws?auth='+token,
                                      ping_interval=None, close_timeout=2) as self.ws:
            self.ready.set()
            async for raw in self.ws:
                response = json.loads(raw)
                if response.get('type') == 5 and response.get('event') == 'loader/plugin_event':
                    event = response['args'][0]
                    if event['plugin'] == self.name:
                        assert len(json.dumps(event)) <= 8192
                        with self.lock:
                            self.cursor += 1
                            self.events.append(dict(sequence=self.cursor, event=event['event'], args=event['args']))
                elif response.get('id') in self.pending:
                    future = self.pending.pop(response['id'])
                    await self.ws.send(json.dumps(dict(type=3, id=response['id'])))
                    if response.get('type') == 1:
                        future.set_result(response['result'])
                    else:
                        future.set_exception(RuntimeError(str(response)))

    async def invoke(self, method, args):
        self.sequence += 1
        request_id = self.sequence
        future = self.loop.create_future()
        self.pending[request_id] = future
        await self.ws.send(json.dumps(dict(type=0, id=request_id,
            route='loader/call_plugin_method', args=[self.name, method, *args])))
        return await asyncio.wait_for(future, 8)

    def call(self, method, args):
        allowed = {'get_terminals','create_terminal','remove_terminal','get_terminal',
            'get_config','subscribe_terminal','unsubscribe_terminal','send_terminal_buffer',
            'change_terminal_window_size','set_terminal_title','send_terminal_input'}
        assert method in allowed and isinstance(args, list) and len(args) <= 3
        if method == 'send_terminal_input':
            assert len(args) == 2 and args[1] in (COMMAND, COMMAND.replace('\n','\r'))
        if method == 'change_terminal_window_size':
            assert len(args) == 3 and all(type(v) is int for v in args[1:])
            assert 1 <= args[1] <= 200 and 1 <= args[2] <= 1000
        result = asyncio.run_coroutine_threadsafe(self.invoke(method,args),self.loop).result(12)
        with self.lock:
            assert len(self.calls) < 200
            self.calls.append(dict(method=method,args=args,result=result))
        return result

    def poll(self, args):
        assert len(args) == 2 and isinstance(args[0], list) and len(args[0]) <= 32
        names, cursor = args
        assert type(cursor) is int and 0 <= cursor <= self.cursor
        assert all(isinstance(n,str) and n.startswith('terminal_output#') and len(n)<=128 for n in names)
        with self.lock:
            events = [v for v in self.events if v['sequence']>cursor and v['event'] in names]
            self.delivered.extend(events)
            assert len(self.delivered) <= 200
            return dict(events=events,cursor=self.cursor)

    def close(self):
        if self.thread.is_alive() and hasattr(self, 'ws'):
            asyncio.run_coroutine_threadsafe(self.ws.close(),self.loop).result(8)
        self.thread.join(8)
        assert not self.thread.is_alive() and self.error is None, self.error


def screenshot(page):
    page.next_id += 1
    page._send(json.dumps(dict(id=page.next_id,method='Page.captureScreenshot',params=dict(format='png'))))
    while True:
        response=json.loads(page._recv())
        if response.get('id')==page.next_id:
            return response['result']['data']


def exercise(name, home):
    assert os.getuid()==1100 and home==Path('/home/tester')
    assert Path('/framey-owned-vm').read_text()=='Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    bridge=Bridge(name)
    policy="<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; script-src 'unsafe-inline' data: blob:; connect-src 'none'; style-src 'unsafe-inline'; img-src data:\">"
    panel=Path('/input/terminal-panel.html').read_text().replace('<html lang="en">','<html lang="en">'+policy)
    panel=panel.replace('</html>','<script>'+PROBE+'</script></html>')
    # The data-URL child inherits this policy as well as its own policy. Allow
    # its embedded runtime and blob module, as in the signed-package browser
    # fixture; the child still denies all connections and stays opaque.
    document='''<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' data: blob:; frame-src data:; connect-src 'self'; style-src 'unsafe-inline'; img-src data:"><title>Owned Terminal actual backend</title><style>body{margin:0;background:#0d1925;color:white}iframe{width:1200px;height:1000px;border:0}</style><iframe id="panel" sandbox="allow-scripts" src="data:text/html;base64,'''+base64.b64encode(panel.encode()).decode()+'''#fixture"></iframe><script>'''+PARENT+'</script>'
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            if self.path!='/':self.send_error(404);return
            data=document.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'));assert 0<length<=32768
                request=json.loads(self.rfile.read(length))
                assert request.get('legacy') is False
                if self.path=='/rpc':value=bridge.call(request['method'],request['args'])
                elif self.path=='/events':value=bridge.poll(request['args'])
                else:raise ValueError('Unknown private route')
                data=json.dumps(value).encode();self.send_response(200)
            except BaseException as error:
                if len(bridge.failures)<10:
                    bridge.failures.append(dict(path=self.path,error=type(error).__name__+': '+str(error)[:1000]))
                data=json.dumps(dict(error=str(error))).encode();self.send_response(500)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    report=dict(success=False,actualDeckyRpc=True,actualDeckyEvents=True,syntheticInput=True,
        privateTestBridge=True,productionHttpParentVerified=False,realSteamCef=False,
        realFrameContacted=False,physicalControllerVerified=False,browserSandboxDisabled=False,
        productionAdaptationEnabled=False,panelSha256=hashlib.sha256(Path('/input/terminal-panel.html').read_bytes()).hexdigest())
    browser=page=None
    stages=[];captures={}
    temporary=tempfile.TemporaryDirectory(prefix='framey-terminal-browser-')
    try:
        profile=Path(temporary.name)
        with (home/'terminal-browser.log').open('w') as log:
            browser=subprocess.Popen(['/usr/bin/chromium','--headless','--disable-gpu','--no-first-run',
                '--no-default-browser-check','--disable-background-networking','--user-data-dir='+temporary.name,
                '--window-size=1240,1050','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
                'http://127.0.0.1:'+str(server.server_port)+'/'],stdout=log,stderr=log,start_new_session=True)
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                assert browser.poll() is None, 'Sandboxed Chromium exited'
                port=profile/'DevToolsActivePort'
                if port.is_file():
                    frame_steam.CDP='http://127.0.0.1:'+port.read_text().splitlines()[0]+'/json'
                    candidate=None;accepted=False
                    try:
                        candidate=frame_steam.Page('Owned Terminal actual backend')
                        accepted=bool(candidate.eval('typeof ready!=="undefined"&&ready'))
                        if not accepted:
                            report['readinessState']=candidate.eval('({state:document.readyState,failure:window.failure||null,errors:window.errors||[]})')
                            assert not report['readinessState']['failure'], report['readinessState']['failure']
                        if accepted:page=candidate;break
                    except (OSError,frame_steam.Fail) as error:
                        report['lastReadinessError']=str(error)[:1500]
                    finally:
                        if candidate is not None and not accepted:candidate.sock.close()
                time.sleep(.2)
            assert page is not None, 'Terminal panel unavailable'
            for action,expected in [('create','terminal'),('input','output'),('close','removed')]:
                page.eval('window.advance('+json.dumps(action)+','+json.dumps(COMMAND)+')')
                deadline=time.monotonic()+90;stage=None
                while time.monotonic()<deadline:
                    assert not page.eval('window.failure||null'), page.eval('window.failure||null')
                    stage=page.eval('window.stage')
                    if stage:break
                    time.sleep(.2)
                assert stage and stage['stage']==expected and not stage['errors'],stage
                stages.append(stage);captures[expected]=screenshot(page)
                if action=='input':
                    assert (home/'framey-browser-terminal-marker').read_bytes()==b'framey-browser-terminal\n'
                    output=''.join(e['args'][0] for e in bridge.delivered)
                    assert '\r\nframey-browser-output\r\n' in output
            assert bridge.call('get_terminals',[])==[]
            assert not page.eval('window.errors'),page.eval('window.errors')
            renderers=[]
            for path in Path('/proc').iterdir():
                if not path.name.isdecimal():continue
                try:
                    command=(path/'cmdline').read_bytes()
                    if b'--type=renderer' not in command:continue
                    fields=dict(line.split(':',1) for line in (path/'status').read_text().splitlines() if ':' in line)
                    assert fields['Seccomp'].strip()=='2' and fields['NoNewPrivs'].strip()=='1'
                    lineage=[int(path.name)]
                    while lineage[-1]!=browser.pid:
                        parent=int(Path('/proc/'+str(lineage[-1])+'/stat').read_text().rsplit(')',1)[1].split()[1])
                        assert parent>1 and parent not in lineage and len(lineage)<16
                        lineage.append(parent)
                    renderers.append(dict(pid=int(path.name),ancestryToBrowser=lineage,seccomp=2,noNewPrivs=1))
                except FileNotFoundError:pass
            assert renderers
            report.update(success=True,stages=stages,screenshots=captures,
                calls=bridge.calls,deliveredEvents=bridge.delivered,sandboxedRendererPids=renderers,
                privateMarkerSha256=hashlib.sha256((home/'framey-browser-terminal-marker').read_bytes()).hexdigest())
    finally:
        if page is not None:page.sock.close()
        if browser is not None:
            if browser.poll() is None:
                os.killpg(browser.pid,signal.SIGTERM)
                try:browser.wait(timeout=8)
                except subprocess.TimeoutExpired:os.killpg(browser.pid,signal.SIGKILL);browser.wait(timeout=8)
            report['ownedBrowserReaped']=browser.poll() is not None
        browser_log=home/'terminal-browser.log'
        if browser_log.is_file():report['browserLogTail']=browser_log.read_text(errors='replace')[-8000:]
        server.shutdown();server.server_close();thread.join(8);report['bridgeStopped']=not thread.is_alive()
        try:
            bridge.close();report['nativeEventSocketClosed']=not bridge.thread.is_alive()
        except BaseException as error:
            report['eventSocketCleanupError']=str(error)[:1000]
            report['success']=False
        temporary.cleanup()
        report.update(stages=stages,screenshots=captures,calls=bridge.calls,
                      deliveredEvents=bridge.delivered,bridgeFailures=bridge.failures)
        print('FRAMEY_TERMINAL_BROWSER_JSON='+json.dumps(report),file=sys.stderr,flush=True)
    return report
