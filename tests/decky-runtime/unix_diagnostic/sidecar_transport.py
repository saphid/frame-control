"""Bounded root reader for fresh, owned diagnostic sidecars; no target execution."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat

CAP = 32768
HOME = Path('/home/tester')
FILES = {'receipt': 'private-observation-receipt.json',
         'observation': 'private-loopback-observation.json',
         'nativeReport': 'private-native-report.json'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate-json-key')
        result[key] = value
    return result


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('nonfinite-json')
    return result


def read_json(path, *, uid=1100):
    """Never follow links, block on a FIFO, or read more than CAP+1 bytes."""
    result = dict(state='unavailable', bytesComplete=False)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != uid
                    or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                    or not 0 < before.st_size <= CAP):
                raise ValueError('file-contract')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                data = stream.read(CAP + 1)
            after = os.fstat(fd)
            fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            if any(getattr(before, k) != getattr(after, k) for k in fields) or len(data) != before.st_size:
                raise ValueError('file-changed')
        finally:
            os.close(fd)
        value = json.loads(data, object_pairs_hook=unique_object, parse_float=finite_float,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite-json')))
        if type(value) is not dict:
            raise ValueError('json-object-required')
        result.update(state='available', bytesComplete=True, bytes=len(data),
                      sha256=hashlib.sha256(data).hexdigest())
        return value, result
    except BaseException:
        # No arbitrary path, error text or file bytes leave the failed reader.
        result['reason'] = 'missing-or-invalid-sidecar'
        return None, result


def receipt_matches(declared, actual, *, native=False):
    if type(declared) is not dict or not actual['bytesComplete']:
        return False
    if native:
        return (declared.get('reportBytesComplete') is True
                and declared.get('state') == 'available'
                and declared.get('bytes') == actual['bytes']
                and declared.get('sha256') == actual['sha256'])
    return (declared.get('bytesComplete') is True and declared.get('state') == 'available'
            and declared.get('bytes') == actual['bytes'] and declared.get('sha256') == actual['sha256'])


def collect(*, home=HOME, uid=1100):
    """Separate diagnostic integrity from native outcome, including failed probes."""
    result = dict(schemaVersion=1, qualificationPassed=False, nativePassInferred=False,
                  sidecars={}, receiptValid=False)
    values = {}
    for key, filename in FILES.items():
        value, status = read_json(home / filename, uid=uid)
        values[key] = value
        result['sidecars'][key] = status
    receipt = values['receipt']
    if (type(receipt) is not dict or receipt.get('schemaVersion') != 1
            or receipt.get('qualificationPassed') is not False
            or receipt.get('executionMode') != 'unchanged-source-import-then-explicit-original-main'
            or receipt.get('fixtureSourceSha256') != 'd28ce497d5bd3dcaeaff78f93212e3a10baa3f415788da7481fe3456cbdd9b00'):
        return result
    result['receiptValid'] = True
    for key, declared in [('observation', receipt.get('loopbackObservation')),
                          ('nativeReport', receipt.get('originalNativeReport'))]:
        matches = receipt_matches(declared, result['sidecars'][key], native=key == 'nativeReport')
        result['sidecars'][key]['matchesDriverReceipt'] = matches
        if matches:
            result[key] = values[key]
    return result
