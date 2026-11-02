"""Private silent AlarMe lifecycle through published Decky's actual API1 RPC/events."""
import asyncio
import hashlib
import os
from pathlib import Path
import socket
import time
from timer_lifecycle import Client
from radiyo_private import descendants, identity


def stop(backend, log, *, disconnect):
    """Observe the loader's own cleanup; never signal its plugin children."""
    children = descendants(backend.pid)
    assert children
    before = Path(log.name).read_text()
    closed = []
    if disconnect:
        for path in Path('/tmp').glob('plugin_socket_*'):
            assert path.is_socket() and path.stat().st_uid == os.getuid()
            with socket.socket(socket.AF_UNIX) as peer:
                peer.settimeout(.2)
                peer.connect(str(path))
                peer.shutdown(socket.SHUT_WR)
            closed.append(str(path))
        assert len(closed) == 1
        time.sleep(.05)
    began = time.monotonic()
    backend.terminate()
    backend.wait(timeout=8)
    adopted = []
    deadline = time.monotonic() + 2
    while True:
        for pid, old in children.items():
            current = identity(pid)
            if current and current['start'] == old['start']:
                try:
                    done, status = os.waitpid(pid, os.WNOHANG)
                    if done:
                        adopted.append(dict(pid=done, returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:
                    pass
        remaining = {pid: current for pid, old in children.items()
                     if (current := identity(pid)) and current['start'] == old['start']}
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(.01)
    console = Path(log.name).read_text()[len(before):]
    forced = console.count('still alive 5 seconds after stop request! Sending SIGKILL!')
    errors = [marker for marker in ('Error during shutdown:', 'asyncio.exceptions.CancelledError',
              'Task was destroyed but it is pending', 'Bad file descriptor') if marker in console]
    elapsed = round(time.monotonic() - began, 3)
    clean = (backend.returncode == 0 and elapsed < 5 and not remaining and not forced and not errors
             and all(child['returncode'] == 0 for child in adopted)
             and console.count('[main][INFO]: Shutdown finished.') == 1
             and 'Plugin AlarMe (v1.6.3) has been stopped in ' in console
             and 'AlarMe: Plugin unloaded' in console)
    return dict(parentOnlySignal=True, loaderPid=backend.pid, returncode=backend.returncode,
                elapsedSeconds=elapsed, descendantsBefore=children,
                exactDescendantsRemaining=remaining, adoptedChildExits=adopted,
                closedUnixPeers=closed, forcedPluginKills=forced, errors=errors,
                console=console, consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
                cleanShutdownVerified=clean)


async def initial(name, calls, transcript):
    async with Client(name, transcript) as client:
        async def call(method, *args):
            value = await client.call(method, *args)
            calls.append(dict(method=method, result=value))
            return value

        assert await call('get_version') == '1.6.3'
        settings = await call('update_settings', dict(timer_subtle_mode=True, timer_volume=0,
            timer_auto_suspend=False, timer_prevent_sleep=False, pomodoro_prevent_sleep=False,
            presets_max_visible=6))
        assert settings['timer_volume'] == 0 and settings['timer_auto_suspend'] is False
        assert await call('get_active_timers') == []
        assert (await call('get_sleep_inhibitor_status'))['active'] is False
        timer = await call('create_timer', 120, 'Private paused timer', True, False, False)
        assert await call('pause_timer', timer) is True
        paused = (await call('get_active_timers'))[0]
        assert paused['id'] == timer and paused['paused'] and 0 < paused['remaining'] <= 120
        await client.drain(.3)
        assert (await call('get_active_timers'))[0]['remaining'] == paused['remaining']
        assert await call('resume_timer', timer) is True
        assert (await call('get_active_timers'))[0]['paused'] is False
        assert await call('cancel_timer', timer) is True
        assert await call('cancel_timer', timer) is False
        assert await call('get_active_timers') == []

        client.events.clear()
        short = await call('create_timer', 1, 'Private silent completion', True, False, False)
        await client.drain(2.5)
        completed = [e for e in client.events if e['event'] == 'alarme_timer_completed']
        assert len(completed) == 1 and completed[0]['args'][0]['id'] == short, completed
        assert completed[0]['args'][0]['subtle'] is True
        assert completed[0]['args'][0]['volume'] == 0
        assert completed[0]['args'][0]['auto_suspend'] is False
        assert await call('get_active_timers') == []

        original_presets = await call('get_presets')
        preset = await call('save_preset', 83, 'Private preset', True, False, False)
        duplicate = await call('save_preset', 83, 'Private preset', True, False, False)
        assert duplicate == preset
        assert (await call('get_presets')) == [preset, *original_presets]
        assert (await call('stopwatch_start'))['status'] == 'running'
        await client.drain(.2)
        first = await call('stopwatch_lap')
        await client.drain(.2)
        second = await call('stopwatch_lap')
        assert len(first['laps']) == 1 and len(second['laps']) == 2
        assert 0 < first['laps'][0]['absolute_ms'] < second['laps'][1]['absolute_ms']
        stopwatch = await call('stopwatch_pause')
        assert stopwatch['status'] == 'paused' and stopwatch['current_elapsed_ms'] > 0
        timer = await call('create_timer', 120, 'Private restart pause', True, False, False)
        assert await call('pause_timer', timer) is True
        paused = (await call('get_active_timers'))[0]
        elapsed = await call('create_timer', 1, 'Private elapsed pause', True, False, False)
        assert await call('pause_timer', elapsed) is True
        frozen = next(t for t in await call('get_active_timers') if t['id'] == elapsed)
        await client.drain(1.3)  # The original deadline expires while paused.
        return dict(timer=paused, elapsedTimer=frozen, preset=preset, originalPresets=original_presets,
                    stopwatch=stopwatch)


async def resumed(name, calls, saved, negative, transcript):
    async with Client(name, transcript) as client:
        async def call(method, *args):
            value = await client.call(method, *args)
            calls.append(dict(method=method, result=value))
            return value

        paused = await call('get_active_timers')
        expected = [saved['timer']] if negative else [saved['timer'], saved['elapsedTimer']]
        assert {t['id'] for t in paused} == {t['id'] for t in expected}, paused
        for timer in expected:
            actual = next(t for t in paused if t['id'] == timer['id'])
            assert actual['paused'] and actual['remaining'] == timer['remaining'], actual
        await client.drain(1.2)
        ticks = [e for e in client.events if e['event'] == 'alarme_timer_tick'
                 and e['args'][0]['id'] == saved['timer']['id']]
        assert bool(ticks) is negative, ticks
        assert (await call('get_presets')) == [saved['preset'], *saved['originalPresets']]
        assert (await call('stopwatch_get_state')) == saved['stopwatch']
        assert await call('cancel_timer', saved['timer']['id']) is True
        if not negative:
            # Resuming must use the frozen duration, not the elapsed deadline.
            assert await call('resume_timer', saved['elapsedTimer']['id']) is True
            client.events.clear()
            await client.drain(2.5)
            completed = [e for e in client.events if e['event'] == 'alarme_timer_completed']
            assert len(completed) == 1, completed
            assert completed[0]['args'][0]['id'] == saved['elapsedTimer']['id'], completed
        assert (await call('stopwatch_reset'))['status'] == 'idle'
        assert await call('remove_preset', saved['preset']['id']) is True
        assert await call('get_presets') == saved['originalPresets']
        assert await call('get_active_timers') == []
        assert (await call('get_sleep_inhibitor_status'))['active'] is False


def probe(name, restart, calls, negative=False):
    transcript = []
    saved = asyncio.run(initial(name, calls, transcript))
    restart()
    asyncio.run(resumed(name, calls, saved, negative, transcript))
    return dict(timerPauseResumeCancel=True, singleSilentCompletion=True,
                pausedTimerRestartPreserved=not negative, originalPausedRestartTicks=negative,
                elapsedPausedDeadlinePreservedAndResumed=not negative,
                originalElapsedPausedTimerDeleted=negative,
                presetDeduplicatedAndRestarted=True,
                stopwatchLapsAndPausedRestart=True, ownedFixtureStateCleaned=True,
                publishedBackendUnmodified=negative, transcript=transcript, realFrameContacted=False,
                soundVerified=False, sleepInhibitionVerified=False, browserVerified=False,
                physicalControllerVerified=False)
