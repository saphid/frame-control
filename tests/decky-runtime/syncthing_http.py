"""Production local HTTP/panel dispatcher with actual Decky and fixture CEF only."""
import base64
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request

DIGEST = '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'
# This page supplies only Decky's RPC protocol, not Steam APIs or a real Steam
# session. Production METHOD_SCRIPT and frame_steam.Page still execute unchanged.
CEF = '''<!doctype html><title>SharedJSContext</title><p>Private Decky RPC CEF fixture</p>
<script>window.fixtureRpcTrace=[];window.fixtureTraceOverflow=false;
window.fixtureSocketCount=0;window.fixtureRequestCount=0;
const fixtureStarted=performance.now(),pending=new Map();
let socket=null,transportFailed=false;
const token=__FIXTURE_TOKEN__;
const finish=(item,outcome)=>{if(item.entry.outcome==='pending')Object.assign(item.entry,
 {outcome,elapsedMilliseconds:Math.round(performance.now()-item.started)});};
const failTransport=()=>{
 transportFailed=true;
 for(const item of pending.values()){
  finish(item,'transport-error');clearTimeout(item.timer);
  item.reject(Error('Fixture Decky WebSocket failed'));
 }
 pending.clear();
};
const send=item=>{
 if(!pending.has(item.message.id))return;
 item.entry.openElapsedMilliseconds=Math.round(performance.now()-item.started);
 socket.send(JSON.stringify(item.message));
};
const connect=()=>{
 window.fixtureSocketCount++;
 socket=new WebSocket('ws://127.0.0.1:1337/ws?auth='+encodeURIComponent(token));
 socket.onopen=()=>{
  // Decky 3.3.0 has one active socket and globally deduplicated request IDs.
  // A new owned frontend first clears stale responses, then multiplexes calls.
  socket.send(JSON.stringify({type:4,messages:[]}));
  for(const item of pending.values())send(item);
 };
 socket.onerror=failTransport;socket.onclose=failTransport;
 socket.onmessage=event=>{
  const reply=JSON.parse(event.data);
  if(![1,-1,2].includes(reply.type)||!Number.isSafeInteger(reply.id))return;
  const item=pending.get(reply.id);
  socket.send(JSON.stringify({type:3,id:reply.id}));
  if(!item)return;
  pending.delete(reply.id);clearTimeout(item.timer);
  if(reply.type===1){finish(item,'succeeded');item.resolve(reply.result);}
  else{finish(item,'rejected');item.reject(Error('Fixture Decky RPC rejected'));}
 };
};
window.DeckyBackend={call:async(route,...args)=>{
 const method=route==='loader/get_plugins'?'discovery':
  ['get_settings_json','set_setting','framey_http_fetch'].includes(args[1])?args[1]:'other';
 const started=performance.now(),id=++window.fixtureRequestCount;
 const entry={requestId:id,method,startedAfterMilliseconds:Math.round(started-fixtureStarted),outcome:'pending'};
 if(fixtureRpcTrace.length<500)fixtureRpcTrace.push(entry);else window.fixtureTraceOverflow=true;
 return new Promise((resolve,reject)=>{
  const item={started,entry,resolve,reject,message:{type:0,id,route,args}};
  item.timer=setTimeout(()=>{
   pending.delete(id);finish(item,'timed-out');reject(Error('Fixture Decky RPC timeout'));
  },20000);
  pending.set(id,item);
  if(transportFailed){failTransport();return;}
  if(!socket)connect();else if(socket.readyState===1)send(item);
 });
}};</script>'''



def emit_gateway_progress(report):
    # A diagnostic profile can exceed journald's single-message bound. Emit
    # small, ordered, checksummed chunks without dropping cleanup fields.
    encoded = json.dumps(report, ensure_ascii=True)
    if len(encoded) > 2*1024**2:
        encoded = json.dumps(dict(progressReportOverflow=True, encodedBytes=len(encoded)))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    chunks = [encoded[offset:offset+4000] for offset in range(0, len(encoded), 4000)]
    for index, data in enumerate(chunks):
        chunk = dict(index=index, total=len(chunks), sha256=digest, data=data)
        print('FRAMEY_HTTP_GATEWAY_PROGRESS_CHUNK_JSON='+json.dumps(chunk), flush=True)


def safe_error_category(value):
    # Inspect only in memory. Never retain raw response bodies, commands,
    # arguments, credentials or exception text in the fixture trace.
    if isinstance(value, dict):
        message = ' '.join(str(value.get(key, '')) for key in ('error', 'detail')).lower()
    else:
        message = str(value).lower()
    for text, category in [('timed out talking to', 'ssh-timeout'),
                           ('fixture decky rpc timeout', 'fixture-decky-timeout'),
                           ('decky backend timed out', 'browser-rpc-timeout'),
                           ('no sharedjscontext page', 'cef-unavailable'),
                           ('devtools closed', 'cef-closed')]:
        if text in message:
            return category
    if isinstance(value, dict) and value.get('offline') is True:
        return 'offline'
    return 'other'


def status_process_tree(thread_id, proc=Path('/proc'), owner_pid=None):
    """Read only this request thread's child tree; never read argv or environment."""
    owner_pid = os.getpid() if owner_pid is None else owner_pid
    def read(path):
        with path.open() as stream:
            return stream.read(4096)
    def children(path, parent):
        return [(int(value), parent) for value in read(path).split() if value.isdecimal()]
    pending = children(proc/'self/task'/str(thread_id)/'children', owner_pid)
    seen, result = set(), []
    while pending and len(seen) < 12:
        pid, parent = pending.pop(0)
        if pid in seen:
            continue
        seen.add(pid)
        try:
            stat = read(proc/str(pid)/'stat')
            prefix, fields = stat.rsplit(') ', 1)
            actual_pid, command = prefix.split(' (', 1)
            fields = fields.split()
            if int(actual_pid) != pid or int(fields[1]) != parent:
                continue  # Exited/reused PID is no longer our child.
            command = command if command in ('python3', 'python3.13', 'python3.12',
                                             'bash', 'sh', 'ssh', 'systemctl') else 'other'
            channel = read(proc/str(pid)/'wchan').strip()
            if channel not in ('0', 'do_wait', 'futex_wait_queue', 'futex_wait_queue_me',
                               'pipe_read', 'pipe_write', 'wait_woken', 'ep_poll',
                               'poll_schedule_timeout', 'hrtimer_nanosleep'):
                channel = 'other'
            result.append(dict(pid=pid, parentPid=parent, command=command,
                               state=fields[0] if fields[0] in ('R', 'S', 'D', 'Z', 'T', 'I') else 'other',
                               cpuTicks=int(fields[11])+int(fields[12]),
                               residentPages=max(0, int(fields[21])), waitChannel=channel))
            pending.extend(children(proc/str(pid)/'task'/str(pid)/'children', pid))
        except (OSError, ValueError, IndexError):
            continue  # A short-lived child can vanish between the reads.
    return dict(processes=result, truncated=bool(pending))


class StatusProcessSampler:
    """Bounded passive samples while the unchanged SSH call runs concurrently."""
    def __init__(self, started):
        self.started = started
        self.thread_id = threading.get_native_id()
        self.cancel = threading.Event()
        self.samples = []
        self.errors = 0
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        for delay in (2, 6, 6):
            if self.cancel.wait(delay):
                return
            try:
                sample = status_process_tree(self.thread_id)
                sample['elapsedSeconds'] = round(time.monotonic()-self.started, 3)
                self.samples.append(sample)
            except (OSError, ValueError):
                self.errors += 1  # No raw paths or exception text.

    def start(self):
        self.thread.start()

    def finish(self):
        self.cancel.set()
        self.thread.join(timeout=1)
        return dict(samples=list(self.samples), unavailableSamples=self.errors,
                    observerStopped=not self.thread.is_alive())


def observe_ssh(call, records, lock, started, kind, *args, process_profiles=None, **kwargs):
    assert kind in ('decky-status', 'panel-method', 'headset-status', 'other')
    begin = time.monotonic()
    entry = dict(kind=kind, startedAfterSeconds=round(begin-started, 3), outcome='success')
    sampler = StatusProcessSampler(begin) if kind == 'decky-status' and process_profiles is not None else None
    sampler_started = False
    if sampler:
        try:
            sampler.start()
            sampler_started = True
        except RuntimeError:
            pass  # Diagnostic thread exhaustion must not replace the SSH call.
    try:
        return call(*args, **kwargs)
    except Exception as error:
        entry.update(outcome='failure', errorCategory=safe_error_category(error))
        raise
    finally:
        if sampler:
            profile = (sampler.finish() if sampler_started else
                       dict(samples=[], unavailableSamples=1, observerStopped=True))
            profile['startedAfterSeconds'] = entry['startedAfterSeconds']
            with lock:
                if len(process_profiles['records']) < 128:
                    process_profiles['records'].append(profile)
                else:
                    process_profiles['overflow'] = True
        entry['elapsedSeconds'] = round(time.monotonic()-begin, 3)
        with lock:
            assert len(records) < 500, 'Parent SSH trace limit exceeded'
            records.append(entry)


def wait_authenticated_rest(fetch, api_key, wait):
    def ready():
        response = fetch('GET', '/rest/system/status', {'X-API-Key': api_key})
        if response['status'] in (425, 502):
            return False
        assert response['status'] == 200, response['status']
        assert json.loads(response['body'])['myID']
        return response
    return wait(ready, 'HTTP gateway authenticated signed runtime readiness')


def exercise(runtime_identity, service):
    assert os.getuid() == 1100 and Path('/framey-owned-vm').read_text() == 'Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    from syncthing_service import prop, wait
    import frame_steam
    bundle = Path.home()/'.local/share/frame-control/headset/bundle'
    assert not bundle.exists()
    bundle.mkdir(parents=True)
    with tarfile.open('/input/framey-http-ui.tar') as packed:
        for member in packed:
            assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
            target = bundle/member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(packed.extractfile(member).read())
            target.chmod(0o700 if member.name == 'ui/local-bin/ssh' else 0o600)
    expected = json.loads(Path('/input/framey-http-ui-sources.json').read_text())
    for name, digest in expected.items():
        assert hashlib.sha256((bundle/name).read_bytes()).hexdigest() == digest
    # This is an explicit synthetic store receipt for an uninstalled candidate,
    # not proof that managed install/update/remove is supported.
    plugin = Path.home()/'.local/share/frame-control/decky/plugins/http-fixture'
    assert not plugin.exists()
    plugin.mkdir(parents=True)
    shutil.copy(Path.home()/'decky/plugins/decky-syncthing/plugin.json', plugin/'plugin.json')
    parent_requested = Path('/input/syncthing_http_parent.py').exists()
    if parent_requested:
        # The host already derived and hashed this frontend from the pinned
        # archive plus candidate patch. Serve it through the real panel route.
        encoded = re.search(rb'<script id="framey-bundle"[^>]*>([^<]+)</script>',
                            Path('/input/browser-panel.html').read_bytes()).group(1)
        (plugin/'dist').mkdir()
        (plugin/'dist/index.js').write_bytes(base64.b64decode(encoded, validate=True))
    marker = plugin/'.frame-control-store.json'
    receipt = dict(storeId=64, version='0.2.7', sha256=DIGEST,
                   compatShims=['syncthing-owned-native-http'])
    marker.write_text(json.dumps(receipt))
    settings = dict(FRAME_LOCAL='1', FRAME_HEADSET_RUNTIME='1',
                    FRAME_CONTROL_DATA_DIR=str(Path.home()/'http-fixture-data'),
                    FRAME_CONTROL_SSH_DIR=str(Path.home()/'http-fixture-ssh'),
                    FRAME_CONTROL_TELEMETRY='0', FRAME_COMPAT_SEARCH_REPORTS='0',
                    FRAME_COMPAT_DB_URL='http://127.0.0.1:9', FRAME_UI_KEY=secrets.token_hex(24))
    previous = {key: os.environ.get(key) for key in settings}
    previous_path = os.environ['PATH']
    previous_cdp = frame_steam.CDP
    os.environ.update(settings)
    sys.path.insert(0, str(bundle/'ui'))
    import server
    assert server.LOCAL and server.HEADSET_RUNTIME
    requests = []
    parent_requests, parent_assets = [], []
    parent_active = False
    parent_started = None
    ssh_records, ssh_lock = [], threading.Lock()
    status_profiles = dict(records=[], overflow=False)
    previous_ssh = server.ssh
    import frame_decky
    import framey_panel
    method_prefix = framey_panel.METHOD_SCRIPT.partition('__FRAMEY_METHOD_PAYLOAD__')[0]
    status_source = (bundle/'ui/frame_status.py').read_text()

    def traced_ssh(*args, **kwargs):
        if not parent_active:
            return previous_ssh(*args, **kwargs)
        source = kwargs.get('stdin')
        kind = ('decky-status' if source in (frame_decky.PROBE, frame_decky.PLUGINS_PROBE, frame_decky.PANEL_STATUS_PROBE) else
                'panel-method' if isinstance(source, str) and source.startswith(method_prefix) else
                'headset-status' if source == status_source else 'other')
        return observe_ssh(previous_ssh, ssh_records, ssh_lock, parent_started, kind, *args,
                           process_profiles=status_profiles, **kwargs)

    # Pass through arguments, results and exceptions unchanged. This observer
    # does not cache, serialize, retry or bypass any receipt/status/RPC check.
    server.ssh = traced_ssh

    class Handler(server.Handler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path == '/cef' and self.local_request():
                with urllib.request.urlopen('http://127.0.0.1:1337/auth/token', timeout=3) as response:
                    token = response.read().decode()
                document = CEF.replace('__FIXTURE_TOKEN__', json.dumps(token))
                self.send_bytes(document.encode(), 'text/html; charset=utf-8')
            elif self.path == '/parent-bootstrap' and self.local_request():
                self.send_bytes(b'<!doctype html><title>Owned HTTP parent bootstrap</title>', 'text/html')
            else:
                if parent_active:
                    assert len(parent_assets) < 100
                    parent_assets.append(self.path.split('?', 1)[0])
                super().do_GET()

        def do_POST(self):
            previous_input = self.rfile
            if parent_active and self.path == '/api/framey/method':
                length = int(self.headers.get('Content-Length', '0'))
                assert 0 < length <= 32768
                raw = self.rfile.read(length)
                req = json.loads(raw)
                self.rfile = io.BytesIO(raw)
                self.parent_request_started = time.monotonic()
                entry = dict(method=req['method'],
                             startedAfterSeconds=round(self.parent_request_started-parent_started, 3))
                if req['method'] == 'framey_http_fetch':
                    entry.update(httpMethod=req['args'][0]['method'], path=req['args'][0]['path'])
                if req['method'] == 'set_setting':
                    entry['setting'] = req['args'][0]['setting']
                self.parent_request = entry
            try:
                super().do_POST()
            finally:
                self.rfile = previous_input

        def send_json(self, obj, status=200):
            entry = getattr(self, 'parent_request', None)
            if entry is not None:
                assert len(parent_requests) < 300
                entry['elapsedSeconds'] = round(time.monotonic()-self.parent_request_started, 3)
                entry['httpStatus'] = status
                if status >= 400:
                    entry['errorCategory'] = safe_error_category(obj)
                value = obj.get('result', {})
                if entry['method'] == 'framey_http_fetch' and isinstance(value, dict):
                    result = value.get('result', {})
                    if isinstance(result, dict):
                        entry['backendStatus'] = result.get('status')
                parent_requests.append(entry)
            super().send_json(obj, status)

    httpd = server.LoopbackServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    base = 'http://127.0.0.1:'+str(httpd.server_port)
    browser = page = None
    report = dict(success=False, realFrameContacted=False, syntheticCef=True,
                  syntheticStoreReceipt=True, realSteamCef=False, managedInstallVerified=False,
                  installerEnabled=False, browserSandboxDisabled=False,
                  productionHttpHandler=True, productionPanelDispatcher=True,
                  productionMethodScript=True, productionLocalSshWrapper=True,
                  uiSourceFingerprints=len(expected))
    report.update(statusImportProfiling=False, productionStatusCommandUnchanged=True)

    def method(name, args, *, digest=DIGEST, plugin_id=64, legacy=True, authenticated=True):
        body = dict(id=plugin_id, receipt=digest, method=name, args=args, legacy=legacy)
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['X-Frame-UI'] = settings['FRAME_UI_KEY']
        connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=30)
        try:
            connection.request('POST', '/api/framey/method', json.dumps(body), headers)
            response = connection.getresponse()
            result = json.loads(response.read())
            entry = dict(method=name, httpStatus=response.status, authenticated=authenticated)
            if name == 'framey_http_fetch':
                entry.update(httpMethod=args[0]['method'], path=args[0]['path'])
            requests.append(entry)
            return response.status, result
        finally:
            connection.close()

    def legacy(name, **kwargs):
        status, reply = method(name, [kwargs])
        assert status == 200, (status, reply)
        value = reply['result']
        assert value['success'] is True, value
        return value['result']

    def fetch(verb, route, headers=None):
        return legacy('framey_http_fetch', method=verb, path=route, headers=headers or {})

    try:
        denied = {}
        args = [dict(method='GET', path='/__decky-watchdog/state', headers={})]
        for label, options, status in [
            ('missingUiKey', dict(authenticated=False), 403),
            ('staleReceipt', dict(digest='0'*64), 400),
            ('wrongPlugin', dict(plugin_id=65), 400),
            ('modernHttpCall', dict(legacy=False), 400),
        ]:
            code, _ = method('framey_http_fetch', args, **options)
            assert code == status, (label, code)
            denied[label] = code
        marker.write_text(json.dumps({**receipt, 'compatShims': []}))
        try:
            code, _ = method('framey_http_fetch', args)
            assert code == 400
            denied['missingHttpShim'] = code
        finally:
            marker.write_text(json.dumps(receipt))
        assert prop(service, 'MainPID') == '0'
        profile = Path.home()/'http-fixture-browser'
        assert not profile.exists()
        with (Path.home()/'http-fixture-browser.log').open('w+') as log:
            browser = subprocess.Popen(['/usr/bin/chromium', '--headless', '--disable-gpu',
                '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
                '--user-data-dir='+str(profile), '--remote-debugging-address=127.0.0.1',
                '--remote-debugging-port=8080', base+'/cef'], stdout=log, stderr=log,
                start_new_session=True)
            frame_steam.CDP = 'http://127.0.0.1:8080/json'
            def ready():
                nonlocal page
                if browser.poll() is not None:
                    raise RuntimeError('Fixture Chromium exited')
                try:
                    candidate = frame_steam.Page()
                    if candidate.eval('typeof DeckyBackend?.call') != 'function':
                        candidate.sock.close()
                        return False
                    page = candidate
                    return True
                except (OSError, frame_steam.Fail):
                    return False
            wait(ready, 'private CEF RPC fixture')
            saved = json.loads(legacy('get_settings_json'))
            assert saved['is_setup'] is True and saved['api_key'] and saved['port'] == 8384
            state = fetch('GET', '/__decky-watchdog/state')
            assert state['status'] == 200 and state['body'].strip() == 'stopped'
            if parent_requested:
                from syncthing_http_parent import exercise as browser_parent
                parent_started = time.monotonic()
                parent_active = True
                try:
                    result = browser_parent(page, base, settings['FRAME_UI_KEY'], browser.pid,
                                            legacy, runtime_identity, service)
                    result.update(httpRequests=parent_requests, requestedAssets=parent_assets)
                    report['browserParent'] = result
                finally:
                    parent_active = False
            assert fetch('POST', '/__decky-watchdog/start')['status'] == 204
            response = wait_authenticated_rest(fetch, saved['api_key'], wait)
            pids = runtime_identity(service)
            assert response['status'] == 200 and json.loads(response['body'])['myID']
            assert fetch('GET', '/rest/system/status')['status'] == 403
            assert fetch('POST', '/__decky-watchdog/stop')['status'] == 204
            assert prop(service, 'MainPID') == '0'
            assert all(not Path('/proc/'+str(pid)).exists() for pid in pids)
            state = fetch('GET', '/__decky-watchdog/state')
            assert state['status'] == 200 and state['body'].strip() == 'stopped'
            report.update(rejectedRequests=denied, actualSignedProcessPids=pids,
                          actualDeckyRpc=True, authenticatedSyncthingRest=True,
                          serviceStartStopVerified=True, stoppedStateBeforeAndAfter=True,
                          requests=requests, success=True)
    finally:
        report.update(requests=requests, rejectedRequests=denied)
        if parent_requested:
            report.update(parentHttpRequests=parent_requests, parentRequestedAssets=parent_assets,
                          parentSshTrace=ssh_records, statusProcessProfiles=status_profiles)
        if page:
            try:
                report['fixtureCefTrace'] = page.eval(
                    '({records:window.fixtureRpcTrace,overflow:window.fixtureTraceOverflow,'
                    'authenticatedSocketCount:window.fixtureSocketCount,issuedRequestCount:window.fixtureRequestCount})')
            except (OSError, frame_steam.Fail) as error:
                report['fixtureCefTraceUnavailable'] = safe_error_category(error)
            finally:
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
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=5)
        report['httpServerStopped'] = not worker.is_alive()
        marker.unlink()
        if parent_requested:
            (plugin/'dist/index.js').unlink()
            (plugin/'dist').rmdir()
        (plugin/'plugin.json').unlink()
        plugin.rmdir()
        report['ownedReceiptRemoved'] = not plugin.exists()
        server.ssh = previous_ssh
        report['sshObserverRemoved'] = server.ssh is previous_ssh
        os.environ['PATH'] = previous_path
        frame_steam.CDP = previous_cdp
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        progress = dict(report)
        if 'browserParent' in progress:
            progress['browserParent'] = {k:v for k,v in progress['browserParent'].items() if k!='screenshots'}
        emit_gateway_progress(progress)
    assert report['ownedBrowserReaped'] and report['httpServerStopped'] and report['ownedReceiptRemoved']
    return report
