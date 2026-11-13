#!/usr/bin/env python3
"""Verify the uninstalled Syncthing candidate in native published Decky 3.3.0."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
DIGEST = '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, required=True, help='Locally built native candidate, never the original ZIP helper')
    parser.add_argument('--archive', type=Path, help='Optional cached exact official ZIP')
    parser.add_argument('--loader', type=Path, help='Optional cached published Decky 3.3.0 loader')
    parser.add_argument('--image', help='Optional prepared native test image; never removed')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('native_decky', ROOT/'scripts/framey-test-decky-runtime.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    loader, loader_digest = native.loader_bytes(args.loader)
    helper = args.helper.read_bytes()
    source_paths = ['scripts/framey-test-syncthing-candidate.py',
                    'tests/decky-runtime/Containerfile',
                    'tests/decky-runtime/syncthing_candidate.py',
                    'ui/vendor/syncthing-0.2.7/main.py', 'ui/framey_decky_ipc.py',
                    'ui/vendor/syncthing-0.2.7/watchdog.patch',
                    'ui/vendor/syncthing-0.2.7/owned_unit.rs']
    source_hashes = {path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in source_paths}
    machine = native.LOADERS[platform.machine()][2]
    if helper[:4] != b'\x7fELF' or int.from_bytes(helper[18:20], 'little') != machine:
        raise ValueError('Candidate helper does not match native runner architecture')
    if args.archive:
        archive = args.archive.read_bytes()
    else:
        request = urllib.request.Request(
            'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/'+DIGEST+'.zip',
            headers={'User-Agent':'Frame-Control-candidate-tests'})
        with urllib.request.urlopen(request, timeout=60) as response:
            archive = response.read(50*1024*1024+1)
    if hashlib.sha256(archive).hexdigest() != DIGEST:
        raise ValueError('Official Syncthing archive mismatch')
    tag = args.image or 'framey-syncthing-candidate:'+uuid.uuid4().hex[:12]
    name = 'framey-syncthing-candidate-'+uuid.uuid4().hex[:12]
    try:
        if not args.image:
            subprocess.run(['docker', 'build', '-q', '-t', tag, '-f', str(ROOT/'tests/decky-runtime/Containerfile'),
                            str(ROOT/'tests/decky-runtime')], check=True, timeout=300)
        image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', tag]))[0]
        expected = {'x86_64':'amd64', 'aarch64':'arm64'}[platform.machine()]
        if image['Architecture'] != expected:
            raise ValueError('Candidate image does not match native runner architecture')
        with tempfile.TemporaryDirectory(prefix='framey-syncthing-probe-') as temp:
            inputs = Path(temp)
            for filename, data in [('watchdog', helper), ('PluginLoader', loader), ('official.zip', archive)]:
                (inputs/filename).write_bytes(data)
                (inputs/filename).chmod(0o644)
            command = ['docker', 'run', '--rm', '--init', '--name', name, '--network', 'none', '--read-only',
                       '--user', '1100:1100',
                       '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                       '--tmpfs', '/tmp:rw,exec,mode=1777',
                       '--tmpfs', '/run/user/1100:rw,uid=1100,gid=1100,mode=700',
                       '--tmpfs', '/home/tester:rw,exec,uid=1100,gid=1100,mode=700',
                       '--mount', f'type=bind,source={ROOT},target=/repo,readonly']
            for filename in ('watchdog', 'PluginLoader', 'official.zip'):
                command += ['--mount', f'type=bind,source={inputs/filename},target=/input/{filename},readonly']
            command += ['--entrypoint', 'python3', image['Id'], '/repo/tests/decky-runtime/syncthing_candidate.py']
            result = subprocess.run(command, capture_output=True, text=True, timeout=210)
            if result.returncode:
                raise RuntimeError('Native candidate failed:\n'+result.stdout+'\n'+result.stderr)
            report = json.loads(result.stdout)
            if any(hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest
                   for path, digest in source_hashes.items()):
                raise RuntimeError('Candidate inputs changed during the native probe')
            report.update(decky=native.RELEASE, loaderSha256=loader_digest, architecture=platform.machine())
            report.update(image=image['Id'], providedImage=bool(args.image))
            report['sourceSha256'] = source_hashes
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2)+'\n')
            print(report['result'])
    finally:
        subprocess.run(['docker', 'rm', '-f', '--volumes', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not args.image:
            subprocess.run(['docker', 'image', 'rm', tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
