"""Actual legacy service/profile migration, only inside the owned package VM."""

import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from syncthing_service import ctl, prop, rpc, wait


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if (os.getuid() != 1100 or not Path('/framey-owned-vm').is_file()
            or Path('/framey-owned-vm').read_text() != 'Frame Control Flatpak VM v1\n'):
        raise RuntimeError('Only the private signed-package VM may run migration')
    home = Path.home()
    app = 'me.kozec.syncthingtk'
    inputs = json.loads(Path('/input/flatpak-inputs.json').read_text())
    run = ['/usr/bin/flatpak', 'run', '--command=syncthing', app]
    runtime = home / 'migration-legacy-state'
    assert not runtime.exists()
    runtime.mkdir(mode=0o700)
    subprocess.run(run + ['generate', '--home', str(runtime)],
                   check=True, capture_output=True, text=True, timeout=60)
    config = runtime / 'config.xml'
    tree = ET.parse(config)
    root = tree.getroot()
    key = root.find('gui/apikey').text
    device_id = root.find('device').get('id')
    root.find('gui/address').text = '127.0.0.1:8386'
    for folder in root.findall('folder'):
        root.remove(folder)
    data = runtime / 'sync'
    data.mkdir()
    marker = data / 'retained.txt'
    marker.write_bytes(b'private legacy migration data\n')
    folder = ET.SubElement(root, 'folder', id='migration-retained', label='Retained legacy data',
                           path=str(data), type='sendreceive', fsWatcherEnabled='false')
    ET.SubElement(folder, 'device', id=device_id, introducedBy='')
    options = root.find('options')
    for field, value in {
        'globalAnnounceEnabled': 'false', 'localAnnounceEnabled': 'false',
        'relaysEnabled': 'false', 'natEnabled': 'false', 'urAccepted': '-1',
        'autoUpgradeIntervalH': '0', 'crashReportingEnabled': 'false',
        'startBrowser': 'false',
    }.items():
        node = options.find(field)
        if node is None:
            node = ET.SubElement(options, field)
        node.text = value
    for address in options.findall('listenAddress'):
        options.remove(address)
    ET.SubElement(options, 'listenAddress').text = 'tcp://127.0.0.1:22006'
    tree.write(config, encoding='utf-8', xml_declaration=True)
    packaged_sha = subprocess.check_output(
        ['/usr/bin/flatpak', 'run', '--command=sha256sum', app, '/app/bin/syncthing'],
        text=True, timeout=60,
    ).split()[0]
    directory = home / '.config/systemd/user'
    directory.mkdir(parents=True, exist_ok=True)
    unit = directory / 'decky-syncthing.service'
    managed = directory / 'frame-control-syncthing.service'
    receipt = directory / 'frame-control-syncthing.framey-owner'
    assert not unit.exists() and not managed.exists() and not receipt.exists()
    unit_bytes = (
        '[Unit]\nDescription=Private pre-existing Syncthing migration fixture\n'
        '[Service]\nExecStart=/usr/bin/flatpak run --die-with-parent '
        f'--command=syncthing {app} serve --home {runtime} --no-browser --no-restart\n'
        '[Install]\nWantedBy=default.target\n'
    ).encode()
    unit.write_bytes(unit_bytes)
    backend = unrelated = None
    helper_pid = None
    logs = []
    report = dict(architecture=os.uname().machine, installerEnabled=False,
                  realFrameContacted=False, flatpakPackageVerified=True)

    def legacy_rest(route):
        request = urllib.request.Request('http://127.0.0.1:8386/rest/' + route,
                                         headers={'X-API-Key': key})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def identity(main_pid):
        found = []
        for process in Path('/proc').iterdir():
            if not process.name.isdigit():
                continue
            try:
                args = (process / 'cmdline').read_bytes().split(b'\0')
                if os.fsencode(runtime) not in args or (process / 'exe').resolve().name != 'syncthing':
                    continue
                assert sha(process / 'exe') == packaged_sha
                info = configparser.ConfigParser()
                info.read_string((process / 'root/.flatpak-info').read_text())
                assert info['Application']['name'] == app
                for kind in ('app', 'runtime'):
                    assert info['Instance'][kind + '-commit'] == inputs['bundles'][kind]['commit']
                assert os.readlink(process / 'ns/mnt') != os.readlink('/proc/self/ns/mnt')
                lineage = [int(process.name)]
                while lineage[-1] != main_pid:
                    assert len(lineage) < 16
                    parent = int(Path(f'/proc/{lineage[-1]}/stat').read_text().rsplit(')', 1)[1].split()[1])
                    assert parent > 1 and parent not in lineage
                    lineage.append(parent)
                found.append(dict(pid=int(process.name), ancestryToMainPid=lineage,
                                  executableSha256=packaged_sha,
                                  appCommit=info['Instance']['app-commit'],
                                  runtimeCommit=info['Instance']['runtime-commit']))
            except FileNotFoundError:
                continue
        assert found
        return sorted(found, key=lambda item: item['pid'])

    try:
        ctl('daemon-reload')
        ctl('enable', unit.name)
        ctl('start', unit.name)
        assert wait(lambda: legacy_rest('system/version'), 'legacy signed package')['version'] == 'v1.27.3'
        assert legacy_rest('system/status')['myID'] == device_id
        legacy_pid = int(prop(unit.name, 'MainPID'))
        before_identity = identity(legacy_pid)
        retained = {name: sha(runtime / name) for name in ('config.xml', 'cert.pem', 'key.pem', 'sync/retained.txt')}
        report.update(actualLegacySignedPackage=True, legacyIdentityBefore=before_identity,
                      legacyMainPidBefore=legacy_pid,
                      packagedBinarySha256=packaged_sha, retainedFilesSha256=retained)
        base = home / 'decky-migration'
        plugins = base / 'plugins'
        plugins.mkdir(parents=True)
        archive = Path('/input/official.zip')
        assert sha(archive) == '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'
        with zipfile.ZipFile(archive) as packed:
            for entry in packed.infolist():
                assert entry.filename.startswith('decky-syncthing/') and '..' not in Path(entry.filename).parts
                target = plugins / entry.filename
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(packed.read(entry))
        plugin = plugins / 'decky-syncthing'
        shutil.copy('/input/main.py', plugin / 'main.py')
        shutil.copy('/input/watchdog', plugin / 'bin/decky-syncthing-watchdog')
        (plugin / 'bin/decky-syncthing-watchdog').chmod(0o700)
        settings_path = base / 'settings/decky-syncthing/decky-syncthing.json'
        settings_path.parent.mkdir(parents=True)
        old = dict(config_version=1, autostart=True, flatpak_name=app, port=8386,
                   api_key=key, basic_auth_user='', basic_auth_pass='', keep_running_on_desktop=True)
        settings_path.write_text(json.dumps(old))
        distractor = home / 'migration-unrelated/decky-syncthing-watchdog'
        distractor.parent.mkdir()
        shutil.copy('/usr/bin/sleep', distractor)
        unrelated = subprocess.Popen([str(distractor), '900'], start_new_session=True)
        loader = base / 'PluginLoader'
        shutil.copy('/input/PluginLoader', loader)
        loader.chmod(0o700)
        env = dict(os.environ, UNPRIVILEGED_PATH=str(base), PRIVILEGED_PATH=str(base),
                   CHOWN_PLUGIN_PATH='0', LIVE_RELOAD='0', USE_CEF_CLOSE_WORKAROUND='0',
                   KEEP_SYSTEMD_SERVICE='1', DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/bus',
                   XDG_RUNTIME_DIR='/run/user/1100', STNOUPGRADE='1')
        log = (home / 'migration-decky.log').open('w+')
        logs.append(log)
        backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
        wait(lambda: rpc('loader/get_plugins'), 'migration Decky discovery')

        def current_pid():
            paths = list(base.rglob('watchdog.pid'))
            if len(paths) != 1:
                return None
            pid = int(paths[0].read_text())
            return pid if Path(f'/proc/{pid}/exe').exists() else None

        helper_pid = wait(current_pid, 'migrated owned helper')

        def method(name, **kwargs):
            result = rpc('loader/call_legacy_plugin_method', 'Syncthing', name, kwargs)
            assert result['success']
            return result['result']

        def http(verb, route, headers=None):
            return method('framey_http_fetch', method=verb, path=route, headers=headers or {})

        migrated = json.loads(method('get_settings_json'))
        assert migrated == json.loads(settings_path.read_text())
        assert migrated['config_version'] == 2 and migrated['is_setup'] == 'migratingV2'
        assert migrated['mode'] == 'flatpak' and migrated['flatpak_name'] == app
        assert migrated['flatpak_binary'] == 'syncthing' and migrated['autostart'] == 'gamescope'
        assert migrated['port'] == 8386 and migrated['api_key'] == key
        assert migrated['keep_running_on_desktop'] is True
        for verb, route in [('GET', 'state'), ('POST', 'start'), ('POST', 'stop')]:
            assert http(verb, '/__decky-watchdog/' + route)['status'] == (200 if verb == 'GET' else 204)
            assert int(prop(unit.name, 'MainPID')) == legacy_pid
            assert unit.read_bytes() == unit_bytes and ctl('is-enabled', unit.name) == 'enabled'
            assert identity(legacy_pid) == before_identity
            assert {name: sha(runtime / name) for name in retained} == retained
            assert not managed.exists() and not receipt.exists() and unrelated.poll() is None
        report.update(v1SettingsMigratedAndPersisted=True, pendingSetupPreservedLiveLegacy=True,
                      legacyUnitAndEnablementPreserved=True, configCertificateDataPreserved=True,
                      unrelatedHelperPreserved=True)
        # Explicitly choose the existing service; no service is adopted while
        # the migrated profile still requires user completion.
        for name, value in [('mode', 'systemd'), ('service_name', unit.name),
                            ('autostart', 'boot'), ('is_setup', True)]:
            method('set_setting', setting=name, value=value)
        assert http('POST', '/__decky-watchdog/reload-config')['status'] == 204
        response = http('GET', '/rest/system/status', {'X-API-Key': key})
        assert response['status'] == 200 and json.loads(response['body'])['myID'] == device_id
        assert http('GET', '/rest/system/status')['status'] == 403
        assert http('POST', '/__decky-watchdog/stop')['status'] == 204
        assert prop(unit.name, 'MainPID') == '0'
        assert all(not Path(f"/proc/{entry['pid']}").exists() for entry in before_identity)
        assert http('POST', '/__decky-watchdog/start')['status'] == 204
        wait(lambda: legacy_rest('system/status'), 'explicit legacy restart')
        restarted_pid = int(prop(unit.name, 'MainPID'))
        assert restarted_pid > 0 and restarted_pid != legacy_pid
        restarted = identity(restarted_pid)
        assert {name: sha(runtime / name) for name in retained} == retained
        assert unit.read_bytes() == unit_bytes and unrelated.poll() is None
        report.update(explicitExternalControlAndAuth=True, actualLegacyStopRestart=True,
                      legacyDataRetainedAfterRestart=True, legacyIdentityAfterRestart=restarted,
                      legacyMainPidAfterRestart=restarted_pid)
    finally:
        if backend is not None:
            if backend.poll() is None:
                os.killpg(backend.pid, signal.SIGTERM)
            backend.wait(timeout=20)
        if helper_pid is not None:
            wait(lambda: not Path(f'/proc/{helper_pid}').exists(), 'migration helper reaped')
        if unrelated is not None:
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait(timeout=5)
        if unit.exists():
            assert unit.read_bytes() == unit_bytes
            ctl('disable', unit.name, check=False)
            ctl('stop', unit.name)
            assert prop(unit.name, 'MainPID') == '0'
            unit.unlink()
            ctl('daemon-reload')
        for log in logs:
            log.seek(0)
            print(log.read()[-2500:], flush=True)
            log.close()
    assert {name: sha(runtime / name) for name in retained} == retained
    assert not managed.exists() and not receipt.exists()
    assert app not in subprocess.check_output(['/usr/bin/flatpak', 'ps', '--columns=application'], text=True, timeout=20)
    report.update(ownedProcessesReaped=True, ownedLegacyFixtureRemoved=True,
                  noOwnedFlatpakInstancesRemain=True, retainedRuntime=str(runtime))
    print('FRAMEY_MIGRATION_JSON=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
