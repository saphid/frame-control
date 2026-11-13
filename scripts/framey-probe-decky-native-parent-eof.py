#!/usr/bin/env python3
"""Bounded parent EOF experiment in a native published Decky 3.3.0 binary.

Build/download may use network; the disposable loader container cannot. This
diagnostic does not establish the historical ARM64 VM timeout's cause.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ['scripts/framey-probe-decky-native-parent-eof.py',
          'scripts/framey-test-decky-runtime.py',
          'tests/decky-runtime/parent_eof_native.py',
          'tests/decky-runtime/Containerfile', 'tests/decky-runtime/check.py',
          'tests/decky-runtime/deck_settings_private.py', 'ui/framey_decky_ipc.py',
          '.github/workflows/decky-native-parent-eof.yml']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader', type=Path, help='Cached native loader; digest and ELF architecture verified')
    parser.add_argument('--image', help='Reuse a prepared local test image; do not remove it')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or not shutil.which('docker'):
        parser.error('Native Linux and Docker are required')
    runtime = runpy.run_path(str(ROOT/'scripts/framey-test-decky-runtime.py'))
    data, digest = runtime['loader_bytes'](args.loader)
    token = 'framey-parent-eof-'+uuid.uuid4().hex[:12]
    image = args.image or token
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    report = dict(architecture=platform.machine(), loaderSha256=digest,
                  sourceSha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in INPUTS},
                  realFrameContacted=False, historicalCauseEstablished=False, releaseHoldCleared=False)
    try:
        with tempfile.TemporaryDirectory(prefix=token+'-') as temp:
            folder = Path(temp)
            # The Containerfile copies no files. Keep .git and unrelated inputs
            # out of the image build context.
            if not args.image:
                with (args.output/'image-build.log').open('w') as log:
                    subprocess.run(['docker', 'build', '-q', '-t', image, '-f',
                                    str(ROOT/'tests/decky-runtime/Containerfile'), temp],
                                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
            loader = folder/'PluginLoader'
            loader.write_bytes(data)
            command = ['docker', 'run', '--rm', '--name', token, '--network', 'none', '--read-only',
                       '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                       '--cpus', '0.5', '--memory', '2g',
                       '--tmpfs', '/tmp:rw,exec,mode=1777',
                       '--tmpfs', '/run/user/1100:rw,uid=1100,gid=1100,mode=700',
                       '--tmpfs', '/home/tester:rw,exec,uid=1100,gid=1100,mode=700',
                       '--mount', 'type=bind,source='+str(ROOT)+',target=/repo,readonly',
                       '--mount', 'type=bind,source='+str(loader)+',target=/input/PluginLoader,readonly',
                       '--entrypoint', 'python3', image, '/repo/tests/decky-runtime/parent_eof_native.py']
            with (args.output/'container.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=95)
            lines = (args.output/'container.log').read_text().splitlines()
            reports = [json.loads(line.removeprefix('PROBE_REPORT ')) for line in lines if line.startswith('PROBE_REPORT ')]
            assert len(reports) == 1
            native, = reports
            report['native'] = native
            assert native['architecture'] == report['architecture']
            assert native['loaderSha256'] == digest
            assert native['normalControlPassed'] is True
            assert native['publishedBinaryParentHangReproduced'] is True
            assert native['allOwnedProcessesReaped'] is True
            assert native['parentUnmodified'] and native['childEofRepairPresent']
            assert native['nativeArm64Executed'] is (platform.machine() == 'aarch64')
            for key in ['realFrameContacted', 'historicalArm64VmExecuted', 'historicalCauseEstablished', 'releaseHoldCleared']:
                assert native[key] is False
            normal, abrupt = native['results']
            assert normal['mode'] == 'normal' and abrupt['mode'] == 'abrupt-child-exit'
            assert normal['console'].count('[main][INFO]: Shutdown finished.') == 1
            assert not abrupt['console'].count('[main][INFO]: Shutting down...')
            assert any(ticks[0] > 0 for ticks in abrupt['cpuTickDeltas'].values())
            assert all(not item['remainingAfterCleanup'] for item in native['results'])
            report['diagnosticPassed'] = True
    finally:
        # Only this invocation's unique container and image are eligible.
        cleanup = subprocess.run(['docker', 'rm', '-f', token], capture_output=True, text=True, timeout=15)
        remaining = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'name=^/'+token+'$'], text=True, timeout=15).strip()
        report['ownedContainerRemoved'] = not remaining
        report['containerCleanupReturncode'] = cleanup.returncode
        if not args.image:
            deleted = subprocess.run(['docker', 'image', 'rm', '-f', image], capture_output=True, text=True, timeout=30)
            report['ownedImageRemoved'] = deleted.returncode == 0
        (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if not report['ownedContainerRemoved'] or (not args.image and not report['ownedImageRemoved']):
        raise RuntimeError('Owned Docker cleanup incomplete')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
