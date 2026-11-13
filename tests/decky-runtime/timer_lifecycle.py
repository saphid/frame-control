"""Simple Timer lifecycle through actual Decky instance dispatch, never Plugin()."""
import asyncio
import json
import time
import urllib.request

import websockets


class Client:
    def __init__(self, name, transcript):
        self.transcript = transcript
        self.name = name
        self.sequence = 0
        self.events = []

    async def __aenter__(self):
        token = urllib.request.urlopen('http://127.0.0.1:1337/auth/token', timeout=2).read().decode()
        self.ws = await websockets.connect('ws://127.0.0.1:1337/ws?auth='+token)
        return self

    async def __aexit__(self, *_):
        await self.ws.close()

    async def receive(self, timeout=8):
        response = json.loads(await asyncio.wait_for(self.ws.recv(), timeout))
        if response.get('type') == 5 and response.get('event') == 'loader/plugin_event':
            event = response['args'][0]
            if event['plugin'] == self.name:
                self.events.append(event)
                self.transcript.append(dict(kind="event", event=event))
        return response

    async def call(self, method, *args, success=True):
        self.sequence += 1
        await self.ws.send(json.dumps({'type': 0, 'id': self.sequence,
            'route': 'loader/call_plugin_method', 'args': [self.name, method, *args]}))
        while True:
            response = await self.receive()
            if response.get('id') != self.sequence:
                continue
            await self.ws.send(json.dumps({'type': 3, 'id': self.sequence}))
            self.transcript.append(dict(kind='rpc', method=method, args=list(args), response=response))
            if success:
                assert response['type'] == 1, response
                return response['result']
            return response

    async def seconds(self):
        offset = len(self.events)
        await self.call('load_remaining_seconds')
        while not any(e['event'] == 'simple_timer_seconds_updated' for e in self.events[offset:]):
            await self.receive()
        return next(e['args'][0] for e in reversed(self.events)
                    if e['event'] == 'simple_timer_seconds_updated')

    async def drain(self, seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            try:
                await self.receive(max(.01, deadline-time.monotonic()))
            except TimeoutError:
                break


async def initial(name, negative, transcript):
    async with Client(name, transcript) as client:
        await client.call('set_subtle_mode', True)  # No sound or physical actions.
        response = await client.call('cancel_timer', success=False)
        if negative:
            assert response['type'] == -1 and 'timer_task' in str(response), response
        else:
            assert response['type'] == 1, response
        await client.call('start_timer', 60)
        end = await client.call('settings_getSetting', 'timer_end', None)
        assert end > time.time()
        await client.call('cancel_timer')
        saved = await client.call('settings_getSetting', 'timer_end', None)
        assert (saved is not None) if negative else (saved is None), saved
        await client.call('start_timer', 1)
        await client.call('start_timer', 60)
        await client.drain(6.5)  # Past upstream's 5-second tick and first timer's expiry.
        completed = [e for e in client.events if e['event'] == 'simple_timer_event']
        if negative:
            assert completed, client.events
        else:
            assert not completed, completed
            assert await client.seconds() > 45
        await client.call('cancel_timer')
        if negative:
            return {'freshCancelError': response, 'cancelRetainsEnd': True,
                    'replacedTimerStillFires': True}
        await client.call('start_timer', 1)
        client.events.clear()
        await client.drain(5.5)
        completed = [e for e in client.events if e['event'] == 'simple_timer_event']
        assert len(completed) == 1 and completed[0]['args'] == ['Your session has ended!', True], completed
        assert await client.seconds() == 0
        assert await client.call('settings_getSetting', 'timer_end', None) is None
        client.events.clear()
        await client.call('start_timer', -20)  # An already expired, private silent deadline.
        await client.drain(.3)
        expired = [e for e in client.events if e['event'] == 'simple_timer_event']
        assert len(expired) == 1 and expired[0]['args'] == ['Your timer has expired!', True], expired
        assert await client.call('settings_getSetting', 'timer_end', None) is None
        await client.call('start_timer', 60)
        return {'end': await client.call('settings_getSetting', 'timer_end', None),
                'recents': await client.call('settings_getSetting', 'recent_timers_seconds', [])}


async def resumed(name, saved, transcript):
    async with Client(name, transcript) as client:
        assert 0 < await client.seconds() < 60
        assert await client.call('settings_getSetting', 'timer_end', None) == saved['end']
        assert await client.call('settings_getSetting', 'recent_timers_seconds', []) == saved['recents']
        await client.call('cancel_timer')
        assert await client.call('settings_getSetting', 'timer_end', None) is None


async def idle(name, transcript):
    async with Client(name, transcript) as client:
        assert await client.seconds() == 0
        assert await client.call('settings_getSetting', 'timer_end', None) is None
        await client.call('cancel_timer')  # Idempotent before any new timer.
        assert await client.call('settings_getSetting', 'subtle_mode', False) is True


def probe(name, restart, log, negative=False, *, unload_regression=False):
    transcript = []
    saved = asyncio.run(initial(name, negative, transcript))
    if unload_regression:
        restart()
        return dict(priorManagedUnloadRegression=True, activeTimer=saved, transcript=transcript)
    if negative:
        restart({'timer_end': time.time()-60, 'subtle_mode': True})
        asyncio.run(read_after_startup(name, transcript))
        assert "has no attribute 'timer_task'" in log.read_text(), log.read_text()[-6000:]
        return saved | {'expiredRestartError': True, 'transcript': transcript}
    restart()
    asyncio.run(resumed(name, saved, transcript))
    restart()
    asyncio.run(idle(name, transcript))
    restart({'timer_end': time.time()-60, 'subtle_mode': True})
    asyncio.run(idle(name, transcript))
    return {'freshCancel': True, 'replacementSuppressesOldCompletion': True,
            'completionClearsEnd': True, 'lateExpiryEmitsWithoutSelfCancel': True,
            'activeRestartPreservesDeadlineAndRecents': True,
            'canceledRestartIdle': True, 'expiredRestartIdle': True, 'transcript': transcript}


async def read_after_startup(name, transcript):
    async with Client(name, transcript) as client:
        # _main is scheduled independently; allow it to finish before reading its journal.
        await client.call('settings_getSetting', 'subtle_mode', False)
        await client.drain(.3)
