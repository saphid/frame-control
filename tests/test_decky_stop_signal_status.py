"""Bounded signal masks inform an owned stop observation, never its pass gate."""
import ast
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class StopSignalStatus(unittest.TestCase):
    def reader(self):
        path = Path(__file__).parent / 'decky-runtime/syncthing_service.py'
        snapshot = next(node for node in ast.parse(path.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'decky_stop_snapshot')
        matches = [node for node in snapshot.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'signal_status']
        self.assertEqual(len(matches), 1, 'Owned stop snapshot lacks bounded signal masks')
        scope = {}
        exec(compile(ast.Module(body=matches, type_ignores=[]), str(path), 'exec'), scope)
        return scope['signal_status']

    def test_only_valid_signal_masks_are_retained_from_real_private_status(self):
        with tempfile.TemporaryDirectory(prefix='framey-signal-status-') as directory:
            root = Path(directory)
            (root / 'status').write_text('Name:\tdisposable-private-name\nUid:\t1100\n'
                'SigPnd:\t0000000000004000\nShdPnd:\t0000000000000000\n'
                'SigBlk:\t0000000000004000\nSigIgn:\t0000000000000000\n'
                'SigCgt:\t0000000000004000\nSigQ:\tprivate-extra-field\n')
            report = self.reader()(root)
            self.assertEqual(set(report['masks']), {'SigPnd', 'ShdPnd', 'SigBlk', 'SigIgn', 'SigCgt'})
            self.assertEqual(int(report['masks']['SigBlk'], 16), 1 << (signal.SIGTERM - 1))
            self.assertFalse(report['truncated'])
            self.assertNotIn('private', json.dumps(report))
            (root / 'status').write_text('SigBlk:\tnot-hex\nSigIgn:\t' + 'f' * 17 + '\nSigCgt:\t\n')
            self.assertEqual(self.reader()(root), {'masks': {}, 'truncated': False})

    def test_real_file_growth_is_bounded_and_explicitly_truncated(self):
        with tempfile.TemporaryDirectory(prefix='framey-signal-bound-') as directory:
            root = Path(directory)
            status = root / 'status'
            status.write_bytes(b'SigBlk:\t0000000000004000\n')
            original_open = Path.open
            reads = []
            class Reader:
                def __init__(self, stream): self.stream = stream
                def __enter__(self): return self
                def __exit__(self, *args): self.stream.close()
                def read(self, size=-1):
                    reads.append(size)
                    self.assert_bounded(size)
                    return self.stream.read(size)
                def assert_bounded(self, size):
                    if size != 4097: raise AssertionError('Unbounded status read')
            def grown_open(path, *args, **kwargs):
                if path == status and args == ('rb',):
                    with original_open(path, 'ab') as stream:
                        stream.write(b'x' * 12000 + b'private-overflow-sentinel')
                    return Reader(original_open(path, *args, **kwargs))
                return original_open(path, *args, **kwargs)
            reader = self.reader()
            with patch.object(Path, 'open', grown_open):
                report = reader(root)
            self.assertEqual(reads, [4097])
            self.assertTrue(report['truncated'])
            self.assertEqual(report['masks'], {'SigBlk': '0000000000004000'})
            self.assertNotIn('sentinel', json.dumps(report))

    def test_unavailable_status_is_a_diagnostic_limit(self):
        reader = self.reader()
        with tempfile.TemporaryDirectory(prefix='framey-signal-missing-') as directory:
            self.assertEqual(reader(Path(directory)), {'error': 'FileNotFoundError'})
            with patch.object(Path, 'open', side_effect=PermissionError('private path')):
                self.assertEqual(reader(Path(directory)), {'error': 'PermissionError'})

    @unittest.skipUnless(Path('/proc/self/status').is_file() and hasattr(signal, 'pthread_sigmask'),
                         'Live Linux signal masks require procfs and pthread_sigmask')
    def test_actual_owned_child_and_main_thread_default_ignore_caught_blocked_pending(self):
        reader = self.reader()
        program = '''import os,signal,sys
mode=sys.argv[1]
if mode=='ignored':signal.signal(signal.SIGTERM,signal.SIG_IGN)
if mode=='caught':signal.signal(signal.SIGTERM,lambda *_:None)
if mode=='blocked-pending':
 signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM})
 os.kill(os.getpid(),signal.SIGTERM)
print('owned-ready',flush=True)
sys.stdin.readline()
'''
        mask = 1 << (signal.SIGTERM - 1)
        for mode in ('default', 'ignored', 'caught', 'blocked-pending'):
            with self.subTest(mode=mode), subprocess.Popen(
                    [sys.executable, '-c', program, mode], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
                try:
                    with selectors.DefaultSelector() as poll:
                        poll.register(child.stdout, selectors.EVENT_READ)
                        self.assertTrue(poll.select(3), 'Owned child readiness timed out')
                    self.assertEqual(child.stdout.readline(), b'owned-ready\n')
                    for path in (Path('/proc') / str(child.pid),
                                 Path('/proc') / str(child.pid) / 'task' / str(child.pid)):
                        observed = reader(path)
                        self.assertFalse(observed['truncated'])
                        masks = {key: int(value, 16) for key, value in observed['masks'].items()}
                        self.assertEqual(bool(masks['SigIgn'] & mask), mode == 'ignored')
                        self.assertEqual(bool(masks['SigCgt'] & mask), mode == 'caught')
                        self.assertEqual(bool(masks['SigBlk'] & mask), mode == 'blocked-pending')
                        self.assertEqual(bool((masks['SigPnd'] | masks['ShdPnd']) & mask),
                                         mode == 'blocked-pending')
                    child.communicate(b'exit\n', timeout=3)
                    self.assertEqual(child.returncode, 0)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate(timeout=3)

    def test_full_owned_snapshot_retains_distinct_process_and_thread_masks(self):
        path = Path(__file__).parent / 'decky-runtime/syncthing_service.py'
        function = next(node for node in ast.parse(path.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'decky_stop_snapshot')
        unit = 'frame-control-migration-decky-fixture.service'
        group = '/user.slice/' + unit
        scope = dict(Path=Path, os=os, prop=lambda *_: group)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), scope)
        with tempfile.TemporaryDirectory(prefix='framey-owned-signal-snapshot-') as directory:
            root = Path(directory)
            cgroup = root / 'cgroups' / group.lstrip('/')
            cgroup.mkdir(parents=True)
            (cgroup / 'cgroup.procs').write_text('811\n812\n')
            proc = root / 'proc'
            own = proc / '811'
            thread = own / 'task/811'
            thread.mkdir(parents=True)
            fields = ['S', '100'] + ['0'] * 20
            fields[19] = '4242'
            (own / 'stat').write_text('811 (private worker) ' + ' '.join(fields))
            (own / 'cgroup').write_text('0::' + group + '\n')
            (own / 'status').write_text('Name:\tprivate-worker\nSigIgn:\t0000000000004000\n')
            (thread / 'status').write_text('SigBlk:\t0000000000004000\n')
            (thread / 'wchan').write_text('do_epoll_wait')
            (thread / 'stack').write_text('private-kernel-stack\n')
            foreign = proc / '812'
            foreign.mkdir()
            (foreign / 'cgroup').write_text('0::/unrelated.service\n')
            snapshot = scope['decky_stop_snapshot'](unit, [], proc=proc, cgroups=root / 'cgroups')
            owned, refused = snapshot['processes']
            self.assertIn('signalStatus', owned, 'Owned process lacks signal status observation')
            self.assertEqual(owned['signalStatus']['masks'], {'SigIgn': '0000000000004000'})
            self.assertEqual(owned['threads'][0]['signalStatus']['masks'], {'SigBlk': '0000000000004000'})
            self.assertEqual(refused, {'pid': 812, 'error': 'Process left the owned cgroup; not inspected'})
            self.assertNotIn('private-worker', json.dumps(snapshot))

    def test_signal_mask_cut_by_read_limit_is_not_reported_as_complete(self):
        with tempfile.TemporaryDirectory(prefix='framey-signal-cut-') as directory:
            root = Path(directory)
            suffix = b'\nSigBlk:\t0000'
            (root / 'status').write_bytes(b'x' * (4096 - len(suffix)) + suffix + b'000000004000\n')
            self.assertEqual(self.reader()(root), {'masks': {}, 'truncated': True})
