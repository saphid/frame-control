"""Real child output must survive probe failure and final cleanup."""
import sandbox  # noqa: F401
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('native_console',
    Path(__file__).parent/'decky-runtime/runtime_console.py')
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


@unittest.skipUnless(sys.platform == 'linux', 'native Linux fixture process groups')
class NativeConsoleEvidence(unittest.TestCase):
    def child(self, log, ignore_term=False):
        source = '''import signal,sys,time
def stop(*_):
    print('FINAL SHUTDOWN OUTPUT', flush=True)
    sys.exit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN if sys.argv[1]=='ignore' else stop)
print('BEGIN FULL CONSOLE', flush=True)
print('x'*40000, flush=True)
print('READY', flush=True)
while True: time.sleep(.02)
'''
        process = subprocess.Popen([sys.executable, '-u', '-c', source,
            'ignore' if ignore_term else 'normal'], stdout=log, stderr=log,
            start_new_session=True)
        def reap():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        self.addCleanup(reap)
        deadline = time.monotonic()+5
        while time.monotonic()<deadline:
            if 'READY' in Path(log.name).read_text():
                return process
            time.sleep(.01)
        self.fail('private child did not become ready')

    def test_success_is_printed_after_shutdown_with_complete_hashed_output(self):
        with tempfile.NamedTemporaryFile(mode='w+') as log:
            child = self.child(log)
            out, err, report = io.StringIO(), io.StringIO(), {'result':'private probe'}
            with console.capture_runtime(log, report, [child], stdout=out, stderr=err):
                self.assertIsNone(child.poll())
                self.assertEqual(out.getvalue(), '')
            emitted = json.loads(out.getvalue())['runtimeConsole']
        self.assertEqual(child.returncode, 0)
        self.assertIn('BEGIN FULL CONSOLE\n'+'x'*40000+'\nREADY\n', emitted['text'])
        self.assertTrue(emitted['text'].endswith('FINAL SHUTDOWN OUTPUT\n'))
        self.assertEqual(emitted['sha256'], hashlib.sha256(emitted['text'].encode()).hexdigest())
        self.assertTrue(emitted['probeCompleted'] and emitted['cleanupCompleted'])
        self.assertFalse(emitted['cleanShutdownVerified'])
        self.assertEqual(err.getvalue(), '')

    def test_failed_probe_keeps_full_output_and_cleanup_tail_without_success_json(self):
        with tempfile.NamedTemporaryFile(mode='w+') as log:
            child = self.child(log)
            out, err, report = io.StringIO(), io.StringIO(), {}
            with self.assertRaisesRegex(RuntimeError, 'private failure'):
                with console.capture_runtime(log, report, [child], stdout=out, stderr=err):
                    raise RuntimeError('private failure')
        self.assertEqual(child.returncode, 0)
        self.assertEqual(out.getvalue(), '')
        self.assertIn('BEGIN FULL CONSOLE\n'+'x'*40000, err.getvalue())
        self.assertIn('FINAL SHUTDOWN OUTPUT', err.getvalue())
        self.assertFalse(report['runtimeConsole']['probeCompleted'])
        self.assertTrue(report['runtimeConsole']['cleanupCompleted'])

    def test_forced_cleanup_is_recorded_without_claiming_clean_shutdown(self):
        with tempfile.NamedTemporaryFile(mode='w+') as log:
            child = self.child(log, ignore_term=True)
            out = io.StringIO()
            with console.capture_runtime(log, {}, [child], stop_timeout=.1, stdout=out):
                pass
            evidence = json.loads(out.getvalue())['runtimeConsole']
        self.assertEqual(child.returncode, -signal.SIGKILL)
        self.assertEqual(evidence['processStops'], [dict(pid=child.pid,
            signaledProcessGroup=True, forcedKill=True, returncode=-signal.SIGKILL)])
        self.assertFalse(evidence['cleanShutdownVerified'])
        self.assertTrue(evidence['cleanupCompleted'])

    def test_cleanup_exception_keeps_console_and_cannot_emit_success(self):
        class BrokenProcess:
            pid = 123
            returncode = None
            def poll(self):
                raise OSError('private cleanup failure')
        with tempfile.NamedTemporaryFile(mode='w+') as log:
            log.write('PRIVATE COMPLETE CONSOLE\n')
            out, err, report = io.StringIO(), io.StringIO(), {}
            with self.assertRaisesRegex(OSError, 'private cleanup failure'):
                with console.capture_runtime(log, report, [BrokenProcess()], stdout=out, stderr=err):
                    pass
        self.assertEqual(out.getvalue(), '')
        self.assertIn('PRIVATE COMPLETE CONSOLE', err.getvalue())
        self.assertFalse(report['runtimeConsole']['cleanupCompleted'])
