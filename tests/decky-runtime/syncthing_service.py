"""Actual Decky and Syncthing service control; only inside the owned service VM."""

import asyncio, hashlib, json, os, shutil, signal, subprocess, time, urllib.request, xml.etree.ElementTree as ET, zipfile
from pathlib import Path
import websockets
from websockets.exceptions import WebSocketException


async def request(route, args):
    token = (
        urllib.request.urlopen('http://127.0.0.1:1337/auth/token', timeout=3)
        .read()
        .decode()
    )
    async with websockets.connect(
        'ws://127.0.0.1:1337/ws?auth=' + token, open_timeout=5, close_timeout=2
    ) as ws:
        await ws.send(json.dumps({'type': 0, 'id': 1, 'route': route, 'args': args}))
        while True:
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
            if response.get('id') != 1:
                continue
            await ws.send(json.dumps({'type': 3, 'id': 1}))
            assert response['type'] == 1, response
            return response['result']


def rpc(route, *args):
    return asyncio.run(request(route, list(args)))


def wait(read, description):
    end = time.monotonic() + 60
    last = None
    while time.monotonic() < end:
        try:
            value = read()
            if value:
                return value
        except (
            OSError,
            ValueError,
            KeyError,
            TimeoutError,
            WebSocketException,
        ) as error:
            last = str(error)
        time.sleep(0.15)
    raise RuntimeError(description + ': ' + str(last))


def ctl(*args, check=True):
    return subprocess.run(
        ['systemctl', '--user', *args],
        check=check,
        capture_output=True,
        text=True,
        timeout=35,
    ).stdout.strip()


def prop(unit, key):
    return ctl('show', unit, '--property=' + key, '--value')


def main():
    assert (
        os.getuid() == 1100
        and Path('/framey-owned-vm').read_text().strip()
        == 'Frame Control service VM v1'
    )
    home = Path.home()
    service = 'frame-control-syncthing.service'
    backend = None
    logs = []
    directory = home / '.config/systemd/user'
    directory.mkdir(parents=True, exist_ok=True)
    legacy = directory / 'decky-syncthing.service'
    legacy.write_text(
        '[Unit]\nDescription=Private preserved legacy marker\n[Service]\nExecStart=/usr/bin/sleep infinity\n[Install]\nWantedBy=default.target\n'
    )
    ctl('daemon-reload')
    ctl('enable', legacy.name)
    ctl('start', legacy.name)
    legacy_pid = int(prop(legacy.name, 'MainPID'))
    original_legacy = legacy.read_bytes()
    runtime = home / 'runtime'
    runtime.mkdir()
    subprocess.run(
        ['/input/syncthing', 'generate', '--home', str(runtime), '--no-port-probing'],
        check=True,
        capture_output=True,
        timeout=40,
    )
    tree = ET.parse(runtime / 'config.xml')
    root = tree.getroot()
    for folder in root.findall('folder'):
        root.remove(folder)
    key = root.find('gui/apikey').text
    for field, value in {
        'globalAnnounceEnabled': 'false',
        'localAnnounceEnabled': 'false',
        'relaysEnabled': 'false',
        'natEnabled': 'false',
        'urAccepted': '-1',
        'autoUpgradeIntervalH': '0',
        'crashReportingEnabled': 'false',
        'startBrowser': 'false',
    }.items():
        node = root.find('options/' + field)
        if node is None:
            node = ET.SubElement(root.find('options'), field)
        node.text = value
    tree.write(runtime / 'config.xml', encoding='utf-8', xml_declaration=True)
    peer_home = home / 'peer'
    peer_home.mkdir()
    subprocess.run(
        ['/input/syncthing', 'generate', '--home', str(peer_home), '--no-port-probing'],
        check=True,
        capture_output=True,
        timeout=40,
    )
    peer_tree = ET.parse(peer_home / 'config.xml')
    peer_root = peer_tree.getroot()
    for folder in peer_root.findall('folder'):
        peer_root.remove(folder)
    own_id = root.find('device').get('id')
    peer_id = peer_root.find('device').get('id')
    for index, (config_tree, config_root, config_home, other_id) in enumerate(
        [(tree, root, runtime, peer_id), (peer_tree, peer_root, peer_home, own_id)]
    ):
        config_root.find('gui/address').text = f'127.0.0.1:{8384+index}'
        options = config_root.find('options')
        for field, value in {
            'globalAnnounceEnabled': 'false',
            'localAnnounceEnabled': 'false',
            'relaysEnabled': 'false',
            'natEnabled': 'false',
            'urAccepted': '-1',
            'autoUpgradeIntervalH': '0',
            'crashReportingEnabled': 'false',
            'startBrowser': 'false',
        }.items():
            node = options.find(field)
            if node is None:
                node = ET.SubElement(options, field)
            node.text = value
        for listen in options.findall('listenAddress'):
            options.remove(listen)
        ET.SubElement(options, 'listenAddress').text = f'tcp://127.0.0.1:{22000+index}'
        device = ET.SubElement(
            config_root,
            'device',
            {
                'id': other_id,
                'name': 'owned-peer',
                'compression': 'metadata',
                'introducer': 'false',
                'skipIntroductionRemovals': 'false',
                'introducedBy': '',
            },
        )
        ET.SubElement(device, 'address').text = f'tcp://127.0.0.1:{22001-index}'
        files = config_home / 'sync'
        files.mkdir()
        folder = ET.SubElement(
            config_root,
            'folder',
            {
                'id': 'framey-private',
                'label': 'Private service sync',
                'path': str(files),
                'type': 'sendreceive',
                'rescanIntervalS': '1',
                'fsWatcherEnabled': 'false',
                'ignorePerms': 'false',
                'autoNormalize': 'true',
            },
        )
        for device_id in (own_id, peer_id):
            ET.SubElement(folder, 'device', {'id': device_id, 'introducedBy': ''})
        config_tree.write(
            config_home / 'config.xml', encoding='utf-8', xml_declaration=True
        )
    peer_log = (home / 'peer.log').open('w+')
    logs.append(peer_log)
    peer = subprocess.Popen(
        [
            '/input/syncthing',
            'serve',
            '--home',
            str(peer_home),
            '--no-browser',
            '--no-restart',
            '--no-upgrade',
        ],
        env=dict(os.environ, STNOUPGRADE='1'),
        stdout=peer_log,
        stderr=peer_log,
        start_new_session=True,
    )
    cert = (runtime / 'cert.pem').read_bytes()
    (runtime / 'owned-marker').write_text('retain private runtime')
    tools = home / 'bin'
    tools.mkdir()
    shim = tools / 'flatpak'
    shim.write_text(
        "#!/usr/bin/python3\nimport os,sys\nassert sys.argv[1:]==['run','--die-with-parent','--command=syncthing','org.framey.Syncthing','--no-browser','--no-restart']\nos.execv('/input/syncthing',['/input/syncthing','serve','--home','/home/tester/runtime','--no-browser','--no-restart','--no-upgrade'])\n"
    )
    shim.chmod(0o700)
    base = home / 'decky'
    plugins = base / 'plugins'
    plugins.mkdir(parents=True)
    packed = Path('/input/official.zip').read_bytes()
    assert (
        hashlib.sha256(packed).hexdigest()
        == '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'
    )
    with zipfile.ZipFile('/input/official.zip') as archive:
        for entry in archive.infolist():
            assert (
                entry.filename.startswith('decky-syncthing/')
                and '..' not in Path(entry.filename).parts
            )
            destination = plugins / entry.filename
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(entry))
    plugin = plugins / 'decky-syncthing'
    shutil.copy('/input/main.py', plugin / 'main.py')
    helper = plugin / 'bin/decky-syncthing-watchdog'
    shutil.copy('/input/watchdog', helper)
    helper.chmod(0o700)
    loader = base / 'PluginLoader'
    shutil.copy('/input/PluginLoader', loader)
    loader.chmod(0o700)
    env = dict(
        os.environ,
        UNPRIVILEGED_PATH=str(base),
        PRIVILEGED_PATH=str(base),
        CHOWN_PLUGIN_PATH='0',
        LIVE_RELOAD='0',
        USE_CEF_CLOSE_WORKAROUND='0',
        KEEP_SYSTEMD_SERVICE='1',
        PATH=str(tools) + ':' + os.environ['PATH'],
        DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/bus',
        XDG_RUNTIME_DIR='/run/user/1100',
        STNOUPGRADE='1',
    )
    report = {
        'architecture': os.uname().machine,
        'flatpakPackageVerified': False,
        'realFrameContacted': False,
        'systemdManagerActual': True,
    }
    try:
        log = (home / 'decky.log').open('w+')
        logs.append(log)
        backend = subprocess.Popen(
            [str(loader)], env=env, stdout=log, stderr=log, start_new_session=True
        )
        found = wait(lambda: rpc('loader/get_plugins'), 'Decky discovery')
        assert any(p['name'] == 'Syncthing' for p in found)

        def legacy_rpc(rpc_method, **kwargs):
            result = rpc(
                'loader/call_legacy_plugin_method', 'Syncthing', rpc_method, kwargs
            )
            assert result['success'], result
            return result['result']

        assert json.loads(legacy_rpc('get_settings_json'))['is_setup'] is False
        wait(lambda: list(base.rglob('watchdog.pid')), 'candidate watchdog')
        helper_pid = int(next(base.rglob('watchdog.pid')).read_text())

        def http(method, route):
            return legacy_rpc(
                'framey_http_fetch',
                method=method,
                path='/__decky-watchdog/' + route,
                headers={},
            )

        def setting(name, value):
            legacy_rpc('set_setting', setting=name, value=value)

        for name, value in [
            ('mode', 'flatpak'),
            ('flatpak_name', 'org.framey.Syncthing'),
            ('is_setup', True),
            ('autostart', 'no'),
        ]:
            setting(name, value)
        reply = http('POST', 'reload-config')
        assert reply['status'] == 204, reply
        unit = directory / service
        receipt = directory / 'frame-control-syncthing.framey-owner'
        assert (
            unit.read_bytes() == receipt.read_bytes()
            and unit.read_bytes().startswith(
                b'# Frame Control managed Syncthing unit v1\n'
            )
        )
        assert prop(service, 'FragmentPath') == str(unit)
        assert ctl('is-enabled', service, check=False) == 'disabled'
        assert (
            legacy.read_bytes() == original_legacy
            and int(prop(legacy.name, 'MainPID')) == legacy_pid
        )
        report['ownedUnitLoadedByActualSystemd'] = True
        reply = http('POST', 'start')
        assert reply['status'] == 204, reply

        def rest():
            result = legacy_rpc(
                'framey_http_fetch',
                method='GET',
                path='/rest/system/version',
                headers={'X-API-Key': key},
            )
            return result if result['status'] == 200 else None

        assert (
            json.loads(wait(rest, 'service-managed real Syncthing')['body'])['version']
            == 'v2.1.7'
        )
        first = int(prop(service, 'MainPID'))
        assert first > 0
        assert Path(f'/proc/{first}/exe').resolve() == Path('/input/syncthing')
        assert service in Path(f'/proc/{first}/cgroup').read_text()
        report['realSyncthingManagedPid'] = True
        report['realDeckyRpcRest'] = True
        transfer = b'Frame Control private service transfer\n' * 37
        reverse = b'Frame Control private service reverse\n' * 29
        (runtime / 'sync/forward.txt').write_bytes(transfer)
        incoming = peer_home / 'sync/forward.txt'
        wait(
            lambda: incoming.is_file() and incoming.read_bytes() == transfer,
            'managed service forward sync',
        )
        (peer_home / 'sync/reverse.txt').write_bytes(reverse)
        returned = runtime / 'sync/reverse.txt'
        wait(
            lambda: returned.is_file() and returned.read_bytes() == reverse,
            'managed service reverse sync',
        )
        report['managedServiceTwoWaySync'] = True
        report['forwardSha256'] = hashlib.sha256(incoming.read_bytes()).hexdigest()
        report['reverseSha256'] = hashlib.sha256(returned.read_bytes()).hexdigest()
        began = time.monotonic()
        reply = http('POST', 'stop')
        elapsed = round(time.monotonic() - began, 3)
        assert reply['status'] == 204, reply
        assert elapsed < 25, elapsed  # Host panel RPC budget.
        assert (
            prop(service, 'ActiveState') == 'inactive'
            and prop(service, 'MainPID') == '0'
        )
        assert not Path(f'/proc/{first}').exists()
        report['stopRpcElapsedSeconds'] = elapsed
        report['actualStopJobReapedRuntime'] = True
        assert (runtime / 'cert.pem').read_bytes() == cert and (
            runtime / 'owned-marker'
        ).read_text() == 'retain private runtime'
        assert int(prop(legacy.name, 'MainPID')) == legacy_pid
        report['legacyRunningUnitPreserved'] = True
        report['retainedCertificateAndMarker'] = True
        setting('autostart', 'boot')
        reply = http('POST', 'reload-config')
        assert reply['status'] == 204, reply
        enabled = directory / 'default.target.wants' / service
        legacy_enabled = directory / 'default.target.wants' / legacy.name
        assert (
            ctl('is-enabled', service) == 'enabled'
            and enabled.is_symlink()
            and enabled.resolve() == unit
        )
        assert (
            legacy_enabled.is_symlink()
            and int(prop(legacy.name, 'MainPID')) == legacy_pid
        )
        setting('autostart', 'no')
        reply = http('POST', 'reload-config')
        assert reply['status'] == 204, reply
        assert not enabled.exists() and legacy_enabled.is_symlink()
        report['actualEnableDisableLinks'] = True
        reply = http('POST', 'start')
        assert reply['status'] == 204, reply
        assert (
            json.loads(wait(rest, 'retained managed restart')['body'])['version']
            == 'v2.1.7'
        )
        assert (
            returned.read_bytes() == reverse
            and (runtime / 'cert.pem').read_bytes() == cert
        )
        external = directory / 'framey-owned-external.service'
        external.write_text(
            '[Unit]\nDescription=Owned external Syncthing fixture\n[Service]\nExecStart=/input/syncthing serve --home=/home/tester/runtime --no-browser --no-restart --no-upgrade\n[Install]\nWantedBy=default.target\n'
        )
        ctl('daemon-reload')
        setting('mode', 'systemd')
        setting('service_name', external.name)
        began = time.monotonic()
        reply = http('POST', 'reload-config')
        assert reply['status'] == 204, reply
        report['externalTransitionRpcElapsedSeconds'] = round(
            time.monotonic() - began, 3
        )
        assert report['externalTransitionRpcElapsedSeconds'] < 25
        assert (
            not unit.exists()
            and not receipt.exists()
            and (directory / 'frame-control-syncthing.framey-lock').is_file()
        )
        assert prop(service, 'MainPID') == '0'
        assert (
            legacy.read_bytes() == original_legacy
            and int(prop(legacy.name, 'MainPID')) == legacy_pid
        )
        report['ownedTransitionRemovedOnlyCandidateUnit'] = True
        reply = http('POST', 'start')
        assert reply['status'] == 204, reply
        assert (
            json.loads(wait(rest, 'actual external Syncthing service')['body'])[
                'version'
            ]
            == 'v2.1.7'
        )
        external_pid = int(prop(external.name, 'MainPID'))
        assert (
            external_pid > 0
            and external.name in Path(f'/proc/{external_pid}/cgroup').read_text()
        )
        reply = http('POST', 'stop')
        assert reply['status'] == 204, reply
        assert (
            prop(external.name, 'MainPID') == '0'
            and not Path(f'/proc/{external_pid}').exists()
        )
        assert (
            returned.read_bytes() == reverse
            and (runtime / 'cert.pem').read_bytes() == cert
        )
        report['actualExternalUserServiceControl'] = True
        report['retainedSyncAcrossServiceTransition'] = True
    finally:
        ctl('stop', service, check=False)
        ctl('stop', 'framey-owned-external.service', check=False)
        ctl('stop', legacy.name, check=False)
        if peer.poll() is None:
            os.killpg(peer.pid, signal.SIGTERM)
        peer.wait(timeout=30)
        assert peer.returncode == 0
        if backend is not None:
            if backend.poll() is None:
                os.killpg(backend.pid, signal.SIGTERM)
            backend.wait(timeout=15)
        for log in logs:
            log.close()
    assert not Path(f'/proc/{helper_pid}').exists()
    report['ownedCleanup'] = True
    print('FRAMEY_USER_SERVICE_JSON=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
