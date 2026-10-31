"""Published-loader dependency discovery; no real Ludusavi or save operations."""
import hashlib
import io
import os
from pathlib import Path
import signal
import subprocess
import time
import zipfile


def exercise(call, plugin, archive, record, backend, loader, env, log,
             processes, until_ready, rpc):
    helper = plugin/'py_modules/ludusavi.py'
    managed = helper.read_bytes()
    hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as original:
        original_helper = original.read(record['folder']+'/py_modules/ludusavi.py')
        for item in original.infolist():
            if item.is_dir():
                continue
            relative = item.filename.split('/', 1)[1]
            payload = (plugin/relative).read_bytes()
            if relative != 'py_modules/ludusavi.py':
                assert payload == original.read(item), relative
            hashes[relative] = hashlib.sha256(payload).hexdigest()
    assert managed != original_helper
    stops, states = [], []
    home = Path.home()
    tools = home/'bin'

    def stop(process):
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
        adopted = []

        def reaped():
            for pid in owned:
                if pid != process.pid:
                    try:
                        child, status = os.waitpid(pid, os.WNOHANG)
                        if child:
                            adopted.append({'pid': child, 'returncode': os.waitstatus_to_exitcode(status)})
                    except ChildProcessError:
                        pass
                try:
                    if (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()[19] == tree[pid][1]:
                        return False
                except (FileNotFoundError, ProcessLookupError):
                    pass
            return True
        until_ready(reaped, 'owned Ludusavi fixture loader descendants reaped')
        stops.append({'returncode': 0, 'elapsedSeconds': time.monotonic()-started,
                      'parentOnlySignal': True, 'ownedProcessCount': len(owned),
                      'adoptedChildExits': adopted, 'ownedProcessIdentitiesReaped': True})

    def initialized(count):
        until_ready(lambda: (home/'runtime.log').read_text().count('Using Binary:') == count,
                    'Ludusavi dependency discovery completion')

    def restart(count):
        process = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log,
                                   start_new_session=True)
        processes.append(process)
        found = until_ready(lambda: rpc('loader/get_plugins'), 'Ludusavi restart discovery')
        assert len(found) == 1 and found[0]['name'] == record['name'] and not found[0]['disabled']
        initialized(count)
        return process

    initialized(1)
    missing = {'bin_path': None, 'version': ''}
    assert call('get_ludusavi_version') == missing
    states.append({'stage': 'missing', 'result': missing})
    stop(backend)

    # A single owned Python executable sleeps past the discovery timeout; it
    # never launches Flatpak or a descendant. A different private CLI is the
    # fallback. Neither binary can touch saves or the network.
    slow = tools/'flatpak'
    pidfile = home/'slow-discovery.pid'
    slow.write_text('#!/usr/bin/python3\nimport os,time\nfrom pathlib import Path\n'
                    'Path('+repr(str(pidfile))+').write_text(str(os.getpid()))\ntime.sleep(60)\n')
    slow.chmod(0o700)
    cli = tools/'ludusavi'
    cli.write_text('#!/usr/bin/python3\nimport sys\nassert sys.argv[1:]==["--version"]\n'
                   'print("ludusavi private-fixture 0.0")\n')
    cli.chmod(0o700)
    started = time.monotonic()
    second = restart(2)
    found = {'bin_path': ['ludusavi'], 'version': 'ludusavi private-fixture 0.0\n'}
    assert call('get_ludusavi_version') == found
    elapsed = time.monotonic()-started
    assert 2 <= elapsed < 12, elapsed
    slow_pid = int(pidfile.read_text())
    assert not (Path('/proc')/str(slow_pid)).exists(), 'timed-out discovery child must be reaped'
    states.append({'stage': 'slow-first-candidate-fallback', 'result': found,
                   'elapsedSeconds': elapsed, 'timedOutChildReaped': True})
    stop(second)
    slow.unlink()
    cli.unlink()

    # Preserve the unchanged published failure as a negative control in the
    # same real loader. Only this disposable installed helper is replaced.
    helper.write_bytes(original_helper)
    third = restart(3)
    try:
        call('get_ludusavi_version')
    except AssertionError as error:
        assert 'version' in str(error), str(error)
        original_failure = str(error)
    else:
        raise AssertionError('Unchanged original unexpectedly reported the missing dependency')
    stop(third)
    helper.write_bytes(managed)
    fourth = restart(4)
    assert call('get_ludusavi_version') == missing
    states.append({'stage': 'managed-missing-after-restart', 'result': missing})
    stop(fourth)
    log.flush()
    log.seek(0)
    console = log.read()
    assert console.count('Starting Decky version v3.3.0') == 4
    assert console.count('[main][INFO]: Shutdown finished.') == 4
    for marker in ['Error during shutdown:', 'Task was destroyed but it is pending',
                   'asyncio.exceptions.CancelledError', 'Bad file descriptor']:
        assert marker not in console, marker
    return {'onlyHelperModified': True, 'managedArchiveMemberSha256': hashes,
            'originalHelperSha256': hashlib.sha256(original_helper).hexdigest(),
            'managedHelperSha256': hashlib.sha256(managed).hexdigest(),
            'states': states, 'originalMissingDependencyFailure': original_failure,
            'ownedLoaderStops': stops, 'loaderConsole': console,
            'loaderConsoleSha256': hashlib.sha256(console.encode()).hexdigest(),
            'publishedDeckyRpcVerified': True, 'fakeExecutablesOnly': True,
            'actualLudusaviVerified': False, 'backupRestoreVerified': False,
            'cloudSyncVerified': False, 'browserVerified': False,
            'realFrameContacted': False, 'physicalControllerVerified': False}
