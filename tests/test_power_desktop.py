"""Desktop observation lifecycle, guarded HTTP API and packaged resource contract."""
import sandbox  # noqa: F401
import contextlib
import io
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import frame_power
import server

STREAM = frame_power.sampler.stream_report

SAMPLE = {'time': 1, 'elapsedSeconds': 0, 'osBuild': 'test', 'readings': {
    'battery.watts': {'value': 0, 'unit': 'W', 'source': '/sys/test', 'state': 'available'}},
    'unavailableGroups': ['fan']}


class DesktopPower(unittest.TestCase):
    def setUp(self):
        self.observation = frame_power.Observation()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lock = Path(self.temp.name) / 'frame-test.lock'
        self.patches = [patch.object(frame_power.sampler, 'LOCK', self.lock)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.observation.shutdown)

    def wait(self):
        self.observation.thread.join(4)
        self.assertFalse(self.observation.thread.is_alive())

    def stream(self, program, preset='minute'):
        real = STREAM
        def collect(command, payload, count, interval, stop, received, **kw):
            return real([sys.executable, '-u', '-c', program], '', count, interval, stop, received, **kw)
        mocked_stream = patch.object(frame_power.sampler, 'stream_report', side_effect=collect)
        mocked_stream.start()
        self.addCleanup(mocked_stream.stop)
        return self.observation.start(preset, ('ssh', '-o', 'HostName=old', 'frame-old'),
                                      {'alias': 'frame-old', 'deviceId': 'old'})

    def test_complete_exports_match_and_no_background_collection_on_status(self):
        def collect(command, payload, count, interval, stop, received, **kw):
            self.assertEqual(count, 12)
            self.assertEqual(interval, 5)
            self.assertIn('HostName=old', command)
            self.assertIn('StrictHostKeyChecking=yes', command)
            self.assertIn('frame-old', command)
            self.assertNotIn('pkill', ' '.join(command))
            for _ in range(count):
                received(SAMPLE.copy())
            return {'schemaVersion': 1, 'requestedSamples': count, 'intervalSeconds': interval,
                    'stopped': None, 'samples': [SAMPLE.copy() for _ in range(count)], 'summary': {}}
        with patch.object(frame_power.sampler, 'stream_report', side_effect=collect) as run:
            self.observation.start('minute', ('ssh', '-o', 'HostName=old', 'frame-old'), {'alias': 'frame-old'})
            self.wait()
            state = self.observation.status()
            self.assertEqual((state['received'], state['running'], state['stopped']), (12, False, None))
            for _ in range(3):
                self.observation.status()
            self.assertEqual(run.call_count, 1)
        report, _ = self.observation.export(state['id'], 'json')
        self.assertEqual(json.loads(report)['summary']['battery.watts']['mean'], 0)
        html, _ = self.observation.export(state['id'], 'html')
        csv, _ = self.observation.export(state['id'], 'csv')
        self.assertIn('Headset: frame-old', html)
        self.assertIn('collection.state,Completed', csv)
        self.assertIn('collection.receivedSamples,12', csv)
        self.assertIn('battery.watts,0,W', csv)

    def test_stop_keeps_received_sample_and_reaps_only_owned_child(self):
        real_popen = subprocess.Popen
        children = []
        def spawn(*a, **kw):
            proc = real_popen(*a, **kw)
            children.append(proc)
            return proc
        event = json.dumps({'sample': SAMPLE})
        with patch.object(frame_power.sampler.subprocess, 'Popen', side_effect=spawn):
            state = self.stream(f'import sys,time; sys.stdin.read(); print({event!r}, flush=True); time.sleep(30)')
            deadline = time.monotonic() + 3
            while self.observation.status()['received'] < 1 and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(self.observation.status()['received'], 1)
            with self.assertRaisesRegex(ValueError, 'already running'):
                self.observation.start('minute', ('ssh', 'frame'), {'alias': 'other'})
            active, _ = self.observation.export(state['id'], 'json')
            self.assertIn('in progress', json.loads(active)['stopped'])
            self.observation.stop()
            self.wait()
        self.assertIsNotNone(children[0].poll())
        data, _ = self.observation.export(state['id'], 'json')
        self.assertEqual(json.loads(data)['samples'], [SAMPLE])
        self.assertIn('Stopped by user', json.loads(data)['stopped'])
        csv, _ = self.observation.export(state['id'], 'csv')
        self.assertIn('incomplete', csv)

    def test_disconnect_and_oversize_keep_partial_and_incomplete(self):
        for ending in ('sys.exit(255)', 'print("x"*262145, flush=True)'):
            with self.subTest(ending=ending):
                event = json.dumps({'sample': SAMPLE})
                state = self.stream(f'import sys; sys.stdin.read(); print({event!r}, flush=True); {ending}')
                self.wait()
                data, _ = self.observation.export(state['id'], 'json')
                report = json.loads(data)
                self.assertEqual(report['samples'], [SAMPLE])
                self.assertTrue(report['stopped'])

    def test_local_lock_preserves_previous_report_and_invalid_inputs_do_not_spawn(self):
        with patch.object(frame_power.sampler, 'stream_report') as run:
            self.lock.mkdir()
            with self.assertRaisesRegex(ValueError, 'Smoke session'):
                self.observation.start('minute', ('ssh', 'frame'), {'alias': 'frame'})
            for preset in ('hour', 1000, None):
                with self.assertRaises(ValueError):
                    self.observation.start(preset, ('ssh', 'frame'), {'alias': 'frame'})
            run.assert_not_called()
        self.assertIsNone(self.observation.status()['id'])

    def test_headset_switch_preserves_original_identity_and_requests_cancel(self):
        done = threading.Event()
        def collect(command, payload, count, interval, cancel, received, **kw):
            received(SAMPLE)
            done.set()
            cancel.wait(3)
            return {'requestedSamples': count, 'intervalSeconds': interval, 'samples': [SAMPLE], 'stopped': None}
        with patch.object(frame_power.sampler, 'stream_report', side_effect=collect), \
             patch.object(server, '_power', self.observation):
            original = server.FRAME, list(server.HOST_OPTS)
            try:
                state = self.observation.start('five-minutes', ('ssh', 'old'), {'alias': 'old'})
                self.assertTrue(done.wait(2))
                server.route('different-headset', [])
                self.wait()
                current = self.observation.status()
                self.assertEqual(current['headset']['alias'], 'old')
                self.assertEqual(current['requested'], 60)
                self.assertIn('Headset switched', current['stopped'])
                with self.assertRaises(ValueError):
                    self.observation.export('stale-id', 'html')
                with self.assertRaises(ValueError):
                    self.observation.export(state['id'], '../file')
            finally:
                server.route(*original)

    def test_http_guards_stale_target_stop_id_and_download_headers(self):
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        conn = http.client.HTTPConnection(*httpd.server_address)
        def request(method, path, body=None, device=None, key=True):
            headers = {'X-Frame-UI': server.UI_KEY} if key else {}
            if device:
                headers['X-Frame-Device'] = device
            conn.request(method, path, json.dumps(body) if body is not None else None, headers)
            r = conn.getresponse()
            return r.status, dict(r.getheaders()), r.read()
        try:
            with patch.object(server, '_power', self.observation), \
                 patch.object(server, 'LINK', SimpleNamespace(active_device=lambda: {'id': 'new'})), \
                 patch.object(frame_power.sampler, 'stream_report') as run:
                for path in ('/api/power', '/api/power/report?id=x&format=html'):
                    self.assertEqual(request('GET', path, key=False)[0], 403)
                self.assertEqual(request('POST', '/api/power', {'action': 'start', 'preset': 'minute'}, key=False)[0], 403)
                for device, expected in ((None, 400), ('old', 409)):
                    self.assertEqual(request('POST', '/api/power', {'action': 'start', 'preset': 'minute'}, device)[0], expected)
                run.assert_not_called()
                self.observation.id = 'test-id'
                self.observation.report = {'schemaVersion': 1, 'requestedSamples': 12, 'intervalSeconds': 5,
                                           'headset': {'alias': 'old'}, 'stopped': 'Disconnected', 'samples': [SAMPLE]}
                status, headers, data = request('GET', '/api/power/report?id=test-id&format=html')
                self.assertEqual(status, 200)
                self.assertIn('attachment;', headers['Content-Disposition'])
                self.assertIn('no-store', headers['Cache-Control'])
                self.assertIn(b'Disconnected', data)
                self.assertEqual(request('POST', '/api/power', {'action': 'stop', 'id': 'stale'}, 'new')[0], 409)
                self.assertEqual(request('POST', '/api/power', {'action': 'stop', 'id': 'test-id'}, 'new')[0], 200)
                received = threading.Event()
                def collect(command, payload, count, interval, cancel, emit, **kw):
                    emit(SAMPLE)
                    received.set()
                    cancel.wait(3)
                    return {'schemaVersion': 1, 'requestedSamples': count, 'intervalSeconds': interval,
                            'samples': [SAMPLE], 'stopped': 'Stopped'}
                run.side_effect = collect
                code, _, data = request('POST', '/api/power', {'action': 'start', 'preset': 'minute'}, 'new')
                self.assertEqual(code, 200)
                new_id = json.loads(data)['id']
                self.assertNotEqual(new_id, 'test-id')
                self.assertTrue(received.wait(2))
                self.assertEqual(request('GET', '/api/power/report?id=test-id&format=json')[0], 409)
                self.assertEqual(request('POST', '/api/power', {'action': 'stop', 'id': new_id}, 'new')[0], 200)
                self.wait()
                self.assertEqual(self.observation.status()['received'], 1)
                self.assertEqual(self.observation.status()['headset']['deviceId'], 'new')
        finally:
            conn.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join()

    def test_early_remote_smoke_lock_has_structured_reason_without_sensor_reads(self):
        self.lock.mkdir()
        output = io.StringIO()
        with patch.object(frame_power.sampler, 'snapshot') as sensor, contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(frame_power.sampler.main(['--probe', '--stream']), 75)
        sensor.assert_not_called()
        self.assertIn('Smoke session active', json.loads(output.getvalue())['finished']['stopped'])

    def test_phone_can_import_without_desktop_sampler_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            import shutil
            shutil.copyfile(ROOT / 'ui/frame_power.py', Path(tmp) / 'frame_power.py')
            program = 'import sys; sys.path.insert(0, sys.argv[1]); import frame_power; assert frame_power.Observation().status()["id"] is None'
            result = subprocess.run([sys.executable, '-I', '-B', '-c', program, tmp],
                                    env={**os.environ, 'FRAME_LOCAL': '1'}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_packaged_resources_under_isolated_python(self):
        config = json.loads((ROOT / 'app/package.json').read_text())
        # Materialize exactly the Python resources selected by electron-builder.
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp)
            import shutil
            for spec in config['build']['extraResources']:
                if spec.get('to') not in ('ui', 'scripts'):
                    continue
                source = ROOT / 'app' / spec['from']
                for pattern in spec['filter']:
                    for file in source.glob(pattern):
                        if file.is_file():
                            dest = resources / spec['to'] / file.name
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(file, dest)
            program = ('import sys; sys.path.insert(0, sys.argv[1]); import frame_power; '
                       'p=frame_power.sampler.remote_payload(); '
                       'assert "def snapshot" in p and "def battery" in p; '
                       'o=frame_power.Observation(); assert not o.status()["running"]')
            run = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(resources / 'ui')], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        run = subprocess.run(['node', '--test', str(ROOT / 'tests/power_desktop.cjs')], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
