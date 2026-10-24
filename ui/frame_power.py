"""One desktop observation using the read-only sampler; reports stay in memory."""
import json
from pathlib import Path
import sys
import threading
import time
import uuid

# Shared with the source-checkout CLI; shipped as explicit desktop resources.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    import frame_power_sample as sampler
    from frame_power_report import render
except ModuleNotFoundError as exc:
    # Phone/headset bundles host the same UI without desktop-only resources.
    if exc.name not in ('frame_power_sample', 'frame_power_report'):
        raise
    sampler = render = None

PRESETS = {'minute': (12, 5), 'five-minutes': (60, 5)}


class Observation:
    def __init__(self):
        self.lock = threading.RLock()
        self.report = None
        self.running = False
        self.thread = None
        self.cancel = None
        self.reason = None
        self.id = None
        self.started = None

    def status(self):
        with self.lock:
            return {'id': self.id, 'running': self.running, 'received': len(self.report['samples']) if self.report else 0,
                    'requested': self.report['requestedSamples'] if self.report else 0,
                    'headset': self.report['headset'] if self.report else None,
                    'started': self.started, 'stopped': self.report['stopped'] if self.report else None}

    def start(self, preset, route, headset):
        if sampler is None:
            raise ValueError('Desktop power-report resources are missing; reinstall the desktop app')
        if preset not in PRESETS:
            raise ValueError('Choose a one-minute or five-minute observation')
        with self.lock:
            if self.running:
                raise ValueError('An observation is already running')
            if sampler.LOCK.exists():
                raise ValueError('Smoke session active (/tmp/frame-test.lock); observation not started')
            count, interval = PRESETS[preset]
            self.id = uuid.uuid4().hex
            self.cancel = threading.Event()
            self.reason = None
            self.started = time.time()
            self.report = {'schemaVersion': 1, 'requestedSamples': count, 'intervalSeconds': interval,
                           'headset': headset, 'stopped': 'Observation in progress; received samples only',
                           'samples': [], 'summary': {}}
            self.running = True
            # Pin the route before the caller releases the server's route lock.
            command = [*route[:-1], '-T', '-o', 'StrictHostKeyChecking=yes',
                       '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2', route[-1],
                       'python3', '-', '--probe', '--count', str(count), '--interval', str(interval)]
            self.thread = threading.Thread(target=self._collect, args=(command, count, interval), daemon=True)
            self.thread.start()
            return self.status()

    def _collect(self, command, count, interval):
        def received(sample):
            with self.lock:
                self.report['samples'].append(sample)
        try:
            result = sampler.stream_report(command, sampler.remote_payload(), count, interval,
                                           self.cancel, received, discard_errors=True)
            with self.lock:
                result['headset'] = self.report['headset']
                result['stopped'] = self.reason or result['stopped']
                self.report = result
        except Exception as exc:
            with self.lock:
                self.report['stopped'] = self.reason or f'Observation interrupted: {exc}'
        finally:
            with self.lock:
                self.running = False

    def stop(self, reason='Stopped by user; received samples retained'):
        with self.lock:
            if self.running:
                self.reason = reason
                self.report['stopped'] = reason
                self.cancel.set()
            return self.status()

    def export(self, observation_id, format):
        if format not in ('html', 'json', 'csv'):
            raise ValueError('Unknown report format')
        with self.lock:
            if not self.report or observation_id != self.id:
                raise ValueError('This report was replaced; refresh the observation')
            # Independent snapshot, including samples already received while running.
            report = json.loads(json.dumps(self.report, allow_nan=False))
        report['summary'] = sampler.summarize(report['samples'])
        if format == 'json':
            return json.dumps(report, allow_nan=False, indent=2), 'application/json'
        csv = sampler.csv_samples(report)
        return (render(report, csv), 'text/html; charset=utf-8') if format == 'html' else (csv, 'text/csv; charset=utf-8')

    def shutdown(self):
        self.stop('App closed; received samples retained')
        if self.thread:
            self.thread.join(timeout=8)
