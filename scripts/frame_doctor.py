"""Read-only doctor. Also sent over SSH on stdin; never installed on the Frame.

Only fixed summaries leave the probe: no raw journals, addresses, account IDs,
process arguments, environment, key material or HTTP response bodies.
"""
import argparse
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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only Frame setup diagnostics. Never pairs, repairs or asks for a password.')
    parser.add_argument('--alias', default='frame', help='Existing trusted SSH alias (default: frame)')
    parser.add_argument('--lan', default='frame.local', help='LAN fallback host/IP')
    parser.add_argument('--usb', default='10.86.200.233', help='USB fallback IP; use only with the intended headset connected')
    args = parser.parse_args(argv)
    for value in (args.alias, args.lan, args.usb):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,252}', value):
            parser.error('Use a plain alias, hostname or IP address.')
    print('Frame doctor: read-only; no passwords, pairing, repairs or raw logs. No report is saved.')
    if not shutil.which('ssh'):
        print('BROKEN Setup: Install an OpenSSH client, then run Set Up Connection.')
        return 2
    config = run(ssh_args(args.alias)[:-1] + ['-G', args.alias])
    if config is None or config.returncode:
        print('UNKNOWN Setup: SSH configuration could not be read; check it locally.')
        return 2
    settings = dict(line.split(' ', 1) for line in config.stdout.splitlines() if ' ' in line)
    identity = settings.get('hostkeyalias') or settings.get('hostname', args.alias)
    source = Path(__file__).read_text()
    for label, host in (('configured alias (Tailscale if configured)', None), ('LAN', args.lan), ('USB-C', args.usb)):
        result = run(ssh_args(args.alias, host, identity) + ['python3 -B - --probe'], timeout=90, input=source)
        if result is not None and result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if not isinstance(data, dict):
                    raise ValueError()
            except ValueError:
                print('UNKNOWN Probe: Invalid response; check Python 3 availability on the headset. No raw output displayed.')
                return 1
            print('OK Connection: ' + label + '; verified SSH identity and key login.')
            return report(data)
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
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


if __name__ == '__main__':
    if sys.argv[1:] == ['--probe']:
        print(json.dumps(probe()))
    else:
        MESSAGES = messages()
        sys.exit(main())
