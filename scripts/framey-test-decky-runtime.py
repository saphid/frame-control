#!/usr/bin/env python3
"""Run every managed backend shim in native, isolated, published Decky 3.3.0.

Downloads a digest-pinned loader, or accepts --loader for an offline cached copy.
Only image build/download use network. All official plugin execution is in
network/device/session-isolated disposable Docker containers. Never uses Frame.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
RELEASE = 'v3.3.0'
LOADERS = {
    'x86_64': ('PluginLoader', 'e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181', 62),
    'aarch64': ('PluginLoader-arm64', '8ef5dcf36cbbbb6e97201a6baed5d79c4cc44ec27789fc9af1c5b6ae8f0b25b6', 183),
}


def check_coverage():
    """A new production shim must declare an actual-runtime probe before CI runs."""
    sys.path.insert(0, str(ROOT/'ui'))
    import frame_decky_store
    tree = ast.parse(frame_decky_store.APPLY)
    shims = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'compat_shims' and node.func.attr == 'append'):
            if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                raise ValueError('Managed shims must declare a literal name for runtime test coverage')
            shims.add(node.args[0].value)
    cases = json.loads((ROOT/'tests/decky-runtime/cases.json').read_text())
    # Frontend-only compatibility probes need no archive/backend adaptation.
    covered = {shim for case in cases for shim in ([case['shim']] if case['shim'] else []) + case.get('additionalShims', [])}
    if shims != covered:
        raise ValueError('Every managed shim needs an actual Decky runtime case')
    return cases


def loader_bytes(path):
    arch = platform.machine()
    if arch not in LOADERS:
        raise ValueError('Run on native Linux x86_64 or aarch64')
    asset, digest, machine = LOADERS[arch]
    if path:
        data = path.read_bytes()
    else:
        url = f'https://github.com/SteamDeckHomebrew/decky-loader/releases/download/{RELEASE}/{asset}'
        request = urllib.request.Request(url, headers={'User-Agent': 'Frame-Control-runtime-tests'})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(80*1024*1024+1)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Decky 3.3.0 loader digest mismatch')
    if data[:4] != b'\x7fELF' or int.from_bytes(data[18:20], 'little') != machine:
        raise ValueError('Loader architecture does not match the native runner')
    return data, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader', type=Path, help='Optional cached, digest-verified native Decky 3.3.0 binary')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', type=int, help='Run one official plugin case locally; CI runs all cases')
    args = parser.parse_args()
    if sys.platform != 'linux' or not shutil.which('docker'):
        parser.error('Linux with Docker is required')
    cases = check_coverage()
    if args.case is not None:
        cases = [case for case in cases if case['id'] == args.case]
        if not cases and args.case != 65:
            parser.error('Unknown official plugin case')
    data, digest = loader_bytes(args.loader)
    tag = 'framey-decky-runtime:'+uuid.uuid4().hex[:12]
    inputs = ['scripts/framey-test-decky-runtime.py', 'ui/framey_decky_ipc.py', 'tests/decky-runtime/check.py',
              'tests/decky-runtime/runtime_console.py', 'tests/decky-runtime/timer_lifecycle.py',
              'tests/decky-runtime/timer_private.py',
              'tests/decky-runtime/deck_settings_private.py',
              'tests/decky-runtime/deckyparty_private.py',
              'tests/decky-runtime/free_loader_private.py',
              'tests/decky-runtime/deck_shelves_private.py',
              'tests/decky-runtime/battery_private.py',
              'tests/decky-runtime/steamback_private.py',
              'tests/decky-runtime/tabmaster_private.py',
              'tests/decky-runtime/prefix_manager_private.py',
              'tests/decky-runtime/radiyo_private.py',
              'tests/decky-runtime/screensaver_private.py', 'ui/framey_screensaver.py',
              'tests/decky-runtime/surround_private.py', 'ui/framey_surround.py',
              'tests/decky-runtime/volume_mixer_private.py',
              'tests/decky-runtime/animation_private.py', 'ui/framey_animation_overrides.py',
              'tests/decky-runtime/Containerfile', 'tests/decky-runtime/cases.json',
              'tests/framey_official.py', 'ui/frame_decky_store.py',
              'tests/decky-runtime/ludusavi_private.py',
              'tests/decky-runtime/game_sync_private.py',
              'tests/decky-runtime/steamgriddb_private.py',
              'tests/decky-runtime/wine_cellar_private.py',
              'tests/decky-runtime/shotty_private.py', 'ui/framey_shotty.py',
              'tests/fixtures/framey-wine-cellar-pre-ipc.py.gz',
              'ui/vendor/wine-cellar-0.2.1/main.py.gz',
              '.github/workflows/decky-runtime.yml']
    report = {'decky': RELEASE, 'architecture': platform.machine(), 'loaderSha256': digest,
              'sourceSha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                               for name in inputs}, 'cases': []}
    try:
        subprocess.run(['docker', 'build', '-q', '-t', tag, '-f', str(ROOT/'tests/decky-runtime/Containerfile'),
                        str(ROOT/'tests/decky-runtime')], check=True, timeout=300)
        with tempfile.TemporaryDirectory(prefix='framey-decky-runtime-') as temp:
            loader = Path(temp)/'PluginLoader'
            loader.write_bytes(data)
            loader.chmod(0o644)  # Private container user copies/chmods its own executable.
            probes = [(case['id'], case.get('version'), None) for case in cases] + [
                (plugin_id, None, negative) for plugin_id, negative in [
                    (38, '--reproduce-volume-mixer-user-regression'),
                    (111, '--reproduce-bound-method-regression'), (96, '--reproduce-timer-regression'),
                    (96, '--reproduce-timer-unload-regression'),
                    (63, '--reproduce-free-loader-unload-regression'),
                    (135, '--reproduce-deck-shelves-unload-regression'),
                    (46, '--reproduce-steamback-unload-regression'),
                    (60, '--reproduce-fileserver-empty-flag-regression'),
                    (93, '--reproduce-deck-settings-unload-regression'),
                    (65, '--reproduce-terminal-import-regression'),
                    (61, '--reproduce-tabmaster-restore-regression'),
                    (61, '--reproduce-tabmaster-unload-regression'),
                    (134, '--reproduce-deck-progress-unload-regression'),
                    (68, '--reproduce-wine-cellar-unload-regression'),
                    (53, '--reproduce-shotty-unload-regression'),
                    (67, '--reproduce-battery-tracker-unload-regression'),
                    (36, '--reproduce-steamgriddb-unload-regression'),
                    (24, '--reproduce-radiyo-unload-regression'),
                    (117, '--reproduce-deckyparty-unload-regression')]
                if args.case is None or args.case == plugin_id]
            if args.case is None or args.case == 130:
                probes.append((130, '1.0.2', '--reproduce-prefix-manager-102-unload-regression'))
            for plugin_id, version, negative in probes:
                name = 'framey-decky-'+uuid.uuid4().hex[:12]
                command = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
                    '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                    '--tmpfs', '/tmp:rw,exec,mode=1777',
                    '--tmpfs', '/run/user/1100:rw,uid=1100,gid=1100,mode=700',
                    '--mount', f'type=bind,source={ROOT},target=/repo,readonly',
                    '--mount', f'type=bind,source={loader},target=/input/PluginLoader,readonly',
                    ]
                # Copyparty deliberately refuses uploads to tmpfs. Use an
                # anonymous Docker volume, populated with the image's owned
                # tester home and removed with this container, for this case.
                home_mount = (['--mount', 'type=volume,destination=/home/tester'] if plugin_id == 117 else
                              ['--tmpfs', '/home/tester:rw,exec,uid=1100,gid=1100,mode=700'])
                command += home_mount
                if plugin_id == 53:
                    # Exercise screenshots whose Pictures target is on another
                    # filesystem, rather than accidentally validating os.link.
                    command += ['--tmpfs', '/home/tester/Pictures:rw,uid=1100,gid=1100,mode=700']
                command += [tag, str(plugin_id), version or '-']
                if negative:
                    command.append(negative)
                try:
                    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                    if result.returncode:
                        raise RuntimeError(f'Decky runtime case {plugin_id} {version or "store"} failed:\n{result.stdout}\n{result.stderr}')
                    observation = json.loads(result.stdout)
                    report['cases'].append(observation)
                    print(f"PASS {plugin_id} {version or 'store'}: {observation['result']}", flush=True)
                finally:
                    subprocess.run(['docker', 'rm', '-f', '--volumes', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        subprocess.run(['docker', 'image', 'rm', tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
