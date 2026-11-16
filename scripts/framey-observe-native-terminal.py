#!/usr/bin/env python3
"""Branch-only diagnostic around exact-main Terminal in an owned native ARM VM.

This never qualifies a release or changes the published fixture. The host must
be Linux aarch64; tracing occurs only inside the disposable networkless guest.
"""
import argparse
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import tarfile
import time

REPO = Path(__file__).resolve().parents[1]
SOURCE = 'dd2223e799bb3db8256285e353d5a0ad2f4bd014'
LOADER_SHA = '8ef5dcf36cbbbb6e97201a6baed5d79c4cc44ec27789fc9af1c5b6ae8f0b25b6'
PAYLOADS = REPO / 'tests/decky-runtime/unix_diagnostic'
PINS = {
    'observer.py': '14c6d0bc218b09e187995a1973efd497902fe125f9afebcbc8104a64589afcb5',
    'base_observer.py': 'd0610c3eb26b5af7a5a2d0f9f020f8b7829e6b816b5261dcaaf3ba1419f53053',
    'guest.py': '1e5e9ff9d348a649a5704c3ad26f9fd022bb9cc10c2c0308e518bdefee7e6512',
}
SOURCES = [
    'ui', 'tests/decky-runtime', 'tests/fixtures/framey-terminal-python314-arm',
    'tests/fixtures/framey-official/65.zip', 'tests/framey_official.py',
    'scripts/framey-test-decky-runtime.py', 'scripts/framey-test-syncthing-service.py',
    '.github/workflows/decky-runtime.yml',
]
PHASES = ['bootstrap-entry', 'imports-ready', 'source-verified', 'user-manager-started',
          'observer-started', 'probe-returned', 'capture-finished', 'user-manager-stop-returned']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def host_guard():
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise ValueError('This diagnostic requires native Linux aarch64; no cross-architecture fallback')


def phase_report(text):
    rows = [line.split('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=', 1)[1].strip()
            for line in text.splitlines() if 'FRAMEY_PRIVATE_ARM_NATIVE_PHASE=' in line]
    valid = (len(rows) <= len(PHASES) and all(row in PHASES for row in rows)
             and [PHASES.index(row) for row in rows] == sorted({PHASES.index(row) for row in rows}))
    return {'observations': rows, 'valid': valid, 'complete': valid and rows == PHASES}


def qemu_command(emulator, kernel, initrd, packet, port):
    return [emulator, '-machine', 'virt', '-accel', 'tcg,thread=multi', '-cpu', 'max',
            '-smp', '2', '-m', '6144', '-nodefaults', '-nographic', '-serial', 'stdio',
            '-monitor', 'none', '-no-reboot', '-nic', 'none', '-kernel', str(kernel),
            '-initrd', str(initrd), '-append', 'console=ttyAMA0 rdinit=/init panic=-1 quiet',
            '-chardev', 'file,id=framey_result,path=' + str(packet),
            '-device', 'virtio-serial-pci,id=framey_result_bus',
            '-device', 'virtserialport,bus=framey_result_bus.0,chardev=framey_result,name=' + port]


def cleanup_qemu(process, result):
    """Bounded cleanup of this Popen's unreaped process group; never mask failure."""
    result['ownedQemuReaped'] = process is None
    result['qemuCleanupErrors'] = []
    if process is None:
        return
    for sig, budget in ((signal.SIGTERM, 8), (signal.SIGKILL, 5)):
        try:
            if process.poll() is not None:
                break
            result['forcedQemuTermination'] = True
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass  # The held child may have exited between poll and signal.
        except BaseException as error:
            result['qemuCleanupErrors'].append(type(error).__name__)
        try:
            process.wait(timeout=budget)
            break
        except BaseException as error:
            result['qemuCleanupErrors'].append(type(error).__name__)
    try:
        result['ownedQemuReaped'] = process.poll() is not None
    except BaseException as error:
        result['qemuCleanupErrors'].append(type(error).__name__)


def remove_boot_files(paths, result):
    result['bootCleanupErrors'] = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except BaseException as error:
            result['bootCleanupErrors'].append(type(error).__name__)
    result['ownedBootArtifactsRemoved'] = all(not path.exists() for path in paths)


def observation_passed(result):
    """Execution transport only: capture and release qualification stay separate."""
    return (result.get('qemuReturnCode') == 0 and not result['forcedQemuTermination']
            and 'hostErrorType' not in result and result.get('guest', {}).get('success') is True
            and result['staticPhases']['complete'] and result['ownedQemuReaped']
            and result['ownedBootArtifactsRemoved'] and not result['qemuCleanupErrors']
            and not result['bootCleanupErrors'] and result['archivedRootfsUnchanged'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs-tar', type=Path, required=True)
    parser.add_argument('--loader', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    host_guard()
    if args.output.exists():
        raise ValueError('Diagnostic output directory must not already exist')
    emulator = shutil.which('qemu-system-aarch64')
    if emulator is None:
        raise ValueError('Missing matching QEMU emulator')
    payload = {name: (PAYLOADS / name).read_bytes() for name in PINS}
    if any(hashlib.sha256(payload[name]).hexdigest() != digest for name, digest in PINS.items()):
        raise ValueError('Reviewed diagnostic payload changed')
    loader = args.loader.read_bytes()
    if (hashlib.sha256(loader).hexdigest() != LOADER_SHA or loader[:4] != b'\x7fELF'
            or int.from_bytes(loader[18:20], 'little') != 183):
        raise ValueError('Pinned ARM loader mismatch')
    source_tar = subprocess.check_output(['git', 'archive', '--format=tar', SOURCE, *SOURCES], cwd=REPO)
    sources, source_bytes = {}, {}
    with tarfile.open(fileobj=io.BytesIO(source_tar)) as archive:
        for item in archive:
            if not (item.isdir() or item.isfile()):
                raise ValueError('Unsupported source archive member')
            if not item.isfile():
                continue
            if item.name in sources or item.size > 32 * 1024 * 1024:
                raise ValueError('Duplicate or oversized source member')
            content = archive.extractfile(item).read()
            sources[item.name] = hashlib.sha256(content).hexdigest()
            source_bytes[item.name] = content
    output = args.output
    output.mkdir(parents=True)
    (output / 'source.tar').write_bytes(source_tar)
    (output / 'runner.py').write_bytes(Path(__file__).read_bytes())
    (output / 'workflow.yml').write_bytes((REPO / '.github/workflows/decky-runtime.yml').read_bytes())
    for name, content in payload.items():
        (output / name).write_bytes(content)
    packer_path, codec_path = output / 'exact-main-vm-packer.py', output / 'guest_result.py'
    packer_path.write_bytes(source_bytes['scripts/framey-test-syncthing-service.py'])
    codec_path.write_bytes(source_bytes['tests/decky-runtime/guest_result.py'])
    packer = module('diagnostic_exact_main_packer', packer_path)
    codec = module('diagnostic_exact_main_codec', codec_path)
    rootfs_digest = sha(args.rootfs_tar)
    inputs = dict(sourceRevision=SOURCE,
                  sourceTree=subprocess.check_output(['git', 'rev-parse', SOURCE + '^{tree}'], cwd=REPO).decode().strip(),
                  diagnosticRevision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO).decode().strip(),
                  runnerSha256=sha(Path(__file__)), workflowSha256=sha(output / 'workflow.yml'),
                  sourceSha256=sources, sourceArchiveSha256=hashlib.sha256(source_tar).hexdigest(),
                  rootfsSha256=rootfs_digest, loaderSha256=LOADER_SHA, architecture='aarch64',
                  observerSha256=PINS['observer.py'], scopeHelperSha256=PINS['base_observer.py'],
                  bootstrapSha256=PINS['guest.py'], rpcDeadlineSeconds=8,
                  publishedNativeOuterDeadlineSeconds=120, originalDefaultDiscoveryDeadlineSeconds=20,
                  serviceDeadlineSeconds=180, qemuDeadlineSeconds=240, memoryMiB=6144, cpus=2,
                  networkDevice=False, hostDevices=False, hostMounts=False, browserRequested=False,
                  observerEnabledDiagnostic=True, qualificationPassed=False)
    (output / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    initrd, kernel_path, packet = output / 'initrd.gz', output / 'vmlinuz', output / 'guest-result.packet'
    started = time.monotonic()
    process = None
    result = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(), success=False,
                  inputs=inputs, forcedQemuTermination=False, qualificationPassed=False,
                  realFrameContacted=False, historicalCauseOrRepairEstablished=False)
    try:
        kernel = packer.pack(args.rootfs_tar, initrd,
                             {'PluginLoader': loader, 'source.tar': source_tar,
                              'inputs.json': json.dumps(inputs).encode(), 'observer.py': payload['observer.py'],
                              'base_observer.py': payload['base_observer.py'], 'guest_result.py': codec_path.read_bytes()},
                             marker=b'Framey private trace capability v1\n', bootstrap=payload['guest.py'],
                             user_probe=b'# no separate probe\n', normal_root=True,
                             timeout=180, root_size_mib=3072, browser=True)
        kernel_path.write_bytes(kernel)
        result['boot'] = dict(kernelSha256=sha(kernel_path), initrdSha256=sha(initrd))
        command = qemu_command(emulator, kernel_path, initrd, packet, codec.PORT)
        with (output / 'console.log').open('wb') as stream:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            result['qemuPid'] = process.pid
            result['qemuReturnCode'] = process.wait(timeout=240)
        result['guest'] = codec.decode(packet.read_bytes())
        result['packetSha256'] = sha(packet)
    except BaseException as error:
        result.update(hostErrorType=type(error).__name__, hostError=str(error)[:1000])
    finally:
        try:
            cleanup_qemu(process, result)
        finally:
            remove_boot_files((initrd, kernel_path), result)
        console = output / 'console.log'
        phases = phase_report(console.read_text(errors='replace') if console.exists() else '')
        result['staticPhases'] = phases
        result['elapsedSeconds'] = time.monotonic() - started
        result['archivedRootfsUnchanged'] = sha(args.rootfs_tar) == rootfs_digest
        result['success'] = observation_passed(result)
        result['proofSha256'] = {str(path): sha(path) for path in output.rglob('*')
                                 if path.is_file() and path.name not in ('assessment.json', 'runner.log')}
        result['proofSha256'][str(args.rootfs_tar)] = rootfs_digest
        result['proofSha256'][str(args.loader)] = LOADER_SHA
        (output / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'assessment': str(output / 'assessment.json'), 'success': result['success'],
                      'qualificationPassed': False}), flush=True)
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
