#!/usr/bin/env python3
"""Rebuild the pinned LocalSend-Go helper (Go 1.25.7 and module access required)."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'ui/vendor/localsend-0.4.5'
SOURCE_SHA256 = 'f1f86292624b989d540689dbfad503bf15f3937d156978157b8dd418d54415d1'
EXPECTED = {
    'amd64': 'd448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843',
    'arm64': 'e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', default='go', help='Path to Go 1.25.7')
    parser.add_argument('--output', type=Path, default=ASSETS)
    args = parser.parse_args()
    assert subprocess.check_output([args.go, 'version'], text=True).split()[2] == 'go1.25.7', 'Use Go 1.25.7'
    source_data = (ASSETS/'source.tar.gz').read_bytes()
    assert hashlib.sha256(source_data).hexdigest() == SOURCE_SHA256, 'Pinned source archive changed'
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='framey-localsend-build-') as temporary:
        base = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(source_data), mode='r:gz') as archive:
            members = archive.getmembers()
            assert all((m.isfile() or m.isdir()) and
                       (m.name == 'source' or m.name.startswith('source/'))
                       and '..' not in Path(m.name).parts for m in members), 'Unsafe source archive'
            archive.extractall(base, filter='data')
        env = dict(os.environ, CGO_ENABLED='0', GOOS='linux', GOTOOLCHAIN='local',
                   GOCACHE=str(base/'cache'), GOMODCACHE=str(base/'modules'))
        for arch in ('amd64', 'arm64'):
            output = base/'localsend-core'
            subprocess.run([args.go, 'build', '-mod=readonly', '-trimpath', '-buildvcs=false',
                            '-ldflags=-s -w', '-o', str(output), '.'], cwd=base/'source',
                           env=dict(env, GOARCH=arch), check=True)
            data = output.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            assert digest == EXPECTED[arch], f'{arch} helper does not match pinned bytes'
            if arch == 'arm64':
                packed = gzip.compress(data, mtime=0)
                (args.output/'aarch64.gz').write_bytes(packed)
                packed_digest = hashlib.sha256(packed).hexdigest()
            else:
                packed_digest = None
            print(json.dumps({'arch': arch, 'sha256': digest, 'gzipSha256': packed_digest,
                              'bytes': len(data)}), flush=True)


if __name__ == '__main__':
    main()
