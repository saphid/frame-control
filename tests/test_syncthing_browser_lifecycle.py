"""Browser startup time cannot consume probe time or leave profile writers."""
import ast
import base64
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class BrowserLifecycle(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1]/'scripts/framey-test-syncthing-browser.py'
        tree = ast.parse(source.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('wait_for_result', 'stop_browser')]
        self.clock = SimpleNamespace(now=0)
        def advance(seconds):
            self.clock.now += seconds
        self.scope = dict(os=os, signal=signal, subprocess=subprocess, base64=base64, json=json,
                          time=SimpleNamespace(monotonic=lambda:self.clock.now, sleep=advance),
                          frame_steam=SimpleNamespace(Fail=RuntimeError))
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), self.scope)

    def probe(self, attach_at, finish_at):
        page = Mock(next_id=0)
        expected = {'type':'test:done', 'welcome':True, 'syntheticInput':True, 'realBackend':False}
        page.eval.side_effect = lambda expression: json.dumps(expected) if self.clock.now>=finish_at else 'Pending'
        page._recv.side_effect = lambda: json.dumps({'id':page.next_id, 'result':{'data':base64.b64encode(b'fixture screenshot').decode()}})
        def attach(title):
            if self.clock.now < attach_at:
                raise RuntimeError('Chrome still starting')
            return page
        self.scope['frame_steam'].Page = attach
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder/'profile').mkdir()
            (folder/'profile/DevToolsActivePort').write_text('12345\nfixture')
            report, screenshot = self.scope['wait_for_result'](Mock(poll=lambda:None), folder, io.StringIO())
        return report, screenshot, page, expected

    def test_slow_start_retains_the_full_probe_budget(self):
        report, screenshot, page, expected = self.probe(attach_at=30, finish_at=49)
        self.assertEqual(report, expected)
        self.assertEqual(screenshot, b'fixture screenshot')
        self.assertGreaterEqual(self.clock.now, 49)
        page.sock.close.assert_called_once()

    def test_attached_but_incomplete_probe_remains_a_failure(self):
        report, screenshot, page, _ = self.probe(attach_at=30, finish_at=100)
        self.assertIs(report['passed'], False)
        self.assertEqual(report['error'], 'Browser fixture did not finish')
        self.assertGreaterEqual(self.clock.now, 50)
        self.assertLess(self.clock.now, 51)
        self.assertEqual(screenshot, b'fixture screenshot')
        page.sock.close.assert_called_once()

    def test_browser_that_never_attaches_has_a_distinct_bounded_failure(self):
        report, screenshot, page, _ = self.probe(attach_at=100, finish_at=100)
        self.assertIs(report['passed'], False)
        self.assertEqual(report['error'], 'Browser fixture did not attach')
        self.assertGreaterEqual(self.clock.now, 45)
        self.assertLess(self.clock.now, 46)
        self.assertIsNone(screenshot)
        page.eval.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux process-group fixture')
    def test_exited_launcher_does_not_leave_a_child_writing_its_profile(self):
        with tempfile.TemporaryDirectory(prefix='framey-browser-group-') as root:
            ready = Path(root)/'child.pid'
            child = ('import os,signal,time; from pathlib import Path; '
                     'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                     'Path('+repr(str(ready))+').write_text(str(os.getpid())); time.sleep(60)')
            parent = 'import subprocess,sys; subprocess.Popen([sys.executable,"-c",'+repr(child)+']).wait()'
            browser = subprocess.Popen([sys.executable, '-c', parent], start_new_session=True)
            try:
                end = time.monotonic()+5
                while not ready.is_file() and time.monotonic()<end:
                    time.sleep(.01)
                self.assertTrue(ready.is_file(), 'child must start before cleanup')
                self.scope['stop_browser'](browser)
                self.assertIsNotNone(browser.poll())
                status = Path('/proc')/ready.read_text()/'stat'
                end = time.monotonic()+2
                while status.exists() and time.monotonic()<end:
                    if status.read_text().rsplit(')',1)[1].split()[0] in ('Z','X'):
                        break
                    time.sleep(.01)
                if status.exists():
                    self.assertIn(status.read_text().rsplit(')',1)[1].split()[0], ('Z','X'))
            finally:
                try:
                    os.killpg(browser.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                browser.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
