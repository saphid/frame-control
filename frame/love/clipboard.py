"""Compile the attributed SDL clipboard fix and merge it into the pinned runtime.

Only the original class definition is removed; D8 resolves references to the
replacement compiled from Java. No game, native library, or other Java source
is patched. The runtime's SHA-256 is checked by package.py before calling this.
"""
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile
import zlib

HERE = Path(__file__).resolve().parent
CLASS = 'Lorg/libsdl/app/SDLClipboardHandler;'
SOURCE_COMMIT = '55feb38fa144f4734c26742389f279fb07d955c0'
UPSTREAM_SOURCE_SHA256 = '88e49e925b1c89f593fcd404925a43762a194ba108c48bb5140e794c292358fd'


def remove_class(data, descriptor=CLASS):
    """Remove one DEX class_def, retaining offsets; refresh map, SHA-1 and Adler32.

    Orphaned class_data/code are ignored by D8 and disappear in its final output.
    Fail closed on a changed/malformed DEX instead of patching instruction bytes.
    """
    if (data[:8] not in (b'dex\n035\0', b'dex\n037\0', b'dex\n038\0', b'dex\n039\0') or
            len(data) < 112 or struct.unpack_from('<I', data, 32)[0] != len(data) or
            hashlib.sha1(data[32:]).digest() != data[12:32] or
            zlib.adler32(data[12:]) != struct.unpack_from('<I', data, 8)[0]):
        raise ValueError('invalid DEX header/checksum')
    def word(offset):
        return struct.unpack_from('<I', data, offset)[0]
    strings_count, strings_offset = word(56), word(60)
    types_count, types_offset = word(64), word(68)
    count, offset = word(96), word(100)
    matches = []
    for i in range(count):
        type_id = word(offset + i * 32)
        if type_id >= types_count:
            raise ValueError('invalid DEX class type')
        string_id = word(types_offset + type_id * 4)
        if string_id >= strings_count:
            raise ValueError('invalid DEX descriptor')
        start = word(strings_offset + string_id * 4)
        # Skip the UTF-16 length ULEB128. Class descriptors are ASCII.
        for _ in range(5):
            byte = data[start]
            start += 1
            if byte < 128:
                break
        else:
            raise ValueError('invalid DEX string length')
        end = data.index(b'\0', start)
        if data[start:end].decode('ascii') == descriptor:
            matches.append(i)
    if len(matches) != 1:
        raise ValueError('expected exactly one SDL clipboard class')
    out = bytearray(data)
    at = offset + matches[0] * 32
    out[at:offset + (count - 1) * 32] = data[at + 32:offset + count * 32]
    out[offset + (count - 1) * 32:offset + count * 32] = bytes(32)
    struct.pack_into('<I', out, 96, count - 1)
    mapped = 0
    map_offset = word(52)
    for i in range(word(map_offset)):
        entry = map_offset + 4 + i * 12
        kind, _, size, position = struct.unpack_from('<HHII', data, entry)
        if kind == 6:
            if size != count or position != offset:
                raise ValueError('inconsistent DEX class map')
            struct.pack_into('<I', out, entry + 4, count - 1)
            mapped += 1
    if mapped != 1:
        raise ValueError('missing DEX class map')
    out[12:32] = hashlib.sha1(out[32:]).digest()
    struct.pack_into('<I', out, 8, zlib.adler32(out[12:]))
    return bytes(out)


def compile_runtime(runtime, android_jar, d8, javac='javac'):
    """Return replacement classes.dex and a source/tool/output provenance receipt."""
    android_jar = Path(android_jar).resolve()
    found_d8 = shutil.which(str(d8))
    if not found_d8:
        raise ValueError('Android SDK build-tools d8 executable was not found')
    d8 = Path(found_d8).resolve()
    source = HERE / 'SDLClipboardHandler.java'
    with zipfile.ZipFile(runtime) as archive:
        dex_names = [n for n in archive.namelist() if n.endswith('.dex')]
        if dex_names != ['classes.dex']:
            raise ValueError('expected pinned single-DEX runtime')
        original = archive.read('classes.dex')
    with tempfile.TemporaryDirectory(prefix='frame-love-java-') as temporary:
        work = Path(temporary)
        classes = work / 'classes'
        classes.mkdir()
        # Compile-only signatures, never shipped; references resolve to the
        # unmodified SDL/SDLActivity classes already in the original DEX.
        (work / 'SDL.java').write_text('package org.libsdl.app; class SDL { '
            'public static android.content.Context getContext() { return null; } }')
        (work / 'SDLActivity.java').write_text('package org.libsdl.app; class SDLActivity { '
            'public static native void onNativeClipboardChanged(); }')
        subprocess.run([str(javac), '--release', '8', '-g:none', '-classpath', str(android_jar),
                        '-d', str(classes), str(source), str(work / 'SDL.java'),
                        str(work / 'SDLActivity.java')], check=True)
        reduced = work / 'original.dex'
        reduced.write_bytes(remove_class(original))
        output = work / 'dex'
        output.mkdir()
        subprocess.run([str(d8), '--release', '--min-api', '26', '--lib', str(android_jar),
                        '--output', str(output), str(reduced),
                        str(classes / 'org/libsdl/app/SDLClipboardHandler.class')], check=True)
        names = [p.name for p in output.iterdir()]
        if names != ['classes.dex']:
            raise ValueError('unexpected compiler output')
        dex = (output / 'classes.dex').read_bytes()
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    receipt = {'fix': 'sdl-null-clipboard-1', 'upstream_commit': SOURCE_COMMIT,
               'upstream_source_sha256': UPSTREAM_SOURCE_SHA256,
               'java_source_sha256': digest(source), 'android_jar_sha256': digest(android_jar),
               'patcher_sha256': digest(__file__), 'min_api': 26, 'java_release': 8,
               'd8_jar_sha256': digest(d8.parent / 'lib/d8.jar'),
               'javac_version': subprocess.check_output([str(javac), '-version'], text=True).strip(),
               'd8_version': subprocess.check_output([str(d8), '--version'], text=True).strip(),
               'original_dex_sha256': hashlib.sha256(original).hexdigest(),
               'patched_dex_sha256': hashlib.sha256(dex).hexdigest()}
    return dex, receipt
