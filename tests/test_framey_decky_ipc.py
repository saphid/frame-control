"""A closed IPC peer cannot starve unload; other connections still work."""
import sandbox  # noqa: F401
import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
from framey_decky_ipc import listen_for_method_call


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


class ChildIpcEof(unittest.IsolatedAsyncioTestCase):
    async def test_closed_peer_returns_without_dispatch_or_starvation(self):
        socket = Socket()
        reader = asyncio.StreamReader()
        reader.feed_eof()
        heartbeat = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().call_soon(heartbeat.set_result, True)
        await listen_for_method_call(socket, reader, object())
        self.assertTrue(await heartbeat)
        self.assertEqual(socket.reads, 1)
        self.assertEqual(socket.messages, [])
        self.assertEqual(socket.replies, [])
        self.assertTrue(socket.active)

    async def test_frames_partial_final_frame_and_later_connection_are_preserved(self):
        socket = Socket()
        writers = [object(), object()]
        for data, writer in zip((b'first\n\npartial', b'second\n'), writers):
            reader = asyncio.StreamReader()
            reader.feed_data(data)
            reader.feed_eof()
            await listen_for_method_call(socket, reader, writer)
        # Join the real dispatch tasks and their done callbacks.
        await asyncio.gather(*(task for task in asyncio.all_tasks()
                               if task is not asyncio.current_task()))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(socket.messages, ['first\n', '\n', 'partial', 'second\n'])
        self.assertEqual(socket.replies, [(writers[0], 'reply:first\n'),
                         (writers[0], 'reply:\n'), (writers[0], 'reply:partial'),
                         (writers[1], 'reply:second\n')])
        self.assertTrue(socket.active)

    async def test_inactive_socket_does_not_read_or_dispatch(self):
        socket = Socket()
        socket.active = False
        reader = asyncio.StreamReader()
        reader.feed_eof()
        await listen_for_method_call(socket, reader, object())
        self.assertEqual(socket.reads, 0)
        self.assertEqual(socket.messages, [])
