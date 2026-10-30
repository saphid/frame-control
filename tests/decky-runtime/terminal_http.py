"""Unchanged production HTTP/events with an isolated Terminal candidate only.

The CEF protocol facade and managed release receipt are synthetic. The actual
Decky user service, production parent, panel, SSH wrapper and event script run
unchanged in a networkless owned VM. This is never a real Steam/Frame test.
"""
from contextlib import redirect_stdout
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

from syncthing_http import CEF as RPC_CEF, observe_ssh, safe_error_category
from syncthing_http_parent import command, install_child_harness, sandboxed_renderers
from terminal_browser import COMMAND, PROBE, screenshot
from syncthing_service import stop_decky_service


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
                    'KillMode=mixed\n')
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
    status_requests, ssh_records, ssh_lock = [], [], threading.Lock()
    status_profiles = dict(records=[], overflow=False)
    previous_ssh = None
    started = time.monotonic()
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
        import frame_decky
        previous_ssh = server.ssh
        status_source = (bundle/'ui/frame_status.py').read_text()

        def traced_ssh(*args, **kwargs):
            source = kwargs.get('stdin')
            kind = ('decky-status' if source in (frame_decky.PROBE, frame_decky.PLUGINS_PROBE, frame_decky.PANEL_STATUS_PROBE) else
                    'headset-status' if source == status_source else 'other')
            return observe_ssh(previous_ssh, ssh_records, ssh_lock, started, kind, *args,
                               process_profiles=status_profiles, **kwargs)

        # Reuse the bounded passive observer: arguments, timeouts, responses
        # and exceptions pass through without caching, retries or bypasses.
        server.ssh = traced_ssh
        class Handler(server.Handler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                assert len(assets) < 200
                assets.append(self.path.split('?', 1)[0])
                self.fixture_status_started = time.monotonic() if self.path in ('/api/decky', '/api/decky/panel-status') else None
                self.fixture_request = None
                if self.path == '/cef' and self.local_request():
                    self.send_bytes(cef_document(token).encode(), 'text/html; charset=utf-8')
                elif self.path == '/parent-bootstrap' and self.local_request():
                    self.send_bytes(b'<!doctype html><title>Owned Terminal HTTP bootstrap</title>', 'text/html')
                else:
                    super().do_GET()

            def do_POST(self):
                self.fixture_status_started = None
                self.fixture_request = None
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
                status_started = getattr(self, 'fixture_status_started', None)
                if status_started is not None:
                    entry = dict(startedAfterSeconds=round(status_started-started, 3),
                                 elapsedSeconds=round(time.monotonic()-status_started, 3),
                                 httpStatus=status)
                    if status == 200:
                        entry.update(running=obj.get('running'),
                                     pluginCount=len(obj.get('plugins', [])))
                    else:
                        entry['errorCategory'] = safe_error_category(obj)
                    with ssh_lock:
                        assert len(status_requests) < 100, 'Status HTTP trace limit exceeded'
                        status_requests.append(entry)
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
            # A completed HTTP event response precedes the child renderer's
            # paint. Require actual output rows, excluding command echo, before
            # taking evidence. This reads DOM only; it never supplies output.
            old_input = "await new Promise(resolve=>setTimeout(resolve,2500));stage('output');"
            assert PROBE.count(old_input) == 1
            driver = PROBE.replace(old_input, """
await wait(()=>[...document.querySelectorAll('.xterm-rows > div')]
 .some(row=>row.textContent.trim()==='framey-browser-output'));
await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);stage('output');""")
            old_stage = 'text:text().slice(0,3000),errors'
            assert driver.count(old_stage) == 1
            driver = driver.replace(old_stage, old_stage+""",
 terminalRows:[...document.querySelectorAll('.xterm-rows > div')].slice(0,200).map(row=>row.textContent.slice(0,512))""")
            report['childHarness'] = install_child_harness(page, panel_url,
                driver+";window.terminalDomHarnessReady=true", "window.terminalDomHarnessReady===true")
            for action, label in [('create', 'terminal'), ('input', 'output'), ('close', 'removed')]:
                page.eval('window.advanceTerminal('+json.dumps(action)+','+json.dumps(COMMAND)+')')
                def advanced():
                    failure = page.eval('window.terminalFailure')
                    assert failure is None, failure
                    return page.eval('window.terminalStage')
                stage = until_ready(advanced, 'production Terminal '+label, timeout=90)
                assert stage['stage'] == label and not stage['errors'], stage
                stages.append(stage)
                if action == 'create':
                    # A textarea appears before asynchronous configuration and
                    # connectIO finish. Observe the real production replies;
                    # never synthesize loaded state or skip frontend setup.
                    until_ready(lambda: any(entry['request'].get('method') == 'send_terminal_buffer'
                                and entry['httpStatus'] == 200 and entry['response'].get('result') is True
                                for entry in requests), 'actual frontend Terminal subscription/buffer', timeout=90)
                    terminal_lists = [entry['response']['result'] for entry in requests
                                      if entry['request'].get('method') == 'get_terminals'
                                      and entry['response'].get('result')]
                    assert len(terminal_lists) == 1 and len(terminal_lists[0]) == 1
                    shell_pid = terminal_lists[0][0]['pid']
                    directory = Path('/proc')/str(shell_pid)
                    assert directory.stat().st_uid == os.getuid()
                    chain = [shell_pid]
                    while chain[-1] != pid:
                        parent = int(Path('/proc/'+str(chain[-1])+'/stat').read_text().rsplit(')', 1)[1].split()[1])
                        assert parent > 1 and parent not in chain and len(chain) < 16
                        chain.append(parent)
                    report['browserShell'] = dict(pid=shell_pid, uid=os.getuid(), ancestryToDeckyService=chain)
                if action == 'input':
                    assert any(row.strip() == 'framey-browser-output' for row in stage['terminalRows']), stage
                    def output_delivered():
                        delivered = [event for entry in requests if entry['route'] == '/api/framey/events'
                                     for event in entry['response'].get('events', [])]
                        output = ''.join(event['args'][0] for event in delivered)
                        return delivered if '\r\nframey-browser-output\r\n' in output else None
                    report['deliveredEvents'] = until_ready(output_delivered, 'actual production event output', timeout=60)
                    marker = (home/'framey-browser-terminal-marker').read_bytes()
                    assert marker == b'framey-browser-terminal\n'
                    report['privateMarkerSha256'] = hashlib.sha256(marker).hexdigest()
                if action == 'close':
                    until_ready(lambda: not Path('/proc/'+str(shell_pid)).exists(),
                                'actual browser-created shell reaped', timeout=30)
                    report['browserShellReaped'] = True
                shots[label] = screenshot(page)
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
        # Never run before the real request: warming imports here cannot make
        # the original replay pass. Its exception and failed outcome persist.
        status_failed = any(entry['kind'] == 'decky-status' and entry['outcome'] == 'failure'
                            for entry in ssh_records)
        if not report['success'] and status_failed and previous_ssh is not None:
            try:
                from terminal_status_diagnostic import diagnose
                report['statusFailureDiagnostic'] = diagnose(frame_decky.PANEL_STATUS_PROBE, home)
            except Exception:
                report['statusFailureDiagnosticUnavailable'] = True
        if page:
            if not report['success']:
                try:
                    report['parentFailureState'] = page.eval("({panel:document.getElementById('frameyPanelStatus')?.textContent,deckyState:document.getElementById('deckyState')?.textContent?.slice(0,512),installed:document.getElementById('deckyInstalled')?.innerText,errors:window.terminalErrors,failure:window.terminalFailure,stage:window.terminalStage})")
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
        if previous_ssh is not None:
            server.ssh = previous_ssh
            report['sshObserverRemoved'] = server.ssh is previous_ssh
        report.update(statusHttpRequests=status_requests, parentSshTrace=ssh_records,
                      statusProcessProfiles=status_profiles, productionStatusCommandUnchanged=True)
        stop_error = None
        try:
            with redirect_stdout(sys.stderr):
                stop_decky_service(unit.name, report)
            report['ownedDeckyServiceStopped'] = True
        except Exception as error:
            # Retain failed stop diagnostics and restore only this VM's dummy
            # unit/receipt; the error remains fatal after the report is emitted.
            stop_error = error
            report['success'] = False
            report['ownedDeckyServiceStopped'] = False
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
        if stop_error is not None:
            raise stop_error
    assert all(report[key] for key in ('ownedTargetClosed', 'ownedBrowserReaped', 'httpServerStopped',
               'ownedDeckyServiceStopped', 'originalUnitRestored', 'ownedBundleRemoved', 'sshObserverRemoved'))
    return report
