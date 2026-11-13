#!/usr/bin/env python3
"""Cache published test inputs; each fixture still verifies its own input pins."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import runpy
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def pins(arch):
    native = runpy.run_path(str(ROOT / 'scripts/framey-test-decky-runtime.py'))
    runtime = runpy.run_path(str(ROOT / 'scripts/framey-test-syncthing-runtime.py'))
    asset, loader_digest, _machine = native['LOADERS'][arch]
    dist, archive_digest, _binary_digest, _machine = runtime['RUNTIMES'][arch]
    return {
        'loader': (f"https://github.com/SteamDeckHomebrew/decky-loader/releases/download/{native['RELEASE']}/{asset}",
                   loader_digest, 80 * 1024**2, 'loader'),
        'syncthing': (f"https://github.com/syncthing/syncthing/releases/download/{runtime['VERSION']}/syncthing-linux-{dist}-{runtime['VERSION']}.tar.gz",
                      archive_digest, 25 * 1024**2, 'syncthing.tar.gz'),
    }


def cache_input(path, url, digest, limit):
    hit = path.exists()
    if hit:
        with path.open('rb') as stream:
            data = stream.read(limit + 1)
    else:
        request = urllib.request.Request(url, headers={'User-Agent': 'Frame-Control-runtime-tests'})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(limit + 1)
    if len(data) > limit or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Pinned runtime input size or digest mismatch: ' + path.name)
    if not hit:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return dict(cacheHit=hit, bytes=len(data), sha256=digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keys', action='store_true', help='Print immutable cache keys for GITHUB_OUTPUT')
    parser.add_argument('--kind', choices=['loader', 'syncthing'])
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    arch = platform.machine()
    if platform.system() != 'Linux' or arch not in ('x86_64', 'aarch64'):
        parser.error('Run on native Linux AMD64 or ARM64')
    inputs = pins(arch)
    if args.keys:
        for kind, (_url, digest, _limit, _filename) in inputs.items():
            print(f'{kind}-key=framey-runtime-input-v1-{kind}-{arch}-{digest}')
        return
    if not args.kind or args.directory is None:
        parser.error('--kind and --directory are required unless --keys is used')
    url, digest, limit, filename = inputs[args.kind]
    receipt = cache_input(args.directory / filename, url, digest, limit)
    print(json.dumps(dict(input=args.kind, architecture=arch, **receipt)))


if __name__ == '__main__':
    main()
