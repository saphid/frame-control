#!/usr/bin/env python3
"""Run exact signed Syncthing packages in an owned, networkless native VM.

Inputs are a disposable Debian rootfs export with systemd, Flatpak, OSTree GI
and a kernel, plus locally generated bundles of the pinned published commits.
No host filesystem, bus, disk, device or network NIC is exposed to the guest.
An optional source-bound candidate helper also tests actual Decky service RPC.
The managed installer and real Frame remain outside this disposable VM.
"""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ARCHES = {
    "x86_64": ("qemu-system-x86_64", "ttyS0", []),
    "aarch64": ("qemu-system-aarch64", "ttyAMA0", ["-machine", "virt"]),
}
# ARM64 TCG spends substantially longer validating/installing the GNOME runtime.
# Keep per-command, user, systemd-unit and outer emulator limits explicit.
BUDGETS = {
    'x86_64': {'installSeconds': 300, 'userSeconds': 840, 'unitSeconds': 900, 'hostSeconds': 960},
    'aarch64': {'installSeconds': 900, 'userSeconds': 2400, 'unitSeconds': 2460, 'hostSeconds': 2520},
}
COMMITS = {
    "x86_64": {
        "app": "2be395a769ce7f1d8332892c1777d9f1f147ce7f66647864d87d5550e7061034",
        "runtime": "2bb946ea4ebb050f6a32f90e979feb975b08280d1ff1aac881dec3d1361ad84d",
    },
    "aarch64": {
        "app": "b5116b67092a6d3bdeb202a0308c2d2ec8f53b980e75e88992781a01aa8937c0",
        "runtime": "c3daeced6f88f9c4ffc4f88c798c48fffd395d873fc0d36b7fc73b753d7f59c9",
    },
}
MARKER = b"Frame Control Flatpak VM v1\n"
KEY_SHA256 = "8bdc20abc4e19c0796460beb5bfe0e7aa4138716999e19c6f2dbdd78cc41aeaa"
BUNDLES = {
    "runtime": {
        "sha256": "9e2a88bf95d9a6bdcf15335d967ef2d311946875d241b24f998631bdb1899069",
        "bytes": 292381320,
    },
    "app": {
        "sha256": "25c3368e362634e6cf239bc58663bb8b7ca69b6f5fbfa90ab3b86956c1884a04",
        "bytes": 9872520,
    },
}
REQUIRED = (
    "signedBundlesInstalled",
    "packageLaunched",
    "actualTwoWaySync",
    "runtimeOriginGpgVerificationEnabled",
    "appOriginGpgVerificationEnabled",
    "actualUserServiceLifecycle",
    "certificateRetained",
    "syncRetainedAfterRestart",
    "ownedServiceRemoved",
    "ownedProcessesReaped",
    "noOwnedFlatpakInstancesRemain",
    "uninstallPreservedOwnedData",
)
MIGRATION_REQUIRED = (
    'actualLegacySignedPackage', 'v1SettingsMigratedAndPersisted',
    'pendingSetupPreservedLiveLegacy', 'legacyUnitAndEnablementPreserved',
    'configCertificateDataPreserved', 'unrelatedHelperPreserved',
    'explicitExternalControlAndAuth', 'actualLegacyStopRestart',
    'legacyDataRetainedAfterRestart', 'ownedProcessesReaped',
    'ownedLegacyFixtureRemoved', 'noOwnedFlatpakInstancesRemain',
)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def reap(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


class Termination:
    """SIGTERM handler raising SystemExit, deferred while a child is registered."""

    def __init__(self):
        self.deferring = False
        self.pending = None

    def __call__(self, signum, _frame):
        if self.deferring:
            self.pending = signum
            return
        raise SystemExit(128 + signum)

    @contextlib.contextmanager
    def deferred(self):
        self.deferring = True
        try:
            yield
        finally:
            self.deferring = False
            if self.pending is not None:
                raise SystemExit(128 + self.pending)


def prepared_bundles(preparation, arch):
    if (
        preparation.get("architecture") != arch
        or preparation.get("commits") != COMMITS[arch]
        or preparation.get("keySha256") != KEY_SHA256
        or preparation.get("payloadIntegrityVerified") is not True
        or any(
            preparation.get("signatures", {}).get(kind, 0) < 1
            for kind in ("app", "runtime")
        )
    ):
        raise ValueError("Incomplete or mismatched preparation proof")
    bundles = preparation["bundles"]
    if set(bundles) != {"app", "runtime"}:
        raise ValueError("Unexpected prepared bundle set")
    for kind, expected in bundles.items():
        if (
            expected.get("commit") != COMMITS[arch][kind]
            or not 0 < expected.get("bytes", 0) <= 384 * 1024**2
        ):
            raise ValueError("Unexpected prepared bundle commit or size")
    return bundles


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def candidate_payloads(helper_path, report_path, archive_path, loader_path, arch):
    build = module('syncthing_build', ROOT / 'scripts/build-framey-syncthing.py')
    native = module('native_decky', ROOT / 'scripts/framey-test-decky-runtime.py')
    runtime = module('syncthing_runtime', ROOT / 'scripts/framey-test-syncthing-runtime.py')
    if report_path.stat().st_size > 256 * 1024 or helper_path.stat().st_size > 40 * 1024**2:
        raise ValueError('Oversized candidate input')
    report = json.loads(report_path.read_text())
    assets = ROOT / 'ui/vendor/syncthing-0.2.7'
    required = {
        'sourceCommit': build.SOURCE_COMMIT,
        'sourceArchiveSha256': sha(assets / 'source.tar.gz'),
        'patchSha256': sha(assets / 'watchdog.patch'),
        'ownedUnitSha256': sha(assets / 'owned_unit.rs'),
        'pythonSha256': sha(assets / 'main.py'),
        'installerEnabled': False,
    }
    if any(report.get(key) != value for key, value in required.items()):
        raise ValueError('Candidate build is not bound to the current sources')
    builds = [item for item in report.get('builds', []) if item.get('architecture') == arch]
    helper = helper_path.read_bytes()
    elf = {'x86_64': 62, 'aarch64': 183}[arch]
    if (len(builds) != 1 or builds[0].get('sha256') != hashlib.sha256(helper).hexdigest()
        or builds[0].get('bytes') != len(helper)
        or builds[0].get('serviceFileTestsExecuted') is not True
        or helper[:4] != b'\x7fELF' or int.from_bytes(helper[18:20], 'little') != elf):
        raise ValueError('Candidate helper/build architecture or digest mismatch')
    loader, loader_sha = native.loader_bytes(loader_path)
    official = (archive_path.read_bytes() if archive_path else runtime.download(
        'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/' + runtime.DIGEST + '.zip',
        50 * 1024**2,
    ))
    if hashlib.sha256(official).hexdigest() != runtime.DIGEST:
        raise ValueError('Pinned official plugin archive mismatch')
    evidence = {
        **required, 'architecture': arch, 'helperSha256': sha(helper_path),
        'buildReportSha256': sha(report_path), 'loaderSha256': loader_sha,
        'decky': native.RELEASE, 'officialArchiveSha256': runtime.DIGEST,
    }
    return {
        'watchdog': helper, 'PluginLoader': loader, 'official.zip': official,
        'main.py': (assets / 'main.py').read_bytes(),
        'syncthing_service.py': (ROOT / 'tests/decky-runtime/syncthing_service.py').read_bytes(),
        'syncthing_migration.py': (ROOT / 'tests/decky-runtime/syncthing_migration.py').read_bytes(),
        'candidate-inputs.json': json.dumps(evidence).encode(),
    }, evidence


def verify_migration(report, arch, bundles):
    if (report.get('architecture') != arch
        or report.get('installerEnabled') is not False
        or report.get('realFrameContacted') is not False
        or report.get('flatpakPackageVerified') is not True
        or any(report.get(key) is not True for key in MIGRATION_REQUIRED)):
        raise ValueError('Missing actual legacy migration preservation/control proof')
    module('syncthing_service_gates', ROOT/'scripts/framey-test-syncthing-service.py').verify_decky_shutdown(
        report, migration=True)
    if report.get('pendingSetupRoutes') != {'GET state': 500, 'POST start': 204, 'POST stop': 204}:
        raise ValueError('Missing pending migration refusal/no-op proof')
    if report.get('legacyMainPidBefore') == report.get('legacyMainPidAfterRestart'):
        raise ValueError('Missing new legacy service PID after restart')
    for key, main_key in (('legacyIdentityBefore', 'legacyMainPidBefore'),
                          ('legacyIdentityAfterRestart', 'legacyMainPidAfterRestart')):
        processes = report.get(key, [])
        if not processes:
            raise ValueError('Missing signed legacy process identity')
        for process in processes:
            lineage = process.get('ancestryToMainPid', [])
            if (process.get('pid', 0) <= 0 or report.get(main_key, 0) <= 0
                or not lineage or lineage[0] != process['pid'] or lineage[-1] != report[main_key]
                or process.get('executableSha256') != report.get('packagedBinarySha256')
                or any(process.get(kind + 'Commit') != bundles[kind]['commit']
                       for kind in ('app', 'runtime'))):
                raise ValueError('Legacy migration used an unexpected process/package')


def verify_candidate(service, arch, bundles, required_results):
    if (service.get('architecture') != arch
        or service.get('flatpakPackageVerified') is not True
        or service.get('realFrameContacted') is not False
        or service.get('noOwnedFlatpakInstancesRemain') is not True
        or service.get('deckyApiKeyErrorStatus') != 403
        or any(service.get(key) is not True for key in required_results)):
        raise ValueError('Incomplete actual-package candidate lifecycle proof')
    module('syncthing_service_gates', ROOT/'scripts/framey-test-syncthing-service.py').verify_decky_shutdown(service)
    wizard = service.get('wizardConfigDiscovery', {})
    if any(wizard.get(key) is not True for key in (
        'defaultPackageConfig', 'remainedUnconfiguredDuringScan',
        'discoveredDefaultPort', 'discoveredDefaultApiKey', 'scannedBasicAuth',
        'persistedThroughDeckyRpc', 'authenticatedRestWithDiscoveredKey',
        'setupCommittedAndReloaded', 'ownedSetupServiceStopped',
    )):
        raise ValueError('Missing actual-package setup discovery proof')
    scans = service.get('setupPortScans', [])
    if (not scans or scans[-1] != 8384
        or any(port is not None for port in scans[:-1])):
        raise ValueError('Missing setup port discovery attempt evidence')
    definitions = service.get('rejectedManagedDefinitions', {})
    routes = {'GET state', 'POST start', 'POST stop', 'POST check/start',
              'POST reload-config', 'POST external transition'}
    if set(definitions) != {'drop-in', 'shadow fragment', 'loaded alias'}:
        raise ValueError('Missing candidate ownership refusal cases')
    for value in definitions.values():
        if (value.get('mainPidBefore', 0) <= 0
            or value.get('mainPidBefore') != value.get('mainPidAfter')
            or value.get('unitAndReceiptPreserved') is not True
            or value.get('legacyStillEnabled') is not True
            or value.get('refused') != dict.fromkeys(routes, 500)):
            raise ValueError('Ownership refusal failed to preserve the live process')
    processes = service.get('actualPackagedServiceProcesses', [])
    if len(processes) < 3:
        raise ValueError('Missing packaged process identity checks')
    for process in processes:
        if (process.get('appCommit') != bundles['app']['commit']
            or process.get('runtimeCommit') != bundles['runtime']['commit']
            or process.get('executableSha256') != service.get('packagedBinarySha256')
            or process.get('mainPid', 0) <= 0 or process.get('syncthingPid', 0) <= 0
            or not process.get('ancestryToMainPid')
            or process['ancestryToMainPid'][0] != process['syncthingPid']
            or process['ancestryToMainPid'][-1] != process['mainPid']):
            raise ValueError('Candidate service executed an unexpected package')


def browser_payloads(official):
    browser = module('syncthing_browser_render', ROOT / 'scripts/framey-test-syncthing-browser.py')
    with tempfile.TemporaryDirectory(prefix='framey-browser-panel-') as temporary:
        archive = Path(temporary) / 'official.zip'
        archive.write_bytes(official)
        bundle = browser.frontend(archive, True)
    with patch.object(browser.framey_panel, '_owned_dist', return_value=(None, bundle, browser.DIGEST)):
        panel = browser.framey_panel.panel(64).decode()
    import base64
    for route, name in [('react.js', 'vendor/react-18.3.1.min.js'),
                        ('react-dom.js', 'vendor/react-dom-18.3.1.min.js'), ('host.js', 'framey-host.js')]:
        data = base64.b64encode((ROOT / 'ui' / name).read_bytes()).decode()
        panel = panel.replace(f'src="/framey-runtime/{route}"', f'src="data:text/javascript;base64,{data}"')
    return {
        'browser-panel.html': panel.encode(),
        'syncthing_browser.py': (ROOT / 'tests/decky-runtime/syncthing_browser.py').read_bytes(),
        'frame_steam.py': (ROOT / 'ui/frame_steam.py').read_bytes(),
    }, {'frontendSha256': hashlib.sha256(bundle).hexdigest(),
        'panelSha256': hashlib.sha256(panel.encode()).hexdigest()}


def http_gateway_payloads(browser_parent=False):
    import io
    import tarfile
    packed = io.BytesIO()
    sources = {}
    with tarfile.open(fileobj=packed, mode='w') as archive:
        for path in sorted(list((ROOT/'ui').rglob('*')) +
                           [ROOT/'apk-catalog'/name for name in ('build.py', 'reports.py', 'pick.py')]):
            name = path.relative_to(ROOT).as_posix()
            if path.suffix not in ('.py', '.json', '.html', '.js') and name != 'ui/local-bin/ssh':
                continue
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 8*1024**2:
                raise ValueError('Unexpected production HTTP UI source')
            data = path.read_bytes()
            sources[name] = hashlib.sha256(data).hexdigest()
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o700 if name == 'ui/local-bin/ssh' else 0o600
            archive.addfile(entry, io.BytesIO(data))
    data = packed.getvalue()
    if len(data) > 32*1024**2:
        raise ValueError('Production HTTP fixture UI exceeds its bound')
    payloads = {
        'framey-http-ui.tar': data,
        'framey-http-ui-sources.json': json.dumps(sources).encode(),
        'syncthing_http.py': (ROOT/'tests/decky-runtime/syncthing_http.py').read_bytes(),
    }
    if browser_parent:
        payloads['syncthing_http_parent.py'] = (ROOT/'tests/decky-runtime/syncthing_http_parent.py').read_bytes()
    return payloads, {'uiArchiveSha256': hashlib.sha256(data).hexdigest(), 'sourceSha256': sources}


def verify_browser(report, expected_panel):
    for key, expected in {
        'success': True, 'actualDeckyRpc': True, 'syntheticInput': True,
        'browserSandboxDisabled': False, 'ownedBrowserReaped': True, 'bridgeStopped': True,
        'realFrameContacted': False, 'hostBusExposed': False, 'installerEnabled': False,
        'setupCommitted': True, 'discoveredApiKeySaved': True, 'savedPort': 8384,
        'panelSha256': expected_panel,
    }.items():
        if type(report.get(key)) is not type(expected) or report[key] != expected:
            raise ValueError('Missing combined browser proof: '+key)
    if type(report.get('manualPortFallbackUsed')) is not bool:
        raise ValueError('Missing explicit automatic/manual port path')
    stages = report.get('stages', [])
    if ([s.get('stage') for s in stages] != ['running', 'stopped', 'restarted', 'stopped']
        or any(s.get('errors') != [] for s in stages)
        or 'Private service sync' not in stages[0].get('text', '')):
        raise ValueError('Missing visible browser lifecycle stages')
    if any(s.get('manualPortFallbackUsed') is not report['manualPortFallbackUsed'] for s in stages):
        raise ValueError('Inconsistent browser port path evidence')
    observations = report.get('actualPackagedProcessObservations', [])
    if (len(observations) != 2
        or [o.get('stage') for o in observations] != ['running', 'restarted']
        or any(not o.get('pids') or any(type(p) is not int or p <= 0 for p in o['pids']) for o in observations)
        or observations[0]['pids'][0] == observations[1]['pids'][0]):
        raise ValueError('Missing real browser-controlled process transitions')
    renderers = report.get('sandboxedRendererPids', [])
    if not renderers or any(len(p.get('ancestryToBrowser', [])) < 2
                           or p['ancestryToBrowser'][0] != p.get('pid')
                           or p.get('seccomp') != 2 or p.get('noNewPrivs') != 1 for p in renderers):
        raise ValueError('Missing sandboxed renderer ancestry')
    posts = [c for c in report.get('calls', []) if c.get('httpMethod') == 'POST']
    expected_routes = {'check/start': 1, 'check/scan_port': 1, 'check/scan_api_key': 1,
                       'check/scan_basic_auth': 1, 'reload-config': 1, 'start': 1, 'stop': 2}
    controls = [c for c in posts if c.get('path') != '/']
    probes = [c['status'] for c in posts if c.get('path') == '/']
    # The published checkIfUp() explicitly polls POST / through 425 Too Early.
    # Require its final successful probe; failed controls and unknown routes
    # remain failures rather than treating arbitrary HTTP errors as readiness.
    if (not 1 <= len(probes) <= 300 or probes[-1] != 200
        or any(status != 425 for status in probes[:-1])
        or any(c.get('path') not in {'/__decky-watchdog/'+route for route in expected_routes}
               or c.get('status') not in (200, 204) for c in controls)
        or {route: sum(c.get('path') == '/__decky-watchdog/'+route for c in posts)
            for route in expected_routes} != expected_routes):
        raise ValueError('Missing actual browser setup/control RPC routes')
    if set(report.get('screenshots', {})) != {'running1', 'stopped2', 'restarted3', 'stopped4'}:
        raise ValueError('Missing browser lifecycle screenshots')


def guest_report(console, browser=False):
    marker = 'FRAMEY_SYSTEMD_PROBE_CHUNK_JSON=' if browser else 'FRAMEY_SYSTEMD_PROBE_JSON='
    lines = [line.partition(marker)[2] for line in console.splitlines() if marker in line]
    if not browser:
        if len(lines) != 1:
            raise RuntimeError('Missing/ambiguous guest result')
        return json.loads(lines[0])
    # Screenshot-bearing JSON exceeds journald's line limit. Each guest record
    # carries at most 4096 characters and must form one complete ordered set.
    if not 1 <= len(lines) <= 4096:
        raise RuntimeError('Missing/oversized chunked guest result')
    chunks = [json.loads(line) for line in lines]
    for index, chunk in enumerate(chunks):
        if (set(chunk) != {'index', 'total', 'data'} or chunk['index'] != index
            or chunk['total'] != len(chunks) or not isinstance(chunk['data'], str)
            or not 1 <= len(chunk['data']) <= 4096):
            raise RuntimeError('Incomplete/ambiguous chunked guest result')
    return json.loads(''.join(chunk['data'] for chunk in chunks))


def verify_http_parent(report):
    for name in ('success', 'syntheticInput', 'syntheticCef', 'syntheticStoreReceipt',
                 'productionParentUnchanged', 'productionPanelUnchanged',
                 'actualDeckyUserService', 'actualDeckyDiscovery', 'ownedTargetClosed'):
        if report.get(name) is not True:
            raise ValueError('Missing production browser parent proof: '+name)
    for name in ('realSteamCef', 'realFrameContacted', 'managedInstallVerified',
                 'installerEnabled', 'bootstrapStateInjected', 'browserSandboxDisabled'):
        if report.get(name) is not False:
            raise ValueError('Invalid production parent scope: '+name)
    harness = report.get('childHarness', {})
    if (harness.get('installed') is not True or harness.get('universalAccessGranted') is not False
            or harness.get('mode') not in ('owned-iframe-target', 'owned-frame-isolated-world')):
        raise ValueError('Missing scoped child DOM harness')
    stages = report.get('stages', [])
    if ([v.get('stage') for v in stages] != ['running', 'stopped', 'restarted', 'stopped']
            or any(v.get('errors') != [] for v in stages)
            or any(not all(label in stages[index].get('text', '')
                           for label in ('Private service sync', 'owned-peer'))
                   for index in (0, 2))
            or any(line.lstrip().startswith('Error:')
                   for stage in stages for line in stage.get('text', '').splitlines())):
        raise ValueError('Missing production parent browser lifecycle')
    if (type(report.get('manualPortFallbackUsed')) is not bool or
            any(v.get('manualPortFallbackUsed') is not report['manualPortFallbackUsed'] for v in stages)):
        raise ValueError('Missing production parent port path')
    observations = report.get('actualPackagedProcessObservations', [])
    if (len(observations) != 2 or [v.get('stage') for v in observations] != ['running', 'restarted']
            or any(not v.get('pids') or any(type(p) is not int or p <= 0 for p in v['pids']) for v in observations)
            or observations[0]['pids'][0] == observations[1]['pids'][0]):
        raise ValueError('Missing production parent signed PID transitions')
    renderers = report.get('sandboxedRendererPids', [])
    if not renderers or any(v.get('seccomp') != 2 or v.get('noNewPrivs') != 1
                           or len(v.get('ancestryToBrowser', [])) < 2 for v in renderers):
        raise ValueError('Missing production parent renderer sandbox')
    requests = report.get('httpRequests', [])
    if (not requests or any(v.get('httpStatus') != 200 for v in requests)
            or not {'get_settings_json', 'set_setting', 'framey_http_fetch'} <= {v.get('method') for v in requests}):
        raise ValueError('Missing production parent HTTP calls')
    if any(type(v.get(key)) not in (int, float) or not 0 <= v[key] < 600
           for v in requests for key in ('startedAfterSeconds', 'elapsedSeconds')):
        raise ValueError('Missing bounded production parent request timings')
    if any(v.get('backendStatus') not in (200, 204, 425, 502)
           for v in requests if v.get('method') == 'framey_http_fetch'):
        raise ValueError('Unexpected production parent backend response')
    controls = {v.get('path') for v in requests if v.get('method') == 'framey_http_fetch'}
    if not {'/__decky-watchdog/start', '/__decky-watchdog/stop', '/__decky-watchdog/state'} <= controls:
        raise ValueError('Missing production parent HTTP service controls')
    if not {'/headset', '/framey/panel/64', '/framey-runtime/host.js'} <= set(report.get('requestedAssets', [])):
        raise ValueError('Missing production parent assets')
    if (report.get('parentErrors') != [] or set(report.get('screenshots', {})) !=
            {'running1', 'stopped2', 'restarted3', 'stopped4'}):
        raise ValueError('Missing production parent captures or unexpected errors')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs-tar", type=Path, required=True)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New evidence directory; existing directories are refused",
    )
    parser.add_argument(
        "--preparation",
        type=Path,
        help="Offline preparation.json for locally generated exact-commit bundles",
    )
    parser.add_argument('--candidate-helper', type=Path)
    parser.add_argument('--candidate-build-report', type=Path)
    parser.add_argument('--archive', type=Path, help='Optional pinned official Syncthing plugin ZIP')
    parser.add_argument('--loader', type=Path, help='Optional pinned native Decky 3.3.0 loader')
    parser.add_argument('--browser-setup', action='store_true',
                        help='AMD64 only: actual browser controls with Decky and the signed package')
    parser.add_argument('--http-gateway', action='store_true',
                        help='With browser setup: production local HTTP/panel dispatch through fixture CEF')
    parser.add_argument('--http-browser-parent', action='store_true',
                        help='With HTTP gateway: unchanged production parent and actual Decky user service')
    parser.add_argument('--keep-boot-artifacts', action='store_true',
                        help='Debugging only: keep the regenerated vmlinuz/initrd.gz in --output')
    args = parser.parse_args()
    if args.http_gateway and not args.browser_setup:
        parser.error('HTTP gateway probe requires --browser-setup')
    if args.http_browser_parent and not args.http_gateway:
        parser.error('HTTP browser parent requires --http-gateway')
    arch = platform.machine()
    if args.http_browser_parent and arch != "x86_64":
        parser.error("Production browser parent probe currently requires AMD64")
    if platform.system() != "Linux" or arch not in ARCHES:
        parser.error("This package probe requires native AMD64 or ARM64 Linux")
    if args.browser_setup and (arch != 'x86_64' or not args.candidate_helper):
        parser.error('Combined browser setup currently requires AMD64 and a source-bound candidate')
    emulator, console_device, machine = ARCHES[arch]
    if shutil.which(emulator) is None:
        parser.error(emulator + " is required")
    if args.rootfs_tar.stat().st_size > 2 * 1024**3:
        parser.error("Guest rootfs exceeds 2 GiB")
    if args.key.stat().st_size > 64 * 1024 or sha(args.key) != KEY_SHA256:
        parser.error("Unexpected Flathub public key")
    payloads = {"flathub-key.gpg": args.key.read_bytes()}
    bundles = BUNDLES
    preparation = None
    if args.preparation:
        if args.preparation.stat().st_size > 256 * 1024:
            parser.error("Oversized preparation report")
        preparation = json.loads(args.preparation.read_text())
        try:
            bundles = prepared_bundles(preparation, arch)
        except ValueError as error:
            parser.error(str(error))
    elif arch != "x86_64":
        parser.error("ARM64 requires an exact signed offline --preparation report")
    candidate = None
    if args.candidate_helper or args.candidate_build_report:
        if not (args.candidate_helper and args.candidate_build_report and args.preparation):
            parser.error('Candidate integration requires helper, build report and preparation')
        extra, candidate = candidate_payloads(
            args.candidate_helper, args.candidate_build_report, args.archive, args.loader, arch,
        )
        payloads.update(extra)
    elif args.archive or args.loader:
        parser.error('Candidate archive/loader require --candidate-helper')
    browser_inputs = None
    if args.browser_setup:
        browser_extra, browser_inputs = browser_payloads(payloads['official.zip'])
        payloads.update(browser_extra)
        result_codec = module('guest_result', ROOT/'tests/decky-runtime/guest_result.py')
        payloads['guest_result.py'] = (ROOT/'tests/decky-runtime/guest_result.py').read_bytes()
    http_gateway = None
    if args.http_gateway:
        http_payloads, http_gateway = http_gateway_payloads(args.http_browser_parent)
        payloads.update(http_payloads)
    budgets = ({'installSeconds': 300, 'userSeconds': 1440, 'unitSeconds': 1500, 'hostSeconds': 1560}
               if args.browser_setup else BUDGETS[arch])
    manifest = {"bundles": bundles, "bundleChunks": {}, "timeouts": budgets,
                "browserSetupRequested": args.browser_setup}
    for kind, expected in bundles.items():
        path = args.bundles / (kind + ".flatpak")
        if path.stat().st_size != expected["bytes"] or sha(path) != expected["sha256"]:
            parser.error("Unexpected pinned " + kind + " bundle")
        chunks = []
        with path.open("rb") as source:
            while data := source.read(64 * 1024**2):
                name = f"{kind}.part-{len(chunks):03}"
                payloads[name] = data
                chunks.append(
                    {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
                )
        manifest["bundleChunks"][kind] = chunks
    payloads["flatpak-inputs.json"] = json.dumps(manifest).encode()
    assert sum(map(len, payloads.values())) < 480 * 1024**2
    args.output.mkdir(parents=True, exist_ok=False)
    packer_path = ROOT / "scripts/framey-test-syncthing-service.py"
    root_probe = ROOT / "tests/decky-runtime/syncthing_flatpak_package_root.py"
    user_probe = ROOT / "tests/decky-runtime/syncthing_flatpak_package.py"
    source_paths = [Path(__file__).resolve(), packer_path, root_probe, user_probe]
    if candidate:
        source_paths.extend(ROOT / path for path in [
            'tests/decky-runtime/syncthing_service.py', 'tests/decky-runtime/syncthing_migration.py',
            'scripts/build-framey-syncthing.py',
            'scripts/framey-test-decky-runtime.py', 'scripts/framey-test-syncthing-runtime.py',
            'ui/vendor/syncthing-0.2.7/main.py', 'ui/vendor/syncthing-0.2.7/source.tar.gz',
            'ui/vendor/syncthing-0.2.7/owned_unit.rs', 'ui/vendor/syncthing-0.2.7/watchdog.patch',
        ])
    if args.browser_setup:
        source_paths.extend(ROOT / path for path in [
            'tests/decky-runtime/guest_result.py',
            'scripts/framey-test-syncthing-browser.py', 'tests/decky-runtime/syncthing_browser.py',
            'tests/decky-runtime/Containerfile.flatpak-vm', 'ui/framey_panel.py', 'ui/framey-host.js',
            'ui/frame_decky.py', 'ui/frame_decky_store.py', 'ui/framey_compatibility.py',
            'ui/frame_steam.py', 'ui/vendor/react-18.3.1.min.js', 'ui/vendor/react-dom-18.3.1.min.js',
            'ui/vendor/syncthing-0.2.7/frontend.patch',
        ])
    if args.http_gateway:
        source_paths.extend(ROOT/name for name in http_gateway['sourceSha256']
                            if ROOT/name not in source_paths)
        source_paths.append(ROOT/'tests/decky-runtime/syncthing_http.py')
        if args.http_browser_parent:
            source_paths.append(ROOT/'tests/decky-runtime/syncthing_http_parent.py')
    fingerprints = {str(path.relative_to(ROOT)): sha(path) for path in source_paths}
    spec = importlib.util.spec_from_file_location("service_vm", packer_path)
    packer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packer)
    rootfs_sha = sha(args.rootfs_tar)
    # Every run regenerates multi-hundred-MB VM boot images in its evidence folder.
    # Whatever ends the run, result.json is written, any owned QEMU is reaped and
    # then the images are removed; inputs.json keeps their digests. SIGTERM (e.g.
    # a job timeout) becomes SystemExit, deferred while QEMU is being registered.
    termination = Termination()
    previous_sigterm = signal.signal(signal.SIGTERM, termination)
    result = {"success": False, "inputs": None}
    process = None
    try:
        try:
            kernel = packer.pack(
                args.rootfs_tar,
                args.output / "initrd.gz",
                payloads,
                marker=MARKER,
                bootstrap=root_probe.read_bytes(),
                user_probe=user_probe.read_bytes(),
                normal_root=True,
                timeout=budgets['unitSeconds'],
                root_size_mib=2048 if args.browser_setup else 1024,
                browser=args.browser_setup,
            )
            (args.output / "vmlinuz").write_bytes(kernel)
            inputs = {
                "rootfsTarSha256": rootfs_sha,
                "rootfsTarBytes": args.rootfs_tar.stat().st_size,
                "kernelSha256": hashlib.sha256(kernel).hexdigest(),
                "initrdSha256": sha(args.output / "initrd.gz"),
                "bootArtifactsRetained": args.keep_boot_artifacts,
                "sourceSha256": fingerprints,
                "bundles": bundles,
                "architecture": arch,
                "preparationSha256": sha(args.preparation) if args.preparation else None,
                "keySha256": KEY_SHA256,
                "memoryMiB": 8192 if args.browser_setup else 6144,
                "timeoutSeconds": budgets['hostSeconds'],
                "guestTimeouts": budgets,
                "networkDevice": False,
                "hostBusExposed": False,
                "realFrameContacted": False,
                "candidate": candidate,
                "browserSetup": browser_inputs,
                "httpGateway": http_gateway,
                "httpBrowserParentRequested": args.http_browser_parent,
                "resultTransport": ({"kind": "virtio-serial", "port": result_codec.PORT,
                                     "maximumPayloadBytes": result_codec.MAX_PAYLOAD}
                                    if args.browser_setup else None),
            }
            result["inputs"] = inputs
            (args.output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
            command = [
                emulator,
                *machine,
                "-accel",
                "tcg,thread=multi",
                "-cpu",
                "max",
                "-smp",
                "2",
                "-m",
                str(inputs['memoryMiB']),
                "-nodefaults",
                "-nographic",
                "-serial",
                "stdio",
                "-monitor",
                "none",
                "-nic",
                "none",
                "-no-reboot",
                "-kernel",
                str(args.output / "vmlinuz"),
                "-initrd",
                str(args.output / "initrd.gz"),
                "-append",
                f"console={console_device} rdinit=/init panic=-1 systemd.show_status=false",
            ]
            console = args.output / "console.log"
            packet_path = args.output / 'guest-result.packet'
            if args.browser_setup:
                command += ['-chardev', 'file,id=framey_result,path='+str(packet_path).replace(',', ',,'),
                            '-device', 'virtio-serial-pci,id=framey_result_bus',
                            '-device', 'virtserialport,bus=framey_result_bus.0,chardev=framey_result,name='+result_codec.PORT]
            with console.open("w") as log:
                with termination.deferred():
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                code = process.wait(timeout=budgets['hostSeconds'])
            if code != 0:
                raise RuntimeError('Nonzero QEMU exit')
            if args.browser_setup:
                if not packet_path.is_file() or not 0 < packet_path.stat().st_size <= result_codec.MAX_PAYLOAD+256:
                    raise RuntimeError('Missing/oversized dedicated guest result packet')
                packet = packet_path.read_bytes()
                guest = result_codec.decode(packet)
                result['guestResultPacket'] = dict(bytes=len(packet), sha256=hashlib.sha256(packet).hexdigest())
            else:
                guest = guest_report(console.read_text())
            result["guest"] = guest
            package = guest.get("flatpak", {})
            if guest.get('success') is not True:
                raise RuntimeError('Guest package probe failed; inspect retained partial result and console')
            if package.get("architecture") != arch:
                raise RuntimeError("Guest architecture does not match the native host")
            if guest.get("success") is not True or any(
                package.get(key) is not True for key in REQUIRED
            ):
                raise RuntimeError(
                    "Incomplete package probe; inspect retained guest result and console"
                )
            if (
                package.get("forcedTermination") is not False
                or package.get("apiKeyErrorStatus") != 403
            ):
                raise RuntimeError("Package cleanup/authentication gate failed")
            if candidate:
                verify_migration(package.get('candidateMigration', {}), arch, bundles)
                verify_candidate(package.get('candidateService', {}), arch, bundles,
                                 packer.REQUIRED_SERVICE_RESULTS)
                if package.get('uninstallPreservedCandidateData') is not True:
                    raise RuntimeError('Candidate certificate/data preserving uninstall proof is missing')
                if package.get('uninstallPreservedMigrationData') is not True:
                    raise RuntimeError('Legacy migration data preserving uninstall proof is missing')
            if args.browser_setup:
                browser_result = package.get('candidateService', {}).get('browserSetup', {})
                verify_browser(browser_result, browser_inputs['panelSha256'])
                import base64
                for name, encoded in browser_result['screenshots'].items():
                    if name not in ('running1', 'stopped2', 'restarted3', 'stopped4'):
                        raise RuntimeError('Unexpected browser screenshot stage')
                    data = base64.b64decode(encoded, validate=True)
                    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > 2*1024**2:
                        raise RuntimeError('Invalid browser screenshot')
                    (args.output / ('browser-'+name+'.png')).write_bytes(data)
            if args.http_gateway:
                gateway = package.get('candidateService', {}).get('httpGateway', {})
                required = ('success', 'actualDeckyRpc', 'authenticatedSyncthingRest',
                            'serviceStartStopVerified', 'stoppedStateBeforeAndAfter',
                            'productionHttpHandler', 'productionPanelDispatcher',
                            'productionMethodScript', 'productionLocalSshWrapper',
                            'ownedBrowserReaped', 'httpServerStopped', 'ownedReceiptRemoved')
                if any(gateway.get(key) is not True for key in required):
                    raise RuntimeError('Production HTTP/panel gateway proof missing')
                if (gateway.get('realFrameContacted') is not False
                    or gateway.get('realSteamCef') is not False
                    or gateway.get('syntheticCef') is not True
                    or gateway.get('syntheticStoreReceipt') is not True
                    or gateway.get('rejectedRequests') != dict(missingUiKey=403, staleReceipt=400,
                        wrongPlugin=400, modernHttpCall=400, missingHttpShim=400)):
                    raise RuntimeError('HTTP gateway scope/refusal proof missing')
                if args.http_browser_parent:
                    parent = gateway.get('browserParent', {})
                    verify_http_parent(parent)
                    if (package['candidateService'].get('actualDeckyUserService') is not True
                            or package['candidateService'].get('ownedDeckyServiceRemoved') is not True):
                        raise RuntimeError('Actual Decky user service cleanup proof missing')
                    for name, encoded in parent['screenshots'].items():
                        import base64
                        data = base64.b64decode(encoded, validate=True)
                        if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > 2*1024**2:
                            raise RuntimeError('Invalid HTTP parent screenshot')
                        (args.output/('http-parent-'+name+'.png')).write_bytes(data)
            if any(
                sha(path) != fingerprints[str(path.relative_to(ROOT))]
                for path in source_paths
            ):
                raise RuntimeError("Probe sources changed during execution")
            if args.preparation and sha(args.preparation) != inputs["preparationSha256"]:
                raise RuntimeError("Preparation changed during execution")
            if sha(args.rootfs_tar) != rootfs_sha:
                raise RuntimeError("Guest rootfs changed during execution")
            result["success"] = True
        except BaseException as error:
            result["error"] = str(error)
            raise
        finally:
            try:
                if process is not None:
                    reap(process)
                    result["ownedQemuReaped"] = process.poll() is not None
            finally:
                (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        if not args.keep_boot_artifacts:
            packer.remove_boot_artifacts(args.output)


if __name__ == "__main__":
    main()
