"""Real doctor/SSH against fake-Frame faults; never a real headset."""
import subprocess
import sys

import harness
from harness import ROOT, ctl

harness.require()


class Doctor(harness.FrameTestCase):
    def doctor(self):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/frame_doctor.py'),
                               '--lan', harness.FAKE_HOST, '--usb', harness.FAKE_HOST],
                              capture_output=True, text=True, timeout=120)

    def test_disk_full(self):
        before = self.doctor()
        self.assertNotIn('BROKEN 4. Steam and storage', before.stdout)
        ctl('disk-full', 'on')
        r = self.doctor()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('BROKEN 4. Steam and storage: Less than 16 MiB free', r.stdout)

    def test_unreachable_asleep(self):
        ctl('sleep', 'on')
        r = self.doctor()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('No authenticated SSH path', r.stdout)

    def test_no_ssh_and_no_devkit(self):
        ctl('sshd', 'off')
        ctl('devkit-service', 'off')
        r = self.doctor()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('Devkit port did not respond', r.stdout)

    def test_no_keys_but_devkit_available(self):
        ctl('keys', 'none')
        r = self.doctor()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('SSH key rejected', r.stdout)
        self.assertIn('no pairing request was sent', r.stdout)
