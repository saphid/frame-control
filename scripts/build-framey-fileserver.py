#!/usr/bin/env python3
"""Rebuild the pinned GPL DeckyFileServer helper offline (Go 1.25.7 required)."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'ui/vendor/deckyfileserver-1.2.0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', default='go')
    parser.add_argument('--output', type=Path, default=ASSETS)
    args = parser.parse_args()
    assert subprocess.check_output([args.go, 'version'], text=True).split()[2] == 'go1.25.7', 'Use Go 1.25.7'
    assert hashlib.sha256((ASSETS/'source.tar.gz').read_bytes()).hexdigest() == '50d90a7328daa412bf963ec68bb4855a9ec0860a8475cdf7d2019e6c2507112d', 'Source archive digest mismatch'
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='framey-fileserver-build-') as temp:
        base = Path(temp)
        with tarfile.open(ASSETS/'source.tar.gz') as archive:
            assert all(m.isfile() and m.name.startswith('source/') and '..' not in Path(m.name).parts
                       for m in archive.getmembers())
            archive.extractall(base, filter='data')
        env = dict(os.environ, CGO_ENABLED='0', GOOS='linux', GOPROXY='off', GOSUMDB='off', GOTOOLCHAIN='local',
                   GOCACHE=str(base/'cache'), GOMODCACHE=str(base/'modules'))
        for arch, name in [('amd64', 'x86_64'), ('arm64', 'aarch64')]:
            output = base/'backend'
            subprocess.run([args.go, 'build', '-mod=vendor', '-trimpath', '-buildvcs=false',
                            '-ldflags=-s -w -buildid=', '-o', str(output), '.'], cwd=base/'source',
                           env=dict(env, GOARCH=arch), check=True)
            data = output.read_bytes()
            packed = gzip.compress(data, mtime=0)
            (args.output/f'{name}.gz').write_bytes(packed)
            print(json.dumps({'arch': name, 'sha256': hashlib.sha256(data).hexdigest(),
                              'gzipSha256': hashlib.sha256(packed).hexdigest(), 'bytes': len(data)}), flush=True)


if __name__ == '__main__':
    main()
