#!/usr/bin/env python3
"""Cache exact catalog archives for fake-Frame transport tests; execute no plugin code."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CDN = 'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/'
MAX_ARCHIVE = 200 * 1024 * 1024


def fingerprint(stream):
    digest, size = hashlib.sha256(), 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            return digest.hexdigest(), size
        size += len(block)
        if size > MAX_ARCHIVE:
            raise ValueError('archive exceeds cache size limit')
        digest.update(block)


def store(stream, target, expected):
    # Failed downloads never publish partial/unverified archive bytes.
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.catalog-', delete=False) as output:
        temp = Path(output.name)
        try:
            digest, size = hashlib.sha256(), 0
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > MAX_ARCHIVE:
                    raise ValueError('archive exceeds cache size limit')
                digest.update(block)
                output.write(block)
            if digest.hexdigest() != expected:
                raise ValueError('archive SHA-256 mismatch')
        except BaseException:
            output.close()
            temp.unlink()
            raise
    try:
        temp.chmod(0o644)  # The fake-Frame test user reads this read-only mount.
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return size


def archive(record, cache, fixtures):
    digest = record['sha256']
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('invalid catalog SHA-256')
    target = cache / (digest + '.zip')
    result = {k: record[k] for k in ('id', 'version', 'sha256')}
    if target.exists():
        with target.open('rb') as source:
            actual, size = fingerprint(source)
        if actual != digest:
            raise ValueError('cached archive SHA-256 mismatch')
        origin = 'cache'
    elif (fixtures / (str(record['id']) + '.zip')).is_file():
        with (fixtures / (str(record['id']) + '.zip')).open('rb') as source:
            size = store(source, target, digest)
        origin = 'fixture'
    else:
        request = urllib.request.Request(CDN + digest + '.zip', headers={'User-Agent': 'Frame-Control'})
        with urllib.request.urlopen(request, timeout=60) as source:
            size = store(source, target, digest)
        origin = 'cdn'
    return dict(result, bytes=size, source=origin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'ui/framey-compatibility.json')
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = args.catalog.read_bytes()
    records = json.loads(data)['plugins']
    args.cache.mkdir(parents=True, exist_ok=True)

    def prepare(record):
        try:
            return archive(record, args.cache, ROOT / 'tests/fixtures/framey-official')
        except Exception as error:
            return {k: record[k] for k in ('id', 'version', 'sha256')} | {'error': str(error)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(prepare, records))
    report = dict(catalogSha256=hashlib.sha256(data).hexdigest(), records=results,
                  success=bool(records) and all('error' not in r for r in results), pluginCodeExecuted=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Verified {sum('error' not in r for r in results)}/{len(records)} pinned archives; {args.output}")
    for r in results:
        if 'error' in r:
            print(f"{r['id']}: {r['error']}")
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
