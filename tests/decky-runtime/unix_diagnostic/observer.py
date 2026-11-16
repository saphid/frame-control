"""PRIVATE proposed function-scoped observer; actual registration unverified.

The kernel routes both AF_UNIX SOCK_STREAM and SOCK_SEQPACKET through
unix_stream_connect. These records describe driver invocations, not all connect
syscalls. IP, datagram and pre-driver failures are outside the capture scope.
Name records describe unix_mkname_bsd normalization, never a lookup outcome.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

from base_observer import CaptureError, bounded, owned_scope

TRACEFS = Path('/sys/kernel/tracing')
READ_CAP = 32768
BUFFER_KIB = 16
STREAM_ENTER = 'stream_enter'
STREAM_RETURN = 'stream_return'
NAME_NORMALIZED = 'name_normalized'
EVENT_NAMES = (STREAM_ENTER, STREAM_RETURN, NAME_NORMALIZED)
DRIVER_SYMBOL = 'unix_stream_connect'
NAME_SYMBOL = 'unix_mkname_bsd'
SCOPE = 'unix_stream_connect driver invocations (Unix stream and seqpacket), plus observed name normalization'


def _identity_text(directory_fd, name, limit):
    """Read one bounded file relative to the pinned procfs task directory."""
    fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC, dir_fd=directory_fd)
    with os.fdopen(fd, 'rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise CaptureError('metadata-read-cap')
    return data.decode('ascii')


def identity(tid):
    """Capture-end task records; pin the directory against task-ID reuse.

    The descriptor cannot redirect to a replacement task between file reads.
    This does not establish that a capture-end task also owned an earlier event.
    """
    try:
        if type(tid) is not int or tid <= 0:
            raise CaptureError('task-identity-schema')
        directory_fd = os.open(Path('/proc') / str(tid), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            stat = _identity_text(directory_fd, 'stat', 4096)
            status = _identity_text(directory_fd, 'status', 8192)
        finally:
            os.close(directory_fd)
        fields = stat[stat.rindex(')') + 2:].split()
        matches = {name: re.search(r'^' + name + r':\s+(\d+)', status, re.M)
                   for name in ('Pid', 'Tgid', 'Uid')}
        if not all(matches.values()) or int(matches['Pid'][1]) != tid or int(stat.split(' ', 1)[0]) != tid:
            raise CaptureError('task-identity-schema')
        return dict(tid=tid, tgid=int(matches['Tgid'][1]), ppid=int(fields[1]),
                    pgid=int(fields[2]), sid=int(fields[3]), startTicks=int(fields[19]),
                    uid=int(matches['Uid'][1]), available=True)
    except (OSError, ValueError, IndexError, CaptureError, UnicodeError) as error:
        return dict(tid=tid, available=False, reason='identity-unavailable', errorType=type(error).__name__)


def _layout_rejection_structure(line, line_number):
    """Bounded shape observations only; never establish a rejected-line cause.

    Candidate anchors can occur inside untrusted text. Zero/multiple anchors
    remain unclassified, and even a unique anchor is not an accepted header.
    No substrings, identifiers, timestamps, addresses or text hashes escape.
    """
    if type(line) is not str or not line.isascii() or not 0 < len(line) <= READ_CAP:
        raise ValueError('layout-summary-input')
    if type(line_number) is not int or not 1 <= line_number <= READ_CAP + 1:
        raise ValueError('layout-summary-input')
    summary = dict(schemaVersion=1, rejectedLineNumber=line_number,
                   lineBytes=len(line), anchorCountCappedAtTwo=0,
                   anchorShape='none', strippedPrefixWidthBucket='unknown',
                   strippedPrefixContainsWhitespace='unknown', flagsWidth=0,
                   cpuDigitCount=0, fractionDigitCount=0, eventLabel='unknown',
                   structuralOnly=True, rejectionCauseEstablished=False)
    # These bounds describe the diagnostic's recognized candidate shape only.
    # They do not replace or broaden the actual parser's acceptance predicate.
    anchors = []
    pattern = (r'-[0-9]{1,10}\s{1,16}\[(?P<cpu>[0-9]{1,8})\]\s{1,16}'
               r'(?P<flags>[A-Za-z0-9.?+]{1,16})\s{1,16}'
               r'[0-9]{1,16}\.(?P<fraction>[0-9]{1,9}):\s{1,16}')
    for candidate in re.finditer(pattern, line):
        anchors.append(candidate)
        if len(anchors) == 2:
            break
    summary['anchorCountCappedAtTwo'] = len(anchors)
    if len(anchors) == 2:
        summary['anchorShape'] = 'ambiguous'
    elif len(anchors) == 1:
        candidate = anchors[0]
        prefix = line[:candidate.start()].strip()
        width = len(prefix)
        label = line[candidate.end():].split(':', 1)[0]
        summary.update(anchorShape='unique-candidate',
                       strippedPrefixWidthBucket=('empty' if width == 0 else '1-16' if width <= 16 else '17-64' if width <= 64 else 'over64'),
                       strippedPrefixContainsWhitespace=('yes' if any(c.isspace() for c in prefix) else 'no'),
                       flagsWidth=len(candidate['flags']), cpuDigitCount=len(candidate['cpu']),
                       fractionDigitCount=len(candidate['fraction']),
                       eventLabel=label if label in EVENT_NAMES else 'unknown')
    assert len(json.dumps(summary, separators=(',', ':')).encode('ascii')) < 768
    return summary


def parse_capture(raw, *, origin_ns, finished_ns, cpu_stats, probe_profiles, truncated=False):
    result = dict(state='incomplete', captureComplete=False, scope=SCOPE,
                  qualificationPassed=False, allConnectSyscallCoverage=False,
                  driverEventTimelineComplete=False, rawPayloadRetained=False,
                  argumentPointersRetained=False, destinationTextRetained=False,
                  driverCalls=[], unassociatedNormalizations=[], reasons=[])
    try:
        if truncated or len(raw) > READ_CAP:
            raise CaptureError('trace-read-cap')
        if not cpu_stats:
            raise CaptureError('missing-cpu-stats')
        required = {'entries', 'overrun', 'commit overrun', 'dropped events'}
        for stats in cpu_stats:
            if not required.issubset(stats) or any(type(stats[k]) is not int or stats[k] < 0 for k in required):
                raise CaptureError('invalid-cpu-stats')
            if any(stats[k] for k in ('overrun', 'commit overrun', 'dropped events')):
                raise CaptureError('kernel-trace-loss')
        if not isinstance(probe_profiles, dict) or set(probe_profiles) != set(EVENT_NAMES):
            raise CaptureError('probe-profile-schema')
        for profile in probe_profiles.values():
            if not isinstance(profile, dict) or set(profile) != {'hits', 'misses'}:
                raise CaptureError('probe-profile-schema')
            if any(type(value) is not int or value < 0 for value in profile.values()):
                raise CaptureError('probe-profile-schema')
            if profile['misses']:
                raise CaptureError('kernel-probe-miss')
        pending, pairs, unassociated, last_stamp = {}, [], [], {}
        counts = {name: 0 for name in EVENT_NAMES}
        for line_number, line in enumerate(raw.decode('ascii').splitlines(), 1):
            if not line or line.startswith('#'):
                continue
            match = re.fullmatch(r'\s*\S+-(\d+)\s+\[\d+\]\s+\S+\s+(\d+\.\d+):\s+(.*)', line)
            if match is None and line.startswith(' ') and line[:16].strip():
                # Upstream trace_print_context uses %16s-%-7d. The fixed
                # task-field boundary supports spaces without searching an
                # arbitrary prefix or exporting its text. Legacy matches stay.
                match = re.fullmatch(r'[ -~]{16}-(\d+)\s+\[\d+\]\s+\S+\s+(\d+\.\d+):\s+(.*)', line)
            if not match:
                try:
                    result['layoutRejectionStructure'] = _layout_rejection_structure(line, line_number)
                except Exception:
                    # Diagnostic failure must never mask or broaden rejection.
                    result['layoutRejectionStructure'] = dict(schemaVersion=1, anchorShape='diagnostic-unavailable',
                                                              structuralOnly=True, rejectionCauseEstablished=False)
                raise CaptureError('trace-layout')
            tid, stamp, body = int(match[1]), float(match[2]), match[3]
            if tid <= 0 or not origin_ns / 1e9 <= stamp <= finished_ns / 1e9:
                raise CaptureError('trace-clock-or-tid')
            if stamp < last_stamp.get(tid, stamp):
                raise CaptureError('per-task-clock-order')
            last_stamp[tid] = stamp
            if body.startswith(STREAM_ENTER + ':'):
                event = re.fullmatch(r'stream_enter:\s+.*?family=(\d+) addrlen=(-?\d+)', body)
                if not event or tid in pending:
                    raise CaptureError('driver-entry-schema-or-pairing')
                family, length = int(event[1]), int(event[2])
                if not 0 <= family <= 65535 or not -(2 ** 31) <= length < 2 ** 31:
                    raise CaptureError('driver-entry-width')
                counts[STREAM_ENTER] += 1
                pending[tid] = dict(tid=tid, enteredSeconds=stamp, inputFamily=family,
                                    inputAddressBytes=length, normalizations=[],
                                    endpointClassification='unclassified')
            elif body.startswith(NAME_NORMALIZED + ':'):
                event = re.fullmatch(r'name_normalized:\s+.*?dest="(.*)" family=(\d+) addrlen=(-?\d+)', body)
                if not event:
                    raise CaptureError('normalization-schema')
                text, family, length = event[1], int(event[2]), int(event[3])
                address = text.encode('ascii')
                if family != 1 or not 3 <= length <= 110:
                    raise CaptureError('normalization-family-or-length')
                if not address.startswith(b'/') or not 1 <= len(address) <= 108 or len(address) > length - 2:
                    raise CaptureError('unsupported-filesystem-name')
                if any(value < 32 or value > 126 for value in address) or any(c in text for c in ('\\', '"')):
                    raise CaptureError('unsupported-destination-encoding')
                normalized = dict(tid=tid, timestampSeconds=stamp,
                                  pathSha256=hashlib.sha256(address).hexdigest(),
                                  pathBytes=len(address), sockaddrBytes=length)
                counts[NAME_NORMALIZED] += 1
                if tid in pending:
                    pending[tid]['normalizations'].append(normalized)
                    pending[tid]['endpointClassification'] = 'filesystem-name-normalized'
                else:
                    unassociated.append(normalized)
            elif body.startswith(STREAM_RETURN + ':'):
                event = re.fullmatch(r'stream_return:\s+.*?result=(-?\d+)', body)
                if not event or tid not in pending:
                    raise CaptureError('driver-return-schema-or-pairing')
                value = int(event[1])
                # The actual C function returns int, not the syscall's long.
                if not -(2 ** 31) <= value < 2 ** 31:
                    raise CaptureError('driver-return-width')
                counts[STREAM_RETURN] += 1
                call = pending.pop(tid)
                call.update(exitedSeconds=stamp, driverResult=value)
                pairs.append(call)
            else:
                raise CaptureError('out-of-scope-event')
        if pending:
            raise CaptureError('unfinished-driver-call')
        if sum(counts.values()) != sum(stats['entries'] for stats in cpu_stats):
            raise CaptureError('trace-entry-count-mismatch')
        for name, count in counts.items():
            if probe_profiles[name]['hits'] < count:
                raise CaptureError('probe-hit-count-mismatch')
        result.update(state='available', captureComplete=True, driverEventTimelineComplete=True,
                      driverCalls=pairs, unassociatedNormalizations=unassociated,
                      events=sum(counts.values()), eventCounts=counts,
                      observedDriverCalls=len(pairs), unclassifiedDriverCalls=sum(not x['normalizations'] for x in pairs),
                      globalProbeHits={name: profile['hits'] for name, profile in probe_profiles.items()},
                      probeMisses=0)
    except (CaptureError, UnicodeError) as error:
        reason = str(error) if isinstance(error, CaptureError) else 'unsupported-trace-encoding'
        result['reasons'] = [reason]
    return result


class Observer:
    def __init__(self, *, enabled=False):
        self.enabled = enabled
        self.instance = None
        self.group = None
        self.paths = []
        self.started = self.finished = False
        self.registration_attempted = []
        self.report = dict(state='disabled', enabled=False, captureComplete=False, qualificationPassed=False)

    def _command(self, text):
        raw = (text + '\n').encode('ascii')
        if not 0 < len(raw) < 512:
            raise CaptureError('probe-command-bound')
        fd = os.open(TRACEFS / 'kprobe_events', os.O_WRONLY | os.O_CLOEXEC)
        try:
            if os.write(fd, raw) != len(raw):
                raise CaptureError('probe-command-short-write')
        finally:
            os.close(fd)

    def _profiles(self):
        text = bounded(TRACEFS / 'kprobe_profile', 4096)
        profiles = {}
        for name in EVENT_NAMES:
            rows = [line for line in text.splitlines() if line.split() and line.split()[0] == name]
            if len(rows) != 1:
                raise CaptureError('owned-probe-profile-ambiguous')
            match = re.fullmatch(r'\s*' + name + r'\s+(\d+)\s+(\d+)\s*', rows[0])
            if not match:
                raise CaptureError('owned-probe-profile-schema')
            profiles[name] = dict(hits=int(match[1]), misses=int(match[2]))
        return profiles

    def _cleanup(self):
        errors = []
        if self.instance is not None:
            try:
                (self.instance / 'tracing_on').write_text('0')
                for path in self.paths:
                    if path.exists():
                        path.write_text('0')
                (self.instance / 'set_event_pid').write_text('')
                self.instance.rmdir()
                self.report['ownedTraceInstanceRemoved'] = True
            except (OSError, CaptureError):
                errors.append('trace-instance-cleanup')
        if self.group is not None:
            removed = True
            for name in reversed(self.registration_attempted):
                try:
                    if (TRACEFS / 'events' / self.group / name).exists():
                        self._command('-:' + self.group + '/' + name)
                        if (TRACEFS / 'events' / self.group / name).exists():
                            raise CaptureError('probe-removal-not-confirmed')
                except (OSError, CaptureError):
                    errors.append('probe-cleanup')
                    removed = False
            self.report['ownedProbesRemoved'] = removed
        if errors:
            self.report.update(state='incomplete', captureComplete=False,
                               participantIdentityCoverageComplete=False, cleanupErrors=errors)
        return not errors

    def start(self):
        if self.started:
            return self.report.copy()
        self.started = True
        if not self.enabled:
            return self.report.copy()
        reason = owned_scope()
        if reason:
            self.report = dict(state='unavailable', enabled=True, reason=reason,
                               captureComplete=False, qualificationPassed=False)
            return self.report.copy()
        self.report = dict(state='unavailable', enabled=True, captureComplete=False, qualificationPassed=False,
                           scope=SCOPE, allConnectSyscallCoverage=False, kernel=os.uname().release,
                           architecture=os.uname().machine, filterOwnerTaskIdentity=identity(os.getpid()),
                           ordinaryQualificationInstrumentation=False, observerTimingPerturbationPossible=True)
        stage = 'observer-source-unavailable'
        try:
            self.report['privateObserverSourceSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            self.report['privateScopeHelperSourceSha256'] = hashlib.sha256(Path(__file__).with_name('base_observer.py').read_bytes()).hexdigest()
            stage = 'tracefs-unavailable'
            if not (TRACEFS / 'kprobe_events').exists():
                raise CaptureError(stage)
            if not self.report['filterOwnerTaskIdentity']['available']:
                raise CaptureError('owner-identity-unavailable')
            token = str(os.getpid()) + '_' + uuid.uuid4().hex[:12]
            self.group = 'framey_stream_' + token
            candidate = TRACEFS / 'instances' / ('framey-stream-' + token)
            if candidate.exists() or (TRACEFS / 'events' / self.group).exists():
                raise CaptureError('owned-name-collision')
            candidate.mkdir()
            self.instance = candidate
            (candidate / 'tracing_on').write_text('0')
            clocks = bounded(candidate / 'trace_clock')
            if 'mono' not in clocks.replace('[', '').replace(']', '').split():
                raise CaptureError('mono-clock-unavailable')
            (candidate / 'trace_clock').write_text('mono')
            (candidate / 'buffer_size_kb').write_text(str(BUFFER_KIB))
            (candidate / 'options/event-fork').write_text('1')
            definitions = [
                ('p', STREAM_ENTER, DRIVER_SYMBOL + ' family=+0($arg2):u16 addrlen=$arg3:s32'),
                ('r32', STREAM_RETURN, DRIVER_SYMBOL + ' result=$retval:s32'),
                ('r32', NAME_NORMALIZED, NAME_SYMBOL + ' dest=+2($arg1):string family=+0($arg1):u16 addrlen=$arg2:s32'),
            ]
            stage = 'probe-registration-unavailable'
            self.report['probeDefinitions'] = []
            for kind, name, body in definitions:
                definition = kind + ':' + self.group + '/' + name + ' ' + body
                self.registration_attempted.append(name)
                self._command(definition)
                self.report['probeDefinitions'].append(definition)
            stage = 'trace-instance-configuration-unavailable'
            self.paths = [candidate / 'events' / self.group / name / 'enable' for name in EVENT_NAMES]
            self.report.update(probeFormats={name: bounded(path.parent / 'format', 8192)
                                            for name, path in zip(EVENT_NAMES, self.paths)},
                               traceClock=bounded(candidate / 'trace_clock'),
                               bufferConfiguredKiBPerCpu=BUFFER_KIB, readCapBytes=READ_CAP)
            (candidate / 'set_event_pid').write_text(str(os.getpid()))
            # Clearing only this newly-created, task-owned instance is allowed.
            (candidate / 'trace').write_text('')
            for path in self.paths:
                path.write_text('1')
            self.origin_ns = time.monotonic_ns()
            self.report['originMonotonicNs'] = self.origin_ns
            stage = 'trace-start-unavailable'
            (candidate / 'tracing_on').write_text('1')
            self.report.update(state='available', captureActive=True)
        except (OSError, CaptureError, UnicodeError) as error:
            self.report.update(state='unavailable', reason=str(error) if isinstance(error, CaptureError) else stage,
                               errorType=type(error).__name__, errno=getattr(error, 'errno', None), captureActive=False)
            self._cleanup()
        return self.report.copy()

    def finish(self):
        if self.finished:
            return self.report.copy()
        self.finished = True
        if not self.enabled or self.report.get('state') != 'available':
            return self.report.copy()
        try:
            (self.instance / 'tracing_on').write_text('0')
            finished = time.monotonic_ns()
            with (self.instance / 'trace').open('rb') as stream:
                raw = stream.read(READ_CAP + 1)
            stats = []
            for path in sorted((self.instance / 'per_cpu').glob('cpu*/stats')):
                record = {}
                for line in bounded(path).splitlines():
                    key, separator, value = line.partition(':')
                    if separator and value.strip().isdigit():
                        record[key.strip()] = int(value.strip())
                stats.append(record)
            profiles = self._profiles()
            parsed = parse_capture(raw, origin_ns=self.origin_ns, finished_ns=finished, cpu_stats=stats,
                                   probe_profiles=profiles, truncated=len(raw) > READ_CAP)
            self.report.update(parsed, finishedMonotonicNs=finished, captureActive=False,
                               rawBytesRead=len(raw), readTruncated=len(raw) > READ_CAP,
                               perCpuStats=stats, probeProfiles=profiles)
            tids = {call['tid'] for call in parsed['driverCalls']} | {
                row['tid'] for row in parsed['unassociatedNormalizations']}
            tasks = [identity(tid) for tid in sorted(tids)]
            owner_matches = identity(os.getpid()) == self.report['filterOwnerTaskIdentity']
            self.report.update(participantTaskIdentitiesAtCaptureEnd=tasks,
                               captureEndTaskRecordsAvailable=bool(tasks) and all(t['available'] for t in tasks),
                               participantIdentityCoverageComplete=False,
                               participantEventTaskIdentitiesEstablished=False,
                               participantIdentityCoverageReason='capture-end-observation-only',
                               filterOwnerTaskIdentityRechecked=owner_matches, taskIdentifiersAreTids=True,
                               exitedTaskStartIdentityNotInferred=True)
            if not owner_matches:
                self.report.update(state='incomplete', captureComplete=False,
                                   participantIdentityCoverageComplete=False, reasons=['owner-identity-changed'])
        except (OSError, CaptureError, UnicodeError) as error:
            self.report.update(state='incomplete', captureComplete=False, captureActive=False,
                               participantIdentityCoverageComplete=False,
                               reason='capture-read-unavailable', errorType=type(error).__name__, errno=getattr(error, 'errno', None))
        finally:
            self._cleanup()
        return self.report.copy()
