#!/usr/bin/env python3
"""Collect native parent EOF stacks without changing the published loader.

Downloads and image preparation use network. The owned experiment cannot.
This is diagnostic evidence, not proof of the historical ARM64 timeout cause.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SAMPLERS = {
    'x86_64': ('manylinux1_x86_64.manylinux_2_5_x86_64',
               '8a4277225f470d394a85cca0cdd944bef87f0097b6f20150a6dd3ac2e92806b8', 62),
    'aarch64': ('manylinux2014_aarch64.manylinux_2_17_aarch64',
                'bbcec46930d464b3bfc142d6d02ade4dd8ad5627823263b3eff0280e80c7c132', 183),
}
INPUTS = ['scripts/framey-probe-decky-parent-stacks.py',
          'scripts/framey-test-decky-runtime.py', 'tests/decky-runtime/parent_eof_stacks.py',
          'tests/decky-runtime/parent_eof_native.py', 'tests/decky-runtime/Containerfile',
          'tests/decky-runtime/check.py', 'tests/decky-runtime/deck_settings_private.py',
          'ui/framey_decky_ipc.py', '.github/workflows/decky-parent-stacks.yml']


def sampler_bytes(path, arch):
    tag, expected, machine = SAMPLERS[arch]
    wheel = f'py_spy-0.4.3-py2.py3-none-{tag}.whl'
    url = 'https://github.com/benfred/py-spy/releases/download/v0.4.3/'+wheel
    if path:
        raw = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=45) as response:
            raw = response.read(8*1024*1024+1)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Sampler wheel digest mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        member, = [m for m in archive.infolist() if m.filename.endswith('.data/scripts/py-spy')]
        if member.file_size > 16*1024*1024:
            raise ValueError('Sampler executable exceeds bound')
        data = archive.read(member)
    if data[:4] != b'\x7fELF' or int.from_bytes(data[18:20], 'little') != machine:
        raise ValueError('Sampler is not native ELF')
    return data, dict(url=url, wheelSha256=expected,
                      executableSha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader', type=Path)
    parser.add_argument('--sampler-wheel', type=Path)
    parser.add_argument('--image', help='Reuse this prepared local image; never remove it')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    arch = platform.machine()
    if sys.platform != 'linux' or arch not in SAMPLERS or not shutil.which('docker'):
        parser.error('Native Linux AMD64/ARM64 and Docker required')
    runtime = runpy.run_path(str(ROOT/'scripts/framey-test-decky-runtime.py'))
    loader, loader_digest = runtime['loader_bytes'](args.loader)
    sampler, provenance = sampler_bytes(args.sampler_wheel, arch)
    token = 'framey-parent-stacks-'+uuid.uuid4().hex[:12]
    image = args.image or token
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = dict(architecture=arch, loaderSha256=loader_digest, sampler=provenance,
                  sourceSha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in INPUTS},
                  realFrameContacted=False, historicalArm64VmExecuted=False,
                  historicalCauseEstablished=False, releaseHoldCleared=False)
    try:
        with tempfile.TemporaryDirectory(prefix=token+'-') as temp:
            folder = Path(temp)
            if not args.image:
                with (args.output/'image-build.log').open('w') as log:
                    subprocess.run(['docker', 'build', '-q', '-t', image, '-f',
                                    str(ROOT/'tests/decky-runtime/Containerfile'), temp],
                                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
            (folder/'PluginLoader').write_bytes(loader)
            (folder/'PluginLoader').chmod(0o644)
            (folder/'py-spy').write_bytes(sampler)
            (folder/'py-spy').chmod(0o755)
            command = ['docker', 'run', '--rm', '--name', token, '--network', 'none', '--read-only',
                       '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                       '--cpus', '0.5', '--memory', '2g',
                       '--tmpfs', '/tmp:rw,exec,mode=1777',
                       '--tmpfs', '/run/user/1100:rw,uid=1100,gid=1100,mode=700',
                       '--tmpfs', '/home/tester:rw,exec,uid=1100,gid=1100,mode=700',
                       '--mount', 'type=bind,source='+str(ROOT)+',target=/repo,readonly',
                       '--mount', 'type=bind,source='+str(folder)+',target=/input,readonly',
                       '--entrypoint', 'python3', image, '/repo/tests/decky-runtime/parent_eof_stacks.py']
            # TemporaryDirectory is private; the unprivileged container needs
            # traversal and read access only to these two verified public inputs.
            folder.chmod(0o755)
            with (args.output/'container.log').open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=95)
            lines = (args.output/'container.log').read_text().splitlines()
            for prefix, key in [('PROBE_REPORT ', 'native'), ('STACK_REPORT ', 'stacks')]:
                matches = [json.loads(line.removeprefix(prefix)) for line in lines if line.startswith(prefix)]
                if len(matches) == 1:
                    report[key] = matches[0]
            report['containerReturncode'] = result.returncode
            assert result.returncode == 0, 'Experiment failed; inspect retained container.log'
            native, stacks = report['native'], report['stacks']
            assert native['architecture'] == arch and native['loaderSha256'] == loader_digest
            assert native['normalControlPassed'] and native['publishedBinaryParentHangReproduced']
            assert native['allOwnedProcessesReaped'] and native['parentUnmodified']
            assert not native['historicalCauseEstablished'] and not native['releaseHoldCleared']
            assert stacks['samplerSha256'] == provenance['executableSha256']
            raw = stacks.pop('stackText').encode()
            assert len(raw) == stacks['stackBytes'] and hashlib.sha256(raw).hexdigest() == stacks['stackSha256']
            (args.output/'stacks.raw').write_bytes(raw)
            verifier = runpy.run_path(str(ROOT/'tests/decky-runtime/parent_eof_stacks.py'))
            assert verifier['listener_samples'](raw.decode(), native) == stacks['listener']
            assert stacks['listener']['samples'] > 0
            report['diagnosticPassed'] = True
    finally:
        cleanup = subprocess.run(['docker', 'rm', '-f', token], capture_output=True, text=True, timeout=15)
        remaining = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'name=^/'+token+'$'], text=True, timeout=15).strip()
        report.update(ownedContainerRemoved=not remaining, containerCleanupReturncode=cleanup.returncode)
        if not args.image:
            deleted = subprocess.run(['docker', 'image', 'rm', '-f', image], capture_output=True, text=True, timeout=30)
            report['ownedImageRemoved'] = deleted.returncode == 0
        (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if not report['ownedContainerRemoved'] or (not args.image and not report['ownedImageRemoved']):
        raise RuntimeError('Owned Docker cleanup incomplete')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
