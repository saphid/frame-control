"""Store requests can reconnect when the headset panel loses the POST response."""
import sandbox  # noqa: F401
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import server


class StoreJobs(unittest.TestCase):
    def test_same_request_id_runs_once_and_conflicting_reuse_is_rejected(self):
        request_id = 'a' * 32
        started = threading.Event()
        finish = threading.Event()
        calls = []

        def change(_ssh, action, plugin_id, report, reviewed_hash=None):
            calls.append((action, plugin_id, reviewed_hash))
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
                self.assertEqual(calls, [('install', 2, 'b' * 64)])
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


if __name__ == '__main__':
    unittest.main()
