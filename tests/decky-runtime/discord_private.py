"""Disposable Discord wire peer; never opens a real Discord socket or account."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import threading
import time


class Peer:
    """Frame constants and READY shape come from the pinned published backend."""
    def __init__(self, path):
        self.path = Path(path)
        self.condition = threading.Condition()
        self.connections = []
        self.workers = []
        self.stopping = threading.Event()
        self.reject_next = False

    def __enter__(self):
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(str(self.path))
        self.path.chmod(0o600)
        self.server.listen()
        self.server.settimeout(.1)
        self.acceptor = threading.Thread(target=self.accept, daemon=True)
        self.acceptor.start()
        return self

    def accept(self):
        while not self.stopping.is_set():
            try:
                client, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self.condition:
                record = dict(index=len(self.connections), frames=[], clientClosed=False,
                              fixtureClosed=False, error=None)
                self.connections.append(record)
                reject, self.reject_next = self.reject_next, False
            worker = threading.Thread(target=self.receive, args=(client, record, reject), daemon=True)
            self.workers.append((worker, client, record))
            worker.start()

    @staticmethod
    def exact(client, size):
        data = b''
        while len(data) < size:
            block = client.recv(size-len(data))
            if not block:
                if data:
                    raise ValueError('truncated private-peer frame')
                return None
            data += block
        return data

    def receive(self, client, record, reject):
        try:
            while not self.stopping.is_set():
                header = self.exact(client, 8)
                if header is None:
                    with self.condition:
                        record['clientClosed'] = not record['fixtureClosed']
                        self.condition.notify_all()
                    return
                op, size = struct.unpack('<ii', header)
                if not 0 <= size <= 65536:
                    raise ValueError('invalid private-peer frame size')
                raw = self.exact(client, size)
                payload = json.loads(raw)
                with self.condition:
                    record['frames'].append(dict(op=op, payload=payload,
                        wireHex=(header+raw).hex(), payloadSha256=hashlib.sha256(raw).hexdigest()))
                    self.condition.notify_all()
                if op == 0:
                    reply = json.dumps(dict(cmd='DISPATCH', evt='ERROR' if reject else 'READY')).encode()
                    client.sendall(struct.pack('<ii', 1, len(reply))+reply)
        except (OSError, ValueError) as error:
            with self.condition:
                if not record['fixtureClosed']:
                    record['error'] = repr(error)
                self.condition.notify_all()
        finally:
            client.close()

    def wait(self, predicate, message):
        with self.condition:
            if not self.condition.wait_for(lambda: predicate(self.connections), timeout=3):
                raise AssertionError(message+': '+repr(self.connections))
            return json.loads(json.dumps(self.connections))

    def closed(self, index):
        rows = self.wait(lambda rows: len(rows)>index and rows[index]['clientClosed'],
                         'private Discord peer did not receive client EOF')
        return rows[index]

    def __exit__(self, *_):
        self.stopping.set()
        self.server.close()
        self.acceptor.join(timeout=2)
        for worker, client, record in self.workers:
            if worker.is_alive():
                record['fixtureClosed'] = True
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            worker.join(timeout=2)
            assert not worker.is_alive(), 'owned private-peer worker survived cleanup'
        assert not self.acceptor.is_alive(), 'owned private-peer acceptor survived cleanup'
        self.path.unlink()


def stop(backend, log, *, disconnect):
    from free_loader_private import descendants, identity
    children = descendants(backend.pid)
    assert children, 'private loader must own its plugin children'
    before = Path(log.name).read_text()
    peers = []
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
                peers.append(str(path))
        assert len(peers) == 1, peers
        time.sleep(.05)
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
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
    console = Path(log.name).read_text()[len(before):]
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [text for text in ('Error during shutdown:', 'Task was destroyed but it is pending',
              'Bad file descriptor', 'was never awaited') if text in console]
    clean = (backend.returncode == 0 and not remaining and not forced and not errors
             and all(c['returncode'] == 0 for c in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin Discord Status (v1.5.0) has been stopped in ' in console)
    result = dict(loaderPid=backend.pid, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted,
        loaderReturncode=backend.returncode, parentOnlySignal=True,
        fixtureClosedUnixPeers=peers, forcedPluginKills=forced, errors=errors,
        seconds=round(time.monotonic()-started, 3), console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(), cleanShutdownVerified=clean)
    assert clean and result['seconds'] < 5, result
    return result


def probe(peer, backend, loader, env, log, processes, current, rpc, until_ready, report, plugin):
    def activity(name, **extra):
        return dict(imageUrl='https://example.invalid/private.png', startTime=1700000000,
                    details=dict(name=name), **extra)

    def closed(index, ops):
        row = peer.closed(index)
        assert not row['fixtureClosed'] and row['error'] is None, row
        assert [f['op'] for f in row['frames']] == ops, row
        assert row['frames'][-1]['payload'] == {}, row
        return row

    evidence = dict(stops=[], realDiscordContacted=False, realFrameContacted=False,
                    physicalControllerVerified=False, cleanShutdownVerified=False)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(100)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        assert current('clear_activity') is False
        assert current('disconnect') is None
        assert current('is_connected') is True
        assert current('update_activity', activity('First private game')) is True
        assert current('update_activity', activity('Second private game', discordId='424242424242424242')) is True
        first = closed(0, [0, 1, 2])
        assert first['frames'][0]['payload'] == dict(v=1, client_id='1055680235682672682')
        first_activity = first['frames'][1]['payload']
        assert first_activity['cmd'] == 'SET_ACTIVITY'
        assert first_activity['args']['activity']['details'] == 'Playing First private game'
        assert first_activity['args']['activity']['timestamps'] == dict(start=1700000000)
        assert first_activity['args']['activity']['assets']['large_image'] == 'https://example.invalid/private.png'
        assert current('clear_activity') is True
        second = closed(1, [0, 1, 1, 2])
        assert second['frames'][0]['payload'] == dict(v=1, client_id='424242424242424242')
        assert 'details' not in second['frames'][1]['payload']['args']['activity']
        assert second['frames'][2]['payload']['args'] == dict(pid=first_activity['args']['pid'])
        assert current('clear_activity') is False
        peer.reject_next = True
        assert current('update_activity', activity('Rejected private game')) is False
        closed(2, [0, 2])
        assert current('update_activity', activity('Private unload activity')) is True
        evidence['stops'].append(stop(backend, log, disconnect=True))
        closed(3, [0, 1, 2])
        assert unrelated.poll() is None
        backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                   start_new_session=True)
        processes.append(backend)
        found = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Discord Status discovery')
        assert found == report['discovered'], found
        evidence['restartedDiscovery'] = found
        assert current('clear_activity') is False
        assert current('is_connected') is True
        assert current('update_activity', activity('Private restart activity')) is True
        assert current('disconnect') is None
        closed(4, [0, 1, 2])
        assert current('update_activity', activity('Second private unload')) is True
        evidence['stops'].append(stop(backend, log, disconnect=False))
        closed(5, [0, 1, 2])
        evidence['connections'] = json.loads(json.dumps(peer.connections))
        evidence['unrelatedSiblingPreserved'] = unrelated.poll() is None
        evidence['cleanShutdownVerified'] = True
        evidence['backendSha256'] = hashlib.sha256((plugin/'main.py').read_bytes()).hexdigest()
        evidence['ipcAdapterSha256'] = hashlib.sha256((plugin/'py_modules/framey_decky_ipc.py').read_bytes()).hexdigest()
        evidence['lifecycleAdapterSha256'] = hashlib.sha256((plugin/'py_modules/framey_discord_lifecycle.py').read_bytes()).hexdigest()
        return evidence
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        unrelated.wait(timeout=3)
