"""Private MangoPeel profile/watch lifecycle; never expose a host compositor."""
from pathlib import Path
import hashlib
import os
import signal
import socket
import subprocess
import sys
import time
from deck_settings_private import descendants, identity


def steam_profile(index):
    return ('control=mangohud\nmangoapp_steam\nfsr_steam_sharpness=5\n'
            f'nis_steam_sharpness=10\npreset={index}')


def start(env, log, processes):
    profile = Path.home()/'private-mangohud.conf'
    profile.write_text(steam_profile(1))
    unrelated = Path.home()/'unrelated-profile.conf'
    unrelated.write_text('preserve unrelated configuration\n')
    # This inert process supplies the same /proc argv/environment interface
    # that MangoPeel discovers. It is not mangoapp or a graphics compositor.
    process = subprocess.Popen(['mangoapp', '-c', 'import signal; signal.pause()'],
        executable=sys.executable, env=dict(env, MANGOHUD_CONFIGFILE=str(profile)),
        stdout=log, stderr=log, start_new_session=True)
    processes.append(process)
    return profile, unrelated, process


def stop_after_eof(backend, log, check_after_eof, *, regression):
    owned = descendants(backend.pid)
    assert owned, 'the private loader must own its plugin children'
    offset = len(Path(log.name).read_text())
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
    time.sleep(.05)
    if not regression:
        assert check_after_eof(), 'the repaired backend must still answer after EOF'
    began = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    adopted = []
    deadline = time.monotonic()+2
    while True:
        for pid, old in owned.items():
            current = identity(pid)
            if current and current['start'] == old['start']:
                try:
                    child, status = os.waitpid(pid, os.WNOHANG)
                    if child:
                        adopted.append(dict(pid=child, returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:
                    pass
        remaining = {pid: state for pid, old in owned.items()
                     if (state := identity(pid)) and state['start'] == old['start']}
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(.01)
    console = Path(log.name).read_text()[offset:]
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [marker for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if marker in console]
    elapsed = round(time.monotonic()-began, 3)
    clean = (backend.returncode == 0 and not remaining and not forced and not errors
             and all(child['returncode'] == 0 for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin MangoPeel (v0.0.7) has been stopped in ' in console and elapsed < 5)
    observation = dict(parentOnlySignal=True, loaderReturncode=backend.returncode,
        elapsedSeconds=elapsed, descendantsBefore=owned, exactDescendantsRemaining=remaining,
        adoptedChildExits=adopted, closedUnixPeers=closed, postEofRpcVerified=not regression,
        forcedPluginKills=forced, errors=errors, console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(), cleanShutdownVerified=clean)
    assert backend.returncode == 0 and not remaining, observation
    if regression:
        assert forced == 1 and not clean and 5 <= elapsed < 8, observation
    else:
        assert clean, observation
    return observation


def exercise(current, rpc, backend, log, fixture, until_ready, *, regression=False):
    profile, unrelated, process = fixture
    assert until_ready(lambda: current('get_steamIndex') == 1, 'private MangoPeel profile')
    assert current('get_steamChannel') == 'main'
    custom = 'fps=1\nframetime=1\nposition=top-left'
    expected = 'mangopeel_flag=1\nmangoapp_steam\n'+custom
    assert current('SetOverwriteConfig', 1, custom) is True
    assert until_ready(lambda: profile.read_text() == expected, 'selected profile write')
    configs = ['', custom, 'fps=1\nposition=top-right', '', '']
    assert current('SetOverwriteConfigs', configs) is True
    profile.write_text(steam_profile(2))
    expected_second = 'mangopeel_flag=2\nmangoapp_steam\n'+configs[2]
    assert until_ready(lambda: profile.read_text() == expected_second,
                       'actual inotify profile change')
    assert current('get_steamIndex') == 2
    assert current('ReloadConfigPath') is True
    before = profile.read_bytes()
    loaded = Path(log.name).read_text().count('Loaded MangoPeel')
    began = Path(log.name).stat().st_size
    if not regression:
        assert rpc('loader/reload_plugin', 'MangoPeel') is None
        # Decky's reload RPC queues work. Wait for replacement discovery before
        # making calls; racing a stopping response listener can strand the call.
        until_ready(lambda: Path(log.name).read_text().count('Loaded MangoPeel') == loaded+1,
                    'queued MangoPeel reload completion')
        console = Path(log.name).read_bytes()[began:].decode()
        assert 'Sending SIGKILL!' not in console, console
        assert 'Error during shutdown:' not in console, console
        assert process.poll() is None
        assert until_ready(lambda: current('get_steamIndex') == 2, 'MangoPeel after reload')
        assert profile.read_bytes() == before
        assert process.poll() is None
    # The old plugin cannot rewrite after its replacement has loaded.
    profile.write_text(steam_profile(3))
    assert until_ready(lambda: current('get_steamIndex') == 3, 'replacement inotify watch')
    assert profile.read_text() == steam_profile(3)
    assert unrelated.read_text() == 'preserve unrelated configuration\n'
    # Signal only the owned launcher after EOF; its own cleanup must reap the
    # recorded plugin descendants while preserving the unrelated fixture.
    stop = stop_after_eof(backend, log, lambda: current('get_steamIndex') == 3,
                          regression=regression)
    console = Path(log.name).read_bytes()[began:].decode()
    if not regression:
        assert 'Sending SIGKILL!' not in console and 'Error during shutdown:' not in console
    assert 'Shutdown finished.' in console
    assert process.poll() is None
    return dict(privateSelectedProfileWrite=True, privateMultiProfileWrite=True,
        actualInotifyCallback=True, replacementWatchActive=not regression,
        reloadWithoutForcedKill=not regression, ownedLoaderShutdownClean=not regression,
        loaderExitCode=backend.returncode, ownedLoaderStop=stop,
        controlledEofForcedKillReproduced=regression,
        reloadAndShutdownConsole=console,
        profilePreservedAcrossReload=not regression, unrelatedProfileAndProcessPreserved=True,
        syntheticMangoappProcess=True, actualMangoHudOverlay=False,
        browserVerified=False, realFrameContacted=False, physicalControllerVerified=False)
