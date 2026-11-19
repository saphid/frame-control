#!/usr/bin/env python3
"""Replay the shipped settings UI against native Decky over a private test bridge.

The container has no network NIC. The browser uses an opaque Framey panel and
synthetic DOM input; this does not exercise Frame's HTTP/SSH parent or worn VR.
"""
import argparse
import base64
import hashlib
import http.server
import importlib.util
import json
import os
import platform
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ui'))
import framey_panel
import frame_steam

TITLE = 'Owned Framey sample settings replay'
SOURCES = (
    'scripts/framey-test-sample-browser.py', 'tests/decky-runtime/sample_browser_rpc.py',
    'scripts/framey-test-sample-runtime.py', 'tests/decky-runtime/sample_settings.py',
    'scripts/framey-test-decky-runtime.py', 'scripts/framey-pack-sample.py',
    'scripts/framey-check-archive.py', 'tests/decky-runtime/Containerfile',
    'tests/decky-runtime/check.py', 'tests/decky-runtime/timer_lifecycle.py',
    'tests/decky-runtime/deck_settings_private.py', 'tests/decky-runtime/runtime_console.py',
    'tests/framey_official.py', 'ui/frame_decky.py', 'ui/frame_decky_store.py',
    'ui/framey_compatibility.py', 'ui/framey-compatibility.json', 'ui/framey_panel.py',
    'ui/framey-host.js', 'ui/frame_steam.py',
    'ui/vendor/react-18.3.1.min.js', 'ui/vendor/react-dom-18.3.1.min.js',
    'examples/framey-settings/plugin.json', 'examples/framey-settings/main.py',
    'examples/framey-settings/py_modules/framey_decky_ipc.py', 'ui/framey_decky_ipc.py',
    'examples/framey-settings/dist/index.js',
    '.github/workflows/framey-sample-browser.yml', 'tests/test_framey_sample_browser_bridge.py',
)

PROBE = r'''
const errors=[];
addEventListener('error',e=>errors.push(e.message));
addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
addEventListener('securitypolicyviolation',e=>errors.push('CSP '+e.violatedDirective));
const text=()=>document.getElementById('framey-root').innerText;
const wait=async read=>{const end=Date.now()+10000;while(Date.now()<end){if(read())return;
 await new Promise(resolve=>setTimeout(resolve,25));}throw Error('Sample DOM condition timed out: '+text());};
const button=label=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===label);
addEventListener('message',async event=>{
 if(event.source!==parent||event.data?.type!=='test:advance')return;
 try{
  const action=event.data.action, expected=event.data.expected;
  await wait(()=>document.querySelector('input[type=checkbox]')&&!document.querySelector('input[type=checkbox]').disabled);
  if(action==='save-on')document.querySelector('input[type=checkbox]').click();
  if(action==='reset-off'){
   button('Reset example setting').click();await wait(()=>button('Reset'));button('Reset').click();
   await wait(()=>!document.getElementById('framey-modal').textContent.includes('Reset example setting?'));
  }
  await wait(()=>text().includes('Saved setting: '+(expected?'on':'off'))&&
    document.querySelector('input[type=checkbox]').checked===expected&&!document.querySelector('input[type=checkbox]').disabled);
  parent.postMessage({type:'test:stage',action,expected,checked:document.querySelector('input[type=checkbox]').checked,text:text(),errors},'*');
 }catch(error){parent.postMessage({type:'test:failure',error:String(error),errors},'*');}
});
'''
PARENT = r'''
window.ready=false;window.stage=null;window.failure=null;
addEventListener('message',async event=>{
 const target=document.getElementById('panel').contentWindow;if(event.source!==target)return;
 const req=event.data||{};
 if(req.type==='framey:cache:init'){target.postMessage({type:'framey:cache:seed',session:req.session,entries:{}},'*');return;}
 if(req.type==='framey:ready'){window.ready=true;return;}
 if(req.type==='framey:error'||req.type==='test:failure'){window.failure=req;return;}
 if(req.type==='test:stage'){window.stage=req;return;}
 if(req.type!=='framey:call')return;
 try{
  const response=await fetch('/rpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(req)});
  if(!response.ok)throw Error('Private bridge HTTP '+response.status);
  const reply=await response.json();
  target.postMessage({type:'framey:reply',id:req.id,...(reply.success?{result:reply.result}:{error:reply.result})},'*');
 }catch(error){window.failure={error:String(error)};}
});
window.advance=(action,expected)=>{window.stage=null;
 document.getElementById('panel').contentWindow.postMessage({type:'test:advance',action,expected},'*');};
'''


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Bridge:
    def __init__(self, process):
        self.process, self.buffer, self.lock = process, b'', threading.Lock()

    def read(self, timeout=30):
        deadline = time.monotonic()+timeout
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while b'\n' not in self.buffer:
                if not selector.select(max(0, deadline-time.monotonic())):
                    raise TimeoutError('Native sample bridge reply timed out')
                data = os.read(self.process.stdout.fileno(), 65536)
                if not data:
                    raise RuntimeError('Native sample bridge exited before replying')
                self.buffer += data
                if len(self.buffer) > 2*1024**2:
                    raise ValueError('Native sample bridge reply exceeds bound')
            line, self.buffer = self.buffer.split(b'\n', 1)
            return json.loads(line)

    def call(self, value):
        with self.lock:
            self.process.stdin.write((json.dumps(value)+'\n').encode())
            self.process.stdin.flush()
            return self.read()


def wait(page, expression, timeout=15):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        failure = page.eval('window.failure')
        if failure:
            raise RuntimeError(str(failure))
        value = page.eval(expression)
        if value:
            return value
        time.sleep(.05)
    raise TimeoutError('Sample browser condition timed out: '+expression)


def screenshot(page):
    page.next_id += 1
    page._send(json.dumps(dict(id=page.next_id, method='Page.captureScreenshot', params={'format':'png'})))
    while True:
        reply = json.loads(page._recv())
        if reply.get('id') == page.next_id:
            return base64.b64decode(reply['result']['data'], validate=True)


def stop_browser(browser):
    try:
        os.killpg(browser.pid, signal.SIGTERM)
        browser.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        pass
    finally:
        try:
            os.killpg(browser.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        browser.wait(timeout=5)
    deadline = time.monotonic()+5
    while True:
        live = []
        for path in Path('/proc').glob('[0-9]*/stat'):
            try:
                fields = path.read_text().rsplit(')', 1)[1].split()
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            if fields[2:4] == [str(browser.pid)]*2 and fields[0] not in ('Z', 'X'):
                live.append(path.parent.name)
        if not live:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Owned browser group remains live: '+str(live))
        time.sleep(.02)


def replay(args, report):
    native = module('sample_browser_native', ROOT/'scripts/framey-test-decky-runtime.py')
    packer = module('sample_browser_packer', ROOT/'scripts/framey-pack-sample.py')
    loader, digest = native.loader_bytes(args.loader)
    report.update(decky=native.RELEASE, loaderSha256=digest)
    identifier = uuid.uuid4().hex[:12]
    image, container = 'framey-sample-browser:'+identifier, 'framey-sample-browser-'+identifier
    process = browser = page = server = None
    with tempfile.TemporaryDirectory(prefix='framey-sample-browser-') as temporary:
        folder = Path(temporary); folder.chmod(0o755)
        try:
            (folder/'PluginLoader').write_bytes(loader)
            packed = packer.pack(ROOT/'examples/framey-settings', folder/'sample.zip', 'Framey Settings Sample')
            (folder/'sample.zip').chmod(0o644)
            report['archiveSha256'] = packed['sha256']
            # Exercise the real ownership reader with a synthetic, private receipt.
            plugin = folder/'plugins/framey-settings'; plugin.mkdir(parents=True)
            with zipfile.ZipFile(folder/'sample.zip') as archive:
                for name in archive.namelist():
                    target=folder/'plugins'/name; target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(archive.read(name))
            (plugin/'.frame-control-store.json').write_text(json.dumps(dict(storeId=65535, sha256=packed['sha256'])))
            framey_panel.PLUGINS = folder/'plugins'
            panel = framey_panel.panel(65535).decode()
            for route, source in [('react.js','vendor/react-18.3.1.min.js'),('react-dom.js','vendor/react-dom-18.3.1.min.js'),('host.js','framey-host.js')]:
                data=base64.b64encode((ROOT/'ui'/source).read_bytes()).decode()
                panel=panel.replace(f'src="/framey-runtime/{route}"', f'src="data:text/javascript;base64,{data}"')
            panel=panel.replace('</html>','<script>'+PROBE+'</script></html>')
            document='''<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' data: blob:; frame-src data:; connect-src 'self'; style-src 'unsafe-inline'; img-src data:"><title>'''+TITLE+'''</title><style>body{margin:0;background:#0d1925;color:white}iframe{width:1100px;height:1050px;border:0}</style><iframe id="panel" sandbox="allow-scripts" src="data:text/html;base64,'''+base64.b64encode(panel.encode()).decode()+'''#fixture"></iframe><script>'''+PARENT+'</script>'
            subprocess.run(['docker','build','-q','-t',image,'-f',str(ROOT/'tests/decky-runtime/Containerfile'),str(ROOT/'tests/decky-runtime')],check=True,timeout=300)
            with (args.output/'native-stderr.log').open('w') as native_log, (args.output/'browser.log').open('w') as browser_log:
                command=['docker','run','--rm','-i','--name',container,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--tmpfs','/tmp:rw,exec,mode=1777','--tmpfs','/run/user/1100:rw,uid=1100,gid=1100,mode=700','--tmpfs','/home/tester:rw,exec,uid=1100,gid=1100,mode=700','--mount',f'type=bind,source={ROOT},target=/repo,readonly','--mount',f'type=bind,source={folder},target=/input,readonly','--entrypoint','python3',image,'/repo/tests/decky-runtime/sample_browser_rpc.py']
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=native_log)
                bridge=Bridge(process);assert bridge.read()==dict(stage='ready',cycle=0)
                class Handler(http.server.BaseHTTPRequestHandler):
                    def log_message(self, *_args): pass
                    def do_GET(self):
                        if self.path!='/':self.send_error(404);return
                        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(document.encode())
                    def do_POST(self):
                        if self.path!='/rpc':self.send_error(404);return
                        length=int(self.headers.get('Content-Length','0'))
                        if not 0<length<=4096:self.send_error(400);return
                        request=json.loads(self.rfile.read(length));assert request.get('legacy') is False
                        assert request['method'] in ('get_setting','set_setting')
                        value=bridge.call(dict(op='rpc',method=request['method'],args=request['args']))
                        report['browserCalls'].append(dict(method=request['method'],args=request['args'],reply=value))
                        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(value).encode())
                server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
                thread=threading.Thread(target=server.serve_forever);thread.start()
                url='http://127.0.0.1:'+str(server.server_address[1])+'/'
                browser=subprocess.Popen([str(args.browser.resolve()),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--user-data-dir='+str(folder/'profile'),'--window-size=1120,1100','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',url],stdout=browser_log,stderr=browser_log,start_new_session=True)
                deadline=time.monotonic()+30
                while page is None and time.monotonic()<deadline:
                    try:
                        port=(folder/'profile/DevToolsActivePort').read_text().splitlines()[0]
                        frame_steam.CDP='http://127.0.0.1:'+port+'/json';page=frame_steam.Page(TITLE)
                    except (OSError,IndexError,frame_steam.Fail):time.sleep(.1)
                assert page is not None,'Owned sample browser did not attach'
                def stage(label, action, expected):
                    wait(page,'window.ready');page.eval('window.advance('+json.dumps(action)+','+json.dumps(expected)+')')
                    value=wait(page,'window.stage');assert value['checked'] is expected and not value['errors'],value
                    report['stages'].append(dict(label=label,**value))
                    capture=screenshot(page);(args.output/(label+'.png')).write_bytes(capture)
                    report['captureSha256'][label]=hashlib.sha256(capture).hexdigest()
                def reopen():
                    page.eval('(()=>{window.ready=false;window.stage=null;window.failure=null;const panel=document.getElementById("panel");panel.replaceWith(panel.cloneNode(false));})()')
                stage('initial','read',False)
                stage('saved-on','save-on',True)
                report['snapshots'].append(bridge.call(dict(op='snapshot')))
                reopen();stage('reopened-on','read',True)
                assert bridge.call(dict(op='finish'))==dict(stage='ready',cycle=1)
                reopen();stage('restarted-on','read',True)
                stage('reset-off','reset-off',False)
                report['snapshots'].append(bridge.call(dict(op='snapshot')))
                reopen();stage('reopened-off','read',False)
                assert bridge.call(dict(op='finish'))==dict(stage='ready',cycle=2)
                reopen();stage('restarted-off','read',False)
                report['snapshots'].append(bridge.call(dict(op='snapshot')))
                complete=bridge.call(dict(op='finish'));assert complete['stage']=='complete';report['native']=complete['report']
                process.stdin.close();assert process.wait(timeout=10)==0
                assert report['native']['success'] and report['native']['cleanShutdownVerified'] and report['native']['forcedFixtureCleanup']==[]
                for index,saved in enumerate(report['snapshots']):
                    assert saved['value']==dict(schema=1,enabled=index==0) and saved['mode']=='0o600',saved
                    assert saved['sha256']==hashlib.sha256((json.dumps(saved['value'])+'\n').encode()).hexdigest()
                assert [c['args'] for c in report['browserCalls'] if c['method']=='set_setting']==[['enabled',True],['enabled',False]]
                report.update(success=True,realLoaderRestarts=2,syntheticInput=True,syntheticReceipt=True,syntheticParentBridge=True,productionFrameHttpParent=False,realFrameContacted=False,physicalControllerVerified=False,wornVisibilityVerified=False,browserSandboxDisabled=False)
        except Exception:
            if page:
                try:
                    capture=screenshot(page);(args.output/'failure.png').write_bytes(capture)
                    report['failureCaptureSha256']=hashlib.sha256(capture).hexdigest()
                except (OSError,KeyError,frame_steam.Fail):
                    pass
            raise
        finally:
            if page:page.sock.close()
            if browser:stop_browser(browser);report['ownedBrowserGroupStopped']=True
            if server:server.shutdown();server.server_close();thread.join(timeout=5);report['httpServerStopped']=not thread.is_alive()
            # Failure containment is not counted as native clean-stop evidence.
            subprocess.run(['docker','rm','-f','--volumes',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
            if process:
                process.wait(timeout=15)
                if not process.stdin.closed:process.stdin.close()
                tail=process.stdout.read(2*1024**2)
                if tail:report['nativeStdoutTail']=tail.decode(errors='replace')
                process.stdout.close()
            subprocess.run(['docker','image','rm',image],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--loader',type=Path);parser.add_argument('--browser',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    source={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}
    report=dict(success=False,architecture=platform.machine(),browserVersion=subprocess.check_output([str(args.browser.resolve()),'--version'],text=True,timeout=10).strip(),sourceRevision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True)),sourceSha256=source,browserCalls=[],stages=[],snapshots=[],captureSha256={})
    try:
        replay(args,report)
        assert source=={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}
    except Exception as error:
        report.update(success=False,error=str(error))
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: actual sample browser settings across reopen and two native Decky restarts')


if __name__=='__main__':main()
