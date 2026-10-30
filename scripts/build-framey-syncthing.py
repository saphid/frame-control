#!/usr/bin/env python3
"""Build the uninstalled Syncthing ownership candidate in an isolated container.

Only locked public dependency fetching uses network access. No helper runs.
The managed installer deliberately continues to reject this official archive.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'ui/vendor/syncthing-0.2.7'
SOURCE_SHA = 'a17f1c0bdfa70cf666c0d57a996a25597ac2f4791d43463a5dbf0639a0e51f8f'
SOURCE_COMMIT = '464fd7ca05ee0bea8daa8d5d125dfc672cf08942'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(folder):
    packed = (ASSETS/'source.tar.gz').read_bytes()
    if sha(packed) != SOURCE_SHA:
        raise ValueError('Pinned Syncthing source archive mismatch')
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:
                raise ValueError('Unexpected source archive entry')
            target = folder/member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(ASSETS/'watchdog.patch')],
                   cwd=folder, check=True, capture_output=True, text=True)
    shutil.copyfile(ASSETS/'owned_unit.rs', folder/'backend/decky-syncthing-watchdog/src/owned_unit.rs')


def build(folder, image, arch, output):
    name = 'framey-syncthing-build-'+uuid.uuid4().hex[:12]
    target = arch+'-unknown-linux-gnu'
    command = ['cargo', 'build', '--frozen', '--offline', '--release', '--target', target, '-j2']
    linker = (['--env', 'CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc']
              if arch == 'aarch64' and platform.machine() != 'aarch64' else [])
    args = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
            '--user', f'{os.getuid()}:{os.getgid()}', '--tmpfs', '/tmp:rw,exec,mode=1777',
            '--mount', f'type=bind,source={folder},target=/src',
            '--env', 'CARGO_HOME=/src/cargo-home',
            *linker,
            '--env', 'RUSTFLAGS=--remap-path-prefix=/src=. -C link-arg=-Wl,--build-id=none',
            '--workdir', '/src/backend/decky-syncthing-watchdog', image]
    try:
        with (output/f'{arch}.build.log').open('w') as log:
            native = arch == platform.machine()
            if native:
                tests = ['rustc', '--edition', '2024', '--test', 'src/owned_unit.rs',
                         '-o', '/src/owned-unit-tests']
                subprocess.run(args+tests, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
                subprocess.run(args+['/src/owned-unit-tests'], stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=30)
            result = subprocess.run(args+command, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        if result.returncode:
            raise RuntimeError(f'{arch} build failed; see {output/arch}.build.log')
        binary = (folder/'backend/decky-syncthing-watchdog/target'/target/'release/decky-syncthing-watchdog').read_bytes()
        machine = {'x86_64':62, 'aarch64':183}[arch]
        if binary[:4] != b'\x7fELF' or int.from_bytes(binary[18:20], 'little') != machine:
            raise RuntimeError('Built Syncthing helper has the wrong ELF architecture')
        path = output/f'{arch}.watchdog'
        path.write_bytes(binary)
        path.chmod(0o700)
        return {'architecture':arch, 'elfMachine':machine, 'bytes':len(binary), 'sha256':sha(binary),
                'command':command, 'executed':False, 'serviceFileTestsExecuted':native}
    finally:
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Rust 1.98.1 Bookworm image with native/ARM64 compilers and targets')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--architectures', nargs='+', choices=['x86_64', 'aarch64'], default=['x86_64', 'aarch64'])
    dependencies = parser.add_mutually_exclusive_group(required=True)
    dependencies.add_argument('--fetch', action='store_true', help='Fetch public dependencies into an owned cache before building')
    dependencies.add_argument('--dependency-cache', type=Path, help='Copy only registry/git from a prepared public Cargo cache')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]['Id']
    inputs = {name:sha((ASSETS/name).read_bytes()) for name in ('source.tar.gz', 'watchdog.patch', 'main.py', 'owned_unit.rs')}
    with tempfile.TemporaryDirectory(prefix='framey-syncthing-build-') as temp:
        source = Path(temp)
        prepare(source)
        cache = source/'cargo-home'
        cache.mkdir()
        manifest = source/'backend/decky-syncthing-watchdog/Cargo.toml'
        lock = manifest.with_name('Cargo.lock').read_bytes()
        if args.fetch:
            subprocess.run(['cargo', 'fetch', '--locked', '--manifest-path', str(manifest)],
                           env={**os.environ, 'CARGO_HOME':str(cache)}, check=True, timeout=180)
        else:
            for name in ('registry', 'git'):
                shutil.copytree(args.dependency_cache/name, cache/name)
        reports = [build(source, image, arch, args.output) for arch in args.architectures]
        if manifest.with_name('Cargo.lock').read_bytes() != lock:
            raise RuntimeError('Locked dependencies changed')
        if any(sha((ASSETS/name).read_bytes()) != digest for name, digest in inputs.items()):
            raise RuntimeError('Candidate inputs changed during the build')
        report = {'sourceCommit':SOURCE_COMMIT, 'sourceArchiveSha256':SOURCE_SHA,
                  'patchSha256':inputs['watchdog.patch'],
                  'ownedUnitSha256':inputs['owned_unit.rs'],
                  'pythonSha256':inputs['main.py'], 'builderImage':image,
                  'cargoLockSha256':sha(lock), 'builds':reports,
                  'installerEnabled':False, 'runtimeVerified':False}
        (args.output/'build-report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
