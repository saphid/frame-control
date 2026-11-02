"""Owned pipe cleanup for the exact managed Discord Status 1.5.0 backend.

Keep the published handshake/activity payloads. Close each prior connection
before replacement, including failed handshakes, and await unload cleanup.
"""
import socket


def install(plugin_type, pipe_type):
    original_update = plugin_type.update_activity
    original_clear = plugin_type.clear_activity
    original_close = pipe_type.disconnect

    def initialize(self):
        self.pipe = None

    def close(self):
        try:
            if self.socket is not None and self.connected:
                original_close(self)
        finally:
            # Upstream closes only after a successful CLOSE-frame send. A
            # disappeared peer must not retain the owned socket or state.
            owned, self.socket = self.socket, None
            self.connected = False
            if owned is not None:
                try:
                    owned.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                owned.close()

    async def disconnect(self):
        owned, self.pipe = self.pipe, None
        if owned is not None:
            try:
                owned.disconnect()
            except OSError:
                # Closing a peer that has already exited remains idempotent.
                # close() has released the descriptor in its finally block.
                pass

    async def update(self, activity):
        await disconnect(self)
        try:
            result = await original_update(self, activity)
            if not result:
                await disconnect(self)
            return result
        except BaseException:
            await disconnect(self)
            raise

    async def clear(self):
        try:
            return await original_clear(self)
        finally:
            await disconnect(self)

    async def unload(self):
        await disconnect(self)

    pipe_type.disconnect = close
    plugin_type.__init__ = initialize
    plugin_type.disconnect = disconnect
    plugin_type.update_activity = update
    plugin_type.clear_activity = clear
    plugin_type._unload = unload
