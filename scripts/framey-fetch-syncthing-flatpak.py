#!/usr/bin/env python3
"""Fetch bounded pinned public app objects; run the offline verifier afterward.

Requires python3-gi on the download host. Existing cache objects are preserved;
only offline signature and fsck verification establish payload integrity.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

from gi.repository import GLib

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('payload', ROOT / 'framey-verify-syncthing-flatpak.py')
payload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payload)
BASE = 'https://dl.flathub.org/repo/'
MAX_TOTAL = 256 * 1024 * 1024
MAX_OBJECT = 64 * 1024 * 1024


def variant(data, signature):
    value = GLib.Variant.new_from_bytes(GLib.VariantType.new(signature), GLib.Bytes.new(data), False)
    if not value.is_normal_form():
        raise ValueError('Invalid OSTree metadata')
    return value.unpack()


def download(url, limit):
    """Retry only bounded transient transport failures, retaining TLS checks."""
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Frame-Control-package-audit'})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Public input exceeds bound: ' + url)
            return data
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if isinstance(error, urllib.error.HTTPError):
                transient = error.code in (429, 500, 502, 503, 504)
            else:
                reason = error.reason if isinstance(error, urllib.error.URLError) else error
                transient = isinstance(reason, (TimeoutError, ConnectionError))
            if not transient or attempt == 2:
                raise RuntimeError('Public fetch failed for ' + url + ': ' + str(error)) from error
            time.sleep(attempt + 1)


def fetch(directory):
    directory.mkdir(parents=True, exist_ok=True)
    store = directory / 'objects'
    store.mkdir(exist_ok=True)
    lock, index = threading.Lock(), {}
    total = 0


    def get(checksum, kind):
        nonlocal total
        if len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
            raise ValueError('Invalid object checksum')
        key = checksum + '.' + kind
        path = store / checksum[:2] / key[2:]
        url = BASE + 'objects/' + checksum[:2] + '/' + key[2:]
        if path.exists() and (path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_OBJECT):
            raise ValueError('Unexpected existing cache object')
        data = path.read_bytes() if path.exists() else download(url, MAX_OBJECT)
        digest = hashlib.sha256(data).hexdigest()
        if kind not in ('filez', 'commitmeta') and digest != checksum:
            raise ValueError('Metadata checksum mismatch')
        with lock:
            if key not in index:
                total += len(data)
                if total > MAX_TOTAL or len(index) >= 10000:
                    raise ValueError('App closure exceeds bound')
                index[key] = {'url': url, 'bytes': len(data), 'downloadSha256': digest}
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            with path.open('xb') as output:
                output.write(data)
        return data

    descriptor = directory / 'flathub.flatpakrepo'
    data = descriptor.read_bytes() if descriptor.exists() else download(BASE + 'flathub.flatpakrepo', 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != payload.DESCRIPTOR_SHA256:
        raise ValueError('Unexpected Flathub descriptor')
    if not descriptor.exists():
        with descriptor.open('xb') as output:
            output.write(data)
    report = {'architectures': {}, 'payloadVerified': False, 'packageLaunched': False,
              'maxDownloadBytes': MAX_TOTAL, 'descriptorSha256': payload.DESCRIPTOR_SHA256}
    for arch, commit in payload.COMMITS.items():
        value = variant(get(commit, 'commit'), '(a{sv}aya(say)sstayay)')
        get(commit, 'commitmeta')
        trees = [(bytes(value[6]).hex(), bytes(value[7]).hex(), '')]
        files, directories = {}, 0
        while trees:
            tree, metadata, path = trees.pop()
            directories += 1
            if directories > 10000:
                raise ValueError('Too many app directories')
            get(metadata, 'dirmeta')
            entries, children = variant(get(tree, 'dirtree'), '(a(say)a(sayay))')
            for name, checksum in entries:
                if not name or name in ('.', '..') or '/' in name or '\x00' in name:
                    raise ValueError('Invalid file name')
                files[path + name] = bytes(checksum).hex()
            for name, child, child_metadata in children:
                if not name or name in ('.', '..') or '/' in name or '\x00' in name:
                    raise ValueError('Invalid directory name')
                trees.append((bytes(child).hex(), bytes(child_metadata).hex(), path + name + '/'))
            if len(files) + len(trees) > 10000:
                raise ValueError('Too many app entries')
        contents = sorted(set(files.values()))
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda checksum: get(checksum, 'filez'), contents))
        report['architectures'][arch] = {'commit': commit, 'fileCount': len(files),
                                       'uniqueContentObjects': len(contents)}
    report.update(totalObjectBytes=total, objects=index)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True, help='Public object cache; preserved')
    args = parser.parse_args()
    try:
        report = fetch(args.directory)
    except Exception as error:
        args.directory.mkdir(parents=True, exist_ok=True)
        failure = {'payloadVerified': False, 'packageLaunched': False, 'error': str(error)}
        (args.directory / 'fetch-error.json').write_text(json.dumps(failure, indent=2) + '\n')
        raise
    (args.directory / 'fetch-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'objects'}, indent=2))


if __name__ == '__main__':
    main()
