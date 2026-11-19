"""Real Cargo controls use only a tiny pinned local Git dependency, never a service."""
import sandbox  # noqa: F401
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux' and shutil.which('cargo') and shutil.which('git'),
                     'Fetch process-group controls need Linux, Cargo and Git')
class LockedCargoFetch(unittest.TestCase):
    def setUp(self):
        # sandbox owns HOME; rustup still needs the already installed toolchain.
        toolchain = patch.dict(os.environ, {'RUSTUP_HOME':sandbox.ORIGINAL_ENV.get(
            'RUSTUP_HOME', str(Path(sandbox.ORIGINAL_ENV['HOME'])/'.rustup'))})
        toolchain.start()
        self.addCleanup(toolchain.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='framey-local-cargo-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        spec = importlib.util.spec_from_file_location('framey_builder',
            ROOT/'scripts/build-framey-syncthing.py')
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        dependency = self.folder/'dependency'
        (dependency/'src').mkdir(parents=True)
        (dependency/'Cargo.toml').write_text(
            '[package]\nname="framey_local_dependency"\nversion="0.1.0"\nedition="2021"\n')
        (dependency/'src/lib.rs').write_text('pub fn value() -> u8 { 1 }\n')
        self.command(['git', 'init', '-q', str(dependency)])
        self.command(['git', '-C', str(dependency), 'add', '.'])
        self.command(['git', '-C', str(dependency), '-c', 'user.name=Fixture',
                      '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'])
        revision = self.command(['git', '-C', str(dependency), 'rev-parse', 'HEAD']).stdout.strip()
        app = self.folder/'app'
        (app/'src').mkdir(parents=True)
        (app/'src/lib.rs').write_text('pub fn value() -> u8 { framey_local_dependency::value() }\n')
        self.manifest = app/'Cargo.toml'
        self.manifest.write_text(
            '[package]\nname="framey_fetch_control"\nversion="0.1.0"\nedition="2021"\n'
            '[dependencies]\nframey_local_dependency={git='+json.dumps(dependency.as_uri())+
            ', rev='+json.dumps(revision)+'}\n')
        self.command(['cargo', 'generate-lockfile', '--manifest-path', str(self.manifest)],
            env={**os.environ, 'CARGO_HOME':str(self.folder/'seed'),
                 'CARGO_NET_GIT_FETCH_WITH_CLI':'true'})
        self.lock = self.manifest.with_name('Cargo.lock').read_bytes()
        self.cache = self.folder/'cache'
        self.marker = self.folder/'owned-child.json'
        self.bin = self.folder/'bin'
        self.bin.mkdir()

    def command(self, args, **kwargs):
        result = subprocess.run(args, capture_output=True, text=True, timeout=15, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def exercise(self, mode):
        # Subreaping belongs to this test harness, not the builder. It lets us
        # inspect the signal that killed an orphaned Git child, then reap it.
        libc = ctypes.CDLL(None, use_errno=True)
        original = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(original), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        real_git = shutil.which('git')
        wrapper = self.bin/'git'
        wrapper.write_text('#!'+sys.executable+'\n'+
            'import json, os, signal, sys, time\nfrom pathlib import Path\n'+
            'if "fetch" in sys.argv[1:]:\n'+
            ' child = os.fork()\n'+
            ' if child == 0:\n'+
            '  signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'+
            # Publish the marker atomically: readers treat existence as complete JSON.
            '  Path('+repr(str(self.marker)+'.tmp')+').write_text(json.dumps(dict(pid=os.getpid(), pgid=os.getpgrp())))\n'+
            '  os.replace('+repr(str(self.marker)+'.tmp')+', '+repr(str(self.marker))+')\n'+
            '  time.sleep(60)\n  os._exit(0)\n'+
            ' while not Path('+repr(str(self.marker))+').exists(): time.sleep(.005)\n'+
            (' time.sleep(60)\n' if mode in ('timeout', 'interrupt') else '')+
            (' sys.exit(42)\n' if mode == 'failure' else '')+
            'os.execv('+repr(real_git)+', ['+repr(real_git)+', *sys.argv[1:]])\n')
        wrapper.chmod(0o700)
        real_popen = subprocess.Popen
        sentinel = real_popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                              start_new_session=True)
        processes, waits = [], []

        def spawn(*args, **kwargs):
            self.assertEqual(args[0], ['cargo', 'fetch', '--locked', '--manifest-path', str(self.manifest)])
            self.assertTrue(kwargs['start_new_session'])
            self.assertEqual(kwargs['env']['CARGO_NET_GIT_FETCH_WITH_CLI'], 'true')
            self.assertEqual(kwargs['env']['CARGO_HOME'], str(self.cache))
            process = real_popen(*args, **kwargs)
            processes.append(process)
            real_wait = process.wait

            def wait(timeout=None):
                waits.append(timeout)
                if timeout == 180:
                    if mode == 'interrupt':
                        deadline = time.monotonic()+8
                        while not self.marker.exists() and time.monotonic() < deadline:
                            time.sleep(.01)
                        self.assertTrue(self.marker.exists())
                        raise KeyboardInterrupt
                    return real_wait(timeout=1.5 if mode == 'timeout' else 8)
                return real_wait(timeout=timeout)

            process.wait = wait
            return process

        def reap_owned(timeout):
            deadline = time.monotonic()+timeout
            while time.monotonic() < deadline:
                pid, status = os.waitpid(json.loads(self.marker.read_text())['pid'], os.WNOHANG)
                if pid:
                    return status
                time.sleep(.01)
            self.fail('Owned Git descendant survived source cleanup')

        try:
            with patch.dict(os.environ, {'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],
                    'CARGO_NET_GIT_FETCH_WITH_CLI':'false', 'CARGO_NET_RETRY':'0'}), \
                    patch.object(self.builder.subprocess, 'Popen', side_effect=spawn):
                if mode == 'success':
                    self.builder.fetch_locked_dependencies(self.manifest, self.cache)
                else:
                    error = {'timeout':subprocess.TimeoutExpired,
                             'failure':subprocess.CalledProcessError, 'interrupt':KeyboardInterrupt}[mode]
                    with self.assertRaises(error) as raised:
                        self.builder.fetch_locked_dependencies(self.manifest, self.cache)
                    if mode == 'failure':
                        self.assertEqual(raised.exception.returncode, 101)
            self.assertEqual(waits, [180, 5])
            process, = processes
            self.assertIsNotNone(process.returncode)
            with self.assertRaises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)
            child = json.loads(self.marker.read_text())
            self.assertEqual(child['pgid'], process.pid)
            status = reap_owned(2)
            self.assertTrue(os.WIFSIGNALED(status))
            self.assertEqual(os.WTERMSIG(status), signal.SIGKILL)
            self.assertIsNone(sentinel.poll(), 'Cleanup touched an unrelated process group')
            self.assertEqual(self.manifest.with_name('Cargo.lock').read_bytes(), self.lock)
            if mode == 'success':
                metadata = self.command(['cargo', 'metadata', '--locked', '--offline', '--format-version', '1',
                    '--manifest-path', str(self.manifest)], env={**os.environ, 'CARGO_HOME':str(self.cache)})
                self.assertEqual(len(json.loads(metadata.stdout)['packages']), 2)
                self.assertEqual(self.manifest.with_name('Cargo.lock').read_bytes(), self.lock)
        finally:
            # Only this harness's groups/PIDs are eligible for fallback cleanup.
            try:
                for process in processes:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)
                if self.marker.exists():
                    try:
                        reap_owned(2)
                    except ChildProcessError:
                        pass
            finally:
                sentinel.kill()
                sentinel.wait(timeout=5)
                self.assertEqual(libc.prctl(36, original.value, 0, 0, 0), 0)

    def test_timeout_kills_git_descendant_and_preserves_unrelated_process(self):
        self.exercise('timeout')

    def test_failed_cargo_kills_leftover_child_and_preserves_exit_code(self):
        self.exercise('failure')

    def test_success_cleans_leftover_child_and_retains_locked_offline_metadata(self):
        self.exercise('success')

    def test_interrupt_kills_git_descendant_and_preserves_interrupt(self):
        self.exercise('interrupt')


if __name__ == '__main__':
    unittest.main()
