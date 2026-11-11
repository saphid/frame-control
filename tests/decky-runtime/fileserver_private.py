"""Private DeckyFileServer EOF, original unload and restart persistence proof."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from theme_music_private import descendants, identity


def stop(backend, log, *, disconnect, expected_helpers, after_disconnect=None):
    children = descendants(backend.pid)
    assert children, 'the private loader must own its children'
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
        if after_disconnect:
            assert after_disconnect()['server_running'] is False
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    console = Path(log.name).read_text()[len(before):]
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
              'Task was destroyed but it is pending', 'Bad file descriptor', 'Failed to save settings:')
              if marker in console]
    unloaded = console.count('[_unload] Unloading plugin') == 1
    def expected_exit(child):
        if child['returncode'] == 0:
            return True
        pid = child['pid']
        return (child['returncode'] == -signal.SIGTERM and pid in expected_helpers
                and children[pid]['start'] == expected_helpers[pid]['start'])
    clean = (backend.returncode == 0 and not remaining and not forced and not errors and unloaded
             and all(expected_exit(child) for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin DeckyFileServer (v1.2.0) has been stopped in ' in console)
    return dict(loaderPid=backend.pid, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted, parentOnlySignal=True,
        loaderReturncode=backend.returncode, seconds=round(time.monotonic()-started, 3),
        fixtureClosedUnixPeers=peers, forcedPluginKills=forced, errors=errors,
        apiStoppedNativeHelperIdentities=expected_helpers,
        postEofRpcVerified=bool(peers and after_disconnect), originalUnloadHookCompleted=unloaded,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)



def probe(backend, loader, env, log, processes, current, rpc, until_ready, report,
          settings_dir, *, regression):
    evidence = report['fileserverLifecycle'] = dict(stops=[], diskReadbacks=[],
        expectedRegression=regression, cleanShutdownVerified=False,
        realFrameContacted=False, physicalControllerVerified=False)
    settings = settings_dir/'settings.json'
    assert settings.is_file()
    original = settings.read_bytes()
    expected = current('get_status')
    assert expected['server_running'] is False and expected['history']
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(80)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        for cycle in range(1 if regression else 2):
            observation = stop(backend, log, disconnect=cycle == 0,
                expected_helpers=report['ownedFileserverHelpers'],
                after_disconnect=(None if regression else lambda: current('get_status')))
            evidence['stops'].append(observation)
            after = settings.read_bytes()
            assert after == original, 'private saved configuration must not change'
            evidence['diskReadbacks'].append(dict(
                sha256=hashlib.sha256(after).hexdigest(), settingsUnchanged=True))
            assert unrelated.poll() is None, 'an unrelated sibling must survive'
            if regression:
                assert (not observation['cleanShutdownVerified'] and
                        observation['forcedPluginKills'] == 1 and
                        not observation['originalUnloadHookCompleted'] and
                        observation['loaderReturncode'] == 0), observation
            else:
                assert observation['cleanShutdownVerified'] and observation['seconds'] < 5, observation
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                discovered = until_ready(lambda: rpc('loader/get_plugins'), 'restarted fileserver discovery')
                assert discovered == report['discovered'], discovered
                assert current('get_status') == expected
                evidence['restartedDiscovery'] = discovered
                evidence['restartedStatus'] = expected
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
