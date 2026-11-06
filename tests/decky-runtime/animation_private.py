"""Disposable movie overrides driven through the published Decky legacy RPC."""
import base64
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

VIDEOS = ('deck_startup.webm', 'steam_os_suspend.webm',
          'steam_os_suspend_from_throbber.webm')
KINDS = ('boot', 'suspend', 'throbber')


def snapshot(path):
    info = path.lstat()
    return dict(base64=base64.b64encode(path.read_bytes()).decode(),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                identity=[info.st_dev, info.st_ino])


def prepare(home, base, folder):
    movies = home/'.steam/root/config/uioverrides/movies'
    movies.mkdir(parents=True)
    originals = {}
    for video in VIDEOS:
        path = movies/video
        path.write_bytes(('Private original '+video+'\n').encode())
        originals[video] = snapshot(path)
    selections = []
    for name in ['a', 'b']:
        path = home/('private-animation-'+name+'.webm')
        path.write_bytes(('Private selected '+name+'\n').encode())
        selections.append(dict(id=name, path=str(path), name='Private '+name, target='boot'))
    settings = base/'settings'/folder/'config.json'
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps(dict(boot='', suspend='', throbber='', randomize='',
        current_set='', downloads=[], custom_animations=selections, custom_sets=[],
        shuffle_exclusions=[], force_ipv4=False)))
    return dict(movies=movies, originals=originals, selections=selections)


def exercise(fixture, legacy, rpc, name, until_ready):
    def ready():
        response = rpc('loader/call_legacy_plugin_method', name, 'getState', {})
        return response.get('success') and response.get('result', {}).get('settings', {}).get('boot') == ''
    until_ready(ready, 'private Animation Changer settings')
    initial = legacy('getState')
    assert initial['settings']['boot'] == initial['settings']['suspend'] == initial['settings']['throbber'] == ''
    movies, originals = fixture['movies'], fixture['originals']
    assert {v:snapshot(movies/v) for v in VIDEOS} == originals
    assert not (movies/'.frame-control-animation-backups').exists()
    transitions = []
    for video, kind in zip(VIDEOS, KINDS):
        target = movies/video
        backup = movies/'.frame-control-animation-backups'/video/'original'
        for selected in ['a', 'a', 'b']:
            legacy('saveSettings', settings={kind:selected})
            source = next(v['path'] for v in fixture['selections'] if v['id'] == selected)
            assert target.is_symlink() and os.readlink(target) == source
            assert snapshot(backup) == originals[video]
            state = legacy('getState')
            assert state['settings'][kind] == selected
            transitions.append(dict(video=video, selection=selected, link=os.readlink(target),
                                    originalBackup=snapshot(backup)))
        legacy('saveSettings', settings={kind:''})
        assert not target.is_symlink() and snapshot(target) == originals[video]
        assert not os.path.lexists(backup)
    final = legacy('getState')
    assert all(final['settings'][kind] == '' for kind in KINDS)
    restored = {v:snapshot(movies/v) for v in VIDEOS}
    assert restored == originals
    return dict(defaultStartupPreservedAllThreeOverrides=True, originals=originals,
        transitions=transitions, restored=restored, repeatAndSwitchPreservedOriginal=True,
        resetRestoredOriginalBytesAndInodes=True, allSelectedSourceBytesRetained={
            v['id']:snapshot(Path(v['path'])) for v in fixture['selections']},
        privateFixtureOnly=True, actualSteamPlaybackVerified=False, externalRepositoryVerified=False,
        realFrameContacted=False, browserVerified=False, physicalControllerVerified=False)


def stop(backend, log, *, disconnect, after_eof):
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
             and 'Plugin Animation Changer (v1.3.2) has been stopped in ' in console
             and console.count('Unloaded Animation Changer (v1.3.2)') == 1
             and console.count('Unloaded\n') == 1 and seconds < 5)
    return dict(parentOnlySignal=True, loaderReturncode=backend.returncode,
        descendantsBefore=children, exactDescendantsRemaining=remaining, adoptedChildExits=adopted,
        fixtureClosedUnixPeers=peers, seconds=round(seconds, 3), forcedPluginKills=forced,
        errors=errors, console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        originalUnloadHookCompleted='Unloaded\n' in console, cleanShutdownVerified=clean)


def lifecycle(fixture, backend, loader, env, log, processes, legacy, rpc, until_ready,
              report, *, regression):
    originals = fixture['originals']
    selections = {v['path']: snapshot(Path(v['path'])) for v in fixture['selections']}
    settings = Path.home()/'.local/share/frame-control/decky/settings/SDH-AnimationChanger/config.json'
    settings_before = settings.read_bytes()
    sibling = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                               start_new_session=True)
    processes.append(sibling)
    evidence = report['animationLifecycle'] = dict(stops=[], rpcAfterEof=False,
        restartedDiscovery=False, unrelatedSiblingPreserved=False, privateBytesPreserved=False,
        expectedRegression=regression, realFrameContacted=False, actualSteamPlaybackVerified=False,
        physicalControllerVerified=False)

    def preserved():
        assert {v: snapshot(fixture['movies']/v) for v in VIDEOS} == originals
        assert {p: snapshot(Path(p)) for p in selections} == selections
        assert settings.read_bytes() == settings_before

    def after_eof():
        state = legacy('getState')
        assert all(state['settings'][kind] == '' for kind in KINDS)
        preserved()
        evidence['rpcAfterEof'] = True

    try:
        for cycle in range(1 if regression else 2):
            if cycle:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                found = until_ready(lambda: rpc('loader/get_plugins'), 'Animation Changer restart discovery')
                assert found == report['discovered'], found
                evidence['restartedDiscovery'] = found
                until_ready(lambda: legacy('getState').get('settings'), 'Animation Changer restart settings')
                preserved()
            observation = stop(backend, log, disconnect=cycle == 0,
                               after_eof=after_eof if not regression and cycle == 0 else None)
            evidence['stops'].append(observation)
            assert sibling.poll() is None
            preserved()
            if regression:
                assert observation['loaderReturncode'] == 0 and observation['forcedPluginKills'] == 1, observation
                assert not observation['cleanShutdownVerified'] and 5 <= observation['seconds'] < 8, observation
                assert not observation['exactDescendantsRemaining'], observation
            else:
                assert observation['cleanShutdownVerified'], observation
        evidence.update(unrelatedSiblingPreserved=True, privateBytesPreserved=True,
                        settingsSha256=hashlib.sha256(settings_before).hexdigest())
    finally:
        if sibling.poll() is None:
            sibling.terminate()
        sibling.wait(timeout=3)
