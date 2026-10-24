"""Offline HTML exports and streamed transport, with real local child cleanup."""
import sandbox  # noqa: F401
import base64
import contextlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import frame_power_sample as power
import frame_power_report as page


SAMPLE = {'time': 1, 'elapsedSeconds': 0, 'osBuild': 'test',
          'readings': {'battery.watts': {'value': 0, 'unit': 'W', 'source': '/sys/battery', 'state': 'available'},
                       'thermal.<script>alert(1)</script>': {'value': None, 'unit': 'C', 'source': '/sys/temp', 'state': power.UNAVAILABLE}},
          'unavailableGroups': ['proximity']}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.scripts += 1
        if tag == 'a':
            self.links[attrs['download']] = base64.b64decode(attrs['href'].split(',', 1)[1]).decode()


class Report(unittest.TestCase):
    def collect(self, program, count=1):
        with contextlib.redirect_stderr(io.StringIO()):
            return power.stream_report([sys.executable, '-c', program], '', count, 1)

    def test_completed_stream_preserves_zero_unknown_units_and_downloads(self):
        event = json.dumps({'sample': SAMPLE})
        program = f'import sys; sys.stdin.read(); print({event!r}); print(\'{{"finished": {{"stopped": null}}}}\')'
        report = self.collect(program)
        self.assertIsNone(report['stopped'])
        self.assertEqual(report['samples'], [SAMPLE])
        markup = page.render(report, power.csv_samples(report))
        parser = Links()
        parser.feed(markup)
        self.assertEqual(parser.scripts, 0)
        self.assertIn('&lt;script&gt;', markup)
        self.assertIn('<td>0</td>', markup)
        self.assertIn('<td>Unknown</td>', markup)
        self.assertIn('<td>C</td>', markup)
        self.assertIn('scope="row"', markup)
        self.assertEqual(json.loads(parser.links['frame-power.json']), report)
        self.assertEqual(parser.links['frame-power.csv'], power.csv_samples(report))
        self.assertIn(power.UNAVAILABLE, parser.links['frame-power.csv'])

    def test_transport_failure_retains_received_samples_as_incomplete(self):
        event = json.dumps({'sample': SAMPLE})
        report = self.collect(f'import sys; sys.stdin.read(); print({event!r}); sys.exit(255)', 2)
        self.assertEqual(report['samples'], [SAMPLE])
        self.assertIn('SSH exit 255', report['stopped'])

    def test_lock_stop_retains_samples(self):
        event = json.dumps({'sample': SAMPLE})
        end = json.dumps({'finished': {'stopped': 'Smoke session active'}})
        report = self.collect(f'import sys; sys.stdin.read(); print({event!r}); print({end!r}); sys.exit(75)', 2)
        self.assertEqual(report['stopped'], 'Smoke session active')
        self.assertEqual(len(report['samples']), 1)

    def test_user_stop_terminates_only_local_child_and_retains_samples(self):
        children = []
        real_popen = subprocess.Popen
        def spawn(*args, **kwargs):
            proc = real_popen(*args, **kwargs)
            children.append(proc)
            return proc
        with mock.patch.object(power.subprocess, 'Popen', side_effect=spawn), \
             mock.patch.object(power.queue.Queue, 'get', side_effect=[json.dumps({'sample': SAMPLE}), KeyboardInterrupt]):
            report = self.collect('import sys,time; sys.stdin.read(); time.sleep(30)', 2)
        self.assertEqual(report['samples'], [SAMPLE])
        self.assertIn('Stopped by user', report['stopped'])
        self.assertIsNotNone(children[0].poll())

    def test_canceled_launch_does_not_open_ssh(self):
        import threading
        stop = threading.Event()
        stop.set()
        with mock.patch.object(power.subprocess, 'Popen') as spawn:
            report = power.stream_report(['ssh', 'frame'], '', 12, 5, stop_event=stop)
        spawn.assert_not_called()
        self.assertIn('Stopped before collection', report['stopped'])

    def test_stop_interrupts_child_that_never_reads_payload(self):
        import threading
        stop = threading.Event()
        timer = threading.Timer(0.1, stop.set)
        timer.start()
        try:
            report = power.stream_report([sys.executable, '-c', 'import time; time.sleep(30)'],
                                         'x' * 1048576, 1, 1, stop_event=stop)
        finally:
            timer.cancel()
        self.assertIn('Stopped', report['stopped'])
        self.assertEqual(report['samples'], [])

    def test_invalid_stream_is_not_completed(self):
        report = self.collect('import sys; sys.stdin.read(); print("not json")')
        self.assertIn('interrupted', report['stopped'])
        self.assertEqual(report['samples'], [])

    def test_deadline_terminates_child(self):
        with mock.patch.object(power.time, 'monotonic', side_effect=[0, 40]):
            report = self.collect('import sys,time; sys.stdin.read(); time.sleep(30)')
        self.assertIn('Timed out', report['stopped'])

    def test_export_bounds_and_existing_file_fail_before_ssh(self):
        with tempfile.TemporaryDirectory() as temp:
            existing = Path(temp) / 'report.html'
            existing.write_text('keep')
            for args in (['--html', str(existing)], ['--html', 'new.html', '--count', '11', '--interval', '60'],
                         ['--html', 'new.html', '--csv']):
                with mock.patch.object(power.subprocess, 'Popen') as spawn, contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        power.main(args)
                spawn.assert_not_called()
            self.assertEqual(existing.read_text(), 'keep')

    def test_cli_writes_incomplete_report_and_returns_nonzero(self):
        report = {'schemaVersion': 1, 'requestedSamples': 2, 'intervalSeconds': 1,
                  'stopped': 'Stopped by user', 'samples': [SAMPLE], 'summary': power.summarize([SAMPLE])}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.html'
            with mock.patch.object(power, 'stream_report', return_value=report), \
                 mock.patch.object(power, 'LOCK', Path(temp) / 'no-lock'), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(power.main(['--html', str(path)]), 75)
            self.assertIn('Stopped by user', path.read_text())

    def test_collect_emits_each_sample_before_completion(self):
        status = mock.Mock()
        with mock.patch.object(power, 'snapshot', return_value=(SAMPLE.copy(), None)):
            events = []
            report = power.collect(status, 1, 1, events.append)
        self.assertEqual(events, [{'sample': report['samples'][0]}])

    def test_failed_save_preserves_json_on_stdout(self):
        report = {'schemaVersion': 1, 'requestedSamples': 1, 'intervalSeconds': 1,
                  'stopped': None, 'samples': [SAMPLE], 'summary': power.summarize([SAMPLE])}
        with tempfile.TemporaryDirectory() as temp:
            output = io.StringIO()
            with mock.patch.object(power, 'stream_report', return_value=report), \
                 mock.patch.object(power, 'LOCK', Path(temp) / 'no-lock'), \
                 contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(output):
                code = power.main(['--html', str(Path(temp) / 'missing' / 'report.html')])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue()), report)

    def test_premature_completion_is_incomplete_even_with_clean_ssh_exit(self):
        report = self.collect('import sys; sys.stdin.read(); print(\'{"finished": {"stopped": null}}\')')
        self.assertIn('Incomplete', report['stopped'])
        self.assertEqual(report['samples'], [])
