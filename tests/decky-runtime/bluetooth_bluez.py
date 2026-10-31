"""Exercise unmodified Bluetooth through Decky RPC against a synthetic bus."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

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


def exercise(current, plugin, archive, record, backend, private, log):
    # Managed installation must preserve every published executable source.
    with zipfile.ZipFile(archive) as bundle:
        names = [name for name in bundle.namelist() if name.endswith(('.py', '.js'))]
        assert names
        for name in names:
            assert (plugin/Path(name).relative_to(record['folder'])).read_bytes() == bundle.read(name)
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
    before = time.monotonic()
    backend.terminate()  # Packaged loader forwards this once to its Python child.
    backend.wait(timeout=8)
    assert backend.returncode == 0
    log.flush(); log.seek(0); retained = log.read()
    assert 'Bluetooth plugin unloaded' in retained
    assert not any(marker in retained for marker in ('Error during shutdown:',
        'asyncio.exceptions.CancelledError', 'Task was destroyed but it is pending'))
    stop_seconds = round(time.monotonic()-before, 3)
    for process in reversed(private):
        process.terminate(); process.wait(timeout=4)
        assert process.returncode in (0, -15)
    return dict(syntheticBluez=True, privateSystemBus=True, exactPublishedSourcesVerified=len(names),
        pairedDeviceFiltering=True, owningAdapterSelected=True, aliasAndBatteryReplies=True,
        missingDeviceDefaults=True, privateConnectionRoundTrip=True, privatePowerRoundTrip=True,
        unselectedAdapterPreserved=True, syntheticWrites=state['writes'],
        retainedLoaderLogSha256=hashlib.sha256(retained.encode()).hexdigest(),
        loaderShutdownLogChecked=True, loaderExitStatus=backend.returncode, loaderStopSeconds=stop_seconds,
        privateBusAndServiceReaped=True, hostBusExposed=False, realRadioVerified=False,
        realPairingVerified=False, browserVerified=False, realFrameContacted=False,
        physicalControllerVerified=False)
