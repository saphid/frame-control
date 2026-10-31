"""Container-only real Decky backend discovery and smoke tests; no host services."""
import argparse
import ast
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
import io

from runtime_console import capture_runtime

import websockets
from websockets.exceptions import WebSocketException

ROOT = Path('/repo')
sys.path[:0] = [str(ROOT/'ui'), str(ROOT/'tests')]
import frame_decky_store
from framey_official import PLUGINS, PREFIX_MANAGER_102, archive


async def request(route, args):
    token = urllib.request.urlopen('http://127.0.0.1:1337/auth/token', timeout=2).read().decode()
    async with websockets.connect('ws://127.0.0.1:1337/ws?auth='+token,
                                  open_timeout=3, close_timeout=2) as ws:
        await ws.send(json.dumps({'type': 0, 'id': 1, 'route': route, 'args': args}))
        while True:
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
            if response.get('id') != 1:
                continue
            await ws.send(json.dumps({'type': 3, 'id': 1}))
            assert response['type'] == 1, response
            return response['result']


def rpc(route, *args):
    return asyncio.run(request(route, list(args)))


def until_ready(read, description):
    deadline = time.monotonic()+20
    last = None
    while time.monotonic() < deadline:
        try:
            value = read()
            if value:
                return value
        except (OSError, ValueError, KeyError, TimeoutError, WebSocketException) as error:
            last = str(error)
        time.sleep(.1)
    raise RuntimeError(f'{description} not ready: {last}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('id', type=int)
    parser.add_argument('version', nargs='?', default='-')
    parser.add_argument('--reproduce-bound-method-regression', action='store_true')
    parser.add_argument('--reproduce-fileserver-empty-flag-regression', action='store_true')
    parser.add_argument('--reproduce-timer-regression', action='store_true')
    parser.add_argument('--reproduce-free-loader-unload-regression', action='store_true')
    parser.add_argument('--reproduce-terminal-import-regression', action='store_true')
    parser.add_argument('--reproduce-tabmaster-restore-regression', action='store_true')
    parser.add_argument('--reproduce-deck-progress-unload-regression', action='store_true')
    parser.add_argument('--reproduce-wine-cellar-unload-regression', action='store_true')
    parser.add_argument('--reproduce-shotty-unload-regression', action='store_true')
    parser.add_argument('--reproduce-battery-tracker-unload-regression', action='store_true')
    args = parser.parse_args()
    if args.reproduce_terminal_import_regression:
        assert args.id == 65 and args.version == '-'
    assert os.getuid() == 1100 and ROOT.is_dir(), 'Run through framey-test-decky-runtime.py'
    record = (PREFIX_MANAGER_102 if args.id == 130 and args.version == '1.0.2'
              else next(p for p in PLUGINS if p['id'] == args.id))
    case = (dict(id=65, shim=None, probe='terminal-import-regression')
            if args.reproduce_terminal_import_regression else
            next(p for p in json.loads((ROOT/'tests/decky-runtime/cases.json').read_text())
                 if p['id'] == args.id and p.get('version', '-') == args.version))
    data = archive(record)
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    assert frame_decky_store.archive_info(data, record['sha256'], record['name']) == record['folder']
    home = Path.home()
    base = home/'.local/share/frame-control/decky'
    (base/'plugins').mkdir(parents=True)
    unit = home/'.config/systemd/user/frame-control-decky.service'
    unit.parent.mkdir(parents=True)
    unit.write_text('# Private fixture marker; no real service manager is contacted.\n')
    tools = home/'bin'
    tools.mkdir()
    systemctl = tools/'systemctl'
    systemctl.write_text('#!/bin/sh\ncase "$*" in *is-active*) exit 3;; *) exit 0;; esac\n')
    systemctl.chmod(0o700)
    env = dict(os.environ, PATH=str(tools)+':'+os.environ['PATH'])
    Path('/tmp/frame-control-decky-plugin-runtime-test').write_bytes(data)
    install = subprocess.run([sys.executable, '-', 'install', 'runtime-test', str(record['id']),
        record['sha256'], record['folder'], record['version'], '-'], input=frame_decky_store.apply_script(record['id'], record['sha256']),
        capture_output=True, text=True, env=env, timeout=30)
    assert install.returncode == 0, install.stderr
    plugin = base/'plugins'/record['folder']
    if args.reproduce_battery_tracker_unload_regression:
        assert record['id'] == 67
        prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                  b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
        managed = (plugin/'main.py').read_bytes()
        assert managed.startswith(prefix)
        previous = managed[len(prefix):]
        assert hashlib.sha256(previous).hexdigest() == '490d8334b173f956f286e50c9d01af5b83416e8e0037685366efb75c6c323241'
        (plugin/'main.py').write_bytes(previous)
        (plugin/'py_modules/framey_decky_ipc.py').unlink()
    receipt = json.loads((plugin/'.frame-control-store.json').read_text())
    if not (args.reproduce_timer_regression or args.reproduce_tabmaster_restore_regression):
        expected_shims = ([case['shim']] if case['shim'] else []) + case.get('additionalShims', [])
        assert receipt.get('compatShims', []) == expected_shims, receipt
    else:
        assert record['id'] == (61 if args.reproduce_tabmaster_restore_regression else 96)
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            (plugin/'main.py').write_bytes(original.read(record['folder']+'/main.py'))
    if args.reproduce_deck_progress_unload_regression:
        assert record['id'] == 134
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            (plugin/'main.py').write_bytes(original.read(record['folder']+'/main.py'))
        (plugin/'py_modules/framey_decky_ipc.py').unlink()
    if args.reproduce_wine_cellar_unload_regression:
        assert record['id'] == 68
        import gzip
        previous = gzip.decompress((ROOT/'tests/fixtures/framey-wine-cellar-pre-ipc.py.gz').read_bytes())
        assert hashlib.sha256(previous).hexdigest() == '44841fea9318bb975aebaf1024ad14c912e5d5fe8b6fef561671e6a0e9559411'
        (plugin/'main.py').write_bytes(previous)
    if record['id'] == 68:
        expected = (previous if args.reproduce_wine_cellar_unload_regression else
                    (ROOT/'ui/vendor/wine-cellar-0.2.1/main.py').read_bytes())
        assert (plugin/'main.py').read_bytes() == expected, 'installed Wine Cellar source must match the tested lifecycle'
        assert (plugin/'py_modules/framey_decky_ipc.py').read_bytes() == (ROOT/'ui/framey_decky_ipc.py').read_bytes()
    if args.reproduce_shotty_unload_regression:
        assert record['id'] == 53
        prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                  b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
        managed = (plugin/'main.py').read_bytes()
        assert managed.startswith(prefix)
        previous = managed[len(prefix):]
        assert hashlib.sha256(previous).hexdigest() == '5c62941c81887727b6f1ea2dbc0ba0c8c9e6153503ae3e3c234a4c4271d336de'
        (plugin/'main.py').write_bytes(previous)
        (plugin/'py_modules/framey_decky_ipc.py').unlink()
    if args.reproduce_free_loader_unload_regression:
        assert record['id'] == 63
        prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                  b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
        managed = (plugin/'main.py').read_bytes()
        assert managed.startswith(prefix)
        original = managed[len(prefix):]
        assert hashlib.sha256(original).hexdigest() == '2514b5a59fe0571734eecbfc893b3ef9f01ee19b9c1b24e54028051e546ab364'
        (plugin/'main.py').write_bytes(original)
        (plugin/'py_modules/framey_decky_ipc.py').unlink()
    # Exercise the production manifest's API convention, never import Plugin ourselves.
    manifest = json.loads((plugin/'plugin.json').read_text())
    assert manifest.get('api_version', 'legacy') == record['api_version'], manifest
    assert '_root' not in manifest.get('flags', []), manifest
    if args.reproduce_fileserver_empty_flag_regression:
        assert record['id'] == 60
        source = plugin/'main.py'
        source.write_text(source.read_text().replace('[arg for arg in [', '[').replace('] if arg],', '],'))
    if args.reproduce_bound_method_regression:
        assert record['id'] == 111
        source = (plugin/'main.py').read_text()
        for old, new in [('self._get_dbus_env(self)', 'self._get_dbus_env()'),
                         ('self._sp_player_dbus(self,', 'self._sp_player_dbus(')]:
            assert old in source
            source = source.replace(old, new)
        (plugin/'main.py').write_text(source)

    (home/'.local/share/Steam/steamui/images').mkdir(parents=True)
    if case['probe'] == 'wine-cellar-private-state':
        steam = home/'.local/share/Steam'
        (steam/'config').mkdir(parents=True)
        (steam/'steamapps').mkdir(exist_ok=True)
        (steam/'compatibilitytools.d').mkdir(exist_ok=True)
        (steam/'config/config.vdf').write_text(
            '"InstallConfigStore" { "Software" { "Valve" { "Steam" { "CompatToolMapping" { } } } } }')
        (steam/'steamapps/libraryfolders.vdf').write_text(
            '"libraryfolders" { "0" { "path" "PRIVATE" } }')
    loader = base/'PluginLoader'
    shutil.copy('/input/PluginLoader', loader)
    loader.chmod(0o700)
    env.update(UNPRIVILEGED_PATH=str(base), PRIVILEGED_PATH=str(base), CHOWN_PLUGIN_PATH='0',
               LIVE_RELOAD='0', USE_CEF_CLOSE_WORKAROUND='0', KEEP_SYSTEMD_SERVICE='1',
               DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/bus')
    if case['probe'] == 'desktop-apps-private-entries':
        # The real backend scans only disposable container paths. Exec is a
        # canary: discovery/settings must never launch a desktop application.
        primary, secondary = home/'desktop-primary', home/'desktop-secondary'
        for directory in (primary, secondary):
            (directory/'applications').mkdir(parents=True)
        canary = home/'desktop-exec-canary'
        executable = home/'fixture-desktop-app'
        executable.write_text('#!/bin/sh\nprintf launched > '+str(canary)+'\n')
        executable.chmod(0o700)
        def entry(directory, name, body):
            path = directory/'applications'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[Desktop Entry]\n'+body)
            return path
        desktop = entry(primary, 'framey-private.desktop',
            'Type=Application\nName=Private Desktop App\nExec='+str(executable)+' --name %c --file %k %U\n')
        entry(secondary, 'framey-private.desktop',
              'Type=Application\nName=Wrong duplicate\nExec=/bin/false\n')
        entry(primary, 'nested/framey-flatpak.desktop',
              'Type=Application\nName=Private Flatpak\nExec=/usr/bin/flatpak run org.framey.Private %f\n'
              'X-Flatpak=org.framey.Private\nPath='+str(home)+'/private-workdir\n')
        for name, body in {
                'hidden': 'Type=Application\nHidden=true\nName=Hidden\nExec=/bin/false\n',
                'nodisplay': 'Type=Application\nNoDisplay=true\nName=NoDisplay\nExec=/bin/false\n',
                'terminal': 'Type=Application\nTerminal=true\nName=Terminal\nExec=/bin/false\n',
                'link': 'Type=Link\nName=Link\nExec=/bin/false\n',
                'noname': 'Type=Application\nExec=/bin/false\n',
                'noexec': 'Type=Application\nName=NoExec\n',
                'malformed': 'Type=Application\nName=Malformed\nExec="unterminated\n',
        }.items():
            entry(primary, 'framey-private-'+name+'.desktop', body)
        env['XDG_DATA_DIRS'] = str(primary)+':'+str(secondary)
    if case['probe'] == 'battery-tracker':
        supply = home/'battery-supply'/'max1720x_bat_7-36'
        supply.mkdir(parents=True)
        for name, value in {'type':'Battery', 'capacity':'89', 'status':'Charging',
                            'voltage_now':'8746718', 'current_now':'1030625'}.items():
            (supply/name).write_text(value+'\n')
        env['FRAMEY_BATTERY_ROOT'] = str(supply.parent)
    processes = []
    report = {'id': record['id'], 'name': record['name'], 'version': record['version'],
              'sha256': record['sha256'], 'shim': case['shim'], 'calls': []}
    with (home/'runtime.log').open('w+') as log:
        with capture_runtime(log, report, processes, loader=loader):
            if case['probe'] == 'bluetooth-private-bluez':
                import bluetooth_bluez
                private_bluez = bluetooth_bluez.start(ROOT, env, log, processes, until_ready)
            if case['probe'] == 'mpris':
                bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork',
                    '--address='+env['DBUS_SESSION_BUS_ADDRESS']], env=env, stdout=log, stderr=log,
                    start_new_session=True)
                processes.append(bus)
                until_ready(lambda: Path('/run/user/1100/bus').is_socket(), 'private session bus')
                player = subprocess.Popen([sys.executable, str(ROOT/'tests/fixtures/framey-mpris/player.py')],
                    env=env, stdout=log, stderr=log, start_new_session=True)
                processes.append(player)
                until_ready(lambda: Path('/tmp/mpris-state.json').is_file(), 'silent MPRIS player')
            backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
            processes.append(backend)
            discovered = until_ready(lambda: rpc('loader/get_plugins'), 'published Decky plugin discovery')
            assert len(discovered) == 1 and discovered[0]['name'] == record['name'], discovered
            assert discovered[0]['version'] == record['version'] and not discovered[0]['disabled'], discovered
            report['discovered'] = discovered

            def legacy(method, **kwargs):
                response = rpc('loader/call_legacy_plugin_method', record['name'], method, kwargs)
                assert response['success'] is True, (method, response)
                recorded = response['result']
                if record['id'] == 117 and method == 'get_status':
                    recorded = dict(recorded, password='[private fixture credential omitted]')
                report['calls'].append({'method': method, 'result': recorded})
                return response['result']

            def current(method, *values):
                response = rpc('loader/call_plugin_method', record['name'], method, *values)
                report['calls'].append({'method': method, 'result': response})
                return response

            if case['probe'] == 'ludusavi-dependency-discovery':
                import ludusavi_private
                report['dependencyDiscovery'] = ludusavi_private.exercise(
                    current, plugin, data, record, backend, loader, env, log,
                    processes, until_ready, rpc)
                report['result'] = ('published Decky missing dependency report, bounded slow discovery, '
                    'private executable fallback, restart and original negative regression passed; '
                    'real Ludusavi backup/restore/cloud, browser and VR unverified')
            elif case['probe'] == 'deck-progress-private-tags':
                import base64
                # Only private SQLite settings/manual tags are exercised. Do
                # not call Steam sync, HLTB search or automatic tagging RPCs.
                initial = until_ready(lambda: current('get_settings').get('settings'),
                                      'private Deck Progress database')
                assert initial == dict(auto_tag_enabled=True, in_progress_threshold=30,
                    cache_ttl=7200, source_installed=True, source_non_steam=True, source_all_owned=True)
                assert current('get_game_tag', '424242') == dict(success=True, tag=None)
                settings = dict(auto_tag_enabled=False, in_progress_threshold=75,
                    cache_ttl=1800, source_installed=False, framey_private_label='Private tags')
                assert current('update_settings', settings) == dict(success=True)
                updated = current('get_settings')
                assert updated['success'] is True
                for key, value in settings.items():
                    assert updated['settings'][key] == value
                assert current('set_manual_tag', {'appid':'424242', 'tag':'completed'}) == dict(success=True)
                assert current('set_manual_tag', '434343', 'mastered') == dict(success=True)
                def tag(appid, expected):
                    result = current('get_game_tag', appid)
                    assert result['success'] is True
                    assert result['tag']['appid'] == appid and result['tag']['tag'] == expected
                    assert result['tag']['is_manual'] is True
                    return result['tag']
                first, other = tag('424242', 'completed'), tag('434343', 'mastered')
                for params, error in [({'appid':'424242', 'tag':'invalid'}, 'Invalid tag'),
                                      ({'appid':'', 'tag':'dropped'}, 'Missing appid'),
                                      ({'appid':'424242'}, 'Missing tag')]:
                    result = current('set_manual_tag', params)
                    assert result['success'] is False and error in result['error']
                assert tag('424242', 'completed') == first
                databases = list(base.rglob('game_tracker.db'))
                assert len(databases) == 1
                database = databases[0]
                assert database.is_relative_to(home) and not database.is_symlink()
                def rows():
                    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as db:
                        return dict(tags=db.execute(
                            'SELECT appid,tag,is_manual FROM game_tags ORDER BY appid').fetchall(),
                            settings=db.execute('SELECT key,value FROM settings ORDER BY key').fetchall())
                before = rows()
                assert before['tags'] == [('424242','completed',1),('434343','mastered',1)]
                raw_settings = dict(before['settings'])
                assert raw_settings['auto_tag_enabled'] == 'false'
                assert raw_settings['in_progress_threshold'] == '75'
                assert raw_settings['framey_private_label'] == 'Private tags'
                stops = []
                def stop_progress_loader():
                    def identity(pid):
                        try:
                            fields = Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
                            return int(fields[1]), int(fields[19])
                        except (FileNotFoundError, ProcessLookupError):
                            return None
                    snapshot = {int(p.name):identity(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()}
                    owned = {backend.pid}
                    while True:
                        children = {pid for pid,value in snapshot.items() if value and value[0] in owned}
                        if children <= owned:
                            break
                        owned |= children
                    identities = {pid:snapshot[pid] for pid in owned}
                    assert len(identities) >= 2 and all(identities.values())
                    started = time.monotonic()
                    backend.send_signal(signal.SIGTERM)
                    assert backend.wait(timeout=8) == 0
                    assert all(identity(pid) != value for pid,value in identities.items())
                    stops.append(dict(returncode=backend.returncode,elapsedSeconds=time.monotonic()-started,
                        signaledOnlyOwnedLoader=True,ownedProcessIdentitiesReaped=True,
                        ownedProcessCount=len(identities)))
                stop_progress_loader()
                assert rows() == before
                stopped_database_sha = hashlib.sha256(database.read_bytes()).hexdigest()
                stopped_database = base64.b64encode(database.read_bytes()).decode()
                backend = subprocess.Popen([str(loader)],env=env,stdout=log,stderr=log,start_new_session=True)
                processes.append(backend)
                restarted = until_ready(lambda:rpc('loader/get_plugins'),'restarted Deck Progress discovery')
                assert len(restarted) == 1 and restarted[0]['name'] == record['name']
                restored = until_ready(lambda:current('get_settings').get('settings'),'restarted private database')
                assert restored == updated['settings']
                assert tag('424242','completed') == first and tag('434343','mastered') == other
                assert current('remove_tag', {'appid':'424242'}) == dict(success=True)
                assert current('get_game_tag','424242') == dict(success=True,tag=None)
                assert tag('434343','mastered') == other
                final = rows()
                assert final['tags'] == [('434343','mastered',1)] and final['settings'] == before['settings']
                stop_progress_loader()
                assert rows() == final
                unchanged = {}
                with zipfile.ZipFile(io.BytesIO(data)) as original:
                    for item in original.infolist():
                        if not item.is_dir():
                            name = item.filename.split('/',1)[1]
                            raw = (plugin/name).read_bytes()
                            if name == 'main.py' and not args.reproduce_deck_progress_unload_regression:
                                assert raw.endswith(original.read(item))
                                assert raw[:-len(original.read(item))] == b'# Frame Control: repair child IPC EOF for the exact Deck Progress 1.3.6 archive.\nfrom framey_decky_ipc import install as _framey_install_ipc_eof\n_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n'
                            else:
                                assert raw == original.read(item)
                                unchanged[name] = hashlib.sha256(raw).hexdigest()
                if not args.reproduce_deck_progress_unload_regression:
                    assert (plugin/'py_modules/framey_decky_ipc.py').read_bytes() == (ROOT/'ui/framey_decky_ipc.py').read_bytes()
                log.flush()
                console = (home/'runtime.log').read_text()
                assert console.count('Starting Decky version v3.3.0') == console.count('[main][INFO]: Shutdown finished.') == 2
                for marker in ('Import failed:', 'Error during shutdown:', 'asyncio.exceptions.CancelledError',
                               'Task was destroyed but it is pending', 'Bad file descriptor'):
                    assert marker not in console, marker
                forced_kills = console.count('Sending SIGKILL!')
                if args.reproduce_deck_progress_unload_regression:
                    assert forced_kills == 2
                    assert console.count('still alive 5 seconds after stop request') == 2
                    report['expectedRegression'] = dict(success=False,phase='plugin unload',
                        originalPluginUnmodified=True,forcedPluginKills=forced_kills,
                        qualifiedCompatibilityPass=False)
                else:
                    assert forced_kills == 0
                    assert 'still alive 5 seconds after stop request' not in console
                report['privateTags'] = dict(scopedChildIpcEofRepair=not args.reproduce_deck_progress_unload_regression,
                    originalBackendRetainedAsExactSuffix=not args.reproduce_deck_progress_unload_regression,
                    publishedBackendUnmodified=args.reproduce_deck_progress_unload_regression,
                    ipcAdapterSha256=(None if args.reproduce_deck_progress_unload_regression else
                        hashlib.sha256((plugin/'py_modules/framey_decky_ipc.py').read_bytes()).hexdigest()),
                    forcedPluginKills=forced_kills,settingsBeforeRestart=before,settingsAfterSelectedDelete=final,
                    settingsAndManualTagsPersistedAcrossRestart=True,invalidTagAndMissingArgumentsRefused=True,
                    selectedDeletePreservedOtherTag=True,independentReadonlySqliteReadback=True,
                    databaseRelativePath=str(database.relative_to(home)),stoppedDatabaseSha256=stopped_database_sha,
                    stoppedDatabaseBase64=stopped_database,
                    finalDatabaseSha256=hashlib.sha256(database.read_bytes()).hexdigest(),
                    finalDatabaseBase64=base64.b64encode(database.read_bytes()).decode(),
                    unchangedPublishedFiles=unchanged,ownedLoaderStops=stops,loaderConsole=console,
                    loaderConsoleSha256=hashlib.sha256(console.encode()).hexdigest(),
                    jsonDecodeDiagnosticCount=console.count('Expecting value: line 1 column 1 (char 0)'),
                    loaderConsoleErrorFree=False,steamLibraryVerified=False,automaticTaggingVerified=False,
                    hltbSearchVerified=False,browserVerified=False,realFrameContacted=False,physicalControllerVerified=False)
                report['result'] = ('managed child-IPC EOF repair with published Decky API1 private settings/manual tags, invalid-input refusals, '
                    'SQLite readback and restart persistence passed; Steam, automatic tags, HLTB, browser and Frame unverified')
                if args.reproduce_deck_progress_unload_regression:
                    report['result'] = 'original unmodified Deck Progress two forced unload kills reproduced; lifecycle failed, not a qualified compatibility pass'
            elif case['probe'] == 'bluetooth-private-bluez':
                report['privateBluez'] = bluetooth_bluez.exercise(
                    current, plugin, io.BytesIO(data), record, backend, private_bluez, log)
                report['result'] = ('published Decky API1 discovery and unmodified backend, private BlueZ '
                    'paired-device filtering, adapter selection, alias/battery replies, connection/power '
                    'round trips and clean shutdown passed; actual radio, pairing, browser and VR unverified')
            elif case['probe'] == 'terminal-import-regression':
                # Discovery also lists a backend whose import failed. Require
                # the precise original failure without attempting backend calls.
                failure = "ModuleNotFoundError: No module named 'termios'"
                until_ready(lambda: failure in (home/'runtime.log').read_text(),
                            'original Terminal termios import regression')
                source_hashes = {}
                with zipfile.ZipFile(io.BytesIO(data)) as original:
                    for name in ('main.py', 'py_modules/decky_terminal/terminal.py'):
                        actual = (plugin/name).read_bytes()
                        assert actual == original.read(record['folder']+'/'+name)
                        source_hashes[name] = hashlib.sha256(actual).hexdigest()
                assert not report['calls']
                report['expectedRegression'] = dict(success=False, phase='backend import',
                    exception=failure, originalPluginUnmodified=True,
                    backendSourceSha256=source_hashes, backendRpcNotAttempted=True,
                    rpcMethodsSucceeded=0, ptyCommandsExecuted=0,
                    realFrameContacted=False, physicalControllerVerified=False)
                report['result'] = ('original published Terminal import regression reproduced; '
                                    'discovery is not backend usability; no PTY or input executed')
            elif case['probe'] == 'steamgriddb-private-artwork':
                # Exact original backend; every path is in the disposable
                # container home. No host Steam, game or artwork is exposed.
                import base64
                artwork = base64.b64decode(
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jC1sAAAAASUVORK5CYII=')
                source = home/'private-artwork.png'
                source.write_bytes(artwork)
                assert current('get_local_start') == str(home)
                assert base64.b64decode(current('read_file_as_base64', str(source)), validate=True) == artwork
                state = base/'settings'/record['folder']/'steamgriddb.json'
                assert current('get_setting', 'framey-private', False) is False
                assert state.read_bytes() == b''
                saved = {'enabled': False, 'label': 'Private artwork fixture', 'ids': [777, 888]}
                assert current('set_setting', 'framey-private', saved) is None
                before = state.read_bytes()
                assert json.loads(before) == {'framey-private': saved}
                assert current('get_setting', 'framey-private', None) == saved

                steam = home/'.local/share/Steam'
                config = steam/'userdata/424242/config'
                (config/'grid').mkdir(parents=True)
                shortcuts = config/'shortcuts.vdf'
                appid = 0xf1234567  # Published backend normalizes signed shortcut IDs.

                def shortcuts_bytes(icon):
                    return (b'\x00shortcuts\x00\x000\x00\x02appid\x00' + appid.to_bytes(4, 'little') +
                            b'\x01icon\x00' + icon.encode() + b'\x00\x08\x001\x00\x02appid\x00' +
                            (0xf7654321).to_bytes(4, 'little') + b'\x01icon\x00unselected-canary\x00\x08\x08\x08')

                shortcuts.write_bytes(shortcuts_bytes('original-private-icon'))
                icon = config/'grid'/f'{appid}_icon.png'
                assert current('set_shortcut_icon_from_path', appid, '424242', str(source)) is True
                assert icon.read_bytes() == artwork
                assert shortcuts.read_bytes() == shortcuts_bytes(str(icon))
                unchanged = shortcuts.read_bytes()
                assert current('set_shortcut_icon', appid, '424242', str(icon)) == 'icon_is_same_path'
                assert shortcuts.read_bytes() == unchanged
                assert current('set_shortcut_icon', appid, '424242', None) is True
                assert shortcuts.read_bytes() == shortcuts_bytes('')
                cache = steam/'appcache/librarycache/777/private-icon.jpg'
                assert current('set_steam_icon_from_path', 777, str(source), 'private-icon') == str(cache)
                assert cache.read_bytes() == artwork
                assert not cache.with_name('private-icon.jpg_temp').exists()

                requests = []

                class ArtworkHandler(BaseHTTPRequestHandler):
                    def do_GET(self):
                        requests.append(self.path)
                        if self.path != '/private.png':
                            self.send_error(404)
                            return
                        self.send_response(200)
                        self.send_header('Content-Type', 'image/png')
                        self.send_header('Content-Length', str(len(artwork)))
                        self.end_headers()
                        self.wfile.write(artwork)

                    def log_message(self, *_):
                        pass

                server = ThreadingHTTPServer(('127.0.0.1', 0), ArtworkHandler)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    url = f'http://127.0.0.1:{server.server_port}/private.png'
                    assert base64.b64decode(current('download_as_base64', url), validate=True) == artwork
                    assert current('set_shortcut_icon_from_url', appid, '424242', url) is True
                    assert icon.read_bytes() == artwork
                    assert shortcuts.read_bytes() == shortcuts_bytes(str(icon))
                    remote_cache = steam/'appcache/librarycache/888/private-download.jpg'
                    assert current('set_steam_icon_from_url', 888, url, 'private-download') == str(remote_cache)
                    assert remote_cache.read_bytes() == artwork
                    assert not remote_cache.with_name('private-download.jpg_temp').exists()
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=3)
                assert requests == ['/private.png']*3
                assert not worker.is_alive()
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                restarted = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert len(restarted) == 1 and restarted[0]['name'] == record['name']
                assert restarted[0]['version'] == record['version'] and not restarted[0]['disabled']
                assert current('get_setting', 'framey-private', None) == saved
                assert state.read_bytes() == before
                assert current('get_local_start') == str(home)
                assert shortcuts.read_bytes() == shortcuts_bytes(str(icon))
                report['privateArtwork'] = dict(settingsPersistedAcrossLoaderRestart=True,
                    settingsSha256=hashlib.sha256(before).hexdigest(),
                    artworkSha256=hashlib.sha256(artwork).hexdigest(),
                    localFileRoundTrip=True, signedShortcutIdNormalized=True,
                    shortcutSetSamePathClear=True, unselectedShortcutPreserved=True,
                    cacheTempFilesReplaced=True, loopbackDownloads=len(requests),
                    ownedHttpServerStopped=True, noProductionChanges=True,
                    externalArtworkServiceVerified=False, steamContextMenuVerified=False,
                    browserVerified=False, realSteamCef=False,
                    realFrameContacted=False, physicalControllerVerified=False)
                report['result'] = ('published Decky API1 discovery, private settings/restart, '
                    'local/base64 and loopback artwork, shortcut icon set/same/clear and signed-ID '
                    'normalization passed; Steam context menu, external service, browser and VR unverified')
            elif case['probe'] == 'deckyparty-private-files':
                assert legacy('is_enabled') is False
                marker = b'Framey private Copyparty download fixture\n'
                (home/'fixture-download.bin').write_bytes(marker)
                assert legacy('get_status')['user'] == 'tester'
                assert legacy('get_status')['home'] == str(home)

                def server_pids():
                    owned = []
                    for entry in Path('/proc').glob('[0-9]*'):
                        try:
                            if (entry.stat().st_uid == os.getuid() and
                                    str(plugin/'bin/copyparty-sfx.py').encode() in
                                    (entry/'cmdline').read_bytes().split(b'\0')):
                                owned.append(int(entry.name))
                        except (OSError, ProcessLookupError): pass
                    return owned

                def closed():
                    with socket.socket() as probe:
                        probe.settimeout(.2)
                        return probe.connect_ex(('127.0.0.1',3923)) != 0

                assert server_pids() == [] and closed()
                legacy('set_enabled', enabled=True)
                state = legacy('get_status')
                credential = state['password']
                assert state['enabled'] is True and isinstance(credential,str) and credential

                def http(path, password=None, data=None, method=None):
                    headers = {'Cookie':'cppwd='+password} if password else {}
                    if data is not None:
                        headers['Content-Type'] = 'application/octet-stream'
                    request = urllib.request.Request('http://127.0.0.1:3923/'+path,
                        headers=headers, data=data, method=method or ('PUT' if data is not None else 'GET'))
                    return urllib.request.urlopen(request, timeout=2).read()

                assert until_ready(lambda: http('fixture-download.bin',credential), 'private Copyparty download') == marker
                pids = server_pids()
                assert pids
                assert marker in http('?ls',credential) or b'fixture-download.bin' in http('?ls',credential)
                for password in (None,'incorrect-private-password'):
                    try: assert http('fixture-download.bin',password) != marker
                    except urllib.error.HTTPError as error: assert error.code in (401,403,404)
                uploaded = b'Framey private uploaded bytes\n'
                try:
                    http('fixture-upload.bin',credential,data=uploaded)
                except urllib.error.HTTPError as error:
                    detail = error.read().decode(errors='replace').replace(credential,'[redacted]')
                    output = '\n'.join(p.read_text(errors='replace')[-5000:] for name in
                        ('std-out.log','std-err.log') for p in home.rglob(name))
                    output = output.replace(credential,'[redacted]')
                    raise AssertionError('Private upload failed: '+detail[:2000]+'\n'+output) from None
                assert (home/'fixture-upload.bin').read_bytes() == uploaded
                legacy('set_enabled', enabled=False)
                assert closed() and server_pids() == []
                # A second start proves that disable reaped the previous child.
                legacy('set_enabled', enabled=True)
                credential = legacy('get_status')['password']
                assert until_ready(lambda: http('fixture-upload.bin',credential), 'restarted Copyparty') == uploaded
                http('fixture-upload.bin',credential,method='DELETE')
                assert not (home/'fixture-upload.bin').exists()
                assert (home/'fixture-download.bin').read_bytes() == marker
                unrelated = subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=True)
                processes.append(unrelated)
                for reload_index in range(3):
                    rpc('loader/reload_plugin',record['name'])
                    # The reload RPC queues work. Do not race a legacy RPC against
                    # the wrapper whose response listener Decky is shutting down.
                    def reload_finished():
                        output = (home/'runtime.log').read_text()
                        return (output.count('Loaded DeckyParty File Manager') == reload_index+2 and
                                output.count('Unloaded DeckyParty File Manager') == reload_index+1)
                    until_ready(reload_finished, 'actual plugin reload completion')
                    until_ready(lambda: closed() and not server_pids(), 'owned server cleanup')
                    assert legacy('is_enabled') is False
                    if reload_index < 2:
                        legacy('set_enabled', enabled=True)
                        credential = legacy('get_status')['password']
                        assert until_ready(lambda: http('fixture-download.bin',credential),
                                           'Copyparty between reloads') == marker
                assert unrelated.poll() is None
                unrelated.terminate()
                unrelated.wait(timeout=3)
                log.flush()
                log.seek(0)
                lifecycle_log = log.read()
                assert 'Unloaded DeckyParty File Manager' in lifecycle_log
                assert 'Sending SIGKILL' not in lifecycle_log
                report['independentState'] = {'privateDownload':True, 'privateUpload':True,
                    'privateDelete':True,
                    'anonymousAndWrongPasswordRefused':True, 'disabledChildReaped':True,
                    'reloadStoppedServer':True, 'reloadCount':3, 'unrelatedChildUntouched':True}
                report['result'] = ('discovery, original Copyparty authenticated private listing/download/upload/delete, '
                    'disable/restart and actual plugin reload cleanup passed; LAN/Frame/UI unverified')
            elif case['probe'] == 'download-all-logging':
                assert current('log_from_ui', 'info', 'Private Framey download fixture') == {'success':True}
                assert 'FrameyQueueDownloads' in (plugin/'dist/index.js').read_text()
                report['result'] = ('published Decky discovery and logging RPC passed; '
                                    'Steam queue behavior is covered by isolated CEF/frontend fixtures, not this backend')
            elif case['probe'] == 'prefix-manager':
                # Only tmpfs fixtures exist here: never a host Steam prefix.
                assert manifest.get('flags') == [] and 'api_version' not in manifest
                assert legacy('get_games') == []
                steam = home/'.local/share/Steam'
                secondary = home/'Private Library'
                marker = b'Private prefix save fixture\n'

                def prefix(library, appid, installed=False):
                    apps = library/'steamapps'
                    path = apps/'compatdata'/str(appid)
                    path.mkdir(parents=True)
                    (path/'save.dat').write_bytes(marker)
                    (path/'empty').mkdir()
                    if installed:
                        (apps/f'appmanifest_{appid}.acf').write_text(
                            f'"AppState" {{ "appid" "{appid}" "name" "Private Game" "installdir" "Private" }}')
                    return path

                installed = prefix(secondary, 4242, True)
                unidentified = prefix(steam, 4343)
                (steam/'steamapps/libraryfolders.vdf').write_text(
                    f'"libraryfolders" {{ "0" {{ "path" "{steam}" }} "1" {{ "path" "{secondary}" }} }}')
                rows = legacy('get_games')
                assert {(g['appid'], g['type']) for g in rows} == {('4242', 'Steam'), ('4343', 'Unidentified')}, rows
                if record['version'] == '1.0.2':
                    # The upstream release added install-folder removal. No
                    # private or real game data may be touched by that action.
                    rejected = legacy('delete_prefix', appid='4242', do_backup=True,
                                      delete_game_folder=True)
                    assert rejected == [False, 'Game data deletion is unavailable on Frame; no files changed'], rejected
                    assert (installed/'save.dat').read_bytes() == marker
                    assert not (home/'Documents/PrefixBackups').exists()
                # The pinned shortcut parser reads only the first Steam user
                # and silently accepts parse failures. Never infer that an
                # unmatched prefix is unused, even with no shortcut files.
                refusal = [0, 'Orphan cleanup is disabled on Frame: non-Steam shortcut coverage is incomplete; unidentified prefixes may still be in use']

                def cleanup_refused():
                    for backup in (False, True):
                        assert legacy('cleanup_orphans', do_backup=backup) == refusal
                        assert (unidentified/'save.dat').read_bytes() == marker
                    assert not (home/'Documents/PrefixBackups').exists()

                cleanup_refused()
                shortcuts = [steam/f'userdata/{user}/config/shortcuts.vdf' for user in (100, 200)]
                for path in shortcuts:
                    path.parent.mkdir(parents=True)
                empty_shortcuts = b'\x00shortcuts\x00\x08\x08'
                valid_shortcuts = (b'\x00shortcuts\x00\x000\x00\x02appid\x00' + (4343).to_bytes(4, 'little')
                    + b'\x01AppName\x00Private shortcut\x00\x08\x08\x08')
                shortcuts[0].write_bytes(empty_shortcuts)
                shortcuts[1].write_bytes(valid_shortcuts)
                rows = legacy('get_games')
                assert all(g['type'] != 'Orphan' for g in rows), rows
                assert next(g for g in rows if g['appid'] == '4343')['type'] == 'Unidentified'
                cleanup_refused()
                # Corrupt either user, and change metadata after discovery.
                for index in (0, 1):
                    shortcuts[0].write_bytes(empty_shortcuts)
                    shortcuts[1].write_bytes(valid_shortcuts)
                    legacy('get_games')
                    shortcuts[index].write_bytes(b'\x00shortcuts\x00\x000\x00\x02appid\x00\x01')
                    cleanup_refused()
                    assert all(g['type'] != 'Orphan' for g in legacy('get_games'))
                    cleanup_refused()
                shortcuts[1].write_bytes(valid_shortcuts)
                shortcuts[1].chmod(0)
                try:
                    assert all(g['type'] != 'Orphan' for g in legacy('get_games'))
                    cleanup_refused()
                finally:
                    shortcuts[1].chmod(0o600)
                # The published panel sends only the clicked row's app ID.
                # With duplicate IDs it cannot identify a library: fail closed
                # for either backup choice, even when selecting the second row.
                duplicate_first = prefix(steam, 4545)
                duplicate_second = prefix(secondary, 4545)
                second_marker = b'Different second-library save fixture\n'
                (duplicate_second/'save.dat').write_bytes(second_marker)
                duplicate_rows = [g for g in legacy('get_games') if g['appid'] == '4545']
                assert len(duplicate_rows) == 2 and len({g['prefix_path'] for g in duplicate_rows}) == 2
                for backup in (False, True):
                    result = legacy('delete_prefix', appid=duplicate_rows[1]['appid'], do_backup=backup)
                    assert result == [False, 'Ambiguous prefix app ID in multiple rows; no prefix changed'], result
                    assert (duplicate_first/'save.dat').read_bytes() == marker
                    assert (duplicate_second/'save.dat').read_bytes() == second_marker
                    assert not (home/'Documents/PrefixBackups').exists()
                # Removing one fixture and refreshing restores an exact match.
                shutil.rmtree(duplicate_first)
                legacy('get_games')
                assert legacy('delete_prefix', appid='4545', do_backup=False) == [True, 'Success']
                assert not duplicate_second.exists()
                outside = home/'outside-marker'
                outside.mkdir()
                (outside/'keep.dat').write_bytes(marker)
                link = installed.parent/'4444'
                link.symlink_to(outside, target_is_directory=True)
                legacy('get_games')
                assert legacy('delete_prefix', appid='../outside-marker', do_backup=False)[0] is False
                assert legacy('delete_prefix', appid='4444', do_backup=False)[0] is False
                assert (outside/'keep.dat').read_bytes() == marker and link.is_symlink()
                link.unlink()
                # Backups must not silently read through nested symlinks.
                (installed/'linked.dat').symlink_to(outside/'keep.dat')
                assert legacy('delete_prefix', appid='4242', do_backup=True)[0] is False
                assert (installed/'save.dat').read_bytes() == marker
                assert not list((home/'Documents/PrefixBackups').glob('*.zip'))
                (installed/'linked.dat').unlink()
                # A Steam root replaced by a link after discovery stays blocked.
                installed.parent.rename(installed.parent.with_name('held-compatdata'))
                installed.parent.symlink_to(installed.parent.with_name('held-compatdata'), target_is_directory=True)
                assert legacy('delete_prefix', appid='4242', do_backup=False)[0] is False
                installed.parent.unlink()
                installed.parent.with_name('held-compatdata').rename(installed.parent)
                assert legacy('delete_prefix', appid='4242', do_backup=True) == [True, 'Success']
                assert not installed.exists()
                backups = list((home/'Documents/PrefixBackups').glob('4242-*.zip'))
                assert len(backups) == 1
                with zipfile.ZipFile(backups[0]) as saved:
                    assert saved.read('save.dat') == marker and 'empty/' in saved.namelist()
                # Reusing an app ID creates another backup, preserving the first.
                prefix(steam, 4242, True)
                legacy('get_games')
                assert legacy('delete_prefix', appid='4242', do_backup=True) == [True, 'Success']
                assert len(list(backups[0].parent.glob('4242-*.zip'))) == 2
                legacy('get_games')
                assert legacy('cleanup_orphans', do_backup=False) == refusal
                assert (unidentified/'save.dat').read_bytes() == marker
                # Explicit user selection remains separate from bulk cleanup.
                assert legacy('delete_prefix', appid='4343', do_backup=False) == [True, 'Success']
                assert not unidentified.exists() and (outside/'keep.dat').read_bytes() == marker
                assert legacy('get_games') == []
                report['independentState'] = {'backupBytesMatch': True, 'oldBackupPreserved': True,
                    'outsideMarkerPreserved': True, 'symlinkAndTraversalRejected': True,
                    'privatePrefixesRemoved': True, 'bulkCleanupAlwaysRefused': True,
                    'secondUserPrefixPreserved': True, 'malformedAndUnreadableShortcutsPreserved': True,
                    'ambiguousLibraryPrefixesPreserved': True}
                report['result'] = ('published Decky legacy discovery, current-user/multi-library discovery, '
                    'private backup/delete, two-user/malformed/unreadable shortcut bulk-cleanup refusals '
                    'and duplicate-library-ID/symlink/traversal refusals passed; no real saves or VR')
            elif case['probe'] == 'tabmaster-private-settings':
                # Exact published backend, synthetic users and private disk only.
                until_ready(lambda: current('get_setting', 'framey-ready', 'ready') == 'ready',
                            'TabMaster settings initialization')
                assert current('get_user_desktop') == str(home/'Desktop')
                assert current('get_users_dict') == {} and current('get_tags') == []
                assert current('set_active_user_id', 'framey-alice') is False
                assert current('get_tabs') == {} and current('get_tab_profiles') == {}
                alice_tabs = {
                    'shared': {'name': 'Private shared tab', 'visibleToOthers': True,
                               'filters': [{'type': 'installed', 'value': False}]},
                    'private': {'name': 'Private hidden tab', 'visibleToOthers': False},
                }
                profiles = {'private-profile': ['shared', 'private']}
                friends = [{'id': 'fixture-friend', 'name': 'Private Friend'}]
                friend_games = {'fixture-friend': [777, 888]}
                tags = [{'id': 17, 'name': 'Private tag'}]
                for method, value in [('set_tabs', alice_tabs), ('set_tab_profiles', profiles),
                                      ('set_friends', friends), ('set_friends_games', friend_games),
                                      ('set_tags', tags)]:
                    assert current(method, value) is None
                assert current('set_setting', 'framey-private-false', False) is False
                assert current('get_setting', 'framey-private-false', True) is False
                assert current('get_tabs') == alice_tabs
                assert current('get_tab_profiles') == profiles
                assert current('get_friends') == friends
                assert current('get_friends_games') == friend_games
                assert current('get_tags') == tags
                assert current('set_active_user_id', 'framey-bob') is False
                assert current('get_tabs') == {} and current('get_friends') == []
                assert current('get_friends_games') == {} and current('get_tab_profiles') == {}
                assert current('get_shared_tabs') == {'framey-alice': {'shared': alice_tabs['shared']}}
                bob_tabs = {'bob-only': {'name': 'Private Bob tab', 'visibleToOthers': False}}
                assert current('set_tabs', bob_tabs) is None
                assert current('set_active_user_id', 'framey-alice') is False
                assert current('get_tabs') == alice_tabs and current('get_shared_tabs') == {}
                state = base/'settings'/record['folder']/'settings.json'
                before = state.read_bytes()
                expected = {
                    'usersDict': {
                        'framey-alice': {'tabs': alice_tabs, 'friends': friends,
                                        'friendsGames': friend_games, 'tabProfiles': profiles},
                        'framey-bob': {'tabs': bob_tabs, 'friends': [], 'friendsGames': {}},
                    },
                    'tags': tags, 'framey-private-false': False,
                }
                assert json.loads(before) == expected
                with zipfile.ZipFile(io.BytesIO(data)) as original:
                    original_backend = original.read(record['folder']+'/main.py')
                installed_backend = (plugin/'main.py').read_bytes()
                assert (installed_backend == original_backend) is args.reproduce_tabmaster_restore_regression
                # Exercise the actual published backup/restore RPCs against
                # owned private files, then require restored bytes on restart.
                backup = home/'private-tabmaster-backup.json'
                assert current('backup_settings', str(backup)) is True
                backup_bytes = backup.read_bytes()
                assert json.loads(backup_bytes) == expected
                assert current('set_tags', [{'id': 99, 'name': 'Private changed tag'}]) is None
                dirty = state.read_bytes()
                assert dirty != before
                malformed = home/'private-tabmaster-invalid.json'
                malformed.write_bytes(b'{invalid private JSON')
                assert current('restore_settings', str(malformed)) is False
                assert state.read_bytes() == dirty and backup.read_bytes() == backup_bytes
                for name, payload in [('list', []), ('null', None), ('string', 'private')]:
                    invalid = home/('private-tabmaster-'+name+'.json')
                    invalid.write_text(json.dumps(payload))
                    assert current('restore_settings', str(invalid)) is False
                    assert state.read_bytes() == dirty and backup.read_bytes() == backup_bytes
                restored = current('restore_settings', str(backup))
                if args.reproduce_tabmaster_restore_regression:
                    assert restored is False and state.read_bytes() == dirty
                    # Reset only our private fixture through real RPC before
                    # retaining the unchanged settings/restart assertions.
                    assert current('set_tags', tags) is None
                else:
                    assert restored is True, {'validBackupRestore': restored,
                                              'nativeCalls': report['calls'][-5:]}
                assert state.read_bytes() == before
                assert backup.read_bytes() == backup_bytes
                stops = []

                def stop_tabmaster_loader():
                    # Match managed KillMode=mixed: let the loader stop its
                    # children before considering the group's cleanup fallback.
                    def identity(pid):
                        try:
                            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
                            return int(fields[1]), int(fields[19])
                        except (FileNotFoundError, ProcessLookupError):
                            return None
                    snapshot = {int(path.name): identity(int(path.name))
                                for path in Path('/proc').iterdir() if path.name.isdigit()}
                    owned = {backend.pid}
                    while True:
                        children = {pid for pid, value in snapshot.items()
                                    if value and value[0] in owned}
                        if children <= owned:
                            break
                        owned |= children
                    identities = {pid: snapshot[pid] for pid in owned}
                    assert all(identities.values()) and len(identities) >= 2
                    started = time.monotonic()
                    backend.send_signal(signal.SIGTERM)
                    assert backend.wait(timeout=8) == 0
                    elapsed = time.monotonic()-started
                    assert all(identity(pid) != value for pid, value in identities.items()), identities
                    log.flush()
                    text = (home/'runtime.log').read_text()
                    for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
                                   'Task was destroyed but it is pending', 'Bad file descriptor'):
                        assert marker not in text, marker
                    stops.append({'returncode': backend.returncode, 'elapsedSeconds': elapsed,
                                  'signaledOnlyOwnedLoader': True,
                                  'ownedProcessIdentitiesReaped': True,
                                  'ownedProcessCount': len(identities)})

                stop_tabmaster_loader()
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                restarted = until_ready(lambda: rpc('loader/get_plugins'), 'restarted TabMaster discovery')
                assert len(restarted) == 1 and restarted[0]['name'] == record['name']
                assert restarted[0]['version'] == record['version'] and not restarted[0]['disabled']
                until_ready(lambda: current('get_users_dict') == expected['usersDict'],
                            'TabMaster users restored from private settings')
                assert current('get_tags') == tags
                assert current('get_setting', 'framey-private-false', True) is False
                assert current('set_active_user_id', 'framey-bob') is False
                assert current('get_tabs') == bob_tabs
                assert current('get_shared_tabs') == {'framey-alice': {'shared': alice_tabs['shared']}}
                assert current('set_active_user_id', 'framey-alice') is False
                assert current('get_tabs') == alice_tabs
                assert current('get_tab_profiles') == profiles
                assert current('get_friends') == friends
                assert current('get_friends_games') == friend_games
                assert state.read_bytes() == before
                stop_tabmaster_loader()
                log.flush()
                loader_console = (home/'runtime.log').read_text()
                assert len(loader_console.encode()) <= 128*1024
                assert loader_console.count('Starting Decky version v3.3.0') == 2
                assert loader_console.count('[main][INFO]: Shutdown finished.') == 2
                report['privateSettings'] = dict(
                    loaderConsole=loader_console,
                    loaderConsoleSha256=hashlib.sha256(loader_console.encode()).hexdigest(),
                    jsonDecodeDiagnosticCount=loader_console.count('Expecting value: line 1 column 1 (char 0)'),
                    loaderConsoleErrorFree=False,
                    publishedBackendUnmodified=args.reproduce_tabmaster_restore_regression,
                    backendSha256=hashlib.sha256(installed_backend).hexdigest(),
                    originalBackendSha256=hashlib.sha256(original_backend).hexdigest(),
                    actualUserHome=True, emptyDefaults=True, falseValuesPreserved=True,
                    perUserTabsAndProfiles=True, perUserFriendsAndGames=True,
                    sharedTabVisibilityFiltered=True, globalTags=True,
                    settingsPersistedToDisk=True, settingsPersistedAcrossLoaderRestart=True,
                    settingsSha256=hashlib.sha256(before).hexdigest(),
                    ownedLoaderStops=stops, completeLoaderShutdownLogged=True,
                    backupRestoreVerified=not args.reproduce_tabmaster_restore_regression,
                    originalValidBackupRestoreRefused=args.reproduce_tabmaster_restore_regression,
                    malformedAndNonObjectBackupsRefused=True,
                    backupFilePreserved=True, restoredSettingsPersistedAcrossRestart=True,
                    steamLibraryEditingVerified=False,
                    browserVerified=False, realSteamCef=False, realFrameContacted=False,
                    physicalControllerVerified=False)
                report['result'] = ('published Decky API1 discovery, private per-user settings, '
                    'shared-tab filtering, false values and disk/loader-restart persistence passed; '+
                    ('original valid backup restore failure reproduced; ' if args.reproduce_tabmaster_restore_regression
                     else 'private backup/restore and malformed/non-object refusals passed; ')+
                    'Steam library editing, browser, Frame and VR unverified')
            elif case['probe'] == 'protondb-private-settings':
                # The exact frontend reads/writes one settings object. Keep
                # every write inside the disposable native container home.
                defaults = dict(size='regular', position='tl', labelTypeOnHover='off',
                    disableSubmit=False, enableLibraryBadge=True, enableStoreBadge=True,
                    storeBadgePosition='bc', showAnalysisButton=True, roundedCorners=False,
                    showLibraryIcons=True, libraryIconPosition='bl')
                state = base/'settings'/record['folder']/'config.json'
                assert current('get_setting', 'settings', defaults) == defaults
                # Published Decky shadows the bundled settings module and
                # creates an empty config during SettingsManager startup.
                initial = state.read_bytes()
                assert initial == b''
                assert current('get_setting', 'missing-private-setting', None) is None
                assert state.read_bytes() == initial, 'Reading defaults must preserve config bytes'
                info = current('get_system_info')
                assert set(info) == {'plugin_version', 'os_name', 'os_version', 'decky_version'}
                assert all(isinstance(value, str) and value for value in info.values()), info
                os_release = dict(line.split('=', 1) for line in
                    Path('/etc/os-release').read_text().splitlines() if '=' in line)
                assert info['os_name'] == os_release['NAME'].strip('"')
                assert info['os_version'] == os_release['VERSION_ID'].strip('"')
                first = dict(defaults, size='compact', position='br', enableLibraryBadge=False)
                assert current('set_setting', 'settings', first) is None
                assert current('get_setting', 'settings', defaults) == first
                assert json.loads(state.read_text()) == {'settings': first}
                saved = dict(first, enableStoreBadge=False, roundedCorners=True)
                assert current('set_setting', 'settings', saved) is None
                before = state.read_bytes()
                assert json.loads(before) == {'settings': saved}
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                restarted = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert len(restarted) == 1 and restarted[0]['name'] == record['name']
                assert restarted[0]['version'] == record['version'] and not restarted[0]['disabled']
                assert current('get_setting', 'settings', defaults) == saved
                assert current('get_setting', 'missing-private-setting', False) is False
                assert current('get_system_info') == info
                assert state.read_bytes() == before, 'Restart/read must preserve settings bytes'
                report['privateSettings'] = dict(defaultReadPreservesEmptyConfig=True,
                    frontendSettingsObject=True, settingsPersistedToDisk=True,
                    settingsPersistedAcrossLoaderRestart=True, falseValuesPreserved=True,
                    systemInfoMatchesPrivateContainer=True, noProductionChanges=True,
                    settingsSha256=hashlib.sha256(before).hexdigest(),
                    badgeRenderingVerified=False, browserVerified=False,
                    realSteamCef=False, realFrameContacted=False,
                    physicalControllerVerified=False)
                report['result'] = ('published Decky API2 discovery, private frontend settings '
                    'write/read and loader-restart persistence, false values and container OS '
                    'metadata passed; badge rendering, browser, Frame and VR unverified')
            elif case['probe'] == 'steam-status-private-settings':
                # Only change private container settings. The public CM-list
                # and 100 MB download diagnostics must never run in this probe.
                source = (plugin/'main.py').read_text()
                assert source.count('ssl.create_default_context()') == 2
                assert 'ssl.CERT_NONE' not in source and 'ssl_context.check_hostname = False' not in source
                settings = current('get_settings')
                assert isinstance(settings, dict) and settings['refresh_interval_seconds'] == 120, settings
                assert current('set_setting', 'refresh_interval_seconds', 180) is True
                assert current('get_setting', 'refresh_interval_seconds') == 180
                state = base/'settings'/record['folder']/'settings.json'
                assert json.loads(state.read_text())['refresh_interval_seconds'] == 180
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert until_ready(lambda: current('get_setting', 'refresh_interval_seconds') == 180,
                                   'private Steam Status setting after restart')
                report['result'] = ('published Decky discovery, private setting write/read and restart '
                                    'persistence passed; both managed public diagnostic contexts retain TLS '
                                    'verification; no public network diagnostics, Frame or VR test')
            elif case['probe'] == 'wine-cellar-private-state':
                helper = plugin/'bin/backend'
                machine = 183 if __import__('platform').machine() == 'aarch64' else 62
                assert helper.read_bytes()[:4] == b'\x7fELF'
                assert int.from_bytes(helper.read_bytes()[18:20], 'little') == machine
                helper_digest = hashlib.sha256(helper.read_bytes()).hexdigest()
                assert helper_digest == (frame_decky_store.WINE_CELLAR_AARCH64 if machine == 183
                                         else frame_decky_store.WINE_CELLAR_ORIGINAL)
                report['helperSha256'] = helper_digest
                import wine_cellar_private
                report.update(wine_cellar_private.probe(backend, helper, loader, env, log, processes,
                    current, rpc, until_ready, regression=args.reproduce_wine_cellar_unload_regression))
            elif case['probe'] == 'deck-settings-readonly':
                # Never upload images, send a token, or change game settings.
                # The container has no network or host Steam library access.
                source = (plugin/'main.py').read_text()
                assert 'ssl.CERT_NONE' not in source and 'ctx.check_hostname = False' not in source
                vendor = current('get_sys_vendor')
                storage = current('is_emmc_storage')
                assert isinstance(vendor, str) and isinstance(storage, bool), (vendor, storage)
                # Exercise only the installed helper method against a private
                # self-signed listener. A successful TLS handshake would expose
                # the fixture bearer header, so rejection is the required result.
                cls = next(node for node in ast.parse(source).body
                           if isinstance(node, ast.ClassDef) and node.name == 'Plugin')
                method = next(node for node in cls.body
                              if isinstance(node, ast.FunctionDef) and node.name == '_http_request')
                namespace = {'ssl': ssl, 'urllib': __import__('urllib'), 'RuntimeError': RuntimeError}
                exec(compile(ast.Module(body=[method], type_ignores=[]),
                             '<managed-deck-settings>', 'exec'), namespace)

                hits = []
                class UploadHandler(BaseHTTPRequestHandler):
                    def do_POST(self):
                        hits.append(self.headers.get('Authorization'))
                        self.send_response(200)
                        self.end_headers()

                    def log_message(self, *_):
                        pass

                secure = ThreadingHTTPServer(('127.0.0.1', 0), UploadHandler)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                fixtures = ROOT/'tests/decky-runtime/fixtures'
                context.load_cert_chain(fixtures/'localhost-selfsigned.crt',
                                        fixtures/'localhost-selfsigned.key')
                secure.socket = context.wrap_socket(secure.socket, server_side=True)
                worker = threading.Thread(target=secure.serve_forever, daemon=True)
                worker.start()
                try:
                    try:
                        namespace['_http_request'](None, f'https://localhost:{secure.server_port}/',
                                                   'POST', {'Authorization': 'Bearer private-fixture'},
                                                   b'private fixture', timeout=3)
                    except RuntimeError as error:
                        assert 'CERTIFICATE_VERIFY_FAILED' in str(error), error
                    else:
                        raise AssertionError('Deck Settings accepted a self-signed upload endpoint')
                    assert hits == [], hits
                finally:
                    secure.shutdown()
                    secure.server_close()
                    worker.join(timeout=3)
                report['result'] = ('published Decky discovery and read-only system/storage RPCs passed; '
                                    'managed upload helper rejected self-signed loopback HTTPS; '
                                    'real uploads, reports, settings writes, Frame and VR unverified')
            elif case['probe'] == 'theme-music-settings':
                # The official plugin can search/download media and patch Steam
                # game pages. This case exercises only private settings in a
                # networkless container, without media or user library data.
                key = 'framey_private_fixture'
                assert current('get_setting', key, 'missing') == 'missing'
                assert current('set_setting', key, 'saved') is None
                assert current('get_setting', key, 'missing') == 'saved'
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert until_ready(lambda: current('get_setting', key, 'missing') == 'saved',
                                   'private Game Theme Music setting after restart')
                report['result'] = ('published Decky discovery and private setting restart passed; '
                                    'search, downloads, playback, Steam page injection, Frame and VR unverified')
            elif case['probe'] == 'emuchievements-private-hash':
                # Synthetic files live only in this networkless, disposable
                # container. Do not read a user's ROMs or log in to RA.
                content = b'Framey private synthetic ROM fixture\n' * 3
                fixture = home/'private.rom'
                fixture.write_bytes(content)
                expected = hashlib.md5(content).hexdigest()
                assert legacy('hash', path=str(fixture)) == expected
                packed = home/'private.zip'
                with zipfile.ZipFile(packed, 'w') as container:
                    container.writestr('private.rom', content)
                assert legacy('hash', path=str(packed)) == expected
                # A path that looks like shell syntax must reach the helper
                # literally; the managed backend never runs a shell.
                literal = home/'$(touch should-not-exist).rom'
                literal.write_bytes(content)
                assert legacy('hash', path=str(literal)) == expected
                assert not (home/'should-not-exist').exists()
                for member, kind in (('../escape.rom', 'traversal'),
                                     ('/tmp/escape.rom', 'absolute')):
                    malicious = home/f'{kind}.zip'
                    with zipfile.ZipFile(malicious, 'w') as container:
                        container.writestr(member, content)
                    try:
                        legacy('hash', path=str(malicious))
                        raise AssertionError(f'{kind} archive was accepted')
                    except AssertionError as error:
                        assert 'ROM hash helper failed' in str(error), error
                link_archive = home/'link.zip'
                with zipfile.ZipFile(link_archive, 'w') as container:
                    entry = zipfile.ZipInfo('link.rom')
                    entry.create_system = 3
                    entry.external_attr = 0o120777 << 16
                    container.writestr(entry, 'target.rom')
                try:
                    legacy('hash', path=str(link_archive))
                    raise AssertionError('symlink archive was accepted')
                except AssertionError as error:
                    assert 'ROM hash helper failed' in str(error), error
                assert not list(Path('/tmp').glob('framey-hash-*'))
                assert not (home/'escape.rom').exists()
                assert not Path('/tmp/escape.rom').exists()
                assert (plugin/'bin/hash').read_bytes()[:4] == b'\x7fELF'
                report['result'] = ('published Decky discovery, direct and archived synthetic ROM hashes, '
                                    'literal path and hostile archive rejection passed; real ROMs, login, '
                                    'Steam UI, Frame and VR unverified')
            elif case['probe'] == 'battery-tracker':
                empty_or_first = legacy('get_recent_data', lookback=2)
                assert isinstance(empty_or_first['x'], list) and isinstance(empty_or_first['cap'], list)
                assert isinstance(empty_or_first['power_data'], list)
                initial = until_ready(lambda: legacy('get_recent_data', lookback=2)['cap'], 'private first battery sample')
                assert initial[-1] == .89, initial
                assert legacy('set_app', app='Framey private') is True
                (supply/'status').write_text('Discharging\n')
                sample = until_ready(lambda: next((row for row in legacy('get_recent_data', lookback=2)['power_data']
                    if row['name']=='Framey private'), None), 'private discharging battery sample')
                assert sample['average_power'] > 0, sample
                history = legacy('get_recent_data', lookback=2)
                assert len(history['x']) == len(history['cap']) >= 2, history
                import battery_private
                report['batteryLifecycle'] = battery_private.probe(
                    backend, loader, env, log, processes, legacy, rpc, until_ready, history,
                    regression=args.reproduce_battery_tracker_unload_regression)
                report['backendSha256'] = hashlib.sha256((plugin/'main.py').read_bytes()).hexdigest()
                report['ipcAdapterSha256'] = (None if args.reproduce_battery_tracker_unload_regression else
                    hashlib.sha256((plugin/'py_modules/framey_decky_ipc.py').read_bytes()).hexdigest())
                if args.reproduce_battery_tracker_unload_regression:
                    report['expectedRegression'] = dict(success=False, phase='plugin unload',
                        previousManagedSourceRestored=True, forcedPluginKills=1,
                        pendingBatterySamplesLost=True, qualifiedCompatibilityPass=False)
                report['result'] = ('previous managed child IPC forced-kill and lost pending samples reproduced'
                    if args.reproduce_battery_tracker_unload_regression else
                    'discovery, private samples, history/per-app power, two clean parent-only stops, pending flush and restart persistence passed; real managed Frame backend unverified')
            elif case['probe'] == 'network-sentinel':
                assert current('get_settings')['auto_monitor'] is False
                assert current('get_network_history') == []
                assert current('get_live_ping') == 0
                assert current('get_bandwidth_stats') == {'download_bps': 0, 'upload_bps': 0}
                assert current('update_settings', {'show_bandwidth': False}) is True
                assert current('get_settings')['show_bandwidth'] is False
                connection = current('get_connection_info')
                assert isinstance(connection.get('hostname', connection.get('error')), str), connection
                status = current('get_network_status')
                assert status['quality']['quality'] == 'disconnected', status
                assert status['quality']['jitter'] == 0, status
                assert current('start_monitoring') is True
                history = until_ready(lambda: current('get_network_history'), 'isolated network sample')
                assert 'bandwidth' in history[0] and 'quality' in history[0], history
                assert current('stop_monitoring') is True
                report['result'] = 'discovery, native psutil, private settings and isolated monitoring loop passed; external latency/DNS and live Frame unverified'
            elif case['probe'] == 'localsend':
                helper = plugin/'bin/localsend-core'
                expected = ('e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae'
                            if __import__('platform').machine() == 'aarch64'
                            else 'd448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843')
                assert hashlib.sha256(helper.read_bytes()).hexdigest() == expected
                status = current('get_backend_status')
                assert status == {'running': False, 'url': 'https://127.0.0.1:53317'}, status
                settings = current('get_backend_config')
                assert settings['use_https'] and not settings['auto_save'], settings
                assert settings['network_interface'] == '*', settings
                assert settings['download_folder'].startswith(str(base)), settings
                stopped = current('proxy_get', '/api/localsend/v2/info')
                assert stopped['status'] == 503 and stopped['data']['error'] == 'Backend not running', stopped
                report['result'] = 'published Decky discovery and public read-only settings/status RPC passed; network helper remained stopped'
            elif case['probe'] == 'fileserver':
                assert until_ready(lambda: current('get_port') == 8000, 'default port')
                assert current('get_directory') == str(home)
                assert current('get_server_running') is False
                for bad_directory in ('', 'relative-folder', str(home/'missing-folder')):
                    rejected = current('set_status', {'directory': bad_directory, 'server_running': True})
                    assert not rejected['server_running'] and 'existing absolute directory' in rejected['error'], rejected
                fixture = home/'public-fixture'
                fixture.mkdir()
                marker = b'Framey public read-only fixture\n'
                (fixture/'marker.txt').write_bytes(marker)
                # A thumbnail-compatible file must remain a normal link when disabled.
                (fixture/'image.png').write_bytes(b'public placeholder; thumbnails disabled')
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = listener.getsockname()[1]
                status = current('set_status', {'directory': str(fixture), 'port': port, 'timeout': 1,
                    'allow_uploads': False, 'disable_thumbnails': True, 'server_running': True})
                assert status['server_running'] and not status['allow_uploads'] and status['disable_thumbnails'], status
                context = ssl._create_unverified_context()  # Upstream ships its public self-signed test cert.
                url = f'https://127.0.0.1:{port}'
                def fetch(path):
                    return urllib.request.urlopen(url+path, context=context, timeout=3).read()
                listing = until_ready(lambda: fetch('/files/'), 'private file server')
                assert b'marker.txt' in listing and b'image.png' in listing, listing
                assert (b'/preview/files/image.png' in listing) == args.reproduce_fileserver_empty_flag_regression, listing
                assert fetch('/files/marker.txt') == marker
                try:
                    fetch('/upload')
                    raise AssertionError('uploads must be disabled')
                except urllib.error.HTTPError as error:
                    assert error.code == 401, error.code
                assert current('set_server_running', False) is False
                assert current('get_server_running') is False
                assert current('get_history') == [str(fixture)]
                report['result'] = ('original empty argument bug reproduced: thumbnail policy ignored'
                    if args.reproduce_fileserver_empty_flag_regression else
                    'discovery, API1 settings, native HTTPS listing/download, thumbnail policy and stop passed; uploads disabled')
            elif case['probe'] == 'free-loader':
                settings = current('settings_read')
                assert settings['notify_on_free_games'] is True, settings
                assert settings['larger_text'] is False, settings
                assert current('read_deals') == {}
                # This plugin commits defaults on startup and writes an empty
                # deals cache on first read. Both paths are private to this
                # disposable container; no feed, notification or store call.
                settings_dir = base/'settings'/record['folder']
                assert (settings_dir/'settings.json').is_file()
                assert (settings_dir/'deal_db.json').is_file()
                current('settings_setSetting', 'larger_text', True)
                assert current('settings_read')['larger_text'] is True
                import free_loader_private
                free_loader_private.probe(backend, loader, env, log, processes, current, rpc,
                    until_ready, report, settings_dir,
                    regression=args.reproduce_free_loader_unload_regression)
                report['backendSha256'] = hashlib.sha256((plugin/'main.py').read_bytes()).hexdigest()
                report['ipcAdapterSha256'] = (None if args.reproduce_free_loader_unload_regression else
                    hashlib.sha256((plugin/'py_modules/framey_decky_ipc.py').read_bytes()).hexdigest())
                if args.reproduce_free_loader_unload_regression:
                    report['expectedRegression'] = dict(success=False, phase='plugin unload',
                        originalSourceRestored=True, forcedPluginKills=1,
                        qualifiedCompatibilityPass=False)
                report['result'] = ('original Free Loader source requires forced stop; expected negative only'
                    if args.reproduce_free_loader_unload_regression else
                    'discovery, private settings/cache/hidden-state persistence and two clean parent-only stops passed; '
                    'feed, notifications, browser and Frame unverified')
            elif case['probe'] == 'game-sync-config':
                # Exercise private settings and read-only selections. This plugin also exposes
                # rclone cloud sync and arbitrary process signals; neither
                # belongs in a passive compatibility probe.
                settings = current('get_config')
                assert settings['sync_on_game_start'] is False, settings
                assert settings['sync_on_game_stop'] is False, settings
                assert settings['capture_upload'] is False, settings
                assert settings['advanced_mode'] is False, settings
                assert current('set_config', 'advanced_mode', True) is None
                assert current('get_config')['advanced_mode'] is True
                selection = home/'sync-selection/saves'
                selection.mkdir(parents=True)
                (selection/'nested').mkdir()
                (selection/'save.bin').write_bytes(b'private save')
                (selection/'nested/save2.bin').write_bytes(b'private nested save')
                outside = home/'sync-selection/saves-other'
                outside.mkdir()
                marker = b'private outside fixture'
                (outside/'private.bin').write_bytes(marker)
                (selection/'alias').symlink_to(selection/'nested')
                assert current('set_config', 'sync_root', str(selection)) is None
                assert current('test_syncpath', str(selection/'save.bin')) == 1
                assert current('test_syncpath', str(selection)+'/*') == 1
                assert current('test_syncpath', str(selection/'nested')+'/**') == 1
                assert current('test_syncpath', str(selection/'alias')+'/**') == 1

                def refused(path):
                    try:
                        current('test_syncpath', str(path))
                    except AssertionError as error:
                        assert 'outside the sync root' in str(error) or 'Recursive directory link' in str(error), error
                    else:
                        raise AssertionError('Expected Game Sync selection refusal')

                refused(outside/'private.bin')
                refused(selection/'../saves-other/private.bin')
                link = selection/'linked.bin'
                link.symlink_to(outside/'private.bin')
                refused(link)
                refused(str(selection)+'/**')
                link.unlink()
                link = selection/'linked-directory'
                link.symlink_to(outside)
                refused(str(selection)+'/**')
                link.unlink()
                (selection/'nested/cycle').symlink_to(selection)
                refused(str(selection)+'/**')
                (selection/'nested/cycle').unlink()
                assert (outside/'private.bin').read_bytes() == marker
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert until_ready(lambda: current('get_config')['advanced_mode'],
                                   'private Game Sync setting after restart') is True
                assert current('get_config')['sync_root'] == str(selection)
                assert current('test_syncpath', str(selection/'save.bin')) == 1
                refused(outside/'private.bin')
                assert (outside/'private.bin').read_bytes() == marker
                report['independentState'] = {'outsideFileUnchanged':True, 'validSelectionCount':True,
                    'siblingAndParentEscapeRefused':True, 'outsideLinksRefused':True,
                    'insideLinksAllowed':True, 'cyclesRefused':True, 'restartBoundaryPreserved':True}
                report['result'] = ('discovery, default config, bounded private selections and setting restart persistence passed; '
                    'rclone, cloud authentication, sync, process signals, real Frame and VR unverified')
            elif case['probe'] == 'suggestme-private':
                # No Steam API key, account, owned library, external request or
                # recommendation fetch enters this network-isolated probe.
                source = (plugin/'main.py').read_text()
                assert 'ssl.CERT_NONE' not in source and 'check_hostname = False' not in source
                config = current('get_config')
                assert config['has_steam_api_key'] is False and config['has_steam_id'] is False, config
                status = current('get_library_status')
                assert status['total_games'] == 0 and status['is_refreshing'] is False, status
                empty = current('get_suggestion', 'luck', {})
                assert empty['game'] is None and 'Library is empty' in empty['error'], empty
                assert current('get_filter_presets')['active_index'] is None
                saved = current('save_filter_preset', 0, 'Framey private', {'genres': []})
                assert saved == {'success': True}, saved
                presets = current('get_filter_presets')
                assert presets['active_index'] == 0 and presets['presets'][0]['label'] == 'Framey private', presets
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                restored = until_ready(lambda: current('get_filter_presets')['presets'][0],
                                       'private SuggestMe preset after restart')
                assert restored['label'] == 'Framey private', restored
                report['result'] = ('published Decky discovery, empty library and private preset restart passed; '
                    'network recommendations, actual Steam library, Frame and VR unverified')
            elif case['probe'] == 'notifications-private':
                assert not Path('/tmp/notifications.log').exists()
                assert 'filename="/tmp/notifications.log"' not in (plugin/'main.py').read_text()
                assert '=== ENVIRON ===' not in (plugin/'py_modules/connector/crypto.py').read_text()

                def fingerprint_when_ready():
                    # Decky lists the plugin before its _main finishes creating
                    # local.crt. Retry only that known startup race; all other
                    # RPC failures still fail this native backend check.
                    response = rpc('loader/call_legacy_plugin_method', record['name'],
                                   'local_fingerprint', {})
                    if response.get('success') is True:
                        report['calls'].append({'method': 'local_fingerprint',
                                                'result': response['result']})
                        return response['result']
                    if (response.get('success') is False and
                            "No such file or directory: 'local.crt'" in str(response.get('result'))):
                        raise FileNotFoundError('private certificate is still being created')
                    raise AssertionError(('local_fingerprint', response))

                fingerprint = until_ready(fingerprint_when_ready, 'private certificate fingerprint')
                assert len(fingerprint) == 64 and all(c in '0123456789abcdef' for c in fingerprint), fingerprint
                assert legacy('device_list') == []
                assert legacy('notification_list') == []
                assert legacy('get_event') is None
                dbs = list(base.rglob('db.sqlite3'))
                assert len(dbs) == 1, dbs
                with sqlite3.connect(dbs[0]) as connection:
                    connection.execute('INSERT INTO notification(id,title,body,appName,silent,requestReplyId,time) '
                        'VALUES (?,?,?,?,?,?,?)', ('private-1','Private title','Private body','Fixture',1,'',1))
                notifications = legacy('notification_list')
                assert len(notifications) == 1 and notifications[0]['title'] == 'Private title', notifications
                assert legacy('notifications_clear') is None
                assert legacy('notification_list') == []
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert until_ready(fingerprint_when_ready, 'persisted fingerprint') == fingerprint
                assert legacy('notification_list') == []
                assert not Path('/tmp/notifications.log').exists()
                report['result'] = ('discovery, private certificate, empty device list and synthetic notification '
                    'read/clear/restart passed; pairing, live notifications, Frame and VR unverified')
            elif case['probe'] == 'radio-local':
                # Exercise HTTP behavior and prove managed RadiYo rejects a
                # self-signed HTTPS endpoint. No station or audio opens.
                marker = 'Framey private radio station\n'
                assert 'ctx.verify_mode = ssl.CERT_NONE' not in (plugin/'main.py').read_text()

                class RadioHandler(BaseHTTPRequestHandler):
                    def do_GET(self):
                        if self.path == '/redirect':
                            self.send_response(302)
                            self.send_header('Location', '/station')
                            self.end_headers()
                        elif self.path == '/station':
                            data = marker.encode()
                            self.send_response(200)
                            self.send_header('Content-Type', 'text/plain')
                            self.send_header('Content-Length', str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                        else:
                            self.send_error(404)

                    def log_message(self, *_):
                        pass

                server = ThreadingHTTPServer(('127.0.0.1', 0), RadioHandler)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    base_url = f'http://127.0.0.1:{server.server_port}'
                    station = legacy('fetch', url=base_url+'/station', customStation=False)
                    assert station['status'] == 200 and station['body'] == marker, station
                    assert station['headers']['Content-Type'] == 'text/plain', station
                    custom = legacy('fetch', url=base_url+'/station', customStation=True)
                    assert custom['status'] == 200 and custom['body'] == '', custom
                    redirect = legacy('getRedirectUrl', url=base_url+'/redirect')
                    assert redirect == {'response': base_url+'/station'}, redirect
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=3)
                secure = ThreadingHTTPServer(('127.0.0.1', 0), RadioHandler)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                fixtures = ROOT/'tests/decky-runtime/fixtures'
                context.load_cert_chain(fixtures/'localhost-selfsigned.crt',
                                        fixtures/'localhost-selfsigned.key')
                secure.socket = context.wrap_socket(secure.socket, server_side=True)
                worker = threading.Thread(target=secure.serve_forever, daemon=True)
                worker.start()
                try:
                    base_url = f'https://localhost:{secure.server_port}'
                    for method, kwargs in (
                            ('fetch', {'url': base_url+'/station', 'customStation': False}),
                            ('getRedirectUrl', {'url': base_url+'/redirect'})):
                        result = legacy(method, **kwargs)
                        assert 'error' in result and 'CERTIFICATE_VERIFY_FAILED' in result['error'], result
                finally:
                    secure.shutdown()
                    secure.server_close()
                    worker.join(timeout=3)
                report['result'] = ('discovery, loopback HTTP fetch/redirect and self-signed HTTPS rejection passed; '
                    'external stations, trusted HTTPS, playback, real Frame and VR unverified')
            elif case['probe'] == 'desktop-apps-private-entries':
                import shlex
                apps = current('get_apps')
                assert apps['framey-private'] == dict(id='framey-private', name='Private Desktop App',
                    bin=str(executable), cmd=shlex.join(['--name', 'Private Desktop App', '--file', str(desktop)]),
                    workdir=str(home), flatpak=False), apps
                flatpak = apps['nested-framey-flatpak']
                assert flatpak == dict(id='nested-framey-flatpak', name='Private Flatpak', bin='/usr/bin/flatpak',
                    cmd='run org.framey.Private', workdir=str(home/'private-workdir'), flatpak=True), flatpak
                assert not any('framey-private-'+name in apps for name in
                               ('hidden','nodisplay','terminal','link','noname','noexec','malformed')), apps
                assert not canary.exists()
                current('set_app_setting', 'framey-private', 'favorite', True)
                current('set_app_setting', 'framey-private', 'hidden', True)
                current('set_app_setting', 'framey-private', 'lastOpened', 424242)
                assert current('get_temporary_shortcuts') == []
                current('save_temporary_shortcut', 424242)
                current('save_temporary_shortcut', 424242)
                assert current('get_temporary_shortcuts') == [424242]
                state = base/'settings'/record['folder']/'settings.json'
                saved = json.loads(state.read_text())
                assert saved['apps']['framey-private'] == dict(favorite=True, hidden=True, lastOpened=424242)
                assert saved['temporaryShortcuts'] == [424242]
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Desktop Apps discovery')
                restored = current('get_apps')['framey-private']
                assert restored['favorite'] is True and restored['hidden'] is True and restored['lastOpened'] == 424242
                assert current('get_temporary_shortcuts') == [424242]
                current('forget_temporary_shortcut', 424242)
                current('forget_temporary_shortcut', 424242)
                assert current('get_temporary_shortcuts') == []
                assert json.loads(state.read_text())['temporaryShortcuts'] == []
                assert not canary.exists()
                report['desktopEntries'] = dict(discovery=True, xdgPrecedence=True, filteredEntries=7,
                    fieldCodes=True, flatpakMetadata=True, privateSettingsPersisted=True,
                    temporaryShortcutBookkeeping=True, loaderRestart=True, noApplicationLaunched=True,
                    actualFlatpakDiscovery=False, actualSteamShortcutChanges=False,
                    realFrameContacted=False, physicalControllerVerified=False)
                report['result'] = ('published Decky discovery, private desktop-entry parsing/filtering, '
                    'settings and temporary-shortcut bookkeeping across restart passed; actual Flatpak installation, '
                    'Steam shortcut changes, app launch, real Frame and VR unverified')
            elif case['probe'] == 'shelves-settings':
                # Private configuration only. Never register a Steam Home
                # patch, import a user's settings, or touch their library.
                defaults = current('get_settings')
                assert defaults['enabled'] is False and defaults['shelves'] == [], defaults
                shelf = {'id': 'framey-private-shelf', 'title': 'Private Test',
                         'source': {'type': 'tab', 'tab': 'all'}, 'limit': 4}
                assert current('set_settings', {'enabled': False, 'shelves': [shelf]}) is True
                saved = current('get_settings')
                assert len(saved['shelves']) == 1 and saved['shelves'][0]['title'] == 'Private Test', saved
                state = base/'settings'/record['folder']/'settings.json'
                assert json.loads(state.read_text())['state']['shelves'][0]['id'] == shelf['id']
                backend.send_signal(signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                restored = until_ready(lambda: current('get_settings')['shelves'],
                                       'private shelf after restart')
                assert restored[0]['id'] == shelf['id'] and restored[0]['title'] == shelf['title'], restored
                report['result'] = ('published Decky discovery, private shelf settings and restart persistence passed; '
                    'Steam Home injection, real Frame and VR unverified')
            elif case['probe'] == 'storage-cleaner':
                # The only deletion is an owned marker under this disposable
                # container's private Steam fixture, never a real game cache.
                apps = home/'.steam/steam/steamapps'
                selected = apps/'shadercache/424242'
                selected.mkdir(parents=True)
                marker = b'Framey private cache fixture\n'
                (selected/'marker').write_bytes(marker)
                assert current('get_size', 'shadercache/424242') == len(marker)
                rows = json.loads(current('list_games_with_temp_data', 'shadercache'))
                assert rows == [{'appid': '424242', 'size': len(marker),
                                 'size_readable': f'{len(marker)}.0 B'}], rows
                assert current('delete_cache', 'shadercache/424242') is None
                assert not selected.exists()
                assert apps.joinpath('shadercache').is_dir()
                whole = apps/'compatdata'
                whole.mkdir()
                (whole/'marker').write_bytes(marker)
                assert current('get_size', 'compatdata') == len(marker)
                assert current('delete_cache', 'compatdata') is None
                assert not whole.exists()
                report['result'] = ('published Decky discovery, private size/list and selected/whole fixture deletion passed; '
                    'real Steam caches, Frame and VR unverified')
            elif case['probe'] == 'steamback-private-save':
                # The loader and plugin only see this disposable container home.
                steam = home/'.local/share/Steam'
                game = steam/'userdata/424242/777'
                remote = game/'remote'
                remote.mkdir(parents=True)
                (steam/'steamapps').mkdir(parents=True)
                (steam/'steamapps/appmanifest_777.acf').write_text(
                    '"AppState"\n{\n"installdir" "private-game"\n}\n')
                (game/'remotecache.vdf').write_text(
                    '"777"\n{\n"save.dat"\n{\n"size" "3"\n}\n}\n')
                save = remote/'save.dat'
                save.write_bytes(b'old')
                game_info = {'game_id': 777, 'install_root': str(steam)}
                assert legacy('set_account_id', id_num=424242) is None
                assert legacy('get_saveinfos') == []
                assert legacy('find_supported', game_infos=[]) == []
                supported = legacy('find_supported', game_infos=[game_info])
                assert len(supported) == 1 and supported[0]['save_games_roots'] == {str(remote): ''}, supported
                snapshot = legacy('do_backup', game_info=supported[0])
                assert snapshot['game_info']['game_id'] == 777 and not snapshot['is_undo'], snapshot
                saved = list(base.rglob(snapshot['filename']+'/save.dat'))
                assert len(saved) == 1 and saved[0].read_bytes() == b'old', saved
                save.write_bytes(b'new')
                assert legacy('do_restore', save_info=snapshot) is None
                assert save.read_bytes() == b'old'
                undo = next(item for item in legacy('get_saveinfos') if item['is_undo'])
                undone = list(base.rglob(undo['filename']+'/save.dat'))
                assert len(undone) == 1 and undone[0].read_bytes() == b'new', undone
                assert legacy('do_restore', save_info=undo) is None
                assert save.read_bytes() == b'new'
                report['result'] = ('published Decky discovery and private save discovery, backup, restore and undo '
                    'passed with independent bytes; real Steam saves, Frame and VR unverified')
            elif case['probe'] == 'toggle-settings':
                def call(method, *values):
                    result = rpc('loader/call_plugin_method', record['name'], method, *values)
                    report['calls'].append({'method': method, 'result': result})
                    return result

                assert call('load_settings') == {}
                # Settings only. Never call pause/resume/kill or signal a process.
                for value in (True, False, True):
                    call('save_setting', 'autoPause', value)
                    assert call('load_settings')['autoPause'] is value
                call('add_no_auto_pause_set', 424242)
                assert call('load_settings')['noAutoPauseSet'] == [424242]
                call('remove_no_auto_pause_set', 424242)
                assert call('load_settings')['noAutoPauseSet'] == []
                settings = json.loads((base/'settings'/record['folder']/'settings.json').read_text())
                assert settings['autoPause'] is True and settings['noAutoPauseSet'] == []
                report['result'] = 'discovery and Toggle-backed private settings persistence passed; no process actions'
            elif case['probe'] == 'timer-lifecycle':
                from timer_lifecycle import probe

                def restart(settings=None):
                    nonlocal backend
                    backend.send_signal(signal.SIGTERM)
                    backend.wait(timeout=8)
                    if settings is not None:
                        path = base/'settings'/record['folder']/'settings.json'
                        assert path.exists(), path
                        path.write_text(json.dumps(settings))
                    backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                               start_new_session=True)
                    processes.append(backend)
                    until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                    until_ready(lambda: rpc('loader/call_plugin_method', record['name'],
                        'settings_getSetting', 'subtle_mode', False), 'restarted instance RPC')

                report['lifecycle'] = probe(record['name'], restart, home/'runtime.log',
                                            args.reproduce_timer_regression)
                report['result'] = ('upstream timer lifecycle regressions reproduced' if args.reproduce_timer_regression
                    else 'discovery, cancel, replace, completion and persistent restart passed')
            elif args.reproduce_bound_method_regression:
                response = rpc('loader/call_legacy_plugin_method', record['name'], 'sp_list_media_players', {})
                assert response['success'] is False and 'self' in response['result'], response
                report['expectedRegression'] = response
                report['result'] = 'historical bad shim rejected by actual Decky legacy dispatch'
            elif case['probe'] == 'mpris':
                player_name = 'org.mpris.MediaPlayer2.FrameySilent'
                assert legacy('sp_list_media_players') == player_name
                legacy('sp_set_media_player', player=player_name)
                assert legacy('sp_get_media_player') == player_name
                assert legacy('sp_identity', orgPath=player_name) == 'Player'  # Upstream truncation.
                metadata = legacy('get_meta_data')
                assert 'title|Silent Test Track' in metadata and 'length|180000000' in metadata, metadata
                assert legacy('sp_track_status') == 'Paused'
                assert legacy('sp_track_progress') == '12000000'
                assert legacy('sp_can_seek') == 'true'
                assert float(legacy('sp_get_volume')) == .4
                assert legacy('sp_test_volume_control') == 'true'
                assert json.loads(Path('/tmp/mpris-state.json').read_text())['Volume'] == .4
                legacy('sp_play')
                assert legacy('sp_track_status') == 'Playing'
                legacy('sp_pause')
                legacy('sp_next')
                legacy('sp_previous')
                legacy('sp_seek', amount=2000000)
                assert legacy('sp_track_progress') == '14000000'
                legacy('sp_set_position', position=45000000, trackid='/org/framey/TestTrack/1')
                legacy('sp_set_volume', volume=.25)
                state = json.loads(Path('/tmp/mpris-state.json').read_text())
                assert state['PlaybackStatus'] == 'Paused' and state['Volume'] == .25, state
                assert state['next'] == state['previous'] == 1 and state['Position'] == 45000000, state
                report['independentState'] = state
                report['result'] = 'discovery, metadata, transport, seek and volume passed'
            elif case['probe'] == 'system-monitor':
                def metric(method):
                    response = legacy(method)
                    if response['code'] != 0:
                        raise ValueError(response['data'])
                    return json.loads(response['data'])
                assert legacy('get_version') == {'code': 0, 'data': record['version']}
                memory = until_ready(lambda: metric('get_memory'), 'DeckySpy stats thread')
                assert memory['vmem']['total'] > 0 and 0 <= memory['vmem']['percent'] <= 100, memory
                cpu = metric('get_cpu')
                assert 0 <= cpu <= 100, cpu
                assert metric('get_boottime') > 0
                assert isinstance(metric('get_battery')['battery'], bool)
                assert isinstance(metric('get_net_interface'), list)
                assert isinstance(legacy('get_settings', key='framey.runtime-test', default=True)['data'], bool)
                report['result'] = 'discovery, native psutil import and read-only system metrics passed'
            else:
                assert case['probe'] == 'screenshots'
                assert legacy('was_rescued') is False
                assert legacy('aggregate_all', allapps=[]) == 0
                screenshots = home/'.local/share/Steam/userdata/9001/760/remote/4242/screenshots'
                screenshots.mkdir(parents=True)
                marker = b'Framey private screenshot fixture\n'
                (screenshots/'selected.jpg').write_bytes(marker)
                legacy('set_id_map_fronend', allapps=[[4242, 'Private Game']])
                assert legacy('copy_screenshot', app_id=4242,
                              url='https://localhost/selected.jpg') is True
                copied = home/'Pictures/Screenshots/Private Game/selected.jpg'
                assert copied.read_bytes() == marker
                assert (home/'Pictures/Screenshots/most_recent.jpg').read_bytes() == marker
                assert screenshots.stat().st_dev != copied.stat().st_dev, 'requires separate source/output filesystems'
                assert legacy('copy_screenshot', app_id=4242,
                              url='https://localhost/selected.jpg') is True
                (screenshots/'selected.jpg').write_bytes(b'changed private original')
                assert copied.read_bytes() == marker, 'destination must not share the source inode'
                assert legacy('copy_screenshot', app_id=4242,
                              url='https://localhost/selected.jpg') is False
                assert copied.read_bytes() == marker, 'conflicting output must survive'
                (screenshots/'selected.jpg').write_bytes(marker)
                legacy('set_id_map_fronend', allapps=[[4242, '../../escaped']])
                assert legacy('copy_screenshot', app_id=4242,
                              url='https://localhost/selected.jpg') is True
                assert not (home/'escaped/selected.jpg').exists()
                legacy('set_id_map_fronend', allapps=[[4242, 'Private Game']])
                external = home/'private-external.jpg'
                external.write_bytes(b'private external marker')
                linked = screenshots/'linked.jpg'
                linked.symlink_to(external)
                assert legacy('copy_screenshot', app_id=4242,
                              url='https://localhost/linked.jpg') is False
                assert external.read_bytes() == b'private external marker'
                linked.unlink()
                for app in ('*', '../*', True, -1):
                    assert legacy('copy_screenshot', app_id=app,
                                  url='https://localhost/selected.jpg') is False
                report['independentState'] = {'differentFilesystems':True, 'repeatCopy':True,
                    'sourceIndependent':True, 'titleConfined':True, 'symlinkRefused':True,
                    'conflictingOutputPreserved':True}
                (screenshots/'historical.jpg').write_bytes(b'Framey historical fixture\n')
                assert legacy('aggregate_all', allapps=[[4242, 'Private Game']]) == 1
                assert (copied.parent/'historical.jpg').read_bytes() == b'Framey historical fixture\n'
                assert legacy('was_rescued') is False
                import shotty_private
                report['shottyLifecycle'] = shotty_private.probe(backend, loader, env, log, processes,
                    legacy, rpc, until_ready, regression=args.reproduce_shotty_unload_regression)
                report['backendSha256'] = hashlib.sha256((plugin/'main.py').read_bytes()).hexdigest()
                report['shottyLifecycle']['unchangedPublishedFiles'] = {}
                with zipfile.ZipFile(io.BytesIO(data)) as original:
                    for item in original.infolist():
                        if item.is_dir() or item.filename == record['folder']+'/main.py':
                            continue
                        name = item.filename.split('/', 1)[1]
                        digest = hashlib.sha256(original.read(item)).hexdigest()
                        assert hashlib.sha256((plugin/name).read_bytes()).hexdigest() == digest
                        report['shottyLifecycle']['unchangedPublishedFiles'][name] = digest
                report['shottyLifecycle']['ipcAdapterSha256'] = (None if args.reproduce_shotty_unload_regression
                    else hashlib.sha256((plugin/'py_modules/framey_decky_ipc.py').read_bytes()).hexdigest())
                if args.reproduce_shotty_unload_regression:
                    report['expectedRegression'] = dict(success=False, phase='plugin unload',
                        previousManagedSourceRestored=True, forcedPluginKills=1,
                        qualifiedCompatibilityPass=False)
                report['result'] = ('discovery, backend import, empty aggregation, private screenshot '
                    'cross-filesystem copy, repeat copy, path/symlink refusals, preserved conflicting output and historical aggregation passed; '
                    + ('prior managed source requires forced plugin stop; expected negative only'
                       if args.reproduce_shotty_unload_regression else
                       'two parent-only clean loader stops and restart passed; no real Steam library or VR proof'))
            log.flush()
            log.seek(0)
            assert 'Starting Decky version v3.3.0' in log.read()


if __name__ == '__main__':
    main()
