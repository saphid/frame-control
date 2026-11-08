"""Silent private MPRIS state across MusicControl EOF, unload and restart."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from deck_settings_private import identity, descendants


def stop(backend, log, record, *, disconnect, after_eof):
    children = descendants(backend.pid)
    assert children, 'the private loader must own its plugin child'
    before = Path(log.name).read_text()
    peers = []
    if disconnect:
        paths = list(Path('/tmp').glob('plugin_socket_*'))
        assert len(paths) == 1 and paths[0].stat().st_uid == os.getuid()
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(.2)
            peer.connect(str(paths[0]))
            peer.shutdown(socket.SHUT_WR)
        peers.append(str(paths[0]))
        time.sleep(.05)
        if after_eof:
            after_eof()
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
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
        remaining = {pid: state for pid, old in children.items()
                     if (state := identity(pid)) and state['start'] == old['start']}
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(.01)
    console = Path(log.name).read_text()[len(before):]
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [marker for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if marker in console]
    seconds = time.monotonic()-started
    clean = (backend.returncode == 0 and not remaining and not forced and not errors
             and all(child['returncode'] == 0 for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and f"Plugin {record['name']} (v{record['version']}) has been stopped in " in console
             # These digest-pinned legacy backends have no _unload method.
             # Require Decky's real legacy unload path, rather than the API1
             # goodbye log that their manifests do not produce.
             and console.count(f"Calling Loader unload function for {record['name']} (v{record['version']}).") == 1
             and console.count(f'Could not find "_unload" in {record["name"]} (v{record["version"]})\'s main.py') == 1
             and seconds < 5)
    return dict(parentOnlySignal=True, loaderReturncode=backend.returncode,
        descendantsBefore=children, exactDescendantsRemaining=remaining, adoptedChildExits=adopted,
        fixtureClosedUnixPeers=peers, seconds=round(seconds, 3), forcedPluginKills=forced,
        errors=errors, console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)


def probe(backend, loader, env, log, processes, record, legacy, rpc, until_ready, report,
          *, regression):
    state = Path('/tmp/mpris-state.json')
    before = state.read_bytes()
    sibling = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                               start_new_session=True)
    processes.append(sibling)
    evidence = report['musicControlLifecycle'] = dict(stops=[], rpcAfterEof=False,
        restartedDiscovery=False, unrelatedSiblingPreserved=False, privatePlayerStatePreserved=False,
        expectedRegression=regression, realFrameContacted=False, audiblePlaybackVerified=False,
        physicalControllerVerified=False)

    def verify_player():
        player = 'org.mpris.MediaPlayer2.FrameySilent'
        assert legacy('sp_list_media_players') == player
        # A fresh legacy child starts with its default player; select only the
        # fixture name before making read-only calls. No media state is changed.
        legacy('sp_set_media_player', player=player)
        assert legacy('sp_get_media_player') == player
        assert legacy('sp_track_status') == 'Paused'
        assert legacy('sp_track_progress') == '45000000'
        assert float(legacy('sp_get_volume')) == .25
        assert state.read_bytes() == before
        return json.loads(before)

    def after_eof():
        evidence['rpcAfterEof'] = verify_player()

    try:
        for cycle in range(1 if regression else 2):
            if cycle:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                found = until_ready(lambda: rpc('loader/get_plugins'), 'MusicControl restart discovery')
                assert found == report['discovered'], found
                evidence['restartedDiscovery'] = found
                verify_player()
            observation = stop(backend, log, record, disconnect=cycle == 0,
                               after_eof=after_eof if not regression and cycle == 0 else None)
            evidence['stops'].append(observation)
            assert sibling.poll() is None and state.read_bytes() == before
            if regression:
                assert observation['loaderReturncode'] == 0 and observation['forcedPluginKills'] == 1, observation
                assert not observation['cleanShutdownVerified'] and 5 <= observation['seconds'] < 8, observation
                assert not observation['exactDescendantsRemaining'], observation
            else:
                assert observation['cleanShutdownVerified'], observation
        evidence.update(unrelatedSiblingPreserved=True, privatePlayerStatePreserved=True)
    finally:
        if sibling.poll() is None:
            sibling.terminate()
        sibling.wait(timeout=3)
