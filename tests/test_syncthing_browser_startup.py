"""Opt-in real-browser regression for the VM fixture's parent/child handshake.

Set FRAMEY_STARTUP_BROWSER to an absolute Chrome/Chromium executable path.
The test uses a temporary profile, loopback HTTP and a minimal opaque child;
it never contacts Decky, Syncthing, Steam or a Frame.
"""
import ast
import base64
import http.server
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
BROWSER = os.environ.get('FRAMEY_STARTUP_BROWSER')
ARCHIVE = os.environ.get('FRAMEY_STARTUP_SYNCTHING_ARCHIVE')
CHILD = '''<html lang="en"><script>
addEventListener('message', event => {
  if (event.source === parent && event.data?.type === 'framey:cache:seed')
    parent.postMessage({type:'framey:ready'}, '*');
});
parent.postMessage({type:'framey:cache:init', session:'fixture'}, '*');
(async () => {
  let parentDomDenied=false, connectionDenied=false;
  try { parent.document.documentElement; } catch (e) { parentDomDenied=true; }
  try { await fetch(new URL('/forbidden', location.href)); }
  catch (e) { connectionDenied=true; }
  parent.postMessage({type:'test:sandbox',parentDomDenied,connectionDenied}, '*');
})();
</script></html>'''


@unittest.skipUnless(BROWSER, 'set FRAMEY_STARTUP_BROWSER for isolated browser proof')
class BrowserStartup(unittest.TestCase):
    def document_builder(self):
        source = ROOT / 'tests/decky-runtime/syncthing_browser.py'
        tree = ast.parse(source.read_text())
        nodes = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == 'browser_documents'
                 or isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id in ('PARENT', 'PROBE')
                     for target in node.targets)]
        scope = dict(base64=base64, json=json)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
        return scope

    def cdp(self):
        spec = importlib.util.spec_from_file_location('startup_cdp', ROOT / 'ui/frame_steam.py')
        cdp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cdp)
        return cdp

    def test_parent_can_receive_the_childs_first_message_during_streaming(self):
        scope, cdp = self.document_builder(), self.cdp()

        for delay, padding in ((0, 0), (7, 0), (0, 2 * 1024**2)):
            with self.subTest(parent_script_delay=delay, padding_bytes=padding):
                documents = scope['browser_documents'](CHILD + '<!--' + 'x' * padding + '-->')
                documents['/'] = documents['/'].replace('</script>', '''
addEventListener('message',event=>{
 if(event.source===document.getElementById('panel').contentWindow &&
    event.data?.type==='test:sandbox')
  window.childSandbox={...event.data,origin:event.origin};
});
</script>''')
                cut = documents['/'].index('<script>' + scope['PARENT'])
                self.check_startup(cdp, documents, cut, delay)

    @unittest.skipUnless(ARCHIVE, 'set FRAMEY_STARTUP_SYNCTHING_ARCHIVE for full frontend proof')
    def test_actual_framey_runtime_and_pinned_frontend_initialize(self):
        spec = importlib.util.spec_from_file_location('startup_package',
            ROOT / 'scripts/framey-test-syncthing-flatpak-package.py')
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        payloads, _metadata = package.browser_payloads(Path(ARCHIVE).read_bytes())
        scope = self.document_builder()
        documents = scope['browser_documents'](payloads['browser-panel.html'].decode())
        self.check_startup(self.cdp(), documents, 0, 0, full_frontend=True)

    def test_readiness_wait_observes_parent_handler_after_native_listener_checkpoint(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = ROOT / 'tests/decky-runtime/syncthing_browser.py'
        node = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'ready_page')
        capture = Mock()
        capture.eval.return_value = {'ready': True}
        scope = dict(time=time, frame_steam=SimpleNamespace(
            Page=lambda _title: capture, Fail=RuntimeError))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
        scope['ready_page']({}, deadline=time.monotonic()+1)
        expression = capture.eval.call_args.args[0]
        cdp, browser, page = self.cdp(), None, None
        with tempfile.TemporaryDirectory(prefix='framey-native-listener-order-') as scratch:
            profile = Path(scratch) / 'profile'
            try:
                with (Path(scratch) / 'browser.log').open('w+') as log:
                    browser = subprocess.Popen([
                        BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                        '--no-default-browser-check', '--disable-background-networking',
                        '--disable-component-extensions-with-background-pages',
                        '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
                        '--user-data-dir='+str(profile),
                        'data:text/html,<title>Framey listener order</title>'],
                        stdout=log, stderr=log, start_new_session=True)
                    deadline = time.monotonic()+15
                    while time.monotonic() < deadline and page is None:
                        self.assertIsNone(browser.poll(), 'isolated browser exited')
                        try:
                            port = (profile/'DevToolsActivePort').read_text().splitlines()[0]
                            cdp.CDP = 'http://127.0.0.1:'+port+'/json'
                            page = cdp.Page('Framey listener order')
                        except (OSError, IndexError, cdp.Fail):
                            time.sleep(.05)
                    self.assertIsNotNone(page, 'isolated CDP page unavailable')
                    for order in ('observer-first', 'parent-first', 'never-ready'):
                        with self.subTest(order=order):
                            setup = r'''
window.ready=false;window.orderEvents=[];window.startupErrors=[];
window.startupEvents=[];window.startupState={};
const nativeTimeout=window.orderNativeTimeout||setTimeout;
window.orderNativeTimeout=nativeTimeout;
window.setTimeout=(fn,ms)=>nativeTimeout(()=>{
 if(ms>500)orderEvents.push('fallback-budget');fn();},ms);
window.orderParentHandler=event=>{
 if(event.data!=='framey-order-fixture')return;
 if(ORDER!=='never-ready'){ready=true;orderEvents.push('parent-ready');}
 removeEventListener('message',orderParentHandler);
};
if(ORDER!=='observer-first')addEventListener('message',orderParentHandler);
nativeTimeout(()=>{
 if(ORDER==='observer-first')addEventListener('message',orderParentHandler);
 postMessage('framey-order-fixture','*');
},20);
'''.replace('ORDER', json.dumps(order))
                            result = page.eval('(()=>{'+setup+'return ('+expression+
                                               ').then(value=>({value,events:orderEvents}));})()')
                            expected_ready = order != 'never-ready'
                            self.assertIs(result['value']['ready'], expected_ready)
                            self.assertEqual('fallback-budget' in result['events'], not expected_ready,
                                             'ready message must resolve before the fallback budget')
                            print('Framey native listener order proof: '+json.dumps(
                                dict(order=order, result=result), sort_keys=True))
            finally:
                if page is not None:
                    page.sock.close()
                if browser is not None:
                    try:
                        os.killpg(browser.pid, signal.SIGTERM)
                        browser.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(browser.pid, signal.SIGKILL)
                        browser.wait(timeout=5)
                    except ProcessLookupError:
                        browser.wait(timeout=5)

    def check_startup(self, cdp, documents, cut, delay, full_frontend=False):
        requests, rpc_calls = [], []
        started = time.monotonic()
        progress = {}
        spec = importlib.util.spec_from_file_location('startup_progress_receiver',
            ROOT / 'tests/decky-runtime/syncthing_browser.py')
        receiver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(receiver)

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                requests.append(self.path)
                if self.path not in documents:
                    self.send_error(404)
                    return
                data = documents[self.path].encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                if self.path == '/':
                    self.wfile.write(data[:cut])
                    self.wfile.flush()
                    time.sleep(delay)
                    self.wfile.write(data[cut:])
                else:
                    self.wfile.write(data)

            def do_POST(self):
                if self.path == '/startup':
                    length = int(self.headers.get('Content-Length', '0'))
                    accepted = receiver.record_startup_progress(
                        progress, json.loads(self.rfile.read(length)), time.monotonic()-started)
                    self.send_response(204 if accepted else 400)
                    self.end_headers()
                    return
                if self.path != '/rpc':
                    self.send_error(404)
                    return
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 32768:
                    self.send_error(413)
                    return
                req = json.loads(self.rfile.read(length))
                if req.get('legacy') is not True or req.get('method') != 'get_settings_json':
                    self.send_error(400)
                    return
                rpc_calls.append(req['method'])
                data = json.dumps(dict(success=True, result=json.dumps(dict(
                    config_version=2, is_setup=False, api_key='')))).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = page = None
        pending_pages, readiness = [], {}
        with tempfile.TemporaryDirectory(prefix='framey-startup-test-') as scratch:
            try:
                profile = Path(scratch) / 'profile'
                with (Path(scratch) / 'browser.log').open('w+') as log:
                    browser = subprocess.Popen([
                        BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                        '--no-default-browser-check', '--disable-background-networking',
                        '--disable-component-extensions-with-background-pages',
                        '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
                        '--user-data-dir=' + str(profile),
                        'http://127.0.0.1:' + str(server.server_port) + '/'],
                        stdout=log, stderr=log, start_new_session=True)
                    deadline = time.monotonic() + 20
                    ready = False
                    while time.monotonic() < deadline:
                        self.assertIsNone(browser.poll(), 'isolated browser exited')
                        if page is None:
                            try:
                                port = (profile / 'DevToolsActivePort').read_text().splitlines()[0]
                                cdp.CDP = 'http://127.0.0.1:' + port + '/json'
                                receiver.frame_steam.CDP = cdp.CDP
                                page = receiver.ready_page(readiness, started, pending_pages)
                            except (OSError, IndexError, receiver.frame_steam.Fail):
                                pass
                        if page is not None:
                            try:
                                ready = page.eval("typeof ready !== 'undefined' && ready")
                            except cdp.Fail:
                                ready = False
                            progress_ready = any(v['type']=='panel-ready' for v in progress.get('records', []))
                            if ready and progress_ready and (bool(rpc_calls) if full_frontend else
                                          page.eval('!!window.childSandbox')):
                                break
                        time.sleep(.1)
                    self.assertTrue(ready, 'child seed request was lost during parent delivery')
                    self.assertEqual(pending_pages, [])
                    if delay:
                        self.assertTrue(any(a['connectionReused'] for a in readiness['readinessAttempts']))
                    self.assertEqual(page.eval('window.startupErrors'), [])
                    state = page.eval('window.startupState')
                    self.assertTrue(state['parentInstalled'])
                    self.assertGreaterEqual(state['cacheRequests'], 1)
                    self.assertEqual(state['seedReplies'], state['cacheRequests'])
                    self.assertGreaterEqual(state['readyMessages'], 1)
                    records = progress['records']
                    self.assertLessEqual(len(records), 16)
                    self.assertTrue(any(v['type']=='parent-installed' for v in records))
                    self.assertTrue(any(v['type']=='cache-seeded' for v in records))
                    self.assertTrue(any(v['type']=='panel-ready' and v['state']['readyMessages']>=1
                                        for v in records))
                    self.assertTrue(all(v['receivedAfterSeconds']>=0 and v['atMs']>=0 for v in records))
                    self.assertIn('/panel', requests)
                    self.assertNotIn('/forbidden', requests)
                    if full_frontend:
                        self.assertTrue(rpc_calls)
                        events = page.eval('window.startupEvents')
                        self.assertIn('framey:ready', [event['type'] for event in events])
                        self.assertTrue(all(event['atMs'] >= 0 for event in events))
                    else:
                        self.assertEqual(page.eval('window.childSandbox'), dict(
                            type='test:sandbox', parentDomDenied=True,
                            connectionDenied=True, origin='null'))
                    self.assertEqual(page.eval("document.getElementById('panel').getAttribute('sandbox')"),
                                     'allow-scripts')
                    # Large panel bytes never become target URLs returned by
                    # /json on every CDP readiness attempt.
                    with urllib.request.urlopen(cdp.CDP, timeout=2) as response:
                        targets = response.read(65537)
                    self.assertLessEqual(len(targets), 65536)
                    self.assertTrue(all(len(t['url']) < 256 for t in json.loads(targets)))
                    # The failure-only reader must inspect the opaque child
                    # directly without changing its sandbox or driving the UI.
                    spec = importlib.util.spec_from_file_location('startup_final_reader',
                        ROOT / 'tests/decky-runtime/syncthing_browser.py')
                    reader = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(reader)
                    reader.frame_steam.CDP = cdp.CDP
                    final = reader.final_browser_state()
                    self.assertFalse(final['timedOut'], final)
                    self.assertEqual(final['returnCode'], 0, final)
                    self.assertEqual(final['phases'], ['interpreter-started', 'module-imported',
                                                      'targets-read', 'parent-connected', 'iframe-connected'])
                    self.assertEqual([s['target'] for s in final['snapshots']], ['parent', 'iframe'])
                    self.assertTrue(final['snapshots'][0]['state']['ready'], final)
                    self.assertEqual(final['snapshots'][1]['state']['documentState'], 'complete')
                    if full_frontend:
                        self.assertIn('Start Setup', final['snapshots'][1]['state']['rootText'])
                        self.assertNotIn('.syncthing-identicon', final['snapshots'][1]['state']['rootText'])
                    print('Framey final browser state proof: '+json.dumps(final, sort_keys=True))
                    print('Framey parent progress proof: '+json.dumps(progress, sort_keys=True))
                    print('Framey readiness connection proof: '+json.dumps(readiness, sort_keys=True))
            finally:
                while pending_pages:
                    pending_pages.pop().sock.close()
                if page is not None:
                    page.sock.close()
                if browser is not None:
                    try:
                        os.killpg(browser.pid, signal.SIGTERM)
                        browser.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(browser.pid, signal.SIGKILL)
                        browser.wait(timeout=5)
                    except ProcessLookupError:
                        browser.wait(timeout=5)
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
