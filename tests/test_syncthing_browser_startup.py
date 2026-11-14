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

    def check_startup(self, cdp, documents, cut, delay, full_frontend=False):
        requests, rpc_calls = [], []

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
        with tempfile.TemporaryDirectory(prefix='framey-startup-test-') as scratch:
            try:
                profile = Path(scratch) / 'profile'
                with (Path(scratch) / 'browser.log').open('w+') as log:
                    browser = subprocess.Popen([
                        BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                        '--no-default-browser-check', '--disable-background-networking',
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
                                page = cdp.Page('Owned Syncthing actual backend')
                            except (OSError, IndexError, cdp.Fail):
                                pass
                        if page is not None:
                            try:
                                ready = page.eval("typeof ready !== 'undefined' && ready")
                            except cdp.Fail:
                                ready = False
                            if ready and (bool(rpc_calls) if full_frontend else
                                          page.eval('!!window.childSandbox')):
                                break
                        time.sleep(.1)
                    self.assertTrue(ready, 'child seed request was lost during parent delivery')
                    self.assertEqual(page.eval('window.startupErrors'), [])
                    state = page.eval('window.startupState')
                    self.assertTrue(state['parentInstalled'])
                    self.assertGreaterEqual(state['cacheRequests'], 1)
                    self.assertEqual(state['seedReplies'], state['cacheRequests'])
                    self.assertGreaterEqual(state['readyMessages'], 1)
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
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
