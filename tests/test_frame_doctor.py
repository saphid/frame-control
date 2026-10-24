"""Doctor tests never contact a headset or the user's SSH configuration."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frame_doctor', ROOT / 'scripts/frame_doctor.py')
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)
doctor.MESSAGES = doctor.messages()


def result(out='', code=0, err=''):
    return subprocess.CompletedProcess([], code, out, err)


class FrameDoctor(unittest.TestCase):
    def main(self, responses, **kwargs):
        config = result('hostname private-tailnet.ts.net\nhostkeyalias pinned-frame\n')
        with patch.object(doctor.shutil, 'which', return_value='/usr/bin/ssh'), \
                patch.object(doctor, 'run', side_effect=[config, *responses]) as run, \
                patch.object(doctor, 'port_open', return_value=kwargs.get('devkit', False)), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            code = doctor.main(kwargs.get('argv', []))
        return code, output.getvalue(), run

    def test_unreachable_is_actionable_without_exposing_stderr(self):
        code, text, _ = self.main([result(code=255, err='secret-token 192.0.2.5')] * 3)
        self.assertEqual(code, 2)
        self.assertIn('wake headset', text)
        self.assertEqual(text.count('No authenticated SSH path.'), 11)
        self.assertNotIn('secret-token', text)
        self.assertNotIn('192.0.2.5', text)
        self.assertNotIn('private-tailnet', text)

    def test_no_keys_and_devkit_available_never_registers(self):
        code, text, run = self.main([result(code=255, err='Permission denied')] * 3, devkit=True)
        self.assertEqual(code, 2)
        self.assertIn('no pairing request was sent', text)
        self.assertIn('Pair new host', text)
        self.assertFalse(any('/register' in str(c.args[0]) for c in run.call_args_list))

    def test_fallback_preserves_identity_and_disables_mutating_ssh_options(self):
        _, text, run = self.main([result(code=255), result(json.dumps({'guard': 'loop', 'checks': []}))])
        args = run.call_args_list[2].args[0]
        for flag in ('HostKeyAlias=pinned-frame', 'HostName=frame.local', 'BatchMode=yes',
                     'StrictHostKeyChecking=yes', 'UpdateHostKeys=no', 'PermitLocalCommand=no',
                     'ClearAllForwardings=yes', 'ControlPath=none'):
            self.assertIn(flag, args)
        self.assertIn('OK Connection: LAN', text)
        self.assertIn('Counters are rising', text)

    def test_hostkey_failure_does_not_suggest_deleting_identity(self):
        _, text, _ = self.main([result(code=255, err='REMOTE HOST IDENTIFICATION HAS CHANGED')] * 3)
        self.assertIn('Do not delete known_hosts', text)

    def test_invalid_probe_response_never_prints_remote_data(self):
        for payload in ('a secret token', json.dumps({'guard': 'stable', 'checks': [['OK', 'secret']] * 11})):
            code, text, _ = self.main([result(payload)])
            self.assertEqual(code, 1)
            self.assertNotIn('secret', text)

    def test_guard_stops_before_any_deeper_checks(self):
        for state in ('loop', 'unknown', 'risk'):
            with patch.object(doctor, 'guard', return_value=state), patch.object(doctor, 'journal') as journal:
                self.assertEqual(doctor.probe(), {'guard': state, 'checks': []})
                journal.assert_not_called()

    def test_rising_and_reset_counters_and_missing_data(self):
        for snapshots, expected in (([[0, 0, 0, 0], [1, 0, 0, 0]], 'loop'),
                                    ([[1, 0, 0, 0], [0, 0, 0, 0]], 'unknown'),
                                    ([None, None], 'unknown'),
                                    ([[0, 4, 0, 0]] * 2, 'risk'),
                                    ([[0, 0, 0, 0]] * 2, 'stable')):
            with patch.object(doctor, 'snapshot', side_effect=snapshots), patch.object(doctor.time, 'sleep'):
                self.assertEqual(doctor.guard(), expected)

    def test_journal_permission_denied_and_empty_are_unknown(self):
        for response in (result('partial', err='not seeing messages from other users'), result(), result(code=1)):
            with patch.object(doctor, 'run', return_value=response):
                self.assertIsNone(doctor.journal('-b'))
        self.assertEqual(doctor.signal_check(None, 'bad', 'problem', 'healthy')[0], 'UNKNOWN')

    def test_disk_full_reports_broken_and_never_fixes(self):
        with patch.object(doctor.shutil, 'disk_usage', return_value=Mock(free=0)):
            check = doctor.storage()
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            code = doctor.report({'guard': 'stable', 'checks': [check] * 11})
        self.assertEqual(code, 1)
        self.assertIn('BROKEN 4. Steam and storage', output.getvalue())

    def test_probe_only_emits_approved_messages_and_rechecks_guard(self):
        with patch.object(doctor, 'guard', side_effect=['stable', 'stable']) as guard, \
                patch.object(doctor, 'journal', return_value=None), \
                patch.object(doctor, 'command', return_value=None), \
                patch.object(doctor, 'run', return_value=None), \
                patch.object(doctor, 'storage', return_value=['UNKNOWN', 'Storage could not be read.']):
            data = doctor.probe()
        self.assertEqual(guard.call_count, 2)
        self.assertEqual(len(data['checks']), 11)
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(doctor.report(data), 1)

    def stable(self, disk=None):
        checks = [['UNKNOWN', 'Evidence unavailable; consult the runbook locally.'] for _ in doctor.SECTIONS]
        checks[3] = disk or ['BROKEN', 'Less than 16 MiB free; review storage in Frame Control before installing.']
        return {'guard': 'stable', 'checks': checks}

    def test_plan_requires_exact_evidence_and_never_adds_remote_commands(self):
        data = self.stable()
        code, text, calls = self.main([result(json.dumps(data))], argv=['--plan'])
        self.assertEqual(code, 1)
        self.assertIn('READ-ONLY', text)
        self.assertIn('use Steam storage management', text)
        self.assertEqual(calls.call_count, 2)  # config read and unchanged read-only probe
        data['checks'][3] = ['BROKEN', 'Evidence unavailable; consult the runbook locally.']
        _, text, _ = self.main([result(json.dumps(data))], argv=['--plan'])
        self.assertNotIn('use Steam storage management', text)
        self.assertIn('does not establish a safe automatic fix', text)

    def test_plan_guard_blocks_all_section_actions(self):
        for state in ('loop', 'risk', 'unknown'):
            _, text, _ = self.main([result(json.dumps({'guard': state, 'checks': []}))], argv=['--plan'])
            self.assertIn('BLOCKED', text)
            self.assertNotIn('PLAN 4.', text)

    def test_before_after_and_exclusive_private_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'before.json'
            before = self.stable()
            _, text, _ = self.main([result(json.dumps(before))], argv=['--save-report', str(path)])
            saved = path.read_text()
            self.assertNotIn('private-tailnet', saved)
            self.assertNotIn('pinned-frame', saved)
            if __import__('os').name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            after = self.stable(['OK', 'Home and title storage have at least 256 MiB free.'])
            _, text, _ = self.main([result(json.dumps(after))], argv=['--compare-before', str(path)])
            self.assertIn('Steam and storage: BROKEN -> OK', text)
            self.assertIn('do not prove repair', text)
            self.assertIn('Before evidence: Less than 16 MiB free', text)
            self.assertIn('After evidence: Home and title storage', text)
            code, _, _ = self.main([result(json.dumps(after))], argv=['--save-report', str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(path.read_text(), saved)
            # Same alias with changed routing cannot masquerade as the same baseline.
            code, text, calls = self.main([], argv=['--compare-before', str(path), '--usb', '192.0.2.9'])
            self.assertEqual(code, 2)
            self.assertIn('comparison refused', text)
            self.assertEqual(calls.call_count, 1)

    def test_report_refuses_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'target'
            target.write_text('preserve')
            link = Path(folder) / 'link'
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('symlinks unavailable')
            code, _, _ = self.main([result(json.dumps(self.stable()))], argv=['--save-report', str(link)])
            self.assertEqual(code, 2)
            self.assertEqual(target.read_text(), 'preserve')

    def test_comparison_suppresses_improvement_if_guard_fails(self):
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            doctor.compare(self.stable(), {'guard': 'risk', 'checks': []})
        self.assertIn('Comparison blocked', output.getvalue())
        self.assertNotIn('BROKEN -> OK', output.getvalue())

    def test_untrusted_baselines_and_probe_are_rejected_without_echo(self):
        for payload in ('secret', '[]', '{"version":1}', 'x' * 65537, '[' * 2000 + ']' * 2000):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'baseline.json'
                path.write_text(payload)
                code, text, calls = self.main([], argv=['--compare-before', str(path)])
                self.assertEqual(code, 2)
                self.assertNotIn('secret', text)
                calls.assert_not_called()
        for data in ({'guard': 'secret', 'checks': []},
                     {'guard': 'risk', 'checks': [['WARN', 'secret']]},
                     dict(self.stable(), raw='secret'),
                     self.stable(['WARN', 'Never pairs'])):
            code, text, _ = self.main([result(json.dumps(data))], argv=['--plan'])
            self.assertEqual(code, 1)
            self.assertNotIn('secret', text)
            self.assertNotIn('Repair plan', text)

    def test_help_shell_entry_point_is_offline(self):
        # This Bash wrapper is for macOS/Linux; Windows uses the Python CLI.
        import os, shutil
        if os.name == 'nt':
            self.skipTest('POSIX shell wrapper')
        if not shutil.which('bash'):
            self.skipTest('bash unavailable')
        r = subprocess.run(['bash', str(ROOT / 'scripts/frame-doctor.sh'), '--help'],
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Never pairs', r.stdout)


if __name__ == '__main__':
    unittest.main()
