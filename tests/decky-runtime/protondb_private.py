"""Private ProtonDB settings persistence and owner-only shutdown after IPC EOF."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from free_loader_private import stop


def snapshot(state):
    data = state.read_bytes()
    return dict(text=data.decode(), sha256=hashlib.sha256(data).hexdigest(),
                parsed=json.loads(data))


def probe(backend, loader, env, log, processes, current, rpc, until_ready,
          report, state, saved, defaults, info, *, regression=False):
    evidence = report['protondbLifecycle'] = dict(stops=[], diskReadbacks=[],
        expectedRegression=regression, cleanShutdownVerified=False,
        unrelatedSiblingPreserved=False, realFrameContacted=False,
        physicalControllerVerified=False)
    # All paths and processes belong to this networkless disposable container.
    # Close one additional peer; never close or signal the loader's own peer.
    closed = []
    for path in Path('/tmp').glob('plugin_socket_*'):
        assert path.is_socket() and path.stat().st_uid == os.getuid()
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(.2)
            try:
                peer.connect(str(path))
            except ConnectionRefusedError:
                continue
            peer.shutdown(socket.SHUT_WR)
            closed.append(str(path))
    assert len(closed) == 1, closed
    evidence['fixtureClosedUnixPeers'] = closed
    time.sleep(.05)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(80)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        started = time.monotonic()
        try:
            reply = current('get_system_info')
        except TimeoutError:
            assert regression, 'repaired backend must answer after peer EOF'
            evidence['postEofRpc'] = dict(method='get_system_info', completed=False,
                error='TimeoutError', seconds=round(time.monotonic()-started, 3))
        else:
            assert not regression and reply == info, reply
            evidence['postEofRpc'] = dict(method='get_system_info', completed=True,
                result=reply, seconds=round(time.monotonic()-started, 3))
        for cycle in range(1 if regression else 2):
            before = snapshot(state)
            assert before['parsed'] == {'settings': saved}
            observation = stop(backend, log, disconnect=False,
                plugin_stop_marker='Plugin ProtonDB Badges (v1.3.4) has been stopped in ')
            evidence['stops'].append(observation)
            after = snapshot(state)
            evidence['diskReadbacks'].append(dict(before=before, after=after))
            assert before == after, 'shutdown must preserve exact private settings bytes'
            assert unrelated.poll() is None, 'unrelated sibling must survive'
            if regression:
                assert (not observation['cleanShutdownVerified'] and
                        observation['forcedPluginKills'] == 1 and
                        observation['loaderReturncode'] == 0), observation
                assert 'Unloaded ProtonDB Badges (v1.3.4)' not in observation['console']
            else:
                assert observation['cleanShutdownVerified'] and observation['seconds'] < 5, observation
                assert observation['console'].count('Unloaded ProtonDB Badges (v1.3.4)') == 1
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                discovered = until_ready(lambda: rpc('loader/get_plugins'), 'restarted ProtonDB discovery')
                assert discovered == report['discovered'], discovered
                evidence['restartedDiscovery'] = discovered
                assert until_ready(lambda: current('get_setting', 'settings', defaults) == saved,
                                   'private ProtonDB settings after restart') is True
                assert current('get_setting', 'missing-private-setting', False) is False
                assert current('get_system_info') == info
                assert snapshot(state) == after
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
