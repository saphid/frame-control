"""Container-only real Decky backend discovery and smoke tests; no host services."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import ssl
import subprocess
import sys
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

            if case['probe'] == 'battery-tracker':
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
