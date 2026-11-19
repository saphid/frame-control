"""Mailing-list HTTP contract; all requests go to a disposable local server."""
import sandbox  # noqa: F401
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ui'))
import frame_mailing as fm  # noqa: E402


class MailingTransport(unittest.TestCase):
    def setUp(self):
        self.got = []
        self.status, self.answer = 200, b'{"ok":true}'
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.got.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(owner.status)
                self.end_headers()
                self.wfile.write(owner.answer)

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        env = mock.patch.dict('os.environ', {'FRAME_CONTROL_MAILING_LIST_URL':
                              f'http://127.0.0.1:{server.server_port}/api/mailing-list'})
        env.start()
        self.addCleanup(env.stop)

    def test_only_email_consent_and_retry_credentials_leave_the_app(self):
        fm.submit('a' * 64, 7, 'me@example.com')
        fm.submit('a' * 64, 8, '')
        self.assertEqual(self.got, [
            ('/api/mailing-list', {'token': 'a' * 64, 'rev': 7, 'email': 'me@example.com', 'updates': True}),
            ('/api/mailing-list', {'token': 'a' * 64, 'rev': 8, 'email': '', 'updates': False}),
        ])

    def test_unavailable_unconfigured_and_invalid_responses_are_retryable(self):
        for status, answer in ((503, b'{}'), (429, b'{}'), (200, b'not json'),
                               (200, b'[]'), (200, b'{"ok":false}')):
            self.status, self.answer = status, answer
            with self.subTest(status=status, answer=answer), self.assertRaises(fm.SendError):
                fm.submit('a' * 64, 1, 'me@example.com')

    def test_timeout_is_bounded_and_retryable(self):
        with mock.patch.object(fm.urllib.request, 'urlopen', side_effect=TimeoutError) as send:
            with self.assertRaises(fm.SendError):
                fm.submit('a' * 64, 1, 'me@example.com')
        self.assertEqual(send.call_args.kwargs['timeout'], 10)

    def test_real_contact_worker_delivers_join_and_removal(self):
        # Isolate the daemon worker in a short-lived process so it cannot outlive
        # a test's temporary state or mocks. Only the local mailing server is real.
        with tempfile.TemporaryDirectory() as state:
            run = subprocess.run([sys.executable, '-c', '''
import time
import frame_contact as fc
fc.frame_telemetry.post = lambda *args, **kwargs: None
fc.start()
for choice in ({'email': 'me@example.com', 'updates': True}, {'email': ''}):
    fc.save(choice)
    deadline = time.monotonic() + 5
    while fc.state()['waiting'] and time.monotonic() < deadline:
        time.sleep(.01)
    assert not fc.state()['waiting'], 'worker did not drain queue'
'''], cwd=Path(__file__).resolve().parent.parent / 'ui',
                env={**os.environ, 'FRAME_CONTROL_DATA_DIR': state},
                capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual([body['email'] for _, body in self.got], ['me@example.com', ''])
        self.assertEqual([body['rev'] for _, body in self.got], [1, 2])
