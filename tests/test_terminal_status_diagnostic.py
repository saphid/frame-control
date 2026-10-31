"""Failure diagnostics retain evidence without replacing a production gate."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('terminal_status_diagnostic',
    ROOT/'tests/decky-runtime/terminal_status_diagnostic.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class RequestDrain(unittest.TestCase):
    def test_late_failed_http_request_is_recorded_before_diagnostics(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import urllib.error
        import urllib.request

        activity = diagnostic.RequestActivity()
        started, release, draining = threading.Event(), threading.Event(), threading.Event()
        records, observed, drain_result = [], [], []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def handle(self):
                with activity.track():
                    super().handle()

            def do_GET(self):
                started.set()
                if not release.wait(5):
                    raise RuntimeError('Test did not release its owned request')
                records.append(dict(kind='panel-method', outcome='failure', errorCategory='ssh-timeout'))
                self.send_response(503)
                self.end_headers()

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        serving = threading.Thread(target=server.serve_forever, kwargs=dict(poll_interval=.01))
        serving.start()

        def fetch():
            try:
                urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port), timeout=5).close()
            except urllib.error.HTTPError as error:
                observed.append(error.code)
                error.close()

        def finish():
            draining.set()
            drain_result.append(activity.drain(5))
            observed.append(any(entry['outcome'] == 'failure' for entry in records))

        client = threading.Thread(target=fetch)
        finalizer = threading.Thread(target=finish)
        try:
            client.start()
            self.assertTrue(started.wait(5))
            # This is the old failure: reading the trace before the active
            # production request ends misses the method diagnostic trigger.
            self.assertFalse(records)
            server.shutdown(); server.server_close(); serving.join(5)
            self.assertFalse(serving.is_alive())
            finalizer.start()
            self.assertTrue(draining.wait(5))
            self.assertFalse(drain_result)
            release.set()
        finally:
            release.set()
            server.shutdown(); server.server_close()
            for thread in (client, finalizer, serving):
                if thread.ident is not None:
                    thread.join(6)
                    self.assertFalse(thread.is_alive())
        self.assertTrue(drain_result[0]['drained'])
        self.assertEqual(drain_result[0]['pendingHandlers'], 0)
        self.assertCountEqual(observed, [503, True])

    def test_drain_is_bounded_and_exception_releases_owned_handler(self):
        activity = diagnostic.RequestActivity()
        with self.assertRaisesRegex(RuntimeError, 'owned test failure'):
            with activity.track():
                report = activity.drain(0)
                self.assertFalse(report['drained'])
                self.assertEqual(report['pendingHandlers'], 1)
                self.assertFalse(report['productionDeadlineChanged'])
                raise RuntimeError('owned test failure')
        self.assertTrue(activity.drain(0)['drained'])


class StatusDiagnostic(unittest.TestCase):
    def method_source(self):
        tree = ast.parse((ROOT/'ui/framey_panel.py').read_text())
        template = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign) and any(
                            isinstance(target, ast.Name) and target.id == 'METHOD_SCRIPT'
                            for target in node.targets))
        return template, diagnostic.read_only_method_source(template, 'Decky Terminal')

    @unittest.skipUnless(os.name == 'posix', 'Owned Linux VM process-group lifecycle')
    def test_read_only_method_uses_shipped_template_and_omits_terminal_contents(self):
        template, source = self.method_source()
        self.assertIn('"get_terminals"', source)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'frame_steam.py').write_text(
                'class Page:\n'
                ' def __init__(self): self.sock=self\n'
                ' def close(self): pass\n'
                ' def eval(self, expression):\n'
                '  assert "get_terminals" in expression\n'
                '  assert "create_terminal" not in expression\n'
                '  return [{"private": "private-canary"}]\n')
            with patch.dict(os.environ, PYTHONPATH=directory):
                report = diagnostic.collect(source, directory, result_kind='method')
        self.assertEqual(report['exitStatus'], 0)
        self.assertEqual(report['sourceSha256'], hashlib.sha256(source.encode()).hexdigest())
        self.assertEqual(report['methodResultSummary'], dict(terminalCount=1))
        self.assertTrue(report['ownedProcessReaped'])
        self.assertFalse(report['productionReplayReplaced'])
        self.assertNotIn('private-canary', json.dumps(report))
        with self.assertRaises(AssertionError):
            diagnostic.read_only_method_source(template, 'Other plugin')

    @unittest.skipUnless(os.name == 'posix', 'Owned Linux VM process-group lifecycle')
    def test_method_timeout_identifies_page_stage_without_retaining_private_values(self):
        _, source = self.method_source()
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'frame_steam.py').write_text(
                'import time\nclass Page:\n'
                ' def __init__(self): time.sleep(60) # private-canary\n')
            with patch.dict(os.environ, PYTHONPATH=directory):
                report = diagnostic.collect(source, directory, result_kind='method',
                                            timeout=1, sample_seconds=.1)
        self.assertTrue(report['timedOut'])
        self.assertTrue(report['ownedProcessReaped'])
        self.assertNotEqual(report['exitStatus'], 0)
        self.assertLess(report['elapsedSeconds'], 5)
        self.assertIn(dict(file='frame_steam.py', line=3, function='__init__'), report['sampledFrames'])
        self.assertNotIn('methodResultSummary', report)
        self.assertNotIn('private-canary', json.dumps(report))

    @unittest.skipUnless(os.name == 'posix', 'Owned Linux VM process-group lifecycle')
    def test_imports_and_status_reply_are_summarized_without_private_values(self):
        source = 'import json, urllib.request\nprint(json.dumps(dict(managed=True, running=False, cef=True, plugins=[dict(password="private-canary")], secret="private-canary")))\n'
        with tempfile.TemporaryDirectory() as directory:
            report = diagnostic.collect(source, directory)
        self.assertEqual(report['sourceSha256'], hashlib.sha256(source.encode()).hexdigest())
        self.assertEqual(report['exitStatus'], 0)
        self.assertTrue(report['ownedProcessReaped'])
        self.assertFalse(report['timedOut'])
        self.assertFalse(report['productionReplayReplaced'])
        self.assertFalse(report['productionDeadlineChanged'])
        self.assertGreater(report['importRecordCount'], 0)
        self.assertEqual(report['statusSummary'], dict(managed=True, running=False, cef=True, pluginCount=1))
        self.assertNotIn('private-canary', json.dumps(report))

    @unittest.skipUnless(os.name == 'posix', 'Owned Linux VM process-group lifecycle')
    def test_timeout_retains_sampled_operation_and_reaps_owned_child(self):
        source = 'import time\ntime.sleep(60)\n'
        with tempfile.TemporaryDirectory() as directory:
            report = diagnostic.collect(source, directory, timeout=1, sample_seconds=.1)
        self.assertTrue(report['timedOut'])
        self.assertTrue(report['ownedProcessReaped'])
        self.assertNotEqual(report['exitStatus'], 0)
        self.assertLess(report['elapsedSeconds'], 5)
        self.assertIn(dict(file='<decky-read-only-status>', line=2, function='<module>'), report['sampledFrames'])
        self.assertNotIn('success', report)

    def test_source_lines_exception_text_and_full_paths_are_not_retained(self):
        report = diagnostic.summarize_stderr(b'import time: 10 | 20 | urllib.request\n  File "/private-canary/lib/request.py", line 7 in open\n    password="private-canary"\nRuntimeError: private-canary\n')
        self.assertEqual(report['sampledFrames'], [dict(file='request.py', line=7, function='open')])
        self.assertEqual(report['slowestImports'][0]['module'], 'urllib.request')
        self.assertNotIn('private-canary', json.dumps(report))

    @unittest.skipUnless(os.name == 'posix', 'Owned diagnostic child signal lifecycle')
    def test_fatal_signal_retains_sanitized_stack_and_reaps_owned_child(self):
        source = ('import os, resource, signal\n'
                  'resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n'
                  'private = "private-canary"\n'
                  'os.kill(os.getpid(), signal.SIGSEGV)\n')
        with tempfile.TemporaryDirectory() as directory:
            report = diagnostic.collect(source, directory, result_kind='method',
                                        timeout=5, sample_seconds=1)
        self.assertEqual(report['exitStatus'], -signal.SIGSEGV)
        self.assertEqual(report['fatalError'], 'Segmentation fault')
        self.assertIn(dict(file='<decky-read-only-method>', line=4, function='<module>'),
                      report['fatalFrames'])
        self.assertTrue(report['ownedProcessReaped'])
        self.assertFalse(report['timedOut'])
        self.assertFalse(report['productionReplayReplaced'])
        self.assertFalse(report['productionDeadlineChanged'])
        self.assertTrue(report['methodJsonUnavailable'])
        self.assertNotIn('private-canary', json.dumps(report))

    def test_fatal_summary_accepts_only_known_headers_and_omits_private_values(self):
        report = diagnostic.summarize_stderr(
            b'Fatal Python error: private-canary\n'
            b'Fatal Python error: Segmentation fault\n'
            b'Current thread 0x123456 (most recent call first):\n'
            b'  File "/private-canary/lib/crash.py", line 8 in fail\n'
            b'    password="private-canary"\n'
            b'Extension modules: private-canary\n')
        self.assertEqual(report['fatalError'], 'Segmentation fault')
        self.assertEqual(report['fatalFrames'], [dict(file='crash.py', line=8, function='fail')])
        self.assertNotIn('private-canary', json.dumps(report))
        self.assertNotIn('0x123456', json.dumps(report))
        self.assertIsNone(diagnostic.summarize_stderr(
            b'Fatal Python error: Segmentation fault private-canary\n')['fatalError'])
