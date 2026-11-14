"""Prove only this disposable Battery Tracker loader flushes before exiting."""
import base64
import hashlib
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import time


def identity(pid):
    try:
        fields = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()
        return dict(state=fields[0], parent=int(fields[1]), start=fields[19])
    except FileNotFoundError:
        return None


def descendants(parent):
    states = {int(p.name): state for p in Path('/proc').iterdir() if p.name.isdigit()
              if (state := identity(int(p.name)))}
    owned = {parent}
    while True:
        added = {pid for pid, state in states.items() if state['parent'] in owned} - owned
        if not added:
            return {pid: states[pid] for pid in owned - {parent}}
        owned.update(added)


def rows(database):
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as db:
        return [list(row) for row in db.execute(
            'SELECT capacity,status,power,app FROM battery ORDER BY rowid')]


def stop(backend, log, database, *, regression, disconnect, previous_rows=()):
    children = descendants(backend.pid)
    assert children, 'the private loader must own its children'
    before_rows = rows(database)
    assert before_rows == list(previous_rows), 'new samples must still be pending before this stop'
    before = Path(log.name).read_text()
    closed_peers = []
    if disconnect:
        for path in Path('/tmp').glob('plugin_socket_*'):
            assert path.is_socket() and path.stat().st_uid == os.getuid()
            with socket.socket(socket.AF_UNIX) as peer:
                peer.settimeout(.2)
                try:
                    peer.connect(str(path))
                except ConnectionRefusedError:
                    continue
                peer.shutdown(socket.SHUT_WR)
                closed_peers.append(str(path))
        assert len(closed_peers) == 1, closed_peers
        time.sleep(.05)
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    console = Path(log.name).read_text()[len(before):]
    # The fixture is container PID1. Reap only recorded adopted descendants;
    # never signal the plugin or its process group to manufacture a clean stop.
    adopted = []
    deadline = time.monotonic()+2
    while True:
        for pid, old in children.items():
            state = identity(pid)
            if state and state['start'] == old['start']:
                try:
                    child, status = os.waitpid(pid, os.WNOHANG)
                    if child:
                        adopted.append(dict(pid=child, returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:
                    pass
        remaining = {pid: state for pid, old in children.items()
                     if (state := identity(pid)) and state['start'] == old['start']}
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(.01)
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [marker for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if marker in console]
    after_rows = rows(database)
    clean = (backend.returncode == 0 and not remaining and not forced and not errors
             and all(child['returncode'] == 0 for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin Battery Tracker (v0.2.0) has been stopped in ' in console)
    observation = dict(loaderPid=backend.pid, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted, parentOnlySignal=True,
        loaderReturncode=backend.returncode, seconds=round(time.monotonic()-started, 3),
        fixtureClosedUnixPeers=closed_peers, forcedPluginKills=forced, errors=errors,
        rowsBefore=before_rows, rowsAfter=after_rows, console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean, expectedRegression=regression)
    if regression:
        assert not clean and forced == 1 and backend.returncode == 0 and not after_rows, observation
    else:
        assert clean and observation['seconds'] < 5 and after_rows, observation
        assert all(row[0] == 89 and row[2] > 0 for row in after_rows), observation
    return observation


def probe(backend, loader, env, log, processes, legacy, rpc, until_ready, history, *, regression):
    databases = list(Path.home().rglob('battery.db'))
    assert len(databases) == 1, databases
    database = databases[0]
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(40)'],
                                 start_new_session=True)
    processes.append(unrelated)
    stops = []
    try:
        stops.append(stop(backend, log, database, regression=regression, disconnect=True))
        assert unrelated.poll() is None, 'an unrelated sibling must survive'
        if not regression:
            assert len(stops[0]['rowsAfter']) >= len(history['cap']) >= 2
            assert any(row[1] == -1 and row[3] == 'Framey private' for row in stops[0]['rowsAfter'])
            saved = stops[0]['rowsAfter']
            backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                       start_new_session=True)
            processes.append(backend)
            until_ready(lambda: rpc('loader/get_plugins'), 'restarted Battery Tracker discovery')
            restored = legacy('get_recent_data', lookback=2)
            assert len(restored['cap']) >= len(saved) and restored['cap'][:len(saved)] == [.89]*len(saved)
            until_ready(lambda: len(legacy('get_recent_data', lookback=2)['cap']) > len(saved),
                        'replacement pending battery sample')
            stops.append(stop(backend, log, database, regression=False,
                              disconnect=False, previous_rows=saved))
            assert len(stops[1]['rowsAfter']) > len(saved)
            assert unrelated.poll() is None
        raw = database.read_bytes()
        log.flush()
        console = Path(log.name).read_text()
        return dict(stops=stops, unrelatedSiblingPreserved=True,
            databaseBase64=base64.b64encode(raw).decode(), databaseSha256=hashlib.sha256(raw).hexdigest(),
            console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
            cleanShutdownVerified=not regression, expectedRegression=regression,
            realFrameContacted=False, physicalControllerVerified=False)
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        unrelated.wait(timeout=3)
