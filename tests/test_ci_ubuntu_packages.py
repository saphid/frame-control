"""CI package installation must recover without bypassing archive trust."""
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/ci-ubuntu-packages.py'))
install = MODULE['install']


class UbuntuPackages(unittest.TestCase):
    def exercise(self, failures, architecture='arm64'):
        calls = []

        def run(command, **kwargs):
            source = Path(command[command.index('-o') + 1].split('=', 1)[1])
            calls.append((command, kwargs, source.read_text()))
            if len(calls) in failures:
                raise subprocess.CalledProcessError(failures[len(calls)], command)

        with patch.object(Path, 'is_file', return_value=True):
            install(['qemu-system-arm'], 'noble', architecture, run=run)
        return calls

    def test_healthy_primary_installs_without_another_mirror(self):
        calls = self.exercise({})
        self.assertEqual(len(calls), 2)
        self.assertIn('https://ports.ubuntu.com/ubuntu-ports', calls[0][2])
        self.assertEqual(calls[0][0][2], '90s')
        self.assertEqual(calls[1][0][2], '180s')

    def test_dns_timeout_uses_fresh_lists_on_independent_mirror(self):
        calls = self.exercise({1: 124})
        self.assertEqual(len(calls), 3)
        self.assertIn('https://mirrors.mit.edu/ubuntu-ports', calls[1][2])
        lists = lambda c: next(x for x in c[0] if x.startswith('Dir::State::lists='))
        self.assertNotEqual(lists(calls[0]), lists(calls[1]))
        self.assertEqual(calls[1][0][-1], 'update')
        self.assertEqual(calls[2][0][-4:], ['install', '-y', '--no-install-recommends', 'qemu-system-arm'])

    def test_archive_download_failure_refreshes_fallback_before_install(self):
        calls = self.exercise({2: 100})
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[2][0][-1], 'update')
        self.assertIn('https://mirrors.mit.edu/ubuntu-ports', calls[3][2])

    def test_signature_failures_remain_failures(self):
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.exercise({1: 100, 2: 100})
        self.assertEqual(caught.exception.returncode, 100)

    def test_no_stale_lists_or_trust_bypass_on_either_architecture(self):
        for architecture in ('amd64', 'amd64v3', 'arm64'):
            with self.subTest(architecture=architecture):
                for command, kwargs, source in self.exercise({1: 100}, architecture):
                    self.assertTrue(kwargs['check'])
                    self.assertIn('Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg', source)
                    self.assertNotIn('Architectures:', source)
                    self.assertIn('ubuntu-ports' if architecture == 'arm64' else '/ubuntu\n', source)
                    self.assertIn('Suites: noble noble-updates noble-security', source)
                    self.assertIn('APT::Update::Error-Mode=any', command)
                    self.assertIn('Dir::Etc::sourceparts=-', command)
                    self.assertFalse(any('trusted=' in x or 'AllowUnauthenticated' in x or
                                         'allow-unauthenticated' in x or 'Verify-Peer=false' in x
                                         for x in command))

    def test_invalid_inputs_never_start_apt(self):
        for packages, codename, architecture in [(['--allow-unauthenticated'], 'noble', 'arm64'),
                                                (['zsh'], 'noble\nTrusted: yes', 'amd64'),
                                                (['zsh'], 'noble', 'unknown')]:
            with self.subTest(packages=packages, architecture=architecture), \
                    patch('subprocess.run') as run:
                with self.assertRaises(ValueError):
                    install(packages, codename, architecture, run=run)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
