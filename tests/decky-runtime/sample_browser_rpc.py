"""Stdin-only browser bridge to the actual sample in its networkless container."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import traceback

import sample_settings as sample
from timer_lifecycle import Client


def reply(value):
    print(json.dumps(value), flush=True)


async def browser_cycle(cycle):
    reply(dict(stage='ready', cycle=cycle))
    for line in sys.stdin:
        request = json.loads(line)
        if request['op'] == 'rpc':
            method, args = request['method'], request['args']
            assert method in ('get_setting', 'set_setting') and isinstance(args, list) and len(args) == 2
            async with Client(sample.NAME, sample.REPORT['transcript']) as client:
                response = await client.call(method, *args, success=False)
            reply(dict(success=response['type'] == 1,
                       result=response.get('result') if response['type'] == 1 else response['error']['message']))
        elif request['op'] == 'snapshot':
            raw = sample.SETTINGS.read_bytes()
            reply(dict(value=json.loads(raw), sha256=hashlib.sha256(raw).hexdigest(),
                       mode=oct(sample.SETTINGS.stat().st_mode & 0o777)))
        elif request['op'] == 'finish':
            return  # The existing probe stops only its loader parent, then restarts it.
        else:
            raise ValueError('Unknown private browser command')
    raise RuntimeError('Browser coordinator closed before completing its cycle')


if __name__ == '__main__':
    sample.exercise = browser_cycle
    try:
        sample.main()
        # The browser cycle replaces the native-only malformed-schema cases.
        sample.REPORT.pop('malformedAndFutureSchemaPreserved', None)
        sample.REPORT.update(browserVerified=True, syntheticParentBridge=True)
    except Exception:
        sample.REPORT.update(success=False, error=traceback.format_exc())
    finally:
        sample.REPORT['forcedFixtureCleanup'] = []
        for process in reversed(sample.PROCESSES):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
                    sample.REPORT['forcedFixtureCleanup'].append(process.pid)
        log = Path('/home/tester/sample-runtime.log')
        if log.exists():
            sample.REPORT.update(console=log.read_text(), consoleSha256=hashlib.sha256(log.read_bytes()).hexdigest())
        reply(dict(stage='complete', report=sample.REPORT))
    raise SystemExit(0 if sample.REPORT['success'] else 1)
