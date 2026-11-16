"""Private diagnostic hook: retain an existing report without changing native outcome.

No default installation, process control, network access or source mutation.
A reviewed caller must choose a fresh task-owned sidecar in its owned guest.
"""
from contextlib import contextmanager
import functools
import hashlib
import json
import os

REPORT_CAP = 32768


def bounded_json(value):
    encoded = bytearray()
    for part in json.JSONEncoder(ensure_ascii=True, allow_nan=False).iterencode(value):
        chunk = part.encode('ascii')
        if len(encoded) + len(chunk) > REPORT_CAP:
            return None
        encoded.extend(chunk)
    return bytes(encoded)


def retain(path, report):
    """Create once; refusal/error leaves native behavior to the original caller."""
    receipt = dict(state='unavailable', reportBytesComplete=False,
                   reportCapBytes=REPORT_CAP, qualificationPassed=False)
    try:
        if (not isinstance(report, dict) or report.get('id') != 65
                or not isinstance(report.get('runtimeConsole'), dict)):
            receipt['reason'] = 'runtime-report-unavailable'
            return receipt
        payload = bounded_json(report)
        if payload is None:
            receipt['reason'] = 'report-byte-cap'
            return receipt
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            pending = memoryview(payload)
            while pending:
                written = os.write(fd, pending)
                if type(written) is not int or not 0 < written <= len(pending):
                    raise OSError('invalid diagnostic write progress')
                pending = pending[written:]
        finally:
            os.close(fd)
        receipt.update(state='available', reportBytesComplete=True, bytes=len(payload),
                       sha256=hashlib.sha256(payload).hexdigest())
    except BaseException as error:
        # A partial task-owned sidecar remains evidence, never a complete report.
        receipt.update(reason='report-retention-error', errorType=type(error).__name__)
    return receipt


def retaining_capture(original, *, path, receipt):
    """Wrap the existing context manager; never suppress or replace its errors."""
    @functools.wraps(original)
    @contextmanager
    def observed(log, report, processes, **kwargs):
        try:
            with original(log, report, processes, **kwargs):
                yield
        finally:
            receipt.update(retain(path, report))
    return observed
