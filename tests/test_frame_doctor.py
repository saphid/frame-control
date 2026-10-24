"""Doctor tests never contact a headset or the user's SSH configuration."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
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
            code = doctor.main([])
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

    def test_help_shell_entry_point_is_offline(self):
        # Bash is optional on Windows test runners; the Python CLI is portable.
        import shutil
        if not shutil.which('bash'):
            self.skipTest('bash unavailable')
        r = subprocess.run(['bash', str(ROOT / 'scripts/frame-doctor.sh'), '--help'],
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Never pairs', r.stdout)


if __name__ == '__main__':
    unittest.main()
