#!/usr/bin/env python3
"""Expand NxNative's DMROMFS1 image into a new folder for the Android fork.

The format is defined by upstream dm/tools/romfs_image.py. No keys are needed.
The source image and any existing destination are never modified.
"""
import argparse
from pathlib import Path
import struct
import shutil
import uuid


def _extract(image, destination):
    image, destination = Path(image), Path(destination)
    with image.open('rb') as src:
        size = image.stat().st_size
        header = src.read(32)
        if len(header) != 32:
            raise ValueError('truncated DMROMFS1 header')
        magic, offset, length, count = struct.unpack('<8sQQQ', header)
        if (magic != b'DMROMFS1' or offset < 32 or offset > size
                or length != size - offset or not count or count > length // 24):
            raise ValueError('invalid DMROMFS1 header')
        src.seek(offset)
        index = src.read(length)
        pool = index[count * 24:]
        entries = [struct.unpack_from('<QQIHBB', index, i * 24) for i in range(count)]
        parents = [None] * count
        parents[0] = Path()
        next_child = 1
        paths = []
        for i, (a, b, no, nl, kind, flags) in enumerate(entries):
            if no + nl > len(pool) or kind > 1 or flags:
                raise ValueError('invalid entry or damaged source file')
            name = pool[no:no + nl].decode('utf-8')
            if i == 0:
                if name or kind:
                    raise ValueError('invalid root')
                path = Path()
            else:
                if not name or name in ('.', '..') or any(c in name for c in '/\\\0') or parents[i] is None:
                    raise ValueError('unsafe or unreachable entry')
                path = parents[i] / name
            if kind:
                if a < 32 or a > offset or b > offset - a:
                    raise ValueError('file outside data section')
            else:
                if a != next_child or a <= i or a > count or b > count - a:
                    raise ValueError('invalid directory children')
                for child in range(a, a + b):
                    parents[child] = path
                next_child += b
            paths.append(path)
        if next_child != count or len(set(paths)) != count:
            raise ValueError('unreachable or duplicate entries')
        destination.mkdir(parents=True, exist_ok=False)
        files = total = 0
        for path, (a, b, _, _, kind, _) in zip(paths, entries):
            target = destination / path
            if not kind:
                if path != Path():
                    target.mkdir()
                continue
            src.seek(a)
            with target.open('xb') as out:
                left = b
                while left:
                    block = src.read(min(left, 4 << 20))
                    if not block:
                        raise ValueError('truncated file')
                    out.write(block)
                    left -= len(block)
            files += 1
            total += b
        return {'files': files, 'bytes': total}


def extract(image, destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    temporary = destination.with_name('.' + destination.name + '.stage-' + uuid.uuid4().hex)
    try:
        result = _extract(image, temporary)
        temporary.rename(destination)
        return result
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('destination')
    args = parser.parse_args()
    print(extract(args.image, args.destination))
