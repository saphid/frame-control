"""Execute saved guest control flow only with synthetic files and fake modules."""
import builtins
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import types
import unittest

ROOT = Path(__file__).parent


class GuestFlow(unittest.TestCase):
    def invoke(self, *, stop_error=False, finish_error=False, transport_error=False):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            def mapped(path='', *rest):
                path=Path(path, *rest)
                return home / str(path).lstrip('/') if path.is_absolute() else path
            def put(path,data):
                path=mapped(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
            put('/framey-owned-vm',b'Framey private trace capability v1\n')
            put('/proc/1/comm',b'systemd\n'); put('/sys/kernel/tracing/trace_clock',b'boot')
            put('/sys/class/virtio-ports/vport0p0/name',b'private-test-port')
            put('/dev/vport0p0',b'')
            source=io.BytesIO()
            with tarfile.open(fileobj=source,mode='w') as archive:
                member=tarfile.TarInfo('tests/decky-runtime/check.py'); member.size=9
                archive.addfile(member,io.BytesIO(b'synthetic'))
            put('/input/source.tar',source.getvalue()); put('/input/PluginLoader',b'loader')
            payloads=['observer.py','base_observer.py','live_boundary.py','loopback_observation.py',
                      'retain_report.py','observe_fixture.py','sidecar_transport.py']
            for name in payloads:put('/input/'+name,b'synthetic payload')
            digest=lambda data:hashlib.sha256(data).hexdigest()
            inputs=dict(architecture='aarch64',sourceRevision='exact-main-model',
                        sourceArchiveSha256=digest(source.getvalue()),loaderSha256=digest(b'loader'),
                        observerSha256=digest(b'synthetic payload'),scopeHelperSha256=digest(b'synthetic payload'),
                        sourceSha256={'tests/decky-runtime/check.py':digest(b'synthetic')},
                        loopbackObservationEnabledDiagnostic=True,
                        loopbackPayloadSha256={n:digest(b'synthetic payload') for n in payloads[2:]})
            put('/input/inputs.json',json.dumps(inputs).encode())
            calls=[]; captured=[]; collections=[]
            class Observer:
                def __init__(self,**kwargs):self.report={'captureActive':False}
                def start(self):self.report['captureActive']=True;return {'state':'available'}
                def finish(self):
                    if finish_error:raise OSError('synthetic finish')
                    self.report['captureActive']=False;return {'captureComplete':True}
            def run(command,**kwargs):
                calls.append((command,kwargs))
                if command[:2]==['systemctl','stop'] and stop_error:
                    raise subprocess.TimeoutExpired('synthetic stop',40)
                return subprocess.CompletedProcess(command,1 if command[0]=='runuser' else 0,stdout='',stderr='synthetic native failure')
            def collect():
                collections.append(1)
                if transport_error:raise ValueError('PRIVATE ERROR')
                return {'retainedOnFailedProbe':True,'qualificationPassed':False}
            replacements={
                'pathlib':types.SimpleNamespace(Path=mapped),
                'os':types.SimpleNamespace(getuid=lambda:0,getpid=lambda:2,uname=lambda:types.SimpleNamespace(machine='aarch64')),
                'subprocess':types.SimpleNamespace(run=run),
                'sys':types.SimpleNamespace(path=[]),
                'observer':types.SimpleNamespace(Observer=Observer,__file__='/input/observer.py'),
                'sidecar_transport':types.SimpleNamespace(collect=collect),
                'guest_result':types.SimpleNamespace(PORT='private-test-port',write_result=lambda stream,value:captured.append(value.copy()))}
            original_import=builtins.__import__
            def importer(name,*a,**kw):return replacements[name] if name in replacements else original_import(name,*a,**kw)
            env={'__builtins__':dict(vars(builtins),__import__=importer)}
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile((ROOT/'guest.py').read_bytes(),'saved-guest.py','exec'),env)
            self.assertEqual(len(captured),1); self.assertEqual(collections,[1])
            return captured[0],calls

    def test_nonzero_probe_still_retains_sidecar_and_native_failure(self):
        report,calls=self.invoke()
        self.assertFalse(report['success']);self.assertEqual(report['probeExitStatus'],1)
        self.assertTrue(report['loopbackDiagnostic']['retainedOnFailedProbe'])
        self.assertTrue(report['ownedUserManagerStopped'])
        command,kw=next(x for x in calls if x[0][0]=='runuser')
        self.assertEqual(command[-2:],['-B','/input/observe_fixture.py'])
        self.assertEqual(kw['timeout'],120)

    def test_manager_timeout_keeps_original_error_and_retains_sidecars(self):
        report,calls=self.invoke(stop_error=True)
        self.assertEqual(report['errorType'],'AssertionError')
        self.assertEqual(report['probeExitStatus'],1)
        self.assertEqual(report['userManagerStopErrorType'],'TimeoutExpired')
        self.assertFalse(report['ownedUserManagerStopped']);self.assertFalse(report['success'])
        self.assertIn('loopbackDiagnostic',report)

    def test_observer_cleanup_error_does_not_skip_manager_or_transport(self):
        report,calls=self.invoke(finish_error=True)
        self.assertEqual(report['errorType'],'OSError');self.assertEqual(report['observerCleanupErrorType'],'OSError')
        self.assertTrue(report['ownedUserManagerStopped']);self.assertFalse(report['success'])
        self.assertIn('loopbackDiagnostic',report)

    def test_transport_error_never_turns_failed_probe_into_success(self):
        report,calls=self.invoke(transport_error=True)
        self.assertFalse(report['success']);self.assertEqual(report['probeExitStatus'],1)
        self.assertEqual(report['loopbackDiagnostic']['reason'],'transport-error')
        self.assertNotIn('PRIVATE ERROR',json.dumps(report))


if __name__=='__main__':unittest.main(verbosity=2)
