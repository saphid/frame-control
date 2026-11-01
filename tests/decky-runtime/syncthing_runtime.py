"""Actual Syncthing peers with candidate Decky RPC; no systemd/host session."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from check import rpc, until_ready

DIGEST = '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'
# Syncthing v2.1.7 allows 10s for supervised services and another 10s for DB
# close (lib/svcutil and lib/syncthing). Do not apply Decky's 8s budget to it.
SYNCTHING_STOP_SECONDS = 25


def helper_snapshot(pid, socket_path):
    """Read only the exact helper created by this isolated probe."""
    snapshot = {'pid':pid, 'present':False}
    if socket_path is not None:
        snapshot['socketParentExists'] = socket_path.parent.exists()
    if pid is None:
        return snapshot
    proc = Path(f'/proc/{pid}')
    try:
        snapshot['status'] = {key:value.strip() for line in (proc/'status').read_text().splitlines()
                              for key, _, value in [line.partition(':')]
                              if key in ('Name', 'State', 'Pid', 'PPid')}
        snapshot['present'] = True
    except FileNotFoundError:
        pass
    except OSError as error:
        snapshot['readError'] = str(error)
    return snapshot


def verify_loader_shutdown(text, returncode):
    """Reaped helpers and a zero exit alone do not prove clean plugin unload."""
    errors = [marker for marker in ('Error during shutdown:',
              'asyncio.exceptions.CancelledError', 'Task was destroyed but it is pending',
              'Sending SIGKILL!', 'Bad file descriptor') if marker in text]
    assert not errors, f'Decky shutdown errors: {errors}'
    assert returncode == 0, f'Decky loader exit was unsuccessful: {returncode}'
    assert text.count('[main][INFO]: Shutdown finished.') == 1, 'Decky shutdown incomplete'
    assert '[plugin][INFO]: Plugin Syncthing (v0.2.7) has been stopped in ' in text, 'Plugin unload incomplete'


def main():
    assert os.getuid() == 1100 and Path('/repo').is_dir(), 'Use the isolated native runner'
    home = Path.home()
    binary = home/'syncthing'
    shutil.copy('/input/syncthing', binary)
    binary.chmod(0o700)
    cases, processes, logs = [], [], []
    forced = False
    helper_pid, socket_path = None, None
    try:
        for index in range(2):
            folder = home/f'peer-{index}'
            folder.mkdir()
            subprocess.run([str(binary), 'generate', '--home', str(folder), '--no-port-probing'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
            config = ET.parse(folder/'config.xml')
            root = config.getroot()
            for item in root.findall('folder'):
                root.remove(item)
            own_id = root.find('device').get('id')
            gui = root.find('gui')
            gui.find('address').text = f'127.0.0.1:{8384+index}'
            key = gui.find('apikey').text
            assert key
            options = root.find('options')
            for item in options.findall('listenAddress'):
                options.remove(item)
            ET.SubElement(options, 'listenAddress').text = f'tcp://127.0.0.1:{22000+index}'
            values = {'globalAnnounceEnabled':'false', 'localAnnounceEnabled':'false',
                      'relaysEnabled':'false', 'natEnabled':'false', 'urAccepted':'-1',
                      'autoUpgradeIntervalH':'0', 'crashReportingEnabled':'false', 'startBrowser':'false'}
            for field, value in values.items():
                node = options.find(field)
                if node is None:
                    node = ET.SubElement(options, field)
                node.text = value
            files = folder/'private-sync'
            files.mkdir()
            cases.append(dict(folder=folder, config=config, root=root, device=own_id, key=key, files=files))

        def spawn(index):
            return subprocess.Popen([str(binary), 'serve', '--home', str(cases[index]['folder']),
                                     '--no-browser', '--no-restart', '--no-upgrade'],
                                    env=dict(os.environ, STNOUPGRADE='1'), stdout=logs[index],
                                    stderr=logs[index], start_new_session=True)

        for index, case in enumerate(cases):
            peer = cases[1-index]
            device = ET.SubElement(case['root'], 'device', {'id':peer['device'], 'name':'owned-peer',
                'compression':'metadata', 'introducer':'false', 'skipIntroductionRemovals':'false', 'introducedBy':''})
            ET.SubElement(device, 'address').text = f'tcp://127.0.0.1:{22001-index}'
            folder = ET.SubElement(case['root'], 'folder', {'id':'framey-private', 'label':'Framey private test',
                'path':str(case['files']), 'type':'sendreceive', 'rescanIntervalS':'1',
                'fsWatcherEnabled':'false', 'ignorePerms':'false', 'autoNormalize':'true'})
            for own in (case, peer):
                ET.SubElement(folder, 'device', {'id':own['device'], 'introducedBy':''})
            case['config'].write(case['folder']/'config.xml', encoding='utf-8', xml_declaration=True)
            logs.append((case['folder']/'process.log').open('w+'))
            processes.append(spawn(index))

        def request(index, path, method='GET'):
            req = urllib.request.Request(f'http://127.0.0.1:{8384+index}'+path,
                                         headers={'X-API-Key':cases[index]['key']}, method=method)
            with urllib.request.urlopen(req, timeout=3) as response:
                data = response.read()
            return json.loads(data) if data.strip() else None

        def wait(read, description):
            deadline, last = time.monotonic()+50, None
            while time.monotonic() < deadline:
                try:
                    value = read()
                    if value:
                        return value
                except (OSError, ValueError, KeyError) as error:
                    last = str(error)
                assert all(p.poll() is None for p in processes), 'Owned runtime child exited'
                time.sleep(.15)
            raise RuntimeError(description+': '+str(last))

        for index in range(2):
            wait(lambda:request(index, '/rest/system/status'), 'Syncthing startup')
        payload = b'Frame Control private Syncthing transfer\n'*79
        (cases[0]['files']/'owned-marker.txt').write_bytes(payload)
        request(0, '/rest/db/scan?folder=framey-private', 'POST')
        target = cases[1]['files']/'owned-marker.txt'
        wait(lambda:target.is_file() and target.read_bytes() == payload, 'Real peer transfer')
        reverse = b'Frame Control private reverse transfer\n'*43
        (cases[1]['files']/'owned-reverse.txt').write_bytes(reverse)
        request(1, '/rest/db/scan?folder=framey-private', 'POST')
        reverse_target = cases[0]['files']/'owned-reverse.txt'
        wait(lambda:reverse_target.is_file() and reverse_target.read_bytes() == reverse, 'Real reverse transfer')
        assert request(0, '/rest/system/version')['version'] == 'v2.1.7'
        reads = {path:type(request(0, path)).__name__ for path in [
            '/rest/system/status', '/rest/system/version', '/rest/config/options', '/rest/config/devices',
            '/rest/stats/device', '/rest/config/folders', '/rest/stats/folder',
            '/rest/db/status?folder=framey-private', '/rest/system/connections']}
        options = request(0, '/rest/config/options')
        assert not any(options[key] for key in ('globalAnnounceEnabled', 'localAnnounceEnabled', 'relaysEnabled', 'natEnabled'))
        assert request(0, '/rest/system/connections')['connections'][cases[1]['device']]['connected'] is True

        base = home/'decky'
        plugins = base/'plugins'
        plugins.mkdir(parents=True)
        assert hashlib.sha256(Path('/input/official.zip').read_bytes()).hexdigest() == DIGEST
        with zipfile.ZipFile('/input/official.zip') as archive:
            for entry in archive.infolist():
                assert entry.filename.startswith('decky-syncthing/') and '..' not in Path(entry.filename).parts
                destination = plugins/entry.filename
                if entry.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(entry))
        plugin = plugins/'decky-syncthing'
        shutil.copy('/repo/ui/vendor/syncthing-0.2.7/main.py', plugin/'main.py')
        helper = plugin/'bin/decky-syncthing-watchdog'
        shutil.copy('/input/watchdog', helper)
        helper.chmod(0o700)
        loader = base/'PluginLoader'
        shutil.copy('/input/PluginLoader', loader)
        loader.chmod(0o700)
        env = dict(os.environ, UNPRIVILEGED_PATH=str(base), PRIVILEGED_PATH=str(base), CHOWN_PLUGIN_PATH='0',
                   LIVE_RELOAD='0', USE_CEF_CLOSE_WORKAROUND='0', KEEP_SYSTEMD_SERVICE='1',
                   DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/no-service-bus')
        logs.append((home/'decky.log').open('w+'))
        backend = subprocess.Popen([str(loader)], env=env, stdout=logs[-1], stderr=logs[-1], start_new_session=True)
        processes.append(backend)
        plugins_found = until_ready(lambda:rpc('loader/get_plugins'), 'Decky discovery')
        assert any(p['name'] == 'Syncthing' and p['version'] == '0.2.7' for p in plugins_found)

        def legacy(rpc_method, **kwargs):
            result = rpc('loader/call_legacy_plugin_method', 'Syncthing', rpc_method, kwargs)
            assert result['success'], result
            return result['result']

        defaults = json.loads(legacy('get_settings_json'))
        assert defaults['is_setup'] is False and defaults['autostart'] == 'no'
        until_ready(lambda:list(base.rglob('watchdog.pid')), 'watchdog startup', timeout=80)
        helper_pid = int(next(base.rglob('watchdog.pid')).read_text())
        entries = Path(f'/proc/{helper_pid}/environ').read_bytes().split(b'\0')
        socket_path = Path(os.fsdecode(next(e.split(b'=', 1)[1] for e in entries if e.startswith(b'FRAMEY_SYNCTHING_SOCKET='))))

        def fetch(path, headers):
            return legacy('framey_http_fetch', method='GET', path=path, headers=headers)

        proxy = {}
        for path, expected in reads.items():
            reply = fetch(path, {'X-API-Key':cases[0]['key']})
            assert reply['status'] == 200, (path, reply['status'])
            assert type(json.loads(reply['body'])).__name__ == expected, path
            proxy[path] = reply['status']
        completion = fetch('/rest/db/completion?folder=framey-private&device='+cases[1]['device'],
                           {'X-API-Key':cases[0]['key']})
        assert completion['status'] == 200 and json.loads(completion['body'])['completion'] == 100
        denied = fetch('/rest/system/status', {'X-API-Key':'wrong-owned-fixture-key'})
        assert denied['status'] == 403, denied['status']
        # Restart only our retained runtime; preserve its private DB and keys.
        peer = processes[1]
        os.killpg(peer.pid, signal.SIGTERM)
        peer.wait(timeout=SYNCTHING_STOP_SECONDS)
        assert peer.returncode == 0, 'Restarted runtime did not exit successfully'
        processes[1] = spawn(1)
        wait(lambda:request(1, '/rest/system/status'), 'Real runtime restart')
        assert target.read_bytes() == payload and reverse_target.read_bytes() == reverse
        report = {'runtime':'v2.1.7', 'binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'helperSha256':hashlib.sha256(helper.read_bytes()).hexdigest(), 'archiveSha256':DIGEST,
            'independentState':{'twoWaySync':True, 'runtimeRestartPreservedFiles':True,
                'realRestProxy':True, 'realApiKeyErrorPreserved':True, 'completionPercent':100},
            'markerBytes':len(payload), 'markerSha256':hashlib.sha256(payload).hexdigest(),
            'reverseBytes':len(reverse), 'reverseSha256':hashlib.sha256(reverse).hexdigest(),
            'realDeckyRpcProxy':proxy, 'apiKeyErrorStatus':denied['status'], 'installerEnabled':False,
            'syncthingStopBudgetSeconds':SYNCTHING_STOP_SECONDS,
            'serviceManagerVerified':False, 'systemdBus':'absent; service setup stays disabled',
            'realFrameContacted':False}
        # Match the service's KillMode=mixed normal stop: signal the loader,
        # which owns plugin unload. A group signal also kills its plugin and
        # helper, hiding whether the loader actually reaped its descendants.
        backend.send_signal(signal.SIGTERM)
        backend.wait(timeout=8)
        until_ready(lambda:not Path(f'/proc/{helper_pid}').exists(), 'owned helper shutdown')
        assert not socket_path.parent.exists()
        report['independentState']['deckyShutdownStoppedOwnedHelper'] = True
        logs[-1].flush()
        logs[-1].seek(0)
        report['loaderConsole'] = logs[-1].read()
        report['loaderConsoleSha256'] = hashlib.sha256(report['loaderConsole'].encode()).hexdigest()
        verify_loader_shutdown(report['loaderConsole'], backend.returncode)
        report['loaderShutdownVerified'] = True
    except BaseException:
        print('OWNED_HELPER_SNAPSHOT '+json.dumps(helper_snapshot(helper_pid, socket_path)), file=sys.stderr)
        for log in logs:
            log.flush()
            log.seek(0)
            print('=== '+str(Path(log.name).name)+' ===', file=sys.stderr)
            print(log.read(), file=sys.stderr)
        raise
    finally:
        # Ask both peers to stop before waiting, so neither keeps a live peer
        # connection while the other is trying to finish its shutdown.
        stop_times = {}
        for process in reversed(processes):
            if process.poll() is None:
                stop_times[process.pid] = time.monotonic()
                os.killpg(process.pid, signal.SIGTERM)
        elapsed = []
        for process in reversed(processes):
            try:
                budget = SYNCTHING_STOP_SECONDS if process.args[0] == str(binary) else 8
                deadline = stop_times.get(process.pid, time.monotonic())+budget
                process.wait(timeout=max(.01, deadline-time.monotonic()))
                if process.args[0] == str(binary) and process.pid in stop_times:
                    elapsed.append(round(time.monotonic()-stop_times[process.pid], 3))
            except subprocess.TimeoutExpired:
                forced = True
                log = logs[processes.index(process)]
                log.flush()
                log.seek(0)
                print('Owned runtime did not stop normally: '+str(process.args[0]), file=sys.stderr)
                print(log.read()[-5000:], file=sys.stderr)
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
        for log in logs:
            log.close()
    assert not forced, 'An owned runtime required forced shutdown'
    assert all(p.returncode == 0 for p in processes if p.args[0] == str(binary)), 'Runtime exit was unsuccessful'
    report['runtimeStopElapsedUpperBoundsSeconds'] = elapsed
    report['independentState']['allOwnedProcessesReaped'] = True
    print(json.dumps(report))


if __name__ == '__main__':
    main()
