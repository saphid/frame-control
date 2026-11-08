"""Private cache preservation and loader-only shutdown after an owned IPC EOF."""
import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from deck_shelves_private import descendants, identity
from steamback_private import snapshot


def stop(backend, log, *, disconnect):
    children = descendants(backend.pid)
    assert children, 'the private loader must own its plugin child'
    log.flush()
    before = Path(log.name).read_text()
    peers = []
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
                peers.append(str(path))
        assert len(peers) == 1, peers
        time.sleep(.05)
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    log.flush()
    console = Path(log.name).read_text()[len(before):]
    adopted = []
    deadline = time.monotonic()+2
    while True:
        for pid, old in children.items():
            current = identity(pid)
            if current and current['start'] == old['start']:
                try:
                    child, status = os.waitpid(pid, os.WNOHANG)
                    if child:
                        adopted.append(dict(pid=child, returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:
                    pass
        remaining = {pid: current for pid, old in children.items()
                     if (current := identity(pid)) and current['start'] == old['start']}
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(.01)
    elapsed = time.monotonic()-started
    forced = console.count('Sending SIGKILL!')
    errors = [m for m in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if m in console]
    clean = (backend.returncode == 0 and elapsed < 5 and not remaining and not forced
             and not errors and all(c['returncode'] == 0 for c in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin Storage Cleaner (v1.4.0) has been stopped in ' in console)
    return dict(loaderPid=backend.pid, returncode=backend.returncode, elapsedSeconds=elapsed,
        signaledOnlyOwnedLoader=True, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted,
        fixtureClosedUnixPeers=peers, forcedPluginKills=forced, errors=errors,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)


def probe(backend, loader, env, log, processes, rpc, until_ready, discovered,
          roots, verify_read, *, regression=False):
    evidence = dict(stops=[], cacheSnapshots=[], expectedRegression=regression,
        unrelatedSiblingPreserved=False, cleanShutdownVerified=False, realFrameContacted=False)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(40)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        for cycle in range(1 if regression else 2):
            before = snapshot(roots)
            observation = stop(backend, log, disconnect=cycle == 0)
            after = snapshot(roots)
            evidence['stops'].append(observation)
            evidence['cacheSnapshots'].append(dict(before=before, after=after))
            evidence['unrelatedSiblingPreserved'] = unrelated.poll() is None
            assert before == after, 'shutdown must preserve every private cache marker'
            assert evidence['unrelatedSiblingPreserved'], evidence
            if regression:
                assert not observation['cleanShutdownVerified'], evidence
                assert observation['forcedPluginKills'] == 1 and observation['returncode'] == 0, evidence
            else:
                assert observation['cleanShutdownVerified'], evidence
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                restarted = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Storage Cleaner')
                assert restarted == discovered, restarted
                evidence['restartedDiscovery'] = restarted
                verify_read()
                assert snapshot(roots) == after, 'restart/read-only RPC must preserve the caches'
        evidence['cleanShutdownVerified'] = not regression
        return evidence
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        unrelated.wait(timeout=3)
