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


ROOT = Path(__file__).resolve().parents[1]
BROWSER = os.environ.get('FRAMEY_STARTUP_BROWSER')
CHILD = '''<html lang="en"><script>
addEventListener('message', event => {
  if (event.source === parent && event.data?.type === 'framey:cache:seed')
    parent.postMessage({type:'framey:ready'}, '*');
});
parent.postMessage({type:'framey:cache:init', session:'fixture'}, '*');
</script></html>'''


@unittest.skipUnless(BROWSER, 'set FRAMEY_STARTUP_BROWSER for isolated browser proof')
class BrowserStartup(unittest.TestCase):
    def test_parent_can_receive_the_childs_first_message_during_streaming(self):
        source = ROOT / 'tests/decky-runtime/syncthing_browser.py'
        tree = ast.parse(source.read_text())
        nodes = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == 'browser_document'
                 or isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id in ('PARENT', 'PROBE')
                     for target in node.targets)]
        scope = dict(base64=base64, json=json)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
        document = scope['browser_document'](CHILD)
        cut = document.index('<script>' + scope['PARENT'])
        spec = importlib.util.spec_from_file_location('startup_cdp', ROOT / 'ui/frame_steam.py')
        cdp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cdp)

        for delay in (0, 7):
            with self.subTest(parent_script_delay=delay):
                self.check_startup(cdp, document, cut, delay)

    def check_startup(self, cdp, document, cut, delay):
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
                self.wfile.write(document[:cut].encode())
                self.wfile.flush()
                time.sleep(delay)
                self.wfile.write(document[cut:].encode())

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
                            if ready:
                                break
                        time.sleep(.1)
                    self.assertTrue(ready, 'child seed request was lost during parent delivery')
                    self.assertEqual(page.eval('window.startupErrors'), [])
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
