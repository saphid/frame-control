"""Child-process EOF repair for the exact managed Deck Progress 1.3.6 ZIP.

Decky 3.3.0 returns an empty string after its IPC peer closes. Its original
server loop dispatches that string repeatedly without yielding. End only that
connection's loop; keep the socket active so another connection can be served.
"""
import asyncio


async def listen_for_method_call(self, reader, writer):
    self.server_writer = writer
    while self.active and self.on_new_message:
        line = await self._read_single_line(reader)
        if line == '':
            return

        def reply(task):
            result = task.result()
            if result is not None:
                asyncio.create_task(self._write_single_line(writer, result))

        asyncio.create_task(self.on_new_message(line)).add_done_callback(reply)


def install():
    # Plugins run in separate child processes. The parent loader and every
    # other plugin retain their original transport and authentication paths.
    from decky_loader.localplatform.localsocket import UnixSocket
    UnixSocket._listen_for_method_call = listen_for_method_call
