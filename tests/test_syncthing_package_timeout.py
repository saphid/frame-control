"""Captured package probes retain real child output when their deadline expires."""

import ast
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch


class CapturedGuestProbe(unittest.TestCase):
    def setUp(self):
        # Compile the real functions without importing the guest-only GI runtime.
        path = Path(__file__).parent / 'decky-runtime/syncthing_flatpak_package.py'
        tree = ast.parse(path.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('run_captured', 'command')]
        self.scope = dict(subprocess=subprocess, time=time, PROGRESS={})
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'),
             self.scope)

    def test_timeout_retains_bounded_output_and_reaps_the_child(self):
        argv = [sys.executable, '-c',
                "import sys,time; "
                "sys.stdout.buffer.write(b'o'*12000+b'owned stdout sentinel'); "
                "sys.stdout.flush(); "
                "sys.stderr.buffer.write(b'e'*12000+b'\\xef\\xbf\\xbdowned stderr sentinel'); "
                "sys.stderr.flush(); time.sleep(30)"]
        children = []
        popen = subprocess.Popen

        def launch(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            return child

        with patch.object(subprocess, 'Popen', side_effect=launch):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.scope['run_captured'](argv, timeout=2)
        evidence = self.scope['PROGRESS']['timedOutCommand']
        self.assertEqual(evidence['argv'], argv)
        self.assertEqual(evidence['timeoutSeconds'], 2)
        self.assertGreaterEqual(evidence['elapsedSeconds'], 2)
        self.assertEqual(len(evidence['stdout']), 10000)
        self.assertEqual(len(evidence['stderr']), 10000)
        self.assertTrue(evidence['stdout'].endswith('owned stdout sentinel'))
        self.assertTrue(evidence['stderr'].endswith('\ufffdowned stderr sentinel'))
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_success_preserves_both_streams_and_command_return_value(self):
        argv = [sys.executable, '-c',
                "import sys; print('owned result'); print('owned warning', file=sys.stderr)"]
        result = self.scope['run_captured'](argv, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'owned result')
        self.assertEqual(result.stderr.strip(), 'owned warning')
        self.assertEqual(self.scope['command'](argv, timeout=10), 'owned result')
        self.assertEqual(self.scope['PROGRESS'], {})

    def test_nonzero_probe_is_not_converted_to_a_success(self):
        argv = [sys.executable, '-c',
                "import sys; print('owned failure', file=sys.stderr); sys.exit(23)"]
        result = self.scope['run_captured'](argv, timeout=10)
        self.assertEqual(result.returncode, 23)
        self.assertEqual(result.stderr.strip(), 'owned failure')
        with self.assertRaisesRegex(RuntimeError, 'exit=23: .*owned failure'):
            self.scope['command'](argv, timeout=10)
        self.assertEqual(self.scope['PROGRESS'], {})
