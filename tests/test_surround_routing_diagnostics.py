"""Observe routing failures without changing command results or probe gates."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parent / 'decky-runtime/surround_route_diagnostic.py'
spec = importlib.util.spec_from_file_location('route_diagnostic', SOURCE)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)
posix_only = unittest.skipIf(os.name == 'nt', 'pactl wrapper uses Linux/POSIX process contracts')


class DiagnosticControls(unittest.TestCase):
    def run_wrapper(self, status, stdout, stderr, deny_log=False):
        with tempfile.TemporaryDirectory(prefix='framey-surround-diagnostic-control-') as temp:
            trace = Path(temp) / 'trace.jsonl'
            original_open = os.open

            def private_open(name, *args):
                self.assertEqual(name, str(diagnostic.TRACE))
                if deny_log:
                    raise PermissionError('controlled private log refusal')
                return original_open(trace, *args)

            out, err = io.BytesIO(), io.BytesIO()
            result = subprocess.CompletedProcess(['/usr/bin/pactl'], status, stdout, stderr)
            with (patch.object(sys, 'argv', ['pactl', 'move-sink-input', '88', '51']),
                  patch.object(sys, 'stdout', types.SimpleNamespace(buffer=out)),
                  patch.object(sys, 'stderr', types.SimpleNamespace(buffer=err)),
                  patch.object(subprocess, 'run', return_value=result) as run,
                  patch.object(os, 'open', side_effect=private_open)):
                with self.assertRaises(SystemExit) as stopped:
                    exec(compile(diagnostic.WRAPPER, 'exact-private-pactl-wrapper', 'exec'), {})
            self.assertEqual(stopped.exception.code, status)
            run.assert_called_once_with(['/usr/bin/pactl', 'move-sink-input', '88', '51'],
                                        capture_output=True)
            self.assertEqual(out.getvalue(), stdout)
            self.assertEqual(err.getvalue(), stderr)
            if deny_log:
                self.assertFalse(trace.exists())
                return None
            row = json.loads(trace.read_text())
            self.assertEqual(row['returncode'], status)
            self.assertEqual(row['args'], ['move-sink-input', '88', '51'])
            self.assertLessEqual(row['startedMonotonicNs'], row['finishedMonotonicNs'])
            self.assertEqual(trace.stat().st_mode & 0o777, 0o600)
            return row

    @posix_only
    def test_success_exit_and_actual_command_are_preserved(self):
        row = self.run_wrapper(0, b'', b'')
        self.assertEqual(row['stdout'], '')
        self.assertFalse(row['stderrTruncated'])

    @posix_only
    def test_failure_exit_and_stderr_are_preserved_without_retry(self):
        row = self.run_wrapper(1, b'', b'Failure: No such entity\n')
        self.assertEqual(row['stderr'], 'Failure: No such entity\n')

    @posix_only
    def test_diagnostic_caps_do_not_truncate_original_outputs(self):
        row = self.run_wrapper(1, b'x' * 8192, b'y' * 8192)
        self.assertEqual(len(row['stdout']), 4096)
        self.assertTrue(row['stdoutTruncated'])
        self.assertTrue(row['stderrTruncated'])

    @posix_only
    def test_non_move_commands_exec_original_without_capture(self):
        class Delegated(Exception):
            pass

        with (patch.object(sys, 'argv', ['pactl', 'list', 'sinks']),
              patch.object(os, 'execv', side_effect=Delegated) as delegate,
              patch.object(subprocess, 'run') as run):
            with self.assertRaises(Delegated):
                exec(compile(diagnostic.WRAPPER, 'exact-private-pactl-wrapper', 'exec'), {})
            delegate.assert_called_once_with('/usr/bin/pactl', ['pactl', 'list', 'sinks'])
            run.assert_not_called()

    @posix_only
    def test_log_write_failure_preserves_command_status_and_output(self):
        self.assertIsNone(self.run_wrapper(1, b'out', b'original error', deny_log=True))

    @posix_only
    def test_actual_child_signal_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix='framey-surround-signal-control-') as temp:
            root = Path(temp)
            child = root / 'pactl-fixture'
            child.write_text(f'#!{sys.executable}\nimport os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n')
            child.chmod(0o700)
            trace = root / 'trace.jsonl'
            source = diagnostic.WRAPPER.replace("'/usr/bin/pactl'", repr(str(child)))
            source = source.replace(str(diagnostic.TRACE), str(trace))
            wrapper = root / 'wrapper.py'
            wrapper.write_text(source)
            result = subprocess.run([sys.executable, str(wrapper), 'move-sink-input', '88', '51'],
                                    capture_output=True, timeout=3)
            self.assertEqual(result.returncode, -signal.SIGTERM)
            self.assertEqual(json.loads(trace.read_text())['returncode'], -signal.SIGTERM)

    def test_diagnostic_error_is_reported_without_masking_probe_result(self):
        output = io.StringIO()
        with (patch.object(diagnostic, 'TRACE', Path('/not-existing-private-trace')),
              patch.object(subprocess, 'run', side_effect=OSError('private fixture')),
              contextlib.redirect_stderr(output)):
            diagnostic.dump({})
        row = json.loads(output.getvalue().split('SURROUND_PRIVATE_COMMAND_DIAGNOSTIC ', 1)[1])
        self.assertEqual(row['diagnosticErrorType'], 'OSError')
        self.assertTrue(row['noRetry'])

    def test_closed_diagnostic_stream_does_not_replace_original_failure(self):
        with (patch.object(diagnostic, 'TRACE', Path('/not-existing-private-trace')),
              patch.object(subprocess, 'run', side_effect=OSError('private fixture')),
              patch('builtins.print', side_effect=BrokenPipeError('closed private evidence stream'))):
            diagnostic.dump({})


if __name__ == '__main__':
    unittest.main(verbosity=2)
