"""Observe private Storage Cleaner EOF, parent-only unload and exact owned exits."""
import hashlib
import os
from pathlib import Path
import signal
import socket
import time
from deck_settings_private import identity, descendants


def stop(backend, log, *, disconnect, after_disconnect=None):
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
        if after_disconnect:
            after_disconnect()
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
             and 'Plugin Storage Cleaner (v1.4.0) has been stopped in ' in console
             and time.monotonic()-started < 5)
    observation = dict(loaderPid=backend.pid, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted, parentOnlySignal=True,
        loaderReturncode=backend.returncode, seconds=round(time.monotonic()-started, 3),
        fixtureClosedUnixPeers=closed_peers, forcedPluginKills=forced, errors=errors,
        console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)
    return observation



def probe(backend, loader, env, log, processes, call, rpc, until_ready, report, *, regression):
    import subprocess
    import sys
    home = Path.home()
    cache = home/'.steam/steam/steamapps/shadercache/424243'
    cache.mkdir(parents=True)
    marker = cache/'marker'
    marker.write_bytes(b'Private EOF cache marker\n')
    sibling = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    processes.append(sibling)
    evidence = report['storageCleanerLifecycle'] = dict(stops=[], readAfterEof=False,
        restartedDiscovery=False, unrelatedSiblingPreserved=False, markerPreserved=False,
        expectedRegression=regression, realFrameContacted=False, realSteamCachesChanged=False)

    def read_cache():
        assert call('get_size', 'shadercache/424243') == len(marker.read_bytes())
        evidence['readAfterEof'] = True

    try:
        for cycle in range(1 if regression else 2):
            if cycle:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
                processes.append(backend)
                found = until_ready(lambda: rpc('loader/get_plugins'), 'Storage Cleaner restart discovery')
                assert found == [dict(name='Storage Cleaner', version='1.4.0', load_type=1, disabled=False)]
                evidence['restartedDiscovery'] = found
                read_cache()
            observation = stop(backend, log, disconnect=cycle == 0,
                after_disconnect=read_cache if cycle == 0 and not regression else None)
            evidence['stops'].append(observation)
            assert sibling.poll() is None and marker.read_bytes() == b'Private EOF cache marker\n'
            if regression:
                assert observation['loaderReturncode'] == 0 and observation['forcedPluginKills'] == 1, observation
                assert not observation['cleanShutdownVerified'] and 5 <= observation['seconds'] < 8, observation
                assert not observation['exactDescendantsRemaining'], observation
            else:
                assert observation['cleanShutdownVerified'], observation
        evidence.update(unrelatedSiblingPreserved=sibling.poll() is None, markerPreserved=True)
    finally:
        if sibling.poll() is None:
            sibling.terminate()
        sibling.wait(timeout=5)
    return evidence
