"""Private opt-in connect observer for an owned networkless systemd guest.

Not a qualification gate or an unperturbed timing source. The return probe
fetches only filesystem names after unix_mkname_bsd terminated them. Other
transports remain unclassified; no argument or kernel pointers leave the guest.
"""
import hashlib
import os
from pathlib import Path
import re
import time
import uuid

TRACEFS=Path('/sys/kernel/tracing')
SYMBOL='unix_mkname_bsd'
READ_CAP=32768
BUFFER_KIB=16

class CaptureError(Exception):
    pass

def bounded(path,limit=4096):
    with path.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise CaptureError('metadata-read-cap')
    return data.decode('ascii')

def identity(pid):
    try:
        raw=bounded(Path('/proc')/str(pid)/'stat',4096)
        fields=raw[raw.rindex(')')+2:].split()
        status=bounded(Path('/proc')/str(pid)/'status',8192)
        uid=re.search(r'^Uid:\s+(\d+)\s+',status,re.M)
        if not uid:raise CaptureError('identity-schema')
        return dict(pid=pid,ppid=int(fields[1]),pgid=int(fields[2]),sid=int(fields[3]),
                    startTicks=int(fields[19]),uid=int(uid[1]),available=True)
    except (OSError,ValueError,IndexError,CaptureError,UnicodeError) as error:
        return dict(pid=pid,available=False,reason='identity-unavailable',errorType=type(error).__name__)

def owned_scope():
    if os.getuid()!=0:return 'requires-owned-guest-root'
    try:
        if bounded(Path('/framey-owned-vm'),128)!='Framey private trace capability v1\n':return 'guest-marker-mismatch'
        if bounded(Path('/proc/1/comm'),64).strip()!='systemd':return 'guest-pid1-mismatch'
        if Path('/sys/class/net/eth0').exists():return 'network-device-present'
        if os.uname().machine not in ('x86_64','aarch64'):return 'unsupported-architecture'
        if os.getpid()==1:return 'observer-cannot-be-pid1'
    except (OSError,CaptureError,UnicodeError):return 'owned-guest-scope-unavailable'
    return None

def parse_capture(raw,*,origin_ns,finished_ns,cpu_stats,probe_profile,truncated=False):
    """Validate actual kernel text, return only bounded structured metadata."""
    result=dict(state='incomplete',captureComplete=False,completeScope='connect syscall timeline and observed filesystem lookup events',
        qualificationPassed=False,rawPayloadRetained=False,argumentPointersRetained=False,
        destinationTextRetained=False,syscalls=[],unassociatedFilesystemLookups=[],reasons=[])
    try:
        if truncated or len(raw)>READ_CAP:raise CaptureError('trace-read-cap')
        if not cpu_stats:raise CaptureError('missing-cpu-stats')
        required={'entries','overrun','commit overrun','dropped events'}
        for stats in cpu_stats:
            if not required.issubset(stats) or any(type(stats[k]) is not int or stats[k]<0 for k in required):raise CaptureError('invalid-cpu-stats')
            if any(stats[k] for k in ['overrun','commit overrun','dropped events']):raise CaptureError('kernel-trace-loss')
        if not isinstance(probe_profile,dict) or set(probe_profile)!={'hits','misses'}:raise CaptureError('probe-profile-schema')
        if any(type(v) is not int or v<0 for v in probe_profile.values()):raise CaptureError('probe-profile-schema')
        if probe_profile['misses']:raise CaptureError('kernel-probe-miss')
        pending={};pairs=[];unassociated=[];event_count=0;destination_count=0;last_stamp={}
        for line in raw.decode('ascii').splitlines():
            if not line or line.startswith('#'):continue
            m=re.fullmatch(r'\s*\S+-(\d+)\s+\[\d+\]\s+\S+\s+(\d+\.\d+):\s+(.*)',line)
            if not m:raise CaptureError('trace-layout')
            pid,stamp,body=int(m[1]),float(m[2]),m[3]
            if pid<=0 or not origin_ns/1e9<=stamp<=finished_ns/1e9:raise CaptureError('trace-clock-or-pid')
            if stamp<last_stamp.get(pid,stamp):raise CaptureError('per-task-clock-order')
            last_stamp[pid]=stamp;event_count+=1
            if body.startswith('sys_connect('):
                sm=re.fullmatch(r'sys_connect\(fd: (?:0x)?([0-9a-f]+), uservaddr: (?:0x)?[0-9a-f]+, addrlen: (?:0x)?([0-9a-f]+)\)',body)
                if not sm or pid in pending:raise CaptureError('syscall-entry-schema-or-pairing')
                pending[pid]=dict(pid=pid,enteredSeconds=stamp,filesystemLookups=[],endpointClassification='unclassified')
            elif body.startswith('unix_destination:'):
                # Prefix may contain return/function instruction pointers; discard it.
                dm=re.fullmatch(r'unix_destination:\s+.*?dest="(.*)" family=(\d+) addrlen=(-?\d+)',body)
                if not dm:raise CaptureError('destination-schema')
                text,family,length=dm[1],int(dm[2]),int(dm[3]);address=text.encode('ascii')
                if family!=1 or not 3<=length<=110:raise CaptureError('destination-family-or-length')
                if not address.startswith(b'/') or not 1<=len(address)<=108 or len(address)>length-2:raise CaptureError('unsupported-filesystem-destination')
                if any(v<32 or v>126 for v in address) or any(c in text for c in ['\\','"']):raise CaptureError('unsupported-destination-encoding')
                endpoint=dict(pid=pid,timestampSeconds=stamp,pathSha256=hashlib.sha256(address).hexdigest(),pathBytes=len(address),sockaddrBytes=length)
                destination_count+=1
                if pid in pending:
                    pending[pid]['filesystemLookups'].append(endpoint);pending[pid]['endpointClassification']='filesystem-lookup-observed'
                else:unassociated.append(endpoint)
            else:
                em=re.fullmatch(r'sys_connect -> (0x[0-9a-f]+)',body)
                if not em or pid not in pending:raise CaptureError('syscall-exit-schema-or-pairing')
                value=int(em[1],16)
                if value>=2**64:raise CaptureError('syscall-result-width')
                if value>=2**63:value-=2**64
                entry=pending.pop(pid);entry.update(exitedSeconds=stamp,result=value);pairs.append(entry)
        if pending:raise CaptureError('unfinished-syscall')
        if event_count!=sum(x['entries'] for x in cpu_stats):raise CaptureError('trace-entry-count-mismatch')
        if probe_profile['hits']<destination_count:raise CaptureError('probe-hit-count-mismatch')
        result.update(state='available',captureComplete=True,syscallCoverageComplete=True,
            endpointForEveryConnect=all(p['filesystemLookups'] for p in pairs),
            unclassifiedConnects=sum(not p['filesystemLookups'] for p in pairs),
            syscalls=pairs,unassociatedFilesystemLookups=unassociated,events=event_count,
            filesystemLookupEvents=destination_count,globalProbeHits=probe_profile['hits'],probeMisses=0)
    except (CaptureError,UnicodeError) as error:
        reason=str(error) if isinstance(error,CaptureError) else 'unsupported-trace-encoding'
        result.update(reasons=[reason],syscallCoverageComplete=False,endpointForEveryConnect=False)
    return result

class Observer:
    def __init__(self,*,enabled=False):
        self.enabled=enabled;self.instance=None;self.group=None;self.registered=False;self.paths=[]
        self.probe_command_attempted=False;self.started=False;self.finished=False
        self.report=dict(state='disabled',enabled=False,captureComplete=False,qualificationPassed=False)
    def _command(self,text):
        raw=(text+'\n').encode('ascii')
        if not 0<len(raw)<512:raise CaptureError('probe-command-bound')
        fd=os.open(TRACEFS/'kprobe_events',os.O_WRONLY|os.O_CLOEXEC)
        try:
            if os.write(fd,raw)!=len(raw):raise CaptureError('probe-command-short-write')
        finally:os.close(fd)
    def _profile(self):
        text=bounded(TRACEFS/'kprobe_profile',4096)
        rows=[line for line in text.splitlines() if line.split() and line.split()[0]=='unix_destination']
        if len(rows)!=1:raise CaptureError('owned-probe-profile-ambiguous')
        m=re.fullmatch(r'\s*unix_destination\s+(\d+)\s+(\d+)\s*',rows[0])
        if not m:raise CaptureError('owned-probe-profile-schema')
        return dict(hits=int(m[1]),misses=int(m[2]))
    def _cleanup(self):
        errors=[]
        if self.instance is not None:
            try:
                (self.instance/'tracing_on').write_text('0')
                for path in self.paths:
                    if path.exists():path.write_text('0')
                (self.instance/'set_event_pid').write_text('');self.instance.rmdir()
                self.report['ownedTraceInstanceRemoved']=True
            except (OSError,CaptureError):errors.append('trace-instance-cleanup')
        if self.group is not None and (self.registered or (self.probe_command_attempted and (TRACEFS/'events'/self.group/'unix_destination').exists())):
            try:
                self._command('-:'+self.group+'/unix_destination');self.report['ownedProbeRemoved']=True
            except (OSError,CaptureError):errors.append('probe-cleanup')
        if errors:
            self.report.update(state='incomplete',captureComplete=False,cleanupErrors=errors)
        return not errors
    def start(self):
        if self.started:return self.report.copy()
        self.started=True
        if not self.enabled:return self.report.copy()
        reason=owned_scope()
        if reason:
            self.report=dict(state='unavailable',enabled=True,reason=reason,captureComplete=False,qualificationPassed=False)
            return self.report.copy()
        self.report=dict(state='unavailable',enabled=True,captureComplete=False,qualificationPassed=False,
            kernel=os.uname().release,architecture=os.uname().machine,filterOwnerIdentity=identity(os.getpid()),
            ordinaryQualificationInstrumentation=False,observerTimingPerturbationPossible=True)
        stage='observer-source-unavailable'
        try:
            self.report['privateObserverSourceSha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            stage='tracefs-unavailable'
            if not (TRACEFS/'kprobe_events').exists():raise CaptureError(stage)
            if not self.report['filterOwnerIdentity']['available']:raise CaptureError('owner-identity-unavailable')
            token=str(os.getpid())+'_'+uuid.uuid4().hex[:12]
            self.group='framey_obs_'+token
            candidate=TRACEFS/'instances'/('framey-observer-'+token)
            if candidate.exists() or (TRACEFS/'events'/self.group).exists():raise CaptureError('owned-name-collision')
            candidate.mkdir();self.instance=candidate
            (candidate/'tracing_on').write_text('0')
            clocks=bounded(candidate/'trace_clock')
            if 'mono' not in clocks.replace('[','').replace(']','').split():raise CaptureError('mono-clock-unavailable')
            (candidate/'trace_clock').write_text('mono');(candidate/'buffer_size_kb').write_text(str(BUFFER_KIB))
            (candidate/'options/event-fork').write_text('1')
            # Only owned private events; no global trace clear or truncation.
            stage='probe-registration-unavailable'
            definition='r32:'+self.group+'/unix_destination '+SYMBOL+' dest=+2($arg1):string family=+0($arg1):u16 addrlen=$arg2:s32'
            self.probe_command_attempted=True
            self._command(definition);self.registered=True
            stage='trace-instance-configuration-unavailable'
            paths=[candidate/'events/syscalls/sys_enter_connect/enable',candidate/'events/syscalls/sys_exit_connect/enable',candidate/'events'/self.group/'unix_destination/enable']
            self.paths=paths
            self.report.update(probeDefinition=definition,probeFormat=bounded(paths[-1].parent/'format',8192),
                traceClock=bounded(candidate/'trace_clock'),bufferConfiguredKiBPerCpu=BUFFER_KIB,readCapBytes=READ_CAP)
            (candidate/'set_event_pid').write_text(str(os.getpid()))
            (candidate/'trace').write_text('')
            stage='trace-start-unavailable'
            for path in paths:path.write_text('1')
            self.origin_ns=time.monotonic_ns();self.report['originMonotonicNs']=self.origin_ns
            (candidate/'tracing_on').write_text('1')
            self.report.update(state='available',captureActive=True)
        except (OSError,CaptureError,UnicodeError) as error:
            self.report.update(state='unavailable',reason=str(error) if isinstance(error,CaptureError) else stage,
                errorType=type(error).__name__,errno=getattr(error,'errno',None),captureActive=False)
            self._cleanup()
        return self.report.copy()
    def finish(self):
        if self.finished:return self.report.copy()
        self.finished=True
        if not self.enabled or self.report.get('state')!='available':return self.report.copy()
        try:
            (self.instance/'tracing_on').write_text('0');finished=time.monotonic_ns()
            with (self.instance/'trace').open('rb') as stream:raw=stream.read(READ_CAP+1)
            stats=[]
            for path in sorted((self.instance/'per_cpu').glob('cpu*/stats')):
                record={}
                for line in bounded(path).splitlines():
                    key,separator,value=line.partition(':')
                    if separator and value.strip().isdigit():record[key.strip()]=int(value.strip())
                stats.append(record)
            profile=self._profile()
            parsed=parse_capture(raw,origin_ns=self.origin_ns,finished_ns=finished,cpu_stats=stats,
                                 probe_profile=profile,truncated=len(raw)>READ_CAP)
            self.report.update(parsed,finishedMonotonicNs=finished,captureActive=False,
                rawBytesRead=len(raw),readTruncated=len(raw)>READ_CAP,perCpuStats=stats,probeProfile=profile)
            pids={p['pid'] for p in parsed['syscalls']}|{p['pid'] for p in parsed['unassociatedFilesystemLookups']}
            participants=[identity(pid) for pid in sorted(pids)]
            owner_after=identity(os.getpid());owner_before=self.report['filterOwnerIdentity']
            self.report.update(participantIdentityAtCaptureEnd=participants,
                participantIdentityCoverageComplete=parsed['captureComplete'] and all(p['available'] for p in participants),
                filterOwnerIdentityRechecked=owner_after==owner_before,
                descendantStartIdentityNotInferredFromPid=True)
            if owner_after!=owner_before:self.report.update(state='incomplete',captureComplete=False,reasons=['owner-identity-changed'])
        except (OSError,CaptureError,UnicodeError) as error:
            self.report.update(state='incomplete',captureComplete=False,captureActive=False,
                reason='capture-read-unavailable',errorType=type(error).__name__,errno=getattr(error,'errno',None))
        finally:self._cleanup()
        return self.report.copy()
