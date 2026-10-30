#!/usr/bin/env python3
"""Test real Syncthing and the uninstalled candidate in isolated native Decky.

Downloads digest-pinned test inputs, never installs them on the host or Frame.
Service management remains disabled; this does not prove systemd/DBus control.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'v2.1.7'
DIGEST = '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'
RUNTIMES = {
    'x86_64': ('amd64', '2edc416e7ed136b7c858ed5f3f02a3b8316589605e54c380228ceea7acbf0142',
               'f5c12679f2bad1b5eff619ba7b04ead1a457e439a1e55dc640d4d8995d7f4dbd', 62),
    'aarch64': ('arm64', '48e456690cd2b97e7d26b02b5ac35f62a3b36172267b144cfeaf02c993ab955c',
                '3381c439af70c31db557d02581d0665d279f9efac1d0ea6806835a5b80dc65c7', 183),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def download(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent':'Frame-Control-runtime-preflight'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(limit+1)
    if len(data) > limit:
        raise ValueError('Runtime test input exceeds its limit')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--archive', type=Path, help='Cached exact official plugin ZIP')
    parser.add_argument('--syncthing-archive', type=Path, help='Cached pinned native Syncthing tarball')
    parser.add_argument('--loader', type=Path, help='Cached published Decky 3.3.0 loader')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    arch = platform.machine()
    if platform.system() != 'Linux' or arch not in RUNTIMES:
        parser.error('Run on native Linux AMD64 or ARM64 with Docker')
    dist, packed_sha, binary_sha, machine = RUNTIMES[arch]
    filename = f'syncthing-linux-{dist}-{VERSION}.tar.gz'
    url = f'https://github.com/syncthing/syncthing/releases/download/{VERSION}/{filename}'
    packed = args.syncthing_archive.read_bytes() if args.syncthing_archive else download(url, 25*1024*1024)
    if sha(packed) != packed_sha:
        raise ValueError('Pinned Syncthing archive digest mismatch')
    # Read only this regular member; do not extract the archive onto disk.
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as archive:
        member = archive.getmember(f'syncthing-linux-{dist}-{VERSION}/syncthing')
        if not member.isfile() or member.size > 40*1024*1024:
            raise ValueError('Unexpected Syncthing executable member')
        runtime = archive.extractfile(member).read()
    if sha(runtime) != binary_sha:
        raise ValueError('Pinned Syncthing executable digest mismatch')
    helper = args.helper.read_bytes()
    for data in (runtime, helper):
        if data[:4] != b'\x7fELF' or int.from_bytes(data[18:20], 'little') != machine:
            raise ValueError('Runtime test executable has the wrong native architecture')
    spec = importlib.util.spec_from_file_location('native_decky', ROOT/'scripts/framey-test-decky-runtime.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    loader, loader_sha = native.loader_bytes(args.loader)
    official = (args.archive.read_bytes() if args.archive else download(
        'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/'+DIGEST+'.zip', 50*1024*1024))
    if sha(official) != DIGEST:
        raise ValueError('Official Syncthing plugin archive digest mismatch')
    paths = ['scripts/framey-test-syncthing-runtime.py', 'tests/decky-runtime/syncthing_runtime.py',
             'ui/vendor/syncthing-0.2.7/main.py', 'ui/vendor/syncthing-0.2.7/watchdog.patch',
                    'ui/vendor/syncthing-0.2.7/owned_unit.rs']
    sources = {path:sha((ROOT/path).read_bytes()) for path in paths}
    tag = 'framey-syncthing-runtime:'+uuid.uuid4().hex[:12]
    name = 'framey-syncthing-runtime-'+uuid.uuid4().hex[:12]
    try:
        subprocess.run(['docker', 'build', '-q', '-t', tag, '-f', str(ROOT/'tests/decky-runtime/Containerfile'),
                        str(ROOT/'tests/decky-runtime')], check=True, timeout=300)
        with tempfile.TemporaryDirectory(prefix='framey-syncthing-runtime-') as temp:
            inputs = Path(temp)
            command = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
                       '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                       '--tmpfs', '/tmp:rw,exec,mode=1777',
                       '--tmpfs', '/run/user/1100:rw,uid=1100,gid=1100,mode=700',
                       '--tmpfs', '/home/tester:rw,exec,uid=1100,gid=1100,mode=700',
                       '--mount', f'type=bind,source={ROOT},target=/repo,readonly']
            for filename, data in [('syncthing', runtime), ('watchdog', helper),
                                   ('PluginLoader', loader), ('official.zip', official)]:
                (inputs/filename).write_bytes(data)
                (inputs/filename).chmod(0o644)
                command += ['--mount', f'type=bind,source={inputs/filename},target=/input/{filename},readonly']
            command += ['--entrypoint', 'python3', tag, '/repo/tests/decky-runtime/syncthing_runtime.py']
            result = subprocess.run(command, capture_output=True, text=True, timeout=180)
            if result.returncode:
                raise RuntimeError('Actual Syncthing runtime failed:\n'+result.stdout+'\n'+result.stderr)
            report = json.loads(result.stdout)
            if any(sha((ROOT/path).read_bytes()) != digest for path, digest in sources.items()):
                raise RuntimeError('Runtime probe inputs changed while running')
            if report['binarySha256'] != binary_sha or report['helperSha256'] != sha(helper):
                raise RuntimeError('Runtime probe executable fingerprints differ')
            report.update(architecture=arch, decky=native.RELEASE, loaderSha256=loader_sha,
                          runtimeArchiveSha256=packed_sha, runtimeArchiveUrl=url, sourceSha256=sources)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2)+'\n')
            print('Actual Syncthing two-way sync, restart and Decky private HTTP RPC passed; '
                  'DBus/service management, managed install, browser, Frame and VR unverified')
    finally:
        subprocess.run(['docker', 'rm', '-f', '--volumes', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'image', 'rm', tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
