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

import websockets
from websockets.exceptions import WebSocketException

ROOT = Path('/repo')
sys.path[:0] = [str(ROOT/'ui'), str(ROOT/'tests')]
import frame_decky_store
from framey_official import PLUGINS, archive


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
    parser.add_argument('--reproduce-bound-method-regression', action='store_true')
    parser.add_argument('--reproduce-fileserver-empty-flag-regression', action='store_true')
    parser.add_argument('--reproduce-timer-regression', action='store_true')
    args = parser.parse_args()
    assert os.getuid() == 1100 and ROOT.is_dir(), 'Run through framey-test-decky-runtime.py'
    record = next(p for p in PLUGINS if p['id'] == args.id)
    case = next(p for p in json.loads((ROOT/'tests/decky-runtime/cases.json').read_text()) if p['id'] == args.id)
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
    receipt = json.loads((plugin/'.frame-control-store.json').read_text())
    if not args.reproduce_timer_regression:
        expected_shims = ([case['shim']] if case['shim'] else []) + case.get('additionalShims', [])
        assert receipt.get('compatShims', []) == expected_shims, receipt
    else:
        assert record['id'] == 96
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            (plugin/'main.py').write_bytes(original.read(record['folder']+'/main.py'))
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
        try:
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
                report['calls'].append({'method': method, 'result': response['result']})
                return response['result']

            def current(method, *values):
                response = rpc('loader/call_plugin_method', record['name'], method, *values)
                report['calls'].append({'method': method, 'result': response})
                return response

            if case['probe'] == 'steam-status-readonly':
                # Only read private defaults. The public CM-list and 100 MB
                # download diagnostics must never run in this runtime probe.
                source = (plugin/'main.py').read_text()
                assert source.count('ssl.create_default_context()') == 2
                assert 'ssl.CERT_NONE' not in source and 'ssl_context.check_hostname = False' not in source
                settings = current('get_settings')
                assert isinstance(settings, dict) and settings['refresh_interval_seconds'] == 120, settings
                report['result'] = ('published Decky discovery and private settings read passed; '
                                    'both managed public diagnostic contexts retain TLS verification; '
                                    'no public network diagnostics, Frame or VR test')
            elif case['probe'] == 'wine-cellar-private-state':
                helper = plugin/'bin/backend'
                machine = 183 if __import__('platform').machine() == 'aarch64' else 62
                assert helper.read_bytes()[:4] == b'\x7fELF'
                assert int.from_bytes(helper.read_bytes()[18:20], 'little') == machine
                token = until_ready(lambda: current('framey_ws_open'), 'private Wine Cellar helper')
                assert isinstance(token, str) and len(token) == 32, token
                assert current('framey_ws_send', token, '{"type":"GetState"}') is None
                reply = until_ready(lambda: next((json.loads(message) for message in
                    current('framey_ws_poll', token)['messages'] if json.loads(message).get('type') == 'UpdateState'),
                    None), 'read-only Wine Cellar state')
                assert reply['app_state']['installed_tools'] == [], reply
                assert current('framey_ws_close', token) is None
                report['result'] = ('actual Decky 3.3.0 discovery, managed native helper and fixed-origin '
                                    'read-only state RPC passed against private empty Steam home; '
                                    'no install/uninstall, real library or VR test')
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
                os.killpg(backend.pid, signal.SIGTERM)
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
                report['result'] = 'discovery, Frame-shaped private battery samples, history and per-app power passed; real managed Frame backend unverified'
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
                os.killpg(backend.pid, signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert until_ready(lambda: current('settings_read')['larger_text'],
                                   'private Free Loader setting after restart') is True
                assert current('read_deals') == {}
                report['result'] = ('discovery, default settings, empty local deals, '
                    'private setting write/read and restart persistence passed; feed, notifications and VR unverified')
            elif case['probe'] == 'game-sync-config':
                # Exercise only private settings. This plugin also exposes
                # rclone cloud sync and arbitrary process signals; neither
                # belongs in a passive compatibility probe.
                settings = current('get_config')
                assert settings['sync_on_game_start'] is False, settings
                assert settings['sync_on_game_stop'] is False, settings
                assert settings['capture_upload'] is False, settings
                assert settings['advanced_mode'] is False, settings
                assert current('set_config', 'advanced_mode', True) is None
                assert current('get_config')['advanced_mode'] is True
                os.killpg(backend.pid, signal.SIGTERM)
                backend.wait(timeout=8)
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                until_ready(lambda: rpc('loader/get_plugins'), 'restarted Decky discovery')
                assert until_ready(lambda: current('get_config')['advanced_mode'],
                                   'private Game Sync setting after restart') is True
                report['result'] = ('discovery, default config and private setting restart persistence passed; '
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
                os.killpg(backend.pid, signal.SIGTERM)
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
                os.killpg(backend.pid, signal.SIGTERM)
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
                os.killpg(backend.pid, signal.SIGTERM)
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
                    os.killpg(backend.pid, signal.SIGTERM)
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
                (screenshots/'historical.jpg').write_bytes(b'Framey historical fixture\n')
                assert legacy('aggregate_all', allapps=[[4242, 'Private Game']]) == 1
                assert (copied.parent/'historical.jpg').read_bytes() == b'Framey historical fixture\n'
                assert legacy('was_rescued') is False
                report['result'] = ('discovery, backend import, empty aggregation, private screenshot '
                                    'copy and historical aggregation passed')
            log.flush()
            log.seek(0)
            assert 'Starting Decky version v3.3.0' in log.read()
            print(json.dumps(report))
        except Exception:
            log.flush()
            log.seek(0)
            print(log.read()[-12000:], file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        continue
                    try:
                        process.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait(timeout=4)


if __name__ == '__main__':
    main()
