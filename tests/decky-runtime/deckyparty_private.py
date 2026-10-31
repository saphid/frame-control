"""Retain actual private DeckyParty reloads, process identities and final stop."""
import hashlib
import os
from pathlib import Path
import signal
import socket
import time


def identity(pid):
    try:
        fields = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()
        return dict(state=fields[0], parent=int(fields[1]), start=fields[19])
    except FileNotFoundError:
        return None


def remaining(before):
    return {pid: state for pid, old in before.items()
            if (state := identity(pid)) and state['start'] == old['start']}


def reload(backend, log, server_pids, rpc, until_ready, index, *, regression):
    servers = {pid: identity(pid) for pid in server_pids()}
    assert servers and all(servers.values())
    # PyInstaller's multiprocessing fork server can sit between the loader and
    # plugin. The server's parent identifies the plugin, not that infrastructure.
    old = {state['parent']: identity(state['parent']) for state in servers.values()}
    assert len(old) == 1 and all(old.values())
    ancestors = []
    pid = next(iter(old))
    while pid != backend.pid:
        state = identity(pid)
        assert state and pid > 1
        ancestors.append(dict(pid=pid, **state))
        pid = state['parent']
    assert all(os.getpgid(pid) == pid for pid in servers), 'owned server sessions only'
    before = Path(log.name).read_text()
    started = time.monotonic()
    # Reproduce the disconnect deterministically instead of relying on the
    # parent/child stop race. Only this isolated fixture's live Unix socket is
    # reachable; previous reloads may leave stale, non-listening socket files.
    closed_peers = []
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
    time.sleep(.05)  # Let the child consume EOF before the parent queues unload.
    rpc('loader/reload_plugin', 'DeckyParty File Manager')

    def completed():
        output = Path(log.name).read_text()
        if not regression:
            assert 'Sending SIGKILL!' not in output, 'Decky forcibly killed the plugin'
        return (output.count('Loaded DeckyParty File Manager') == index+2 and
                (regression or output.count('Unloaded DeckyParty File Manager') == index+1))

    # Reload queues work. Never issue another legacy RPC to the closing wrapper.
    until_ready(completed, 'actual DeckyParty reload completion')
    console = Path(log.name).read_text()[len(before):]
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    survivors = remaining(servers)
    parent = next(iter(old.values()))['parent']
    def replacement():
        found = {int(p.name): state for p in Path('/proc').iterdir() if p.name.isdigit()
                 if (state := identity(int(p.name))) and state['parent'] == parent
                 and int(p.name) not in old}
        return found if len(found) == 1 else None
    new = until_ready(replacement, 'replacement plugin process')
    observation = dict(pluginChildrenBefore=old, pluginAncestorsBefore=ancestors,
        pluginChildrenAfter=new, exactPluginChildrenRemaining=remaining(old),
        fixtureClosedUnixPeers=closed_peers,
        serverProcessesBefore=servers, exactServerProcessesRemaining=survivors,
        seconds=round(time.monotonic()-started, 3), forcedPluginKills=forced,
        unloadHookCompleted='Unloaded DeckyParty File Manager' in console,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        expectedRegression=regression)
    assert not observation['exactPluginChildrenRemaining'], observation
    if regression:
        assert forced == 1 and not observation['unloadHookCompleted'], observation
        # The old plugin may leave its owned server alive. Only reap the exact
        # previously recorded session inside this disposable container.
        cleaned = []
        for pid, state in survivors.items():
            now = identity(pid)
            if now and now['start'] == state['start'] and pid in server_pids():
                os.killpg(pid, signal.SIGTERM)
                cleaned.append(pid)
        observation['testCleanupSignaledOwnedServers'] = cleaned
    else:
        assert forced == 0 and observation['unloadHookCompleted'] and not survivors, observation
        observation['testCleanupSignaledOwnedServers'] = []
    return observation


def stop(backend, log, server_pids, old):
    assert old and remaining(old).keys() == old.keys()
    before = Path(log.name).read_text()
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    console = Path(log.name).read_text()[len(before):]
    errors = [marker for marker in ('Sending SIGKILL!', 'Error during shutdown:',
        'asyncio.exceptions.CancelledError', 'Task was destroyed but it is pending',
        'Bad file descriptor') if marker in console]
    observation = dict(loaderPid=backend.pid, pluginChildrenBefore=old,
        exactPluginChildrenRemaining=remaining(old), serverPidsAfter=server_pids(),
        parentOnlySignal=True, loaderReturncode=backend.returncode,
        seconds=round(time.monotonic()-started, 3), errors=errors,
        console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest())
    assert (backend.returncode == 0 and not errors and not observation['exactPluginChildrenRemaining']
            and not observation['serverPidsAfter'] and observation['seconds'] < 5
            and 'Unloaded DeckyParty File Manager' in console
            and console.count('[main][INFO]: Shutdown finished.') == 1), observation
    return observation
