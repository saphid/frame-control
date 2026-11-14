"""Notebook's unmodified backend, private app IDs and independent file readback."""
import hashlib
import json


def probe(call, restart, settings):
    app_a, app_b = 424242, 434343
    strokes = {
        (0, 0): [{"paths": [{"x": 4, "y": 8}, {"x": 16, "y": 24}],
                  "strokeWidth": 3, "strokeColor": "#ffffff", "drawMode": True}],
        (app_a, 2): [{"paths": [{"x": 10, "y": 20}, {"x": 30, "y": 40}],
                      "strokeWidth": 4, "strokeColor": "#ff0000", "drawMode": True}],
        (app_b, 2): [{"paths": [{"x": 50, "y": 60}, {"x": 70, "y": 80}],
                      "strokeWidth": 5, "strokeColor": "#00ff00", "drawMode": True}],
    }
    payloads = {key: json.dumps(value, separators=(',', ':')) for key, value in strokes.items()}
    for app in (0, app_a, app_b):
        assert call('listPages', appid=app) == []
        assert call('loadLastSelectedPage', appid=app) == 0
        assert call('loadPage', appid=app, page=2) == dict(page=2, timestamp=0, empty=True, data='')
    for (app, page), data in payloads.items():
        saved = call('savePage', appid=app, page=page, data=data)
        assert type(saved['timestamp']) is int and saved['timestamp'] > 0
        path = settings / str(app) / (str(page) + '.json')
        assert path.read_text() == data
        loaded = call('loadPage', appid=app, page=page)
        assert loaded == dict(page=page, timestamp=int(path.stat().st_mtime * 1000), empty=False, data=data)
    assert call('savePage', appid=app_a, page=7, data='')['timestamp'] > 0
    assert call('loadPage', appid=app_a, page=7)['empty'] is True
    selections = {0: 0, app_a: 7, app_b: 2}
    for app, page in selections.items():
        assert call('saveLastSelectedPage', appid=app, page=page) is True
        assert (settings / str(app) / 'page').read_text() == str(page)
    before = {str(path.relative_to(settings)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in settings.rglob('*') if path.is_file()}
    restart()
    for app, page in selections.items():
        assert call('loadLastSelectedPage', appid=app) == page
    for (app, page), data in payloads.items():
        assert call('loadPage', appid=app, page=page)['data'] == data
    pages = sorted(call('listPages', appid=app_a), key=lambda item: item['page'])
    assert [p['page'] for p in pages] == [2, 7]
    assert [p['empty'] for p in pages] == [False, True]
    assert all(type(p['timestamp']) is int and p['timestamp'] > 0 for p in pages)
    assert call('deletePage', appid=app_a, page=2) is True
    assert call('deletePage', appid=app_a, page=2) is False
    assert call('loadPage', appid=app_a, page=2)['empty'] is True
    assert not (settings / str(app_a) / '2.json').exists()
    for app in (0, app_b):
        page = 0 if app == 0 else 2
        assert call('loadPage', appid=app, page=page)['data'] == payloads[(app, page)]
    assert [p['page'] for p in call('listPages', appid=app_a)] == [7]
    after = {str(path.relative_to(settings)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in settings.rglob('*') if path.is_file()}
    assert after == {name: digest for name, digest in before.items() if name != str(app_a) + '/2.json'}
    return dict(defaultAndTwoAppNamespaces=True, samePageNumberIsolated=True,
                strokeBytesIndependentlyReadBack=True, emptyPageMetadata=True,
                perAppSelectionPersistedAcrossRestart=True, pageBytesPersistedAcrossRestart=True,
                selectedDeletePreservedOtherPages=True, retainedFilesSha256=after,
                publishedBackendUnmodified=True, syntheticAppIds=[0, app_a, app_b],
                browserVerified=False, realSteamGameSelectionVerified=False,
                realFrameContacted=False, physicalControllerVerified=False)


def stop(backend, log, call, *, regression):
    """Close an owned IPC peer; then stop only the loader and audit its children."""
    import os
    from pathlib import Path
    import signal
    import socket
    import time
    from deck_shelves_private import descendants, identity

    children = descendants(backend.pid)
    assert children, 'the private loader must own its Notebook child'
    log.flush()
    before = Path(log.name).read_text()
    closed = []
    for path in Path('/tmp').glob('plugin_socket_*'):
        assert path.is_socket() and path.stat().st_uid == os.getuid()
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(.2)
            try:
                peer.connect(str(path))
            except ConnectionRefusedError:
                continue
            peer.shutdown(socket.SHUT_WR)
            closed.append(str(path))
    assert len(closed) == 1, closed
    time.sleep(.05)
    # A completed RPC after EOF proves the original event-loop spin is gone.
    readback = None if regression else call('loadLastSelectedPage', appid=0)
    if not regression:
        assert readback == 0
    started = time.monotonic()
    backend.send_signal(signal.SIGTERM)
    backend.wait(timeout=8)
    elapsed = time.monotonic()-started
    log.flush()
    console = Path(log.name).read_text()[len(before):]
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
    forced = console.count('Sending SIGKILL!')
    errors = [m for m in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
                         'Task was destroyed but it is pending', 'Bad file descriptor') if m in console]
    clean = (backend.returncode == 0 and elapsed < 5 and not remaining and not forced and not errors
             and all(c['returncode'] == 0 for c in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and console.count('Unloaded Notebook (v0.1.5)') == 1)
    return dict(parentOnlySignal=True, returncode=backend.returncode, elapsedSeconds=round(elapsed, 3),
                fixtureClosedUnixPeers=closed, postEofRpcReadback=readback,
                descendantsBefore=children, exactDescendantsRemaining=remaining,
                adoptedChildExits=adopted, forcedPluginKills=forced, errors=errors,
                console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
                cleanShutdownVerified=clean)
