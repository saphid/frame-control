"""Exercise the vendored Wine Cellar bridge without Decky or a headset."""
import sandbox  # noqa: F401
import ast
import asyncio
import base64
from collections import deque
import hashlib
import json
import logging
import os
from pathlib import Path
import struct
import time
import unittest


SOURCE = Path(__file__).resolve().parent.parent/'ui/vendor/wine-cellar-0.2.1/main.py'


def socket_class():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'FrameySocket')
    scope = dict(asyncio=asyncio, base64=base64, deque=deque, hashlib=hashlib, os=os,
                 struct=struct, time=time, logger=logging.getLogger('wine-test'))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), scope)
    return scope['FrameySocket']


class WineSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_origin_masked_request_and_state_reply(self):
        captured = {}

        async def helper(reader, writer):
            try:
                request = await reader.readuntil(b'\r\n\r\n')
                captured['origin'] = b'Origin: https://steamloopback.host\r\n' in request
                key = next(line.split(b':', 1)[1].strip() for line in request.split(b'\r\n')
                           if line.lower().startswith(b'sec-websocket-key:'))
                accept = base64.b64encode(hashlib.sha1(key + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n'
                             b'Connection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + b'\r\n\r\n')
                await writer.drain()
                first, second = await reader.readexactly(2)
                captured['masked'] = bool(second & 0x80) and first == 0x81
                length = second & 127
                mask = await reader.readexactly(4)
                body = await reader.readexactly(length)
                captured['message'] = bytes(byte ^ mask[i % 4] for i, byte in enumerate(body)).decode()
                reply = json.dumps({'type':'UpdateState', 'app_state':{'installed_tools':[]}}).encode()
                writer.write(bytes([0x81, len(reply)]) + reply)
                await writer.drain()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(helper, '127.0.0.1', 0)
        cls = socket_class()
        cls.PORT = server.sockets[0].getsockname()[1]
        try:
            sock = await cls.connect()
            try:
                await sock.send_frame(1, b'{"type":"GetState"}')
                await asyncio.wait_for(sock.event.wait(), 2)
                self.assertEqual(json.loads(sock.messages.popleft())['type'], 'UpdateState')
                self.assertEqual(captured, {'origin':True, 'masked':True, 'message':'{"type":"GetState"}'})
            finally:
                await sock.close()
        finally:
            server.close()
            await server.wait_closed()

    async def test_refuses_untrusted_handshake(self):
        async def helper(reader, writer):
            await reader.readuntil(b'\r\n\r\n')
            writer.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(helper, '127.0.0.1', 0)
        cls = socket_class()
        cls.PORT = server.sockets[0].getsockname()[1]
        try:
            with self.assertRaisesRegex(ValueError, 'refused'):
                await cls.connect()
        finally:
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    unittest.main()
