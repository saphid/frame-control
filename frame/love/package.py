#!/usr/bin/env python3
"""Package a user's extracted LÖVE game with the official Android embed runtime.

The runtime is supplied separately; neither it nor game files are committed.
Uses Frame Control's APK signer, keeping the same local signing identity for updates.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ui'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from clipboard import compile_runtime
import frame_apk
import frame_apk_sign
from frame_apk_vr import _append_string

ENGINE_SHA256 = 'dcf71c1b54c5b5a09598ef1e6cf4852ced5e5e612de3d0f30cfdd39b5014e889'
ENGINE_URL = 'https://github.com/love2d/love-android/releases/download/11.5a/love-11.5-android-embed-norecording.apk'
ENGINE_PACKAGE = 'org.love2d.android'


def manifest(data, package, label):
    """Change app identity without changing the runtime's Java/JNI class names."""
    if len(package) > 255 or not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', package):
        raise ValueError('package must be a lowercase Android package name')
    if package == ENGINE_PACKAGE or not label or len(label.encode('utf-8')) > 100:
        raise ValueError('use a distinct package and a label of 1..100 UTF-8 bytes')
    chunks = list(frame_apk._chunks(data, 8, len(data)))
    pool = next(c for c in chunks if c[0] == 1)
    strings = frame_apk._string_pool(data, pool[2])
    updated_pool = data[pool[2]:pool[2] + pool[3]]
    replacements = {}
    for old, new in ((ENGINE_PACKAGE, package),
                     (ENGINE_PACKAGE + '.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION',
                      package + '.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'),
                     (ENGINE_PACKAGE + '.androidx-startup', package + '.androidx-startup'),
                     ('LÖVE for Android', label)):
        if old not in strings:
            raise ValueError('unexpected embed runtime manifest: missing ' + old)
        updated_pool, index = _append_string(updated_pool, new)
        replacements[strings.index(old)] = index
    out = bytearray(data[:8])
    for kind, hs, off, size in chunks:
        part = bytearray(data[off:off + size])
        if off == pool[2]:
            part = updated_pool
        elif kind == 0x0102:
            start, stride, count = struct.unpack_from('<HHH', part, hs + 8)
            for i in range(count):
                at = hs + start + i * stride
                raw = struct.unpack_from('<I', part, at + 8)[0]
                dtype, value = struct.unpack_from('<3xBI', part, at + 12)
                if raw in replacements:
                    struct.pack_into('<I', part, at + 8, replacements[raw])
                if dtype == 3 and value in replacements:
                    struct.pack_into('<I', part, at + 16, replacements[value])
        out += part
    struct.pack_into('<I', out, 4, len(out))
    return bytes(out)


def build(runtime, game, output, package, label, android_jar, d8, javac='javac'):
    if hashlib.sha256(runtime.read_bytes()).hexdigest() != ENGINE_SHA256:
        raise ValueError('runtime must be the pinned official LÖVE 11.5a embed APK: ' + ENGINE_URL)
    if not (game / 'main.lua').is_file():
        raise ValueError('game folder must contain main.lua')
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(game.rglob('*')):
            if path.is_symlink():
                raise ValueError('game folder must not contain symlinks')
            if path.is_file():
                archive.write(path, path.relative_to(game).as_posix())
    with zipfile.ZipFile(runtime) as archive:
        if 'lib/arm64-v8a/liblove.so' not in archive.namelist():
            raise ValueError('runtime lacks ARM64 support')
        axml = manifest(archive.read('AndroidManifest.xml'), package, label)
    dex, receipt = compile_runtime(runtime, android_jar, d8, javac)
    frame_apk_sign.repack(runtime, output, replace={'AndroidManifest.xml': axml, 'classes.dex': dex},
                          add={'assets/game.love': payload.getvalue()})
    receipt.update({'runtime_sha256': ENGINE_SHA256, 'package': package,
                    'game_love_sha256': hashlib.sha256(payload.getvalue()).hexdigest(),
                    'signer_certificate_sha256': hashlib.sha256(frame_apk_sign.certificate(
                        frame_apk_sign.signing_key())).hexdigest(),
                    'apk_sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    output.with_suffix(output.suffix + '.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--game', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--package', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--android-jar', type=Path, default=os.environ.get('ANDROID_JAR'),
                   help='Android SDK platform android.jar (or ANDROID_JAR)')
    p.add_argument('--d8', default='d8', help='Android SDK build-tools d8 executable')
    p.add_argument('--javac', default='javac', help='JDK javac executable')
    a = p.parse_args()
    if not a.android_jar:
        p.error('--android-jar or ANDROID_JAR is required for the SDL clipboard fix')
    print(build(a.runtime, a.game, a.output, a.package, a.label, a.android_jar, a.d8, a.javac))
