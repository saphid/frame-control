"""Private silent AlarMe lifecycle through published Decky's actual API1 RPC/events."""
import asyncio
from timer_lifecycle import Client


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
