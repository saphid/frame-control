"""Production local HTTP/panel dispatcher with actual Decky and fixture CEF only."""
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
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
<script>window.DeckyBackend={call:async(route,...args)=>{
const token=__FIXTURE_TOKEN__;
return new Promise((resolve,reject)=>{
 const ws=new WebSocket('ws://127.0.0.1:1337/ws?auth='+encodeURIComponent(token));
 const timer=setTimeout(()=>{ws.close();reject(Error('Fixture Decky RPC timeout'));},20000);
 ws.onopen=()=>ws.send(JSON.stringify({type:0,id:1,route,args}));
 ws.onerror=()=>{clearTimeout(timer);reject(Error('Fixture Decky WebSocket failed'));};
 ws.onmessage=event=>{const reply=JSON.parse(event.data);if(reply.id!==1)return;
  ws.send(JSON.stringify({type:3,id:1}));clearTimeout(timer);ws.close();
  if(reply.type===1)resolve(reply.result);else reject(Error('Fixture Decky RPC rejected'));};
});}};</script>'''


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

    class Handler(server.Handler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path == '/cef' and self.local_request():
                with urllib.request.urlopen('http://127.0.0.1:1337/auth/token', timeout=3) as response:
                    token = response.read().decode()
                document = CEF.replace('__FIXTURE_TOKEN__', json.dumps(token))
                self.send_bytes(document.encode(), 'text/html; charset=utf-8')
            else:
                super().do_GET()

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
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=5)
        report['httpServerStopped'] = not worker.is_alive()
        marker.unlink()
        (plugin/'plugin.json').unlink()
        plugin.rmdir()
        report['ownedReceiptRemoved'] = not plugin.exists()
        os.environ['PATH'] = previous_path
        frame_steam.CDP = previous_cdp
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        print('FRAMEY_HTTP_GATEWAY_PROGRESS_JSON='+json.dumps(report), flush=True)
    assert report['ownedBrowserReaped'] and report['httpServerStopped'] and report['ownedReceiptRemoved']
    return report
