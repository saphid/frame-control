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
import tempfile
import time
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


def time_wait_recovery(helper, home):
    """Use a real closed TCP client, not a mocked bind error or timer."""
    with tempfile.TemporaryDirectory(prefix='time-wait-', dir=home) as temporary:
        root = Path(temporary)
        settings = root/'invalid-settings.json'
        settings.write_text('not JSON')
        pid = root/'watchdog.pid'
        pid.write_text('private PID marker')
        logs = root/'logs'
        logs.mkdir()
        env = dict(os.environ, FRAMEY_SYNCTHING_OWNER_PID=str(os.getpid()),
                   FRAMEY_SYNCTHING_SOCKET=str(root/'private.sock'))
        with socket.socket() as server, socket.socket() as client:
            client.bind(('127.0.0.1', 58384))
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            client.connect(server.getsockname())
            accepted, _ = server.accept()
            with accepted:
                client.shutdown(socket.SHUT_WR)
                assert accepted.recv(1) == b''
            assert client.recv(1) == b''
        rows = [row.split() for row in Path('/proc/net/tcp').read_text().splitlines()[1:]
                if row.split()[1] == '0100007F:E410']
        assert rows and all(row[3] == '06' for row in rows), rows
        began = time.monotonic()
        child = subprocess.Popen([str(helper), str(settings), str(pid), str(logs)],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(.25)
            assert child.poll() is None, 'TIME_WAIT must not cause immediate startup failure'
            assert pid.read_text() == 'private PID marker'
            assert settings.read_text() == 'not JSON' and not list(logs.iterdir())
            assert not (root/'private.sock').exists()
            stdout, stderr = child.communicate(timeout=80)
            assert child.returncode != 0, 'invalid settings remain a deliberate negative control'
            assert 'Watchdog waiting for loopback TCP TIME_WAIT' in stderr, stderr
            assert 'Watchdog listener unavailable' not in stderr, stderr
            # Upstream's registered panic hook writes to this owned file,
            # rather than stderr. Retain the deliberate settings failure.
            panic = (logs/'last_panic.txt').read_text()
            assert 'SerdeJson' in panic, panic
            assert pid.read_text() == str(child.pid)
            assert settings.read_text() == 'not JSON'
            elapsed = round(time.monotonic()-began, 3)
            assert 1 < elapsed < 80, elapsed
            return dict(initialTcpRows=rows, seconds=elapsed, helperExit=child.returncode,
                        stdout=stdout, stderr=stderr, panicLog=panic,
                        heldStateUntouchedWhileWaiting=True,
                        actualTcpTimeWaitExpired=True, listenerReservedBeforeSettings=True,
                        settingsStillInvalid=True, realFrameContacted=False)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=3)


def main():
    assert os.getuid() == 1100 and ROOT.is_dir(), 'Use the isolated candidate runner'
    home = Path.home()
    helper = home/'candidate-watchdog'
    shutil.copy('/input/watchdog', helper)
    helper.chmod(0o700)
    recovery = time_wait_recovery(helper, home)
    # Invalid settings and an absent log directory make ordering observable:
    # a listener conflict must be refused before either can be opened.
    settings = home/'invalid-settings.json'
    settings.write_text('not JSON')
    pid_path = home/'foreign-watchdog.pid'
    pid_path.write_text('unrelated PID marker')
    for expected_parent in ('invalid', str(os.getpid()+1)):
        rejected = subprocess.run([str(helper), str(settings), str(pid_path), str(home/'absent-log')],
            env=dict(os.environ, FRAMEY_SYNCTHING_OWNER_PID=expected_parent),
            capture_output=True, text=True, timeout=5)
        assert rejected.returncode != 0 and 'parent unavailable' in rejected.stderr, rejected.stderr
        assert pid_path.read_text() == 'unrelated PID marker'
        assert not pid_path.with_suffix('.framey-lock').exists()
        assert not (home/'absent-log').exists()
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
              'timeWaitRecovery':recovery,
              'independentState':{'listenerConflictBeforeSettingsOrService':True,
                                  'invalidOrMismatchedParentBeforeOwnershipOrSettings':True}}
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

            first = until_ready(current_pid, 'owned native watchdog', timeout=80)
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
            # Private filesystem proof: every managed route rejects a foreign
            # unit before any absent DBus manager or Flatpak executable is used.
            unit_dir = home/'.config/systemd/user'
            unit_dir.mkdir(parents=True, exist_ok=True)
            foreign_unit = unit_dir/'frame-control-syncthing.service'
            legacy_unit = unit_dir/'decky-syncthing.service'
            foreign_unit.write_text('pre-existing private unit marker')
            legacy_unit.write_text('pre-existing private legacy marker')
            settings_path = next(base.rglob('decky-syncthing.json'))
            assert settings_path.is_file(), settings_path
            retained_settings = settings_path.read_bytes()
            configured = dict(defaults, mode='flatpak', is_setup=True, flatpak_name='example.Syncthing')
            settings_path.write_text(json.dumps(configured))
            for method, route in [('POST','reload-config'), ('GET','state'), ('POST','start'),
                                  ('POST','stop'), ('POST','check/start')]:
                reply = legacy('framey_http_fetch', method=method, path='/__decky-watchdog/'+route, headers={})
                assert reply['status'] == 500 and 'unowned or was edited' in reply['body'], reply
                assert foreign_unit.read_text() == 'pre-existing private unit marker'
                assert legacy_unit.read_text() == 'pre-existing private legacy marker'
            configured.update(mode='systemd', service_name='frame-control-syncthing.service')
            settings_path.write_text(json.dumps(configured))
            reply = legacy('framey_http_fetch', method='POST', path='/__decky-watchdog/reload-config', headers={})
            assert reply['status'] == 500
            for route in ['start','stop']:
                reply = legacy('framey_http_fetch', method='POST', path='/__decky-watchdog/'+route, headers={})
                assert reply['status'] == 500 and 'Reserved managed unit' in reply['body'], reply
            settings_path.write_bytes(retained_settings)
            reply = legacy('framey_http_fetch', method='POST', path='/__decky-watchdog/reload-config', headers={})
            assert reply['status'] == 204, reply
            assert foreign_unit.read_text() == 'pre-existing private unit marker'
            assert legacy_unit.read_text() == 'pre-existing private legacy marker'
            assert settings_path.read_bytes() == retained_settings
            report['independentState']['foreignServiceFilesPreservedBeforeDBus'] = True
            report['independentState']['reservedManagedNameRefusedAsExternal'] = True
            report['serviceManagerVerified'] = False
            actual_pid_path = next(base.rglob('watchdog.pid'))
            second = subprocess.run([str(binary), str(actual_pid_path.parent/'unused.json'),
                                     str(actual_pid_path), str(home/'unused-log')],
                                    capture_output=True, text=True, timeout=5)
            assert second.returncode != 0 and 'ownership unavailable' in second.stderr, second.stderr
            assert int(actual_pid_path.read_text()) == first and alive(first)
            # A stale/foreign PID value must not make reset signal that process.
            actual_pid_path.write_text(str(unrelated.pid))
            assert legacy('restart_watchdog') is None
            restarted = until_ready(current_pid, 'owned restart', timeout=80)
            assert restarted != first and not alive(first) and unrelated.poll() is None
            assert not first_socket.parent.exists()
            old = restarted
            old_socket = owned_socket(old)
            for _ in range(3):
                rpc('loader/reload_plugin', 'Syncthing')
                new = until_ready(lambda: (pid if (pid := current_pid()) != old else None), 'candidate reload', timeout=80)
                assert not alive(old) and unrelated.poll() is None
                assert not old_socket.parent.exists()
                old = new
                old_socket = owned_socket(old)
            report['independentState'].update(ownedRestartReaped=True, foreignPidIgnored=True,
                duplicateOwnershipRefused=True, activeReloadCount=3, unrelatedProcessPreserved=True)
            report['independentState'].update(privateSocketMode=True, privateHttpProxy=True,
                privateFixtureAuthErrorPreserved=True, privateSocketCleanupOnReload=True)
            # Exercise Decky's documented five-second SIGKILL fallback, rather
            # than relying on the intermittent missed-unload failure from CI.
            # The helper must die with its exact owning plugin process, even
            # when Python cannot run _unload or TemporaryDirectory cleanup.
            parent = int(next(line.split(':', 1)[1].strip() for line in
                              Path(f'/proc/{old}/status').read_text().splitlines()
                              if line.startswith('PPid:')))
            assert parent not in (1, os.getpid(), backend.pid) and alive(parent)
            parent_command = Path(f'/proc/{parent}/cmdline').read_bytes()
            assert b'Syncthing' in parent_command, parent_command
            forced_log_start = Path(log.name).stat().st_size
            os.kill(parent, signal.SIGSTOP)
            rpc('loader/reload_plugin', 'Syncthing')
            new = until_ready(lambda: (pid if (pid := current_pid()) != old else None),
                              'reload after forced plugin termination', timeout=80)
            assert until_ready(lambda: not alive(old), 'helper stopped with killed plugin')
            assert not alive(parent) and unrelated.poll() is None
            forced_console = Path(log.name).read_bytes()[forced_log_start:].decode('utf-8')
            assert 'still alive 5 seconds after stop request! Sending SIGKILL!' in forced_console, forced_console
            report['forcedReloadConsole'] = forced_console
            # This directory belonged to the killed Python owner; only the
            # isolated probe cleans it, after proving its helper has exited.
            assert old_socket.parent.name.startswith('framey-syncthing-')
            shutil.rmtree(old_socket.parent)
            old, old_socket = new, owned_socket(new)
            report['independentState'].update(forcedPluginTerminationReleasesHelper=True,
                forcedReloadPreservesUnrelatedProcess=True, forcedOwnerTempCleanedByFixture=True,
                publishedDeckyForcedTerminationLogVerified=True)
            report['result'] = ('published Decky discovery, disabled defaults, native listener/ownership conflicts, '
                'owned restart, three normal reloads, forced plugin termination/reload and private-socket HTTP transport passed; '
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
