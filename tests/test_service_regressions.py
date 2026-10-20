"""Offline production-seam coverage for SERVICES01–04; no headset or provider calls."""
import sandbox  # noqa: F401
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import server
import frame_agent as agent
import frame_android as android


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.active = {'id': 'a', 'name': 'Headset A'}
        self.link = mock.Mock()
        self.link.active_device.side_effect = lambda: dict(self.active)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(server, 'LINK', self.link))
        self.stack.enter_context(mock.patch.object(server, 'PRIVATE', False))
        self.stack.enter_context(mock.patch.object(server, '_work', [0]))
        self.stack.enter_context(mock.patch.object(server, '_backfill', {'running': False, 'last': 0.0}))
        self.stack.enter_context(mock.patch.object(server.macview, 'retarget'))
        self.stack.enter_context(mock.patch.object(server._input, 'stop'))
        self.stack.enter_context(mock.patch.object(server.frame_link, 'devices_action', self.switch))

    def switch(self, link, body, setup, busy):
        if busy():
            raise server.frame_devices.DeviceError('Wait for work')
        self.active.update(id='b', name='Headset B')
        return {'message': 'switched'}

    def test_route_closes_touch_and_never_sends_to_old_process(self):
        touch = server.TouchAgent()
        proc = mock.Mock()
        proc.poll.return_value = None
        touch.proc, touch.status = proc, {'state': 'ready'}
        before = (server.FRAME, list(server.HOST_OPTS))
        try:
            with mock.patch.object(server, '_touch', touch), mock.patch.object(touch, 'start'):
                server.route('headset-b', [])
                result = server.remote_touch({'events': [{'dx': 17, 'dy': -4}]})
                self.assertFalse(result['sent'])
                self.assertEqual(touch.status['state'], 'off')
                proc.stdin.write.assert_not_called()
                self.assertTrue(proc.stdin.close.called or proc.terminate.called)
        finally:
            server.route(*before)

    def test_route_invalidates_touch_start_already_inside_popen(self):
        touch = server.TouchAgent()
        touch.launching = touch.generation
        proc = mock.Mock()
        proc.poll.return_value = None
        entered, release = threading.Event(), threading.Event()
        before = (server.FRAME, list(server.HOST_OPTS))
        def popen(*a, **kw):
            entered.set()
            if not release.wait(2):
                raise AssertionError('test did not release launch')
            return proc
        with mock.patch.object(server, '_touch', touch), \
                mock.patch.object(server, 'ensure_master'), \
                mock.patch.object(server.subprocess, 'Popen', side_effect=popen), \
                mock.patch.object(touch, '_watch', return_value=(False, True)):
            thread = threading.Thread(target=touch._launch, args=(0,))
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                server.route('headset-b', [])
                release.set()
                thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertIsNone(touch.proc)
                self.assertEqual(touch.status['state'], 'off')
                self.assertTrue(proc.terminate.called or proc.stdin.close.called)
            finally:
                release.set()
                thread.join(2)
                server._live_tunnels.discard(proc)
                server.route(*before)

    def test_backfill_counts_work_until_error_cleanup(self):
        entered, release = threading.Event(), threading.Event()
        writes = []
        def check(*a, **kw):
            entered.set()
            if not release.wait(2):
                raise AssertionError('test did not release backfill')
        def refresh(*a, **kw):
            writes.append(self.active['id'])
            raise RuntimeError('art failure')
        original = server.threading.Thread
        threads = []
        def thread_factory(*a, **kw):
            thread = original(*a, **kw)
            threads.append(thread)
            return thread
        with mock.patch.object(server.frame_android, 'shortcut_tool', side_effect=check), \
                mock.patch.object(server.frame_android, 'refresh_art', side_effect=refresh), \
                mock.patch.object(server.threading, 'Thread', side_effect=thread_factory):
            server.backfill_art(apps=[{'package': 'org.test.app', 'art_pending': True}])
            try:
                self.assertTrue(entered.wait(2))
                self.assertGreater(server._work[0], 0)
                with self.assertRaises(server.Failure):
                    server.devices_post({'action': 'use', 'id': 'b'})
            finally:
                release.set()
                for thread in threads:
                    thread.join(2)
        self.assertEqual(writes, ['a'])
        self.assertEqual(server._work[0], 0)
        self.assertFalse(server._backfill['running'])
        server.devices_post({'action': 'use', 'id': 'b'})

    def test_listing_cannot_switch_before_backfill_registration(self):
        handler = server.Handler.__new__(server.Handler)
        handler.path = '/api/android'
        handler.local_request = lambda: True
        handler.send_json = mock.Mock()
        handler.send_error_json = mock.Mock()
        attempts = []
        def listing():
            try:
                server.devices_post({'action': 'use', 'id': 'b'})
            except server.Failure:
                attempts.append('refused')
            return []
        with mock.patch.object(server, 'ensure_master'), \
                mock.patch.object(android, 'list_apps', side_effect=listing), \
                mock.patch.object(server, 'backfill_art') as backfill, \
                mock.patch.object(server.apk_search, 'artwork_for', return_value={}):
            handler.do_GET()
        self.assertEqual(attempts, ['refused'])
        backfill.assert_called_once()
        self.assertEqual(server._work[0], 0)

    def test_failed_worker_start_releases_count_and_throttle(self):
        with mock.patch.object(server.threading.Thread, 'start', side_effect=RuntimeError('cannot start')):
            with self.assertRaisesRegex(RuntimeError, 'cannot start'):
                server.backfill_art(apps=[{'package': 'org.test.app', 'art_pending': True}])
        self.assertEqual(server._work[0], 0)
        self.assertFalse(server._backfill['running'])
        self.assertEqual(server._backfill['last'], 0)

    def test_backfill_refuses_identifiers_from_an_old_listing_target(self):
        self.active.update(id='b', name='Headset B')
        with mock.patch.object(android, 'refresh_art') as refresh:
            with self.assertRaises(server.Failure):
                server.backfill_art(apps=[{'package': 'org.test.app', 'art_pending': True}], meant='a')
        refresh.assert_not_called()
        self.assertEqual(server._work[0], 0)
        self.assertFalse(server._backfill['running'])

    def test_failed_thread_constructor_releases_count_and_throttle(self):
        with mock.patch.object(server.threading, 'Thread', side_effect=RuntimeError('thread allocation')):
            with self.assertRaisesRegex(RuntimeError, 'thread allocation'):
                server.backfill_art(apps=[{'package': 'org.test.app', 'art_pending': True}])
        self.assertEqual(server._work[0], 0)
        self.assertEqual(server._backfill, {'running': False, 'last': 0})

    def test_approval_same_device_runs_once_and_releases_work_on_error(self):
        with mock.patch.object(agent, 'approvals', agent.Approvals()), \
                mock.patch.object(server, 'launch', side_effect=RuntimeError('launch failed')) as launch:
            body = {'name': 'launch', 'arguments': {'appid': '620'}}
            approval = agent.call(server, body)
            agent.approvals.decide(approval['confirmation'], True)
            with self.assertRaisesRegex(RuntimeError, 'launch failed'):
                agent.call(server, dict(body, confirmation=approval['confirmation']))
            with self.assertRaises(ValueError):
                agent.call(server, dict(body, confirmation=approval['confirmation']))
            launch.assert_called_once()
        self.assertEqual(server._work[0], 0)

    def test_approval_records_target_and_rejects_switch(self):
        with mock.patch.object(agent, 'approvals', agent.Approvals()), mock.patch.object(server, 'launch') as launch:
            body = {'name': 'launch', 'arguments': {'appid': '620'}}
            approval = agent.call(server, body)
            self.assertEqual(approval['action']['target'], self.active)
            self.assertEqual(agent.approvals.inspect(approval['confirmation'])['action']['target'], self.active)
            agent.approvals.decide(approval['confirmation'], True)
            server.devices_post({'action': 'use', 'id': 'b'})
            with self.assertRaises(ValueError):
                agent.call(server, dict(body, confirmation=approval['confirmation']))
            launch.assert_not_called()
            self.assertEqual(server._work[0], 0)

    def test_approval_dispatch_holds_existing_work_guard(self):
        attempts = []
        def launch(args):
            try:
                server.devices_post({'action': 'use', 'id': 'b'})
            except server.Failure:
                attempts.append('refused')
            return {'message': 'launched'}
        with mock.patch.object(agent, 'approvals', agent.Approvals()), mock.patch.object(server, 'launch', side_effect=launch):
            body = {'name': 'launch', 'arguments': {'appid': '620'}}
            approval = agent.call(server, body)
            agent.approvals.decide(approval['confirmation'], True)
            result = agent.call(server, dict(body, confirmation=approval['confirmation']))
        self.assertEqual(result['message'], 'launched')
        self.assertEqual(attempts, ['refused'])
        self.assertEqual(self.active['id'], 'a')
        self.assertEqual(server._work[0], 0)


class FinalLaunchTests(unittest.TestCase):
    """Production delivery/cleanup with separate temporary A/B remote homes."""
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.before = (server.FRAME, list(server.HOST_OPTS))
        self.stack.enter_context(mock.patch.object(server, 'LOCAL', False))
        self.stack.enter_context(mock.patch.object(server, 'LINK', None))
        self.stack.enter_context(mock.patch.object(server, '_work', [0]))
        self.stack.enter_context(mock.patch.object(server.macview, 'retarget'))
        self.stack.enter_context(mock.patch.object(server, '_touch'))
        self.stack.enter_context(mock.patch.object(server, 'ensure_master'))
        local = self.root / 'local'
        (local / 'packages').mkdir(parents=True)
        packages = []
        for n in (1, 2):
            name, data = 'test%d.pkg.tar.zst' % n, ('offline package %d' % n).encode()
            (local / 'packages' / name).write_bytes(data)
            packages.append((name, hashlib.sha256(data).hexdigest()))
        self.stack.enter_context(mock.patch.object(server, 'KDECONNECT', local))
        self.agent = server.InputAgent(packages=packages)
        self.stack.enter_context(mock.patch.object(server, '_input', self.agent))
        self.stack.callback(lambda: server.route(*self.before))
        for alias in ('target-a', 'target-b'):
            (self.root / alias).mkdir()
        server.route('target-a', ['-o', 'HostName=192.0.2.1'])
        self.original_route = tuple([*server.SSH, server.FRAME])
        self.calls = []
        self.real_popen = subprocess.Popen

    def remote(self, argv, **kw):
        target, command = argv[-2:]
        self.assertIn(target, ('target-a', 'target-b'))
        feed = kw.get('input')
        if isinstance(feed, str):
            feed = feed.encode()
        home = self.root / target
        proc = self.real_popen(['sh', '-c', command], cwd=home,
                               env={**os.environ, 'HOME': str(home)},
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(feed, timeout=3)
        self.calls.append({'route': tuple(argv[:-1]), 'command': command, 'input': feed})
        return subprocess.CompletedProcess(argv, proc.returncode,
                                           out.decode() if kw.get('text') else out,
                                           err.decode() if kw.get('text') else err)

    def delivery_boundary(self, boundary, cancel=False):
        entered, release = threading.Event(), threading.Event()
        def remote(argv, **kw):
            result = self.remote(argv, **kw)
            command = argv[-1]
            hit = ((boundary == 'stamp' and 'cmp -s' in command)
                   or (boundary == 'mkdir' and command.startswith('mkdir -p'))
                   or (boundary == 'copy' and command.startswith('cd ')))
            if hit and not entered.is_set():
                entered.set()
                if not release.wait(3):
                    raise AssertionError('delivery barrier not released')
            return result
        self.agent.launching = self.agent.generation
        with mock.patch.object(server.frame_host, 'run_ssh', side_effect=remote), \
                mock.patch.object(server.subprocess, 'Popen') as launch:
            worker = threading.Thread(target=self.agent._launch, args=(self.agent.generation,))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                if cancel:
                    self.agent.stop()
                else:
                    server.route('target-b', ['-o', 'HostName=192.0.2.2'])
                release.set()
                worker.join(3)
                self.assertFalse(worker.is_alive())
                launch.assert_not_called()
            finally:
                release.set()
                worker.join(3)
        self.assertTrue(all(c['route'] == self.original_route for c in self.calls), self.calls)
        copies = [c for c in self.calls if c['command'].startswith('cd ')]
        self.assertEqual(len(copies), 1 if boundary == 'copy' else 0)
        for alias in ('target-a', 'target-b'):
            self.assertFalse(list((self.root / alias).rglob('*.part')))
            self.assertFalse(list((self.root / alias).glob('**/incoming/*')))
        self.assertIsNone(self.agent.proc)
        self.assertEqual(self.agent.status['state'], 'off')
        self.assertEqual(server._work[0], 0)

    def test_switch_after_stamp_cannot_deliver_to_b(self):
        self.delivery_boundary('stamp')

    def test_switch_after_mkdir_cleans_only_a(self):
        self.delivery_boundary('mkdir')

    def test_switch_after_first_copy_stops_next_copy_and_cleans_a(self):
        self.delivery_boundary('copy')

    def test_cancel_after_first_copy_stops_next_copy_and_cleans_a(self):
        self.delivery_boundary('copy', cancel=True)

    def test_deferred_no_output_cleanup_keeps_the_original_route(self):
        watching, release = threading.Event(), threading.Event()
        proc = mock.Mock()
        proc.poll.return_value = None
        proc.wait.return_value = 0
        def stdout():
            watching.set()
            if not release.wait(3):
                raise AssertionError('watch barrier not released')
            yield from ()
        proc.stdout = stdout()
        with mock.patch.object(server.frame_host, 'run_ssh', side_effect=self.remote), \
                mock.patch.object(server.subprocess, 'Popen', return_value=proc):
            self.agent.start()
            try:
                self.assertTrue(watching.wait(3))
                self.assertEqual(server._work[0], 0, 'watch lifetime must not block device switching')
                server.route('target-b', ['-o', 'HostName=192.0.2.2'])
                release.set()
                # The real watch completes and discard runs after route publication.
                for _ in range(150):
                    if any(c['command'].startswith('rm -rf') for c in self.calls):
                        break
                    threading.Event().wait(.01)
                self.assertTrue(any(c['command'].startswith('rm -rf') for c in self.calls))
            finally:
                release.set()
        self.assertTrue(all(c['route'] == self.original_route for c in self.calls), self.calls)
        self.assertFalse(list((self.root / 'target-a').glob('**/incoming/*')))
        self.assertIsNone(self.agent.proc)
        self.assertEqual(self.agent.status['state'], 'off')
    def test_package_retry_keeps_the_original_ssh_route(self):
        first, second = mock.Mock(), mock.Mock()
        first.stdout = [b'{"state":"need-packages"}\n']
        second.stdout = [b'{"state":"ready"}\n']
        first.poll.return_value = second.poll.return_value = 0
        first.wait.side_effect = lambda: server.route('target-a', ['-o', 'HostName=192.0.2.2'])
        second.wait.return_value = 0
        with mock.patch.object(server.frame_host, 'run_ssh', side_effect=self.remote), \
                mock.patch.object(server.subprocess, 'Popen', side_effect=[first, second]) as popen:
            self.agent.launching = self.agent.generation
            self.agent._launch(self.agent.generation)
        self.assertEqual(popen.call_count, 2)
        self.assertTrue(all(tuple(call.args[0][:-1]) == self.original_route for call in popen.call_args_list))
        self.assertTrue(all(c['route'] == self.original_route for c in self.calls), self.calls)
        self.assertEqual(len([c for c in self.calls if c['command'].startswith('cd ')]), 4)



class FinalGetStartTests(unittest.TestCase):
    setUp = TargetTests.setUp
    switch = TargetTests.switch
    def handler(self, path, meant):
        handler = server.Handler.__new__(server.Handler)
        handler.command, handler.path = 'GET', path
        handler.headers = {'Host': '127.0.0.1:8123', 'X-Frame-UI': server.UI_KEY}
        if meant is not None:
            handler.headers['X-Frame-Device'] = meant
        handler.send_json, handler.send_error_json = mock.Mock(), mock.Mock()
        return handler

    def test_stale_authenticated_get_start_is_rejected_before_start(self):
        self.active.update(id='b', name='Headset B')
        for name in ('input', 'touch'):
            with self.subTest(name=name):
                fresh = server.InputAgent(packages=[]) if name == 'input' else server.TouchAgent()
                handler = self.handler('/api/%s?start=1' % name, 'a')
                with mock.patch.object(server, '_' + name, fresh), mock.patch.object(fresh, 'start') as start:
                    handler.do_GET()
                start.assert_not_called()
                self.assertEqual(handler.send_error_json.call_args.args[1], 409)
                self.assertEqual(server._work[0], 0)

    def test_desktop_get_start_requires_an_intended_device(self):
        for name in ('input', 'touch'):
            with self.subTest(name=name):
                fresh = server.InputAgent(packages=[]) if name == 'input' else server.TouchAgent()
                handler = self.handler('/api/%s?start=1' % name, None)
                with mock.patch.object(server, '_' + name, fresh), mock.patch.object(fresh, 'start') as start:
                    handler.do_GET()
                start.assert_not_called()
                self.assertEqual(handler.send_error_json.call_args.args[1], 400)
                self.assertEqual(server._work[0], 0)

    def test_get_start_validation_and_thread_registration_are_one_reservation(self):
        attempts = []
        fresh = server.TouchAgent()
        def register():
            try:
                server.devices_post({'action': 'use', 'id': 'b'})
            except server.Failure:
                attempts.append('refused')
        with mock.patch.object(server, '_touch', fresh), mock.patch.object(fresh, 'start', side_effect=register):
            handler = self.handler('/api/touch?start=1', 'a')
            handler.do_GET()
        self.assertEqual(attempts, ['refused'])
        self.assertEqual(self.active['id'], 'a')
        self.assertEqual(server._work[0], 0)

    def test_delayed_launch_uses_the_synchronously_captured_route(self):
        pending = []
        class QueuedThread:
            def __init__(self, target, args=(), kwargs=None, **ignored):
                self.target, self.args, self.kwargs = target, args, kwargs or {}
            def start(self):
                pending.append(self)
        before = (server.FRAME, list(server.HOST_OPTS))
        try:
            for switched in (False, True):
                with self.subTest(switched=switched):
                    fresh = server.TouchAgent()
                    proc = mock.Mock()
                    proc.poll.return_value = None
                    with mock.patch.object(server, '_touch', fresh), \
                            mock.patch.object(server.threading, 'Thread', QueuedThread), \
                            mock.patch.object(server, 'ensure_master'), \
                            mock.patch.object(fresh, '_watch', return_value=(False, True)), \
                            mock.patch.object(server.subprocess, 'Popen', return_value=proc) as popen:
                        server.route('target-a', ['-o', 'HostName=192.0.2.1'])
                        original = tuple([*server.SSH, server.FRAME])
                        handler = self.handler('/api/touch?start=1', 'a')
                        handler.do_GET()
                        self.assertEqual(len(pending), 1)
                        # Also change options without a generation change: this
                        # proves the route was captured before the thread runs.
                        server.route('target-b' if switched else 'target-a', ['-o', 'HostName=192.0.2.2'])
                        thread = pending.pop()
                        thread.target(*thread.args, **thread.kwargs)
                        if switched:
                            popen.assert_not_called()
                            self.assertIsNone(fresh.proc)
                        else:
                            self.assertEqual(tuple(popen.call_args.args[0][:-1]), original)
                        fresh.stop()
                        server._live_tunnels.discard(proc)
        finally:
            server.route(*before)

    def test_same_target_start_status_and_local_ios_remain_usable(self):
        for link, meant, query in ((self.link, 'a', '?start=1'), (self.link, 'stale', ''),
                                    (None, None, '?start=1')):
            for name in ('input', 'touch'):
                with self.subTest(name=name, query=query, local=link is None):
                    fresh = server.InputAgent(packages=[]) if name == 'input' else server.TouchAgent()
                    handler = self.handler('/api/' + name + query, meant)
                    with mock.patch.object(server, 'LINK', link), mock.patch.object(server, 'LOCAL', link is None), \
                            mock.patch.object(server, '_' + name, fresh), mock.patch.object(fresh, 'start') as start:
                        handler.do_GET()
                    self.assertEqual(start.call_count, 1 if query else 0)
                    handler.send_error_json.assert_not_called()
                    self.assertEqual(server._work[0], 0)


class UpdateTests(unittest.TestCase):
    """Execute generated remote commands in a temporary home; only Steam is synthetic."""
    def exercise(self, failure, repair_failure=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / 'Applications/Android/org.test.app'
            d.mkdir(parents=True)
            old = {'package': 'org.test.app', 'version': '1', 'label': 'Old', 'instance': 2800000001,
                   'shortcut': 42, 'flatscreen': False, 'artwork': {}}
            files = {'app.apk': b'old APK', 'launch.sh': b'old launcher', 'instance.id': b'2800000001',
                     'meta.json': json.dumps(old).encode(), 'shortcut.id': b'42', 'user-save': b'precious data'}
            for name, data in files.items():
                (d / name).write_bytes(data)
            (d / 'launch.sh').chmod(0o755)
            save = root / '.local/share/Steam/steamapps/compatdata/2800000001/internal/save'
            save.parent.mkdir(parents=True)
            save.write_bytes(b'Android saved data')
            apk = root / 'new.apk'
            apk.write_bytes(b'new APK')
            info = {'package': 'org.test.app', 'version': '2', 'label': 'New', 'vr': False}
            writes = []
            repairing = [False]
            repair_failure_pending = [False]
            cleanup_attempts = []
            def ssh(cmd, input=None, **kw):
                repair_stage = None
                if repairing[0] and repair_failure_pending[0]:
                    if '/meta.json.tmp' in cmd and cmd.startswith('cat >'):
                        repair_stage = 'meta'
                    elif '/update-recovery.json.tmp' in cmd and cmd.startswith('cat >'):
                        repair_stage = 'checkpoint'
                    elif cmd.startswith('rm -rf ') and '.frame-update-backup' in cmd:
                        repair_stage = 'cleanup'
                    if repair_failure == 'cleanup-partial' and repair_stage == 'cleanup':
                        (d / '.frame-update-backup/ready').unlink()
                        repair_failure_pending[0] = False
                        raise android.FrameError('partial repair cleanup')
                    if repair_failure == repair_stage:
                        repair_failure_pending[0] = False
                        raise android.FrameError('transient repair ' + repair_stage)
                if failure == 'cleanup' and cmd == 'rm -rf Applications/Android/org.test.app/.frame-update-backup' and not cleanup_attempts:
                    cleanup_attempts.append(cmd)
                    raise android.FrameError('backup cleanup unavailable')
                if repairing[0] and cmd == 'python3 -':
                    return json.dumps({'icon_png': '', 'artwork': {}})
                if failure == 'rollback' and 'frame-update-backup' in cmd and ('cp -' in cmd or 'mv ' in cmd) and writes and not repairing[0]:
                    raise android.FrameError('restore connection lost')
                if failure == 'meta' and '/meta.json.tmp' in cmd and not writes:
                    writes.append('meta failed')
                    raise android.FrameError('metadata unavailable')
                if isinstance(input, str):
                    input = input.encode()
                p = subprocess.run(['sh', '-c', cmd], input=input, cwd=root,
                                   env={**os.environ, 'HOME': str(root)}, capture_output=True)
                if p.returncode:
                    raise android.FrameError(p.stderr.decode())
                if repair_stage and repair_failure == repair_stage + '-after':
                    repair_failure_pending[0] = False
                    raise android.FrameError('lost repair ' + repair_stage + ' response')
                if failure == 'meta-after' and '/meta.json.tmp' in cmd and not writes:
                    writes.append('meta response lost')
                    raise android.FrameError('metadata response lost')
                return p.stdout.decode()
            def copy(src, dest, **kw):
                target = root / dest
                shutil.copyfile(src, target)
                if kw.get('executable'):
                    target.chmod(0o755)
            def shortcut_tool(*args, **kw):
                if args[0] == 'add':
                    return '43'
                if args[0] == 'remove':
                    if not repairing[0]:
                        raise android.FrameError('shortcut cleanup unavailable')
                    return '{}'
                raise AssertionError(args)
            def library(*a, **kw):
                if repairing[0]:
                    self.assertEqual(a[1], 'Old')
                    self.assertTrue(kw['vr'])
                    self.assertEqual(kw['fill_only'], not (d / 'update-recovery.json').exists())
                    (root / 'steam-state').write_text('old library settings')
                    if repair_failure_pending[0] and repair_failure == 'library':
                        repair_failure_pending[0] = False
                        raise android.FrameError('transient repair library failure')
                    return {'artwork': {}, 'warnings': []}
                # A partial library mutation is externally observable even when configure fails.
                (root / 'steam-state').write_text('new library settings')
                if failure in ('library', 'rollback', 'orphan'):
                    writes.append('library failed')
                    raise android.FrameError('Steam unavailable after partial configure')
                return {'artwork': {}, 'warnings': []}
            with mock.patch.object(android.frame_artwork, 'prepare', return_value=({}, [])), \
                    mock.patch.object(android, 'ssh', side_effect=ssh), \
                    mock.patch.object(android, '_copy', side_effect=copy), \
                    mock.patch.object(android, '_shortcut_ids', return_value=set() if failure == 'orphan' else {42}), \
                    mock.patch.object(android, 'shortcut_tool', side_effect=shortcut_tool), \
                    mock.patch.object(android, 'apply_library', side_effect=library):
                with self.assertRaises(android.FrameError) as error:
                    android._install(str(apk), info, info['package'], True, None, None)
            if failure != 'rollback':
                for name, data in files.items():
                    self.assertEqual((d / name).read_bytes(), data, name)
                self.assertFalse((d / 'lepton-show-flatscreen').exists())
                if os.name != 'nt':  # Windows has no execute bit to restore
                    self.assertTrue((d / 'launch.sh').stat().st_mode & 0o100)
                self.assertFalse((d / 'app.apk.part').exists())
                self.assertFalse((d / 'meta.json.tmp').exists())
            self.assertEqual((d / 'user-save').read_bytes(), b'precious data')
            self.assertEqual(save.read_bytes(), b'Android saved data')
            # Steam's API cannot guarantee a full rollback. Never hide that residual state.
            self.assertIn('repair', str(error.exception).lower())
            record = json.loads((d / 'update-recovery.json').read_text())
            self.assertIn('error', record)
            self.assertIn('repair', record)
            if failure == 'rollback':
                self.assertIn('restore connection lost', str(error.exception))
                self.assertTrue((d / '.frame-update-backup').is_dir())
            if failure == 'orphan':
                self.assertEqual(record['orphan_shortcut'], 43)
                self.assertIn('shortcut cleanup unavailable', str(error.exception))
            snapshot = {str(p.relative_to(d)): p.read_bytes() for p in d.rglob('*') if p.is_file()}
            with mock.patch.object(android.frame_artwork, 'prepare', return_value=({}, [])), \
                    mock.patch.object(android, 'ssh', side_effect=ssh), \
                    mock.patch.object(android, '_copy', side_effect=AssertionError('pending recovery must refuse before copying')):
                with self.assertRaises(android.FrameError):
                    android._install(str(apk), info, info['package'], True, None, None)
            self.assertEqual({str(p.relative_to(d)): p.read_bytes() for p in d.rglob('*') if p.is_file()}, snapshot,
                             'Retry must preserve all prior recovery evidence byte for byte')
            repairing[0] = True
            with mock.patch.object(android.frame_artwork, 'prepare', return_value=({}, [])), \
                    mock.patch.object(android, 'ssh', side_effect=ssh), \
                    mock.patch.object(android, '_shortcut_ids', return_value={42}), \
                    mock.patch.object(android, 'shortcut_tool', side_effect=shortcut_tool) as api, \
                    mock.patch.object(android, 'apply_library', side_effect=library):
                if repair_failure:
                    repair_failure_pending[0] = True
                    with self.assertRaises(android.FrameError):
                        android.refresh_art(info['package'], fill_only=True)
                    # A later failure must retain either the ready snapshot or a
                    # durable terminal checkpoint, never an unconfirmed dead end.
                    if (d / 'update-recovery.json').exists():
                        retry_record = json.loads((d / 'update-recovery.json').read_text())
                        for key in ('error', 'rollback_error', 'orphan_shortcut', 'cleanup_error'):
                            self.assertEqual(retry_record[key], record[key], key)
                        self.assertTrue((d / '.frame-update-backup/ready').exists() or
                                        retry_record.get('repair_completed') is True)
                    else:
                        self.assertFalse((d / '.frame-update-backup').exists())
                    self.assertEqual((d / 'app.apk').read_bytes(), files['app.apk'])
                    self.assertEqual((d / 'launch.sh').read_bytes(), files['launch.sh'])
                    self.assertFalse((d / 'lepton-show-flatscreen').exists())
                    coherent = json.loads((d / 'meta.json').read_text())
                    self.assertEqual(coherent['version'], '1')
                    self.assertFalse(coherent['flatscreen'])
                repaired = android.refresh_art(info['package'], fill_only=True)
            if failure == 'orphan':
                api.assert_called_once_with('remove', '43')
            self.assertEqual(repaired['version'], '1')
            self.assertFalse(repaired['flatscreen'])
            self.assertEqual((root / 'steam-state').read_text(), 'old library settings')
            for name in ('app.apk', 'launch.sh', 'instance.id', 'shortcut.id', 'user-save'):
                self.assertEqual((d / name).read_bytes(), files[name], name)
            self.assertFalse((d / 'update-recovery.json').exists())
            self.assertFalse((d / '.frame-update-backup').exists())
            self.assertFalse((d / 'lepton-show-flatscreen').exists())
            self.assertEqual(save.read_bytes(), b'Android saved data')
            return record

    def test_late_library_failure_restores_executable_metadata_and_preserves_data(self):
        self.exercise('library')

    def test_meta_write_failure_restores_executable_metadata_and_preserves_data(self):
        self.exercise('meta')

    def test_missing_snapshot_cannot_claim_an_unconfirmed_rollback_is_repaired(self):
        def ssh(cmd, **kw):
            if cmd.startswith('test -f'):
                return 'yes'
            if cmd.startswith('cat ') and cmd.endswith('update-recovery.json'):
                return json.dumps({'files_restored': False, 'library_may_have_changed': True})
            if cmd == 'python3 -':
                return json.dumps({'icon_png': '', 'artwork': {}})
            return ''
        meta = {'package': 'org.test.app', 'label': 'Old', 'shortcut': 42, 'flatscreen': False}
        with mock.patch.object(android, 'ssh', side_effect=ssh), \
                mock.patch.object(android, '_meta_or_fail', return_value=meta), \
                mock.patch.object(android, '_shortcut_ids', return_value={42}), \
                mock.patch.object(android.frame_artwork, 'prepare', return_value=({}, [])), \
                mock.patch.object(android, '_write_meta'), \
                mock.patch.object(android, 'apply_library', return_value={}) as library:
            with self.assertRaisesRegex(android.FrameError, 'unconfirmed'):
                android.refresh_art('org.test.app')
        library.assert_not_called()

    def test_retry_preserves_absent_snapshot_uncertainty_and_repair_still_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / 'Applications/Android/org.test.app'
            d.mkdir(parents=True)
            record = {'files_restored': False, 'files_unchanged': False, 'error': 'original lost rollback',
                      'library_may_have_changed': True, 'orphan_shortcut': 43}
            (d / 'update-recovery.json').write_text(json.dumps(record))
            evidence = (d / 'update-recovery.json').read_bytes()
            def ssh(cmd, input=None, **kw):
                result = subprocess.run(['sh', '-c', cmd], cwd=root, capture_output=True)
                if result.returncode:
                    raise android.FrameError(result.stderr.decode())
                return result.stdout.decode()
            with mock.patch.object(android, 'ssh', side_effect=ssh), \
                    mock.patch.object(android.frame_artwork, 'prepare', side_effect=AssertionError('must refuse before artwork')), \
                    mock.patch.object(android, '_copy', side_effect=AssertionError('must refuse before copy')):
                with self.assertRaisesRegex(android.FrameError, 'Pending'):
                    android._install('unused.apk', {'label': 'New'}, 'org.test.app', True, None, None)
                self.assertEqual((d / 'update-recovery.json').read_bytes(), evidence)
                with self.assertRaisesRegex(android.FrameError, 'unconfirmed'):
                    android.refresh_art('org.test.app')
                self.assertEqual((d / 'update-recovery.json').read_bytes(), evidence)

    def test_recovery_appearing_after_preflight_is_not_owned_by_the_new_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / 'Applications/Android/org.test.app'
            d.mkdir(parents=True)
            meta = {'package': 'org.test.app', 'instance': 2800000001, 'shortcut': 42, 'label': 'Old'}
            (d / 'meta.json').write_text(json.dumps(meta))
            (d / 'app.apk').write_bytes(b'old APK')
            record = b'{"orphan_shortcut":43,"files_restored":false,"error":"prior failure"}'
            def prepare(*args):
                (d / 'update-recovery.json').write_bytes(record)
                (d / 'app.apk.part').write_bytes(b'prior partial evidence')
                return {}, []
            def ssh(cmd, input=None, **kw):
                if isinstance(input, str):
                    input = input.encode()
                result = subprocess.run(['sh', '-c', cmd], input=input, cwd=root, capture_output=True)
                if result.returncode:
                    raise android.FrameError(result.stderr.decode())
                return result.stdout.decode()
            with mock.patch.object(android, 'ssh', side_effect=ssh), \
                    mock.patch.object(android.frame_artwork, 'prepare', side_effect=prepare), \
                    mock.patch.object(android, '_copy', side_effect=AssertionError('pending recovery must refuse before copy')):
                with self.assertRaisesRegex(android.FrameError, 'Pending'):
                    android._install('unused.apk', {'label': 'New'}, 'org.test.app', True, None, None)
            self.assertEqual((d / 'update-recovery.json').read_bytes(), record)
            self.assertEqual((d / 'app.apk.part').read_bytes(), b'prior partial evidence')
            self.assertEqual((d / 'app.apk').read_bytes(), b'old APK')
            self.assertFalse((d / '.frame-update-backup').exists())

    def test_snapshot_without_record_cannot_be_repaired_or_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / 'Applications/Android/org.test.app'
            backup = d / '.frame-update-backup'
            backup.mkdir(parents=True)
            (backup / 'ready').touch()
            (backup / 'app.apk').write_bytes(b'old APK evidence')
            def ssh(cmd, input=None, **kw):
                result = subprocess.run(['sh', '-c', cmd], cwd=root, capture_output=True)
                if result.returncode:
                    raise android.FrameError(result.stderr.decode())
                return result.stdout.decode()
            with mock.patch.object(android, 'ssh', side_effect=ssh), \
                    mock.patch.object(android.frame_artwork, 'prepare', side_effect=AssertionError('must refuse before artwork')):
                with self.assertRaisesRegex(android.FrameError, 'Pending'):
                    android._install('unused.apk', {'label': 'New'}, 'org.test.app', True, None, None)
                with self.assertRaisesRegex(android.FrameError, 'unconfirmed'):
                    android.refresh_art('org.test.app')
            self.assertFalse((d / 'update-recovery.json').exists())
            self.assertEqual((backup / 'app.apk').read_bytes(), b'old APK evidence')

    def test_meta_write_response_loss_restores_old_metadata_too(self):
        self.exercise('meta-after')

    def test_new_shortcut_cleanup_failure_is_recorded_and_repaired(self):
        self.exercise('orphan')

    def test_backup_cleanup_failure_rolls_back_and_has_a_repair_path(self):
        self.exercise('cleanup')

    def test_restore_failure_reports_and_keeps_recovery_evidence(self):
        self.exercise('rollback')

    def test_repair_retains_recovery_until_all_stages_and_cleanup_succeed(self):
        for stage in ('library', 'meta', 'meta-after', 'checkpoint',
                      'checkpoint-after', 'cleanup', 'cleanup-partial', 'cleanup-after'):
            with self.subTest(stage=stage):
                self.exercise('rollback', repair_failure=stage)


if __name__ == '__main__':
    unittest.main()
