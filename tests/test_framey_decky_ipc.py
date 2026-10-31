"""A closed IPC peer cannot starve unload; other connections still work."""
import sandbox  # noqa: F401
import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
from framey_decky_ipc import repair_socket


class Socket:
    active = True
    reads = 0

    def __init__(self):
        self.messages = []
        self.replies = []

    async def _read_single_line(self, reader):
        self.reads += 1
        if self.reads > 100:
            raise AssertionError('EOF loop starved the event loop')
        return (await reader.readline()).decode()

    async def on_new_message(self, line):
        self.messages.append(line)
        return 'reply:'+line

    async def _write_single_line(self, writer, result):
        self.replies.append((writer, result))

    async def _listen_for_method_call(self, reader, writer):
        while self.active:
            line = await self._read_single_line(reader)
            result = await self.on_new_message(line)
            await self._write_single_line(writer, result)


class ChildIpcEof(unittest.IsolatedAsyncioTestCase):
    def socket(self):
        socket_type = type('PrivateSocket', (Socket,), {})
        repair_socket(socket_type)
        return socket_type()

    async def test_closed_peer_returns_without_dispatch_or_starvation(self):
        socket = self.socket()
        reader = asyncio.StreamReader()
        reader.feed_eof()
        heartbeat = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().call_soon(heartbeat.set_result, True)
        await socket._listen_for_method_call(reader, object())
        self.assertTrue(await heartbeat)
        self.assertEqual(socket.reads, 1)
        self.assertEqual(socket.messages, [])
        self.assertEqual(socket.replies, [])
        self.assertTrue(socket.active)

    async def test_frames_partial_final_frame_and_later_connection_are_preserved(self):
        socket = self.socket()
        writers = [object(), object()]
        for data, writer in zip((b'first\n\npartial', b'second\n'), writers):
            reader = asyncio.StreamReader()
            reader.feed_data(data)
            reader.feed_eof()
            await socket._listen_for_method_call(reader, writer)
        self.assertEqual(socket.messages, ['first\n', '\n', 'partial', 'second\n'])
        self.assertEqual(socket.replies, [(writers[0], 'reply:first\n'),
                         (writers[0], 'reply:\n'), (writers[0], 'reply:partial'),
                         (writers[1], 'reply:second\n')])
        self.assertTrue(socket.active)

    async def test_inactive_socket_does_not_read_or_dispatch(self):
        socket = self.socket()
        socket.active = False
        reader = asyncio.StreamReader()
        reader.feed_eof()
        await socket._listen_for_method_call(reader, object())
        self.assertEqual(socket.reads, 0)
        self.assertEqual(socket.messages, [])

    async def test_original_dispatch_errors_are_not_swallowed(self):
        socket = self.socket()

        async def failed_message(line):
            raise ValueError('private dispatch failure')

        socket.on_new_message = failed_message
        reader = asyncio.StreamReader()
        reader.feed_data(b'message\n')
        reader.feed_eof()
        with self.assertRaisesRegex(ValueError, 'private dispatch failure'):
            await socket._listen_for_method_call(reader, object())
