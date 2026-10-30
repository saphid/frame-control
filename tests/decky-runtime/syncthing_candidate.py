"""Uninstalled ownership candidate, run only in a disposable native container."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
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
    transport_requests = []
    class PrivateTransport(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_HEAD(self):
            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):
            transport_requests.append(self.path)
            accepted = self.headers.get('X-API-Key') == 'private-fixture'
            body = b'{"privateTransport":true}' if accepted else b'private fixture refused'
            self.send_response(200 if accepted else 401)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    transport = ThreadingHTTPServer(('127.0.0.1',8384), PrivateTransport)
    worker = threading.Thread(target=transport.serve_forever, daemon=True)
    worker.start()
    report = {'archiveSha256':DIGEST, 'pythonSha256':hashlib.sha256((plugin/'main.py').read_bytes()).hexdigest(),
              'helperSha256':hashlib.sha256(binary.read_bytes()).hexdigest(), 'installerEnabled':False,
              'independentState':{'listenerConflictBeforeSettingsOrService':True}}
    with (home/'candidate-runtime.log').open('w+') as log:
        backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
        forced = False
        try:
            plugins_found = until_ready(lambda: rpc('loader/get_plugins'), 'candidate discovery')
            assert any(row['name'] == 'Syncthing' and row['version'] == '0.2.7' for row in plugins_found), plugins_found

            def legacy(rpc_method, **kwargs):
                response = rpc('loader/call_legacy_plugin_method', 'Syncthing', rpc_method, kwargs)
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
            def owned_socket(pid):
                key = b'FRAMEY_SYNCTHING_SOCKET='
                entries = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
                path = Path(os.fsdecode(next(entry[len(key):] for entry in entries if entry.startswith(key))))
                assert path.stat().st_mode & 0o777 == 0o600
                assert path.parent.stat().st_mode & 0o777 == 0o700
                return path
            first_socket = owned_socket(first)
            response = legacy('framey_http_fetch', method='GET', path='/rest/db/status?folder=private%20fixture',
                              headers={'X-API-Key':'private-fixture','Accept':'application/json'})
            assert response['status'] == 200 and json.loads(response['body']) == {'privateTransport':True}, response
            assert transport_requests[-1] == '/rest/db/status?folder=private%20fixture'
            response = legacy('framey_http_fetch', method='GET', path='/rest/system/status', headers={})
            assert response['status'] == 401, response
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
            assert not first_socket.parent.exists()
            old = restarted
            old_socket = owned_socket(old)
            for _ in range(3):
                rpc('loader/reload_plugin', 'Syncthing')
                new = until_ready(lambda: (pid if (pid := current_pid()) != old else None), 'candidate reload')
                assert not alive(old) and unrelated.poll() is None
                assert not old_socket.parent.exists()
                old = new
                old_socket = owned_socket(old)
            report['independentState'].update(ownedRestartReaped=True, foreignPidIgnored=True,
                duplicateOwnershipRefused=True, activeReloadCount=3, unrelatedProcessPreserved=True)
            report['independentState'].update(privateSocketMode=True, privateHttpProxy=True,
                privateFixtureAuthErrorPreserved=True, privateSocketCleanupOnReload=True)
            report['result'] = ('published Decky discovery, disabled defaults, native listener/ownership conflicts, '
                'owned restart, three reloads and private-socket HTTP transport passed; '
                'the upstream HTTP fixture is synthetic; service control, actual Syncthing, sync, Frame and VR unverified')
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
            transport.shutdown()
            transport.server_close()
            worker.join(timeout=3)
    assert not forced, 'Candidate required a forced Decky shutdown'
    assert until_ready(lambda: not alive(old), 'watchdog stopped after Decky shutdown')
    assert not old_socket.parent.exists()
    report['independentState']['loaderExitStoppedOwnedWatchdog'] = True
    print(json.dumps(report))


if __name__ == '__main__':
    main()
