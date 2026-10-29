import asyncio
import asyncio.subprocess
import base64
from collections import deque
import hashlib
import json
import logging
import os
import secrets
import socket
import struct
import time
import typing

import decky  # type: ignore
from settings import SettingsManager  # type: ignore

PLUGIN_DIR = decky.DECKY_PLUGIN_DIR
PLUGIN_SETTINGS_DIR = decky.DECKY_PLUGIN_SETTINGS_DIR

logger = decky.logger
logger.setLevel(logging.DEBUG)
logger.info("Wine Cellar main.py https://github.com/FlashyReese/decky-wine-cellar")

logger.info('[backend] Settings path: {}'.format(PLUGIN_SETTINGS_DIR))
settings = SettingsManager(name="settings", settings_directory=PLUGIN_SETTINGS_DIR)
settings.read()


class FrameySocket:
    """One bounded connection to this plugin's loopback helper, not a public proxy."""
    ORIGIN = 'https://steamloopback.host'
    HOST = '127.0.0.1'
    PORT = 8887
    GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    LIMIT = 256 * 1024

    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.messages = deque()
        self.queued_size = 0
        self.event = asyncio.Event()
        self.send_lock = asyncio.Lock()
        self.last_poll = time.monotonic()
        self.closed = False
        self.task = None

    @classmethod
    async def connect(cls):
        reader, writer = await asyncio.wait_for(asyncio.open_connection(cls.HOST, cls.PORT), 3)
        try:
            key = base64.b64encode(os.urandom(16)).decode('ascii')
            request = (f'GET / HTTP/1.1\r\nHost: {cls.HOST}:{cls.PORT}\r\nUpgrade: websocket\r\n'
                       f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
                       f'Sec-WebSocket-Version: 13\r\nOrigin: {cls.ORIGIN}\r\n\r\n')
            writer.write(request.encode('ascii'))
            await writer.drain()
            response = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 3)
            if len(response) > 4096 or not response.startswith(b'HTTP/1.1 101 '):
                raise ValueError('Wine Cellar helper refused its fixed-origin connection')
            headers = {}
            for line in response.split(b'\r\n')[1:]:
                if not line:
                    break
                name, sep, value = line.partition(b':')
                if not sep:
                    raise ValueError('Invalid Wine Cellar handshake')
                headers[name.strip().lower()] = value.strip()
            expected = base64.b64encode(hashlib.sha1((key + cls.GUID).encode('ascii')).digest())
            if (headers.get(b'sec-websocket-accept') != expected or
                    headers.get(b'upgrade', b'').lower() != b'websocket' or
                    b'upgrade' not in headers.get(b'connection', b'').lower()):
                raise ValueError('Wine Cellar helper handshake mismatch')
            result = cls(reader, writer)
            result.task = asyncio.create_task(result.receive())
            return result
        except BaseException:
            writer.close()
            await writer.wait_closed()
            raise

    async def send_frame(self, opcode, body=b''):
        if self.closed:
            raise ValueError('Wine Cellar socket closed')
        if len(body) > self.LIMIT:
            raise ValueError('Wine Cellar message exceeds limit')
        mask = os.urandom(4)
        length = len(body)
        header = (struct.pack('!BB', 0x80 | opcode, 0x80 | length) if length < 126 else
                  struct.pack('!BBH', 0x80 | opcode, 0x80 | 126, length) if length < 65536 else
                  struct.pack('!BBQ', 0x80 | opcode, 0x80 | 127, length))
        async with self.send_lock:
            self.writer.write(header + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(body)))
            await self.writer.drain()

    async def receive(self):
        fragment = bytearray()
        try:
            while not self.closed and time.monotonic() - self.last_poll < 20:
                try:
                    first, second = await asyncio.wait_for(self.reader.readexactly(2), 5)
                except asyncio.TimeoutError:
                    continue
                opcode, length = first & 15, second & 127
                if second & 0x80:
                    raise ValueError('Wine Cellar server sent a masked frame')
                if length == 126:
                    length = struct.unpack('!H', await self.reader.readexactly(2))[0]
                elif length == 127:
                    length = struct.unpack('!Q', await self.reader.readexactly(8))[0]
                if length > self.LIMIT or len(fragment) + length > self.LIMIT:
                    raise ValueError('Wine Cellar response exceeds limit')
                body = await self.reader.readexactly(length)
                if opcode == 8:
                    break
                if opcode == 9:
                    await self.send_frame(10, body)
                    continue
                if opcode == 10:
                    continue
                if opcode not in (0, 1):
                    raise ValueError('Wine Cellar sent an unsupported frame')
                fragment.extend(body)
                if first & 0x80:
                    if len(self.messages) >= 32 or self.queued_size + len(fragment) > self.LIMIT:
                        raise ValueError('Wine Cellar response queue is full')
                    self.messages.append(fragment.decode('utf-8'))
                    self.queued_size += len(fragment)
                    fragment.clear()
                    self.event.set()
        except (OSError, ValueError, UnicodeError, asyncio.IncompleteReadError) as error:
            logger.warning('Wine Cellar Framey socket closed: %s', error)
        finally:
            self.closed = True
            self.event.set()
            self.writer.close()
            await self.writer.wait_closed()

    async def close(self):
        self.closed = True
        self.event.set()
        self.writer.close()
        await self.writer.wait_closed()
        if self.task and self.task is not asyncio.current_task():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


class Plugin:
    BACKEND_PATH = f"{PLUGIN_DIR}/bin/backend"
    BACKEND_ADDRESS = None
    BACKEND_PROC: typing.Optional[asyncio.subprocess.Process] = None
    BACKEND_WATCH_TASK: typing.Optional[asyncio.Task[None]] = None
    BACKEND_STOPPING = False
    BACKEND_RESTART_DELAY_SECONDS = 2
    FRAMEY_SOCKETS = {}

    @classmethod
    async def _spawn_backend(cls):
        logger.info("Starting Wine Cask (the Wine Cellar backend)...")
        # The official frontend's fixed URL is intercepted by Framey. Bind
        # this managed helper to a private loopback port so it cannot collide
        # with another Wine Cellar process in the user's Steam session.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        cls.BACKEND_ADDRESS = f'127.0.0.1:{port}'
        FrameySocket.PORT = port
        cls.BACKEND_PROC = await asyncio.subprocess.create_subprocess_exec(cls.BACKEND_PATH, cls.BACKEND_ADDRESS)
        logger.info(f"Wine Cask started with PID {cls.BACKEND_PROC.pid}")

    @classmethod
    async def _backend_supervisor(cls):
        while not cls.BACKEND_STOPPING:
            try:
                await cls._spawn_backend()
            except Exception:
                logger.exception("Failed to start Wine Cask")
                await asyncio.sleep(cls.BACKEND_RESTART_DELAY_SECONDS)
                continue

            backend_proc = cls.BACKEND_PROC
            if backend_proc is None:
                await asyncio.sleep(cls.BACKEND_RESTART_DELAY_SECONDS)
                continue

            returncode = await backend_proc.wait()
            if cls.BACKEND_PROC is backend_proc:
                cls.BACKEND_PROC = None

            if cls.BACKEND_STOPPING:
                logger.info(f"Wine Cask stopped with exit code {returncode}")
                return

            logger.error(
                f"Wine Cask exited unexpectedly with exit code {returncode}; restarting..."
            )
            await asyncio.sleep(cls.BACKEND_RESTART_DELAY_SECONDS)

    @classmethod
    async def _start_backend_supervisor(cls):
        if cls.BACKEND_WATCH_TASK is not None and not cls.BACKEND_WATCH_TASK.done():
            logger.warning("Wine Cask supervisor is already running!")
            return

        cls.BACKEND_STOPPING = False
        cls.BACKEND_WATCH_TASK = asyncio.create_task(cls._backend_supervisor())

    @classmethod
    async def _stop_backend(cls):
        cls.BACKEND_STOPPING = True

        if cls.BACKEND_PROC is None:
            logger.warning("Wine Cask is not running!")
        else:
            logger.info("Terminating Wine Cask (the Wine Cellar backend)...")
            cls.BACKEND_PROC.terminate()

            try:
                await asyncio.wait_for(cls.BACKEND_PROC.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Wine Cask did not exit after SIGTERM, killing process...")
                cls.BACKEND_PROC.kill()
                await cls.BACKEND_PROC.wait()

            cls.BACKEND_PROC = None

        watch_task = cls.BACKEND_WATCH_TASK
        if watch_task is not None and watch_task is not asyncio.current_task():
            try:
                await asyncio.wait_for(watch_task, timeout=6)
            except asyncio.TimeoutError:
                watch_task.cancel()
            except asyncio.CancelledError:
                pass
        cls.BACKEND_WATCH_TASK = None

    @classmethod
    async def _main(cls):
        if cls.BACKEND_WATCH_TASK is not None and not cls.BACKEND_WATCH_TASK.done():
            logger.warning("Wine Cask is already running!")
            return

        await cls._start_backend_supervisor()

    @classmethod
    async def _unload(cls):
        for token in list(cls.FRAMEY_SOCKETS):
            await cls.framey_ws_close(token)
        await cls._stop_backend()

    @classmethod
    async def framey_ws_open(cls):
        for token, sock in list(cls.FRAMEY_SOCKETS.items()):
            if sock.closed or time.monotonic() - sock.last_poll >= 20:
                await cls.framey_ws_close(token)
        if (cls.BACKEND_PROC is None or cls.BACKEND_PROC.returncode is not None or
                len(cls.FRAMEY_SOCKETS) >= 2):
            raise ValueError('Wine Cellar helper unavailable or socket limit reached')
        sock = await FrameySocket.connect()
        token = secrets.token_hex(16)
        cls.FRAMEY_SOCKETS[token] = sock
        return token

    @classmethod
    async def framey_ws_send(cls, token, text):
        sock = cls.FRAMEY_SOCKETS.get(token)
        if sock is None or sock.closed or not isinstance(text, str) or len(text.encode('utf-8')) > 65536:
            raise ValueError('Wine Cellar socket or message unavailable')
        payload = json.loads(text)
        if not isinstance(payload, dict) or payload.get('type') not in ('GetState', 'ReportSteamVisibleTools', 'Command'):
            raise ValueError('Unsupported Wine Cellar message')
        if payload['type'] == 'Command':
            command = payload.get('command')
            if not isinstance(command, dict) or command.get('type') not in (
                    'RefreshCatalog', 'InstallCatalogRelease', 'UninstallInstalledTool', 'CancelOperation'):
                raise ValueError('Unsupported Wine Cellar command')
            if any(not isinstance(value, str) or len(value) > 128 for key, value in command.items() if key != 'type'):
                raise ValueError('Invalid Wine Cellar command ID')
        elif payload['type'] == 'ReportSteamVisibleTools':
            if not isinstance(payload.get('steam_visible_tools'), list) or len(payload['steam_visible_tools']) > 256:
                raise ValueError('Invalid Wine Cellar tool list')
        await sock.send_frame(1, text.encode('utf-8'))

    @classmethod
    async def framey_ws_poll(cls, token):
        sock = cls.FRAMEY_SOCKETS.get(token)
        if sock is None:
            raise ValueError('Wine Cellar socket unavailable')
        sock.last_poll = time.monotonic()
        if not sock.messages and not sock.closed:
            try:
                await asyncio.wait_for(sock.event.wait(), 1)
            except asyncio.TimeoutError:
                pass
        sock.event.clear()
        messages = list(sock.messages)
        sock.messages.clear()
        sock.queued_size = 0
        return {'messages': messages, 'closed': sock.closed}

    @classmethod
    async def framey_ws_close(cls, token):
        sock = cls.FRAMEY_SOCKETS.pop(token, None)
        if sock is not None:
            await sock.close()

    @classmethod
    async def restart_backend(cls):
        await cls._stop_backend()
        await cls._start_backend_supervisor()

    @classmethod
    async def settings_read(cls):
        logger.info('Reading settings')
        return settings.read()

    @classmethod
    async def settings_commit(cls):
        logger.info('Saving settings')
        return settings.commit()

    @classmethod
    async def settings_getSetting(cls, key: str, defaults):
        logger.info('Get {}'.format(key))
        return settings.getSetting(key, defaults)

    @classmethod
    async def settings_setSetting(cls, key: str, value):
        logger.info('Set {}: {}'.format(key, value))
        return settings.setSetting(key, value)
