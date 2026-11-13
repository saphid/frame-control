"""Read-only PC checks for the Frame's observed USB-C network path.

The known Frame USB address was observed on a Mac in 2026-09. It is a clue,
not a promise that every Frame OS or host uses the same address. Never set an
interface address, accept a new SSH host key, or change a network route here.
"""
import argparse
import ipaddress
import json
import re
import socket
import subprocess

import frame_host

TARGET = '10.86.200.233'
SUBNET = ipaddress.ip_network('10.86.200.232/29')
ALIAS = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')


class Probe:
    def route_source(self):
        # UDP connect chooses a route but sends no packet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((TARGET, 22))
            return sock.getsockname()[0]

    def port_open(self):
        with socket.create_connection((TARGET, 22), timeout=2):
            return True

    def host_key_name(self, alias):
        result = frame_host.run_ssh(['ssh', '-G', alias], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=5)
        if result.returncode:
            raise OSError('SSH configuration unavailable')
        settings = dict(line.split(None, 1) for line in result.stdout.splitlines() if ' ' in line)
        name = settings.get('hostkeyalias') or settings.get('hostname') or alias
        if not name or len(name) > 253 or name.startswith('-') or any(c.isspace() for c in name):
            raise ValueError('Invalid SSH host-key name')
        return name

    def ssh_check(self, alias, host_key_name):
        return frame_host.run_ssh([
            'ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'NumberOfPasswordPrompts=0', '-o', 'ConnectTimeout=5',
            '-o', 'ConnectionAttempts=1', '-o', 'ProxyCommand=none',
            '-o', 'ProxyJump=none', '-o', 'PermitLocalCommand=no',
            '-o', 'RemoteCommand=none', '-o', 'ClearAllForwardings=yes',
            '-o', 'ControlMaster=no', '-o', 'ControlPath=none',
            '-o', f'HostName={TARGET}',
            '-o', f'HostKeyAlias={host_key_name}', alias, 'true',
        ], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=9)


def check(identifier, title, status, detail):
    return {'id': identifier, 'title': title, 'status': status, 'detail': detail}


def diagnose(alias='frame', *, probe=None, local=False):
    """No headset request unless the PC chooses the known local USB subnet."""
    if local:
        return {'supported': False, 'state': 'unsupported', 'checks': [],
                'message': 'Run this doctor on your computer, not the headset.'}
    if not ALIAS.fullmatch(alias):
        raise ValueError('Choose one configured headset alias.')
    probe = probe or Probe()
    checks = []
    try:
        source = probe.route_source()
        wired = ipaddress.ip_address(source) in SUBNET and source != TARGET
    except (OSError, ValueError):
        source, wired = None, False
    if wired:
        checks.append(check('route', 'PC route to Frame USB address', 'ok',
                            f'This PC chooses {source} on the previously observed Frame USB subnet. This alone does not prove the cable or headset identity.'))
    else:
        checks.append(check('route', 'PC route to Frame USB address', 'unknown',
                            'No route using the previously observed 10.86.200.232/29 USB subnet. Check a data-capable USB-C cable, port and the PC network interface. This OS may use a different subnet.'))
        checks += [check('port', 'USB path SSH port', 'unknown', 'Skipped: the known local USB route was not observed.'),
                   check('ssh', 'Pinned headset SSH identity', 'unknown', 'Skipped: no known USB route; no headset was contacted.')]
        return {'supported': True, 'state': 'unknown', 'alias': alias, 'checks': checks}
    try:
        open_port = probe.port_open()
    except OSError:
        open_port = False
    if not open_port:
        checks += [check('port', 'USB path SSH port', 'warning',
                         'Port 22 did not answer on the observed USB route. Check the cable and whether Developer Mode SSH is enabled on the Frame.'),
                   check('ssh', 'Pinned headset SSH identity', 'unknown', 'Skipped: port 22 did not answer.')]
        return {'supported': True, 'state': 'partial', 'alias': alias, 'checks': checks}
    checks.append(check('port', 'USB path SSH port', 'ok', 'Port 22 answered on the observed USB route. This does not authenticate the headset.'))
    try:
        host_key_name = probe.host_key_name(alias)
        result = probe.ssh_check(alias, host_key_name)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result = None
    if result and result.returncode == 0:
        checks.append(check('ssh', 'Pinned headset SSH identity', 'ok',
                            'A read-only SSH command succeeded over the USB address using strict host-key checking.'))
    else:
        error = (result.stderr or '') if result else ''
        reason = ('The saved host key was not accepted. Verify and pair through the normal headset alias first; do not bypass host-key checking.'
                  if 'Host key verification failed' in error or 'No ' in error and 'host key is known' in error
                  else 'The USB SSH login did not complete. Check the saved headset key and Developer Mode SSH; no key or security setting was changed.')
        checks.append(check('ssh', 'Pinned headset SSH identity', 'warning', reason))
    return {'supported': True, 'state': 'ready' if checks[-1]['status'] == 'ok' else 'partial',
            'alias': alias, 'checks': checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only wired Frame connection doctor')
    parser.add_argument('--alias', default='frame', help='configured SSH alias (default: frame)')
    parser.add_argument('--json', action='store_true', help='print a JSON report')
    args = parser.parse_args(argv)
    try:
        report = diagnose(args.alias)
    except ValueError as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for item in report['checks']:
            print(f"{item['status'].upper():7} {item['title']}: {item['detail']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
