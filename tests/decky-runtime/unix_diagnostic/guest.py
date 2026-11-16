print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=bootstrap-entry',flush=True)
"""One opt-in private observation; published check and loader bytes unchanged."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import traceback

sys.path.insert(0, '/input')
from guest_result import PORT, write_result
import observer
print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=imports-ready',flush=True)

assert os.getuid() == 0 and os.getpid() != 1
assert Path('/framey-owned-vm').read_bytes() == b'Framey private trace capability v1\n'
assert Path('/proc/1/comm').read_text().strip() == 'systemd'
assert not Path('/sys/class/net/eth0').exists()
report = dict(success=False, observerEnabledDiagnostic=True, qualificationPassed=False,
              realFrameContacted=False, browserExecuted=False, networkDevice=False,
              publishedLoaderExecuted=False, historicalCauseOrRepairEstablished=False)
active = None
manager_started = False
try:
    inputs = json.loads(Path('/input/inputs.json').read_text())
    assert os.uname().machine == inputs['architecture'] == 'aarch64'
    data = Path('/input/source.tar').read_bytes()
    assert hashlib.sha256(data).hexdigest() == inputs['sourceArchiveSha256']
    assert hashlib.sha256(Path('/input/PluginLoader').read_bytes()).hexdigest() == inputs['loaderSha256']
    assert hashlib.sha256(Path(observer.__file__).read_bytes()).hexdigest() == inputs['observerSha256']
    assert hashlib.sha256(Path('/input/base_observer.py').read_bytes()).hexdigest() == inputs['scopeHelperSha256']
    root = Path('/repo')
    root.mkdir(exist_ok=True)
    assert root.is_dir() and not root.is_symlink() and not any(root.iterdir())
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        members = [item for item in archive if item.isfile()]
        assert {member.name for member in members} == set(inputs['sourceSha256'])
        for member in members:
            assert not member.name.startswith('/') and '..' not in Path(member.name).parts
            assert 0 <= member.size <= 32 * 1024 * 1024
            content = archive.extractfile(member).read()
            assert hashlib.sha256(content).hexdigest() == inputs['sourceSha256'][member.name]
            path = root / member.name
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(content)
            path.chmod(member.mode & 0o755)
    report['sourceBindingsVerified'] = len(inputs['sourceSha256'])
    report['sourceRevision'] = inputs['sourceRevision']
    print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=source-verified',flush=True)
    subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=768m,uid=1100,gid=1100,mode=700',
                    'tmpfs', '/home/tester'], check=True, timeout=15)
    subprocess.run(['systemctl', 'start', 'user@1100.service'], check=True, timeout=40)
    manager_started = True
    print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=user-manager-started',flush=True)
    tracefs = Path('/sys/kernel/tracing')
    if not (tracefs / 'trace_clock').exists():
        subprocess.run(['mount', '-t', 'tracefs', '-o', 'nodev,nosuid,noexec', 'tracefs', str(tracefs)],
                       check=True, timeout=3, capture_output=True)
    active = observer.Observer(enabled=True)
    report['observerStart'] = active.start()
    assert report['observerStart']['state'] == 'available', report['observerStart'].get('reason')
    print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=observer-started',flush=True)
    command = ['runuser', '-u', 'tester', '--', 'env', 'HOME=/home/tester',
               'PYTHONDONTWRITEBYTECODE=1', 'PYTHONUNBUFFERED=1', 'XDG_RUNTIME_DIR=/run/user/1100',
               'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus', 'python3',
               '/repo/tests/decky-runtime/check.py', '65', '-', '--terminal-candidate']
    report['publishedLoaderExecuted'] = True
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    report['probeExitStatus'] = result.returncode
    print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=probe-returned',flush=True)
    # Stop tracing before manager cleanup; result keeps failed probes failed.
    report['observerCapture'] = active.finish()
    print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=capture-finished',flush=True)
    report['stdoutTail'] = result.stdout[-100000:]
    report['stderrTail'] = result.stderr[-32000:]
    assert result.returncode == 0, 'Private native Terminal probe failed'
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    terminal = json.loads(lines[0])
    report['terminal'] = terminal
    assert terminal['candidate']['loaderPythonAbi']['architecture'] == 'aarch64'
    report['runtimeFixturePassed'] = True
    # Capture availability/completeness is a separate observation, never a
    # replacement for original runtime/CI qualification.
    report['success'] = True
except BaseException as error:
    report.update(errorType=type(error).__name__, error=str(error)[:2000],
                  errorTraceback=traceback.format_exc(limit=4))
finally:
    if active is not None and active.report.get('captureActive'):
        report['observerCapture'] = active.finish()
    if manager_started:
        stop = subprocess.run(['systemctl', 'stop', 'user@1100.service'],
                              capture_output=True, text=True, timeout=40)
        report['ownedUserManagerStopped'] = stop.returncode == 0
        print('FRAMEY_PRIVATE_ARM_NATIVE_PHASE=user-manager-stop-returned',flush=True)
        if stop.returncode:
            report['success'] = False
    ports = [p for p in Path('/sys/class/virtio-ports').glob('vport*p*/name') if p.read_text().strip() == PORT]
    assert len(ports) == 1
    with Path('/dev', ports[0].parent.name).open('wb', buffering=0) as stream:
        write_result(stream, report)
    subprocess.run(['systemd-run', '--unit=framey-private-observer-shutdown', '--on-active=2',
                    '--timer-property=AccuracySec=100ms', '/usr/bin/systemctl', 'poweroff'],
                   check=True, timeout=15)
