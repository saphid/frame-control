"""Verify only the owned SteamGridDB child and private artwork/settings."""
import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import base64


def identity(pid):
    try:
        fields = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()
        return dict(state=fields[0], parent=int(fields[1]), start=fields[19])
    except FileNotFoundError:
        return None


def descendants(parent):
    states = {int(p.name): state for p in Path('/proc').iterdir() if p.name.isdigit()
              if (state := identity(int(p.name)))}
    owned = {parent}
    while True:
        added = {pid for pid, state in states.items() if state['parent'] in owned} - owned
        if not added:
            return {pid: states[pid] for pid in owned - {parent}}
        owned.update(added)


def stop(backend, log, *, disconnect):
    children = descendants(backend.pid)
    assert children, 'the private loader must own its children'
    before = Path(log.name).read_text()
    closed_peers = []
    if disconnect:
        for path in Path('/tmp').glob('plugin_socket_*'):
            assert path.is_socket() and path.stat().st_uid == os.getuid()
            with socket.socket(socket.AF_UNIX) as peer:
                peer.settimeout(.2)
                try:
                    peer.connect(str(path))
                except ConnectionRefusedError:
                    continue
                peer.shutdown(socket.SHUT_WR)
                closed_peers.append(str(path))
        assert len(closed_peers) == 1, closed_peers
        time.sleep(.05)
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    console = Path(log.name).read_text()[len(before):]
    # The fixture is container PID1. Reap only recorded adopted descendants;
    # never signal the plugin or its process group to manufacture a clean stop.
    adopted = []
    deadline = time.monotonic()+2
    while True:
        for pid, old in children.items():
            state = identity(pid)
            if state and state['start'] == old['start']:
                try:
                    child, status = os.waitpid(pid, os.WNOHANG)
                    if child:
                        adopted.append(dict(pid=child, returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:
                    pass
        remaining = {pid: state for pid, old in children.items()
                     if (state := identity(pid)) and state['start'] == old['start']}
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(.01)
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [marker for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if marker in console]
    clean = (backend.returncode == 0 and not remaining and not forced and not errors
             and all(child['returncode'] == 0 for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin SteamGridDB (v1.8.1) has been stopped in ' in console)
    observation = dict(loaderPid=backend.pid, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted, parentOnlySignal=True,
        loaderReturncode=backend.returncode, seconds=round(time.monotonic()-started, 3),
        fixtureClosedUnixPeers=closed_peers, forcedPluginKills=forced, errors=errors,
        console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)
    return observation


def snapshot(paths):
    result = {}
    for path in paths:
        data = path.read_bytes()
        result[str(path)] = dict(base64=base64.b64encode(data).decode(),
                                 sha256=hashlib.sha256(data).hexdigest())
    return result


def probe(backend, loader, env, log, processes, rpc, until_ready, discovered,
          paths, verify_restart, *, regression):
    evidence = dict(stops=[], diskReadbacks=[], cleanShutdownVerified=False,
        expectedRegression=regression, unrelatedSiblingPreserved=False,
        realFrameContacted=False, physicalControllerVerified=False)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(40)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        for cycle in range(1 if regression else 2):
            before = snapshot(paths)
            observation = stop(backend, log, disconnect=cycle == 0)
            evidence['stops'].append(observation)
            after = snapshot(paths)
            evidence['diskReadbacks'].append(dict(before=before, after=after))
            assert before == after, 'unload must preserve exact private artwork/settings bytes'
            assert unrelated.poll() is None, 'unrelated sibling must survive'
            if regression:
                assert not observation['cleanShutdownVerified']
                assert observation['forcedPluginKills'] == 1 and observation['loaderReturncode'] == 0
            else:
                assert observation['cleanShutdownVerified'] and observation['seconds'] < 5, observation
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                restarted = until_ready(lambda: rpc('loader/get_plugins'), 'restarted SteamGridDB discovery')
                assert restarted == discovered, restarted
                evidence['restartedDiscovery'] = restarted
                verify_restart()
        evidence['unrelatedSiblingPreserved'] = unrelated.poll() is None
        evidence['cleanShutdownVerified'] = not regression
        return evidence
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        unrelated.wait(timeout=3)
        log.flush()
        console = Path(log.name).read_text()
        evidence['console'] = console
        evidence['consoleSha256'] = hashlib.sha256(console.encode()).hexdigest()
