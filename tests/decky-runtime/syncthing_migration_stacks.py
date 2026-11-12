"""Opt-in guest-root observation of the disposable migration Decky service."""

import hashlib
import http.client
import json
import os
from pathlib import Path
import selectors
import subprocess
import threading
import time

UNIT = 'frame-control-migration-decky-fixture.service'
GROUP = '/user.slice/user-1100.slice/user@1100.service/app.slice/' + UNIT
WINDOWS = (10, 30, 60)
MAX_PIDS = 8
DUMP_SECONDS = 2
OUTPUT_LIMITS = (16384, 4096)

# This helper has tester credentials and only reads the four properties used
# by the root observer. Keep one bus connection instead of starting systemctl
# for every sample, which still exceeded three seconds under ARM64 QEMU.
UNIT_QUERY = r'''
import dbus, json, os, sys
assert os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1100
assert not os.getgroups()
bus = dbus.bus.BusConnection(os.environ['DBUS_SESSION_BUS_ADDRESS'])
manager = dbus.Interface(bus.get_object('org.freedesktop.systemd1',
    '/org/freedesktop/systemd1', introspect=False), 'org.freedesktop.systemd1.Manager')
print(json.dumps({'ready': True}), flush=True)
for request in sys.stdin:
    if request != 'query\n':
        raise ValueError('Unexpected observer request')
    try:
        path = manager.GetUnit('frame-control-migration-decky-fixture.service', timeout=2)
        properties = dbus.Interface(bus.get_object('org.freedesktop.systemd1', path,
            introspect=False), 'org.freedesktop.DBus.Properties')
        unit = properties.GetAll('org.freedesktop.systemd1.Unit', timeout=2)
        service = properties.GetAll('org.freedesktop.systemd1.Service', timeout=2)
        budget = int(service['TimeoutStopUSec'])
        reply = dict(MainPID=str(int(service['MainPID'])),
                     ControlGroup=str(service['ControlGroup']), ActiveState=str(unit['ActiveState']),
                     TimeoutStopUSec='1min 30s' if budget == 90000000 else str(budget))
    except dbus.DBusException as error:
        reply = ({} if error.get_dbus_name() in ('org.freedesktop.systemd1.NoSuchUnit',
                                                'org.freedesktop.DBus.Error.UnknownObject')
                 else {'error': error.get_dbus_name()[:256]})
    print(json.dumps(reply), flush=True)
'''


class UnitQuery:
    """Own one bounded, read-only user-bus helper and reap it on every exit."""

    def __init__(self, user_command, *, executable='python3', helper=UNIT_QUERY):
        self.command = user_command + [executable, '-u', '-c', helper]
        self.process = None

    def read(self, timeout):
        deadline = time.monotonic() + timeout
        data = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise TimeoutError('Migration unit query deadline exceeded')
                chunk = os.read(self.process.stdout.fileno(), 4097 - len(data))
                if not chunk:
                    raise RuntimeError('Migration unit query helper exited')
                data.extend(chunk)
                if len(data) > 4096:
                    raise ValueError('Oversized migration unit query reply')
                if b'\n' in data:
                    line, extra = data.split(b'\n', 1)
                    if extra:
                        raise ValueError('Unexpected extra unit query reply')
                    result = json.loads(line)
                    if not isinstance(result, dict):
                        raise ValueError('Invalid migration unit query reply')
                    return result

    def start(self):
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            # Import and connect before starting the actual migration probe.
            if self.read(15) != {'ready': True}:
                raise ValueError('Migration unit query helper not ready')
        except BaseException:
            self.close()
            raise

    def query(self):
        try:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError('Migration unit query helper unavailable')
            self.process.stdin.write(b'query\n')
            self.process.stdin.flush()
            result = self.read(3)
            if set(result) == {'error'}:
                raise RuntimeError('Migration unit bus error: ' + str(result['error'])[:256])
            required = {'MainPID', 'ControlGroup', 'ActiveState', 'TimeoutStopUSec'}
            if result and (set(result) != required or
                           any(not isinstance(value, str) for value in result.values())):
                raise ValueError('Unexpected migration unit properties')
            return result
        except BaseException:
            # Never consume a stale reply after a timed-out request.
            self.close()
            raise

    def close(self):
        if self.process is None:
            return
        try:
            try:
                self.process.stdin.close()
            except BrokenPipeError:
                pass
            finally:
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
        finally:
            self.process.stdout.close()


def identity(pid, group=GROUP, proc=Path('/proc')):
    """Reject another user, another cgroup, or a reused process identity."""
    if type(pid) is not int or pid <= 1 or group != GROUP:
        raise ValueError('Not an owned migration process')
    base = proc / str(pid)
    stat = (base / 'stat').read_text()
    fields = stat.rsplit(')', 1)[1].split()
    uids = next(line for line in (base / 'status').read_text().splitlines()
                if line.startswith('Uid:')).split()[1:]
    if (stat.split(' ', 1)[0] != str(pid) or uids != ['1100'] * 4
            or '0::' + group not in (base / 'cgroup').read_text().splitlines()):
        raise ValueError('Migration process UID/cgroup mismatch')
    start = int(fields[19])
    if start <= 0:
        raise ValueError('Invalid process start ticks')
    return dict(pid=pid, startTicks=start, parentPid=int(fields[1]), uid=1100,
                controlGroup=group)


def bounded_dump(sampler, pid):
    """Drain both pipes with hard output/time bounds; reap our sampler only."""
    output = [bytearray(), bytearray()]
    timed_out = truncated = False
    process = subprocess.Popen([str(sampler), 'dump', '--pid', str(pid), '--nonblocking'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + DUMP_SECONDS
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate((process.stdout, process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, index)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    data = os.read(key.fileobj.fileno(), 4096)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    target = output[key.data]
                    room = OUTPUT_LIMITS[key.data] - len(target)
                    target.extend(data[:room])
                    if len(data) > room:
                        truncated = True
                        break
                if truncated:
                    break
        if timed_out or truncated:
            process.kill()
        process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait(timeout=2)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        process.stdout.close()
        process.stderr.close()
    result = dict(returncode=process.returncode, timedOut=timed_out,
                  outputTruncated=truncated)
    for name, data in zip(('stdout', 'stderr'), output):
        result[name] = bytes(data).decode('utf-8', errors='replace')
        result[name + 'Sha256'] = hashlib.sha256(result[name].encode()).hexdigest()
    return result


def sample_group(properties, sampler, *, proc=Path('/proc'),
                 cgroups=Path('/sys/fs/cgroup'), dump=bounded_dump, cancelled=lambda: False):
    group = properties['ControlGroup']
    if group != GROUP or properties['TimeoutStopUSec'] != '1min 30s':
        raise ValueError('Unexpected migration cgroup or stop budget')
    pids = sorted({int(value) for value in (cgroups / GROUP.lstrip('/') / 'cgroup.procs')
                   .read_text().split()})
    if int(properties['MainPID']) not in pids:
        raise ValueError('Migration main process is not in its cgroup')
    snapshot = dict(controlGroup=group, processes=[], processesTruncated=len(pids) > MAX_PIDS)
    for pid in pids[:MAX_PIDS]:
        if cancelled():
            snapshot['cancelled'] = True
            break
        entry = dict(pid=pid)
        snapshot['processes'].append(entry)
        try:
            before = identity(pid, group, proc)
            sample = dump(sampler, pid)
            after = identity(pid, group, proc)
            if before != after:
                raise ValueError('Process identity changed during sample')
            entry.update(identity=before, identityUnchanged=True, **sample)
        except (OSError, ValueError, IndexError, StopIteration) as error:
            # Do not retain stack text that cannot be bound to the same UID,
            # cgroup and start ticks on both sides of the sampling operation.
            entry.update(error=type(error).__name__ + ': ' + str(error),
                         identityUnchanged=False, sampleOutputDiscarded=True)
    return snapshot


class Observer:
    """Run beside the real unprivileged probe; never stop or signal Decky."""

    def __init__(self, sampler, metadata, user_command, *, query=None, capture=None):
        self.sampler = sampler
        self.user_command = user_command
        self.transport = UnitQuery(user_command) if query is None else None
        self.query = query or self.properties
        self.capture = capture or (lambda properties: sample_group(
            properties, sampler, cancelled=self.stop.is_set))
        self.stop = threading.Event()
        self.thread = None
        self.report = dict(sampler=metadata, unit=UNIT, snapshots=[],
                           errors=[], deactivationTimeBasis='first observed deactivating state',
                           changesStopBudget=False, historicalCauseEstablished=False)
        self.baseline = False
        self.deactivating_at = None
        self.captured_windows = set()

    def properties(self):
        properties = self.transport.query()
        # Type=exec becomes active before the published bootloader has started
        # Python. HEAD waits for its actual HTTP server without reading a token.
        if not self.baseline and properties.get('ActiveState') == 'active':
            connection = http.client.HTTPConnection('127.0.0.1', 1337, timeout=0.5)
            try:
                connection.request('HEAD', '/auth/token')
                properties['PythonReady'] = connection.getresponse().status == 200
            except (OSError, http.client.HTTPException):
                properties['PythonReady'] = False
            finally:
                connection.close()
        return properties

    def tick(self, properties, now):
        state = properties.get('ActiveState')
        if state not in ('active', 'deactivating'):
            return
        if state == 'deactivating' and self.deactivating_at is None:
            self.deactivating_at = now
        if not self.baseline:
            # A late observer is reported honestly; a stop-time sample cannot
            # silently substitute for the required running-service baseline.
            if state != 'active' or properties.get('PythonReady') is not True:
                return
            window = 'baseline'
            self.baseline = True
        elif state == 'deactivating':
            due = [value for value in WINDOWS if value not in self.captured_windows
                   and now - self.deactivating_at >= value]
            if not due:
                return
            window = due[0]
            self.captured_windows.add(window)
        else:
            return
        snapshot = dict(window=window, observedMonotonic=now, activeState=state,
                        pythonServerReady=properties.get('PythonReady') is True)
        if self.deactivating_at is not None:
            snapshot['observedDeactivationSeconds'] = round(now - self.deactivating_at, 3)
        self.report['snapshots'].append(snapshot)
        try:
            snapshot.update(self.capture(properties))
        except Exception as error:
            snapshot['error'] = type(error).__name__ + ': ' + str(error)

    def run(self):
        while not self.stop.is_set():
            try:
                self.tick(self.query(), time.monotonic())
            except Exception as error:
                if len(self.report['errors']) < 8:
                    self.report['errors'].append(type(error).__name__ + ': ' + str(error))
            self.stop.wait(0.2)

    def __enter__(self):
        if self.transport is not None:
            self.transport.start()
        self.thread = threading.Thread(target=self.run, name='migration-stack-observer')
        try:
            self.thread.start()
        except BaseException:
            if self.transport is not None:
                self.transport.close()
            raise
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=8)
        if self.transport is not None:
            self.transport.close()
        self.report['queryHelperJoined'] = (self.transport is None or
                                           self.transport.process.poll() is not None)
        self.report['observerJoined'] = not self.thread.is_alive()
        if self.thread.is_alive():
            raise RuntimeError('Migration stack observer did not stop')


def guest_observer(metadata):
    """Only the marked systemd guest root can install and launch the sampler."""
    if (os.getuid() != 0 or os.getpid() == 1
            or Path('/framey-owned-vm').read_text() != 'Frame Control Flatpak VM v1\n'
            or Path('/proc/1/comm').read_text().strip() != 'systemd'):
        raise RuntimeError('Migration stack observer requires the private systemd guest')
    data = Path('/input/migration-py-spy').read_bytes()
    if (metadata['architecture'] != os.uname().machine
            or hashlib.sha256(data).hexdigest() != metadata['executableSha256']
            or hashlib.sha256(Path('/input/PluginLoader').read_bytes()).hexdigest()
            != metadata['loaderSha256']
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != metadata['observerSha256']):
        raise ValueError('Migration sampler/loader provenance mismatch')
    sampler = Path('/run/framey-migration-py-spy')
    with sampler.open('xb') as stream:
        stream.write(data)
    sampler.chmod(0o700)
    # Drop credentials once for the persistent read-only user-bus helper.
    query_user = ['setpriv', '--reuid=1100', '--regid=1100', '--clear-groups', '--',
                  'env', 'XDG_RUNTIME_DIR=/run/user/1100',
                  'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus']
    return Observer(sampler, metadata, query_user)
