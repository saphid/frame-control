"""Actual shipped sample backend RPCs in a disposable, networkless native container."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import traceback
import zipfile

from check import rpc, until_ready
from deck_settings_private import descendants, identity
from timer_lifecycle import Client

HOME = Path('/home/tester')
NAME = 'Framey Settings Sample'
BASE = HOME/'.local/share/frame-control/decky'
SETTINGS = BASE/'settings/framey-settings/settings.json'
REPORT = dict(success=False, cleanShutdownVerified=False, realFrameContacted=False,
              browserVerified=False, physicalControllerVerified=False, transcript=[], stops=[])
PROCESSES = []


def stop(backend, log):
    owned = descendants(backend.pid)
    assert owned, 'published loader must own its plugin child'
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

    async def after_eof():
        async with Client(NAME, REPORT['transcript']) as client:
            expected = json.loads(SETTINGS.read_bytes())['enabled']
            assert await client.call('get_setting', 'enabled', not expected) is expected

    asyncio.run(after_eof())
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
    clean = (backend.returncode == 0 and not remaining
             and all(p['returncode'] == 0 for p in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and console.count(f'[plugin][INFO]: Plugin {NAME} has been stopped in ') == 1
             and not any(s in console for s in ('Sending SIGKILL!', 'Error during shutdown:',
                         'Task was destroyed but it is pending', 'asyncio.exceptions.CancelledError')))
    result = dict(parentOnlySignal=True, closedUnixPeers=closed, postEofRpcVerified=True,
                  elapsedSeconds=round(time.monotonic()-began, 3),
                  descendantsBefore=owned, exactDescendantsRemaining=remaining,
                  adoptedChildExits=adopted, loaderReturncode=backend.returncode, console=console,
                  consoleSha256=hashlib.sha256(console.encode()).hexdigest(), cleanShutdownVerified=clean)
    REPORT['stops'].append(result)
    assert clean, result


async def exercise(cycle):
    async with Client(NAME, REPORT['transcript']) as client:
        if cycle == 0:
            assert await client.call('get_setting', 'enabled', False) is False
            assert not SETTINGS.exists(), 'default reads must not create settings'
            assert await client.call('set_setting', 'enabled', True) is True
        elif cycle == 1:
            assert await client.call('get_setting', 'enabled', False) is True
            assert await client.call('set_setting', 'enabled', False) is True
        else:
            # Opposite default distinguishes persisted false from a missing value.
            assert await client.call('get_setting', 'enabled', True) is False
        expected = dict(schema=1, enabled=cycle == 0)
        assert json.loads(SETTINGS.read_bytes()) == expected
        assert SETTINGS.stat().st_mode & 0o777 == 0o600
        committed = SETTINGS.read_bytes()
        for method, args in [('set_setting', ['other', True]), ('set_setting', ['enabled', 'true'])]:
            rejected = await client.call(method, *args, success=False)
            assert rejected['type'] == -1, rejected
            assert SETTINGS.read_bytes() == committed
        if cycle == 1:
            for invalid in [b'{damaged', b'{"schema":2,"enabled":true}', b'{"schema":1,"enabled":"false"}']:
                SETTINGS.write_bytes(invalid)
                for method, args in [('get_setting', ['enabled', True]), ('set_setting', ['enabled', True])]:
                    rejected = await client.call(method, *args, success=False)
                    assert rejected['type'] == -1, rejected
                    assert SETTINGS.read_bytes() == invalid
            SETTINGS.write_bytes(committed)
            assert await client.call('get_setting', 'enabled', True) is False
        assert not list(SETTINGS.parent.glob('.settings-*'))
        REPORT.setdefault('savedSnapshots', []).append(dict(cycle=cycle, value=expected,
            sha256=hashlib.sha256(committed).hexdigest(), mode=oct(SETTINGS.stat().st_mode & 0o777)))


def main():
    assert os.getuid() == 1100 and Path.home() == HOME
    assert not Path('/sys/class/net/eth0').exists()
    plugin = BASE/'plugins/framey-settings'
    plugin.mkdir(parents=True)
    with zipfile.ZipFile('/input/sample.zip') as archive:
        assert set(archive.namelist()) == {'framey-settings/'+p for p in ('plugin.json', 'main.py', 'py_modules/framey_decky_ipc.py', 'dist/index.js')}
        for name in archive.namelist():
            path = BASE/'plugins'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    manifest = json.loads((plugin/'plugin.json').read_text())
    assert manifest['name'] == NAME and manifest['api_version'] == 2 and not manifest['flags']
    assert (plugin/'main.py').read_bytes() == Path('/repo/examples/framey-settings/main.py').read_bytes()
    assert (plugin/'py_modules/framey_decky_ipc.py').read_bytes() == Path('/repo/ui/framey_decky_ipc.py').read_bytes()
    loader = BASE/'PluginLoader'
    shutil.copyfile('/input/PluginLoader', loader)
    loader.chmod(0o700)
    (HOME/'.local/share/Steam/steamui/images').mkdir(parents=True)
    env = dict(os.environ, UNPRIVILEGED_PATH=str(BASE), PRIVILEGED_PATH=str(BASE),
               CHOWN_PLUGIN_PATH='0', LIVE_RELOAD='0', USE_CEF_CLOSE_WORKAROUND='0', KEEP_SYSTEMD_SERVICE='1',
               DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/bus')
    with (HOME/'sample-runtime.log').open('w+') as log:
        sibling = subprocess.Popen(['/bin/sleep', '120'], start_new_session=True)
        PROCESSES.append(sibling)
        for cycle in range(3):
            backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
            PROCESSES.append(backend)
            found = until_ready(lambda: rpc('loader/get_plugins'), 'published sample discovery')
            assert len(found) == 1 and found[0]['name'] == NAME and not found[0]['disabled'], found
            REPORT.setdefault('discoveries', []).append(found)
            asyncio.run(exercise(cycle))
            stop(backend, log)
            assert json.loads(SETTINGS.read_bytes()) == dict(schema=1, enabled=cycle == 0)
            assert sibling.poll() is None, 'unrelated sibling must survive loader stop'
        REPORT.update(success=True, cleanShutdownVerified=True, realLoaderRestart=True, loaderRestarts=2,
                      privateSettingsPersisted=True, malformedAndFutureSchemaPreserved=True,
                      unrelatedSiblingPreserved=True, sampleBackendUnmodified=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        REPORT['error'] = traceback.format_exc()
    finally:
        # Failure containment is explicitly separate from clean-stop evidence.
        REPORT['forcedFixtureCleanup'] = []
        for process in reversed(PROCESSES):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
                    REPORT['forcedFixtureCleanup'].append(process.pid)
        log = HOME/'sample-runtime.log'
        if log.exists():
            REPORT['console'] = log.read_text()
            REPORT['consoleSha256'] = hashlib.sha256(REPORT['console'].encode()).hexdigest()
        print(json.dumps(REPORT))
    raise SystemExit(0 if REPORT['success'] else 1)
