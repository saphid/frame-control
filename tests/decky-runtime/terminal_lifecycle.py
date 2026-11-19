"""Fixed commands in a disposable native container; never a host/user terminal."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from timer_lifecycle import Client


def startup_processes(parent_pid, *, proc_root=Path('/proc')):
    """Bounded identity/CPU observations; no commands, environments or task input."""
    import os as proc_os
    from itertools import islice
    report = dict(observedMonotonicNs=time.monotonic_ns(), parentPid=parent_pid,
                  processes=[], truncated=False)
    try:
        report['clockTicksPerSecond'] = proc_os.sysconf('SC_CLK_TCK')
    except (AttributeError, OSError, ValueError) as error:
        report['clockTicksUnavailable'] = type(error).__name__
    def read(directory, name):
        with (directory/name).open('rb') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError('bounded procfs record exceeded')
        return raw.decode('ascii')
    def identity(pid):
        directory = proc_root/str(pid)
        fields = read(directory, 'stat').rsplit(')', 1)[1].split()
        return dict(pid=pid, uid=directory.stat().st_uid, state=fields[0],
                    ppid=int(fields[1]), userTicks=int(fields[11]),
                    systemTicks=int(fields[12]), threadCount=int(fields[17]),
                    startTicks=int(fields[19]))
    try:
        parent = identity(parent_pid)
        queue = [(parent_pid, None)]
        visited = set()
        while queue and len(visited) < 16:
            pid, expected_parent = queue.pop(0)
            if pid in visited:
                continue
            visited.add(pid)
            try:
                before = identity(pid)
                if pid == parent_pid and before['startTicks'] != parent['startTicks']:
                    report['identityChanged'] = True
                    continue
                if before['uid'] != parent['uid'] or (expected_parent is not None and
                        before['ppid'] != expected_parent):
                    continue
                directory = proc_root/str(pid)
                with proc_os.scandir(directory/'task') as tasks:
                    entries = list(islice(tasks, 17))
                tids = sorted({int(task.name) for task in entries
                               if task.name.isascii() and task.name.isdecimal()})
                # The process leader need not be the thread that forked a child.
                tids = [pid] + [tid for tid in tids if tid != pid]
                threads_truncated = len(tids) > 16 or len(entries) > 16
                report['truncated'] |= threads_truncated
                children = []
                unavailable_tasks = []
                for tid in tids[:16]:
                    try:
                        children.extend(read(directory, 'task/'+str(tid)+'/children').split())
                    except (OSError, ValueError, UnicodeError) as error:
                        unavailable_tasks.append(dict(tid=tid, errorType=type(error).__name__))
                after = identity(pid)
                if (before['startTicks'], before['ppid'], before['uid']) != (
                        after['startTicks'], after['ppid'], after['uid']):
                    report['identityChanged'] = True
                    continue
                after['taskChildListsObserved'] = len(tids[:16])-len(unavailable_tasks)
                after['taskListsTruncated'] = threads_truncated
                if unavailable_tasks:
                    after['unavailableTaskChildListCount'] = len(unavailable_tasks)
                    after['unavailableTaskChildLists'] = unavailable_tasks[:4]
                    after['unavailableTaskChildListsTruncated'] = len(unavailable_tasks) > 4
                report['processes'].append(after)
                remaining = 16-len(visited)-len(queue)
                valid = [int(value) for value in children if value.isascii() and value.isdecimal()]
                report['truncated'] |= len(valid) > max(0, remaining)
                queue.extend((child, pid) for child in valid[:max(0, remaining)])
            except (OSError, ValueError, IndexError, UnicodeError) as error:
                report.setdefault('unavailable', []).append(dict(pid=pid, errorType=type(error).__name__))
        report['truncated'] |= bool(queue)
    except (OSError, ValueError, IndexError, UnicodeError) as error:
        report['unavailable'] = [dict(pid=parent_pid, errorType=type(error).__name__)]
    report['finishedMonotonicNs'] = time.monotonic_ns()
    return report


def startup_events(log):
    """Read bounded phase records from this fixture's owned runtime log."""
    report = dict(observedMonotonicNs=time.monotonic_ns(), events=[])
    try:
        with log.open('rb') as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size-65536))
            text = stream.read(65536).decode(errors='replace')
        report['logTailTruncated'] = size > 65536
        for line in text.splitlines():
            marker = 'FRAMEY_TERMINAL_STARTUP_JSON='
            if marker not in line:
                continue
            try:
                event = json.loads(line.split(marker, 1)[1])
                # Keep only timing/identity; no plugin output or arguments.
                if (isinstance(event, dict) and type(event.get('pid')) is int and
                        type(event.get('monotonicNs')) is int and isinstance(event.get('phase'), str)):
                    clean = dict(pid=event['pid'], monotonicNs=event['monotonicNs'],
                                 phase=event['phase'][:64])
                    if isinstance(event.get('errorType'), str):
                        clean['errorType'] = event['errorType'][:64]
                    report['events'].append(clean)
            except ValueError:
                report['incompleteRecord'] = True
        report['eventsTruncated'] = len(report['events']) > 16
        report['events'] = report['events'][-16:]
    except OSError as error:
        report['unavailable'] = type(error).__name__
    return report


def observe_initial_timeout(log, backend):
    """Observe only after the original failure; never issue or retry an RPC."""
    started = time.monotonic_ns()
    deadline = started + 2_500_000_000
    reason = 'observation-deadline'
    while time.monotonic_ns() < deadline:
        if backend.poll() is not None:
            reason = 'parent-exited'
            break
        observation = startup_events(log)
        if any(event['phase'] == 'message-handled' for event in observation['events']):
            reason = 'message-handled-observed'
            break
        remaining = (deadline-time.monotonic_ns()) / 1_000_000_000
        if remaining > 0:
            time.sleep(min(.1, remaining))
    return dict(originalFailureRetained=True, qualificationPassed=False, newRpcIssued=False,
                startedMonotonicNs=started, observationDeadlineMonotonicNs=deadline,
                finishedMonotonicNs=time.monotonic_ns(), stopReason=reason,
                startup=startup_events(log))


async def timed_call(client, method, args, timings):
    entry = dict(method=method, requestId=client.sequence+1,
                 startedMonotonicNs=time.monotonic_ns(), outcome='pending')
    if len(timings) < 64:
        timings.append(entry)
    try:
        result = await client.call(method, *args)
    except BaseException as error:
        entry.update(finishedMonotonicNs=time.monotonic_ns(), outcome='failed',
                     errorType=type(error).__name__)
        raise
    entry.update(finishedMonotonicNs=time.monotonic_ns(), outcome='succeeded')
    return result


def probe(name, home, backend, processes, *, discovery_ns=None):
    assert os.getuid() == 1100 and home == Path('/home/tester')
    assert not Path('/sys/class/net/eth0').exists()
    marker = home/'framey-terminal-marker'
    assert not marker.exists()
    observed = []
    transcript = []
    timings = []
    startup_before_first_rpc = None

    async def exercise():
        nonlocal startup_before_first_rpc
        async with Client(name, transcript) as client:
            startup_before_first_rpc = startup_events(home/'runtime.log')
            startup_before_first_rpc['processes'] = startup_processes(backend.pid)
            async def call(method, *args):
                result = await timed_call(client, method, args, timings)
                observed.append(dict(method=method, result=result))
                return result
            assert await call('get_terminals') == []
            assert '/bin/sh' in await call('get_shells')
            assert await call('set_default_shell', '/bin/sh') is True
            assert await call('get_default_shell') == '/bin/sh'
            config = await call('get_config')
            assert config == dict(__version__=1, default_shell='/bin/sh')
            terminal_id = 'a1b2-private-pty'
            assert await call('create_terminal', terminal_id) is True
            terminal = await call('get_terminal', terminal_id)
            assert terminal['is_started'] is True and terminal['is_completed'] is False
            pid = terminal['pid']
            assert pid > 0 and (Path('/proc')/str(pid)).stat().st_uid == os.getuid()
            assert await call('subscribe_terminal', terminal_id) is True
            assert await call('change_terminal_window_size', terminal_id, 31, 97) is True
            # A newly started interactive shell may emit its prompt after input
            # is echoed. Separate it from stty's result; retain exact line checks.
            command = "printf 'framey-owned-terminal\\n' > framey-terminal-marker; printf '\\n'; stty size; printf 'framey-owned-output\\n'; printf 'framey-owned-stderr\\n' >&2\n"
            assert await call('send_terminal_input', terminal_id, command) is True
            await client.drain(1)
            output = ''.join(e['args'][0] for e in client.events if e['event']=='terminal_output#'+terminal_id)
            observed.append(dict(method='private_pty_output', result=dict(
                markerHex=marker.read_bytes()[:256].hex(), output=output[-2048:])))
            assert marker.read_bytes() == b'framey-owned-terminal\n'
            assert '\r\n31 97\r\n' in output
            assert '\r\nframey-owned-output\r\n' in output
            assert '\r\nframey-owned-stderr\r\n' in output
            assert await call('unsubscribe_terminal', terminal_id) is True
            assert await call('remove_terminal', terminal_id) is True
            assert await call('get_terminals') == []
            assert not (Path('/proc')/str(pid)).exists()
            assert await call('create_terminal', terminal_id) is True
            second = await call('get_terminal', terminal_id)
            assert second['pid'] != pid and second['is_completed'] is False
            return dict(firstPid=pid, reloadPid=second['pid'], config=config,
                        outputSha256=hashlib.sha256(output.encode()).hexdigest(),
                        transcript=transcript)

    try:
        report = asyncio.run(exercise())
    except Exception as error:
        print('FRAMEY_TERMINAL_RPC_FAILURE_JSON='+json.dumps(dict(
            discoveryMonotonicNs=discovery_ns, lastRequest=timings[-1] if timings else None,
            parentPid=backend.pid, parentAlive=backend.poll() is None,
            beforeFirstRpc=startup_before_first_rpc,
            processesAtFailure=startup_processes(backend.pid),
            atFailure=startup_events(home/'runtime.log'))), flush=True, file=sys.stderr)
        if (isinstance(error, (TimeoutError, asyncio.TimeoutError)) and len(timings) == 1
                and timings[0]['method'] == 'get_terminals' and not observed):
            try:
                late = observe_initial_timeout(home/'runtime.log', backend)
            except Exception as observation_error:
                late = dict(originalFailureRetained=True, qualificationPassed=False,
                            newRpcIssued=False, unavailable=type(observation_error).__name__)
            print('FRAMEY_TERMINAL_LATE_CONNECTION_JSON='+json.dumps(late),
                  flush=True, file=sys.stderr)
        print('FRAMEY_TERMINAL_PROGRESS_JSON='+json.dumps(dict(
            calls=observed, transcript=transcript, success=False, realFrameContacted=False,
            privateContainerInputOnly=True)), flush=True, file=sys.stderr)
        raise
    def identity(pid):
        directory = Path('/proc')/str(pid)
        try:
            fields = (directory/'stat').read_text().rsplit(')', 1)[1].split()
            return dict(pid=pid, uid=directory.stat().st_uid, state=fields[0],
                        ppid=int(fields[1]), startTicks=int(fields[19]),
                        cmdline=(directory/'cmdline').read_bytes()[:256].decode(errors='replace'))
        except FileNotFoundError:
            return None
    from check import rpc, until_ready
    report['reloadBefore'] = identity(report['reloadPid'])
    unrelated = subprocess.Popen(['/bin/sleep','30'], start_new_session=True)
    processes.append(unrelated)
    rpc('loader/reload_plugin',name)
    def reloaded():
        text=(home/'runtime.log').read_text()
        return text.count('Loaded '+name)==2 and text.count('Unloaded '+name)==1
    try:
        until_ready(reloaded, 'actual Terminal reload')
    except Exception:
        print('FRAMEY_TERMINAL_RELOAD_FAILURE_JSON='+json.dumps(dict(
            report, reloadAfter=identity(report['reloadPid']), calls=observed,
            realFrameContacted=False, privateContainerInputOnly=True)), flush=True, file=sys.stderr)
        raise
    report['reloadAfter'] = identity(report['reloadPid'])
    print('FRAMEY_TERMINAL_RELOAD_JSON='+json.dumps(dict(
        report, calls=observed, realFrameContacted=False, privateContainerInputOnly=True)), flush=True, file=sys.stderr)
    assert report['reloadAfter'] is None
    assert rpc('loader/call_plugin_method',name,'get_terminals') == []
    assert rpc('loader/call_plugin_method',name,'get_config') == report['config']
    assert unrelated.poll() is None
    unrelated.terminate(); unrelated.wait(timeout=3)
    report.update(calls=observed, transcript=transcript, privateInputOutput=True, resizeVerified=True,
                  explicitRemoveReaped=True, reloadReaped=True, unrelatedProcessPreserved=True,
                  configPersistedAcrossPluginReload=True, realFrameContacted=False,
                  browserVerified=False, physicalControllerVerified=False,
                  initialRpcDiagnostics=dict(discoveryMonotonicNs=discovery_ns,
                      beforeFirstRpc=startup_before_first_rpc, requests=timings,
                      afterReload=startup_events(home/'runtime.log')))
    return report
