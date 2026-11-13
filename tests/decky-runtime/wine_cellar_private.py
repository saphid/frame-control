"""Read-only native Wine Cask RPCs and parent-only Decky unload in private containers."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def identity(pid):
    try:
        fields = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()
        return dict(state=fields[0], parent=int(fields[1]), start=fields[19])
    except FileNotFoundError:
        return None


def failed_unload_evidence(observation):
    """Keep the original failure negative whether its owned helper died or survived."""
    samples = [sample['child'] for sample in observation['samples']
               if sample['child'] and sample['child']['start'] == observation['childBefore']['start']]
    zombie = any(child['state'] == 'Z' for child in samples)
    orphan = observation['exactChildRemaining'] and any(
        child['parent'] == 1 and child['state'] in ('R', 'S', 'D', 'T', 't', 'I')
        for child in samples)
    assert observation['parentOnlySignal'] and observation['cleanShutdownVerified'] is False, observation
    assert observation['forcedPluginKills'] == 1 and observation['loaderReturncode'] == 0, observation
    assert 'Shutdown finished.' in observation['console'] and (zombie or orphan), observation
    return dict(zombieObserved=zombie, liveOrphanObserved=bool(orphan))


def stop(backend, helper, log, *, regression):
    log.flush()
    before = Path(log.name).read_text()
    pid = int(re.findall(r'Wine Cask started with PID (\d+)', before)[-1])
    child = identity(pid)
    assert child and (Path('/proc')/str(pid)/'exe').resolve() == helper.resolve()
    assert os.getpgid(pid) == backend.pid
    ancestors = []
    parent_pid = child['parent']
    for _ in range(10):
        ancestors.append(parent_pid)
        if parent_pid == backend.pid:
            break
        parent = identity(parent_pid)
        assert parent and parent_pid > 1, 'helper must belong to this owned Decky loader'
        parent_pid = parent['parent']
    assert ancestors[-1] == backend.pid, ancestors
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)  # no process-group signal during qualification
    samples = []
    while backend.poll() is None and time.monotonic()-started < 8:
        samples.append(dict(seconds=round(time.monotonic()-started, 3), child=identity(pid)))
        time.sleep(.05)
    log.flush()
    console = Path(log.name).read_text()[len(before):]
    remaining = identity(pid)
    exact_child_remaining = remaining is not None and remaining['start'] == child['start']
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    clean = (backend.returncode == 0 and not exact_child_remaining and forced == 0
             and 'Unloaded Wine Cellar' in console and 'Shutdown finished.' in console
             and 'Wine Cask stopped with exit code -15' in console
             and 'Bad file descriptor' not in console and 'CancelledError' not in console
             and 'Failed to unload' not in console
             and 'Task was destroyed but it is pending' not in console)
    observation = dict(loaderPid=backend.pid, helperPid=pid, childBefore=child, ancestors=ancestors,
        parentOnlySignal=True, loaderReturncode=backend.returncode,
        seconds=round(time.monotonic()-started, 3), samples=samples,
        exactChildRemaining=exact_child_remaining, forcedPluginKills=forced,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean, expectedRegression=regression)
    if regression:
        observation['failedUnloadEvidence'] = failed_unload_evidence(observation)
    else:
        assert clean, observation
    return observation


def probe(backend, helper, loader, env, log, processes, current, rpc, until_ready, *, regression):
    observations = []
    state_readbacks = []
    for cycle in range(1 if regression else 2):
        token = until_ready(lambda: current('framey_ws_open'), 'private Wine Cellar helper')
        assert isinstance(token, str) and len(token) == 32
        assert current('framey_ws_send', token, '{"type":"GetState"}') is None
        reply = until_ready(lambda: next((json.loads(message) for message in
            current('framey_ws_poll', token)['messages'] if json.loads(message).get('type') == 'UpdateState'),
            None), 'read-only Wine Cellar state')
        assert reply['app_state']['installed_tools'] == []
        state_readbacks.append(reply)
        socket_open = not regression and cycle == 0
        if not socket_open:
            assert current('framey_ws_close', token) is None
        observation = stop(backend, helper, log, regression=regression)
        observation['socketOpenAtUnload'] = socket_open
        observations.append(observation)
        if not regression and cycle == 0:
            backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                       start_new_session=True)
            processes.append(backend)
            until_ready(lambda: rpc('loader/get_plugins'), 'restarted Wine Cellar discovery')
    log.flush()
    console = Path(log.name).read_text()
    return dict(wineCellarLifecycle=dict(stops=observations, readbacks=state_readbacks,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=not regression, expectedRegression=regression),
        result=('prior managed IPC EOF failure reproduced: unreaped helper and Decky forced plugin stop; '
                'negative control only, not clean qualification' if regression else
                'actual Decky 3.3.0 discovery, two read-only native helper state replies and two '
                'parent-only zero-exit loader stops with reaped children; no install/uninstall, Frame or VR test'))
