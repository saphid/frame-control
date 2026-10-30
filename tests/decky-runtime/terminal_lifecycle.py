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


def probe(name, home, backend, processes):
    assert os.getuid() == 1100 and home == Path('/home/tester')
    assert not Path('/sys/class/net/eth0').exists()
    marker = home/'framey-terminal-marker'
    assert not marker.exists()
    observed = []

    async def exercise():
        async with Client(name) as client:
            async def call(method, *args):
                result = await client.call(method, *args)
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
            command = "printf 'framey-owned-terminal\\n' > framey-terminal-marker; stty size; printf 'framey-owned-output\\n'; printf 'framey-owned-stderr\\n' >&2\n"
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
                        outputSha256=hashlib.sha256(output.encode()).hexdigest())

    try:
        report = asyncio.run(exercise())
    except Exception:
        print('FRAMEY_TERMINAL_PROGRESS_JSON='+json.dumps(dict(
            calls=observed, success=False, realFrameContacted=False,
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
    report.update(calls=observed, privateInputOutput=True, resizeVerified=True,
                  explicitRemoveReaped=True, reloadReaped=True, unrelatedProcessPreserved=True,
                  configPersistedAcrossPluginReload=True, realFrameContacted=False,
                  browserVerified=False, physicalControllerVerified=False)
    return report
