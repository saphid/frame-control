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
        capture_output=True, text=True, env=env, timeout=15)
    assert install.returncode == 0, install.stderr
    plugin = base/'plugins'/record['folder']
    receipt = json.loads((plugin/'.frame-control-store.json').read_text())
    assert receipt['compatShims'] == [case['shim']], receipt
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

            if case['probe'] == 'fileserver':
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
            else:
                assert case['probe'] == 'screenshots'
                assert legacy('was_rescued') is False
                assert legacy('aggregate_all', allapps=[]) == 0
                report['result'] = 'discovery, backend import and empty screenshot aggregation passed'
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
