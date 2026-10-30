"""Uninstalled ownership candidate, run only in a disposable native container."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import zipfile

from check import rpc, until_ready

ROOT = Path('/repo')
ASSETS = ROOT/'ui/vendor/syncthing-0.2.7'
DIGEST = '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def main():
    assert os.getuid() == 1100 and ROOT.is_dir(), 'Use the isolated candidate runner'
    home = Path.home()
    helper = home/'candidate-watchdog'
    shutil.copy('/input/watchdog', helper)
    helper.chmod(0o700)
    # Invalid settings and an absent log directory make ordering observable:
    # a listener conflict must be refused before either can be opened.
    settings = home/'invalid-settings.json'
    settings.write_text('not JSON')
    pid_path = home/'foreign-watchdog.pid'
    pid_path.write_text('unrelated PID marker')
    with socket.socket() as foreign:
        foreign.bind(('127.0.0.1', 58384))
        foreign.listen()
        blocked = subprocess.run([str(helper), str(settings), str(pid_path), str(home/'absent-log')],
                                 capture_output=True, text=True, timeout=5)
        assert blocked.returncode != 0 and 'listener unavailable' in blocked.stderr, blocked.stderr
        assert pid_path.read_text() == 'unrelated PID marker'
        assert not (home/'absent-log').exists()
        assert foreign.getsockname() == ('127.0.0.1', 58384)

    archive = Path('/input/official.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == DIGEST
    base = home/'.local/share/frame-control/decky'
    plugins = base/'plugins'
    plugins.mkdir(parents=True)
    with zipfile.ZipFile(archive) as original:
        for entry in original.infolist():
            assert entry.filename.startswith('decky-syncthing/') and '..' not in Path(entry.filename).parts
            destination = plugins/entry.filename
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(original.read(entry))
    plugin = plugins/'decky-syncthing'
    shutil.copy(ASSETS/'main.py', plugin/'main.py')
    binary = plugin/'bin/decky-syncthing-watchdog'
    shutil.copy(helper, binary)
    binary.chmod(0o700)
    loader = base/'PluginLoader'
    shutil.copy('/input/PluginLoader', loader)
    loader.chmod(0o700)
    env = dict(os.environ, UNPRIVILEGED_PATH=str(base), PRIVILEGED_PATH=str(base),
               CHOWN_PLUGIN_PATH='0', LIVE_RELOAD='0', USE_CEF_CLOSE_WORKAROUND='0',
               KEEP_SYSTEMD_SERVICE='1', DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/no-service-bus')
    # Match the original name-wide kill pattern without sharing any functionality.
    unrelated_binary = home/'unrelated/decky-syncthing-watchdog'
    unrelated_binary.parent.mkdir()
    shutil.copy('/usr/bin/sleep', unrelated_binary)
    unrelated = subprocess.Popen([str(unrelated_binary), '120'])
    report = {'archiveSha256':DIGEST, 'pythonSha256':hashlib.sha256((plugin/'main.py').read_bytes()).hexdigest(),
              'helperSha256':hashlib.sha256(binary.read_bytes()).hexdigest(), 'installerEnabled':False,
              'independentState':{'listenerConflictBeforeSettingsOrService':True}}
    with (home/'candidate-runtime.log').open('w+') as log:
        backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
        forced = False
        try:
            plugins_found = until_ready(lambda: rpc('loader/get_plugins'), 'candidate discovery')
            assert any(row['name'] == 'Syncthing' and row['version'] == '0.2.7' for row in plugins_found), plugins_found

            def legacy(method):
                response = rpc('loader/call_legacy_plugin_method', 'Syncthing', method, {})
                assert response['success'], response
                return response['result']

            defaults = json.loads(legacy('get_settings_json'))
            assert defaults['is_setup'] is False and defaults['autostart'] == 'no', defaults

            def current_pid():
                paths = list(base.rglob('watchdog.pid'))
                if len(paths) != 1:
                    return None
                pid = int(paths[0].read_text())
                if not alive(pid):
                    return None
                command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
                return pid if os.fsencode(binary) in command else None

            first = until_ready(current_pid, 'owned native watchdog')
            actual_pid_path = next(base.rglob('watchdog.pid'))
            second = subprocess.run([str(binary), str(actual_pid_path.parent/'unused.json'),
                                     str(actual_pid_path), str(home/'unused-log')],
                                    capture_output=True, text=True, timeout=5)
            assert second.returncode != 0 and 'ownership unavailable' in second.stderr, second.stderr
            assert int(actual_pid_path.read_text()) == first and alive(first)
            # A stale/foreign PID value must not make reset signal that process.
            actual_pid_path.write_text(str(unrelated.pid))
            assert legacy('restart_watchdog') is None
            restarted = until_ready(current_pid, 'owned restart')
            assert restarted != first and not alive(first) and unrelated.poll() is None
            old = restarted
            for _ in range(3):
                rpc('loader/reload_plugin', 'Syncthing')
                new = until_ready(lambda: (pid if (pid := current_pid()) != old else None), 'candidate reload')
                assert not alive(old) and unrelated.poll() is None
                old = new
            report['independentState'].update(ownedRestartReaped=True, foreignPidIgnored=True,
                duplicateOwnershipRefused=True, activeReloadCount=3, unrelatedProcessPreserved=True)
            report['result'] = ('published Decky discovery, disabled defaults, native listener/ownership conflicts, '
                'owned restart and three reloads passed; service control, HTTP bridge, sync, Frame and VR unverified')
        except BaseException:
            log.flush()
            print(Path(log.name).read_text()[-10000:], file=sys.stderr)
            raise
        finally:
            if backend.poll() is None:
                os.killpg(backend.pid, signal.SIGTERM)
            try:
                backend.wait(timeout=8)
            except subprocess.TimeoutExpired:
                forced = True
                os.killpg(backend.pid, signal.SIGKILL)
                backend.wait(timeout=3)
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait(timeout=3)
    assert not forced, 'Candidate required a forced Decky shutdown'
    assert until_ready(lambda: not alive(old), 'watchdog stopped after Decky shutdown')
    report['independentState']['loaderExitStoppedOwnedWatchdog'] = True
    print(json.dumps(report))


if __name__ == '__main__':
    main()
