"""Synthetic PlayTime sessions through the published loader; no Steam session."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
import zipfile


def exercise(call, plugin, archive, record, base, backend, loader, env, log,
             processes, until_ready, rpc):
    # Preserve every official archive member, not just the backend entrypoint.
    hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as original:
        for item in original.infolist():
            if item.is_dir():
                continue
            relative = item.filename.split('/', 1)[1]
            data = (plugin/relative).read_bytes()
            assert data == original.read(item)
            if relative.endswith('.py'):
                hashes[relative] = hashlib.sha256(data).hexdigest()

    runtime = base/'data'/record['folder']
    users = ['76561198000000001', '76561198000000002']
    game = '424242'
    paths = {user: runtime/'users'/user/'storage.db' for user in users}
    snapshots, stops = [], []

    def rows(user):
        with sqlite3.connect(paths[user].as_uri()+'?mode=ro', uri=True) as db:
            return {table: db.execute(query).fetchall() for table, query in {
                'games': 'SELECT game_id,name FROM game_dict ORDER BY game_id',
                'sessions': 'SELECT game_id,duration FROM play_time ORDER BY rowid',
                'totals': 'SELECT game_id,duration FROM overall_time ORDER BY game_id',
                'tracking': 'SELECT game_id,status FROM game_tracking_status ORDER BY game_id',
            }.items()}

    def observe(user, duration, name, paused=False):
        actual = rows(user)
        assert actual == {'games': [(game, name)], 'sessions': [(game, duration)],
                          'totals': [(game, duration)],
                          'tracking': [(game, 'pause')] if paused else []}, actual
        snapshots.append({'user': user, 'rows': actual})

    def stop(process):
        # Signal only this parent, then require its descendants to leave without
        # the fixture's group cleanup hiding an unload stall.
        tree = {}
        for entry in Path('/proc').glob('[0-9]*'):
            try:
                fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
                tree[int(entry.name)] = (int(fields[1]), fields[19])
            except (FileNotFoundError, ProcessLookupError):
                continue
        owned = {process.pid}
        while True:
            children = {pid for pid, (parent, _) in tree.items() if parent in owned}
            if children <= owned:
                break
            owned.update(children)
        assert len(owned) >= 2
        started = time.monotonic()
        os.kill(process.pid, signal.SIGTERM)
        assert process.wait(timeout=8) == 0
        def reaped():
            for pid in owned:
                try:
                    current = Path('/proc')/str(pid)/'stat'
                    if current.read_text().rsplit(')', 1)[1].split()[19] == tree[pid][1]:
                        return False
                except (FileNotFoundError, ProcessLookupError):
                    pass
            return True
        until_ready(reaped, 'owned PlayTime loader descendants reaped')
        stops.append({'returncode': 0, 'elapsedSeconds': time.monotonic()-started,
                      'parentOnlySignal': True, 'ownedProcessCount': len(owned),
                      'ownedProcessIdentitiesReaped': True})

    assert call('has_min_required_python_version') is True
    assert call('get_current_user') is None
    assert call('set_current_user', users[0]) is None
    assert call('get_current_user') == users[0]
    assert call('fetch_playtime_information') == []
    assert call('add_time', dict(started_at=1706788800, ended_at=1706789100,
                                game_id=game, game_name='Private Alice game')) is None
    alice = call('get_game', game)
    assert alice['game'] == {'id': game, 'name': 'Private Alice game'}
    assert alice['totalTime'] == 300
    observe(users[0], 300, 'Private Alice game')
    assert call('set_game_tracking_status', {'game_id': game, 'status': 'pause'}) is True
    assert call('add_time', dict(started_at=1706789200, ended_at=1706789800,
                                game_id=game, game_name='Private Alice game')) is None
    observe(users[0], 300, 'Private Alice game', paused=True)
    assert call('remove_game_tracking_status', game) is True
    assert call('set_current_user', users[1]) is None
    assert call('fetch_playtime_information') == []
    assert call('get_game', game) is None
    assert call('add_time', dict(started_at=1706788800, ended_at=1706789400,
                                game_id=game, game_name='Private Bob game')) is None
    bob = call('get_game', game)
    assert bob['game'] == {'id': game, 'name': 'Private Bob game'}
    assert bob['totalTime'] == 600
    observe(users[1], 600, 'Private Bob game')
    observe(users[0], 300, 'Private Alice game')
    assert call('set_current_user', users[0]) is None
    assert call('get_game', game) == alice
    stop(backend)
    restarted = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                 start_new_session=True)
    processes.append(restarted)
    found = until_ready(lambda: rpc('loader/get_plugins'), 'restarted PlayTime discovery')
    assert len(found) == 1 and found[0]['name'] == record['name'] and not found[0]['disabled']
    assert call('get_current_user') is None
    for user, expected, name, duration in [(users[0], alice, 'Private Alice game', 300),
                                            (users[1], bob, 'Private Bob game', 600)]:
        assert call('set_current_user', user) is None
        assert call('get_game', game) == expected
        observe(user, duration, name)
    stop(restarted)
    databases = {}
    for user, path in paths.items():
        assert not path.with_name(path.name+'-wal').exists()
        payload = path.read_bytes()
        databases[user] = {'sha256': hashlib.sha256(payload).hexdigest(),
                           'base64': base64.b64encode(payload).decode()}
    assert not (runtime/'storage.db').exists(), 'the fixture must not create a legacy database'
    log.flush()
    log.seek(0)
    console = log.read()
    assert console.count('Starting Decky version v3.3.0') == 2
    assert console.count('[main][INFO]: Shutdown finished.') == 2
    for marker in ['Error during shutdown:', 'Task was destroyed but it is pending',
                   'asyncio.exceptions.CancelledError', 'Bad file descriptor']:
        assert marker not in console, marker
    return {'publishedArchiveMembersUnmodified': True, 'backendSourceSha256': hashes,
            'sessionReadbacks': snapshots, 'finalDatabases': databases, 'ownedLoaderStops': stops,
            'loaderConsole': console, 'loaderConsoleSha256': hashlib.sha256(console.encode()).hexdigest(),
            'privateSessionRpcVerified': True, 'perUserIsolationVerified': True,
            'pauseSkipsSessionVerified': True, 'restartPersistenceVerified': True,
            'automaticRecordingVerified': False, 'realSteamLibraryVerified': False,
            'browserVerified': False, 'realFrameContacted': False,
            'physicalControllerVerified': False}
