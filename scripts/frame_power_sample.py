"""Bounded read-only Frame measurements; no device files are written.

The host sends this and frame_status.py over one trusted SSH connection. Only
battery() and CPU tick helpers are reused: no OpenVR, services or analytics.
"""
import argparse
import csv
import glob
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import time

LOCK = Path('/tmp/frame-test.lock')
UNAVAILABLE = 'unavailable: not reported, unreadable or invalid'


def read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None


def number(path, scale=1, minimum=None, maximum=None):
    try:
        value = int(read(path)) * scale
        if not math.isfinite(value):
            return None
        if minimum is not None and value < minimum or maximum is not None and value > maximum:
            return None
        return round(value, 6)
    except (TypeError, ValueError, OverflowError):
        return None


def snapshot(status, before):
    if LOCK.exists():
        raise RuntimeError('Smoke session active (/tmp/frame-test.lock); no sensors read.')
    ticks = status.cpu_ticks()
    readings = {}

    def add(key, value, unit, source):
        readings[key] = {'value': value, 'unit': unit, 'source': source,
                         'state': 'available' if value is not None else UNAVAILABLE}

    battery = status.battery() or {}
    for field, unit in (('percent', '%'), ('status', 'state'), ('watts', 'W'),
                        ('tempC', 'C')):
        value = battery.get(field)
        if field == 'status' and value not in ('Charging', 'Discharging', 'Not charging', 'Full'):
            value = None
        add('battery.' + field, value, unit, battery.get('source'))
    add('cpu.percent', status.cpu_percent(before, ticks), '%', '/proc/stat')
    if before is None:
        readings['cpu.percent']['state'] = 'unavailable: needs two valid CPU tick samples'
    add('gpu.clock', number('/sys/class/devfreq/3d00000.gpu/cur_freq', 1e-6, 0),
        'MHz', '/sys/class/devfreq/3d00000.gpu/cur_freq')

    # Discover by driver name/label, never assume a hwmon index. Keep source
    # paths and channel numbers to distinguish duplicate labels.
    for node in sorted(glob.glob('/sys/class/hwmon/hwmon*')):
        name = read(node + '/name') or Path(node).name
        for path in sorted(glob.glob(node + '/power*_input')):
            channel = Path(path).name[:-6]
            label = read(node + '/' + channel + '_label') or channel
            add(f'rail.{name}.{label}.{channel}', number(path, 1e-6, 0), 'W', path)
        for path in sorted(glob.glob(node + '/fan*_input')):
            add(f'fan.{name}.{Path(path).stem}', number(path, minimum=0), 'RPM', path)
        # pwm1 on Frame's driver is percent; leave raw to avoid assuming the
        # generic hwmon 0..255 scale on other drivers or later firmware.
        if name == 'slg4ax46073v':
            add('fan.pwmRaw', number(node + '/pwm1', minimum=0), 'raw', node + '/pwm1')
    for node in sorted(glob.glob('/sys/class/thermal/thermal_zone*')):
        name = read(node + '/type') or Path(node).name
        add(f'thermal.{name}.{Path(node).name}', number(node + '/temp', 0.001, -273.15, 200),
            'C', node + '/temp')
    for node in sorted(glob.glob('/sys/bus/iio/devices/iio:device*')):
        for path in sorted(glob.glob(node + '/in_temp_*_input')):
            add(f'board.{Path(node).name}.{Path(path).stem}', number(path, 0.001, -273.15, 200),
                'C', path)
        for field in ('iin', 'ichg'):
            path = node + '/in_current_pm8550b_' + field + '_fb_input'
            # Known names, but no fixed IIO index; absent channels are covered
            # by group availability below.
            if Path(path).exists():
                add(f'charger.{Path(node).name}.{field}', number(path, 1e-6), 'A', path)
        if read(node + '/name') == 'vcnl4000':
            add('proximity.raw', number(node + '/in_proximity_raw', minimum=0),
                'raw', node + '/in_proximity_raw')
    unavailable = [group for group in ('rail', 'fan', 'thermal', 'board', 'charger', 'proximity')
                   if not any(k.startswith(group + '.') and v['value'] is not None
                              for k, v in readings.items())]
    os_info = dict(line.split('=', 1) for line in (read('/etc/os-release') or '').splitlines()
                   if '=' in line)
    return {'time': time.time(), 'osBuild': os_info.get('BUILD_ID', '').strip('"') or None,
            'readings': readings, 'unavailableGroups': unavailable}, ticks


def summarize(samples):
    result = {}
    keys = sorted({key for sample in samples for key in sample['readings']})
    for key in keys:
        rows = [s['readings'][key] for s in samples if key in s['readings']]
        values = [r['value'] for r in rows if r['value'] is not None]
        item = {'unit': rows[0]['unit'], 'sources': sorted({r['source'] for r in rows if r['source']}),
                'available': len(values), 'unavailable': len(samples) - len(values)}
        if values and all(isinstance(v, (int, float)) for v in values):
            item.update(min=min(values), max=max(values), mean=round(sum(values) / len(values), 6),
                        first=values[0], last=values[-1])
        else:
            item['states'] = sorted(set(values))
        result[key] = item
    return result


def collect(status, count, interval):
    samples, before = [], None
    started = time.monotonic()
    stopped = None
    for index in range(count):
        if index:
            time.sleep(max(0, started + index * interval - time.monotonic()))
        try:
            sample, before = snapshot(status, before)
        except RuntimeError as exc:
            stopped = str(exc)
            break
        sample['elapsedSeconds'] = round(time.monotonic() - started, 6)
        samples.append(sample)
    return {'schemaVersion': 1, 'requestedSamples': count, 'intervalSeconds': interval,
            'stopped': stopped, 'samples': samples, 'summary': summarize(samples)}


def csv_samples(report):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('time', 'elapsedSeconds', 'metric', 'value', 'unit', 'source', 'state'))
    for sample in report['samples']:
        for key, row in sample['readings'].items():
            # csv quoting does not prevent spreadsheet formulas in labels.
            def cell(value):
                return "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value
            writer.writerow([cell(v) for v in (sample['time'], sample['elapsedSeconds'], key,
                                               row['value'], row['unit'], row['source'], row['state'])])
        for group in sample['unavailableGroups']:
            writer.writerow((sample['time'], sample['elapsedSeconds'], group, '', '', '', UNAVAILABLE))
    return output.getvalue()


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--count', type=int, default=12, help='samples, 1..720 (default 12)')
    ap.add_argument('--interval', type=float, default=5, help='seconds, 1..60 (default 5)')
    ap.add_argument('--csv', action='store_true', help='CSV samples on stdout; JSON summary on stderr')
    ap.add_argument('--probe', action='store_true', help=argparse.SUPPRESS)
    return ap


def remote_payload():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'ui/frame_status.py').read_text()
    # Executing as a module prevents frame_status.main() from probing unrelated
    # status. Nothing is installed, cached or logged on the headset.
    return ('import types, sys\n'
            'status = types.ModuleType("frame_status")\n'
            f'exec(compile({source!r}, "frame_status.py", "exec"), status.__dict__)\n'
            'sys.modules["frame_status"] = status\n' + Path(__file__).read_text())


def main(argv=None):
    ap = parser()
    args = ap.parse_args(argv)
    if not 1 <= args.count <= 720 or not math.isfinite(args.interval) or not 1 <= args.interval <= 60:
        ap.error('count must be 1..720 and interval must be finite, 1..60 seconds')
    # Also honor a coordinator lock on the computer before opening SSH.
    if LOCK.exists():
        print('Smoke session active (/tmp/frame-test.lock); no SSH or sensors accessed.', file=sys.stderr)
        return 75
    if args.probe:
        import frame_status
        report = collect(frame_status, args.count, args.interval)
    else:
        command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=5',
                   '-o', 'ServerAliveCountMax=2', 'frame',
                   'python3', '-', '--probe', '--count', str(args.count), '--interval', str(args.interval)]
        try:
            run = subprocess.run(command, input=remote_payload(), text=True, capture_output=True,
                                 timeout=args.count * args.interval + 30)
            if run.returncode:
                print('Read-only sample failed: ' + (run.stderr.strip() or f'SSH exit {run.returncode}'),
                      file=sys.stderr)
                return run.returncode
            report = json.loads(run.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            print(f'Read-only sample unavailable: {exc}', file=sys.stderr)
            return 1
    if args.csv:
        sys.stdout.write(csv_samples(report))
        print(json.dumps({k: v for k, v in report.items() if k != 'samples'}, allow_nan=False), file=sys.stderr)
    else:
        print(json.dumps(report, allow_nan=False))
    return 75 if report['stopped'] else 0


if __name__ == '__main__':
    sys.exit(main())
