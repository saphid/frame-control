"""Bootstrap the private VM user manager; never run this on a host or Frame."""

import json, os, subprocess, traceback
from pathlib import Path


def command(args, timeout=40, **kwargs):
    return subprocess.run(
        args, check=True, capture_output=True, text=True, timeout=timeout, **kwargs
    ).stdout.strip()


# Guard outside the exception/shutdown path: accidental host execution must
# never reach journalctl, service operations or the guest poweroff timer.
if (
    os.getpid() == 1
    or os.getuid() != 0
    or not Path('/framey-owned-vm').is_file()
    or Path('/framey-owned-vm').read_text().strip() != 'Frame Control service VM v1'
):
    raise RuntimeError('This bootstrap runs only inside the owned service VM')

try:
    command(['systemctl', 'start', 'user@1100.service'])
    user = [
        'runuser',
        '-u',
        'tester',
        '--',
        'env',
        'XDG_RUNTIME_DIR=/run/user/1100',
        'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus',
    ]
    version = command(
        user + ['systemctl', '--user', 'show', '--property=Version', '--value']
    )
    command(
        user
        + [
            'systemd-run',
            '--user',
            '--unit=framey-owned-probe',
            '--wait',
            '--collect',
            '/usr/bin/true',
        ]
    )
    report = {
        'success': True,
        'pid1': Path('/proc/1/comm').read_text().strip(),
        'userManagerVersion': version,
        'userBusPresent': Path('/run/user/1100/bus').exists(),
        'transientUnitExecuted': True,
        'kernel': os.uname().release,
        'realFrameContacted': False,
        'hostBusExposed': False,
    }
    output = command(user + ['python3', '/framey-user.py'], timeout=240)
    print(output, flush=True)
    lines = [
        line.partition('FRAMEY_USER_SERVICE_JSON=')[2]
        for line in output.splitlines()
        if 'FRAMEY_USER_SERVICE_JSON=' in line
    ]
    assert len(lines) == 1
    report['candidateService'] = json.loads(lines[0])
    command(['systemctl', 'stop', 'user@1100.service'])
except BaseException as error:
    traceback.print_exc()
    if isinstance(error, subprocess.CalledProcessError):
        print(error.stdout[-3000:], flush=True)
        print(error.stderr[-5000:], flush=True)
    report = {'success': False, 'realFrameContacted': False}
    subprocess.run(['journalctl', '-b', '--no-pager', '-n', '100'], timeout=10)
print('FRAMEY_SYSTEMD_PROBE_JSON=' + json.dumps(report), flush=True)
subprocess.run(
    [
        'systemd-run',
        '--unit=framey-fixture-shutdown',
        '--on-active=2',
        '--timer-property=AccuracySec=100ms',
        '/usr/bin/systemctl',
        'poweroff',
    ],
    check=True,
    timeout=10,
)
