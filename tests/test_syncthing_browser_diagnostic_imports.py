"""Failure-only child import evidence; no readiness, plugin or device runs."""
import ast
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(os.environ.get('FRAMEY_DIAGNOSTIC_SOURCE',
    Path(__file__).parent/'decky-runtime/syncthing_browser.py'))


class DiagnosticImports(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root/'syncthing_browser.py'
        self.source.write_bytes(SOURCE.read_bytes())
        self.backend = self.root/'frame_steam.py'
        tree = ast.parse(self.source.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'final_browser_state')
        self.scope = dict(sys=sys, Path=Path, subprocess=subprocess, json=json,
            __file__=str(self.source), time=time,
            frame_steam=SimpleNamespace(__file__=str(self.backend), CDP=''))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(self.source), 'exec'),
             self.scope)
        self.read = self.scope['final_browser_state']

    def test_stalled_owned_transport_import_is_retained_before_child_timeout(self):
        self.backend.write_text('import time\ntime.sleep(30)\n')
        report = self.read(timeout=1)
        self.assertTrue(report['timedOut'])
        self.assertEqual(report['snapshots'], [])
        self.assertEqual(report['phases'], ['interpreter-started'])
        self.assertIn('frame_steam', report.get('importModulesStarted', []),
                      'timed-out reader must retain the last owned import reached')

    def test_completed_actual_reader_keeps_target_phases_and_bounded_import_names(self):
        self.backend.write_text('import http.client\nfrom urllib.parse import urlsplit\n'
                                'CDP=""\nclass Fail(Exception): pass\n')
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'[]')
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            self.scope['frame_steam'].CDP = f'http://127.0.0.1:{server.server_port}/json'
            report = self.read()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(report['timedOut'])
        self.assertEqual(report['returnCode'], 0)
        self.assertEqual(report['phases'],
                         ['interpreter-started', 'module-imported', 'targets-read'])
        self.assertEqual(report['snapshots'], [dict(target='parent', unavailable=True),
                                               dict(target='iframe', unavailable=True)])
        imports = report.get('importModulesStarted', [])
        self.assertNotIn('syncthing_browser', imports)
        self.assertIn('frame_steam', imports)
        self.assertLessEqual(len(imports), 8)
        self.assertEqual(len(imports), len(set(imports)))

    def test_import_records_reject_unknown_names_and_keep_existing_phase_capacity(self):
        rows = [dict(importModule='private.secret'), dict(importModule='frame_steam'),
                dict(importModule='frame_steam'), dict(phase='interpreter-started'),
                dict(phase='module-imported'), dict(phase='targets-read'),
                dict(phase='parent-connected'), dict(phase='iframe-connected')]
        output = b'\n'.join(json.dumps(r).encode() for r in rows)
        result = SimpleNamespace(returncode=0, stdout=output)
        with patch.object(subprocess, 'run', return_value=result) as run:
            report = self.read()
        self.assertGreater(run.call_args.kwargs['timeout'], 0)
        self.assertLessEqual(run.call_args.kwargs['timeout'], 8)
        self.assertEqual(report.get('importModulesStarted'), ['frame_steam'])
        self.assertEqual(report['phases'], [r['phase'] for r in rows if 'phase' in r])
        self.assertNotIn('secret', json.dumps(report))
        self.assertNotIn('readinessPassed', report)

    def test_failure_reader_does_not_execute_browser_module_initialization(self):
        # The helper must read the query, rather than import unrelated setup.
        self.source.write_text('import time as fixture_boot\nfixture_boot.sleep(30)\n'+
                               self.source.read_text())
        self.backend.write_text('import http.client\nfrom urllib.parse import urlsplit\n'
                                'CDP=""\nclass Fail(Exception): pass\n')
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'[]')
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            self.scope['frame_steam'].CDP = f'http://127.0.0.1:{server.server_port}/json'
            report = self.read(timeout=1)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(report['timedOut'],
                         'unrelated browser module initialization blocked the failure query')
        self.assertEqual(report['returnCode'], 0)
        self.assertEqual(report['snapshots'], [dict(target='parent', unavailable=True),
                                               dict(target='iframe', unavailable=True)])
        self.assertNotIn('syncthing_browser', report.get('importModulesStarted', []))
        self.assertNotIn('readinessPassed', report)

    def test_missing_or_oversized_query_returns_diagnostic_unavailability(self):
        original = self.source.read_text()
        cases = [original.replace('def print_final_browser_state():',
                                  'def other_fixture_query():'),
                 original.replace('def print_final_browser_state():',
                                  'def print_final_browser_state():\n    '+repr('x'*8193)),
                 ' '*65537]
        for source in cases:
            with self.subTest(size=len(source)), patch.object(subprocess, 'run') as run:
                self.source.write_text(source)
                report = self.read()
                run.assert_not_called()
                self.assertEqual(report['snapshots'], [])
                self.assertIn(report['errorType'], ['StopIteration', 'AssertionError'])
                self.assertNotIn('readinessPassed', report)

    def test_unavailable_source_does_not_replace_failure_with_private_error_text(self):
        self.source.unlink()
        with patch.object(subprocess, 'run') as run:
            report = self.read()
        run.assert_not_called()
        self.assertEqual(report['errorType'], 'FileNotFoundError')
        self.assertEqual(report['snapshots'], [])
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_query_preparation_consumes_the_existing_timeout(self):
        with patch.object(time, 'monotonic', side_effect=[100,108.01]), \
                patch.object(subprocess, 'run') as run:
            report = self.read()
        run.assert_not_called()
        self.assertTrue(report['timedOut'])
        self.assertTrue(report['preparationDeadlineExceeded'])
        self.assertEqual(report['timeoutSeconds'], 8)
        self.assertEqual(report['snapshots'], [])
        self.assertNotIn('readinessPassed', report)


if __name__ == '__main__':
    unittest.main()
