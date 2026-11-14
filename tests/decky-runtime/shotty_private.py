"""Qualify only the private Shotty plugin owned by this disposable Decky loader."""
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


def identity(pid):
    try:
        fields = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()
        return dict(state=fields[0], parent=int(fields[1]), start=fields[19])
    except FileNotFoundError:
        return None


def stop(backend, log, *, regression):
    children = {int(p.name): state for p in Path('/proc').iterdir() if p.name.isdigit()
                if (state := identity(int(p.name))) and state['parent'] == backend.pid}
    assert children, 'the loader must own a plugin child before stopping'
    assert all(os.getpgid(pid) == backend.pid for pid in children)
    log.flush()
    before = Path(log.name).read_text()
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    elapsed = time.monotonic()-started
    log.flush()
    console = Path(log.name).read_text()[len(before):]
    remaining = {pid: state for pid, old in children.items()
                 if (state := identity(pid)) and state['start'] == old['start']}
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [m for m in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if m in console]
    clean = (backend.returncode == 0 and not remaining and not forced and not errors
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and '[plugin][INFO]: Plugin Shotty (v0.1.0) has been stopped in ' in console)
    observation = dict(loaderPid=backend.pid, childrenBefore=children,
        exactChildrenRemaining=remaining, parentOnlySignal=True,
        loaderReturncode=backend.returncode, seconds=round(elapsed, 3),
        forcedPluginKills=forced, console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean, expectedRegression=regression)
    if regression:
        assert not clean and forced == 1 and backend.returncode == 0, observation
    else:
        assert clean and elapsed < 3, observation
    return observation


def probe(backend, loader, env, log, processes, legacy, rpc, until_ready, *, regression):
    stops = []
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        for cycle in range(1 if regression else 2):
            stops.append(stop(backend, log, regression=regression))
            assert unrelated.poll() is None, 'unrelated sibling must survive loader shutdown'
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Shotty discovery')
                assert legacy('was_rescued') is False
        log.flush()
        console = Path(log.name).read_text()
        return dict(stops=stops, unrelatedSiblingPreserved=True,
                    console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
                    cleanShutdownVerified=not regression, expectedRegression=regression,
                    realFrameContacted=False, physicalControllerVerified=False)
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        unrelated.wait(timeout=3)
