#!/usr/bin/env python3
"""Run exact signed Syncthing packages in an owned, networkless native VM.

Inputs are a disposable Debian rootfs export with systemd, Flatpak, OSTree GI
and a kernel, plus locally generated bundles of the pinned published commits.
No host filesystem, bus, disk, device or network NIC is exposed to the guest.
An optional source-bound candidate helper also tests actual Decky service RPC.
The managed installer and real Frame remain outside this disposable VM.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess

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
    if report.get('pendingSetupRoutes') != {'GET state': 500, 'POST start': 204, 'POST stop': 204}:
        raise ValueError('Missing pending migration refusal/no-op proof')
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
    wizard = service.get('wizardConfigDiscovery', {})
    if any(wizard.get(key) is not True for key in (
        'defaultPackageConfig', 'remainedUnconfiguredDuringScan',
        'discoveredDefaultPort', 'discoveredDefaultApiKey', 'scannedBasicAuth',
        'persistedThroughDeckyRpc', 'authenticatedRestWithDiscoveredKey',
        'setupCommittedAndReloaded', 'ownedSetupServiceStopped',
    )):
        raise ValueError('Missing actual-package setup discovery proof')
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
    args = parser.parse_args()
    arch = platform.machine()
    if platform.system() != "Linux" or arch not in ARCHES:
        parser.error("This package probe requires native AMD64 or ARM64 Linux")
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
    budgets = BUDGETS[arch]
    manifest = {"bundles": bundles, "bundleChunks": {}, "timeouts": budgets}
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
    fingerprints = {str(path.relative_to(ROOT)): sha(path) for path in source_paths}
    spec = importlib.util.spec_from_file_location("service_vm", packer_path)
    packer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packer)
    rootfs_sha = sha(args.rootfs_tar)
    kernel = packer.pack(
        args.rootfs_tar,
        args.output / "initrd.gz",
        payloads,
        marker=MARKER,
        bootstrap=root_probe.read_bytes(),
        user_probe=user_probe.read_bytes(),
        normal_root=True,
        timeout=budgets['unitSeconds'],
    )
    (args.output / "vmlinuz").write_bytes(kernel)
    inputs = {
        "rootfsTarSha256": rootfs_sha,
        "rootfsTarBytes": args.rootfs_tar.stat().st_size,
        "kernelSha256": hashlib.sha256(kernel).hexdigest(),
        "initrdSha256": sha(args.output / "initrd.gz"),
        "sourceSha256": fingerprints,
        "bundles": bundles,
        "architecture": arch,
        "preparationSha256": sha(args.preparation) if args.preparation else None,
        "keySha256": KEY_SHA256,
        "memoryMiB": 6144,
        "timeoutSeconds": budgets['hostSeconds'],
        "guestTimeouts": budgets,
        "networkDevice": False,
        "hostBusExposed": False,
        "realFrameContacted": False,
        "candidate": candidate,
    }
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
        "6144",
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
    result = {"success": False, "inputs": inputs}
    try:
        with console.open("w") as log:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=budgets['hostSeconds'])
            finally:
                reap(process)
                result["ownedQemuReaped"] = process.poll() is not None
        lines = [
            line.partition("FRAMEY_SYSTEMD_PROBE_JSON=")[2]
            for line in console.read_text().splitlines()
            if "FRAMEY_SYSTEMD_PROBE_JSON=" in line
        ]
        if code != 0 or len(lines) != 1:
            raise RuntimeError("Missing/ambiguous guest result or nonzero QEMU exit")
        guest = json.loads(lines[0])
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
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
