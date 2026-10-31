"""Real owned loopback HTTP discovery and WebSocket input, with no Steam/Frame."""
import sandbox  # noqa: F401
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ui'))
import frame_steam


@contextmanager
def devtools(mode='chunked'):
    requests, messages = [], []
    discovery_closed = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_):
            pass

        def finish(self):
            super().finish()
            if self.path.startswith('/json'):
                discovery_closed.set()

        def do_GET(self):
            requests.append(self.path)
            if self.path.startswith('/json'):
                if mode == 'unavailable':
                    self.send_response(503)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                data = json.dumps([dict(title='Other'), dict(title='SharedJSContext',
                    webSocketDebuggerUrl=f'ws://127.0.0.1:{self.server.server_port}/owned')]).encode()
                if mode == 'malformed':
                    data = b'{'
                self.send_response(200)
                if mode == 'chunked':
                    self.send_header('Transfer-Encoding', 'chunked')
                    self.end_headers()
                    for part in (data[:9], data[9:]):
                        self.wfile.write(f'{len(part):x}\r\n'.encode()+part+b'\r\n')
                    self.wfile.write(b'0\r\n\r\n')
                else:
                    self.send_header('Content-Length', str(len(data)+(10 if mode == 'truncated' else 0)))
                    self.end_headers()
                    self.wfile.write(data)
                    if mode == 'truncated':
                        self.close_connection = True
                return
            self.send_response(101)
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'Upgrade')
            self.end_headers()
            header = self.rfile.read(2)
            size = header[1] & 127
            if size == 126:
                size = struct.unpack('>H', self.rfile.read(2))[0]
            mask = self.rfile.read(4)
            data = self.rfile.read(size)
            message = json.loads(bytes(v ^ mask[i % 4] for i, v in enumerate(data)))
            messages.append(message)
            reply = json.dumps(dict(id=message['id'], result=dict(result=dict(value={'owned': True})))).encode()
            self.wfile.write(bytes([0x81, len(reply)])+reply)
            self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
    worker.start()
    try:
        with patch.object(frame_steam, 'CDP', f'http://127.0.0.1:{server.server_port}/json?owned=1'):
            yield requests, messages, discovery_closed
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
        assert not worker.is_alive()


class SteamCdp(unittest.TestCase):
    def test_chunked_discovery_selects_title_and_completes_websocket_eval(self):
        with devtools() as (requests, messages, closed):
            page = frame_steam.Page()
            try:
                self.assertEqual(page.eval('({owned:true})'), {'owned': True})
            finally:
                page.sock.close()
            self.assertTrue(closed.wait(2), 'discovery HTTP connection must close')
        self.assertEqual(requests, ['/json?owned=1', '/owned'])
        self.assertEqual(messages[0]['method'], 'Runtime.evaluate')
        self.assertEqual(messages[0]['params']['expression'], '({owned:true})')

    def test_unavailable_and_truncated_discovery_fail_before_websocket_and_close(self):
        for mode, detail in [('unavailable', 'HTTP 503'), ('truncated', 'bytes read')]:
            with self.subTest(mode=mode), devtools(mode) as (requests, messages, closed):
                with self.assertRaisesRegex(frame_steam.Fail, detail):
                    frame_steam.Page()
                self.assertTrue(closed.wait(2))
                self.assertEqual(requests, ['/json?owned=1'])
                self.assertEqual(messages, [])

    def test_malformed_json_also_closes_discovery_connection(self):
        with devtools('malformed') as (requests, messages, closed):
            with self.assertRaises(json.JSONDecodeError):
                frame_steam.Page()
            self.assertTrue(closed.wait(2))
            self.assertEqual(messages, [])

    def test_cold_helper_import_omits_general_url_opener(self):
        result = subprocess.run([sys.executable, '-c',
            'import sys; import frame_steam; print("urllib.request" in sys.modules)'],
            cwd=ROOT/'ui', capture_output=True, text=True, check=True, timeout=20)
        self.assertEqual(result.stdout.strip(), 'False')
