"""Retain private Free Loader settings/cache and clean owner shutdown evidence."""
import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import json


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


def stop(backend, log, *, disconnect):
    children = descendants(backend.pid)
    assert children, 'the private loader must own its children'
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
    clean = (backend.returncode == 0 and not remaining and not forced and not errors
             and all(child['returncode'] == 0 for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin Free Loader (v1.6.0) has been stopped in ' in console)
    observation = dict(loaderPid=backend.pid, descendantsBefore=children,
        exactDescendantsRemaining=remaining, adoptedChildExits=adopted, parentOnlySignal=True,
        loaderReturncode=backend.returncode, seconds=round(time.monotonic()-started, 3),
        fixtureClosedUnixPeers=closed_peers, forcedPluginKills=forced, errors=errors,
        console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=clean)
    return observation



def snapshot(directory):
    result = {}
    for name in ['settings.json', 'deal_db.json']:
        data = (directory/name).read_bytes()
        result[name] = dict(text=data.decode(), sha256=hashlib.sha256(data).hexdigest(),
                            parsed=json.loads(data))
    return result


def probe(backend, loader, env, log, processes, current, rpc, until_ready, report,
          settings_dir, *, regression=False):
    evidence = report['freeLoaderLifecycle'] = dict(stops=[], diskReadbacks=[],
        unrelatedSiblingPreserved=False, cleanShutdownVerified=False,
        expectedRegression=regression, realFrameContacted=False, physicalControllerVerified=False)
    key = 'framey-private-63'
    deal = dict(id=key, title='Framey private cached game', worth='N/A',
        image='https://example.invalid/framey-owned.png',
        open_giveaway_url='https://example.invalid/framey-owned',
        published_date='2026-10-31', end_date='N/A', status='Active', platforms='Steam', hidden=False)
    # Seed only this disposable container's owned local cache. No feed request,
    # notification, browser, Steam store or real user file is involved.
    (settings_dir/'deal_db.json').write_text(json.dumps({key: deal}, indent=4))
    assert current('read_deals') == {key: deal}
    assert current('toggle_deal_visibility', key) == {'hidden': True}
    deal['hidden'] = True
    assert current('read_deals') == {key: deal}
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(80)'],
                                 start_new_session=True)
    processes.append(unrelated)
    try:
        for cycle in range(1 if regression else 2):
            before = snapshot(settings_dir)
            assert before['settings.json']['parsed']['larger_text'] is True
            assert before['deal_db.json']['parsed'] == {key: deal}
            observation = stop(backend, log, disconnect=cycle == 0)
            evidence['stops'].append(observation)
            after = snapshot(settings_dir)
            evidence['diskReadbacks'].append(dict(before=before, after=after))
            assert before == after, 'unload must preserve exact private settings/cache bytes'
            assert unrelated.poll() is None, 'an unrelated sibling must survive'
            if regression:
                assert (not observation['cleanShutdownVerified'] and
                        observation['forcedPluginKills'] == 1 and
                        observation['loaderReturncode'] == 0), observation
            else:
                assert observation['cleanShutdownVerified'] and observation['seconds'] < 5, observation
            if not regression and cycle == 0:
                backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                processes.append(backend)
                discovered = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Free Loader discovery')
                assert discovered == report['discovered'], discovered
                evidence['restartedDiscovery'] = discovered
                assert until_ready(lambda: current('settings_read')['larger_text'],
                                   'private Free Loader setting after restart') is True
                assert current('read_deals') == {key: deal}
                assert current('toggle_deal_visibility', key) == {'hidden': False}
                deal['hidden'] = False
                assert current('read_deals') == {key: deal}
        evidence['unrelatedSiblingPreserved'] = unrelated.poll() is None
        evidence['cleanShutdownVerified'] = not regression
        return evidence
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        unrelated.wait(timeout=3)
        log.flush()
        console = Path(log.name).read_text()
        evidence['console'] = console
        evidence['consoleSha256'] = hashlib.sha256(console.encode()).hexdigest()
