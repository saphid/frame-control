"""Browser controls -> actual Decky RPC -> signed package, in the owned VM only."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, '/input')
import frame_steam

PROBE = r'''
const errors=[];
addEventListener('error',e=>errors.push(e.message));
addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
addEventListener('securitypolicyviolation',e=>errors.push('CSP '+e.violatedDirective));
const text=()=>document.getElementById('framey-root').innerText;
const button=label=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===label);
const dashboardReady=()=>text().includes('Running')&&text().includes('Private service sync')&&
 text().includes('owned-peer')&&!text().split('\n').some(line=>line.trimStart().startsWith('Error:'));
const wait=async read=>{const end=Date.now()+60000;while(Date.now()<end){if(read())return;
 await new Promise(resolve=>setTimeout(resolve,100));}throw Error('Browser DOM readiness timed out');};
const stage=value=>parent.postMessage({type:'test:stage',stage:value,text:text().slice(0,3000),errors,manualPortFallbackUsed:window.manualPortFallbackUsed,manualApiKeyFallbackUsed:window.manualApiKeyFallbackUsed},'*');
let busy=false;window.manualPortFallbackUsed=false;window.manualApiKeyFallbackUsed=false;
addEventListener('message',async event=>{
 if(event.source!==parent||event.data?.type!=='test:advance'||busy)return;
 busy=true;
 try{
  if(event.data.action==='setup'){
   await wait(()=>button('Start Setup'));button('Start Setup').click();
   await wait(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('"Syncthing GTK" Flatpak')));
   [...document.querySelectorAll('button')].find(b=>b.textContent.includes('"Syncthing GTK" Flatpak')).click();
   await wait(()=>text().includes('Almost done!')||text().includes('Please enter the web UI port')||
    text().includes('Please enter the currently configured API key'));
   if(text().includes('Please enter the web UI port')){
    // Enter only the known private fixture port, through the rendered input.
    const input=document.querySelector('input');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'8384');
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    await new Promise(resolve=>setTimeout(resolve,50));
    window.manualPortFallbackUsed=true;button('Continue').click();
   }
   await wait(()=>text().includes('Almost done!')||text().includes('Please enter the currently configured API key'));
   if(text().includes('Please enter the currently configured API key')){
    if(typeof event.data.apiKey!=='string'||!event.data.apiKey)
     throw Error('Missing private fixture API key for manual setup');
    const input=document.querySelector('input');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,event.data.apiKey);
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    await new Promise(resolve=>setTimeout(resolve,50));
    window.manualApiKeyFallbackUsed=true;button('Continue').click();
   }
   await wait(()=>text().includes('Almost done!'));
   button('Continue').click();await wait(()=>button('Get Started'));button('Get Started').click();
   await wait(dashboardReady);
   stage('running');
  }else{
   const controls=[...document.querySelector('[flow-children="horizontal"]').querySelectorAll(':scope > button')];
   if(controls.length!==4)throw Error('Unexpected dashboard controls');
   controls[3].click();
   const target=event.data.action==='start'?'Running':'Stopped';
   await wait(()=>{if(text().includes('Failed'))throw Error('Actual dashboard reported Failed after '+event.data.action);
    return text().includes(target);});
   if(event.data.action==='start')await wait(dashboardReady);
   stage(event.data.action==='start'?'restarted':'stopped');
  }
 }catch(e){stage('failed');parent.postMessage({type:'test:failure',error:e.message},'*');}
 finally{busy=false;}
});
'''
PARENT = r'''
let ready=false;window.stage=null;window.startupErrors=[];
window.startupState={parentInstalled:true,iframeLoads:0,cacheRequests:0,seedReplies:0,readyMessages:0};
window.startupEvents=[];
const startedAt=performance.now();
let progressCount=0,progressFinished=false;
const reportStartup=type=>{
 if(progressFinished||(progressCount>=15&&type!=='panel-ready'))return;
 progressCount++;
 if(type==='panel-ready')progressFinished=true;
 // Evidence only: never await this request or use it to decide readiness.
 try{fetch('/startup',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({type,atMs:Math.round(performance.now()-startedAt),
   documentState:document.readyState,state:{...startupState}})}).catch(()=>{});}catch(e){}
};
const traceStartup=(type,method,id)=>{
 if(startupEvents.length<32)startupEvents.push({type,method,id,atMs:Math.round(performance.now()-startedAt)});
};
addEventListener('error',event=>startupErrors.push(event.message));
addEventListener('unhandledrejection',event=>startupErrors.push(String(event.reason)));
const panel=()=>document.getElementById('panel').contentWindow;
addEventListener('message',async event=>{
 if(event.source!==panel())return;
 const req=event.data||{};
 traceStartup(String(req.type||'unknown').slice(0,64),
   typeof req.method==='string'?req.method.slice(0,64):null,req.id);
 if(req.type==='framey:cache:init'){
  startupState.cacheRequests++;
  panel().postMessage({type:'framey:cache:seed',session:req.session,entries:{}},'*');
  startupState.seedReplies++;reportStartup('cache-seeded');return;
 }
 if(req.type==='framey:ready'){startupState.readyMessages++;ready=true;reportStartup('panel-ready');return;}
 if(req.type==='framey:error'){
  if(startupErrors.length<16)startupErrors.push(String(req.message||'Panel startup failed').slice(0,1000));
  reportStartup('panel-error');
  return;
 }
 if(req.type==='test:stage'){window.stage=req;return;}
 if(req.type==='test:failure'){window.failure=req.error;return;}
 if(req.type!=='framey:call')return;
 reportStartup('rpc-dispatched');
 try{
  const response=await fetch('/rpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(req)});
  const result=await response.json();panel().postMessage({type:'framey:reply',id:req.id,result},'*');
  traceStartup('rpc-reply',req.method,req.id);
  reportStartup('rpc-replied');
 }catch(e){traceStartup('rpc-failure',req.method,req.id);reportStartup('rpc-failed');window.failure='RPC bridge failed';}
});
reportStartup('parent-installed');
window.advance=(action,apiKey)=>{if(!ready)throw Error('Panel not ready');window.stage=null;
 panel().postMessage({type:'test:advance',action,apiKey},'*');};
'''


def wait_browser_group(group, deadline):
    """Do not remove the owned profile while a live session member can write it."""
    while True:
        live = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if fields[2:4] == [str(group), str(group)] and fields[0] not in ('Z', 'X'):
                live.append(entry.name)
        if not live:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Owned browser group did not stop: '+', '.join(live))
        time.sleep(.01)


def stop_browser(browser):
    """Stop the private browser session, retaining the two ten-second budgets."""
    try:
        os.killpg(browser.pid, signal.SIGTERM)
        try:
            browser.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    except ProcessLookupError:
        pass
    finally:
        # Launcher exit does not prove that its profile-writing children exited.
        deadline = time.monotonic()+10
        try:
            os.killpg(browser.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        browser.wait(timeout=max(0, deadline-time.monotonic()))
        wait_browser_group(browser.pid, deadline)


def screenshot(page):
    page.next_id += 1
    page._send(json.dumps({'id': page.next_id, 'method': 'Page.captureScreenshot',
                           'params': {'format': 'png'}}))
    while True:
        response = json.loads(page._recv())
        if response.get('id') == page.next_id:
            return response['result']['data']


def ready_page(report, clock_start=None, pending=None, deadline=None):
    """Accept only a ready panel, retaining at most one pending owned socket."""
    candidate = None
    accepted = False
    phase = 'page-connect'
    started = time.monotonic()
    outcome = 'not-ready'
    failure = None
    reused = bool(pending)
    try:
        candidate = pending.pop() if reused else frame_steam.Page('Owned Syncthing actual backend')
        phase = 'panel-snapshot'
        # Keep one browser-side wait on the owned connection. Repeated CDP
        # snapshots need not compete with the renderer while it initializes.
        expression = """(() => {
            const snapshot=()=>({ready:typeof ready !== 'undefined' && ready,
                errors:window.startupErrors||[],state:window.startupState||null,
                documentState:document.readyState,
                iframeAssigned:!!document.getElementById('panel')?.getAttribute('src'),
                events:window.startupEvents||[]});
            const initial=snapshot(),budget=WAIT_MILLISECONDS;
            if(initial.ready||budget<=0)return initial;
            return new Promise(resolve=>{
                let timer,finished=false;
                const finish=()=>{
                    if(finished)return;finished=true;
                    removeEventListener('message',onMessage);clearTimeout(timer);
                    resolve(snapshot());
                };
                // Native dispatch can checkpoint microtasks between listeners.
                // Inspect ready in a task after the parent's handler has run.
                const onMessage=()=>setTimeout(()=>{if(snapshot().ready)finish();},0);
                addEventListener('message',onMessage);
                timer=setTimeout(finish,budget);
            });
        })()"""
        wait_seconds = max(0, deadline-time.monotonic()) if deadline is not None else 0
        expression = expression.replace('WAIT_MILLISECONDS', repr(wait_seconds*1000))
        if deadline is not None:
            original_timeout = candidate.sock.gettimeout()
            candidate.sock.settimeout(max(.001, wait_seconds))
        try:
            snapshot = candidate.eval(expression)
        finally:
            if deadline is not None:
                candidate.sock.settimeout(original_timeout)
        accepted = snapshot['ready'] is True
        if accepted:
            outcome = 'ready'
            return candidate
        report['startupErrors'] = snapshot['errors']
        report['startupEvents'] = snapshot.get('events', [])
        report['startupState'] = {key: snapshot[key] for key in
                                  ('state', 'documentState', 'iframeAssigned')}
    except (OSError, frame_steam.Fail) as error:
        outcome = 'failure'
        failure = str(error)[:1500]
        report['lastReadinessError'] = failure
    finally:
        if candidate is not None and not accepted:
            if pending is not None and outcome == 'not-ready':
                pending.append(candidate)
            else:
                candidate.sock.close()
        attempt = dict(phase=phase, outcome=outcome,
                       connectionReused=reused,
                       elapsedSeconds=round(time.monotonic()-started, 3))
        if clock_start is not None:
            attempt.update(startedAfterSeconds=round(started-clock_start, 3),
                           finishedAfterSeconds=round(time.monotonic()-clock_start, 3))
        if failure is not None:
            attempt['error'] = failure
        if deadline is not None and phase == 'panel-snapshot':
            attempt['browserEventWaitBudgetSeconds'] = round(wait_seconds, 3)
        report['lastReadinessAttempt'] = attempt
        attempts = report.setdefault('readinessAttempts', [])
        if len(attempts) < 16:
            attempts.append(attempt)
        else:
            report['readinessTraceOverflow'] = True
    return None


def record_startup_progress(report, value, received_after):
    """Keep bounded fixed-field evidence; never accept it as a readiness gate."""
    if not isinstance(value, dict) or value.get('type') not in (
            'parent-installed', 'cache-seeded', 'panel-ready', 'panel-error',
            'rpc-dispatched', 'rpc-replied', 'rpc-failed'):
        return False
    at = value.get('atMs')
    state = value.get('state')
    if (type(at) not in (int, float) or not math.isfinite(at) or at < 0 or
            value.get('documentState') not in ('loading', 'interactive', 'complete') or
            not isinstance(state, dict) or type(state.get('parentInstalled')) is not bool):
        return False
    keys = ('iframeLoads', 'cacheRequests', 'seedReplies', 'readyMessages')
    if any(type(state.get(key)) is not int or not 0 <= state[key] <= 128 for key in keys):
        return False
    record = dict(type=value['type'], atMs=at, documentState=value['documentState'],
                  state={key: state[key] for key in ('parentInstalled',)+keys},
                  receivedAfterSeconds=round(received_after, 3))
    records = report.setdefault('records', [])
    if len(records) == 16:
        report['overflow'] = True
        del records[0]
    records.append(record)
    return True


def owned_browser_process_diagnostics(group, proc_root=Path('/proc')):
    """Read bounded process counters for this disposable browser session only."""
    report = dict(processes=[], entriesScanned=0, scanTruncated=False,
                  processesTruncated=False, unreadableEntries=0)
    if type(group) is not int or group <= 0:
        report['error'] = 'InvalidProcessGroup'
        return report
    report['clockTicksPerSecond'] = os.sysconf('SC_CLK_TCK')
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal():
            continue
        if report['entriesScanned'] == 4096:
            report['scanTruncated'] = True
            break
        report['entriesScanned'] += 1
        try:
            with (entry/'stat').open('rb') as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                report['unreadableEntries'] += 1
                continue
            fields = raw.rsplit(b')', 1)[1].split()
            if fields[2:4] != [str(group).encode(), str(group).encode()]:
                continue
            if len(report['processes']) == 64:
                report['processesTruncated'] = True
                break
            # Recheck identity and ownership before retaining this process.
            with (entry/'stat').open('rb') as stream:
                again = stream.read(4097)
            if len(again) > 4096:
                report['unreadableEntries'] += 1
                continue
            current = again.rsplit(b')', 1)[1].split()
            if current[19] != fields[19] or current[2:4] != fields[2:4]:
                continue
            record = dict(pid=int(entry.name), parentPid=int(current[1]),
                          state=current[0].decode('ascii'),
                          userTicks=int(current[11]), systemTicks=int(current[12]),
                          threadCount=int(current[17]), startTicks=int(current[19]),
                          residentPages=int(current[21]))
            try:
                with (entry/'wchan').open('rb') as stream:
                    wait = stream.read(129)
                record['wchan'] = wait[:128].decode(errors='replace')
                record['wchanTruncated'] = len(wait) > 128
            except OSError as error:
                record['wchanError'] = type(error).__name__
            report['processes'].append(record)
        except (OSError, ValueError, IndexError) as error:
            report['unreadableEntries'] += 1
    return report


def startup_diagnostics(browser, profile, log):
    """Bounded evidence from the owned fixture only; never change readiness."""
    report = dict(processAlive=browser.poll() is None,
                  returnCode=browser.returncode,
                  devToolsPortFilePresent=(profile/'DevToolsActivePort').is_file())
    try:
        report['ownedProcessSnapshot'] = owned_browser_process_diagnostics(browser.pid)
    except OSError as error:
        report['ownedProcessSnapshot'] = {'error': type(error).__name__}
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
            with urllib.request.urlopen(frame_steam.CDP, timeout=2) as reply:
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


def browser_documents(panel):
    """Serve the opaque child separately, with its receiver installed first.

    A data URL repeats the entire encoded panel in Chromium's target metadata.
    Use the same HTTP delivery as the production parent, while preserving the
    child's opaque sandbox and its policy that denies network connections.
    """
    # The parent permits embedded runtime scripts; the opaque child separately
    # denies every network connection, including the private parent's RPC URL.
    policy = '''<meta http-equiv="Content-Security-Policy" content="default-src 'none';
script-src 'unsafe-inline' data: blob:; connect-src 'none'; style-src 'unsafe-inline'; img-src data:">'''
    panel = panel.replace('<html lang="en">', '<html lang="en">'+policy)
    panel = panel.replace('</html>', '<script>'+PROBE+'</script></html>')
    parent = '''<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy"
content="default-src 'none'; script-src 'unsafe-inline' data: blob:; frame-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; img-src data:">
<title>Owned Syncthing actual backend</title><style>body{margin:0;background:#0d1925;color:white}iframe{width:1200px;height:1050px;border:0}</style>
<iframe id="panel" sandbox="allow-scripts"></iframe><script>''' + PARENT + '''
document.getElementById('panel').addEventListener('load',()=>startupState.iframeLoads++);
document.getElementById('panel').src = '/panel#fixture';
</script>'''
    return {'/': parent, '/panel': panel}


def print_final_browser_state():
    """Read only the two owned fixture targets; never promote them to ready."""
    target = frame_steam.urlsplit(frame_steam.CDP)
    client = (frame_steam.http.client.HTTPSConnection if target.scheme == 'https'
              else frame_steam.http.client.HTTPConnection)
    connection = client(target.hostname, target.port, timeout=2)
    try:
        path = target.path or '/'
        if target.query:
            path += '?' + target.query
        connection.request('GET', path)
        response = connection.getresponse()
        if response.status != 200:
            raise OSError('Owned target metadata request failed')
        encoded = response.read(65537)
    finally:
        connection.close()
    assert len(encoded) <= 65536, 'Owned target metadata exceeds diagnostic bound'
    targets = json.loads(encoded)
    print('{"phase":"targets-read"}', flush=True)
    for kind in ('parent', 'iframe'):
        target = next((item for item in targets if
            str(item.get('url', '')).startswith('http://127.0.0.1:') and
            (item.get('type') == 'page' and item.get('title') == 'Owned Syncthing actual backend'
             if kind == 'parent' else item.get('type') == 'iframe' and
             str(item.get('url', '')).endswith('/panel#fixture'))), None)
        if target is None:
            print(json.dumps(dict(target=kind, unavailable=True)), flush=True)
            continue
        page = None
        try:
            page = frame_steam.Page(target['title'])
            print(json.dumps(dict(phase=kind+'-connected')), flush=True)
            page.sock.settimeout(2)
            common = """({documentState:document.readyState,atMs:Math.round(performance.now()),
                rootText:(document.getElementById('framey-root')?.innerText||'').slice(0,1000),
                errorText:(document.getElementById('framey-error')?.innerText||'').slice(0,1000),
                probeInstalled:typeof dashboardReady==='function',
                runtimeInstalled:typeof window.DFL==='object'})"""
            if kind == 'parent':
                common = """({documentState:document.readyState,atMs:Math.round(performance.now()),
                    elapsedMs:typeof startedAt==='number'?Math.round(performance.now()-startedAt):null,
                    ready:typeof ready!=='undefined'&&ready,state:window.startupState||null,
                    failure:String(window.failure||'').slice(0,1000),
                    errors:(window.startupErrors||[]).slice(0,4).map(x=>String(x).slice(0,256)),
                    events:(window.startupEvents||[]).slice(-16)})"""
            snapshot = dict(target=kind, state=page.eval(common))
            line = json.dumps(snapshot)
            print(line if len(line.encode()) <= 8192 else
                  json.dumps(dict(target=kind, snapshotTooLarge=True)), flush=True)
        except (OSError, frame_steam.Fail) as error:
            print(json.dumps(dict(target=kind, errorType=type(error).__name__)), flush=True)
        finally:
            if page is not None:
                page.sock.close()


def final_browser_state(timeout=8):
    """An isolated reader gives the complete final snapshot a hard wall bound."""
    started = time.monotonic()
    import ast
    report = dict(timeoutSeconds=timeout, timedOut=False)
    # The failure reader needs this read-only query, not browser setup imports.
    try:
        with Path(__file__).open('rb') as stream:
            source = stream.read(65537)
        assert len(source) <= 65536, 'Failure reader source exceeds bound'
        source = source.decode('utf-8')
        query = next(node for node in ast.parse(source).body
                     if isinstance(node, ast.FunctionDef) and node.name == 'print_final_browser_state')
        query_source = ast.get_source_segment(source, query)
        assert query_source is not None and len(query_source.encode()) <= 8192
    except (OSError, ValueError, SyntaxError, StopIteration, AssertionError) as error:
        report.update(errorType=type(error).__name__, snapshots=[], phases=[],
                      importModulesStarted=[])
        return report
    command = [sys.executable, '-c',
        'print(\'{"phase":"interpreter-started"}\',flush=True); '
        'import sys; '
        'watched={"syncthing_browser","frame_steam","urllib.request",'
        '"http.client","ssl","tempfile","threading","hashlib"}; seen=set(); '
        'sys.addaudithook(lambda event,args: '
        '(seen.add(args[0]),print(\'{"importModule":"\'+args[0]+\'"}\',flush=True)) '
        'if event=="import" and args[0] in watched and args[0] not in seen else None); '
        'sys.path[:0]=sys.argv[1:3]; import json,frame_steam; '
        'print(\'{"phase":"module-imported"}\',flush=True); '
        'frame_steam.CDP=sys.argv[3]; exec(sys.argv[4]); print_final_browser_state()',
        str(Path(__file__).resolve().parent), str(Path(frame_steam.__file__).resolve().parent),
        frame_steam.CDP, query_source]
    remaining = timeout-(time.monotonic()-started)
    if remaining <= 0:
        report.update(timedOut=True, preparationDeadlineExceeded=True,
                      snapshots=[], phases=[], importModulesStarted=[])
        return report
    try:
        result = subprocess.run(command, capture_output=True, timeout=remaining)
        output = result.stdout
        report['returnCode'] = result.returncode
    except subprocess.TimeoutExpired as error:
        output = error.stdout or b''
        report['timedOut'] = True
    except OSError as error:
        report['errorType'] = type(error).__name__
        output = b''
    snapshots, phases, imports = [], [], []
    for line in output[:32768].splitlines():
        try:
            value = json.loads(line)
            if value.get('importModule') in (
                    'syncthing_browser', 'frame_steam', 'urllib.request',
                    'http.client', 'ssl', 'tempfile', 'threading', 'hashlib'):
                if value['importModule'] not in imports:
                    imports.append(value['importModule'])
            elif 'phase' in value:
                phases.append(value['phase'])
            elif value.get('target') in ('parent', 'iframe'):
                snapshots.append(value)
        except (ValueError, UnicodeError):
            report['incompleteSnapshot'] = True
    report['snapshots'] = snapshots[:2]
    report['phases'] = phases[:5]
    report['importModulesStarted'] = imports[:8]
    return report


def exercise(legacy_rpc, runtime_identity, service, expected_api_key):
    # The bounded failure-only reader imports this module too. It makes only
    # outbound CDP requests and must not initialize the VM's inbound server.
    import http.server
    from syncthing_service import prop
    assert os.getuid() == 1100 and Path('/framey-owned-vm').read_text() == 'Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    assert isinstance(expected_api_key, str) and expected_api_key
    initial = json.loads(legacy_rpc('get_settings_json'))
    assert initial['is_setup'] is False and not initial['api_key']
    documents = browser_documents(Path('/input/browser-panel.html').read_text())
    document_requests = []
    calls, stages, screenshots, observations = [], [], {}, []
    rpc_lock = threading.Lock()
    calls_lock = threading.Lock()
    bridge_started = time.monotonic()
    parent_progress = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path not in documents:
                self.send_error(404)
                return
            data = documents[self.path].encode()
            entry = dict(path=self.path, bytes=len(data),
                         receivedAfterSeconds=round(time.monotonic()-bridge_started, 3))
            if len(document_requests) < 16:
                document_requests.append(entry)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            entry['responseWrittenAfterSeconds'] = round(time.monotonic()-bridge_started, 3)

        def do_POST(self):
            if self.path == '/startup':
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2048:
                    self.send_error(413)
                    return
                try:
                    value = json.loads(self.rfile.read(length))
                except ValueError:
                    self.send_error(400)
                    return
                with calls_lock:
                    accepted = record_startup_progress(parent_progress, value,
                                                       time.monotonic()-bridge_started)
                self.send_response(204 if accepted else 400)
                self.end_headers()
                return
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
            entry = {'method': method, 'id': req.get('id'),
                     'receivedAfterSeconds': round(time.monotonic()-bridge_started, 3)}
            if method == 'set_setting':
                entry['setting'] = kwargs['setting']
            if method == 'framey_http_fetch':
                entry.update(httpMethod=kwargs['method'], path=kwargs['path'])
            with calls_lock:
                assert len(calls) < 300
                calls.append(entry)
            try:
                with rpc_lock:
                    entry['backendStartedAfterSeconds'] = round(time.monotonic()-bridge_started, 3)
                    value = legacy_rpc(method, **kwargs)
                    entry['backendFinishedAfterSeconds'] = round(time.monotonic()-bridge_started, 3)
                    if method == 'framey_http_fetch':
                        entry['status'] = value['status']
            except BaseException as error:
                entry['failureType'] = type(error).__name__
                raise
            data = json.dumps({'success': True, 'result': value}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            entry['responseWrittenAfterSeconds'] = round(time.monotonic()-bridge_started, 3)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = page = None
    pending_pages = []
    temporary = tempfile.TemporaryDirectory(prefix='framey-owned-browser-')
    report = {'success': False, 'syntheticInput': True, 'actualDeckyRpc': True,
              'installerEnabled': False, 'realFrameContacted': False,
              'hostBusExposed': False, 'browserSandboxDisabled': False,
              'documentDelivery': 'loopback-http-opaque-sandbox',
              'documentSha256': {path: hashlib.sha256(text.encode()).hexdigest()
                                 for path, text in documents.items()},
              'panelSha256': hashlib.sha256(Path('/input/browser-panel.html').read_bytes()).hexdigest()}
    clock = report['startupClock'] = dict(origin='bridge-monotonic', readinessBudgetSeconds=60)
    try:
        profile = Path(temporary.name)
        command = ['/usr/bin/chromium', '--headless', '--disable-gpu', '--no-first-run',
                   '--no-default-browser-check', '--disable-background-networking',
                   '--disable-component-extensions-with-background-pages',
                   '--user-data-dir='+str(profile), '--window-size=1240,1100',
                   '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
                   'http://127.0.0.1:'+str(server.server_port)+'/']
        with (Path.home()/'browser.log').open('w+') as log:
            clock['browserLaunchStartedAfterSeconds'] = round(time.monotonic()-bridge_started, 3)
            browser = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
            clock['browserLaunchReturnedAfterSeconds'] = round(time.monotonic()-bridge_started, 3)
            deadline = time.monotonic()+60
            clock['readinessDeadlineAfterSeconds'] = round(deadline-bridge_started, 3)
            while time.monotonic() < deadline:
                if browser.poll() is not None:
                    raise RuntimeError('Sandboxed browser exited: '+str(browser.returncode))
                port = profile/'DevToolsActivePort'
                if port.is_file():
                    try:
                        frame_steam.CDP = 'http://127.0.0.1:'+port.read_text().splitlines()[0]+'/json'
                        page = ready_page(report, bridge_started, pending_pages, deadline)
                        if page is not None:
                            break
                    except (OSError, IndexError, frame_steam.Fail) as error:
                        report['lastReadinessError'] = str(error)[:1500]
                time.sleep(.2)
            while pending_pages:
                pending_pages.pop().sock.close()
            finished = time.monotonic()
            clock['readinessFinishedAfterSeconds'] = round(finished-bridge_started, 3)
            if page is not None and finished > deadline:
                page.sock.close()
                page = None
                clock['lateReadyPageRejected'] = True
            clock['readinessPassed'] = page is not None
            assert page is not None, 'Browser CDP/panel readiness unavailable'
            first_pids = []
            for label, action in [('running', 'setup'), ('stopped', 'stop'), ('restarted', 'start'), ('stopped', 'stop')]:
                page.eval('window.advance('+json.dumps(action)+','+json.dumps(expected_api_key)+')')
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
                          validatedApiKeySaved=saved['api_key']==expected_api_key,
                          discoveredApiKeySaved=not stages[0]['manualApiKeyFallbackUsed'], savedPort=saved['port'],
                          manualApiKeyFallbackUsed=stages[0]['manualApiKeyFallbackUsed'],
                          manualPortFallbackUsed=stages[0]['manualPortFallbackUsed'],
                          browserVersion=subprocess.check_output(['/usr/bin/chromium', '--version'], text=True).strip(),
                          browserExecutableSha256=hashlib.file_digest(Path('/usr/lib/chromium/chromium').open('rb'), 'sha256').hexdigest(),
                          browserPackages=subprocess.check_output(['dpkg-query', '-W', 'chromium', 'chromium-common', 'chromium-sandbox'], text=True).strip(),
                          sandboxedRendererPids=renderers, actualPackagedProcessObservations=observations,
                          stages=stages, calls=calls, screenshots=screenshots, success=True)
    except BaseException:
        if browser:
            report['startupDiagnostics'] = startup_diagnostics(browser, profile, Path.home()/'browser.log')
            report['finalBrowserState'] = final_browser_state()
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
        report.update(stages=stages, calls=calls, actualPackagedProcessObservations=observations,
                      documentRequests=list(document_requests), parentStartupProgress=parent_progress)
        while pending_pages:
            pending_pages.pop().sock.close()
        if page:
            page.sock.close()
        if browser:
            stop_browser(browser)
            report['ownedBrowserReaped'] = browser.poll() is not None
            report['ownedBrowserGroupStopped'] = True
        temporary.cleanup()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        report['bridgeStopped'] = not thread.is_alive()
        print('FRAMEY_BROWSER_PROGRESS_JSON='+json.dumps({k: v for k, v in report.items() if k != 'screenshots'}), flush=True)
    assert report['setupCommitted'] and report['validatedApiKeySaved'] and report['savedPort'] == 8384
    assert report['ownedBrowserReaped'] and report['bridgeStopped']
    return report
