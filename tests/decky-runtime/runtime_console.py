"""Retain native fixture output after owned process cleanup, including failures.

Signal the owned Decky loader so it can unload its children. Auxiliary fixtures
retain process-group cleanup. Output and return codes remain diagnostics, not
a clean Decky/plugin shutdown gate.
"""
from contextlib import contextmanager
import hashlib
import json
import os
import signal
import subprocess
import sys


@contextmanager
def capture_runtime(log, report, processes, *, loader=None, stop_timeout=8, stdout=None, stderr=None):
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    probe_completed = False
    cleanup_completed = False
    stops = []
    try:
        yield
        probe_completed = True
    finally:
        try:
            for process in reversed(processes):
                is_loader = loader is not None and process.args == [str(loader)]
                stop = dict(pid=process.pid, signaledProcessGroup=False, forcedKill=False,
                            loader=is_loader, parentOnlySignal=False)
                stops.append(stop)
                try:
                    if process.poll() is None:
                        try:
                            if is_loader:
                                process.send_signal(signal.SIGTERM)
                                stop['parentOnlySignal'] = True
                            else:
                                os.killpg(process.pid, signal.SIGTERM)
                                stop['signaledProcessGroup'] = True
                        except ProcessLookupError:
                            continue
                        try:
                            process.wait(timeout=stop_timeout)
                        except subprocess.TimeoutExpired:
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                                stop['forcedKill'] = True
                            except ProcessLookupError:
                                pass
                            process.wait(timeout=stop_timeout)
                finally:
                    stop['returncode'] = process.returncode
            cleanup_completed = True
        finally:
            log.flush()
            log.seek(0)
            console = log.read()
            report['runtimeConsole'] = dict(text=console,
                sha256=hashlib.sha256(console.encode()).hexdigest(),
                probeCompleted=probe_completed, cleanupCompleted=cleanup_completed,
                processStops=stops, cleanShutdownVerified=False)
            if not probe_completed or not cleanup_completed:
                print(console, file=stderr)
    print(json.dumps(report), file=stdout)
