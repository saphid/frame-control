"""Sample only the disposable published-loader probe and its descendants."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def listener_samples(text, native):
    """Bind listener frames to the abrupt fixture's recorded process tree."""
    abrupt = native['results'][1]
    owned = abrupt['descendantsBefore']
    groups = []
    for line in text.splitlines():
        if 'PluginWrapper._response_listener (' not in line:
            continue
        process_part, separator, frames = line.partition(';thread ')
        if not separator:
            continue
        pids = [int(p) for p in re.findall(r'(?:^|;)process (\d+):"', process_part)]
        thread = re.match(r'\((\d+)\):', frames)
        if (not pids or abrupt['loaderPid'] not in pids or not thread or
                int(thread[1]) != pids[-1] or str(pids[-1]) not in owned):
            continue
        # Do not credit a descendant of another descendant to the loader parent.
        if owned[str(pids[-1])]['parent'] != abrupt['loaderPid']:
            continue
        match = re.search(r' (\d+)$', line)
        if match and int(match[1]) > 0:
            groups.append(dict(pid=pids[-1], samples=int(match[1])))
    return dict(groups=len(groups), samples=sum(g['samples'] for g in groups),
                pids=sorted({g['pid'] for g in groups}))


def main():
    # Only this fixture adopts its own orphaned descendants. The loader and
    # transport remain unchanged; no capability or ptrace setting is added.
    code = '''import ctypes,runpy
libc=ctypes.CDLL(None,use_errno=True)
libc.prctl.argtypes=[ctypes.c_int]+[ctypes.c_ulong]*4
libc.prctl.restype=ctypes.c_int
if libc.prctl(36,1,0,0,0)!=0:
    raise OSError(ctypes.get_errno(),'private probe subreaper failed')
runpy.run_path('/repo/tests/decky-runtime/parent_eof_native.py')
'''
    command = ['/input/py-spy', 'record', '--subprocesses', '--threads', '--rate', '50',
               '--format', 'raw', '--nonblocking', '--output', '/tmp/parent-stacks.raw',
               '--', sys.executable, '-c', code]
    result = subprocess.run(command, capture_output=True, text=True, timeout=85)
    # Preserve the probe's own report even when sampling or validation fails.
    print(result.stdout, end='', flush=True)
    reports = [json.loads(line.removeprefix('PROBE_REPORT '))
               for line in result.stdout.splitlines() if line.startswith('PROBE_REPORT ')]
    assert len(reports) == 1, result.stderr[-2000:]
    native, = reports
    raw = Path('/tmp/parent-stacks.raw').read_bytes()
    assert 0 < len(raw) <= 4*1024*1024, 'stack output missing or exceeds bound'
    text = raw.decode()
    report = dict(samplerSha256=hashlib.sha256(Path('/input/py-spy').read_bytes()).hexdigest(),
                  returncode=result.returncode, stderr=result.stderr,
                  stackBytes=len(raw), stackSha256=hashlib.sha256(raw).hexdigest(),
                  stackText=text, listener=listener_samples(text, native),
                  nonblockingSampling=True, probeSubreaperEnabled=True,
                  addedCapabilities=False, realFrameContacted=False,
                  historicalCauseEstablished=False, releaseHoldCleared=False)
    print('STACK_REPORT '+json.dumps(report), flush=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert native['normalControlPassed'] and native['publishedBinaryParentHangReproduced']
    assert native['allOwnedProcessesReaped'] and report['listener']['samples'] > 0


if __name__ == '__main__':
    main()
