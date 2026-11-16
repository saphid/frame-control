"""Pure host-runner protocol/fault controls; never launch QEMU or a loader."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_diagnostic', ROOT / 'scripts/framey-observe-native-terminal.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Process:
    pid = 99999999

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.waits = []
        self.code = None

    def poll(self):
        return self.code

    def wait(self, timeout):
        self.waits.append(timeout)
        outcome = self.outcomes.pop(0)
        if outcome == 'timeout':
            raise subprocess.TimeoutExpired('modeled-qemu', timeout)
        self.code = outcome
        return outcome


class DiagnosticTests(unittest.TestCase):
    def invoke(self, outcomes, signal_error=None):
        """Exercise actual main/finalization with synthetic files and mocked Popen."""
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode='w') as archive:
            for name in ('scripts/framey-test-syncthing-service.py', 'tests/decky-runtime/guest_result.py'):
                member = tarfile.TarInfo(name)
                member.size = 0
                archive.addfile(member, io.BytesIO(b''))
        fake_loader = b'\x7fELF' + bytes(14) + (183).to_bytes(2, 'little')
        process = Process(outcomes)
        signals = []
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            rootfs, loader, output = folder / 'rootfs', folder / 'loader', folder / 'out'
            rootfs.write_bytes(b'synthetic rootfs; not executable')
            loader.write_bytes(fake_loader)

            def pack(_rootfs, initrd, *_args, **_kwargs):
                initrd.write_bytes(b'synthetic initrd')
                return b'synthetic kernel'

            def start(*_args, **_kwargs):
                (output / 'console.log').write_text('\n'.join('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=' + p for p in runner.PHASES))
                (output / 'guest-result.packet').write_bytes(b'modeled packet')
                return process

            def git(command, **_kwargs):
                return archive_bytes.getvalue() if command[1] == 'archive' else b'synthetic-tree\n'

            def kill(pid, sig):
                signals.append((pid, sig))
                if signal_error:
                    raise signal_error('modeled signal failure')

            with patch.object(sys, 'argv', ['runner', '--rootfs-tar', str(rootfs), '--loader', str(loader), '--output', str(output)]), \
                 patch.object(runner, 'host_guard'), patch.object(runner.shutil, 'which', return_value='modeled-qemu'), \
                 patch.object(runner, 'LOADER_SHA', hashlib.sha256(fake_loader).hexdigest()), \
                 patch.object(runner, 'module', side_effect=[types.SimpleNamespace(pack=pack), types.SimpleNamespace(PORT='modeled', decode=lambda _: {'success': True})]), \
                 patch.object(runner.subprocess, 'check_output', side_effect=git), \
                 patch.object(runner.subprocess, 'Popen', side_effect=start), \
                 patch.object(runner.os, 'killpg', side_effect=kill), contextlib.redirect_stdout(io.StringIO()):
                code = runner.main()
            result = json.loads((output / 'assessment.json').read_text())
            self.assertFalse((output / 'initrd.gz').exists())
            self.assertFalse((output / 'vmlinuz').exists())
            return code, result, process.waits, signals

    def test_normal_exit_needs_no_signal(self):
        code, result, waits, signals = self.invoke([0])
        self.assertEqual((code, waits, signals), (0, [240], []))
        self.assertTrue(result['success'])
        self.assertFalse(result['qualificationPassed'])

    def test_original_timeout_survives_term_timeout_and_kill(self):
        code, result, waits, signals = self.invoke(['timeout', 'timeout', -9])
        self.assertEqual(waits, [240, 8, 5])
        self.assertEqual([s for _, s in signals], [signal.SIGTERM, signal.SIGKILL])
        self.assertEqual(result['hostErrorType'], 'TimeoutExpired')
        self.assertEqual(result['qemuCleanupErrors'], ['TimeoutExpired'])
        self.assertTrue(result['ownedQemuReaped'])
        self.assertTrue(result['ownedBootArtifactsRemoved'])
        self.assertEqual(code, 1)

    def test_both_cleanup_timeouts_still_finalize(self):
        code, result, waits, _ = self.invoke(['timeout', 'timeout', 'timeout'])
        self.assertEqual(waits, [240, 8, 5])
        self.assertFalse(result['ownedQemuReaped'])
        self.assertTrue(result['ownedBootArtifactsRemoved'])
        self.assertEqual((code, result['hostErrorType']), (1, 'TimeoutExpired'))

    def test_signal_failure_does_not_skip_waits_or_assessment(self):
        code, result, waits, _ = self.invoke(['timeout', 'timeout', -9], PermissionError)
        self.assertEqual(waits, [240, 8, 5])
        self.assertEqual(result['qemuCleanupErrors'].count('PermissionError'), 2)
        self.assertEqual((code, result['hostErrorType']), (1, 'TimeoutExpired'))

    def test_exited_before_signal_is_reaped_without_signal(self):
        process = Process([])
        process.code = 0
        result = {'forcedQemuTermination': False}
        with patch.object(runner.os, 'killpg') as kill:
            runner.cleanup_qemu(process, result)
        kill.assert_not_called()
        self.assertTrue(result['ownedQemuReaped'])

    def test_unlink_failure_does_not_skip_other_boot_file(self):
        first, second = unittest.mock.Mock(), unittest.mock.Mock()
        first.unlink.side_effect = PermissionError('synthetic')
        first.exists.return_value = True
        second.exists.return_value = False
        result = {}
        runner.remove_boot_files([first, second], result)
        second.unlink.assert_called_once_with(missing_ok=True)
        self.assertEqual(result['bootCleanupErrors'], ['PermissionError'])
        self.assertFalse(result['ownedBootArtifactsRemoved'])

    def test_success_refuses_each_failed_cleanup_and_transport_gate(self):
        good = dict(qemuReturnCode=0, forcedQemuTermination=False, guest={'success': True},
                    staticPhases={'complete': True}, ownedQemuReaped=True, ownedBootArtifactsRemoved=True,
                    qemuCleanupErrors=[], bootCleanupErrors=[], archivedRootfsUnchanged=True)
        self.assertTrue(runner.observation_passed(good))
        for key, value in [('qemuReturnCode', 1), ('forcedQemuTermination', True), ('guest', {'success': False}),
                           ('staticPhases', {'complete': False}), ('ownedQemuReaped', False),
                           ('ownedBootArtifactsRemoved', False), ('qemuCleanupErrors', ['TimeoutExpired']),
                           ('bootCleanupErrors', ['PermissionError']), ('archivedRootfsUnchanged', False),
                           ('hostErrorType', 'TimeoutExpired')]:
            with self.subTest(key=key):
                bad = copy.deepcopy(good)
                bad[key] = value
                self.assertFalse(runner.observation_passed(bad))

    def test_phase_order_and_subsets_fail_closed(self):
        def report(phases):
            return runner.phase_report('\n'.join('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=' + p for p in phases))
        self.assertTrue(report(runner.PHASES)['complete'])
        for order in itertools.permutations(runner.PHASES):
            self.assertEqual(report(order)['complete'], list(order) == runner.PHASES)
        for mask in range(255):
            self.assertFalse(report([p for i, p in enumerate(runner.PHASES) if mask & (1 << i)])['complete'])
        self.assertFalse(report(runner.PHASES + [runner.PHASES[-1]])['valid'])
        self.assertFalse(report(['unknown'])['valid'])

    def test_qemu_has_no_network_host_mount_or_passthrough(self):
        command = runner.qemu_command('qemu', Path('kernel'), Path('initrd'), Path('packet'), 'port')
        self.assertEqual(command[command.index('-nic') + 1], 'none')
        self.assertEqual(command[command.index('-smp') + 1], '2')
        self.assertEqual(command[command.index('-m') + 1], '6144')
        self.assertEqual(command[command.index('-accel') + 1], 'tcg,thread=multi')
        self.assertFalse({'-fsdev', '-virtfs', '-netdev', '-drive', '-usb'}.intersection(command))


if __name__ == '__main__':
    unittest.main()
