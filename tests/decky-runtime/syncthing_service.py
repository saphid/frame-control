"""Actual Decky and Syncthing service control; only inside the owned service VM."""

import asyncio, configparser, hashlib, json, os, shutil, signal, subprocess, sys, time, urllib.request, xml.etree.ElementTree as ET, zipfile
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


def main(signed_flatpak=False):
    assert (
        os.getuid() == 1100
        and Path('/framey-owned-vm').read_text().strip()
        == ('Frame Control Flatpak VM v1' if signed_flatpak else 'Frame Control service VM v1')
    )
    home = Path.home()
    app = 'me.kozec.syncthingtk' if signed_flatpak else 'org.framey.Syncthing'
    version = 'v1.27.3' if signed_flatpak else 'v2.1.7'
    launcher = (
        ['/usr/bin/flatpak', 'run', '--die-with-parent', '--env=STNOUPGRADE=1',
         '--command=syncthing', app]
        if signed_flatpak else ['/input/syncthing']
    )

    def generate(directory=None):
        command = launcher + ['generate']
        if directory is not None:
            command += ['--home', str(directory)]
        if not signed_flatpak:
            command += ['--no-port-probing']
        subprocess.run(command, check=True, capture_output=True, timeout=60)

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
    if signed_flatpak:
        # Use the package's actual default; the candidate unit adds no --home.
        paths = subprocess.check_output(launcher + ['--paths'], text=True, timeout=40)
        lines = paths.splitlines()
        config_path = Path(lines[lines.index('Configuration file:') + 1].strip())
        runtime = config_path.parent
        assert runtime.is_relative_to(home / '.var/app' / app)
        assert config_path.name == 'config.xml' and not config_path.exists()
        generate()
        assert config_path.is_file()
        packaged_binary_sha = subprocess.check_output(
            ['/usr/bin/flatpak', 'run', '--command=sha256sum', app, '/app/bin/syncthing'],
            text=True, timeout=40,
        ).split()[0]
    else:
        runtime = home / 'runtime'
        runtime.mkdir()
        generate(runtime)
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
    generate(peer_home)
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
        launcher + [
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
    tools.mkdir(exist_ok=True)
    shim = tools / 'flatpak'
    if not signed_flatpak:
        shim.write_text(
            "#!/usr/bin/python3\nimport os,sys\nassert sys.argv[1:]==['run','--die-with-parent','--command=syncthing','org.framey.Syncthing','--no-browser','--no-restart']\nos.execv('/input/syncthing',['/input/syncthing','serve','--home','/home/tester/runtime','--no-browser','--no-restart','--no-upgrade'])\n"
        )
        shim.chmod(0o700)
    else:
        assert not shim.exists() and shutil.which('flatpak') == '/usr/bin/flatpak'
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
        'flatpakPackageVerified': signed_flatpak,
        'realFrameContacted': False,
        'systemdManagerActual': True,
    }
    if signed_flatpak:
        report.update(defaultPackagePaths=paths, defaultConfigPath=str(config_path),
                      packagedBinarySha256=packaged_binary_sha)

    def runtime_identity(unit):
        main_pid = int(prop(unit, 'MainPID'))
        assert main_pid > 0
        if not signed_flatpak:
            assert Path(f'/proc/{main_pid}/exe').resolve() == Path('/input/syncthing')
            assert unit in Path(f'/proc/{main_pid}/cgroup').read_text()
            return [main_pid]
        group = prop(unit, 'ControlGroup')
        assert group.startswith('/') and group != '/'
        # Flatpak moves its process tree into its own transient app scope.
        # Bind the executable to systemd's actual MainPID through ancestry;
        # requiring the service cgroup alone would miss the real application.
        parents = {}
        for process in Path('/proc').iterdir():
            if process.name.isdecimal():
                try:
                    parents[int(process.name)] = int(
                        (process / 'stat').read_text().rsplit(') ', 1)[1].split()[1]
                    )
                except FileNotFoundError:
                    pass

        def lineage(pid):
            chain = []
            while pid > 1 and pid not in chain:
                chain.append(pid)
                if pid == main_pid:
                    return chain
                pid = parents.get(pid, 0)
            return []

        launcher_groups = Path(f'/proc/{main_pid}/cgroup').read_text().splitlines()
        identities = []
        diagnostic = []
        for process in Path('/proc').iterdir():
            if not process.name.isdecimal() or not lineage(int(process.name)):
                continue
            try:
                executable = os.readlink(process / 'exe')
                diagnostic.append({'pid': int(process.name),
                                   'exe': executable,
                                   'cgroup': (process / 'cgroup').read_text()})
                if executable != '/app/bin/syncthing':
                    continue
                groups = [line.split(':', 2)[2] for line in (process / 'cgroup').read_text().splitlines()]
                launcher_paths = [line.split(':', 2)[2] for line in launcher_groups]
                assert all(g != '/' for g in groups)
                assert any(g == outer or g.startswith(outer + '/')
                           for g in groups for outer in launcher_paths)
                digest = hashlib.file_digest((process / 'exe').open('rb'), 'sha256').hexdigest()
                assert digest == packaged_binary_sha
                namespace = os.readlink(process / 'ns/mnt')
                assert namespace != os.readlink('/proc/self/ns/mnt')
                info = configparser.ConfigParser()
                info.read(process / 'root/.flatpak-info')
                assert info['Application']['name'] == app
                assert info['Instance']['app-commit'] == json.loads(
                    Path('/input/flatpak-inputs.json').read_text()
                )['bundles']['app']['commit']
                identities.append(int(process.name))
                report.setdefault('actualPackagedServiceProcesses', []).append({
                    'unit': unit, 'mainPid': main_pid, 'syncthingPid': int(process.name),
                    'controlGroup': group, 'executableSha256': digest,
                    'launcherCgroups': launcher_groups, 'applicationCgroups': groups,
                    'ancestryToMainPid': lineage(int(process.name)),
                    'mountNamespace': namespace,
                    'appCommit': info['Instance']['app-commit'],
                    'runtimeCommit': info['Instance']['runtime-commit'],
                })
            except FileNotFoundError as error:
                diagnostic.append({'pid': int(process.name), 'missing': str(error)})
                continue
        # v1.27.3 may retain a launcher/monitor as well as its server process.
        # Every matching process must satisfy the same executable/namespace,
        # signed commit and ancestry proof; all are checked after stop.
        assert identities, diagnostic
        return [main_pid, *identities]
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
            ('flatpak_name', app),
            ('autostart', 'no'),
        ]:
            setting(name, value)
        if signed_flatpak:
            initial = json.loads(legacy_rpc('get_settings_json'))
            assert initial['is_setup'] is False and initial['api_key'] == ''
            reply = http('POST', 'check/start')
            assert reply['status'] == 200 and json.loads(reply['body'])['success'] is True
            runtime_identity(service)
            # Running systemd state does not establish GUI/API readiness.
            # Probe eventual backend discovery without claiming a browser replay;
            # retain returned ports instead of crediting first-attempt discovery.
            port_scans = []
            scan_started = time.monotonic()

            def scan_port():
                reply = http('POST', 'check/scan_port')
                assert reply['status'] == 200, reply
                port = json.loads(reply['body'])['port']
                port_scans.append(port)
                assert port in (None, 8384), port_scans
                return port

            try:
                scanned_port = wait(scan_port, 'signed package setup port discovery')
            finally:
                report['setupPortScans'] = port_scans
                report['setupPortScanElapsedSeconds'] = round(time.monotonic() - scan_started, 3)
                print('FRAMEY_SETUP_PORT_SCAN_JSON=' + json.dumps({
                    'ports': port_scans, 'elapsedSeconds': report['setupPortScanElapsedSeconds'],
                }), flush=True)
            setting('port', scanned_port)
            reply = http('POST', 'check/scan_api_key')
            assert reply['status'] == 200
            scanned_key = json.loads(reply['body'])['api_key']
            assert scanned_key == key, 'Setup did not discover the signed package API key'
            setting('api_key', scanned_key)
            reply = http('POST', 'check/scan_basic_auth')
            assert reply['status'] == 200 and json.loads(reply['body'])['basic_auth_user'] is None
            saved = json.loads(legacy_rpc('get_settings_json'))
            assert saved['is_setup'] is False
            assert saved['port'] == scanned_port and saved['api_key'] == scanned_key
            authenticated = legacy_rpc(
                'framey_http_fetch', method='GET', path='/rest/system/status',
                headers={'X-API-Key': scanned_key},
            )
            assert authenticated['status'] == 200
            assert json.loads(authenticated['body'])['myID'] == own_id
            # The official wizard commits setup before normal service controls
            # become active, then explicitly reloads the watchdog's settings.
            setting('is_setup', True)
            assert http('POST', 'reload-config')['status'] == 204
            assert http('POST', 'stop')['status'] == 204
            assert prop(service, 'MainPID') == '0'
            report['wizardConfigDiscovery'] = dict(
                defaultPackageConfig=True, remainedUnconfiguredDuringScan=True,
                discoveredDefaultPort=True, discoveredDefaultApiKey=True,
                scannedBasicAuth=True, persistedThroughDeckyRpc=True,
                setupCommittedAndReloaded=True,
                authenticatedRestWithDiscoveredKey=True, ownedSetupServiceStopped=True,
            )
        else:
            setting('is_setup', True)
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

        def refused_control(label, pid):
            original_unit, original_receipt = unit.read_bytes(), receipt.read_bytes()
            refused = {}
            for method, route in [
                ('GET', 'state'),
                ('POST', 'start'),
                ('POST', 'stop'),
                ('POST', 'check/start'),
                ('POST', 'reload-config'),
            ]:
                reply = http(method, route)
                assert reply['status'] == 500, (label, route, reply)
                refused[method + ' ' + route] = reply['status']
                assert int(prop(service, 'MainPID')) == pid, (label, route)
                assert Path(f'/proc/{pid}/exe').resolve() == Path('/usr/bin/sleep')
                assert (
                    unit.read_bytes() == original_unit
                    and receipt.read_bytes() == original_receipt
                )
                assert legacy.read_bytes() == original_legacy
                assert int(prop(legacy.name, 'MainPID')) == legacy_pid
            # A transition may not stop the replaced managed process or disable
            # the explicitly selected private legacy service before refusal.
            setting('mode', 'systemd')
            setting('service_name', legacy.name)
            reply = http('POST', 'reload-config')
            assert reply['status'] == 500, (label, 'external transition', reply)
            refused['POST external transition'] = reply['status']
            assert int(prop(service, 'MainPID')) == pid
            assert int(prop(legacy.name, 'MainPID')) == legacy_pid
            assert ctl('is-enabled', legacy.name) == 'enabled'
            assert (
                unit.read_bytes() == original_unit
                and receipt.read_bytes() == original_receipt
            )
            setting('mode', 'flatpak')
            setting('service_name', '')
            report.setdefault('rejectedManagedDefinitions', {})[label] = {
                'mainPidBefore': pid,
                'mainPidAfter': int(prop(service, 'MainPID')),
                'fragmentPath': prop(service, 'FragmentPath'),
                'id': prop(service, 'Id'),
                'names': prop(service, 'Names'),
                'dropInPaths': prop(service, 'DropInPaths'),
                'refused': refused,
                'unitAndReceiptPreserved': True,
                'legacyPidPreserved': legacy_pid,
                'legacyStillEnabled': True,
            }

        foreign_bytes = b'[Service]\nExecStart=\nExecStart=/usr/bin/sleep infinity\n'
        dropin = directory / (service + '.d')
        dropin.mkdir()
        override = dropin / 'private-foreign.conf'
        override.write_bytes(foreign_bytes)
        ctl('daemon-reload')
        ctl('start', service)
        foreign_pid = int(prop(service, 'MainPID'))
        assert foreign_pid > 0 and str(override) in prop(service, 'DropInPaths')
        assert prop(service, 'FragmentPath') == str(unit)
        refused_control('drop-in', foreign_pid)
        assert override.read_bytes() == foreign_bytes
        report['dropInOverridePreserved'] = True
        ctl('stop', service)  # Only this fixture created the private sleep process.
        override.unlink()
        dropin.rmdir()
        ctl('daemon-reload')
        assert http('POST', 'reload-config')['status'] == 204

        control_directory = home / '.config/systemd/user.control'
        control_directory.mkdir(mode=0o700)
        shadow = control_directory / service
        shadow.write_bytes(b'[Service]\nExecStart=/usr/bin/sleep infinity\n')
        ctl('daemon-reload')
        assert prop(service, 'FragmentPath') == str(shadow)
        ctl('start', service)
        foreign_pid = int(prop(service, 'MainPID'))
        assert foreign_pid > 0
        refused_control('shadow fragment', foreign_pid)
        assert shadow.read_bytes() == b'[Service]\nExecStart=/usr/bin/sleep infinity\n'
        report['shadowFragmentPreserved'] = True
        ctl('stop', service)
        shadow.unlink()
        ctl('daemon-reload')
        assert http('POST', 'reload-config')['status'] == 204

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
            == version
        )
        first = int(prop(service, 'MainPID'))
        assert first > 0
        running_pids = runtime_identity(service)
        report['realSyncthingManagedPid'] = True
        report['realDeckyRpcRest'] = True
        if signed_flatpak:
            denied = legacy_rpc('framey_http_fetch', method='GET',
                                path='/rest/system/version', headers={})
            assert denied['status'] == 403, denied
            report['deckyApiKeyErrorStatus'] = denied['status']
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
        # A pending definition change must not be mistaken for the definition
        # currently running. Do not reload it or signal the live sync process.
        dropin.mkdir()
        override.write_bytes(foreign_bytes)
        assert prop(service, 'NeedDaemonReload') == 'yes'
        reply = http('POST', 'stop')
        assert reply['status'] == 500, reply
        assert int(prop(service, 'MainPID')) == first
        assert runtime_identity(service) == running_pids
        assert override.read_bytes() == foreign_bytes
        override.unlink()
        dropin.rmdir()
        ctl('daemon-reload')
        report['pendingReloadRefused'] = True
        began = time.monotonic()
        reply = http('POST', 'stop')
        elapsed = round(time.monotonic() - began, 3)
        assert reply['status'] == 204, reply
        assert elapsed < 25, elapsed  # Host panel RPC budget.
        assert (
            prop(service, 'ActiveState') == 'inactive'
            and prop(service, 'MainPID') == '0'
        )
        assert all(not Path(f'/proc/{pid}').exists() for pid in running_pids)
        if signed_flatpak:
            assert len(subprocess.check_output(
                ['/usr/bin/flatpak', 'ps', '--columns=application'], text=True, timeout=20,
            ).splitlines()) == 1  # Only the separate private peer remains.
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
            == version
        )
        restarted_pids = runtime_identity(service)
        assert restarted_pids[0] != first
        assert (
            returned.read_bytes() == reverse
            and (runtime / 'cert.pem').read_bytes() == cert
        )
        external = directory / 'framey-owned-external.service'
        external_command = launcher + [
            'serve', '--home=' + str(runtime), '--no-browser', '--no-restart', '--no-upgrade',
        ]
        external.write_text(
            '[Unit]\nDescription=Owned external Syncthing fixture\n[Service]\nExecStart='
            + ' '.join(external_command) + '\n[Install]\nWantedBy=default.target\n'
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
            == version
        )
        external_pid = int(prop(external.name, 'MainPID'))
        assert external_pid > 0
        if not signed_flatpak:
            assert external.name in Path(f'/proc/{external_pid}/cgroup').read_text()
        external_pids = runtime_identity(external.name)
        reply = http('POST', 'stop')
        assert reply['status'] == 204, reply
        assert (
            prop(external.name, 'MainPID') == '0'
            and all(not Path(f'/proc/{pid}').exists() for pid in external_pids)
        )
        assert (
            returned.read_bytes() == reverse
            and (runtime / 'cert.pem').read_bytes() == cert
        )
        report['actualExternalUserServiceControl'] = True
        report['retainedSyncAcrossServiceTransition'] = True
        # Recreate the owned unit, then prove a higher-priority alias cannot
        # redirect candidate operations to the already-running legacy fixture.
        setting('mode', 'flatpak')
        setting('service_name', '')
        assert http('POST', 'reload-config')['status'] == 204
        shadow.symlink_to(legacy)
        ctl('daemon-reload')
        assert prop(service, 'Id') == legacy.name
        assert int(prop(service, 'MainPID')) == legacy_pid
        refused_control('loaded alias', legacy_pid)
        assert shadow.is_symlink() and shadow.resolve() == legacy
        assert legacy.read_bytes() == original_legacy
        report['loadedAliasPreserved'] = True
    finally:
        ctl('stop', service, check=False)
        ctl('stop', 'framey-owned-external.service', check=False)
        ctl('stop', legacy.name, check=False)
        if peer.poll() is None:
            os.killpg(peer.pid, signal.SIGTERM)
        peer.wait(timeout=30)
        assert peer.returncode in ((0, -signal.SIGTERM) if signed_flatpak else (0,))
        report['peerExitStatus'] = peer.returncode
        if backend is not None:
            if backend.poll() is None:
                os.killpg(backend.pid, signal.SIGTERM)
            backend.wait(timeout=15)
        for log in logs:
            log.seek(0)
            print(log.read()[-3000:], flush=True)
            log.close()
    assert not Path(f'/proc/{helper_pid}').exists()
    if signed_flatpak:
        instances = subprocess.check_output(
            ['/usr/bin/flatpak', 'ps', '--columns=application'], text=True, timeout=20,
        )
        assert app not in instances
        report['noOwnedFlatpakInstancesRemain'] = True
        report['retainedCertificateSha256'] = hashlib.sha256(
            (runtime / 'cert.pem').read_bytes()
        ).hexdigest()
    report['ownedCleanup'] = True
    print('FRAMEY_USER_SERVICE_JSON=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--signed-flatpak'])
    main(signed_flatpak=sys.argv[1:] == ['--signed-flatpak'])
