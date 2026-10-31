"""A real probe child's failure or timeout must retain its diagnostic output."""
import sandbox  # noqa: F401
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
