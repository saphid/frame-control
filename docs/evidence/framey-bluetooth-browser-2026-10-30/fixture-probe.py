"""Owned VM: official Bluetooth panel, synthetic app context, real legacy RPC."""
import asyncio, base64, hashlib, http.server, io, json, os, shutil, signal
import subprocess, sys, threading, time, traceback, urllib.request, zipfile
from pathlib import Path
from unittest.mock import patch
sys.path[:0] = ['/repo/ui', '/input']
import frame_decky_store, framey_panel, frame_steam
from browser_common import Bridge, PARENT, screenshot

DIGEST = 'f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5'
MAC = '42:00:00:00:00:01'
sys.path.insert(0, '/repo/tests/decky-runtime')
import bluetooth_bluez

class BluetoothBridge(Bridge):
    def call(self, method, args):
        assert method in {'get_bluetooth_status','get_paired_devices_with_info','get_device_info','toggle_device_connection','toggle_bluetooth'}
        assert isinstance(args,list)
        if method in {'get_bluetooth_status','get_paired_devices_with_info'}:assert args==[]
        if method=='get_device_info':assert args==[MAC]
        if method=='toggle_bluetooth':assert len(args)==1 and type(args[0]) is bool
        if method=='toggle_device_connection':assert len(args)==2 and args[0]==MAC and type(args[1]) is bool
        result=asyncio.run_coroutine_threadsafe(self.invoke(method,args),self.loop).result(12)
        with self.lock:
            assert len(self.calls)<500
            self.calls.append(dict(method=method,args=args,result=result))
        return result

    def native(self, method, *args):
        return self.call(method,list(args))


PROBE = r'''
const errors=[];addEventListener('error',e=>errors.push(e.message));addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
const wait=async f=>{const end=Date.now()+45000;while(Date.now()<end){if(f())return;await new Promise(r=>setTimeout(r,100));}throw Error('Bluetooth DOM timed out');};
const toggle=()=>document.querySelector('#bluetooth input[type=checkbox]');
const rows=()=>[...document.querySelectorAll('.connect-container')];
const row=()=>rows().find(r=>r.querySelector('.device-name')?.textContent==='Private Controller');
const info=()=>rows().map(r=>({name:r.querySelector('.device-name')?.textContent,status:r.querySelector('.device-status')?.textContent,off:r.classList.contains('off')}));
const stage=name=>parent.postMessage({type:'test:stage',stage:name,text:document.getElementById('framey-root').innerText,powered:toggle()?.checked,devices:info(),errors},'*');
let busy=false;addEventListener('message',async e=>{if(e.source!==parent||e.data?.type!=='test:advance'||busy)return;busy=true;
try{
 await wait(()=>toggle()&&rows().length===2);
 if(e.data.action==='inspect'){await wait(()=>row()?.querySelector('.device-status')?.textContent.includes('73%'));stage('loaded');}
 if(e.data.action==='connection'){row().click();await wait(()=>row()?.querySelector('.device-status span')?.textContent.trim().toLowerCase()===(e.data.command?'connected':'not connected')&&!row()?.querySelector('.device-spinner'));stage(e.data.command?'connected':'disconnected');}
 if(e.data.action==='power'){toggle().click();await wait(()=>toggle().checked===e.data.command&&rows().every(r=>r.classList.contains('off')===!e.data.command));stage(e.data.command?'on':'off');}
 if(e.data.action==='off-activation'){row().click();await new Promise(r=>setTimeout(r,1000));stage('off-activation');}
 if(e.data.action==='refresh'){const b=[...document.querySelectorAll('#bluetooth label')].find(l=>l.querySelector('strong')?.textContent==='Devices')?.querySelector('button');if(!b)throw Error('Bluetooth refresh absent');await wait(()=>b.querySelector('.refresh-icon')&&!b.querySelector('.refresh-icon').classList.contains('spinning'));b.click();await new Promise(r=>setTimeout(r,1000));stage('refreshed');}
}catch(error){parent.postMessage({type:'test:failure',error:String(error)},'*');}finally{busy=false;}});
'''


def main():
    assert os.getuid() == 1100 and Path('/framey-owned-vm').read_text() == 'Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    home = Path.home(); base = home / '.local/share/frame-control/decky'
    (base / 'plugins').mkdir(parents=True)
    unit = home / '.config/systemd/user/frame-control-decky.service'
    unit.parent.mkdir(parents=True); unit.write_text('# private fixture marker\n')
    tools = home / 'bin'; tools.mkdir()
    ctl = tools / 'systemctl'; ctl.write_text('#!/bin/sh\ncase "$*" in *is-active*) exit 3;; *) exit 0;; esac\n'); ctl.chmod(0o700)
    env = dict(os.environ, PATH=str(tools) + ':' + os.environ['PATH'])
    data = Path('/repo/tests/fixtures/framey-official/18.zip').read_bytes()
    assert hashlib.sha256(data).hexdigest() == DIGEST
    Path('/tmp/frame-control-decky-plugin-bluetooth-browser').write_bytes(data)
    install = subprocess.run([sys.executable, '-', 'install', 'bluetooth-browser', '18', DIGEST,
        'Bluetooth', '3.1.1', '-'], input=frame_decky_store.apply_script(18, DIGEST),
        text=True, capture_output=True, env=env, timeout=30)
    assert install.returncode == 0, install.stderr
    plugin = base / 'plugins/Bluetooth'
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=[n for n in archive.namelist() if n.endswith(('.py','.js'))]
        for name in names:
            assert (plugin/Path(name).relative_to('Bluetooth')).read_bytes()==archive.read(name)
        frontend = archive.read('Bluetooth/dist/index.js')
    loader = base / 'PluginLoader'; shutil.copyfile('/input/PluginLoader', loader); loader.chmod(0o700)
    env.update(UNPRIVILEGED_PATH=str(base), PRIVILEGED_PATH=str(base), CHOWN_PLUGIN_PATH='0',
        LIVE_RELOAD='0', USE_CEF_CLOSE_WORKAROUND='0', KEEP_SYSTEMD_SERVICE='1')
    report = dict(success=False, realFrameContacted=False, physicalControllerVerified=False,
        syntheticInput=True, syntheticBluez=True, hostBusExposed=False, realRadioVerified=False, realPairingVerified=False, privateBridge=True,
        productionHttpParentVerified=False, realSteamCef=False, browserSandboxDisabled=False,
        stages=[], screenshots={}, loaderStops=[])
    backend = browser = page = server = worker = bridge = None
    bridges = []; processes = []; log = (home / 'loader.log').open('w+')
    private = []

    def wait_value(fn, seconds=45):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = fn()
            if value:
                return value
            time.sleep(.1)
        raise AssertionError('Bluetooth fixture condition not ready')

    def start():
        process = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
        processes.append(process)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                connection = BluetoothBridge('Bluetooth'); bridges.append(connection)
                assert connection.native('get_bluetooth_status') is True
                return process, connection
            except (OSError, AssertionError, RuntimeError):
                if bridges and bridges[-1].thread.is_alive():
                    bridges[-1].close()
                time.sleep(.2)
        raise RuntimeError('Bluetooth loader unavailable')

    def stop():
        started = time.monotonic(); backend.terminate(); code = backend.wait(timeout=10)
        assert code == 0, code
        report['loaderStops'].append(dict(returncode=code, elapsedSeconds=round(time.monotonic()-started, 3)))

    def advance(action, value=None):
        page.eval('window.advance(' + json.dumps(action) + ',' + json.dumps(value) + ')')
        def read():
            failure = page.eval('window.failure||null'); assert not failure, failure
            return page.eval('window.stage')
        stage = wait_value(read); assert stage['errors'] == [], stage
        report['stages'].append(stage); return stage

    try:
        def until(fn,label):return wait_value(fn,30)
        private=list(bluetooth_bluez.start(Path('/repo'),env,log,processes,until))
        backend, bridge = start()
        with patch.object(framey_panel, '_owned_dist', return_value=(None, frontend, DIGEST)):
            panel = framey_panel.panel(18).decode()
        report['panelSha256'] = hashlib.sha256(panel.encode()).hexdigest()
        for route, name in [('react.js', 'vendor/react-18.3.1.min.js'), ('react-dom.js', 'vendor/react-dom-18.3.1.min.js'), ('host.js', 'framey-host.js')]:
            panel = panel.replace('src="/framey-runtime/' + route + '"', 'src="data:text/javascript;base64,' + base64.b64encode((Path('/repo/ui') / name).read_bytes()).decode() + '"')
        panel = panel.replace('<html lang="en">', '<html lang="en"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\' data: blob:; connect-src \'none\'; style-src \'unsafe-inline\'; img-src data:">').replace('</html>', '<script>' + PROBE + '</script></html>')
        parent = PARENT
        document = '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\' data: blob:; frame-src data:; connect-src \'self\'; style-src \'unsafe-inline\'; img-src data:"><title>Owned Bluetooth pages</title><style>body{margin:0;background:#0d1925;color:white}iframe{width:1200px;height:1000px;border:0}</style><iframe id="panel" sandbox="allow-scripts" src="data:text/html;base64,' + base64.b64encode(panel.encode()).decode() + '"></iframe><script>' + parent + '</script>'

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                if self.path == '/': raw = document.encode(); kind = 'text/html; charset=utf-8'
                else: self.send_error(404); return
                self.send_response(200); self.send_header('Content-Type', kind); self.end_headers(); self.wfile.write(raw)
            def do_POST(self):
                try:
                    length = int(self.headers.get('Content-Length', '0')); assert 0 < length < 131072
                    request = json.loads(self.rfile.read(length)); assert self.path == '/rpc' and request['legacy'] is False
                    raw = json.dumps(bridge.call(request['method'], request['args'])).encode(); self.send_response(200)
                except BaseException as error:
                    raw = json.dumps(dict(error=str(error))).encode(); self.send_response(500)
                    report.setdefault('bridgeFailures', []).append(str(error))
                self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(raw)

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.daemon_threads = True
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        profile = home / 'browser-profile'; url = 'http://127.0.0.1:' + str(server.server_port) + '/'
        with (home / 'browser.log').open('w') as blog:
            browser = subprocess.Popen(['/usr/bin/chromium', '--headless', '--disable-gpu', '--no-first-run',
                '--no-default-browser-check', '--disable-background-networking', '--user-data-dir=' + str(profile),
                '--window-size=1240,1100', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', url],
                stdout=blog, stderr=blog, start_new_session=True)
            wait_value(lambda: (profile / 'DevToolsActivePort').is_file(), 60)
            frame_steam.CDP = 'http://127.0.0.1:' + (profile / 'DevToolsActivePort').read_text().splitlines()[0] + '/json'
            wait_value(lambda: any(p.get('title') == 'Owned Bluetooth pages' for p in json.load(urllib.request.urlopen(frame_steam.CDP, timeout=5))), 60)
            page = frame_steam.Page('Owned Bluetooth pages')

            wait_value(lambda: page.eval('typeof ready!=="undefined"&&ready'), 60)
            stage=advance('inspect');assert len(stage['devices'])==2 and stage['powered'] is True
            assert 'Unpaired Canary' not in stage['text'] and '73%' in stage['text']
            assert 'Not connected' in next(d['status'] for d in stage['devices'] if d['name']=='Private Headphones')
            report['screenshots']['initial']=screenshot(page)
            advance('connection',False);assert json.loads(bluetooth_bluez.STATE.read_text())['connected'] is False
            report['screenshots']['disconnected']=screenshot(page)
            advance('connection',True);assert json.loads(bluetooth_bluez.STATE.read_text())['connected'] is True
            advance('power',False);wait_value(lambda:json.loads(bluetooth_bluez.STATE.read_text())['adapterPowered'] is False);state=json.loads(bluetooth_bluez.STATE.read_text());assert state['adapterPowered'] is False and state['otherAdapterPowered'] is False
            report['screenshots']['poweredOff']=screenshot(page)
            before=state['writes'];advance('off-activation');assert json.loads(bluetooth_bluez.STATE.read_text())['writes']==before
            advance('power',True);wait_value(lambda:json.loads(bluetooth_bluez.STATE.read_text())['adapterPowered'] is True);state=json.loads(bluetooth_bluez.STATE.read_text());assert state['adapterPowered'] is True and state['otherAdapterPowered'] is False
            refresh_before=sum(c['method']=='get_paired_devices_with_info' for c in bridge.calls)
            advance('refresh');wait_value(lambda:sum(c['method']=='get_paired_devices_with_info' for c in bridge.calls)>refresh_before)
            page.eval("location.href='about:blank'");time.sleep(.5);bridge.close();stop()
            backend,bridge=start();page.eval('location.href='+json.dumps(url));time.sleep(.3)
            wait_value(lambda:page.eval('typeof ready!=="undefined"&&ready'),60);advance('inspect')
            report['screenshots']['restarted']=screenshot(page)
            state=json.loads(bluetooth_bluez.STATE.read_text());assert state['adapterPowered'] is True and state['connected'] is True and state['otherAdapterPowered'] is False
            assert state['writes']==[['Disconnect',bluetooth_bluez.DEVICE],['Connect',bluetooth_bluez.DEVICE],['Set',bluetooth_bluez.ROOT,'org.bluez.Adapter1','Powered',False],['Set',bluetooth_bluez.ROOT,'org.bluez.Adapter1','Powered',True]]
            report['privateBluezState']=state
            renderers = []
            for process in Path('/proc').iterdir():
                if not process.name.isdecimal(): continue
                try:
                    if b'--type=renderer' not in (process / 'cmdline').read_bytes(): continue
                    fields = dict(line.split(':', 1) for line in (process / 'status').read_text().splitlines() if ':' in line)
                    assert fields['Seccomp'].strip() == '2' and fields['NoNewPrivs'].strip() == '1'
                    lineage = [int(process.name)]
                    while lineage[-1] != browser.pid:
                        pid = int(Path('/proc/' + str(lineage[-1]) + '/stat').read_text().rsplit(')', 1)[1].split()[1])
                        assert pid > 1 and pid not in lineage and len(lineage) < 16; lineage.append(pid)
                    renderers.append(dict(pid=int(process.name), ancestryToBrowser=lineage, seccomp=2, noNewPrivs=1))
                except FileNotFoundError: pass
            assert renderers
            report.update(success=True,actualFrontendConnectionRoundTrip=True,actualFrontendPowerRoundTrip=True,
                poweredOffActivationDidNotWrite=True,actualFrontendRefresh=True,backendRestartVisible=True,
                pairedFilterAndBatteryVisible=True,unchangedPublishedSources=len(names),sandboxedRenderers=renderers)

    except BaseException as error:
        report.update(error=str(error), traceback=traceback.format_exc())
        if page is not None:
            try:
                report['failureDom'] = page.eval("document.body.innerText")
                report['screenshots']['failure'] = screenshot(page)
            except BaseException as diagnostic_error: report['failureDiagnosticError'] = str(diagnostic_error)
    finally:
        if page is not None: page.sock.close()
        if browser is not None:
            if browser.poll() is None:
                os.killpg(browser.pid, signal.SIGTERM)
                try: browser.wait(timeout=8)
                except subprocess.TimeoutExpired: os.killpg(browser.pid, signal.SIGKILL); browser.wait(timeout=8)
            report['ownedBrowserReaped'] = browser.poll() is not None
        if server is not None:
            server.shutdown(); server.server_close(); worker.join(8); report['ownedHttpStopped'] = not worker.is_alive()
        try:
            if bridge is not None: bridge.close()
            if backend is not None and backend.poll() is None: stop()
        except BaseException as error: report.update(cleanupError=str(error), success=False)
        for process in reversed(private):
            if process.poll() is None:process.terminate();process.wait(timeout=5)
        report['privateBusAndServiceReaped']=all(p.poll() is not None for p in private)
        log.flush(); console = (home / 'loader.log').read_text(); report['loaderLog'] = console
        report['loaderShutdownsLogged'] = console.count('Shutdown finished.')
        if report['loaderShutdownsLogged'] != 2 or any(s in console for s in ('Error during shutdown:', 'asyncio.exceptions.CancelledError', 'Task was destroyed but it is pending')):
            report['success'] = False
        report['calls'] = [c for b in bridges for c in b.calls]
        report['nativeEventSocketsClosed'] = all(not b.thread.is_alive() for b in bridges)
        report['ownedLoaderProcessesReaped'] = all(p.poll() is not None for p in processes)
        if (home / 'browser.log').is_file(): report['browserLogTail'] = (home / 'browser.log').read_text(errors='replace')[-6000:]
        log.close(); (home / 'bluetooth-browser-result.json').write_text(json.dumps(report))
        print(json.dumps(dict(success=report['success'], error=report.get('error'))))


if __name__ == '__main__': main()
