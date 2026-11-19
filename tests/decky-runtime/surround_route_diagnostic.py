"""Private runtime evidence: observe actual pactl moves without retrying them."""
import json
from pathlib import Path
import subprocess
import sys

TRACE = Path('/tmp/framey-surround-command-trace.jsonl')
WRAPPER = r'''#!/usr/bin/python3
import json, os, signal, subprocess, sys, time
args = sys.argv[1:]
if not args or args[0] != 'move-sink-input':
    os.execv('/usr/bin/pactl', ['pactl', *args])
started = time.monotonic_ns()
result = subprocess.run(['/usr/bin/pactl', *args], capture_output=True)
record = dict(args=args, startedMonotonicNs=started,
              finishedMonotonicNs=time.monotonic_ns(), returncode=result.returncode,
              stdout=result.stdout[:4096].decode(errors='replace'),
              stderr=result.stderr[:4096].decode(errors='replace'),
              stdoutTruncated=len(result.stdout)>4096,
              stderrTruncated=len(result.stderr)>4096)
path = '/tmp/framey-surround-command-trace.jsonl'
try:
    fd = os.open(path, os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_size < 65536:
            os.write(fd, (json.dumps(record)+'\n').encode())
    finally:
        os.close(fd)
except OSError:
    # Observation failure must not replace the actual command's result.
    pass
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
if result.returncode < 0:
    signal.signal(-result.returncode, signal.SIG_DFL)
    os.kill(os.getpid(), -result.returncode)
sys.exit(result.returncode)
'''


def install(tools):
    path = tools / 'pactl'
    path.write_text(WRAPPER)
    path.chmod(0o700)


def dump(env):
    """Bounded observations after the original probe result; never mask it."""
    record = dict(privateAudioOnly=True, noRetry=True, observations={})
    try:
        if TRACE.exists():
            with TRACE.open('rb') as stream:
                data = stream.read(65537)
            record['traceTruncated'] = len(data) > 65536
            record['moveCommands'] = [json.loads(line) for line in data[:65536].splitlines()
                                      if line.endswith(b'}')]
        else:
            record['moveCommands'] = []
        for name, args in [('inputs', ['/usr/bin/pactl', '-f', 'json', 'list', 'sink-inputs']),
                           ('sinks', ['/usr/bin/pactl', '-f', 'json', 'list', 'sinks']),
                           ('metadata', ['/usr/bin/pw-metadata', '-n', 'default'])]:
            try:
                result = subprocess.run(args, env=env, capture_output=True, timeout=3)
                record['observations'][name] = dict(returncode=result.returncode,
                    stdout=result.stdout[:16384].decode(errors='replace'),
                    stderr=result.stderr[:4096].decode(errors='replace'),
                    stdoutTruncated=len(result.stdout)>16384,
                    stderrTruncated=len(result.stderr)>4096)
            except subprocess.TimeoutExpired:
                record['observations'][name] = dict(timedOut=True, originalLimitSeconds=3)
    except Exception as error:
        record['diagnosticErrorType'] = type(error).__name__
    try:
        print('SURROUND_PRIVATE_COMMAND_DIAGNOSTIC '+json.dumps(record), file=sys.stderr, flush=True)
    except OSError:
        # A closed evidence stream must not replace the original probe failure.
        pass
