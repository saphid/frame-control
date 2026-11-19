"""Bounded post-failure counters from the owned disposable browser session."""
import ast
import io
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch


def stat_line(pid, group=42, session=42, start=1234, name='private (fixture)'):
    values = ['S', '1', str(group), str(session)] + ['0'] * 25
    values[11], values[12], values[17] = '17', '3', '2'
    values[19], values[21] = str(start), '9'
    return (str(pid)+' ('+name+') '+' '.join(values)+'\n').encode()


class BrowserProcessDiagnostics(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).parent/'decky-runtime/syncthing_browser.py'
        self.tree = ast.parse(source.read_text())
        methods = {n.name: n for n in self.tree.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('owned_browser_process_diagnostics', methods,
                      'post-failure owned browser process counters are missing')
        self.scope = dict(Path=Path, os=SimpleNamespace(sysconf=lambda key: 100))
        exec(compile(ast.Module(body=[methods['owned_browser_process_diagnostics']],
                               type_ignores=[]), str(source), 'exec'), self.scope)
        self.observe = self.scope['owned_browser_process_diagnostics']
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def process(self, pid, raw=None, **kwargs):
        path = self.root/str(pid)
        path.mkdir()
        (path/'stat').write_bytes(raw if raw is not None else stat_line(pid, **kwargs))
        (path/'wchan').write_bytes(b'do_poll\n')
        return path

    def test_records_only_owned_session_with_exact_process_counters(self):
        self.process(101)
        self.process(102, group=91, session=91)
        (self.root/'not-a-process').mkdir()
        result = self.observe(42, self.root)
        self.assertEqual(result['clockTicksPerSecond'], 100)
        self.assertEqual(result['entriesScanned'], 2)
        self.assertFalse(result['scanTruncated'])
        self.assertEqual(result['processes'], [dict(pid=101, parentPid=1, state='S',
            userTicks=17, systemTicks=3, threadCount=2, startTicks=1234, residentPages=9,
            wchan='do_poll\n', wchanTruncated=False)])
        self.assertNotIn('private', str(result))

    def test_matching_process_group_with_other_session_is_excluded(self):
        self.process(101, session=99)
        self.assertEqual(self.observe(42, self.root)['processes'], [])

    def test_oversized_and_malformed_records_are_bounded_and_retained_as_counts(self):
        self.process(101, raw=b'x'*4097)
        self.process(102, raw=b'malformed')
        self.process(103)
        result = self.observe(42, self.root)
        self.assertEqual(result['unreadableEntries'], 2)
        self.assertEqual([r['pid'] for r in result['processes']], [103])

    def test_invalid_group_cannot_scan_proc(self):
        root = Mock()
        for group in [0, -1, True, '42', None]:
            with self.subTest(group=group):
                self.assertEqual(self.observe(group, root)['error'], 'InvalidProcessGroup')
        root.iterdir.assert_not_called()

    def test_owned_process_and_wait_channel_output_caps_are_explicit(self):
        for pid in range(100, 165):
            self.process(pid)
        for path in self.root.iterdir():
            (path/'wchan').write_bytes(b'a'*129)
        result = self.observe(42, self.root)
        self.assertEqual(len(result['processes']), 64)
        self.assertTrue(result['processesTruncated'])
        self.assertTrue(all(len(row['wchan']) == 128 and row['wchanTruncated']
                            for row in result['processes']))

    def test_unrelated_entry_scan_has_its_own_explicit_cap(self):
        path = self.process(100, group=91, session=91)
        root = SimpleNamespace(iterdir=lambda: iter([path]*4097))
        result = self.observe(42, root)
        self.assertEqual(result['entriesScanned'], 4096)
        self.assertTrue(result['scanTruncated'])
        self.assertEqual(result['processes'], [])

    def test_identity_or_ownership_change_during_read_is_excluded(self):
        self.process(101)
        for changed in [stat_line(101, start=999), stat_line(101, group=99),
                        stat_line(101, session=99)]:
            with self.subTest(changed=changed), patch.object(Path, 'open',
                    side_effect=[io.BytesIO(stat_line(101)), io.BytesIO(changed)]):
                self.assertEqual(self.observe(42, self.root)['processes'], [])

    def test_actual_failure_diagnostics_include_snapshot_without_changing_gate(self):
        fn = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'startup_diagnostics')
        observer = Mock(return_value={'processes': []})
        scope = dict(owned_browser_process_diagnostics=observer)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<exact failure diagnostic>', 'exec'), scope)
        log = self.root/'browser.log'
        log.write_text('')
        browser = SimpleNamespace(pid=42, poll=lambda: None, returncode=None)
        result = scope['startup_diagnostics'](browser, self.root, log)
        observer.assert_called_once_with(42)
        self.assertEqual(result['ownedProcessSnapshot'], {'processes': []})
        self.assertNotIn('readinessPassed', result)
        exercise = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'exercise')
        handlers = [n for n in ast.walk(exercise) if isinstance(n, ast.ExceptHandler)]
        calls = lambda node: [n for n in ast.walk(node) if isinstance(n, ast.Call)
                             and isinstance(n.func, ast.Name) and n.func.id == 'startup_diagnostics']
        self.assertEqual(len(calls(exercise)), 1)
        self.assertEqual(sum(len(calls(n)) for n in handlers), 1)

    @unittest.skipUnless(os.name == 'posix' and Path('/proc/self/stat').exists(),
                         'actual process counters require Linux procfs')
    def test_disposable_live_child_is_observed_without_foreign_processes(self):
        import select
        import subprocess
        import sys
        child = subprocess.Popen([sys.executable, '-u', '-c',
            'import os,time; print(os.getpid(),flush=True); time.sleep(60)'],
            start_new_session=True, stdout=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 5)[0])
            self.assertEqual(int(child.stdout.readline()), child.pid)
            self.scope['os'] = os
            result = self.observe(child.pid)
            self.assertEqual([p['pid'] for p in result['processes']], [child.pid])
            row = result['processes'][0]
            self.assertGreater(row['startTicks'], 0)
            self.assertGreaterEqual(row['userTicks'], 0)
            self.assertGreaterEqual(row['systemTicks'], 0)
            self.assertGreaterEqual(row['threadCount'], 1)
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()
        self.assertIsNotNone(child.returncode)


if __name__ == '__main__':
    unittest.main()
