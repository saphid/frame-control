"""Exercise pinned Bluetooth RPC, private BlueZ and owned child shutdown."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import zipfile
from deck_settings_private import descendants, identity

ADDRESS = 'unix:path=/run/user/1100/framey-bluez-bus'
STATE = Path('/tmp/framey-bluez-state.json')
ROOT = '/org/bluez/hci1'
MAC = '42:00:00:00:00:01'
DEVICE = ROOT+'/dev_42_00_00_00_00_01'


def start(root, env, log, processes, until_ready):
    assert os.getuid() == 1100 and not Path('/run/dbus/system_bus_socket').exists()
    env['DBUS_SYSTEM_BUS_ADDRESS'] = ADDRESS
    bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--address='+ADDRESS],
                           env=env, stdout=log, stderr=log, start_new_session=True)
    processes.append(bus)
    until_ready(lambda: Path(ADDRESS.split('=', 1)[1]).is_socket(), 'owned private BlueZ bus')
    service = subprocess.Popen([sys.executable, str(root/'tests/fixtures/framey-bluez/service.py')],
                               env=env, stdout=log, stderr=log, start_new_session=True)
    processes.append(service)
    until_ready(STATE.is_file, 'synthetic BlueZ objects')
    return bus, service


def stop(backend, log, *, disconnect, after_disconnect=None):
    children = descendants(backend.pid)
    assert children
    before = Path(log.name).read_text()
    closed = []
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
                closed.append(str(path))
        assert len(closed) == 1, closed
        time.sleep(.05)
        if after_disconnect:
            after_disconnect()
    began = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
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
    console = Path(log.name).read_text()[len(before):]
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [marker for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if marker in console]
    elapsed = round(time.monotonic()-began, 3)
    clean = (backend.returncode == 0 and not remaining and not forced and not errors and elapsed < 5
             and all(child['returncode'] == 0 for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and console.count('Bluetooth plugin unloaded') == 1
             and 'Plugin Bluetooth (v3.1.1) has been stopped in ' in console)
    return dict(parentOnlySignal=True, loaderPid=backend.pid, returncode=backend.returncode,
        elapsedSeconds=elapsed, descendantsBefore=children, exactDescendantsRemaining=remaining,
        adoptedChildExits=adopted, closedUnixPeers=closed, forcedPluginKills=forced, errors=errors,
        postEofRpcVerified=bool(disconnect and after_disconnect), console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(), cleanShutdownVerified=clean)


def exercise(current, plugin, archive, record, backend, private, log, *,
             loader, env, processes, rpc, until_ready, regression=False):
    # Preserve every original file, with only a scoped prefix on managed main.py.
    prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
              b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
    with zipfile.ZipFile(archive) as bundle:
        names = [item.filename for item in bundle.infolist() if not item.is_dir()]
        assert names
        for name in names:
            relative = Path(name).relative_to(record['folder'])
            expected = bundle.read(name)
            if str(relative) == 'main.py' and not regression:
                expected = prefix+expected
            assert (plugin/relative).read_bytes() == expected, name
    if not regression:
        assert (plugin/'py_modules/framey_decky_ipc.py').read_bytes() == Path('/repo/ui/framey_decky_ipc.py').read_bytes()
    assert current('get_bluetooth_status') is True  # hci1 owns the paired devices.
    paired = current('get_paired_devices_with_info')
    assert paired == [dict(mac=MAC, name='Private Controller', connected=True, icon='input-gaming', battery=73),
                      dict(mac='42:00:00:00:00:02', name='Private Headphones', connected=False,
                           icon='audio-headphones', battery=None)]
    info = current('get_device_info', MAC.lower())
    assert info == dict(mac=MAC, name='Private Alias', connected=True, icon='input-gaming',
        original_name='Private Controller', paired=True, trusted=True, blocked=False,
        address_type='public', uuids=['private-uuid'], rssi=-42, tx_power=4,
        device_class=1288, appearance=964, battery=73)
    missing = '42:00:00:00:00:FF'
    assert current('get_device_info', missing) == dict(mac=missing, name='Unnamed device',
                                                       connected=False, icon='', battery=None)
    assert current('toggle_device_connection', missing, False) is False
    assert json.loads(STATE.read_text())['writes'] == []
    assert current('toggle_device_connection', MAC, True) is True
    assert current('get_device_info', MAC)['connected'] is False
    assert current('toggle_device_connection', MAC, False) is True
    assert current('get_device_info', MAC)['connected'] is True
    assert current('toggle_bluetooth', False) is True
    assert current('get_bluetooth_status') is False
    assert current('toggle_bluetooth', True) is True
    assert current('get_bluetooth_status') is True
    state = json.loads(STATE.read_text())
    assert state['adapterPowered'] is True and state['otherAdapterPowered'] is False and state['connected'] is True
    assert state['writes'] == [['Disconnect', DEVICE], ['Connect', DEVICE],
        ['Set', ROOT, 'org.bluez.Adapter1', 'Powered', False],
        ['Set', ROOT, 'org.bluez.Adapter1', 'Powered', True]]
    assert ['Get', ROOT, 'org.bluez.Adapter1', 'Powered'] in state['reads']
    assert ['GetAll', DEVICE, 'org.bluez.Device1'] in state['reads']
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(90)'], start_new_session=True)
    processes.append(unrelated)
    def after_eof():
        assert current('get_bluetooth_status') is True
        assert current('get_paired_devices_with_info') == paired
    first = stop(backend, log, disconnect=True, after_disconnect=None if regression else after_eof)
    stops = [first]
    assert first['returncode'] == 0 and not first['exactDescendantsRemaining'], first
    assert unrelated.poll() is None
    if regression:
        assert first['forcedPluginKills'] == 1 and not first['cleanShutdownVerified'], first
        assert 5 <= first['elapsedSeconds'] < 8, first
    else:
        assert first['cleanShutdownVerified'], first
        backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
        processes.append(backend)
        found = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Bluetooth discovery')
        assert len(found) == 1 and found[0]['name'] == record['name']
        assert current('get_bluetooth_status') is True
        assert current('get_paired_devices_with_info') == paired
        second = stop(backend, log, disconnect=False)
        stops.append(second)
        assert second['cleanShutdownVerified'], second
        assert unrelated.poll() is None
    assert json.loads(STATE.read_text())['writes'] == state['writes']
    unrelated.terminate(); unrelated.wait(timeout=4)
    log.flush()
    retained = Path(log.name).read_text()
    for process in reversed(private):
        process.terminate(); process.wait(timeout=4)
        assert process.returncode in (0, -15)
    return dict(syntheticBluez=True, privateSystemBus=True, exactPublishedSourcesVerified=len(names),
        pairedDeviceFiltering=True, owningAdapterSelected=True, aliasAndBatteryReplies=True,
        missingDeviceDefaults=True, privateConnectionRoundTrip=True, privatePowerRoundTrip=True,
        unselectedAdapterPreserved=True, syntheticWrites=state['writes'],
        retainedLoaderLogSha256=hashlib.sha256(retained.encode()).hexdigest(),
        loaderShutdownLogChecked=True, loaderExitStatus=backend.returncode, ownedLoaderStops=stops,
        archiveFilesVerified=names,
        unchangedPublishedFiles=[name for name in names if regression or name != record['folder']+'/main.py'],
        backendSha256=hashlib.sha256((plugin/'main.py').read_bytes()).hexdigest(),
        postEofRpcVerified=not regression, restartBluezReadbackVerified=not regression,
        controlledOriginalForcedKillReproduced=regression, originalBackendUnmodified=regression,
        unrelatedProcessPreserved=True,
        privateBusAndServiceReaped=True, hostBusExposed=False, realRadioVerified=False,
        realPairingVerified=False, browserVerified=False, realFrameContacted=False,
        physicalControllerVerified=False)
