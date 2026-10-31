"""Private MangoPeel profile/watch lifecycle; never expose a host compositor."""
from pathlib import Path
import signal
import subprocess
import sys


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


def exercise(current, rpc, backend, log, fixture, until_ready):
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
    # Signal the owned launcher once; it forwards to its Python child.
    backend.send_signal(signal.SIGTERM)
    loader_exit = backend.wait(timeout=8)
    assert loader_exit == 0, loader_exit
    console = Path(log.name).read_bytes()[began:].decode()
    assert 'Sending SIGKILL!' not in console and 'Error during shutdown:' not in console
    assert 'Shutdown finished.' in console
    assert process.poll() is None
    return dict(privateSelectedProfileWrite=True, privateMultiProfileWrite=True,
        actualInotifyCallback=True, replacementWatchActive=True,
        reloadWithoutForcedKill=True, ownedLoaderShutdownClean=True, loaderExitCode=loader_exit,
        reloadAndShutdownConsole=console,
        profilePreservedAcrossReload=True, unrelatedProfileAndProcessPreserved=True,
        syntheticMangoappProcess=True, actualMangoHudOverlay=False,
        browserVerified=False, realFrameContacted=False, physicalControllerVerified=False)
