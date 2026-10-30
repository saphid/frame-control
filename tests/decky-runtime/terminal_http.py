"""Unchanged production HTTP/events with an isolated Terminal candidate only.

The CEF protocol facade and managed release receipt are synthetic. The actual
Decky user service, production parent, panel, SSH wrapper and event script run
unchanged in a networkless owned VM. This is never a real Steam/Frame test.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from syncthing_http import CEF as RPC_CEF
from syncthing_http_parent import command, install_child_harness, sandboxed_renderers
from terminal_browser import COMMAND, PROBE, screenshot


def cef_document(token):
    # Extend only the explicit test facade with Decky 3.3.0's event envelope.
    # Production framey-events.js owns filtering, session bounds and cursors.
    needle = '  const reply=JSON.parse(event.data);'
    assert RPC_CEF.count(needle) == 1
    document = RPC_CEF.replace(needle, needle+r'''
  if(reply.type===5&&reply.event==='loader/plugin_event'){
   if(window.fixtureNativeEvents.length>=200)throw Error('Fixture event trace overflow');
   window.fixtureNativeEvents.push(reply.args[0]);
   for(const listener of [...window.fixtureListeners])listener(...reply.args);
   return;
  }''')
    document = document.replace('<script>', '<script>window.fixtureNativeEvents=[];window.fixtureListeners=new Set();', 1)
    document = document.replace('</script>', r'''
DeckyBackend.addEventListener=(name,listener)=>{
 if(name!=='loader/plugin_event'||typeof listener!=='function')throw Error('Unexpected fixture listener');
 window.fixtureListeners.add(listener);
};
DeckyBackend.removeEventListener=(name,listener)=>{
 if(name!=='loader/plugin_event')throw Error('Unexpected fixture listener removal');
 window.fixtureListeners.delete(listener);
};
</script>''')
    return document.replace('__FIXTURE_TOKEN__', json.dumps(token))


def exercise(name, home):
    assert os.getuid() == 1100 and home == Path('/home/tester')
    assert Path('/framey-owned-vm').read_text() == 'Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    from check import until_ready
    import frame_steam
    base = home/'.local/share/frame-control/decky'
    unit = home/'.config/systemd/user/frame-control-decky.service'
    original_unit = unit.read_bytes()
    assert original_unit == b'# Private fixture marker; no real service manager is contacted.\n'
    receipt = base/'.frame-control/receipt.json'
    assert not receipt.exists()
    receipt.parent.mkdir()
    bundle = home/'.local/share/frame-control/headset/bundle'
    assert not bundle.exists()
    inputs = json.loads(Path('/input/terminal-inputs.json').read_text())
    sources = {k:v for k,v in inputs['sourceSha256'].items()
               if k.startswith(('ui/', 'apk-catalog/'))}
    for path, digest in sources.items():
        source = Path('/repo')/path
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        target = bundle/path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o700 if path == 'ui/local-bin/ssh' else 0o600)
    settings = dict(FRAME_LOCAL='1', FRAME_HEADSET_RUNTIME='1',
                    FRAME_CONTROL_DATA_DIR=str(home/'terminal-http-data'),
                    FRAME_CONTROL_SSH_DIR=str(home/'terminal-http-ssh'),
                    FRAME_CONTROL_TELEMETRY='0', FRAME_COMPAT_SEARCH_REPORTS='0',
                    FRAME_COMPAT_DB_URL='http://127.0.0.1:9', FRAME_UI_KEY=secrets.token_hex(24))
    saved = {key:os.environ.get(key) for key in settings}
    saved_path, saved_cdp = os.environ['PATH'], frame_steam.CDP
    os.environ.update(settings)
    # This synthetic receipt makes production managed-status checks possible;
    # it is not evidence for the production installation/update workflow.
    receipt.write_text(json.dumps(dict(managedBy='Frame Control', version='v3.3.0')))
    unit.write_text('[Unit]\nDescription=Owned Terminal HTTP candidate fixture\n'
                    '[Service]\nType=simple\nWorkingDirectory=/home/tester\n'
                    'ExecStart=/usr/bin/env UNPRIVILEGED_PATH='+str(base)+' PRIVILEGED_PATH='+str(base)+
                    ' CHOWN_PLUGIN_PATH=0 LIVE_RELOAD=0 USE_CEF_CLOSE_WORKAROUND=0 KEEP_SYSTEMD_SERVICE=1 '+str(base/'PluginLoader')+'\n'
                    'KillMode=control-group\nTimeoutStopSec=10\n')
    def ctl(*args, check=True):
        return subprocess.run(['/usr/bin/systemctl', '--user', *args], check=check,
                              capture_output=True, text=True, timeout=30)
    report = dict(success=False, actualDeckyUserService=True, syntheticCef=True,
                  syntheticManagedReceipt=True, realSteamCef=False, realFrameContacted=False,
                  managedInstallVerified=False, productionAdaptationEnabled=False,
                  physicalControllerVerified=False, syntheticInput=True,
                  productionParentUnchanged=True, productionPanelUnchanged=True,
                  productionHttpHandler=True, productionMethodScript=True,
                  productionEventScript=True, productionLocalSshWrapper=True,
                  browserSandboxDisabled=False, uiSourceFingerprints=sources)
    browser = cef = page = httpd = worker = None
    stages, shots, requests, assets = [], {}, [], []
    temporary = tempfile.TemporaryDirectory(prefix='framey-terminal-http-')
    try:
        ctl('daemon-reload'); ctl('start', unit.name)
        pid = int(ctl('show', unit.name, '--property=MainPID', '--value').stdout.strip())
        assert pid > 0 and Path('/proc/'+str(pid)+'/exe').resolve() == base/'PluginLoader'
        report['deckyMainPid'] = pid
        def token_ready():
            with urllib.request.urlopen('http://127.0.0.1:1337/auth/token', timeout=2) as response:
                return response.read().decode()
        token = until_ready(token_ready, 'owned Decky user service', timeout=60)
        import server
        assert server.LOCAL and server.HEADSET_RUNTIME
        class Handler(server.Handler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                assert len(assets) < 200
                assets.append(self.path.split('?', 1)[0])
                if self.path == '/cef' and self.local_request():
                    self.send_bytes(cef_document(token).encode(), 'text/html; charset=utf-8')
                elif self.path == '/parent-bootstrap' and self.local_request():
                    self.send_bytes(b'<!doctype html><title>Owned Terminal HTTP bootstrap</title>', 'text/html')
                else:
                    super().do_GET()

            def do_POST(self):
                original = self.rfile
                if self.path in ('/api/framey/method', '/api/framey/events'):
                    length = int(self.headers.get('Content-Length', '0'))
                    assert 0 < length <= 32768
                    raw = self.rfile.read(length)
                    body = json.loads(raw)
                    self.rfile = io.BytesIO(raw)
                    assert body['id'] == 65
                    if body.get('method') == 'send_terminal_input':
                        assert body['args'][1] in (COMMAND, COMMAND.replace('\n', '\r'))
                    self.fixture_request = dict(route=self.path, request=body)
                try:
                    super().do_POST()
                finally:
                    self.rfile = original

            def send_json(self, obj, status=200):
                entry = getattr(self, 'fixture_request', None)
                if entry is not None:
                    assert len(requests) < 500
                    requests.append(dict(entry, httpStatus=status, response=obj))
                super().send_json(obj, status)

        httpd = server.LoopbackServer(('127.0.0.1', 0), Handler)
        httpd.daemon_threads = True
        worker = threading.Thread(target=httpd.serve_forever, daemon=True); worker.start()
        origin = 'http://127.0.0.1:'+str(httpd.server_port)
        with (home/'terminal-http-browser.log').open('w') as log:
            browser = subprocess.Popen(['/usr/bin/chromium', '--headless', '--disable-gpu',
                '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
                '--user-data-dir='+temporary.name, '--window-size=1240,1400',
                '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=8080', origin+'/cef'],
                stdout=log, stderr=log, start_new_session=True)
            frame_steam.CDP = 'http://127.0.0.1:8080/json'
            def opened_cef():
                nonlocal cef
                assert browser.poll() is None, 'Owned sandboxed Chromium exited'
                try:
                    candidate = frame_steam.Page()
                    if candidate.eval("typeof DeckyBackend?.addEventListener==='function'"):
                        cef = candidate
                        return True
                    candidate.sock.close()
                except (OSError, frame_steam.Fail):
                    return False
            until_ready(opened_cef, 'owned synthetic CEF', timeout=60)
            found = cef.eval("DeckyBackend.call('loader/get_plugins')")
            assert len(found) == 1 and found[0]['name'] == name and not found[0]['disabled'], found
            report['actualDeckyDiscovery'] = found
            assert cef.eval("DeckyBackend.call('loader/call_plugin_method',"+json.dumps(name)+",'get_terminals')") == []
            bootstrap = r'''
window.terminalStage=null;window.terminalFailure=null;window.terminalErrors=[];
addEventListener('error',e=>terminalErrors.push(e.message));
addEventListener('unhandledrejection',e=>terminalErrors.push(String(e.reason)));
addEventListener('message',e=>{
 if(e.source!==document.getElementById('frameyFrame')?.contentWindow)return;
 if(e.data?.type==='test:stage')window.terminalStage=e.data;
 if(e.data?.type==='test:failure')window.terminalFailure=e.data.error;
});
window.advanceTerminal=(action,command)=>{window.terminalStage=null;
 document.getElementById('frameyFrame').contentWindow.postMessage({type:'test:advance',action,command},'*');};
'''
            target = command(cef, 'Target.createTarget', dict(url=origin+'/parent-bootstrap'))['targetId']
            report['parentTargetId'] = target
            def opened_parent():
                nonlocal page
                try:
                    page = frame_steam.Page('Owned Terminal HTTP bootstrap')
                    return True
                except (OSError, frame_steam.Fail):
                    return False
            until_ready(opened_parent, 'owned production parent', timeout=60)
            command(page, 'Page.enable', {})
            command(page, 'Page.addScriptToEvaluateOnNewDocument', dict(source=bootstrap))
            command(page, 'Emulation.setDeviceMetricsOverride', dict(width=1240, height=1400, deviceScaleFactor=1, mobile=False))
            command(page, 'Page.navigate', dict(url=origin+'/headset#'+settings['FRAME_UI_KEY']))
            until_ready(lambda: page.eval("!![...document.querySelectorAll('#deckyInstalled button')].find(b=>b.textContent==='Open panel'&&!b.disabled)"),
                        'actual service in unchanged production installed list', timeout=90)
            page.eval("[...document.querySelectorAll('#deckyInstalled button')].find(b=>b.textContent==='Open panel').click()")
            until_ready(lambda: page.eval("document.getElementById('frameyPanelStatus')?.textContent==='Plugin panel ready'"),
                        'unchanged production panel ready', timeout=90)
            frame = page.eval("({sandbox:document.getElementById('frameyFrame').getAttribute('sandbox'),src:new URL(document.getElementById('frameyFrame').src).pathname})")
            assert frame == dict(sandbox='allow-scripts allow-popups', src='/framey/panel/65'), frame
            report['iframe'] = frame
            panel_url = page.eval("document.getElementById('frameyFrame').src")
            report['childHarness'] = install_child_harness(page, panel_url,
                PROBE+";window.terminalDomHarnessReady=true", "window.terminalDomHarnessReady===true")
            for action, label in [('create', 'terminal'), ('input', 'output'), ('close', 'removed')]:
                page.eval('window.advanceTerminal('+json.dumps(action)+','+json.dumps(COMMAND)+')')
                def advanced():
                    failure = page.eval('window.terminalFailure')
                    assert failure is None, failure
                    return page.eval('window.terminalStage')
                stage = until_ready(advanced, 'production Terminal '+label, timeout=90)
                assert stage['stage'] == label and not stage['errors'], stage
                stages.append(stage); shots[label] = screenshot(page)
                if action == 'input':
                    assert (home/'framey-browser-terminal-marker').read_bytes() == b'framey-browser-terminal\n'
                    delivered = [event for entry in requests if entry['route'] == '/api/framey/events'
                                 for event in entry['response'].get('events', [])]
                    output = ''.join(event['args'][0] for event in delivered)
                    assert '\r\nframey-browser-output\r\n' in output, output
                    report['deliveredEvents'] = delivered
            assert cef.eval("DeckyBackend.call('loader/call_plugin_method',"+json.dumps(name)+",'get_terminals')") == []
            page.eval("document.getElementById('frameyClose').click()")
            until_ready(lambda: cef.eval('window.fixtureListeners.size===0&&window.__frameyEventBridgeV1.sessions.size===0'),
                        'production event listener cleanup', timeout=30)
            assert not page.eval('window.terminalErrors'), page.eval('window.terminalErrors')
            assert requests and all(entry['httpStatus'] == 200 for entry in requests), requests
            for path in ['/headset', '/framey/panel/65', '/framey-runtime/host.js', '/framey-runtime/react.js', '/framey-runtime/react-dom.js']:
                assert path in assets, path
            report.update(success=True, stages=stages, screenshots=shots,
                requests=requests, assets=assets, productionEventListenerCleanup=True,
                sandboxedRendererPids=sandboxed_renderers(browser.pid),
                fixtureCefTrace=cef.eval('({records:fixtureRpcTrace,overflow:fixtureTraceOverflow,socketCount:fixtureSocketCount,nativeEvents:fixtureNativeEvents})'))
    finally:
        report.update(stages=stages, screenshots=shots, requests=requests, assets=assets)
        if page:
            if not report['success']:
                try:
                    report['parentFailureState'] = page.eval("({panel:document.getElementById('frameyPanelStatus')?.textContent,installed:document.getElementById('deckyInstalled')?.innerText,errors:window.terminalErrors,failure:window.terminalFailure,stage:window.terminalStage})")
                    report['screenshots']['failure'] = screenshot(page)
                except (OSError, frame_steam.Fail):
                    report['parentFailureUnavailable'] = True
            page.sock.close()
        if cef:
            if report.get('parentTargetId'):
                report['ownedTargetClosed'] = command(cef, 'Target.closeTarget', dict(targetId=report['parentTargetId']))['success']
            cef.sock.close()
        if browser:
            if browser.poll() is None:
                os.killpg(browser.pid, signal.SIGTERM)
                try: browser.wait(timeout=10)
                except subprocess.TimeoutExpired: os.killpg(browser.pid, signal.SIGKILL); browser.wait(timeout=10)
            report['ownedBrowserReaped'] = browser.poll() is not None
        if httpd:
            httpd.shutdown(); httpd.server_close(); worker.join(timeout=8)
            report['httpServerStopped'] = not worker.is_alive()
        ctl('stop', unit.name)
        report['ownedDeckyServiceStopped'] = ctl('is-active', unit.name, check=False).returncode != 0
        unit.write_bytes(original_unit); receipt.unlink(); receipt.parent.rmdir()
        ctl('daemon-reload')
        report['originalUnitRestored'] = unit.read_bytes() == original_unit and not receipt.exists()
        shutil.rmtree(bundle)
        report['ownedBundleRemoved'] = not bundle.exists()
        os.environ['PATH'], frame_steam.CDP = saved_path, saved_cdp
        for key, value in saved.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        temporary.cleanup()
        print('FRAMEY_TERMINAL_BROWSER_JSON='+json.dumps(report), file=sys.stderr, flush=True)
    assert all(report[key] for key in ('ownedTargetClosed', 'ownedBrowserReaped', 'httpServerStopped',
               'ownedDeckyServiceStopped', 'originalUnitRestored', 'ownedBundleRemoved'))
    return report
