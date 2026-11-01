"""Own only this plugin's connection and names on the configured user bus."""
import asyncio
import os

NAMES = ('org.freedesktop.PowerManagement', 'org.freedesktop.ScreenSaver',
         'org.gnome.SessionManager')


def install(namespace):
    from dbus_next.constants import NameFlag, RequestNameReply

    plugin = namespace['Plugin']
    original_unload = plugin._unload
    original_events = plugin.get_event
    lock = asyncio.Lock()
    owned = None
    closed = False

    def clear():
        namespace['BaseInterface'].request_map.clear()
        events = namespace['event_queue']
        while not events.empty():
            events.get_nowait()

    async def disconnect(bus):
        if bus is not None:
            bus.disconnect()
            await asyncio.wait_for(bus.wait_for_disconnect(), 2)

    async def stop_owned():
        nonlocal owned
        bus, owned = owned, None
        namespace['bus'] = None
        clear()
        await disconnect(bus)

    async def start():
        nonlocal owned
        async with lock:
            if closed:
                return False
            await stop_owned()
            address = os.environ.get('DBUS_SESSION_BUS_ADDRESS')
            if not address:
                return False
            candidate = None
            try:
                candidate = namespace['MessageBus'](bus_address=address)
                await asyncio.wait_for(candidate.connect(), 3)
                screen = namespace['InhibitInterface']()
                for path, interface in (
                    ('/ScreenSaver', screen), ('/org/freedesktop/ScreenSaver', screen),
                    ('/org/freedesktop/PowerManagement/Inhibit', namespace['PMInhibitInterface']()),
                    ('/org/gnome/SessionManager', namespace['GnomeInterface']()),
                ):
                    candidate.export(path, interface)
                for name in NAMES:
                    reply = await asyncio.wait_for(candidate.request_name(name, NameFlag.DO_NOT_QUEUE), 2)
                    if reply not in (RequestNameReply.PRIMARY_OWNER, RequestNameReply.ALREADY_OWNER):
                        raise RuntimeError('Existing session service owns '+name)
                owned = candidate
                namespace['bus'] = candidate
                return True
            except Exception as error:
                namespace['decky_plugin'].logger.warning('ScreenSaver bus start refused: %s', error)
                await disconnect(candidate)
                return False

    async def stop():
        async with lock:
            await stop_owned()

    async def start_backend(self):
        return await start()

    async def stop_backend(self):
        await stop()

    async def is_running(self):
        return owned is not None and owned.connected

    async def get_event(self):
        async with lock:
            return await original_events(self) if await is_running(self) else []

    async def unload(self):
        nonlocal closed
        async with lock:
            closed = True
            await stop_owned()
        await original_unload(self)

    plugin.start_backend = start_backend
    plugin.stop_backend = stop_backend
    plugin.is_running = is_running
    plugin.get_event = get_event
    plugin._unload = unload
    plugin._uninstall = unload
    namespace['start_dbus'] = start
    namespace['stop_dbus'] = stop
