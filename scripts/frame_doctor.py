"""Read-only doctor. Also sent over SSH on stdin; never installed on the Frame.

Only fixed summaries leave the probe: no raw journals, addresses, account IDs,
process arguments, environment, key material or HTTP response bodies.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

SECTIONS = ('Boot and crash history', 'Wi-Fi', 'Displays and SteamVR',
            'Steam and storage', 'Idle sleep and keep-awake', 'Remote wake',
            'Lepton (Android)', 'Chromium XR', 'KDE Connect',
            'Streaming and capture', 'Panels')


def run(args, timeout=4, **kwargs):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return None


def command(*args):
    r = run(list(args))
    return r.stdout if r is not None and r.returncode == 0 else None


def journal(*args):
    # Even exit 0 can mean the account cannot see the system journal.
    r = run(['journalctl', '--no-pager', '-q', '-n', '2000', *args])
    if r is None or r.returncode or r.stderr.strip() or not r.stdout.strip():
        return None
    return r.stdout


def snapshot():
    values = []
    for unit in ('steam', 'steamvr'):
        s = command('systemctl', '--user', 'show', unit + '.service',
                    '-p', 'NRestarts', '--value')
        if s is None or not s.strip().isdigit():
            return None
        values.append(int(s.strip()))
        p = Path('/run/user') / str(os.getuid()) / (unit + '-short-session-tracker')
        try:
            values.append(p.stat().st_size)
        except FileNotFoundError:
            values.append(0)
        except OSError:
            return None
    return values


def guard():
    first = snapshot()
    time.sleep(2)
    second = snapshot()
    if first is None or second is None:
        return 'unknown'
    if any(b > a for a, b in zip(first, second)):
        return 'loop'
    if first != second:
        return 'unknown'  # counters reset or tracker replaced during the sample
    if second[1] or second[3]:
        return 'risk'  # avoid a long run even if a short sample missed the loop
    return 'stable'


def signal_check(text, pattern, problem, healthy):
    if text is None:
        return ['UNKNOWN', 'Evidence unavailable; consult the runbook locally.']
    return ['WARN', problem] if re.search(pattern, text, re.I) else ['OK', healthy]


def storage():
    # devkit-game may be a separate mount (including in the fake Frame).
    try:
        paths = [Path.home()]
        games = Path.home() / 'devkit-game'
        if games.exists():
            paths.append(games)
        free = min(shutil.disk_usage(p).free for p in paths)
        if free < 16 * 1024**2:
            return ['BROKEN', 'Less than 16 MiB free; review storage in Frame Control before installing.']
        if free < 256 * 1024**2:
            return ['WARN', 'Less than 256 MiB free; review storage before large installs.']
        return ['OK', 'Home and title storage have at least 256 MiB free.']
    except OSError:
        return ['UNKNOWN', 'Storage could not be read.']


def probe():
    state = guard()
    if state != 'stable':
        return {'guard': state, 'checks': []}
    kernel = journal('-b', '-k', '--since=-10min')
    recent = journal('-b', '--since=-10min')
    previous = journal('-b', '-1', '-k')
    crashes = command('coredumpctl', 'list', '--no-pager', '--since=-1d')
    checks = []
    boot = signal_check(previous, r'Unable to handle kernel|Internal error|Kernel panic',
                        'Previous boot has a kernel oops; this alone does not prove an unclean reset.',
                        'No kernel-oops signature in the sampled previous boot.')
    if crashes is None and boot[0] != 'WARN':
        boot = ['UNKNOWN', 'Crash history unavailable; inspect boot history locally.']
    elif crashes is not None and boot[0] != 'WARN' and re.search(r'SIG(SEGV|ABRT)|\b(SEGV|ABRT)\b', crashes):
        boot = ['WARN', 'Crash records exist in the last day; inspect locally using the runbook.']
    checks.append(boot)
    wifi = command('nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device')
    checks.append(signal_check(wifi if wifi and 'wlan0:wifi:' in wifi else None, r'wlan0:wifi:(unavailable|disconnected|failed)',
                               'Wi-Fi is unavailable or disconnected; check Steam Settings > Internet. Never reload ath12k.',
                               'No unavailable/disconnected wlan0 reported; other interfaces may differ.'))
    checks.append(signal_check(kernel, r'wait for video done',
                               'Display timeouts observed; follow display recovery before touching Steam.',
                               'No display-timeout signature in recent kernel sample.'))
    if checks[-1][0] != 'WARN' and recent is not None and re.search(r'left-over process|steamvr.service: Failed|!modifiers.empty', recent):
        checks[-1] = ['WARN', 'SteamVR/session failure signature observed; inspect locally before restarting anything.']
    disk = storage()
    if disk[0] == 'OK' and not (Path.home() / '.local/share/Steam/.install-complete').exists():
        disk = ['WARN', 'Steam install marker is missing; do not restart Steam for diagnosis. Consult the runbook.']
    checks.append(disk)
    awake = command('systemctl', '--user', 'show', 'fc-keep-awake.service', '-p', 'ActiveState', '--value')
    checks.append(['UNKNOWN', 'Keep-awake state unavailable.'] if awake is None or not awake.strip() else
                  ['WARN', 'Keep-awake is active; leave it with its owner.'] if awake.strip() == 'active' else
                  ['OK', 'Keep-awake is inactive; diagnostics do not inhibit sleep.'])
    wow = command('iw', 'phy', 'phy0', 'wowlan', 'show')
    checks.append(['UNKNOWN', 'WoWLAN state unavailable; remote wake is not verified.'] if wow is None else
                  ['OK', 'WoWLAN is disabled; wake the headset with its power button.'] if 'WoWLAN is disabled' in wow else
                  ['WARN', 'WoWLAN may be armed; review the runbook. Remote wake is not reliable.'])
    checks.append(signal_check(recent, r'Listen failed for HOST TCP|binder_user_error|Clearing baked app data',
                               'Android failure signature observed; inspect Lepton locally before retrying.',
                               'No known Android failure signature in recent journal sample.'))
    checks.append(signal_check(crashes, r'chromium|/chrome\b',
                               'Chromium crash history found; update/relaunch the panel through its normal UI.',
                               'No Chromium crash signature in available crash history.'))
    kde = run(['pgrep', '-f', 'frame-control/kdeconnect/root/usr/lib/kdeconnectd'])
    checks.append(['UNKNOWN', 'KDE Connect process check unavailable.'] if kde is None or kde.returncode not in (0, 1) else
                  ['OK', 'KDE Connect process found.'] if kde.returncode == 0 else
                  ['WARN', 'KDE Connect is not running; normal if keyboard/trackpad sharing is off.'])
    checks.append(signal_check(crashes, r'ffmpeg',
                               'Capture crash history found; consult software-encoder guidance in the runbook.',
                               'No ffmpeg crash signature in available crash history.'))
    checks.append(['UNKNOWN', 'Panel placement needs visual confirmation; open one panel at a time.'])
    # A short sample is not proof that Steam is healthy. Recheck after collecting.
    after = guard()
    return {'guard': after, 'checks': checks if after == 'stable' else []}


SSH_OPTIONS = ['BatchMode=yes', 'NumberOfPasswordPrompts=0', 'StrictHostKeyChecking=yes',
               'UpdateHostKeys=no', 'CheckHostIP=no', 'ConnectTimeout=3', 'ConnectionAttempts=1',
               'ControlMaster=no', 'ControlPath=none', 'ClearAllForwardings=yes',
               'PermitLocalCommand=no', 'RemoteCommand=none', 'RequestTTY=no',
               'ProxyCommand=none', 'ProxyJump=none', 'ForwardAgent=no', 'ForwardX11=no']


def ssh_args(alias, host=None, identity=None):
    args = ['ssh']
    for opt in SSH_OPTIONS:
        args += ['-o', opt]
    if host:
        args += ['-o', 'HostName=' + host, '-o', 'HostKeyAlias=' + identity]
    return args + [alias]


def failure(text):
    # Never echo SSH stderr: it can contain addresses, paths or remote text.
    if 'REMOTE HOST IDENTIFICATION HAS CHANGED' in text:
        return 'SSH identity changed; use Devices > Check its key after verifying the headset. Do not delete known_hosts.'
    if 'Host key verification failed' in text:
        return 'SSH identity is untrusted; verify it through Set Up Connection or Devices > Check its key.'
    if 'Permission denied' in text:
        return "SSH key rejected; use Set Up Connection, then Developer > Pair new host in the headset."
    return 'No SSH response; wake the headset, check the network/cable and enable Developer Mode.'


def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def report(data):
    state = data.get('guard')
    if state != 'stable':
        status = 'BROKEN' if state == 'loop' else 'WARN' if state == 'risk' else 'UNKNOWN'
        message = {'loop': 'Counters are rising. Stop diagnostics; use the runbook health-check recovery procedure.',
                   'risk': 'Health-check trackers contain failures. Deeper checks skipped; review the runbook before recovery.'}
        print(status + ' Restart safety: ' + message.get(state, 'Cannot verify restart counters; deeper checks skipped for safety.'))
        for i, label in enumerate(SECTIONS, 1):
            print(f'UNKNOWN {i}. {label}: Skipped until restart safety is verified.')
        return 1
    checks = data.get('checks')
    # Treat the remote endpoint as untrusted. Only accept pairs from our own
    # fixed vocabulary by matching against the production probe's messages.
    if not isinstance(checks, list) or len(checks) != len(SECTIONS):
        print('UNKNOWN Probe: Incomplete diagnostic response; no raw output displayed.')
        return 1
    for check in checks:
        if (not isinstance(check, list) or len(check) != 2 or check[0] not in ('OK', 'WARN', 'BROKEN', 'UNKNOWN')
                or not isinstance(check[1], str) or check[1] not in MESSAGES):
            print('UNKNOWN Probe: Unexpected diagnostic response; no raw output displayed.')
            return 1
    print('OK Restart safety: No rising counters during short samples; this is not a health guarantee.')
    for i, (label, (status, message)) in enumerate(zip(SECTIONS, checks), 1):
        print(f'{status} {i}. {label}: {message}')
    return int(any(c[0] != 'OK' for c in checks))


def valid_data(data):
    """Validate before saving, comparing or deriving any recommendation."""
    if (not isinstance(data, dict) or set(data) != {'guard', 'checks'}
            or data.get('guard') not in ('stable', 'loop', 'risk', 'unknown')):
        return False
    checks = data.get('checks')
    if data['guard'] != 'stable':
        return checks == []
    return (isinstance(checks, list) and len(checks) == len(SECTIONS)
            and all(isinstance(c, list) and len(c) == 2
                    and c[0] in ('OK', 'WARN', 'BROKEN', 'UNKNOWN')
                    and isinstance(c[1], str) and c[1] in MESSAGES for c in checks))


def repair_plan(data):
    print('Repair plan (READ-ONLY): no commands executed; no automatic repair is available.')
    if data['guard'] != 'stable':
        print('BLOCKED: Restart safety is unverified or unsafe. Needs your hands: review the runbook health-check recovery with the headset user; do not restart services.')
        return
    # Each action needs the exact section, severity AND recognized evidence.
    actions = {
        (1, 'WARN', 'Wi-Fi is unavailable or disconnected; check Steam Settings > Internet. Never reload ath12k.'):
            'Needs your hands: check Steam Settings > Internet. Do not reload ath12k.',
        (2, 'WARN', 'Display timeouts observed; follow display recovery before touching Steam.'):
            'Needs your hands: inspect the display in-headset and review display recovery before any Steam action.',
        (3, 'BROKEN', 'Less than 16 MiB free; review storage in Frame Control before installing.'):
            'Needs your hands: review Game storage and use Steam storage management after choosing what to keep; no files are deleted by doctor.',
        (3, 'WARN', 'Less than 256 MiB free; review storage before large installs.'):
            'Needs your hands: review Game storage before installing; choose any storage changes yourself.',
        (3, 'WARN', 'Steam install marker is missing; do not restart Steam for diagnosis. Consult the runbook.'):
            'Needs your hands: inspect Steam installation/extraction locally with the runbook. A missing marker does not authorize repair or restart.',
        (4, 'WARN', 'Keep-awake is active; leave it with its owner.'):
            'Leave keep-awake with its owner; do not take ownership or change idle settings.',
    }
    for i, (status, message) in enumerate(data['checks']):
        if status == 'OK':
            continue
        action = actions.get((i, status, message))
        if action is None:
            action = ('Collect missing evidence locally; no repair is justified.' if status == 'UNKNOWN'
                      else 'Review this signal locally with the runbook; it does not establish a safe automatic fix.')
        print(f'PLAN {i + 1}. {SECTIONS[i]}: {action}')


def compare(before, after):
    print('Before/after diagnostics: observations only; changes do not prove repair or causation.')
    print('Restart safety: ' + before['guard'] + ' -> ' + after['guard'])
    if before['guard'] != 'stable' or after['guard'] != 'stable':
        print('Comparison blocked: deeper checks were skipped in at least one sample; no improvement claimed.')
        return
    for i, label in enumerate(SECTIONS):
        a, b = before['checks'][i], after['checks'][i]
        detail = 'unchanged' if a == b else 'evidence changed'
        print(f'{i + 1}. {label}: {a[0]} -> {b[0]} ({detail})')
        if a != b:
            print('  Before evidence: ' + a[1])
            print('  After evidence: ' + b[1])


def load_baseline(path):
    # Local reports are untrusted too; bound input and never echo file contents.
    with open(path, 'rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError()
    saved = json.loads(raw)
    if (not isinstance(saved, dict) or saved.get('version') != 1
            or not isinstance(saved.get('target'), str)
            or not re.fullmatch('[a-f0-9]{64}', saved['target'])
            or not valid_data(saved.get('diagnostics'))):
        raise ValueError()
    return saved


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only Frame setup diagnostics. Never pairs, repairs or asks for a password.')
    parser.add_argument('--alias', default='frame', help='Existing trusted SSH alias (default: frame)')
    parser.add_argument('--lan', help='Optional LAN IP or host name; SteamOS 0.5.6 no longer publishes .local names')
    parser.add_argument('--usb', default='10.86.200.233', help='USB fallback IP; use only with the intended headset connected')
    parser.add_argument('--plan', action='store_true', help='Print a read-only repair plan from recognized evidence')
    parser.add_argument('--save-report', metavar='FILE', help='Create a local JSON baseline (never overwrite an existing file)')
    parser.add_argument('--compare-before', metavar='FILE', help='Compare a saved baseline with this fresh read-only run')
    args = parser.parse_args(argv)
    baseline = None
    if args.compare_before:
        try:
            baseline = load_baseline(args.compare_before)
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
            print('UNKNOWN Baseline: Cannot read a valid doctor report; no comparison performed.')
            return 2
    for value in (args.alias, args.lan, args.usb):
        if value is None:
            continue
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,252}', value):
            parser.error('Use a plain alias, hostname or IP address.')
    print('Frame doctor: read-only; no passwords, pairing, repairs or raw logs. Reports are saved only with --save-report.')
    if not shutil.which('ssh'):
        print('BROKEN Setup: Install an OpenSSH client, then run Set Up Connection.')
        return 2
    config = run(ssh_args(args.alias)[:-1] + ['-G', args.alias])
    if config is None or config.returncode:
        print('UNKNOWN Setup: SSH configuration could not be read; check it locally.')
        return 2
    settings = dict(line.split(' ', 1) for line in config.stdout.splitlines() if ' ' in line)
    identity = settings.get('hostkeyalias') or settings.get('hostname', args.alias)
    # Bind reports to the configured logical SSH target, across LAN/USB fallback.
    # This is configuration continuity, not proof of physical headset identity.
    target = hashlib.sha256(json.dumps([args.alias, identity, settings.get('hostname'),
                                      settings.get('user'), settings.get('port'), args.lan, args.usb]).encode()).hexdigest()
    if baseline is not None and baseline['target'] != target:
        print('UNKNOWN Baseline: SSH target configuration differs; comparison refused.')
        return 2
    source = Path(__file__).read_text()
    routes = [('configured alias (Tailscale if configured)', None)]
    if args.lan:
        routes.append(('LAN', args.lan))
    routes.append(('USB-C', args.usb))
    for label, host in routes:
        result = run(ssh_args(args.alias, host, identity) + ['python3 -B - --probe'], timeout=90, input=source)
        if result is not None and result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if not valid_data(data):
                    raise ValueError()
            except (ValueError, RecursionError):
                print('UNKNOWN Probe: Invalid response; check Python 3 availability on the headset. No raw output displayed.')
                return 1
            print('OK Connection: ' + label + '; verified SSH identity and key login.')
            code = report(data)
            if args.plan:
                repair_plan(data)
            if baseline is not None:
                compare(baseline['diagnostics'], data)
            if args.save_report:
                try:
                    # Exclusive create prevents clobbering a baseline or following a symlink.
                    fd = os.open(args.save_report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w') as stream:
                        json.dump({'version': 1, 'target': target, 'diagnostics': data}, stream)
                        stream.write('\n')
                    print('OK Report: Local baseline created; review it before sharing.')
                except OSError:
                    print('UNKNOWN Report: Could not create local baseline; existing files are never overwritten.')
                    return 2
            return code
        if result is not None and result.returncode != 255:
            print('UNKNOWN Probe: SSH connected but diagnostics failed; check Python 3 on the headset.')
            return 1
        reason = failure(result.stderr if result is not None else '')
        print('WARN Connection (' + label + '): ' + reason)
    # No /register call: an open devkit port cannot prove pairing mode is enabled.
    hosts = (settings.get('hostname', args.alias), args.lan, args.usb)
    if any(port_open(host, 32000) for host in hosts):
        print('WARN Pairing: Devkit port responds. Use Set Up Connection and Developer > Pair new host; no pairing request was sent.')
    else:
        print('UNKNOWN Pairing: Devkit port did not respond. Needs your hands: wake headset, enable Developer Mode and check its address.')
    for i, label in enumerate(SECTIONS, 1):
        print(f'UNKNOWN {i}. {label}: No authenticated SSH path.')
    return 2


# Derive the output allowlist from literal strings, not remote data. This module
# has no dynamic diagnostic messages. AST stays stdlib and runs only locally.
def messages():
    import ast
    tree = ast.parse(Path(__file__).read_text())
    allowed = set()
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef) or function.name not in ('probe', 'storage', 'signal_check'):
            continue
        for node in ast.walk(function):
            if (isinstance(node, ast.List) and len(node.elts) == 2
                    and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts)
                    and node.elts[0].value in ('OK', 'WARN', 'BROKEN', 'UNKNOWN')):
                allowed.add(node.elts[1].value)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'signal_check':
                allowed.update(arg.value for arg in node.args[2:4] if isinstance(arg, ast.Constant))
    return allowed


if __name__ == '__main__':
    if sys.argv[1:] == ['--probe']:
        print(json.dumps(probe()))
    else:
        MESSAGES = messages()
        sys.exit(main())
