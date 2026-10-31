"""Audit published Bluetooth UI -> native Decky -> owned synthetic BlueZ."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

root = Path('/tmp/framey-bluetooth-private-bluez-mppkd9qczt')
output = Path(sys.argv[1])
fixture = Path(sys.argv[2]) if len(sys.argv)>2 else Path('/tmp/framey-bluetooth-browser-fixture-v2-mppkd9qczt')
head = '6a2175e3f7fbfd1388db54a08a5942b0e7b5e4fd'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
report = json.loads((output/'result.json').read_text())
inputs = json.loads((output/'inputs.json').read_text())
assert report['inputs'] == inputs and inputs['sourceRevision'] == head
assert inputs['architecture'] == 'x86_64'
assert inputs['loaderSha256'] == 'e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181'
assert inputs['privateTestBridge'] is True
for key in ('realFrameContacted', 'networkDevice', 'hostBusExposed', 'productionHttpParentVerified'):
    assert inputs[key] is False
for name, digest in inputs['sourceSha256'].items():
    assert sha(subprocess.check_output(['git', 'show', head+':'+name], cwd=root)) == digest, name
for name, path in [('probe.py', fixture/'probe.py'), ('runner', fixture/'run.py'),
    ('browser_common.py', Path('/tmp/framey-terminal-browser-candidate-mppkd9qczt/tests/decky-runtime/terminal_browser.py')),
    ('guest_result.py', root/'tests/decky-runtime/guest_result.py')]:
    assert sha(path.read_bytes()) == inputs['auxiliarySourceSha256'][name], name
spec = importlib.util.spec_from_file_location('bluetooth_independent_codec', root/'tests/decky-runtime/guest_result.py')
codec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)
packet = (output/'guest-result.packet').read_bytes()
assert sha(packet) == report['guestPacketSha256'] and codec.decode(packet) == report['guest']
assert report['success'] is True and report['ownedQemuReaped'] is True
guest = report['guest']
assert guest['success'] is True and guest['exitStatus'] == 0 and guest['ownedUserManagerStopped'] is True
assert guest['realFrameContacted'] is False
browser = guest['browser']
for key in ('success', 'syntheticInput', 'syntheticBluez', 'privateBridge',
    'actualFrontendConnectionRoundTrip', 'actualFrontendPowerRoundTrip',
    'poweredOffActivationDidNotWrite', 'actualFrontendRefresh', 'backendRestartVisible',
    'pairedFilterAndBatteryVisible', 'ownedBrowserReaped', 'ownedHttpStopped',
    'nativeEventSocketsClosed', 'ownedLoaderProcessesReaped', 'privateBusAndServiceReaped'):
    assert browser[key] is True, key
for key in ('hostBusExposed', 'realRadioVerified', 'realPairingVerified',
    'realFrameContacted', 'physicalControllerVerified', 'productionHttpParentVerified',
    'realSteamCef', 'browserSandboxDisabled'):
    assert browser[key] is False, key
assert not any(browser.get(k) for k in ('error', 'cleanupError', 'bridgeFailures'))
assert browser['unchangedPublishedSources'] == 31
assert len(browser['loaderStops']) == browser['loaderShutdownsLogged'] == 2
assert all(s['returncode'] == 0 and 0 <= s['elapsedSeconds'] < 10 for s in browser['loaderStops'])
log = browser['loaderLog']
assert log.count('Shutdown finished.') == log.count('Bluetooth plugin unloaded') == 2
assert not any(marker in log for marker in ('Error during shutdown:',
    'asyncio.exceptions.CancelledError', 'Task was destroyed but it is pending'))
stages = browser['stages']
assert [s['stage'] for s in stages] == ['loaded', 'disconnected', 'connected', 'off', 'off-activation', 'on', 'refreshed', 'loaded']
for stage in stages:
    assert stage['errors'] == [] and len(stage['devices']) == 2
    assert {d['name'] for d in stage['devices']} == {'Private Controller', 'Private Headphones'}
    assert 'Unpaired Canary' not in stage['text']
    assert all(d['off'] is (not stage['powered']) for d in stage['devices'])
for index, stage in enumerate(stages):
    controller = next(d for d in stage['devices'] if d['name'] == 'Private Controller')
    assert controller['status'].strip().startswith('Not connected' if index == 1 else 'Connected')
    assert '73%' in controller['status']
    assert stage['powered'] is (index not in (3, 4))
state = browser['privateBluezState']
device = '/org/bluez/hci1/dev_42_00_00_00_00_01'
assert state['synthetic'] is True and state['adapterPowered'] is True and state['connected'] is True
assert state['otherAdapterPowered'] is False
assert state['writes'] == [['Disconnect', device], ['Connect', device],
    ['Set', '/org/bluez/hci1', 'org.bluez.Adapter1', 'Powered', False],
    ['Set', '/org/bluez/hci1', 'org.bluez.Adapter1', 'Powered', True]]
calls = browser['calls']
assert all(c['method'] in {'get_bluetooth_status', 'get_paired_devices_with_info',
    'get_device_info', 'toggle_device_connection', 'toggle_bluetooth'} for c in calls)
assert [c['args'] for c in calls if c['method'] == 'toggle_device_connection'] == [
    ['42:00:00:00:00:01', True], ['42:00:00:00:00:01', False]]
assert [c['args'] for c in calls if c['method'] == 'toggle_bluetooth'] == [[False], [True]]
assert all(c['result'] is True for c in calls if c['method'].startswith('toggle_'))
assert browser['sandboxedRenderers']
for renderer in browser['sandboxedRenderers']:
    lineage = renderer['ancestryToBrowser']
    assert renderer['seccomp'] == 2 and renderer['noNewPrivs'] == 1
    assert len(lineage) >= 2 and len(lineage) == len(set(lineage)) and lineage[0] == renderer['pid']
assert set(browser['screenshots']) == {'initial', 'disconnected', 'poweredOff', 'restarted'}
screenshots = {}
for name, encoded in browser['screenshots'].items():
    data = base64.b64decode(encoded, validate=True)
    assert data == (output/(name+'.png')).read_bytes()
    assert data.startswith(b'\x89PNG\r\n\x1a\n') and 0 < len(data) < 2*1024**2
    assert struct.unpack('>II', data[16:24]) == (1240, 1013)
    screenshots[name] = sha(data)
summary = dict(head=head, architecture='x86_64', allProductSourceHashesVerified=True,
    productSourceCount=len(inputs['sourceSha256']), auxiliarySourcesSeparatelyFingerprinted=True,
    resultPacketSha256=sha(packet), resultPacketVerified=True, loaderStops=browser['loaderStops'],
    actualFrontendConnectionRoundTrip=True, actualFrontendPowerRoundTrip=True,
    poweredOffActivationDidNotWrite=True, actualFrontendRefresh=True, backendRestartVisible=True,
    pairedFilterAndBatteryVisible=True, syntheticWrites=state['writes'],
    rendererSandboxVerified=True, ownedCleanupVerified=True, screenshotSha256=screenshots,
    capturesVisuallyInspected=False, privateBridge=True, syntheticInput=True, syntheticBluez=True,
    productionHttpParentVerified=False, realSteamCef=False, realFrameContacted=False,
    physicalControllerVerified=False, realRadioVerified=False, realPairingVerified=False)
(output/'verified.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
