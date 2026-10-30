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

    def chunked_console(self):
        report = {'success': True, 'screenshots': 'private-image-fixture' * 3000}
        data = json.dumps(report)
        parts = [data[offset:offset+4096] for offset in range(0, len(data), 4096)]
        lines = ['[ 12.0] python3[42]: FRAMEY_SYSTEMD_PROBE_CHUNK_JSON=' + json.dumps(
            {'index': index, 'total': len(parts), 'data': part})
            for index, part in enumerate(parts)]
        return report, lines

    def test_large_browser_evidence_survives_bounded_console_records(self):
        report, lines = self.chunked_console()
        self.assertEqual(self.module.guest_report('\n'.join(lines), browser=True), report)

    def test_chunked_guest_evidence_rejects_loss_duplicates_and_reordering(self):
        _, lines = self.chunked_console()
        for changed in (lines[:-1], lines + lines[-1:], lines[::-1], []):
            with self.subTest(count=len(changed)), self.assertRaises(RuntimeError):
                self.module.guest_report('\n'.join(changed), browser=True)

    def test_native_guest_result_requires_one_unambiguous_record(self):
        line = 'FRAMEY_SYSTEMD_PROBE_JSON={"success": true}'
        self.assertEqual(self.module.guest_report(line), {'success': True})
        for changed in ('', line+'\n'+line):
            with self.assertRaises(RuntimeError):
                self.module.guest_report(changed)

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

    def migration(self):
        report = dict.fromkeys(self.module.MIGRATION_REQUIRED, True)
        report.update(self.decky_shutdown(migration=True))
        report.update(architecture='x86_64', installerEnabled=False,
                      realFrameContacted=False, flatpakPackageVerified=True,
                      packagedBinarySha256='b' * 64, legacyMainPidBefore=150,
                      legacyMainPidAfterRestart=250,
                      pendingSetupRoutes={'GET state': 500, 'POST start': 204, 'POST stop': 204})
        for key, main, pid in [('legacyIdentityBefore', 150, 151),
                               ('legacyIdentityAfterRestart', 250, 251)]:
            report[key] = [dict(pid=pid, ancestryToMainPid=[pid, main],
                                executableSha256='b' * 64,
                                appCommit=self.module.COMMITS['x86_64']['app'],
                                runtimeCommit=self.module.COMMITS['x86_64']['runtime'])]
        return report

    def test_migration_requires_preservation_before_explicit_control(self):
        report = self.migration()
        bundles = self.prepared('x86_64')['bundles']
        self.module.verify_migration(report, 'x86_64', bundles)
        for mutation in (dict(pendingSetupPreservedLiveLegacy=False),
                         dict(configCertificateDataPreserved=False),
                         dict(explicitExternalControlAndAuth=False),
                         dict(ownedProcessesReaped=False), dict(installerEnabled=True)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.module.verify_migration({**report, **mutation}, 'x86_64', bundles)

    def test_migration_rejects_unsigned_wrong_process_or_missing_restart_proof(self):
        bundles = self.prepared('x86_64')['bundles']
        for key in ('legacyIdentityBefore', 'legacyIdentityAfterRestart'):
            for mutation in (dict(appCommit='0' * 64), dict(executableSha256='0' * 64),
                             dict(ancestryToMainPid=[151, 999])):
                report = self.migration()
                report[key][0].update(mutation)
                with self.subTest(key=key, mutation=mutation), self.assertRaises(ValueError):
                    self.module.verify_migration(report, 'x86_64', bundles)
        report = self.migration()
        del report['legacyIdentityAfterRestart']
        with self.assertRaises(ValueError):
            self.module.verify_migration(report, 'x86_64', bundles)

    def test_migration_requires_missing_unit_refusal_and_control_noops(self):
        bundles = self.prepared('x86_64')['bundles']
        for routes in (None, {'GET state': 200, 'POST start': 204, 'POST stop': 204},
                       {'GET state': 500, 'POST start': 500, 'POST stop': 204}):
            report = self.migration()
            report['pendingSetupRoutes'] = routes
            with self.subTest(routes=routes), self.assertRaises(ValueError):
                self.module.verify_migration(report, 'x86_64', bundles)

    def test_migration_cannot_reuse_the_initial_process_as_restart_proof(self):
        report = self.migration()
        report['legacyMainPidAfterRestart'] = report['legacyMainPidBefore']
        report['legacyIdentityAfterRestart'] = copy.deepcopy(report['legacyIdentityBefore'])
        with self.assertRaises(ValueError):
            self.module.verify_migration(report, 'x86_64', self.prepared('x86_64')['bundles'])

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
        report.update(self.decky_shutdown())
        return report, required

    def decky_shutdown(self, migration=False):
        # Fields emitted by the actual mixed-policy service fixtures. The
        # current AMD64 ownership artifact reports a clean 328 -> 0 stop.
        actual, removed = (('actualMigrationDeckyUserService', 'ownedMigrationDeckyServiceRemoved')
                           if migration else ('actualDeckyUserService', 'ownedDeckyServiceRemoved'))
        return {actual: True, removed: True, 'deckyShutdownLogChecked': True,
                'ownedDeckyStop': dict(mainPidBefore=328, mainPidAfter=0,
                    activeState='inactive', result='success', killMode='mixed',
                    execMainStatus='0', execMainCode='0', elapsedSeconds=6.7,
                    timeoutStopUSec='1min 30s')}

    def test_both_package_paths_require_checked_loader_shutdown(self):
        for migration in (False, True):
            for field in self.decky_shutdown(migration):
                for value in (None, False):
                    report = self.migration() if migration else self.candidate()[0]
                    if value is None:
                        del report[field]
                    else:
                        report[field] = value
                    with self.subTest(migration=migration, field=field, value=value):
                        with self.assertRaisesRegex(ValueError, 'Decky shutdown'):
                            if migration:
                                self.module.verify_migration(report, 'x86_64', self.prepared('x86_64')['bundles'])
                            else:
                                self.verify(report, self.candidate()[1])

    def test_both_package_paths_refuse_unsuccessful_or_incomplete_stop(self):
        for migration in (False, True):
            for mutation in (dict(result='timeout'), dict(activeState='failed'),
                             dict(killMode='control-group'), dict(execMainStatus='1'),
                             dict(mainPidBefore=0), dict(mainPidAfter=328)):
                report = self.migration() if migration else self.candidate()[0]
                report['ownedDeckyStop'].update(mutation)
                with self.subTest(migration=migration, mutation=mutation):
                    with self.assertRaisesRegex(ValueError, 'Decky shutdown'):
                        if migration:
                            self.module.verify_migration(report, 'x86_64', self.prepared('x86_64')['bundles'])
                        else:
                            self.verify(report, self.candidate()[1])

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

    def browser(self):
        report = dict.fromkeys(('success', 'actualDeckyRpc', 'syntheticInput', 'ownedBrowserReaped',
                                'bridgeStopped', 'setupCommitted', 'discoveredApiKeySaved'), True)
        report.update(dict.fromkeys(('browserSandboxDisabled', 'realFrameContacted',
                                     'hostBusExposed', 'installerEnabled'), False))
        report.update(savedPort=8384, panelSha256='a'*64, manualPortFallbackUsed=False,
                      stages=[{'stage': s, 'errors': [], 'text': 'Private service sync', 'manualPortFallbackUsed': False} for s in
                              ('running', 'stopped', 'restarted', 'stopped')],
                      actualPackagedProcessObservations=[{'stage': 'running', 'pids': [100, 101]},
                                                         {'stage': 'restarted', 'pids': [200, 201]}],
                      sandboxedRendererPids=[{'pid': 300, 'ancestryToBrowser': [300, 301],
                                             'seccomp': 2, 'noNewPrivs': 1}],
                      screenshots=dict.fromkeys(('running1', 'stopped2', 'restarted3', 'stopped4'), 'fixture'),
                      calls=[{'httpMethod': 'POST', 'path': '/__decky-watchdog/'+route, 'status': 204}
                             for route in ('check/start', 'check/scan_port', 'check/scan_api_key',
                                           'check/scan_basic_auth', 'reload-config', 'stop', 'start', 'stop')])
        report['calls'].insert(-1, {'httpMethod': 'POST', 'path': '/', 'status': 200})
        return report

    def test_browser_registration_or_synthetic_only_results_cannot_pass_combined_gate(self):
        self.module.verify_browser(self.browser(), 'a'*64)
        mutations = [dict(actualDeckyRpc=False), dict(panelSha256='b'*64), dict(realFrameContacted=True),
                     dict(browserSandboxDisabled=True), dict(ownedBrowserReaped=False), dict(stages=[]),
                     dict(sandboxedRendererPids=[]), dict(calls=[]), dict(screenshots={}),
                     dict(sandboxedRendererPids=[{'pid': 300, 'ancestryToBrowser': [300, 301],
                                                 'seccomp': 0, 'noNewPrivs': 1}]),
                     dict(actualPackagedProcessObservations=[{'stage': 'running', 'pids': [100]},
                                                            {'stage': 'restarted', 'pids': [100]}])]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.module.verify_browser({**self.browser(), **mutation}, 'a'*64)

    def test_browser_evidence_distinguishes_manual_port_entry_from_automatic_discovery(self):
        for manual in (False, True):
            report = self.browser()
            report['manualPortFallbackUsed'] = manual
            for stage in report['stages']:
                stage['manualPortFallbackUsed'] = manual
            self.module.verify_browser(report, 'a'*64)
            report['stages'][0]['manualPortFallbackUsed'] = not manual
            with self.assertRaisesRegex(ValueError, 'port path evidence'):
                self.module.verify_browser(report, 'a'*64)
        for value in (None, 0, 1, 'false'):
            report = self.browser()
            report['manualPortFallbackUsed'] = value
            with self.assertRaisesRegex(ValueError, 'port path'):
                self.module.verify_browser(report, 'a'*64)

    def test_browser_readiness_accepts_only_bounded_425_then_success(self):
        for statuses in ([200], [425, 200], [425] * 9 + [200]):
            report = self.browser()
            controls = [c for c in report['calls'] if c['path'] != '/']
            probes = [{'httpMethod': 'POST', 'path': '/', 'status': status} for status in statuses]
            report['calls'] = controls[:-1] + probes + controls[-1:]
            self.module.verify_browser(report, 'a'*64)

    def test_browser_readiness_failure_or_unknown_post_is_not_success(self):
        for statuses in ([], [425], [500], [425, 500], [200, 425], [200, 200], [425] * 300 + [200]):
            report = self.browser()
            report['calls'] = [c for c in report['calls'] if c['path'] != '/'] + [
                {'httpMethod': 'POST', 'path': '/', 'status': status} for status in statuses]
            with self.subTest(statuses=statuses), self.assertRaises(ValueError):
                self.module.verify_browser(report, 'a'*64)
        report = self.browser()
        report['calls'].append({'httpMethod': 'POST', 'path': '/unexpected', 'status': 200})
        with self.assertRaises(ValueError):
            self.module.verify_browser(report, 'a'*64)

    def test_failed_browser_control_or_javascript_error_is_not_a_pass(self):
        report = self.browser()
        report['calls'][-1]['status'] = 500
        with self.assertRaises(ValueError):
            self.module.verify_browser(report, 'a'*64)
        report = self.browser()
        report['stages'][1]['errors'] = ['Browser script failure']
        with self.assertRaises(ValueError):
            self.module.verify_browser(report, 'a'*64)


if __name__ == "__main__":
    unittest.main()
