"""Store requests can reconnect when the headset panel loses the POST response."""
import sandbox  # noqa: F401
import sys
import subprocess
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import server


class StoreJobs(unittest.TestCase):
    def test_invalid_plugin_ids_do_not_reserve_jobs_or_start_workers(self):
        request_id = 'e' * 32
        body = {'action': 'install', 'sha256': 'a' * 64,
                'acknowledged': True, 'requestId': request_id}
        with patch.object(server, 'busy_thread') as worker:
            for plugin_id in (0, -1, True, False, 2.0, '2', None, []):
                with self.subTest(plugin_id=plugin_id):
                    try:
                        with self.assertRaises(server.Failure) as error:
                            server.decky_plugin({**body, 'id': plugin_id})
                        self.assertEqual(error.exception.status, 400)
                        with server._jobs_lock:
                            self.assertNotIn(request_id, server._jobs)
                    finally:
                        with server._jobs_lock:
                            server._jobs.pop(request_id, None)
            worker.assert_not_called()

    def test_invalid_reviewed_hashes_do_not_reserve_jobs_or_start_workers(self):
        request_id = 'e' * 32
        body = {'id': 2, 'acknowledged': True, 'requestId': request_id}
        cases = [(action, digest) for action in ('install', 'update')
                 for digest in (False, 1, '', 'A' * 64, 'a' * 63, 'a' * 65, [], {})]
        cases.append(('remove', 'a' * 64))
        with patch.object(server, 'busy_thread') as worker:
            for action, digest in cases:
                with self.subTest(action=action, digest=digest):
                    try:
                        with self.assertRaises(server.Failure) as error:
                            server.decky_plugin({**body, 'action': action, 'sha256': digest})
                        self.assertEqual(error.exception.status, 400)
                        with server._jobs_lock:
                            self.assertNotIn(request_id, server._jobs)
                    finally:
                        with server._jobs_lock:
                            server._jobs.pop(request_id, None)
            worker.assert_not_called()

    def test_corrected_request_can_use_id_from_rejected_submission(self):
        request_id = 'e' * 32
        body = {'action': 'install', 'id': 2, 'sha256': 'a' * 64,
                'acknowledged': True, 'requestId': request_id}
        try:
            with patch.object(server, 'busy_thread') as worker, \
                 patch.object(server.frame_decky_store, 'change', return_value={'message': 'Installed once'}) as change:
                with self.assertRaises(server.Failure) as error:
                    server.decky_plugin({**body, 'sha256': ''})
                self.assertEqual(error.exception.status, 400)
                worker.assert_not_called()
                first = server.decky_plugin(body)
                self.assertEqual(first['job'], request_id)
                self.assertEqual(server.decky_plugin(body), first)
                self.assertEqual(worker.call_count, 1)
                # Run only the captured worker function, with store work stubbed;
                # no real thread, download, SSH or headset action is started.
                target, *args = worker.call_args.args
                target(*args)
                result = server.job_status('id=' + request_id)
                self.assertTrue(result['done'])
                self.assertEqual(result['message'], 'Installed once')
                self.assertEqual(change.call_args.kwargs['reviewed_hash'], 'a' * 64)
                self.assertEqual(server.decky_plugin(body), first)
                change.assert_called_once()
                with self.assertRaises(server.Failure) as conflict:
                    server.decky_plugin({**body, 'sha256': 'b' * 64})
                self.assertEqual(conflict.exception.status, 409)
        finally:
            with server._jobs_lock:
                server._jobs.pop(request_id, None)

    def test_desktop_lost_post_and_poll_replies_recover_without_resubmitting(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_desktop_store_recovery.mjs')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_desktop_store_actions_keep_the_displayed_installed_receipt(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/framey_desktop_store.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_worker_start_failure_is_terminal_and_request_can_be_checked(self):
        for stage in ('construct', 'start'):
            request_id = ('c' if stage == 'construct' else 'd') * 32
            body = {'action': 'install', 'id': 2, 'sha256': 'b' * 64,
                    'acknowledged': True, 'requestId': request_id}
            work_before = server._work[0]
            try:
                with patch.object(server.threading, 'Thread') as worker, \
                     patch.object(server.frame_decky_store, 'change') as change:
                    if stage == 'construct':
                        worker.side_effect = RuntimeError('No worker available')
                    else:
                        worker.return_value.start.side_effect = RuntimeError('No worker available')
                    with self.assertRaisesRegex(RuntimeError, 'No worker available'):
                        server.decky_plugin(body)
                    result = server.job_status('id=' + request_id)
                    self.assertTrue(result['done'], 'failed startup cannot leave a phantom running job')
                    self.assertIn('No worker available', result['error'])
                    self.assertEqual(server._work[0], work_before, 'release headset-switch protection')
                    self.assertEqual(server.decky_plugin(body)['job'], request_id)
                    self.assertEqual(worker.call_count, 1, 'reconnect must not start work again')
                    with self.assertRaises(server.Failure) as conflict:
                        server.decky_plugin({**body, 'id': 3})
                    self.assertEqual(conflict.exception.status, 409)
                    change.assert_not_called()
            finally:
                with server._jobs_lock:
                    server._jobs.pop(request_id, None)

    def test_same_request_id_runs_once_and_conflicting_reuse_is_rejected(self):
        request_id = 'a' * 32
        started = threading.Event()
        finish = threading.Event()
        calls = []

        def change(_ssh, action, plugin_id, report, reviewed_hash=None, installed_hash=None):
            calls.append((action, plugin_id, reviewed_hash, installed_hash))
            started.set()
            self.assertTrue(finish.wait(5))
            report('Installed', 100)
            return {'message': 'Installed once'}

        body = {'action': 'install', 'id': 2, 'sha256': 'b' * 64,
                'acknowledged': True, 'requestId': request_id}
        try:
            with patch.object(server.frame_decky_store, 'change', side_effect=change):
                first = server.decky_plugin(body)
                self.assertTrue(started.wait(5))
                self.assertEqual(server.decky_plugin(body), first)
                for changed in ({'action': 'update'}, {'id': 3}, {'sha256': 'c' * 64}):
                    with self.subTest(changed=changed), self.assertRaises(server.Failure) as error:
                        server.decky_plugin({**body, **changed})
                    self.assertEqual(error.exception.status, 409)
                self.assertEqual(calls, [('install', 2, 'b' * 64, None)])
                self.assertNotIn('_request', server.job_status('id=' + request_id))
                finish.set()
                for _ in range(100):
                    if server.job_status('id=' + request_id)['done']:
                        break
                    time.sleep(0.01)
                self.assertEqual(server.job_status('id=' + request_id)['message'], 'Installed once')
                self.assertEqual(server.decky_plugin(body), first)
                self.assertEqual(len(calls), 1)
        finally:
            finish.set()
            with server._jobs_lock:
                server._jobs.pop(request_id, None)

    def test_invalid_request_id_does_not_start_work(self):
        with patch.object(server.frame_decky_store, 'change') as change:
            for request_id in (1, '', 'A' * 32, 'f' * 31, 'f' * 33, '../' * 11):
                with self.subTest(request_id=request_id), self.assertRaises(server.Failure) as error:
                    server.decky_plugin({'action': 'install', 'id': 2,
                                         'acknowledged': True, 'requestId': request_id})
                self.assertEqual(error.exception.status, 400)
            change.assert_not_called()

    def test_reviewed_installed_receipt_is_forwarded_and_part_of_job_identity(self):
        request_id = 'd' * 32
        body = {'action': 'remove', 'id': 2, 'installedSha256': 'a' * 64,
                'acknowledged': True, 'requestId': request_id}
        try:
            with patch.object(server.frame_decky_store, 'change', return_value={}) as change:
                first = server.decky_plugin(body)
                for _ in range(100):
                    if server.job_status('id=' + request_id)['done']:
                        break
                    time.sleep(0.01)
                self.assertTrue(server.job_status('id=' + request_id)['done'])
                self.assertEqual(change.call_args.kwargs['installed_hash'], 'a' * 64)
                self.assertEqual(server.decky_plugin(body), first)
                self.assertEqual(change.call_count, 1)
                with self.assertRaises(server.Failure) as error:
                    server.decky_plugin({**body, 'installedSha256': 'b' * 64})
                self.assertEqual(error.exception.status, 409)
        finally:
            with server._jobs_lock:
                server._jobs.pop(request_id, None)

    def test_invalid_installed_receipt_does_not_reserve_a_job(self):
        with patch.object(server, 'start_job') as start:
            for receipt in (False, 1, '', 'A' * 64, 'a' * 63, 'a' * 65, []):
                with self.subTest(receipt=receipt), self.assertRaises(server.Failure) as error:
                    server.decky_plugin({'action': 'remove', 'id': 2,
                                         'acknowledged': True, 'installedSha256': receipt})
                self.assertEqual(error.exception.status, 400)
            with self.assertRaises(server.Failure):
                server.decky_plugin({'action': 'install', 'id': 2,
                                     'acknowledged': True, 'installedSha256': 'a' * 64})
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
