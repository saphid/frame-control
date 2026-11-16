#!/usr/bin/env python3
"""Private owned-guest driver around fixed-main source; never qualification."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import types

from live_boundary import Observation, installed

SOURCE_SHA = 'd28ce497d5bd3dcaeaff78f93212e3a10baa3f415788da7481fe3456cbdd9b00'
CHECK = Path('/repo/tests/decky-runtime/check.py')
HOME = Path('/home/tester')
OBSERVATION = HOME / 'private-loopback-observation.json'
NATIVE_REPORT = HOME / 'private-native-report.json'
RECEIPT = HOME / 'private-observation-receipt.json'
OUTPUT_CAP = 32768


def read_proc(limit):
    if limit != 16385:
        raise ValueError('passive-read-bound')
    with Path('/proc/net/tcp').open('rb') as stream:
        return stream.read(limit)


def load_fixture(path, expected_sha):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError('fixed-fixture-source')
    tree = ast.parse(data)
    names = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == '__name__']
    if (len(names) != 1 or not isinstance(tree.body[-1], ast.If)
            or ast.unparse(tree.body[-1].test) != "__name__ == '__main__'"
            or [ast.unparse(n) for n in tree.body[-1].body] != ['main()']):
        raise ValueError('unsupported-fixture-entry')
    # Import definitions from identical source, then call the original main
    # explicitly after installing isolated fixture globals. No AST is edited.
    fixture = types.ModuleType('private_observed_exact_main_fixture')
    fixture.__file__ = str(path)
    exec(compile(data, str(path), 'exec'), fixture.__dict__)
    return fixture


def write_sidecar(path, payload):
    result = dict(state='unavailable', bytesComplete=False)
    try:
        if type(payload) is not bytes or len(payload) > OUTPUT_CAP:
            raise ValueError('sidecar-byte-cap')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            pending = memoryview(payload)
            while pending:
                n = os.write(fd, pending)
                if type(n) is not int or not 0 < n <= len(pending):
                    raise OSError('sidecar-write-progress')
                pending = pending[n:]
        finally:
            os.close(fd)
        result.update(state='available', bytesComplete=True, bytes=len(payload),
                      sha256=hashlib.sha256(payload).hexdigest())
    except BaseException as error:
        result.update(reason='sidecar-write-error', errorType=type(error).__name__)
    return result


def finish_sidecars(observation, native_receipt):
    """Errors in diagnostics never replace the original native outcome."""
    try:
        payload = json.dumps(observation.result(), separators=(',', ':'), allow_nan=False).encode('ascii')
        observation_receipt = write_sidecar(OBSERVATION, payload)
    except BaseException as error:
        observation_receipt = dict(state='unavailable', bytesComplete=False,
                                   reason='observer-finalization-error', errorType=type(error).__name__)
    metadata = dict(schemaVersion=1, qualificationPassed=False,
                    executionMode='unchanged-source-import-then-explicit-original-main',
                    fixtureSourceSha256=SOURCE_SHA, originalNativeReport=native_receipt,
                    loopbackObservation=observation_receipt)
    try:
        payload = json.dumps(metadata, separators=(',', ':'), allow_nan=False).encode('ascii')
        write_sidecar(RECEIPT, payload)
    except BaseException:
        pass  # Missing/incomplete receipt remains unavailable to the guest reader.


def main():
    if sys.argv[1:]:
        raise ValueError('fixed-fixture-arguments')
    if (os.getuid() != 1100 or os.getpid() == 1
            or Path('/framey-owned-vm').read_bytes() != b'Framey private trace capability v1\n'
            or Path('/sys/class/net/eth0').exists()):
        raise ValueError('owned-networkless-guest-only')
    inputs = json.loads(Path('/input/inputs.json').read_text())
    if inputs['sourceSha256']['tests/decky-runtime/check.py'] != SOURCE_SHA:
        raise ValueError('fixed-main-binding')
    enabled = inputs.get('loopbackObservationEnabledDiagnostic', False)
    if type(enabled) is not bool:
        raise ValueError('diagnostic-enable-schema')
    sys.path.insert(0, str(CHECK.parent))
    fixture = load_fixture(CHECK, SOURCE_SHA)
    observation = Observation(enabled=enabled, reader=read_proc)
    native_receipt = {}
    argv = sys.argv
    sys.argv = [str(CHECK), '65', '-', '--terminal-candidate']
    try:
        with installed(fixture, observation, report_path=NATIVE_REPORT, receipt=native_receipt):
            fixture.main()
    finally:
        sys.argv = argv
        if enabled:
            finish_sidecars(observation, native_receipt)


if __name__ == '__main__':
    main()
