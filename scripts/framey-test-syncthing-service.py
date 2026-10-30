#!/usr/bin/env python3
"""Exercise candidate service control in an owned, networkless systemd VM.

QEMU uses TCG with no host devices, disks, home, session bus or network NIC.
Only published digest-pinned plugin/Decky/Syncthing inputs enter the guest.
The Flatpak launcher is a fixture shim; real Flatpak packaging remains unverified.
"""

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
MARKER = b'Frame Control service VM v1\n'
ARCHES = {
    'x86_64': ('amd64', 'qemu-system-x86_64', 'ttyS0', []),
    'aarch64': ('arm64', 'qemu-system-aarch64', 'ttyAMA0', ['-machine', 'virt']),
}
REQUIRED_SERVICE_RESULTS = (
    'systemdManagerActual',
    'ownedUnitLoadedByActualSystemd',
    'realSyncthingManagedPid',
    'realDeckyRpcRest',
    'managedServiceTwoWaySync',
    'actualStopJobReapedRuntime',
    'legacyRunningUnitPreserved',
    'retainedCertificateAndMarker',
    'actualEnableDisableLinks',
    'ownedTransitionRemovedOnlyCandidateUnit',
    'actualExternalUserServiceControl',
    'retainedSyncAcrossServiceTransition',
    'ownedCleanup',
    'dropInOverridePreserved',
    'shadowFragmentPreserved',
    'pendingReloadRefused',
    'loadedAliasPreserved',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def pack(archive_path, output, payloads):
    """Write guest-only newc bytes directly; never extract/chown host files."""
    unit = (
        b'[Unit]\nDescription=Private Framey service probe\nAfter=dbus.service\nRequires=dbus.service\n'
        b'[Service]\nType=oneshot\nExecStart=/usr/bin/python3 /framey-root.py\nTimeoutStartSec=300\n'
        b'StandardOutput=journal+console\nStandardError=journal+console\n'
        b'[Install]\nWantedBy=multi-user.target\n'
    )
    init = (
        b'#!/bin/sh\nmount -t devtmpfs devtmpfs /dev\nmount -t proc proc /proc\n'
        b'mount -t sysfs sysfs /sys\nmount -t tmpfs tmpfs /run\nmkdir -p /run/lock\n'
        b'exec /usr/lib/systemd/systemd --log-target=console\n'
    )
    regular, directory, link = stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK
    overlays = {
        'init': (regular | 0o755, init),
        'framey-owned-vm': (regular | 0o444, MARKER),
        'framey-root.py': (
            regular | 0o644,
            (ROOT / 'tests/decky-runtime/syncthing_service_root.py').read_bytes(),
        ),
        'framey-user.py': (
            regular | 0o644,
            (ROOT / 'tests/decky-runtime/syncthing_service.py').read_bytes(),
        ),
        'etc/machine-id': (regular | 0o444, uuid.uuid4().hex.encode() + b'\n'),
        'etc/hostname': (regular | 0o644, b'framey-owned-vm\n'),
        'etc/hosts': (regular | 0o644, b'127.0.0.1 localhost framey-owned-vm\n'),
        'etc/resolv.conf': (regular | 0o644, b''),
        'etc/systemd/system/default.target': (
            link | 0o777,
            b'/usr/lib/systemd/system/multi-user.target',
        ),
        'etc/systemd/system/framey-probe.service': (regular | 0o644, unit),
        'etc/systemd/system/multi-user.target.wants': (directory | 0o755, b''),
        'etc/systemd/system/multi-user.target.wants/framey-probe.service': (
            link | 0o777,
            b'../framey-probe.service',
        ),
        'dev/console': (stat.S_IFCHR | 0o600, b''),
        'input': (directory | 0o755, b''),
    }
    for name, data in payloads.items():
        mode = 0o755 if name in ('watchdog', 'PluginLoader', 'syncthing') else 0o644
        overlays['input/' + name] = (regular | mode, data)
    inode, kernel = 0, None
    with tarfile.open(archive_path) as archive, output.open('wb') as raw, gzip.GzipFile(
        fileobj=raw, mode='wb', mtime=0, compresslevel=1
    ) as target:

        def write(name, mode, data, uid=0, gid=0, major=0, minor=0):
            nonlocal inode
            inode += 1
            name = name.encode() + b'\0'
            fields = [
                inode,
                mode,
                uid,
                gid,
                1,
                0,
                len(data),
                0,
                0,
                major,
                minor,
                len(name),
                0,
            ]
            header = b'070701' + ''.join(f'{value:08x}' for value in fields).encode()
            target.write(header + name)
            target.write(b'\0' * (-(len(header) + len(name)) % 4))
            target.write(data)
            target.write(b'\0' * (-len(data) % 4))

        for member in archive:
            name = member.name.removeprefix('./').rstrip('/')
            if (
                name.startswith('/')
                or '..' in Path(name).parts
                or member.size > 256 * 1024 * 1024
            ):
                raise ValueError('Unexpected guest root filesystem entry')
            if name.startswith('boot/vmlinuz-'):
                if (
                    kernel is not None
                    or not member.isfile()
                    or member.size > 50 * 1024 * 1024
                ):
                    raise ValueError('Unexpected guest kernel')
                kernel = archive.extractfile(member).read()
            if (
                name in overlays
                or name == '.dockerenv'
                or name.startswith(('boot/', 'usr/lib/modules/', 'lib/modules/'))
            ):
                continue
            if member.isfile() or member.islnk():
                mode, data = regular | member.mode, archive.extractfile(member).read()
            elif member.isdir():
                mode, data = directory | member.mode, b''
            elif member.issym():
                mode, data = link | member.mode, member.linkname.encode()
            elif member.ischr():
                mode, data = stat.S_IFCHR | member.mode, b''
            elif member.isblk():
                mode, data = stat.S_IFBLK | member.mode, b''
            else:
                continue
            write(
                name,
                mode,
                data,
                member.uid,
                member.gid,
                member.devmajor or 0,
                member.devminor or 0,
            )
        for name, (mode, data) in overlays.items():
            write(
                name,
                mode,
                data,
                major=5 if name == 'dev/console' else 0,
                minor=1 if name == 'dev/console' else 0,
            )
        write('TRAILER!!!', 0, b'')
    if kernel is None:
        raise ValueError('Guest kernel is absent')
    return kernel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--syncthing-archive', type=Path)
    parser.add_argument('--loader', type=Path)
    parser.add_argument(
        '--image', help='Optional prepared private service-VM image; never removed'
    )
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    arch = platform.machine()
    if platform.system() != 'Linux' or arch not in ARCHES:
        parser.error(
            'Use Linux AMD64 or ARM64 with Docker and the matching QEMU system emulator'
        )
    dist, emulator, console, machine = ARCHES[arch]
    if shutil.which(emulator) is None:
        parser.error(f'{emulator} is required')
    native = module('native_decky', ROOT / 'scripts/framey-test-decky-runtime.py')
    runtime = module(
        'syncthing_runtime', ROOT / 'scripts/framey-test-syncthing-runtime.py'
    )
    loader, loader_sha = native.loader_bytes(args.loader)
    _, archive_sha, binary_sha, elf = runtime.RUNTIMES[arch]
    filename = f'syncthing-linux-{dist}-{runtime.VERSION}.tar.gz'
    packed = (
        args.syncthing_archive.read_bytes()
        if args.syncthing_archive
        else runtime.download(
            f'https://github.com/syncthing/syncthing/releases/download/{runtime.VERSION}/{filename}',
            25 * 1024 * 1024,
        )
    )
    if sha(packed) != archive_sha:
        raise ValueError('Pinned Syncthing archive mismatch')
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as archive:
        member = archive.getmember(filename.removesuffix('.tar.gz') + '/syncthing')
        if not member.isfile() or member.size > 40 * 1024 * 1024:
            raise ValueError('Unexpected Syncthing binary')
        binary = archive.extractfile(member).read()
    helper = args.helper.read_bytes()
    if sha(binary) != binary_sha:
        raise ValueError('Pinned Syncthing binary mismatch')
    for data in (binary, helper):
        if data[:4] != b'\x7fELF' or int.from_bytes(data[18:20], 'little') != elf:
            raise ValueError(
                'Service test executable has the wrong native architecture'
            )
    official = (
        args.archive.read_bytes()
        if args.archive
        else runtime.download(
            'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/'
            + runtime.DIGEST
            + '.zip',
            50 * 1024 * 1024,
        )
    )
    if sha(official) != runtime.DIGEST:
        raise ValueError('Pinned official plugin archive mismatch')
    paths = [
        'scripts/framey-test-syncthing-service.py',
        'tests/decky-runtime/Containerfile.systemd',
        'tests/decky-runtime/syncthing_service.py',
        'tests/decky-runtime/syncthing_service_root.py',
        'scripts/framey-test-syncthing-runtime.py',
        'scripts/framey-test-decky-runtime.py',
        'ui/vendor/syncthing-0.2.7/main.py',
        'ui/vendor/syncthing-0.2.7/watchdog.patch',
        'ui/vendor/syncthing-0.2.7/owned_unit.rs',
    ]
    sources = {path: sha((ROOT / path).read_bytes()) for path in paths}
    image = args.image or 'framey-syncthing-service:' + uuid.uuid4().hex[:12]
    container = 'framey-syncthing-service-export-' + uuid.uuid4().hex[:12]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # A failed rerun must never leave an earlier success at the requested path.
    args.output.unlink(missing_ok=True)
    try:
        if not args.image:
            subprocess.run(
                [
                    'docker',
                    'build',
                    '-q',
                    '-t',
                    image,
                    '--build-arg',
                    'KERNEL_PACKAGE=linux-image-' + dist,
                    '-f',
                    str(ROOT / 'tests/decky-runtime/Containerfile.systemd'),
                    str(ROOT / 'tests/decky-runtime'),
                ],
                check=True,
                timeout=600,
            )
        image_info = json.loads(
            subprocess.check_output(['docker', 'image', 'inspect', image])
        )[0]
        if image_info['Architecture'] != dist:
            raise ValueError('Service VM image has the wrong architecture')
        with tempfile.TemporaryDirectory(
            prefix='framey-syncthing-service-'
        ) as temporary:
            folder = Path(temporary)
            subprocess.run(
                [
                    'docker',
                    'create',
                    '--name',
                    container,
                    '--network',
                    'none',
                    '--read-only',
                    '--cap-drop',
                    'ALL',
                    '--entrypoint',
                    '/bin/true',
                    image,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            with (folder / 'rootfs.tar').open('wb') as output:
                subprocess.run(
                    ['docker', 'export', container],
                    check=True,
                    stdout=output,
                    timeout=120,
                )
            if (folder / 'rootfs.tar').stat().st_size > 2 * 1024 * 1024 * 1024:
                raise ValueError('Guest filesystem exceeds its size limit')
            payloads = {
                'watchdog': helper,
                'PluginLoader': loader,
                'syncthing': binary,
                'official.zip': official,
                'main.py': (ROOT / 'ui/vendor/syncthing-0.2.7/main.py').read_bytes(),
            }
            kernel = pack(folder / 'rootfs.tar', folder / 'initrd.gz', payloads)
            (folder / 'vmlinuz').write_bytes(kernel)
            command = [
                emulator,
                '-accel',
                'tcg,thread=multi',
                '-cpu',
                'max',
                *machine,
                '-smp',
                '2',
                '-m',
                '2048',
                '-nodefaults',
                '-nographic',
                '-serial',
                'stdio',
                '-monitor',
                'none',
                '-nic',
                'none',
                '-no-reboot',
                '-kernel',
                str(folder / 'vmlinuz'),
                '-initrd',
                str(folder / 'initrd.gz'),
                '-append',
                f'console={console} rdinit=/init panic=-1 systemd.show_status=false',
            ]
            with args.output.with_suffix('.console.log').open('w') as log:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    result = process.wait(timeout=360)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=5)
            if result:
                raise RuntimeError(
                    'Service VM exited unsuccessfully; inspect its console log'
                )
            lines = [
                line.partition('FRAMEY_SYSTEMD_PROBE_JSON=')[2]
                for line in args.output.with_suffix('.console.log')
                .read_text()
                .splitlines()
                if 'FRAMEY_SYSTEMD_PROBE_JSON=' in line
            ]
            if len(lines) != 1:
                raise RuntimeError('Service VM result is missing or ambiguous')
            report = json.loads(lines[0])
            if not report.get('success') or report.get('pid1') != 'systemd':
                raise RuntimeError(
                    'Actual service VM probe failed; inspect its console log'
                )
            if report['candidateService']['architecture'] != arch:
                raise RuntimeError('Service guest executed the wrong architecture')
            if (
                report.get('userBusPresent') is not True
                or report.get('transientUnitExecuted') is not True
                or report.get('realFrameContacted') is not False
                or report.get('hostBusExposed') is not False
            ):
                raise RuntimeError('Service manager or isolation proof is incomplete')
            service = report['candidateService']
            if (
                any(service.get(key) is not True for key in REQUIRED_SERVICE_RESULTS)
                or service.get('flatpakPackageVerified') is not False
                or service.get('realFrameContacted') is not False
            ):
                raise RuntimeError('Service lifecycle results are incomplete')
            if any(
                sha((ROOT / path).read_bytes()) != digest
                for path, digest in sources.items()
            ):
                raise RuntimeError('Service probe inputs changed during execution')
            report.update(
                architecture=arch,
                accelerator='TCG',
                image=image_info['Id'],
                providedImage=bool(args.image),
                kernelSha256=sha(kernel),
                initrdSha256=sha((folder / 'initrd.gz').read_bytes()),
                sourceSha256=sources,
                helperSha256=sha(helper),
                loaderSha256=loader_sha,
                decky=native.RELEASE,
                runtimeArchiveSha256=archive_sha,
                runtimeBinarySha256=binary_sha,
                officialArchiveSha256=runtime.DIGEST,
                installerEnabled=False,
            )
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            print(
                'Actual systemd user service, real Syncthing and Decky RPC passed in an isolated VM; '
                'Flatpak packaging, managed install, browser, Frame and VR remain unverified'
            )
    finally:
        subprocess.run(
            ['docker', 'rm', '-f', container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not args.image:
            subprocess.run(
                ['docker', 'image', 'rm', image],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


if __name__ == '__main__':
    main()
