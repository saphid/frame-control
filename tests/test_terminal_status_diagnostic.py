"""Failure diagnostics retain evidence without replacing a production gate."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('terminal_status_diagnostic',
    ROOT/'tests/decky-runtime/terminal_status_diagnostic.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class StatusDiagnostic(unittest.TestCase):
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
