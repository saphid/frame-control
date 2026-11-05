#!/usr/bin/env python3
"""Build the pinned NxNative Android fork with Frame patches on macOS.

Requires an NDK, Android SDK/JDK, .NET 10, spirv-cross and Xcode Metal tools.
Set ANDROID_SDK, ANDROID_BUILD_TOOLS, ANDROID_JAR, JAVA_HOME, DOTNET_ROOT and
PATH for those tools. Game data stays outside this repository.
"""
import argparse
import os
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

from extract_romfs import extract

PIN = '32b0ef2c5408e1e32cb5c0bc49f84d1e63653dc3'
REMOTE = 'https://github.com/joaquinsandoval2307/nxnative.git'
HERE = Path(__file__).resolve().parent


def run(*args, cwd=None, env=None):
    subprocess.run([str(x) for x in args], cwd=cwd, env=env, check=True)


def build(a):
    if a.jobs < 1:
        raise ValueError('jobs must be positive')
    if not re.fullmatch('[0-9A-Fa-f]{16}', a.title):
        raise ValueError('title must be a 16-digit title ID')
    source, out = a.source.resolve(), a.build.resolve()
    if not source.exists():
        run('git', 'clone', '--branch', 'android', REMOTE, source)
        run('git', 'checkout', '--detach', PIN, cwd=source)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if head != PIN:
        raise ValueError('source must be at pinned Android fork ' + PIN)
    patch = HERE / 'android-frame.patch'
    applied = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=source,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not applied:
        run('git', 'apply', '--check', patch, cwd=source)
        run('git', 'apply', patch, cwd=source)
    env = dict(os.environ, DM_GAME=a.title.upper(), DM_PATCH_TP='android', DM_REWRITE_J=str(a.jobs))
    out.mkdir(parents=True, exist_ok=True)
    extracted = a.extracted.resolve()
    identity = {'extracted': str(extracted)}
    image = extracted / 'RomFS.img'
    if not (extracted / 'RomFS').is_dir() and image.is_file():
        st = image.stat()
        identity['image'] = [st.st_size, st.st_mtime_ns]
    receipt = out / 'frame-inputs.json'
    if receipt.exists() and json.loads(receipt.read_text()) != identity:
        raise ValueError('build folder belongs to different inputs; use a new build folder')
    receipt.write_text(json.dumps(identity, indent=2) + '\n')
    inputs = out / 'extract' / extracted.name
    inputs.mkdir(parents=True, exist_ok=True)
    for name in ('ExeFS', 'icon.jpg', 'control.nacp'):
        target = inputs / name
        if target.exists() and target.resolve() != (extracted / name).resolve():
            raise ValueError('existing build input differs: ' + str(target))
        if not target.exists():
            target.symlink_to(extracted / name)
    if not (inputs / 'RomFS').exists():
        if (extracted / 'RomFS').is_dir():
            (inputs / 'RomFS').symlink_to(extracted / 'RomFS')
        else:
            extract(extracted / 'RomFS.img', inputs / 'RomFS')
    font = out / 'font'
    font.mkdir(exist_ok=True)
    shutil.copyfile(a.font, font / 'standard.ttf')
    run(sys.executable, source / 'dm/tools/make_ext_font.py', font / 'nintendo_ext.ttf', env=env)
    patched = out / 'patched_android'
    patched.mkdir(exist_ok=True)
    for name in ('main', 'subsdk0', 'sdk'):
        run(sys.executable, source / 'dm/tools/patch_nso.py', extracted / 'ExeFS' / name,
            patched, name, cwd=source, env=env)
    # Record this machine's tool fingerprints through the fork's supported path.
    run(sys.executable, source / 'dm/gfx/tools/dmsh_chain.py', '--update-lock', cwd=source, env=env)
    run(sys.executable, source / 'dm/gfx/tools/dmsh_chain.py', '--header', cwd=source, env=env)
    run(sys.executable, source / 'dm/android/tools/spv_android.py', a.shader_package.resolve(),
        a.shader_cache.resolve(), out / 'shader/vk', cwd=source, env=env)
    run('make', '-C', source / 'dm/android', 'GAME=' + a.title.upper(), 'NDK=' + str(a.ndk.resolve()),
        '-j' + str(a.jobs), env=env)
    if a.title.upper() == '010093801237C000':
        run('make', '-C', source / 'dm/host/tests', 'GAME=' + a.title.upper(), 'frame-handoff', env=env)
    run(sys.executable, source / 'dm/android/tools/make_apk.py', a.title.upper(), out,
        out / 'game.apk', '--label', a.label, env=env)
    # Preserve the exact toolchain fingerprints as a receipt, without game data.
    (out / 'toolchain.patch').write_bytes(subprocess.check_output([
        'git', 'diff', '--', 'dm/gfx/tools/dmsh_chain.lock',
        'dm/games/' + a.title.upper() + '/dmsh_chain.h'], cwd=source))
    print('APK:', out / 'game.apk')
    if a.bundle:
        run(sys.executable, HERE.parent.parent / 'ui/frame_nxnative.py', 'export',
            '--build', out, '--output', a.bundle.resolve(), '--title', a.title.upper(),
            '--name', a.label, '--version', a.version, env=env)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'build', 'extracted', 'shader-package', 'shader-cache', 'ndk'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--title', default='010093801237C000')
    parser.add_argument('--label', default='Metroid Dread (NxNative)')
    parser.add_argument('--font', type=Path, default=Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--bundle', type=Path, help='also export a portable .nxnative.zip installer')
    parser.add_argument('--version', default='', help='game version recorded in the portable bundle')
    build(parser.parse_args())
