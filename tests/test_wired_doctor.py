"""The wired doctor never requires a cable or contacts the real Frame in tests."""
import sandbox  # noqa: F401
from pathlib import Path
import http.client
import json
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ui'))
import frame_wired_doctor as wired


class FakeProbe:
    def __init__(self, source='10.86.200.234', port=True, ssh_code=0, stderr=''):
        self.source, self.port, self.ssh_code, self.stderr = source, port, ssh_code, stderr
        self.calls = []

    def route_source(self):
        self.calls.append('route')
        return self.source

    def port_open(self):
        self.calls.append('port')
        return self.port

    def host_key_name(self, alias):
        self.calls.append('config')
        return alias + '.example.ts.net'

    def ssh_check(self, alias, name):
        self.calls.append(('ssh', alias, name))
        return subprocess.CompletedProcess([], self.ssh_code, '', self.stderr)


class WiredDoctor(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the page script')
    def test_page_is_on_demand_and_clears_stale_results(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/wired_doctor.mjs')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_known_usb_route_and_pinned_login(self):
        probe = FakeProbe()
        report = wired.diagnose('frame', probe=probe)
        self.assertEqual(report['state'], 'ready')
        self.assertEqual([c['status'] for c in report['checks']], ['ok', 'ok', 'ok'])
        self.assertEqual(probe.calls, ['route', 'port', 'config', ('ssh', 'frame', 'frame.example.ts.net')])

    def test_other_route_never_contacts_target(self):
        for source in ('100.91.1.2', '192.168.1.10', '127.0.0.1'):
            probe = FakeProbe(source=source)
            report = wired.diagnose(probe=probe)
            self.assertEqual(report['state'], 'unknown')
            self.assertEqual(probe.calls, ['route'])
            self.assertIn('no headset was contacted', report['checks'][-1]['detail'])

    def test_closed_port_skips_ssh_and_key_mismatch_is_not_bypassed(self):
        closed = FakeProbe(port=False)
        self.assertEqual(wired.diagnose(probe=closed)['state'], 'partial')
        self.assertEqual(closed.calls, ['route', 'port'])
        mismatch = FakeProbe(ssh_code=255, stderr='Host key verification failed.')
        report = wired.diagnose(probe=mismatch)
        self.assertEqual(report['checks'][-1]['status'], 'warning')
        self.assertIn('do not bypass', report['checks'][-1]['detail'])

    def test_invalid_alias_and_headset_mode_do_not_probe(self):
        probe = FakeProbe()
        with self.assertRaises(ValueError):
            wired.diagnose('-oProxyCommand=bad', probe=probe)
        self.assertFalse(wired.diagnose(local=True, probe=probe)['supported'])
        self.assertEqual(probe.calls, [])

    def test_real_command_uses_strict_identity_and_disables_proxy(self):
        with patch.object(wired.frame_host, 'run_ssh', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            wired.Probe().ssh_check('frame', 'frame.example.ts.net')
        argv = run.call_args.args[0]
        self.assertIn('StrictHostKeyChecking=yes', argv)
        self.assertIn('HostName=10.86.200.233', argv)
        self.assertIn('HostKeyAlias=frame.example.ts.net', argv)
        self.assertIn('ProxyCommand=none', argv)
        self.assertIn('ControlMaster=no', argv)
        self.assertEqual(argv[-2:], ['frame', 'true'])
        self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)


class HttpBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server_module = server
        cls.httpd = server.LoopbackServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, path, authorized=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_address[1], timeout=5)
        headers = {'X-Frame-UI': self.server_module.UI_KEY} if authorized else {}
        conn.request('GET', path, headers=headers)
        response = conn.getresponse()
        result = response.status, response.read()
        conn.close()
        return result

    def test_auth_alias_and_page_without_headset_link(self):
        with patch.object(self.server_module, 'ssh', side_effect=AssertionError('no generic SSH')), \
                patch.object(self.server_module, 'working', side_effect=AssertionError('no headset lock')), \
                patch.object(wired, 'diagnose', return_value={'supported': True, 'checks': []}) as probe:
            self.assertEqual(self.request('/api/host/wired', authorized=False)[0], 403)
            probe.assert_not_called()
            code, data = self.request('/api/host/wired?alias=bedroom')
            self.assertEqual(code, 200)
            self.assertTrue(json.loads(data)['supported'])
            probe.assert_called_once_with('bedroom', local=self.server_module.LOCAL)
        code, page = self.request('/wired-doctor')
        self.assertEqual(code, 200)
        self.assertIn(b'No checks have run', page)

    def test_invalid_alias_and_headset_page_guard(self):
        self.assertEqual(self.request('/api/host/wired?alias=-bad')[0], 400)
        with patch.object(self.server_module, 'LOCAL', True):
            self.assertEqual(self.request('/wired-doctor')[0], 400)
            code, body = self.request('/api/host/wired')
            self.assertEqual(code, 200)
            self.assertFalse(json.loads(body)['supported'])


if __name__ == '__main__':
    unittest.main()
