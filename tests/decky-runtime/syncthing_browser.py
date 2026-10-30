"""Browser controls -> actual Decky RPC -> signed package, in the owned VM only."""
import base64
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

sys.path.insert(0, '/input')
import frame_steam

PROBE = r'''
const errors=[];
addEventListener('error',e=>errors.push(e.message));
addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
addEventListener('securitypolicyviolation',e=>errors.push('CSP '+e.violatedDirective));
const text=()=>document.getElementById('framey-root').innerText;
const button=label=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===label);
const wait=async read=>{const end=Date.now()+60000;while(Date.now()<end){if(read())return;
 await new Promise(resolve=>setTimeout(resolve,100));}throw Error('Browser DOM readiness timed out');};
const stage=value=>parent.postMessage({type:'test:stage',stage:value,text:text().slice(0,3000),errors,manualPortFallbackUsed:window.manualPortFallbackUsed},'*');
let busy=false;window.manualPortFallbackUsed=false;
addEventListener('message',async event=>{
 if(event.source!==parent||event.data?.type!=='test:advance'||busy)return;
 busy=true;
 try{
  if(event.data.action==='setup'){
   await wait(()=>button('Start Setup'));button('Start Setup').click();
   await wait(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('"Syncthing GTK" Flatpak')));
   [...document.querySelectorAll('button')].find(b=>b.textContent.includes('"Syncthing GTK" Flatpak')).click();
   await wait(()=>text().includes('Almost done!')||text().includes('Please enter the web UI port'));
   if(text().includes('Please enter the web UI port')){
    // Enter only the known private fixture port, through the rendered input.
    const input=document.querySelector('input');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'8384');
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    await new Promise(resolve=>setTimeout(resolve,50));
    window.manualPortFallbackUsed=true;button('Continue').click();
   }
   await wait(()=>text().includes('Almost done!'));
   button('Continue').click();await wait(()=>button('Get Started'));button('Get Started').click();
   await wait(()=>text().includes('Running')&&text().includes('Private service sync')&&text().includes('Devices'));
   stage('running');
  }else{
   const controls=[...document.querySelector('[flow-children="horizontal"]').querySelectorAll(':scope > button')];
   if(controls.length!==4)throw Error('Unexpected dashboard controls');
   controls[3].click();
   const target=event.data.action==='start'?'Running':'Stopped';
   await wait(()=>{if(text().includes('Failed'))throw Error('Actual dashboard reported Failed after '+event.data.action);
    return text().includes(target);});
   stage(event.data.action==='start'?'restarted':'stopped');
  }
 }catch(e){stage('failed');parent.postMessage({type:'test:failure',error:e.message},'*');}
 finally{busy=false;}
});
'''
PARENT = r'''
let ready=false;window.stage=null;window.startupErrors=[];
addEventListener('error',event=>startupErrors.push(event.message));
addEventListener('unhandledrejection',event=>startupErrors.push(String(event.reason)));
const panel=()=>document.getElementById('panel').contentWindow;
addEventListener('message',async event=>{
 if(event.source!==panel())return;
 const req=event.data||{};
 if(req.type==='framey:cache:init'){panel().postMessage({type:'framey:cache:seed',session:req.session,entries:{}},'*');return;}
 if(req.type==='framey:ready'){ready=true;return;}
 if(req.type==='test:stage'){window.stage=req;return;}
 if(req.type==='test:failure'){window.failure=req.error;return;}
 if(req.type!=='framey:call')return;
 try{
  const response=await fetch('/rpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(req)});
  const result=await response.json();panel().postMessage({type:'framey:reply',id:req.id,result},'*');
 }catch(e){window.failure='RPC bridge failed';}
});
window.advance=action=>{if(!ready)throw Error('Panel not ready');window.stage=null;
 panel().postMessage({type:'test:advance',action},'*');};
'''


def screenshot(page):
    page.next_id += 1
    page._send(json.dumps({'id': page.next_id, 'method': 'Page.captureScreenshot',
                           'params': {'format': 'png'}}))
    while True:
        response = json.loads(page._recv())
        if response.get('id') == page.next_id:
            return response['result']['data']


def ready_page(report):
    """Accept only a ready panel; close every rejected owned CDP candidate."""
    candidate = None
    accepted = False
    phase = 'page-connect'
    started = time.monotonic()
    outcome = 'not-ready'
    try:
        candidate = frame_steam.Page('Owned Syncthing actual backend')
        phase = 'panel-ready'
        accepted = bool(candidate.eval("typeof ready !== 'undefined' && ready"))
        if accepted:
            outcome = 'ready'
            return candidate
        phase = 'panel-errors'
        report['startupErrors'] = candidate.eval('window.startupErrors')
    except (OSError, frame_steam.Fail) as error:
        outcome = 'failure'
        report['lastReadinessError'] = str(error)[:1500]
    finally:
        if candidate is not None and not accepted:
            candidate.sock.close()
        attempts = report.setdefault('readinessAttempts', [])
        if len(attempts) < 16:
            attempts.append(dict(phase=phase, outcome=outcome,
                                 elapsedSeconds=round(time.monotonic()-started, 3)))
        else:
            report['readinessTraceOverflow'] = True
    return None


def startup_diagnostics(browser, profile, log):
    """Bounded evidence from the owned fixture only; never change readiness."""
    report = dict(processAlive=browser.poll() is None,
                  returnCode=browser.returncode,
                  devToolsPortFilePresent=(profile/'DevToolsActivePort').is_file())
    try:
        with log.open('rb') as stream:
            stream.seek(0, 2)
            report['stderrBytes'] = stream.tell()
            stream.seek(max(0, stream.tell()-2048))
            tail = stream.read(2048)
        # The disposable browser has no user session, secrets or external
        # network. Preserve its final diagnostic lines, with a strict bound.
        report['stderrTail'] = ''.join(chr(value) if 32 <= value < 127 or value == 10
                                       else '?' for value in tail)
    except OSError:
        report['stderrUnavailable'] = True
    if report['devToolsPortFilePresent']:
        try:
            with frame_steam.urllib.request.urlopen(frame_steam.CDP, timeout=2) as reply:
                encoded = reply.read(65537)
            if len(encoded) > 65536:
                report['targetReportTooLarge'] = True
            else:
                targets = json.loads(encoded)
                assert isinstance(targets, list)
                report['targetCount'] = len(targets)
                report['targets'] = [dict(type=str(target.get('type', ''))[:32],
                    title=str(target.get('title', ''))[:80],
                    urlKind=('loopback-http' if str(target.get('url', '')).startswith('http://127.0.0.1:')
                             else 'data' if str(target.get('url', '')).startswith('data:') else 'other'))
                    for target in targets[:8] if isinstance(target, dict)]
        except (OSError, ValueError, AssertionError):
            report['targetsUnavailable'] = True
    return report


def exercise(legacy_rpc, runtime_identity, service):
    from syncthing_service import prop
    assert os.getuid() == 1100 and Path('/framey-owned-vm').read_text() == 'Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    initial = json.loads(legacy_rpc('get_settings_json'))
    assert initial['is_setup'] is False and not initial['api_key']
    # The parent permits embedded runtime scripts; the opaque child separately
    # denies every network connection, including the private parent's RPC URL.
    policy = '''<meta http-equiv="Content-Security-Policy" content="default-src 'none';
script-src 'unsafe-inline' data: blob:; connect-src 'none'; style-src 'unsafe-inline'; img-src data:">'''
    panel = Path('/input/browser-panel.html').read_text().replace('<html lang="en">', '<html lang="en">'+policy)
    panel = panel.replace('</html>', '<script>'+PROBE+'</script></html>')
    document = '''<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy"
content="default-src 'none'; script-src 'unsafe-inline' data: blob:; frame-src data:; connect-src 'self'; style-src 'unsafe-inline'; img-src data:">
<title>Owned Syncthing actual backend</title><style>body{margin:0;background:#0d1925;color:white}iframe{width:1200px;height:1050px;border:0}</style>
<iframe id="panel" sandbox="allow-scripts" src="data:text/html;base64,''' + base64.b64encode(panel.encode()).decode() + '''#fixture"></iframe><script>''' + PARENT + '</script>'
    calls, stages, screenshots, observations = [], [], {}, []
    rpc_lock = threading.Lock()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(document.encode())

        def do_POST(self):
            if self.path != '/rpc':
                self.send_error(404)
                return
            length = int(self.headers.get('Content-Length', '0'))
            assert 0 < length <= 32768
            req = json.loads(self.rfile.read(length))
            assert req.get('legacy') is True
            method, args = req['method'], req['args']
            assert method in ('get_settings_json', 'set_setting', 'framey_http_fetch')
            assert len(args) <= 1 and (not args or isinstance(args[0], dict))
            kwargs = args[0] if args else {}
            entry = {'method': method}
            if method == 'set_setting':
                entry['setting'] = kwargs['setting']
            if method == 'framey_http_fetch':
                entry.update(httpMethod=kwargs['method'], path=kwargs['path'])
            with rpc_lock:
                assert len(calls) < 300
                value = legacy_rpc(method, **kwargs)
                if method == 'framey_http_fetch':
                    entry['status'] = value['status']
                calls.append(entry)
            data = json.dumps({'success': True, 'result': value}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = page = None
    temporary = tempfile.TemporaryDirectory(prefix='framey-owned-browser-')
    report = {'success': False, 'syntheticInput': True, 'actualDeckyRpc': True,
              'installerEnabled': False, 'realFrameContacted': False,
              'hostBusExposed': False, 'browserSandboxDisabled': False,
              'panelSha256': hashlib.sha256(Path('/input/browser-panel.html').read_bytes()).hexdigest()}
    try:
        profile = Path(temporary.name)
        command = ['/usr/bin/chromium', '--headless', '--disable-gpu', '--no-first-run',
                   '--no-default-browser-check', '--disable-background-networking',
                   '--user-data-dir='+str(profile), '--window-size=1240,1100',
                   '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
                   'http://127.0.0.1:'+str(server.server_port)+'/']
        with (Path.home()/'browser.log').open('w+') as log:
            browser = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
            deadline = time.monotonic()+60
            while time.monotonic() < deadline:
                if browser.poll() is not None:
                    raise RuntimeError('Sandboxed browser exited: '+str(browser.returncode))
                port = profile/'DevToolsActivePort'
                if port.is_file():
                    frame_steam.CDP = 'http://127.0.0.1:'+port.read_text().splitlines()[0]+'/json'
                    page = ready_page(report)
                    if page is not None:
                        break
                time.sleep(.2)
            assert page is not None, 'Browser CDP/panel readiness unavailable'
            first_pids = []
            for label, action in [('running', 'setup'), ('stopped', 'stop'), ('restarted', 'start'), ('stopped', 'stop')]:
                page.eval('window.advance('+json.dumps(action)+')')
                deadline = time.monotonic()+120
                stage = None
                while time.monotonic() < deadline:
                    failure = page.eval('window.failure||null')
                    assert failure is None, failure
                    stage = page.eval('window.stage')
                    if stage:
                        break
                    time.sleep(.2)
                assert stage and stage['stage'] == label and not stage['errors'], stage
                stages.append(stage)
                if label == 'stopped':
                    assert prop(service, 'MainPID') == '0'
                    assert all(not Path('/proc/'+str(pid)).exists() for pid in first_pids)
                else:
                    pids = runtime_identity(service)
                    if first_pids:
                        assert pids[0] != first_pids[0]
                    first_pids = pids
                    observations.append({'stage': label, 'pids': pids})
                name = label+str(len(stages))
                screenshots[name] = screenshot(page)
            renderers = []
            browser_processes = []
            for process in Path('/proc').iterdir():
                try:
                    if not process.name.isdecimal():
                        continue
                    raw_command = (process/'cmdline').read_bytes()
                    # Chromium can rewrite argv into one process-title string.
                    # Match a whole flag in either form, retaining strict PID
                    # ancestry and actual kernel sandbox requirements below.
                    arguments = raw_command.replace(b'\0', b' ').split()
                    if b'chromium' in raw_command:
                        browser_processes.append({'pid': int(process.name),
                                                  'command': raw_command[:4096].decode(errors='replace')})
                    if b'--type=renderer' in arguments:
                        lineage = [int(process.name)]
                        while lineage[-1] != browser.pid:
                            parent = int(Path('/proc/'+str(lineage[-1])+'/stat').read_text().rsplit(')', 1)[1].split()[1])
                            assert parent > 1 and parent not in lineage and len(lineage) < 16
                            lineage.append(parent)
                        status = (process/'status').read_text()
                        assert 'Seccomp:\t2\n' in status and 'NoNewPrivs:\t1\n' in status
                        renderers.append({'pid': int(process.name), 'ancestryToBrowser': lineage,
                                          'commandLineStyle': 'argv' if b'--type=renderer' in raw_command.split(b'\0') else 'process-title',
                                          'seccomp': 2, 'noNewPrivs': 1})
                except FileNotFoundError:
                    continue
            report['browserProcesses'] = browser_processes
            assert renderers, 'No sandboxed Chromium renderer observed'
            saved = json.loads(legacy_rpc('get_settings_json'))
            assert Path('/proc/'+str(browser.pid)+'/exe').resolve() == Path('/usr/lib/chromium/chromium')
            report.update(setupCommitted=saved['is_setup'] is True,
                          discoveredApiKeySaved=bool(saved['api_key']), savedPort=saved['port'],
                          manualPortFallbackUsed=stages[0]['manualPortFallbackUsed'],
                          browserVersion=subprocess.check_output(['/usr/bin/chromium', '--version'], text=True).strip(),
                          browserExecutableSha256=hashlib.file_digest(Path('/usr/lib/chromium/chromium').open('rb'), 'sha256').hexdigest(),
                          browserPackages=subprocess.check_output(['dpkg-query', '-W', 'chromium', 'chromium-common', 'chromium-sandbox'], text=True).strip(),
                          sandboxedRendererPids=renderers, actualPackagedProcessObservations=observations,
                          stages=stages, calls=calls, screenshots=screenshots, success=True)
    except BaseException:
        if browser:
            report['startupDiagnostics'] = startup_diagnostics(browser, profile, Path.home()/'browser.log')
        # GetUnit is read-only and does not load a collected inactive unit.
        lookup = subprocess.run(
            ['busctl', '--user', 'call', 'org.freedesktop.systemd1',
             '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager',
             'GetUnit', 's', service], capture_output=True, text=True, timeout=10,
        )
        report['failureUnitLookup'] = {'returncode': lookup.returncode,
                                     'stdout': lookup.stdout.strip(), 'stderr': lookup.stderr.strip()}
        report['failureSystemdProperties'] = {
            field: prop(service, field) for field in
            ('MainPID', 'ActiveState', 'SubState', 'Result', 'ExecMainCode', 'ExecMainStatus', 'LoadState')
        }
        if page:
            try:
                report['lastStage'] = page.eval('window.stage')
                image = screenshot(page)
                parts = [image[offset:offset+4096] for offset in range(0, len(image), 4096)]
                for index, data in enumerate(parts):
                    print('FRAMEY_BROWSER_FAILURE_SCREENSHOT_CHUNK_JSON='+json.dumps(
                        dict(index=index, total=len(parts), data=data)), flush=True)
            except (OSError, frame_steam.Fail):
                report['lastStageUnavailable'] = True
        raise
    finally:
        report.update(stages=stages, calls=calls, actualPackagedProcessObservations=observations)
        if page:
            page.sock.close()
        if browser:
            if browser.poll() is None:
                os.killpg(browser.pid, signal.SIGTERM)
            try:
                browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGKILL)
                browser.wait(timeout=10)
            report['ownedBrowserReaped'] = browser.poll() is not None
        temporary.cleanup()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        report['bridgeStopped'] = not thread.is_alive()
        print('FRAMEY_BROWSER_PROGRESS_JSON='+json.dumps({k: v for k, v in report.items() if k != 'screenshots'}), flush=True)
    assert report['setupCommitted'] and report['discoveredApiKeySaved'] and report['savedPort'] == 8384
    assert report['ownedBrowserReaped'] and report['bridgeStopped']
    return report
