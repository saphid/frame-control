"""Real private Unix IPC, exact managed archive; no live Discord or Steam."""
import sandbox  # noqa: F401
import asyncio
from contextlib import ExitStack
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

import framey_official
import test_frame_decky_store as transactions

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('discord_private', ROOT/'tests/decky-runtime/discord_private.py')
private = importlib.util.module_from_spec(spec)
spec.loader.exec_module(private)


@unittest.skipIf(os.name == 'nt', 'managed plugin transaction and private IPC require POSIX')
class DiscordLifecycle(unittest.TestCase):
    def setUp(self):
        self.transaction = transactions.StoreTransaction()
        self.transaction.setUp()
        self.addCleanup(self.transaction.doCleanups)
        self.record = next(p for p in framey_official.PLUGINS if p['id'] == 37)
        self.data = framey_official.archive(self.record)
        result = self.transaction.apply('install', self.data, plugin_id=37,
            folder=self.record['folder'], version=self.record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.folder = self.transaction.folder.parent/self.record['folder']
        fixtures = ExitStack()
        self.addCleanup(fixtures.close)
        self.temp = fixtures.enter_context(tempfile.TemporaryDirectory(prefix='framey-dipc-', dir='/tmp'))
        fixtures.enter_context(patch.dict(os.environ, XDG_RUNTIME_DIR=self.temp))
        self.peer = fixtures.enter_context(private.Peer(Path(self.temp)/'discord-ipc-0'))
        stubs = {'decky': types.SimpleNamespace(logger=logging.getLogger('fixture-discord')),
                 'framey_decky_ipc': types.SimpleNamespace(install=lambda: None)}
        helper = self.folder/'py_modules/framey_discord_lifecycle.py'
        if helper.exists():
            module = types.ModuleType('framey_discord_lifecycle')
            exec(compile(helper.read_bytes(), str(helper), 'exec'), module.__dict__)
            stubs['framey_discord_lifecycle'] = module
        self.module = types.ModuleType('fixture_discord_plugin')
        with patch.dict(sys.modules, stubs):
            exec(compile((self.folder/'main.py').read_bytes(), 'managed-discord.py', 'exec'), self.module.__dict__)
        self.plugin = self.module.Plugin()

    @staticmethod
    def activity(name='Private fixture game'):
        return dict(imageUrl='https://example.invalid/private.png', startTime=1700000000,
                    details=dict(name=name))

    def call(self, method, *args):
        return asyncio.run(getattr(self.plugin, method)(*args))

    def assert_closed(self, index):
        row = self.peer.closed(index)
        self.assertFalse(row['fixtureClosed'])
        self.assertIsNone(row['error'])
        self.assertEqual(row['frames'][-1]['op'], 2, 'close frame must precede EOF')
        self.assertEqual(row['frames'][-1]['payload'], {})
        return row

    def test_replacement_and_unload_send_close_before_client_eof(self):
        self.assertTrue(self.call('update_activity', self.activity()))
        self.assertTrue(self.call('update_activity', self.activity('Second private game')))
        first = self.assert_closed(0)
        self.assertEqual([f['op'] for f in first['frames']], [0, 1, 2])
        self.call('_unload')
        self.assert_closed(1)
        self.assertIsNone(self.plugin.pipe)

    def test_fresh_clear_disconnect_and_repeated_unload_are_idle(self):
        self.assertFalse(self.call('clear_activity'))
        self.call('disconnect')
        self.call('_unload')
        self.call('_unload')
        self.assertEqual(self.peer.connections, [])

    def test_clear_sends_empty_activity_then_closes(self):
        self.assertTrue(self.call('update_activity', self.activity()))
        self.assertTrue(self.call('clear_activity'))
        row = self.assert_closed(0)
        self.assertEqual([f['op'] for f in row['frames']], [0, 1, 1, 2])
        self.assertEqual(row['frames'][-2]['payload']['cmd'], 'SET_ACTIVITY')
        self.assertNotIn('activity', row['frames'][-2]['payload']['args'])
        self.assertIsNone(self.plugin.pipe)

    def test_rejected_handshake_closes_without_activity_and_can_retry(self):
        self.peer.reject_next = True
        self.assertFalse(self.call('update_activity', self.activity()))
        row = self.assert_closed(0)
        self.assertEqual([f['op'] for f in row['frames']], [0, 2])
        self.assertIsNone(self.plugin.pipe)
        self.assertTrue(self.call('update_activity', self.activity()))
        self.call('disconnect')
        self.assert_closed(1)

    def test_closed_peer_still_releases_owned_socket(self):
        local, remote = socket.socketpair()
        self.addCleanup(local.close)
        remote.close()
        pipe = self.module.Pipe.__new__(self.module.Pipe)
        pipe.socket, pipe.connected = local, True
        self.plugin.pipe = pipe
        self.call('disconnect')
        self.assertEqual(local.fileno(), -1)
        self.assertIsNone(pipe.socket)
        self.assertIsNone(self.plugin.pipe)

    def test_installed_helpers_and_original_archive_bytes(self):
        import frame_decky_store
        receipt = json.loads((self.folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['discord-status-pipe-lifecycle', 'discord-status-ipc-eof'])
        import framey_compatibility
        args = (37, self.record['sha256'], self.record['version'])
        current = framey_compatibility.lookup(*args, installed_shims=receipt['compatShims'])
        previous = framey_compatibility.lookup(*args, installed_shims=[])
        self.assertEqual(current['status'], 'partial')
        self.assertEqual(previous['status'], 'partial')
        self.assertTrue(previous['reason'].startswith('Update or reinstall'))
        self.assertFalse(current['reason'].startswith('Update or reinstall'))

        prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                  b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
        suffix = (b'\nfrom framey_discord_lifecycle import install as _framey_discord_lifecycle\n'
                  b'_framey_discord_lifecycle(Plugin, Pipe)\ndel _framey_discord_lifecycle\n')
        with zipfile.ZipFile(io.BytesIO(self.data)) as original:
            for member in original.infolist():
                if member.is_dir():
                    continue
                relative = member.filename.split('/', 1)[1]
                expected = original.read(member)
                if relative == 'main.py':
                    expected = prefix + expected + suffix
                self.assertEqual((self.folder/relative).read_bytes(), expected, relative)
        for name in ('framey_decky_ipc.py', 'framey_discord_lifecycle.py'):
            self.assertEqual((self.folder/'py_modules'/name).read_bytes(), (ROOT/'ui'/name).read_bytes())

    def test_changed_archive_is_not_adapted(self):
        self.assertEqual(self.transaction.apply('remove', plugin_id=37, folder=self.record['folder']).returncode, 0)
        changed = io.BytesIO(self.data)
        with zipfile.ZipFile(changed, 'a') as bundle:
            bundle.writestr(self.record['folder']+'/different-release.txt', 'unrecognized archive')
        result = self.transaction.apply('install', changed.getvalue(), plugin_id=37,
            folder=self.record['folder'], version=self.record['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.folder/'.frame-control-store.json').read_text()).get('compatShims', []), [])
        with zipfile.ZipFile(io.BytesIO(self.data)) as original:
            self.assertEqual((self.folder/'main.py').read_bytes(), original.read(self.record['folder']+'/main.py'))
        self.assertFalse((self.folder/'py_modules/framey_discord_lifecycle.py').exists())
        self.assertFalse((self.folder/'py_modules/framey_decky_ipc.py').exists())

    def test_missing_helpers_refuse_incomplete_install(self):
        import frame_decky_store
        self.assertEqual(self.transaction.apply('remove', plugin_id=37, folder=self.record['folder']).returncode, 0)
        delivered = frame_decky_store.apply_script(37, self.record['sha256'])
        for key in ('FRAMEY_DISCORD_IPC_SOURCE', 'FRAMEY_DISCORD_LIFECYCLE_SOURCE'):
            incomplete = '\n'.join(line for line in delivered.splitlines() if not line.startswith(key+' = '))+'\n'
            with self.subTest(missing=key), patch.object(frame_decky_store, 'apply_script', return_value=incomplete):
                result = self.transaction.apply('install', self.data, plugin_id=37,
                    folder=self.record['folder'], version=self.record['version'])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Missing Discord Status lifecycle repair', result.stderr)
                self.assertFalse(self.folder.exists())
