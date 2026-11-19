"""Execute the exact fixture cleanup AST with private real process groups."""
import ast
import ctypes
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
from unittest.mock import Mock, call
SOURCE = Path(os.environ.get('FRAMEY_OWNED_BROWSER_SOURCE', str(Path(__file__).resolve().parents[1] / 'tests/decky-runtime/syncthing_browser.py')))

def cleanup_scope():
    tree = ast.parse(SOURCE.read_text())
    exercise = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'exercise'))
    outer = next((n for n in exercise.body if isinstance(n, ast.Try) and n.finalbody))
    branch = next((n for n in outer.finalbody if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and (n.test.id == 'browser')))
    wrapper = ast.parse('def cleanup(browser, report):\n    pass\n').body[0]
    wrapper.body = [branch]
    helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('stop_browser', 'wait_browser_group')]
    scope = dict(os=os, signal=signal, subprocess=subprocess, time=time, Path=Path)
    exec(compile(ast.fix_missing_locations(ast.Module(body=helpers + [wrapper], type_ignores=[])), str(SOURCE), 'exec'), scope)
    return scope

class CleanupBudgets(unittest.TestCase):

    def scope(self):
        scope = cleanup_scope()
        # The guest is Linux; keep mocked deadline controls portable on CI hosts.
        scope['signal'] = SimpleNamespace(SIGTERM=15, SIGKILL=9)
        return scope

    def test_original_two_ten_second_wait_budgets_and_owned_group_signals(self):
        scope = self.scope()
        clock = SimpleNamespace(monotonic=lambda: 123.0)
        scope['time'] = clock
        fake_os = SimpleNamespace(killpg=Mock())
        scope['os'] = fake_os
        browser = Mock(pid=1234)
        browser.poll.return_value = None
        browser.wait.side_effect = [subprocess.TimeoutExpired('private browser', 10), 0]
        if 'wait_browser_group' in scope:
            scope['wait_browser_group'] = Mock()
        report = {}
        scope['cleanup'](browser, report)
        self.assertEqual(browser.wait.call_args_list, [call(timeout=10), call(timeout=10)])
        self.assertEqual(fake_os.killpg.call_args_list, [call(1234, scope['signal'].SIGTERM), call(1234, scope['signal'].SIGKILL)])
        if 'wait_browser_group' in scope:
            scope['wait_browser_group'].assert_called_once_with(1234, 133.0)

    def test_launcher_wait_and_descendants_share_the_final_deadline(self):
        scope = self.scope()
        if 'stop_browser' not in scope:
            self.skipTest('descendant deadline regression for the new group cleanup helper')
        clock = SimpleNamespace(now=100.0)
        scope['time'] = SimpleNamespace(monotonic=lambda: clock.now)
        scope['os'] = SimpleNamespace(killpg=Mock())

        def waited(timeout):
            clock.now += 7
        browser = Mock(pid=1234, wait=Mock(side_effect=waited))

        def group_wait(group, deadline):
            self.assertEqual(group, 1234)
            self.assertEqual(deadline, 117.0)
            self.assertEqual(deadline - clock.now, 3.0)
        scope['wait_browser_group'] = group_wait
        scope['cleanup'](browser, {})
        self.assertEqual(browser.wait.call_args_list, [call(timeout=10), call(timeout=10)])

    def test_live_group_past_deadline_fails_without_claiming_cleanup(self):
        scope = self.scope()
        if 'wait_browser_group' not in scope:
            self.skipTest('descendant deadline regression for the new group cleanup helper')
        entry = Mock(name='proc entry')
        entry.name = '55'
        stat = Mock()
        stat.read_text.return_value = '55 (owned browser) S 1 1234 1234 0'
        entry.__truediv__ = Mock(return_value=stat)
        scope['Path'] = Mock(return_value=SimpleNamespace(iterdir=lambda: [entry]))
        scope['time'] = SimpleNamespace(monotonic=lambda: 20.0, sleep=Mock(side_effect=AssertionError('must not wait past deadline')))
        with self.assertRaisesRegex(RuntimeError, 'Owned browser group did not stop: 55'):
            scope['wait_browser_group'](1234, 20.0)

    def test_dead_and_unrelated_group_members_do_not_prevent_cleanup(self):
        scope = self.scope()
        if 'wait_browser_group' not in scope:
            self.skipTest('descendant deadline regression for the new group cleanup helper')
        entries = []
        for pid, state, group, session in [(51, 'Z', 1234, 1234), (52, 'X', 1234, 1234), (53, 'S', 9999, 9999)]:
            entry = Mock()
            entry.name = str(pid)
            stat = Mock()
            stat.read_text.return_value = f'{pid} (private child) {state} 1 {group} {session} 0'
            entry.__truediv__ = Mock(return_value=stat)
            entries.append(entry)
        scope['Path'] = Mock(return_value=SimpleNamespace(iterdir=lambda: entries))
        scope['time'] = SimpleNamespace(monotonic=lambda: 20.0, sleep=Mock(side_effect=AssertionError('no live owned process')))
        scope['wait_browser_group'](1234, 20.0)

@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux procfs and owned process-group fixture')
class RealCleanup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Become a temporary subreaper so disposable orphan children can be reaped.
        # Linux prctl: PR_GET_CHILD_SUBREAPER=37, PR_SET_CHILD_SUBREAPER=36.
        cls.libc = ctypes.CDLL(None, use_errno=True)
        old = ctypes.c_int()
        assert cls.libc.prctl(37, ctypes.byref(old), 0, 0, 0) == 0
        cls.old_subreaper = old.value
        assert cls.libc.prctl(36, 1, 0, 0, 0) == 0

    @classmethod
    def tearDownClass(cls):
        assert cls.libc.prctl(36, cls.old_subreaper, 0, 0, 0) == 0

    def check_group(self, early=False, parent_ignores=False, child=True):
        scope = cleanup_scope()
        browser = sibling = None
        child_pid = None
        with tempfile.TemporaryDirectory(prefix='framey-owned-browser-cleanup-') as scratch:
            root = Path(scratch)
            ready = root / 'ready'
            pidfile = root / 'child.pid'
            heartbeat = root / 'profile-writes'
            code = 'import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(' + repr(str(pidfile)) + ').write_text(str(os.getpid()));\nwhile True:\n with Path(' + repr(str(heartbeat)) + ").open('a')as f:f.write('owned\\n')\n time.sleep(.01)\n"
            parent = 'import signal,subprocess,sys,time;from pathlib import Path;' + ('signal.signal(signal.SIGTERM,signal.SIG_IGN);' if parent_ignores else '') + ("subprocess.Popen([sys.executable,'-c'," + repr(code) + ']);' if child else '') + ('\nwhile not Path(' + repr(str(pidfile)) + ').exists():time.sleep(.005)\n' if child else '\n') + 'Path(' + repr(str(ready)) + ").write_text('ready');" + ('sys.exit(0)' if early else 'time.sleep(60)')
            try:
                sibling = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                browser = subprocess.Popen([sys.executable, '-c', parent], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.005)
                self.assertTrue(ready.exists(), 'owned test processes must start')
                if child:
                    child_pid = int(pidfile.read_text())
                if early:
                    self.assertEqual(browser.wait(timeout=5), 0)
                report = {}
                cleanup_started = time.monotonic()
                scope['cleanup'](browser, report)
                elapsed = time.monotonic() - cleanup_started
                self.assertTrue(report['ownedBrowserReaped'])
                self.assertIsNone(sibling.poll(), 'unrelated session was signalled')
                if child:
                    stat = Path('/proc') / str(child_pid) / 'stat'
                    state = stat.read_text().rsplit(')', 1)[1].split()[0] if stat.exists() else 'gone'
                    before = heartbeat.stat().st_size
                    time.sleep(0.03)
                    after = heartbeat.stat().st_size
                    self.assertIn(state, ('Z', 'X', 'gone'), 'launcher was reaped but its owned child is still live')
                    self.assertEqual(after, before, 'owned child continued writing after cleanup returned')
                print('OWNED_BROWSER_CLEANUP_OBSERVATION ' + json.dumps(dict(earlyLauncherExit=early, parentIgnoresTerm=parent_ignores, hasChild=child, cleanupSeconds=elapsed, launcherReturnCode=browser.returncode, childPid=child_pid, unrelatedSessionPreserved=True)))
            finally:
                if browser:
                    try:
                        os.killpg(browser.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    browser.wait(timeout=5)
                if child_pid:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            got, _ = os.waitpid(child_pid, os.WNOHANG)
                        except ChildProcessError:
                            break
                        if got == child_pid:
                            break
                        if time.monotonic() > deadline:
                            raise AssertionError('owned child was not reaped')
                        time.sleep(0.01)
                if sibling:
                    sibling.terminate()
                    sibling.wait(timeout=5)

    def test_exited_launcher_does_not_leave_its_profile_writer(self):
        self.check_group(early=True)

    def test_term_exited_launcher_does_not_leave_its_ignoring_child(self):
        self.check_group()

    def test_normal_browser_without_children_still_stops(self):
        self.check_group(child=False)

    def test_term_ignoring_browser_and_child_use_existing_kill_budget(self):
        self.check_group(parent_ignores=True)
if __name__ == '__main__':
    unittest.main(verbosity=2)
