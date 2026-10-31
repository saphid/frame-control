"""Audit the private Deck Shelves loader's own shutdown, including closed IPC peers."""
import base64
import hashlib
import json
import stat
import subprocess
import sys
import os
from pathlib import Path
import signal
import socket
import time


def identity(pid):
    try:
        fields = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()
        return dict(state=fields[0], parent=int(fields[1]), start=fields[19])
    except FileNotFoundError:
        return None


def descendants(parent):
    snapshot = {int(p.name): state for p in Path('/proc').iterdir() if p.name.isdigit()
                if (state := identity(int(p.name)))}
    owned = {parent}
    while True:
        added = {pid for pid, state in snapshot.items() if state['parent'] in owned} - owned
        if not added:
            return {pid: snapshot[pid] for pid in owned - {parent}}
        owned.update(added)


def stop(backend, log, *, disconnect):
    children = descendants(backend.pid)
    assert children, 'the private loader must own its plugin children'
    log.flush()
    before = Path(log.name).read_text()
    closed_peers = []
    if disconnect:
        # This network-isolated container owns exactly one published plugin.
        # Exercise an ordinary peer EOF; never signal its child to aid shutdown.
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
    elapsed = time.monotonic()-started
    log.flush()
    console = Path(log.name).read_text()[len(before):]
    # The container's PID1 reaps only the identities owned by this loader.
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
    forced = console.count('Sending SIGKILL!')
    errors = [m for m in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if m in console]
    unloads = console.count('Unloaded Deck Shelves (v2.0.0)')
    hooks = console.count('Deck Shelves backend unloaded')
    clean = (backend.returncode == 0 and elapsed < 5 and not remaining and not forced and not errors and hooks == 1
             and all(c['returncode'] == 0 for c in adopted) and unloads == 1
             and console.count('[main][INFO]: Shutdown finished.') == 1)
    return dict(loaderPid=backend.pid, returncode=backend.returncode, elapsedSeconds=elapsed,
        signaledOnlyOwnedLoader=True, ownedProcessCount=len(children)+1,
        ownedProcessIdentitiesReaped=not remaining, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted,
        fixtureClosedUnixPeers=closed_peers, forcedPluginKills=forced,
        originalUnloadHookCompleted=unloads == hooks == 1, errors=errors,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)


def snapshot(paths):
    result = {}
    for path in paths:
        data = path.read_bytes()
        metadata = path.stat()
        result[str(path)] = dict(base64=base64.b64encode(data).decode(),
            sha256=hashlib.sha256(data).hexdigest(), parsed=json.loads(data),
            metadata=dict(mode=stat.S_IMODE(metadata.st_mode), uid=metadata.st_uid,
                          gid=metadata.st_gid, inode=metadata.st_ino, mtimeNs=metadata.st_mtime_ns))
    return result


def probe(backend, loader, env, log, processes, rpc, until_ready, discovered,
          paths, verify_restart, *, regression=False):
    evidence = dict(stops=[], settingsSnapshots=[], expectedRegression=regression,
        unrelatedSiblingPreserved=False, cleanShutdownVerified=False,
        realFrameContacted=False, physicalControllerVerified=False)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(40)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        for cycle in range(1 if regression else 2):
            before = snapshot(paths)
            observation = stop(backend, log, disconnect=cycle == 0)
            after = snapshot(paths)
            evidence['stops'].append(observation)
            evidence['settingsSnapshots'].append(dict(before=before, after=after))
            evidence['unrelatedSiblingPreserved'] = unrelated.poll() is None
            assert before == after, evidence
            assert evidence['unrelatedSiblingPreserved'], evidence
            if regression:
                assert not observation['cleanShutdownVerified'], evidence
                assert observation['forcedPluginKills'] == 1 and observation['returncode'] == 0, evidence
                assert not observation['originalUnloadHookCompleted'], evidence
            else:
                assert observation['cleanShutdownVerified'], evidence
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                restarted = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Deck Shelves discovery')
                assert restarted == discovered, restarted
                evidence['restartedDiscovery'] = restarted
                verify_restart()
                assert snapshot(paths) == after, evidence
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
