"""Failure-only read-only status profiling in an owned, networkless VM.

This runs after the real production replay has already failed. Its modified
Python invocation never substitutes for that replay or changes its deadline.
Raw status replies, stderr, paths and stack source lines are not retained.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time


def summarize_stderr(raw):
    imports, frames = [], []
    for line in raw.decode(errors='replace').splitlines():
        match = re.fullmatch(r'import time:\s+(\d+)\s+\|\s+(\d+)\s+\|\s+([A-Za-z0-9_.]+)', line)
        if match:
            own, total, module = match.groups()
            imports.append(dict(module=module[:120], selfMicroseconds=int(own),
                                cumulativeMicroseconds=int(total)))
        match = re.fullmatch(r'\s*File "([^"]+)", line (\d+) in ([A-Za-z0-9_<>]+)', line)
        if match:
            filename, number, function = match.groups()
            filename = Path(filename).name
            if re.fullmatch(r'[A-Za-z0-9_.<>-]{1,100}', filename):
                frames.append(dict(file=filename, line=int(number), function=function[:100]))
    return dict(importRecordCount=len(imports),
                slowestImports=sorted(imports, key=lambda row: row['cumulativeMicroseconds'], reverse=True)[:30],
                lastImports=imports[-20:], sampledFrames=frames[-60:])


def collect(source, directory, *, timeout=35, sample_seconds=5):
    """Capture only bounded summaries; every child belongs to this invocation."""
    assert 0 < len(source.encode()) <= 256 * 1024
    assert 0 < timeout <= 35 and 0 < sample_seconds <= 5
    compile(source, '<decky-read-only-status>', 'exec')
    # The original source is executed verbatim; import timing and faulthandler
    # are diagnostic additions to the invocation, explicitly reported below.
    wrapper = ('import faulthandler\n'
               'faulthandler.dump_traceback_later('+repr(sample_seconds)+', repeat=True)\n'
               'try:\n exec(compile('+repr(source)+', "<decky-read-only-status>", "exec"), {})\n'
               'finally:\n faulthandler.cancel_dump_traceback_later()\n')
    began = time.monotonic()
    report = dict(diagnosticOnly=True, invocationModified=True,
                  productionReplayReplaced=False, productionDeadlineChanged=False,
                  sourceSha256=hashlib.sha256(source.encode()).hexdigest(),
                  timeoutSeconds=timeout, timedOut=False, ownedProcessReaped=False)
    process = None
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen([sys.executable, '-X', 'importtime', '-'],
                stdin=subprocess.PIPE, stdout=output, stderr=errors,
                cwd=directory, start_new_session=True)
            try:
                process.communicate(wrapper.encode(), timeout=timeout)
            except subprocess.TimeoutExpired:
                report['timedOut'] = True
        finally:
            if process is not None:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=3)
                report.update(exitStatus=process.returncode,
                              ownedProcessReaped=process.poll() is not None)
                if process.stdin is not None:
                    process.stdin.close()
            report['elapsedSeconds'] = round(time.monotonic()-began, 3)
        assert report['ownedProcessReaped']
        output.seek(0); errors.seek(0)
        stdout, stderr = output.read(256*1024+1), errors.read(256*1024+1)
    report['outputLimitExceeded'] = len(stdout) > 256*1024 or len(stderr) > 256*1024
    if not report['outputLimitExceeded']:
        report.update(summarize_stderr(stderr))
        try:
            value = json.loads(stdout)
            if isinstance(value, dict):
                report['statusSummary'] = {key: value[key] for key in ('managed', 'running', 'cef')
                                          if type(value.get(key)) is bool}
                if isinstance(value.get('plugins'), list):
                    report['statusSummary']['pluginCount'] = len(value['plugins'])
        except (ValueError, UnicodeError):
            report['statusJsonUnavailable'] = True
    return report


def diagnose(source, home):
    assert os.getuid() == 1100 and home == Path('/home/tester')
    assert Path('/framey-owned-vm').read_bytes() == b'Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    report = collect(source, home)
    report.update(afterFailedProductionReplay=True, realFrameContacted=False,
                  physicalControllerVerified=False)
    return report
