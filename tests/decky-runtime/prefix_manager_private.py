"""Audit the private Games Prefix Manager loader's own shutdown, including closed IPC peers."""
import hashlib
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


def stop(backend, log, *, disconnect, after_disconnect=None):
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
        if after_disconnect:
            after_disconnect()
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
    # This published plugin has no _unload hook. Require the child's missing-hook
    # diagnostic and a normal framework stop; the parent also logs a stop after SIGKILL.
    stopped = console.count('[plugin][INFO]: Plugin Games Prefix Manager (v1.0.2) has been stopped in ')
    unloads = int(stopped == 1 and not forced and
        console.count('Could not find \"_unload\" in Games Prefix Manager (v1.0.2)\'s main.py') == 1)
    clean = (backend.returncode == 0 and elapsed < 5 and not remaining and not forced and not errors
             and all(c['returncode'] == 0 for c in adopted) and unloads == 1
             and console.count('[main][INFO]: Shutdown finished.') == 1)
    return dict(loaderPid=backend.pid, returncode=backend.returncode, elapsedSeconds=elapsed,
        signaledOnlyOwnedLoader=True, ownedProcessCount=len(children)+1,
        ownedProcessIdentitiesReaped=not remaining, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted,
        fixtureClosedUnixPeers=closed_peers, forcedPluginKills=forced,
        pluginUnloadCompleted=unloads == 1, errors=errors,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)


def probe(backend, loader, env, log, processes, legacy, rpc, until_ready, report, *, regression):
    import subprocess
    import sys
    home = Path.home()
    backups = home/'Documents/PrefixBackups'
    marker = home/'outside-marker/keep.dat'
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in backups.glob('*.zip')}
    assert len(before) == 2 and marker.read_bytes() == b'Private prefix save fixture\n'
    evidence = report['prefixManagerLifecycle'] = dict(stops=[], emptyLibraryReadbacks=[],
        backupSha256Before=before, backupsPreserved=False, outsideMarkerPreserved=False,
        unrelatedSiblingPreserved=False, cleanShutdownVerified=False, expectedRegression=regression,
        customUnloadHookPresent=False, realFrameContacted=False, physicalControllerVerified=False)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                 start_new_session=True)
    processes.append(unrelated)
    def readback():
        value = legacy('get_games')
        assert value == [], value
        evidence['emptyLibraryReadbacks'].append(value)
    try:
        for cycle in range(1 if regression else 2):
            observation = stop(backend, log, disconnect=cycle == 0,
                after_disconnect=readback if cycle == 0 and not regression else None)
            evidence['stops'].append(observation)
            assert unrelated.poll() is None, 'unrelated sibling must survive loader shutdown'
            if regression:
                assert observation['returncode'] == 0 and observation['forcedPluginKills'] == 1, observation
                assert not observation['cleanShutdownVerified'] and not observation['pluginUnloadCompleted'], observation
                assert 5 <= observation['elapsedSeconds'] < 8 and observation['ownedProcessIdentitiesReaped'], observation
            else:
                assert observation['cleanShutdownVerified'], observation
            assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in backups.glob('*.zip')} == before
            assert marker.read_bytes() == b'Private prefix save fixture\n'
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                discovered = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Prefix Manager discovery')
                assert discovered == [dict(name='Games Prefix Manager', version='1.0.2', load_type=0, disabled=False)]
                evidence['restartedDiscovery'] = discovered
                readback()
        evidence.update(backupsPreserved=True, outsideMarkerPreserved=True,
            unrelatedSiblingPreserved=unrelated.poll() is None, cleanShutdownVerified=not regression)
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        unrelated.wait(timeout=5)
    return evidence
