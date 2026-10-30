"""Prepared bundles cannot bypass exact architecture/commit/signature gates."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PreparedPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (
            Path(__file__).resolve().parents[1]
            / "scripts/framey-test-syncthing-flatpak-package.py"
        )
        spec = importlib.util.spec_from_file_location("flatpak_package", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def prepared(self, arch):
        return {
            "architecture": arch,
            "commits": self.module.COMMITS[arch],
            "keySha256": self.module.KEY_SHA256,
            "payloadIntegrityVerified": True,
            "signatures": {"app": 1, "runtime": 1},
            "bundles": {
                kind: {"commit": commit, "bytes": 100, "sha256": "a" * 64}
                for kind, commit in self.module.COMMITS[arch].items()
            },
        }

    def test_fingerprints_work_without_python_311_file_digest(self):
        # The checks job runs the input-refusal tests on Python 3.9.
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture'
            data = b'bounded source fingerprint\n' * 50000
            path.write_bytes(data)
            with patch.object(hashlib, 'file_digest', None, create=True):
                self.assertEqual(self.module.sha(path), hashlib.sha256(data).hexdigest())

    def test_native_architecture_has_its_own_exact_commit_pins(self):
        for arch in self.module.ARCHES:
            report = self.prepared(arch)
            self.assertEqual(
                self.module.prepared_bundles(report, arch), report["bundles"]
            )
        self.assertNotEqual(
            self.module.COMMITS["x86_64"], self.module.COMMITS["aarch64"]
        )

    def test_other_architecture_or_unsigned_or_unverified_closure_is_refused(self):
        report = self.prepared("aarch64")
        mutations = [
            dict(architecture="x86_64"),
            dict(commits=self.module.COMMITS["x86_64"]),
            dict(keySha256="0" * 64),
            dict(payloadIntegrityVerified=False),
            dict(signatures={"app": 1, "runtime": 0}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.module.prepared_bundles({**report, **mutation}, "aarch64")

    def test_mismatched_bundle_commit_and_oversized_bundle_are_refused(self):
        for kind in ("app", "runtime"):
            for mutation in (
                dict(commit="0" * 64),
                dict(bytes=0),
                dict(bytes=384 * 1024**2 + 1),
            ):
                report = copy.deepcopy(self.prepared("aarch64"))
                report["bundles"][kind].update(mutation)
                with self.subTest(kind=kind, mutation=mutation), self.assertRaises(
                    ValueError
                ):
                    self.module.prepared_bundles(report, "aarch64")

    def test_missing_bundle_is_refused(self):
        report = self.prepared("x86_64")
        del report["bundles"]["runtime"]
        with self.assertRaises(ValueError):
            self.module.prepared_bundles(report, "x86_64")

    def candidate(self):
        required = ('ownedCleanup', 'actualStopJobReapedRuntime', 'realDeckyRpcRest')
        report = dict.fromkeys(required, True)
        report.update(
            architecture='x86_64', flatpakPackageVerified=True,
            realFrameContacted=False, noOwnedFlatpakInstancesRemain=True,
            packagedBinarySha256='b' * 64,
            deckyApiKeyErrorStatus=403, setupPortScans=[None, 8384],
            wizardConfigDiscovery=dict.fromkeys((
                'defaultPackageConfig', 'remainedUnconfiguredDuringScan',
                'discoveredDefaultPort', 'discoveredDefaultApiKey', 'scannedBasicAuth',
                'persistedThroughDeckyRpc', 'authenticatedRestWithDiscoveredKey',
                'setupCommittedAndReloaded', 'ownedSetupServiceStopped',
            ), True),
            rejectedManagedDefinitions={name: {
                'mainPidBefore': 120, 'mainPidAfter': 120,
                'unitAndReceiptPreserved': True, 'legacyStillEnabled': True,
                'refused': dict.fromkeys([
                    'GET state', 'POST start', 'POST stop', 'POST check/start',
                    'POST reload-config', 'POST external transition',
                ], 500),
            } for name in ('drop-in', 'shadow fragment', 'loaded alias')},
            actualPackagedServiceProcesses=[{
                'appCommit': self.module.COMMITS['x86_64']['app'],
                'runtimeCommit': self.module.COMMITS['x86_64']['runtime'],
                'executableSha256': 'b' * 64, 'mainPid': 150, 'syncthingPid': 151,
                'ancestryToMainPid': [151, 150],
            } for _ in range(3)],
        )
        return report, required

    def test_setup_requires_discovery_and_authenticated_use_without_preset_key(self):
        for field in ('discoveredDefaultApiKey', 'authenticatedRestWithDiscoveredKey',
                      'remainedUnconfiguredDuringScan', 'setupCommittedAndReloaded',
                      'ownedSetupServiceStopped'):
            report, required = self.candidate()
            report['wizardConfigDiscovery'][field] = False
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(report, required)
        report, required = self.candidate()
        del report['wizardConfigDiscovery']
        with self.assertRaises(ValueError):
            self.verify(report, required)

    def verify(self, report, required):
        self.module.verify_candidate(report, 'x86_64',
                                     self.prepared('x86_64')['bundles'], required)

    def test_port_readiness_retries_cannot_hide_a_failed_or_wrong_scan(self):
        for scans in ([], [None], [8080, 8384], [8384, 8384]):
            report, required = self.candidate()
            report['setupPortScans'] = scans
            with self.subTest(scans=scans), self.assertRaises(ValueError):
                self.verify(report, required)
        report, required = self.candidate()
        report['setupPortScans'] = [8384]
        self.verify(report, required)

    def test_old_shim_or_incomplete_lifecycle_cannot_establish_package_integration(self):
        report, required = self.candidate()
        self.verify(report, required)
        for mutation in [dict(flatpakPackageVerified=False), dict(architecture='aarch64'),
                         dict(ownedCleanup=False), dict(actualStopJobReapedRuntime=False),
                         dict(noOwnedFlatpakInstancesRemain=False),
                         dict(actualPackagedServiceProcesses=[])]:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.verify({**report, **mutation}, required)

    def test_missing_refusal_or_signalled_foreign_process_is_refused(self):
        for mutate in (
            lambda r: r['rejectedManagedDefinitions'].pop('loaded alias'),
            lambda r: r['rejectedManagedDefinitions']['drop-in'].update(mainPidAfter=121),
            lambda r: r['rejectedManagedDefinitions']['shadow fragment']['refused'].update({'POST stop': 204}),
            lambda r: r['rejectedManagedDefinitions']['loaded alias'].update(legacyStillEnabled=False),
        ):
            report, required = self.candidate()
            mutate(report)
            with self.assertRaises(ValueError):
                self.verify(report, required)

    def test_wrong_installed_commit_or_running_binary_is_refused(self):
        for mutation in [dict(appCommit='0' * 64), dict(runtimeCommit='0' * 64),
                         dict(executableSha256='0' * 64), dict(syncthingPid=0),
                         dict(ancestryToMainPid=[151, 200])]:
            report, required = self.candidate()
            report['actualPackagedServiceProcesses'][0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.verify(report, required)

    def test_helper_from_other_sources_or_architecture_is_refused_before_download(self):
        root = Path(__file__).resolve().parents[1]
        assets = root / 'ui/vendor/syncthing-0.2.7'
        digest = lambda name: hashlib.sha256((assets / name).read_bytes()).hexdigest()
        binary = b'\x7fELF' + b'\0' * 14 + (62).to_bytes(2, 'little')
        report = {
            'sourceCommit': '464fd7ca05ee0bea8daa8d5d125dfc672cf08942',
            'sourceArchiveSha256': digest('source.tar.gz'),
            'patchSha256': digest('watchdog.patch'),
            'ownedUnitSha256': digest('owned_unit.rs'),
            'pythonSha256': digest('main.py'), 'installerEnabled': False,
            'builds': [{'architecture': 'x86_64',
                        'sha256': hashlib.sha256(binary).hexdigest(),
                        'bytes': len(binary), 'serviceFileTestsExecuted': True}],
        }
        with tempfile.TemporaryDirectory() as temporary:
            helper = Path(temporary) / 'helper'
            build_report = Path(temporary) / 'build.json'
            helper.write_bytes(binary)
            for mutation, arch in [(dict(patchSha256='0' * 64), 'x86_64'),
                                   ({}, 'aarch64')]:
                build_report.write_text(json.dumps({**report, **mutation}))
                with self.assertRaises(ValueError):
                    self.module.candidate_payloads(helper, build_report, None, None, arch)


if __name__ == "__main__":
    unittest.main()
