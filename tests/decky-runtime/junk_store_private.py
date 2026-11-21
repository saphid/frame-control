"""Network-isolated Junk-Store 1.1.13 static menu and clean-unload/IPC-EOF probe."""
import hashlib
import io
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import zipfile
from deck_settings_private import identity, descendants

OLD_STOP = (
    b'            # Stop the event loop if it exists\n'
    b'            if Helper.ws_loop and Helper.ws_loop.is_running():\n'
    b'                Helper.ws_loop.stop()\n'
)
NEW_STOP = b"            # Leave Decky's shared event loop running during plugin unload.\n"
OLD_CANCEL = (
    b'            # Cancel all pending asyncio tasks\n'
    b'            tasks = [task for task in asyncio.all_tasks() if not task.done()]\n'
    b'            if tasks:\n'
    b'                decky_plugin.logger.info(f"Cancelling {len(tasks)} pending tasks...")\n'
    b'                for task in tasks:\n'
    b'                    task.cancel()\n'
    b'                # Wait for all tasks to complete cancellation\n'
    b'                await asyncio.gather(*tasks, return_exceptions=True)\n'
)
NEW_CANCEL = b"            # Leave Decky's shared IPC and unload tasks intact.\n"
PREFIX = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
          b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')


def patch_unload(source):
    assert source.count(OLD_STOP) == 1 and source.count(OLD_CANCEL) == 1
    return source.replace(OLD_STOP, NEW_STOP).replace(OLD_CANCEL, NEW_CANCEL)


def stop(backend, log, disconnect, after_disconnect=None, *, expect_forced_kill=False, expect_unload_crash=False):
    before = descendants(backend.pid)
    assert before
    peers = []
    if disconnect:
        paths = list(Path('/tmp').glob('plugin_socket_*'))
        assert len(paths) == 1, paths
        assert paths[0].is_socket() and paths[0].stat().st_uid == os.getuid()
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(.2)
            peer.connect(str(paths[0]))
            peer.shutdown(socket.SHUT_WR)
        peers = [str(paths[0])]
        time.sleep(.05)
        if after_disconnect is not None:
            after_disconnect()
    log.flush()
    previous = Path(log.name).read_text()
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=12)
    adopted = []
    deadline = time.monotonic() + 2
    while True:
        for pid, old in before.items():
            current = identity(pid)
            if current and current['start'] == old['start']:
                try:
                    done, status = os.waitpid(pid, os.WNOHANG)
                    if done:
                        adopted.append(dict(pid=done, returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:
                    pass
        remaining = {pid: state for pid, old in before.items()
                     if (state := identity(pid)) and state['start'] == old['start']}
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(.01)
    log.flush()
    console = Path(log.name).read_text()[len(previous):]
    seconds = time.monotonic() - started
    forced = console.count('Sending SIGKILL!')
    recursion_error = 'RecursionError: maximum recursion depth exceeded' in console
    assert backend.returncode == 0 and not remaining, (backend.returncode, remaining, console)
    if expect_unload_crash:
        assert recursion_error, console
        assert 'Junk-Store out!' not in console and 'Unloaded Junk-Store (v1.1.13)' not in console, console
    elif expect_forced_kill:
        assert forced == 1 and seconds >= 5, (forced, seconds, console)
    else:
        assert forced == 0 and seconds < 5 and not recursion_error, (forced, seconds, console)
        assert all(v['returncode'] == 0 for v in adopted), adopted
        assert 'Error during shutdown:' not in console and 'Traceback' not in console, console
        assert 'Plugin Junk-Store (v1.1.13) has been stopped in ' in console, console
        assert 'Junk-Store out!' in console and 'Unloaded Junk-Store (v1.1.13)' in console, console
    return dict(
        parentOnlySignal=True,
        returncode=backend.returncode,
        seconds=seconds,
        forcedPluginKills=forced,
        recursionError=recursion_error,
        unloadCompleted='Junk-Store out!' in console and 'Unloaded Junk-Store (v1.1.13)' in console,
        descendantsBefore=before,
        exactDescendantsRemaining=remaining,
        adoptedChildExits=adopted,
        closedUnixPeers=peers,
        console=console,
        consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=not expect_forced_kill and not expect_unload_crash,
    )


def probe(backend, loader, env, log, processes, legacy, rpc, until_ready, plugin,
          discovered, archive_bytes, *, original_unload=False, ipc_regression=False):
    evidence = dict(
        realFrameContacted=False,
        networkDevice=False,
        legendaryInstalled=False,
        officialUiVerified=False,
        stops=[],
    )
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative = member.filename.split('/', 1)[1]
            expected = archive.read(member)
            if relative == 'main.py':
                if ipc_regression:
                    expected = patch_unload(expected)
                elif not original_unload:
                    expected = PREFIX + patch_unload(expected)
            assert (plugin / relative).read_bytes() == expected, relative
    ipc_helper = plugin / 'py_modules/framey_decky_ipc.py'
    if original_unload or ipc_regression:
        assert not ipc_helper.exists()
    else:
        assert ipc_helper.is_file()

    # Verify owner execute bit preserved for shebang scripts.
    assert (plugin / 'scripts/junk-store.sh').stat().st_mode & 0o100
    assert (plugin / 'scripts/Extensions/Epic/store.sh').stat().st_mode & 0o100

    marker = Path.home() / 'unrelated-junk-store-marker'
    marker.write_bytes(b'private unrelated file')
    before = dict(
        inode=marker.stat().st_ino,
        sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),
        mtimeNs=marker.stat().st_mtime_ns,
    )
    sibling = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(100)'], start_new_session=True)
    processes.append(sibling)
    sibling_before = identity(sibling.pid)

    init_actions = legacy('execute_action', actionSet='init', actionName='InitActions')
    assert isinstance(init_actions, dict) and init_actions.get('Type') == 'ActionSet', init_actions
    assert init_actions.get('Content', {}).get('SetName') == 'MainMenu', init_actions

    ws_port = legacy('get_websocket_port')
    assert isinstance(ws_port, int) and ws_port >= 8765, ws_port

    if original_unload:
        # Unmodified Junk-Store cancels all asyncio tasks (including _unload)
        # and stops Decky's shared event loop on SIGTERM, crashing with
        # RecursionError before completing unload.
        evidence['stops'].append(stop(backend, log, False, expect_unload_crash=True))
        evidence['expectedRegression'] = dict(
            recursionError=evidence['stops'][0]['recursionError'],
            seconds=evidence['stops'][0]['seconds'],
            unloadCompleted=evidence['stops'][0]['unloadCompleted'],
            qualifiedCompatibilityPass=False,
        )
        return evidence

    if ipc_regression:
        evidence['stops'].append(stop(backend, log, True, expect_forced_kill=True))
        evidence['expectedRegression'] = dict(
            forcedPluginKills=evidence['stops'][0]['forcedPluginKills'],
            seconds=evidence['stops'][0]['seconds'],
            unloadCompleted=evidence['stops'][0]['unloadCompleted'],
            qualifiedCompatibilityPass=False,
        )
        return evidence

    main_menu = legacy('execute_action', actionSet='MainMenu', actionName='GetContent')
    assert isinstance(main_menu, dict) and main_menu.get('Type') != 'Error', main_menu
    js_init = legacy('execute_action', actionSet='MainMenu', actionName='JunkStoreInit')
    assert isinstance(js_init, dict) and js_init.get('Type') == 'ActionSet', js_init
    js_actions = legacy('execute_action', actionSet='JunkStoreActions', actionName='GetContent')
    assert isinstance(js_actions, dict) and js_actions.get('Type') != 'Error', js_actions
    epic_actions = legacy('execute_action', actionSet='JunkStoreActions', actionName='GetEpicActions')
    assert isinstance(epic_actions, dict) and epic_actions.get('Type') == 'ActionSet', epic_actions
    evidence['staticActions'] = dict(
        initSetName=init_actions['Content']['SetName'],
        initActionCount=len(init_actions['Content'].get('Actions', [])),
        mainMenuType=main_menu.get('Type'),
        junkStoreInitSetName=js_init.get('Content', {}).get('SetName'),
        junkStoreActionsType=js_actions.get('Type'),
        epicActionsSetName=epic_actions.get('Content', {}).get('SetName'),
        websocketPort=ws_port,
    )

    post_eof = {}

    def verify_post_eof():
        post_eof['websocketPort'] = legacy('get_websocket_port')
        res = legacy('execute_action', actionSet='init', actionName='InitActions')
        post_eof['initType'] = res.get('Type') if isinstance(res, dict) else None
        assert post_eof['websocketPort'] == ws_port and post_eof['initType'] == 'ActionSet', post_eof

    for cycle in range(2):
        evidence['stops'].append(stop(backend, log, cycle == 0,
                                      after_disconnect=verify_post_eof if cycle == 0 else None))
        s = identity(sibling.pid)
        assert s and s['start'] == sibling_before['start'] and s['parent'] == sibling_before['parent']
        assert dict(
            inode=marker.stat().st_ino,
            sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),
            mtimeNs=marker.stat().st_mtime_ns,
        ) == before
        if cycle == 0:
            backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
            processes.append(backend)
            found = until_ready(lambda: rpc('loader/get_plugins'), 'restarted Junk-Store discovery')
            assert found == discovered
            restarted_init = legacy('execute_action', actionSet='init', actionName='InitActions')
            assert isinstance(restarted_init, dict) and restarted_init.get('Type') == 'ActionSet', restarted_init
            restarted_port = legacy('get_websocket_port')
            assert isinstance(restarted_port, int) and restarted_port >= 8765, restarted_port
            evidence['restartedActionsVerified'] = dict(initType=restarted_init['Type'], websocketPort=restarted_port)

    evidence['postEofReadback'] = post_eof
    evidence['siblingAndMarkerPreserved'] = True
    evidence['installedHashes'] = {
        p: hashlib.sha256((plugin / p).read_bytes()).hexdigest()
        for p in ['main.py', 'py_modules/framey_decky_ipc.py']
    }
    return evidence
