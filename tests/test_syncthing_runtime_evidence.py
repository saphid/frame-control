"""A real probe child's failure or timeout must retain its diagnostic output."""
import sandbox  # noqa: F401
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('syncthing_runtime_runner',
    Path(__file__).resolve().parents[1]/'scripts/framey-test-syncthing-runtime.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
ROOT = Path(__file__).resolve().parents[1]
fixture = ROOT/'tests/decky-runtime/syncthing_runtime.py'
function = next(node for node in ast.parse(fixture.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == 'verify_loader_shutdown')
scope = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(fixture), 'exec'), scope)
verify_shutdown = scope['verify_loader_shutdown']


class RuntimeEvidence(unittest.TestCase):
    def test_long_failed_output_is_retained_without_changing_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            console = Path(temp)/'nested/runtime.console.log'
            result = runner.run_probe([sys.executable, '-c',
                'import sys; print("start-marker"+"x"*12000); '
                'print("failure-marker", file=sys.stderr); sys.exit(23)'], console, 10)
            self.assertEqual(result.returncode, 23)
            self.assertIn('start-marker'+'x'*12000, console.read_text())
            self.assertIn('failure-marker', console.read_text())

    def test_timeout_retains_partial_output_and_remains_a_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            console = Path(temp)/'runtime.console.log'
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run_probe([sys.executable, '-u', '-c',
                    'import sys,time; print("before-timeout"); '
                    'print("stderr-before-timeout",file=sys.stderr); time.sleep(30)'], console, 5)
            self.assertIn('before-timeout', console.read_text())
            self.assertIn('stderr-before-timeout', console.read_text())

    def test_success_replaces_stale_console_output(self):
        with tempfile.TemporaryDirectory() as temp:
            console = Path(temp)/'runtime.console.log'
            console.write_text('stale-failure')
            result = runner.run_probe([sys.executable, '-c', 'print("passed")'], console, 10)
            self.assertEqual(result.returncode, 0)
            self.assertIn('passed', console.read_text())
            self.assertNotIn('stale-failure', console.read_text())


class LoaderShutdownGate(unittest.TestCase):
    clean = ('[plugin][INFO]: Plugin Syncthing (v0.2.7) has been stopped in 0.1s\n'
             '[main][INFO]: Cancelling tasks...\n[main][INFO]: Shutdown finished.\n')

    def test_actual_green_job_cancellation_is_rejected_and_retained(self):
        # Exact PR513 AMD64 artifact 13030957526; no synthetic error text.
        log = ROOT/'tests/fixtures/syncthing-runtime-shutdown-error.log'
        with tempfile.TemporaryDirectory() as temp:
            console = Path(temp)/'rejected.console.log'
            command = (ast.unparse(function)+'\nfrom pathlib import Path\n'
                       'text=Path('+repr(str(log))+').read_text()\n'
                       'print(text, flush=True)\nverify_loader_shutdown(text, 0)\n')
            result = runner.run_probe([sys.executable, '-c', command], console, 10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(log.read_text(), console.read_text())
            self.assertIn('Decky shutdown errors', console.read_text())

    def test_clean_shutdown_allows_normal_task_cancellation_banner(self):
        verify_shutdown(self.clean, 0)

    def test_nonzero_exit_or_incomplete_unload_is_rejected(self):
        for text, code in [(self.clean, 1), ('', 0),
                           ('[main][INFO]: Shutdown finished.\n', 0),
                           (self.clean+self.clean, 0)]:
            with self.subTest(text=text, returncode=code):
                with self.assertRaises(AssertionError):
                    verify_shutdown(text, code)

    def test_forced_kill_and_other_loader_errors_are_rejected(self):
        for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
                       'Task was destroyed but it is pending', 'Sending SIGKILL!', 'Bad file descriptor'):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(AssertionError, 'Decky shutdown errors'):
                    verify_shutdown(marker+'\n'+self.clean, 0)
