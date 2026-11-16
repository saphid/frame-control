"""Private opt-in adapter; no default install, sampler thread or extra request.

The reviewed caller owns source verification, guest scope, transport and files.
Listener samples describe a network namespace, never a process or bind instant.
"""
from contextlib import contextmanager
import json
import time
import threading

import loopback_observation as model
from retain_report import retaining_capture

TOKEN_URL = 'http://127.0.0.1:1337/auth/token'
LOADER_ARGS = ['/home/tester/.local/share/frame-control/decky/PluginLoader']
DISCOVERY = 'published Decky plugin discovery'
SAMPLE_INTERVAL_NS = 500_000_000


class TimedRecorder(model.Recorder):
    def sample(self, reader, clock):
        if not self.enabled or self.truncated:
            return
        started = clock()
        try:
            value = model.listener_snapshot(reader(model.READ_CAP + 1))
        except OSError:
            value = {'listener': 'unavailable', 'reason': 'os-error'}
        finished = clock()
        stamp = clock()
        if not all(type(n) is int for n in (started, finished, stamp)) or not 0 < started <= finished <= stamp:
            raise ValueError('snapshot-clock')
        self._append(dict(kind='listener', atMonotonicNs=stamp,
                          readStartedMonotonicNs=started, readFinishedMonotonicNs=finished, **value))


class Observation:
    def __init__(self, *, enabled, reader, clock=time.monotonic_ns):
        self.recorder = TimedRecorder(enabled=enabled)
        self.reader, self.clock = reader, clock
        self.owner = threading.get_ident()
        self.active = False
        self.last_sample_ns = None
        self.hook_faults = 0

    def _owner(self):
        if threading.get_ident() != self.owner:
            raise ValueError('serialization-owner')

    def phase(self, name, error=None):
        if not self.recorder.enabled:
            return
        try:
            self._owner()
            self.recorder.phase(name, self.clock(),
                                error='none' if error is None else model.error_category(error))
        except BaseException:
            self.hook_faults += 1

    def sample_due(self):
        if not self.recorder.enabled or self.recorder.truncated:
            return
        try:
            self._owner()
            now = self.clock()
            if self.last_sample_ns is not None and now - self.last_sample_ns < SAMPLE_INTERVAL_NS:
                return
            self.last_sample_ns = now
            self.recorder.sample(self.reader, self.clock)
            self.last_sample_ns = self.clock()
        except BaseException:
            self.hook_faults += 1

    def token(self, original, url, *args, **kwargs):
        if not self.active or type(url) is not str or url != TOKEN_URL:
            return original(url, *args, **kwargs)
        self.sample_due()
        self.phase('token-http-entered')
        try:
            value = original(url, *args, **kwargs)
        except BaseException as error:
            self.phase('token-http-error', error)
            self.sample_due()
            raise
        self.phase('token-http-returned')
        self.sample_due()
        return value

    def discovery(self, original, read, description, **kwargs):
        if not self.recorder.enabled or description != DISCOVERY:
            return original(read, description, **kwargs)
        previous = self.active
        self.active = True
        self.phase('discovery-entered')
        try:
            value = original(read, description, **kwargs)
        except BaseException as error:
            self.phase('discovery-error', error)
            raise
        else:
            self.phase('discovery-returned')
            return value
        finally:
            self.active = previous

    def spawn(self, original, *args, **kwargs):
        observed = self.recorder.enabled and args and args[0] == LOADER_ARGS
        if observed:
            self.phase('loader-spawn-entered')
        value = original(*args, **kwargs)
        if observed:
            self.phase('loader-spawn-returned')
        return value

    def result(self):
        value = self.recorder.result()
        value.update(adapterSchemaVersion=1, hookFaults=self.hook_faults,
                     passiveSchedule='existing-token-boundaries-min-500ms-after-previous-read-completion',
                     readWindowsAreMeasuredSeparately=True,
                     recordTimestampIsAfterReadCompletion=True,
                     noExtraNetworkRequests=True, noSamplerThreadOrProcess=True,
                     websocketStageHooksInstalled=False,
                     tokenHttpReturnedBoundary='urlopen-response-headers-returned',
                     tokenResponseBodyCompletionObserved=False,
                     tokenHttpReturnEstablishesAuthenticationOrDiscoveryReadiness=False,
                     phaseEntryReturnAreObservedCallBoundariesNotDeadlineProof=True,
                     originalValuesExceptionsAndStageTimeoutsForwarded=True)
        value['complete'] = value['enabled'] and bool(value['records']) and not value['truncated'] and self.hook_faults == 0
        value['completeMeansNoKnownRecorderLossOnly'] = True
        value['continuousListenerCoverageEstablished'] = False
        value['partialOperationsPossibleWhenOriginalCallRaises'] = True
        value['finalizationRecordsRemoved'] = 0
        # Additional adapter metadata is inside the same fixed output cap.
        while len(json.dumps(value, separators=(',', ':'), allow_nan=False).encode('ascii')) > model.OUTPUT_CAP:
            if not value['records']:
                raise ValueError('fixed-metadata-byte-cap')
            value['records'].pop()
            value['truncated'] = True
            value['complete'] = False
            value['finalizationRecordsRemoved'] += 1
        return value


class Proxy:
    def __init__(self, original, **overrides):
        self.original, self.overrides = original, overrides

    def __getattr__(self, name):
        return self.overrides[name] if name in self.overrides else getattr(self.original, name)


@contextmanager
def installed(fixture, observation, *, report_path, receipt):
    """Only replace globals in this private loaded fixture; restore all finally.

    The original subprocess/urllib/runtime_console modules remain unchanged.
    A disabled adapter never reads procfs or creates a sidecar.
    """
    if not observation.recorder.enabled:
        yield
        return
    names = ('until_ready', 'subprocess', 'urllib', 'capture_runtime')
    saved = {name: getattr(fixture, name) for name in names}
    try:
        fixture.until_ready = lambda read, description, **kw: observation.discovery(saved['until_ready'], read, description, **kw)
        fixture.subprocess = Proxy(saved['subprocess'], Popen=lambda *a, **kw: observation.spawn(saved['subprocess'].Popen, *a, **kw))
        requests = Proxy(saved['urllib'].request, urlopen=lambda *a, **kw: observation.token(saved['urllib'].request.urlopen, *a, **kw))
        fixture.urllib = Proxy(saved['urllib'], request=requests)
        fixture.capture_runtime = retaining_capture(saved['capture_runtime'], path=report_path, receipt=receipt)
        yield
    finally:
        for name, original in saved.items():
            setattr(fixture, name, original)
