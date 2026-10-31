"""Child-process EOF repair for exact managed plugin archives.

Decky 3.3.0 returns an empty string after its IPC peer closes. Its original
server loop dispatches that string repeatedly without yielding. End only that
connection's loop; keep the socket active so another connection can be served.
"""
class _PeerClosed(Exception):
    pass


def repair_socket(socket_type):
    original_read = socket_type._read_single_line
    original_listen = socket_type._listen_for_method_call

    async def read(self, reader):
        line = await original_read(self, reader)
        if line == '' and reader.at_eof():
            raise _PeerClosed
        return line

    async def listen(self, reader, writer):
        try:
            await original_listen(self, reader, writer)
        except _PeerClosed:
            return

    # Delegate framing, dispatch, replies and exceptions to the original
    # implementation. Only this private EOF signal ends the connection loop.
    socket_type._read_single_line = read
    socket_type._listen_for_method_call = listen


def install():
    # Plugins run in separate child processes. The parent loader and every
    # other plugin retain their original transport and authentication paths.
    from decky_loader.localplatform.localsocket import UnixSocket
    repair_socket(UnixSocket)
