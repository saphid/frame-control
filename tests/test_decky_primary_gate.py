"""The real CLI must reject a hidden forced kill despite Docker/loader exit zero."""
import sandbox  # noqa: F401
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('primary_gate', ROOT/'scripts/framey-test-decky-runtime.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
RECORDED = json.loads((ROOT/'tests/fixtures/decky-primary-forced-kill-arm64.json').read_text())


def observation(text):
    return dict(id=104, result='fixture RPCs completed', runtimeConsole=dict(
        text=text, sha256=hashlib.sha256(text.encode()).hexdigest(),
        probeCompleted=True, cleanupCompleted=True, cleanShutdownVerified=False,
        processStops=[dict(loader=True, returncode=0, forcedKill=False)]))


class PrimaryShutdownGate(unittest.TestCase):
    def invoke(self, output, primary, *, negative=None):
        ident = 104 if negative is None else 111

        def docker(command, **kwargs):
            if command[:2] == ['docker', 'run']:
                control = any(arg.startswith('--reproduce-') for arg in command)
                value = copy.deepcopy(negative if control else primary)
                value['id'] = ident
                return subprocess.CompletedProcess(command, 0, json.dumps(value), '')
            return subprocess.CompletedProcess(command, 0, '', '')

        with patch.object(gate, 'check_coverage', return_value=[dict(id=ident)]), \
             patch.object(gate, 'loader_bytes', return_value=(b'fixture', 'fixture digest')), \
             patch.object(gate.shutil, 'which', return_value='/fixture/docker'), \
             patch.object(gate.subprocess, 'run', side_effect=docker), \
             patch.object(gate.sys, 'platform', 'linux'), \
             patch.object(gate.sys, 'argv', ['runtime', '--case', str(ident), '--output', str(output)]), \
             redirect_stdout(io.StringIO()):
            gate.main()

    def test_real_arm64_forced_kill_fails_with_zero_exit_and_retains_report(self):
        failed = RECORDED['observation']
        self.assertTrue(RECORDED['source']['observedParentZeroExit'])
        self.assertTrue(any(p['loader'] and p['returncode'] == 0
                            for p in failed['runtimeConsole']['processStops']))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result.json'
            with self.assertRaisesRegex(RuntimeError, 'primary case 104.*Sending SIGKILL'):
                self.invoke(output, failed)
            self.assertEqual(json.loads(output.read_text())['cases'], [failed])

    def test_shutdown_error_fails_even_with_zero_exit(self):
        failed = observation('[main][ERROR]: Error during shutdown: fixture failure\n')
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, 'primary case 104.*Error during shutdown'):
                self.invoke(Path(temp)/'result.json', failed)

    def test_expected_rpc_failure_does_not_fail_clean_shutdown(self):
        clean = observation('[loader][ERROR]: Method test_syncpath failed: outside sync root\n'
                            '[main][INFO]: Shutdown finished.\n')
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result.json'
            self.invoke(output, clean)
            self.assertEqual(json.loads(output.read_text())['cases'], [clean])

    def test_incomplete_or_modified_console_cannot_pass(self):
        for field, value, reason in [('probeCompleted', False, 'incomplete'),
                                     ('cleanupCompleted', False, 'incomplete'),
                                     ('sha256', 'modified', 'digest mismatch')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                failed = observation('[main][INFO]: Shutdown finished.\n')
                failed['runtimeConsole'][field] = value
                output = Path(temp)/'result.json'
                with self.assertRaisesRegex(RuntimeError, reason):
                    self.invoke(output, failed)
                self.assertEqual(json.loads(output.read_text())['cases'], [failed])

    def test_explicit_original_source_control_is_kept_separate(self):
        clean = observation('[main][INFO]: Shutdown finished.\n')
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result.json'
            self.invoke(output, clean, negative=RECORDED['observation'])
            cases = json.loads(output.read_text())['cases']
            self.assertEqual(len(cases), 2)
            self.assertNotIn('Sending SIGKILL!', cases[0]['runtimeConsole']['text'])
            self.assertIn('Sending SIGKILL!', cases[1]['runtimeConsole']['text'])
