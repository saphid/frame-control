#!/usr/bin/env python3
"""Rebuild the pinned, safety-patched Emuchievements helpers without network access."""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'ui/vendor/emuchievements-2.0.5'
SOURCE_SHA = '74b98fe484af0d50d3b5fdf3c478c260a6dcb20773dceea3cb4d7961a80c51a1'
BINARIES = {
    'x86_64': '7a3430fa47d2321b93e0a9d1346c70ea920ae4d6f0766c04d5044122fed25e07',
    'aarch64': 'c492ed3b3ea3bdacbd5d530958c455a0d6928e8c51ae28a739b616ce164874b6',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(source, image, arch, output):
    name = 'framey-emu-build-' + uuid.uuid4().hex[:12]
    args = [
        'docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
        '--user', f'{os.getuid()}:{os.getgid()}', '--tmpfs', '/tmp:rw,exec,mode=1777',
        '--mount', f'type=bind,source={source},target=/src', image,
        'sh', '-ec',
    ]
    build_dir = 'build-bookworm' if arch == 'x86_64' else 'build-bookworm-arm'
    flags = [
        'cmake', '-S', 'backend', '-B', f'/src/{build_dir}',
        '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_EXE_LINKER_FLAGS=-Wl,--build-id=none',
        '-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG -ffile-prefix-map=/src=.',
        '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG -ffile-prefix-map=/src=.',
        '-DENABLE_OPENSSL=OFF', '-DENABLE_LIBB2=OFF',
    ]
    if arch == 'aarch64':
        flags.extend([
            '-DCMAKE_SYSTEM_NAME=Linux', '-DCMAKE_SYSTEM_PROCESSOR=aarch64',
            '-DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc',
            '-DCMAKE_CXX_COMPILER=aarch64-linux-gnu-g++',
        ])
    command = ' '.join(shlex_quote(arg) for arg in flags)
    command += ' >/src/config.log 2>&1 && '
    command += f'cmake --build /src/{build_dir} -j2 --target hash >/src/build.log 2>&1'
    try:
        result = subprocess.run(args + [command], capture_output=True, text=True, timeout=600)
        if result.returncode:
            log = '\n'.join((source / name).read_text(errors='replace')[-5000:]
                            for name in ('config.log', 'build.log') if (source / name).exists())
            raise RuntimeError(f'{arch} build failed:\n{result.stderr[-1500:]}\n{log}')
        binary = (source / build_dir / 'hash').read_bytes()
        if digest(binary) != BINARIES[arch]:
            raise RuntimeError(f'{arch} binary differs from pinned build')
        packed = (ASSETS / f'{arch}.gz').read_bytes()
        if gzip.decompress(packed) != binary:
            raise RuntimeError(f'{arch} bundled helper differs from rebuilt source')
        (output / f'{arch}.hash').write_bytes(binary)
        print(f'{arch}: {digest(binary)}')
    finally:
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)


def shlex_quote(value):
    import shlex
    return shlex.quote(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amd64-image', required=True, help='prebuilt Bookwormfile image')
    parser.add_argument('--arm64-image', required=True, help='prebuilt BookwormCrossfile image')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    packed = (ASSETS / 'source.tar.gz').read_bytes()
    if digest(packed) != SOURCE_SHA:
        raise RuntimeError('Corresponding source SHA-256 mismatch')
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='framey-emuchievements-source-') as temp:
        source = Path(temp)
        with tarfile.open(fileobj=io_bytes(packed), mode='r:gz') as archive:
            archive.extractall(source, filter='data')
        for arch, image in (('x86_64', args.amd64_image), ('aarch64', args.arm64_image)):
            build(source, image, arch, args.output)


def io_bytes(data):
    import io
    return io.BytesIO(data)


if __name__ == '__main__':
    main()
