"""Media transfer through the real HTTP/SSH path; the fake has no VR renderer."""
import http.client
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys

import harness
from harness import api, ok, ssh, wait_for

harness.require()


class Media(harness.FrameTestCase):
    def test_desktop_direct_copy_uses_local_path_and_ssh(self):
        # A small file exercises the route used for large desktop transfers.
        # It does not establish 26.5 GB throughput or external USB behavior.
        source = Path(self.path('USB media')) / 'movie sample.bin'
        source.parent.mkdir()
        source.write_bytes(b'direct copy through the fake Frame\n')
        body = {'action': 'copy-local', 'path': str(source)}
        remote_file = '~/Downloads/' + shlex.quote(source.name)
        self.addCleanup(ssh, 'rm -f ' + remote_file)
        self.assertEqual(api('POST', '/api/transfer', body)[0], 403,
                         'the ordinary browser server must refuse a local path')

        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]

        def request(method, path, payload=None):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            try:
                data = json.dumps(payload).encode() if payload is not None else None
                headers = {'X-Frame-UI': '1'}
                if data is not None:
                    headers['Content-Type'] = 'application/json'
                conn.request(method, path, data, headers)
                response = conn.getresponse()
                return response.status, json.loads(response.read())
            finally:
                conn.close()

        # Private SSH mode permits an isolated second server without taking
        # the primary server's one-instance lock or starting another sync loop.
        env = dict(os.environ, FRAME_CONTROL_APP='1', FRAME_PRIVATE_SSH='1',
                   FRAME_ALIAS='frame', FRAME_CONTROL_LOCAL_LINKS='1')
        log_path = self.path('desktop-server.log')
        with open(log_path, 'wb') as log:
            proc = subprocess.Popen([sys.executable, str(harness.ROOT / 'ui' / 'server.py'),
                                     '--port', str(port)], cwd=harness.ROOT, env=env,
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            try:
                def ready():
                    try:
                        return request('GET', '/api/host')[0] == 200
                    except OSError:
                        return False

                try:
                    wait_for(ready, 20, 'desktop-mode server to listen')
                except AssertionError as error:
                    self.fail(f'{error}; exit={proc.poll()}; log={Path(log_path).read_text(errors="replace")[-1200:]}')
                status, result = request('POST', '/api/transfer', body)
                self.assertEqual(status, 200, result)
                self.assertEqual(result['message'], 'Sent movie sample.bin to ~/Downloads/')
                self.assertEqual(ssh('cat ' + remote_file), source.read_text())
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

    def test_upload_and_list_without_launching_a_viewer(self):
        # The transfer endpoint doesn't decode. Rendering belongs to the real
        # headset smoke checks documented in docs/vr-video.md.
        self.assertEqual(ssh('stat -c "%U:%G %a" ~/.local/share').strip(), 'steamos:steamos 755')
        result = ok('POST', '/api/upload', raw=b'fake-media', headers={
            'X-Mode': 'media', 'X-Filename': 'test_SBS.png'})
        identity = result['id']
        try:
            files = ok('POST', '/api/media', {'action': 'list'})['files']
            self.assertIn(identity, [f['id'] for f in files])
            self.assertEqual(ssh('cat ~/Videos/FrameControl/'+identity), 'fake-media')
        finally:
            ssh('rm -rf ~/Videos/FrameControl/'+identity.split('/')[0])
