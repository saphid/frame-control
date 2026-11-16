"""Private pure diagnostic model; never installs hooks or reads live procfs.

The caller must obtain a bounded passive snapshot in its owned networkless
guest. No listener record establishes process ownership or an exact bind time.
"""
import errno
import json
import re
import urllib.error

READ_CAP = 16384
OUTPUT_CAP = 32768
MAX_RECORDS = 256
PHASES = frozenset({
    'loader-spawn-entered', 'loader-spawn-returned',
    'discovery-entered', 'discovery-returned', 'discovery-error',
    'token-http-entered', 'token-http-returned', 'token-http-error',
    'websocket-entered', 'websocket-returned', 'websocket-error',
})
ERRORS = frozenset({'none', 'refused', 'timed-out', 'other-os', 'other'})
LISTENERS = frozenset({'absent', 'loopback', 'wildcard', 'loopback+wildcard', 'unavailable'})
REASONS = frozenset({'none', 'read-cap', 'invalid-format', 'os-error'})


def listener_snapshot(raw):
    """Only classify the known IPv4 localhost:1337 listening boundary.

    Parse /proc/net/tcp without exporting row text, unrelated endpoints, UIDs,
    socket inodes or their hashes. Truncation is unavailable, never absent.
    The deployment reader must read READ_CAP+1 bytes and pass those bytes here.
    """
    missing = {'listener': 'unavailable', 'reason': 'invalid-format'}
    if type(raw) is not bytes:
        return missing
    if len(raw) > READ_CAP:
        return {'listener': 'unavailable', 'reason': 'read-cap'}
    try:
        rows = raw.decode('ascii').splitlines()
    except UnicodeError:
        return missing
    if not rows or rows[0].split()[:4] != ['sl', 'local_address', 'rem_address', 'st']:
        return missing
    found = set()
    for row in rows[1:]:
        if not row.strip():
            continue
        fields = row.split()
        patterns = (r'[0-9]+:', r'[0-9A-F]{8}:[0-9A-F]{4}',
                    r'[0-9A-F]{8}:[0-9A-F]{4}', r'[0-9A-F]{2}',
                    r'[0-9A-F]{8}:[0-9A-F]{8}', r'[0-9A-F]{2}:[0-9A-F]{8}',
                    r'[0-9A-F]{8}', r'[0-9]+', r'[0-9]+', r'[0-9]+')
        if len(fields) < len(patterns) or any(not re.fullmatch(pattern, field)
                                            for pattern, field in zip(patterns, fields)):
            return missing
        # Exact kernel-rendered constants; never search a user-controlled suffix.
        if fields[3] != '0A':
            continue
        if fields[1] == '0100007F:0539':
            found.add('loopback')
        elif fields[1] == '00000000:0539':
            found.add('wildcard')
    return {'listener': '+'.join(sorted(found)) if found else 'absent', 'reason': 'none'}


def error_category(error):
    """Never retain str/repr, URL, token, response, traceback or arbitrary type."""
    if isinstance(error, urllib.error.URLError) and isinstance(error.reason, BaseException):
        error = error.reason
    if isinstance(error, TimeoutError):
        return 'timed-out'
    if isinstance(error, OSError):
        if error.errno == errno.ECONNREFUSED:
            return 'refused'
        if error.errno == errno.ETIMEDOUT:
            return 'timed-out'
        return 'other-os'
    return 'other'


class Recorder:
    """One fixed-cap passive observation; no thread, timer, socket or process.

    A single owner must serialize records. An owner must schedule snapshots
    under the original fixture's 120s ceiling,
    ideally at 500ms intervals. Scheduling and live hooks are NOT implemented
    or approved by this model. At most 256 combined phase/snapshot records and
    32KiB of serialized output are retained. Exhaustion retains an explicit flag.
    """
    def __init__(self, *, enabled=False):
        if type(enabled) is not bool:
            raise ValueError('enable-schema')
        self.enabled = enabled
        self.records = []
        self.truncated = False
        self.last_ns = None

    def result(self):
        return dict(schemaVersion=1, enabled=self.enabled, records=list(self.records),
                    truncated=self.truncated, outputCapBytes=OUTPUT_CAP,
                    readCapBytes=READ_CAP, maxRecords=MAX_RECORDS,
                    passiveNetworkNamespaceObservationOnly=True,
                    timingPerturbationPossible=True,
                    listenerProcessOwnershipEstablished=False,
                    exactBindTimeEstablished=False, diagnosisOrRepairEstablished=False,
                    runtimeOrReleaseQualified=False)

    def _append(self, row):
        stamp = row['atMonotonicNs']
        if type(stamp) is not int or not 0 < stamp < 2**63:
            raise ValueError('clock-schema')
        if self.last_ns is not None and stamp < self.last_ns:
            raise ValueError('clock-order')
        if not self.enabled:
            return
        self.last_ns = stamp
        if len(self.records) >= MAX_RECORDS:
            self.truncated = True
            return
        self.records.append(row)
        if len(json.dumps(self.result(), separators=(',', ':')).encode('ascii')) > OUTPUT_CAP:
            self.records.pop()
            self.truncated = True

    def phase(self, name, stamp, *, error='none'):
        if name not in PHASES or error not in ERRORS:
            raise ValueError('phase-schema')
        self._append(dict(kind='phase', phase=name, atMonotonicNs=stamp, error=error))

    def snapshot(self, stamp, reader):
        if not self.enabled or self.truncated:
            return
        try:
            value = listener_snapshot(reader(READ_CAP + 1))
        except OSError:
            value = {'listener': 'unavailable', 'reason': 'os-error'}
        if value['listener'] not in LISTENERS or value['reason'] not in REASONS:
            raise ValueError('snapshot-schema')
        self._append(dict(kind='listener', atMonotonicNs=stamp, **value))
