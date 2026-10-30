"""The optional HTTP gateway must stay inside its marked disposable VM."""
import importlib.util
import copy
import io
import json
from pathlib import Path
import tarfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GatewayProgressTransport(unittest.TestCase):
    def emit(self, report):
        from contextlib import redirect_stdout
        gateway = load('gateway_progress_chunks', ROOT/'tests/decky-runtime/syncthing_http.py')
        output = io.StringIO()
        with redirect_stdout(output):
            gateway.emit_gateway_progress(report)
        lines = output.getvalue().splitlines()
        self.assertTrue(lines)
        self.assertTrue(all(len(line.encode()) < 8192 for line in lines))
        chunks = [json.loads(line.removeprefix('FRAMEY_HTTP_GATEWAY_PROGRESS_CHUNK_JSON='))
                  for line in lines]
        self.assertEqual([v['index'] for v in chunks], list(range(len(chunks))))
        self.assertTrue(all(v['total'] == len(chunks) for v in chunks))
        encoded = ''.join(v['data'] for v in chunks)
        import hashlib
        self.assertEqual({v['sha256'] for v in chunks}, {hashlib.sha256(encoded.encode()).hexdigest()})
        return json.loads(encoded), len(chunks)

    def test_large_profile_keeps_complete_trace_and_cleanup_beyond_journal_line_limit(self):
        report = dict(statusProcessProfiles={'records': [{'samples': [{'processes': [dict(
            pid=1, parentPid=2, command='python3', state='R', cpuTicks=100,
            residentPages=5000, waitChannel='0')]*12}]*3}]*39},
            fixtureCefTrace={'records': [{'requestId': n, 'outcome': 'succeeded'} for n in range(40)]},
            ownedBrowserReaped=True, httpServerStopped=True, ownedReceiptRemoved=True,
            sshObserverRemoved=True)
        self.assertGreater(len(json.dumps(report)), 49152)
        restored, count = self.emit(report)
        self.assertEqual(restored, report)
        self.assertGreater(count, 1)

    def test_escaped_and_unicode_data_round_trip_with_bounded_lines(self):
        report = {'value': '\u2603"\\\n'*3000, 'ownedReceiptRemoved': True}
        restored, _count = self.emit(report)
        self.assertEqual(restored, report)

    def test_oversized_progress_explicitly_refuses_complete_evidence_claim(self):
        report = {'unexpected': 'x'*(2*1024**2)}
        restored, count = self.emit(report)
        self.assertEqual(count, 1)
        self.assertEqual(restored, dict(progressReportOverflow=True,
                                       encodedBytes=len(json.dumps(report))))


class GatewayIsolation(unittest.TestCase):
    def test_host_and_wrong_guest_marker_refuse_before_commands_or_environment_changes(self):
        gateway = load('http_gateway_guard', ROOT/'tests/decky-runtime/syncthing_http.py')
        for uid, marker in [(0, 'Frame Control Flatpak VM v1\n'), (1100, 'different guest\n')]:
            with self.subTest(uid=uid, marker=marker), \
                    patch.object(gateway.os, 'getuid', return_value=uid, create=True), \
                    patch.object(gateway.Path, 'read_text', return_value=marker), \
                    patch.object(gateway.subprocess, 'Popen') as start, \
                    patch.dict(gateway.os.environ, {}, clear=True):
                with self.assertRaises(AssertionError):
                    gateway.exercise(None, 'unused.service')
                start.assert_not_called()
                self.assertEqual(dict(gateway.os.environ), {})

    def test_production_bundle_contains_unchanged_dispatch_and_catalogue_import_dependencies(self):
        driver = load('http_gateway_packer', ROOT/'scripts/framey-test-syncthing-flatpak-package.py')
        payloads, metadata = driver.http_gateway_payloads()
        with tarfile.open(fileobj=io.BytesIO(payloads['framey-http-ui.tar'])) as archive:
            names = set(archive.getnames())
            self.assertTrue({'ui/server.py', 'ui/framey_panel.py', 'ui/local-bin/ssh',
                             'ui/frame_steam.py', 'apk-catalog/build.py',
                             'apk-catalog/reports.py', 'apk-catalog/pick.py'} <= names)
            self.assertEqual(names, set(metadata['sourceSha256']))
            self.assertEqual(metadata['sourceSha256'],
                             json.loads(payloads['framey-http-ui-sources.json']))
            for member in archive:
                self.assertTrue(member.isfile())
                self.assertFalse(member.name.startswith('/'))
                self.assertNotIn('..', Path(member.name).parts)
                self.assertEqual(archive.extractfile(member).read(), (ROOT/member.name).read_bytes())
            self.assertEqual(archive.getmember('ui/local-bin/ssh').mode, 0o700)


class ProductionBrowserParent(unittest.TestCase):
    def driver(self):
        return load('http_parent_driver', ROOT/'scripts/framey-test-syncthing-flatpak-package.py')

    def test_optional_parent_is_packed_only_when_requested(self):
        driver = self.driver()
        self.assertNotIn('syncthing_http_parent.py', driver.http_gateway_payloads()[0])
        payloads, _metadata = driver.http_gateway_payloads(browser_parent=True)
        self.assertEqual(payloads['syncthing_http_parent.py'],
                         (ROOT/'tests/decky-runtime/syncthing_http_parent.py').read_bytes())

    def test_parent_refuses_host_before_service_or_browser_commands(self):
        parent = load('http_parent_guard', ROOT/'tests/decky-runtime/syncthing_http_parent.py')
        with patch.object(parent.os, 'getuid', return_value=0, create=True), \
                patch.object(parent, 'command') as command:
            with self.assertRaises(AssertionError):
                parent.exercise(None, None, None, None, None, None, None)
            command.assert_not_called()

    def evidence(self):
        report = dict.fromkeys(('success', 'syntheticInput', 'syntheticCef', 'syntheticStoreReceipt',
            'productionParentUnchanged', 'productionPanelUnchanged', 'actualDeckyUserService',
            'actualDeckyDiscovery', 'ownedTargetClosed'), True)
        report.update(dict.fromkeys(('realSteamCef', 'realFrameContacted', 'managedInstallVerified',
            'installerEnabled', 'bootstrapStateInjected', 'browserSandboxDisabled'), False))
        report.update(childHarness=dict(installed=True, mode='owned-iframe-target', universalAccessGranted=False),
            manualPortFallbackUsed=False, parentErrors=[],
            stages=[dict(stage=stage, errors=[],
                         text=('Running\nFolders\nPrivate service sync\nDevices\nowned-peer'
                               if stage in ('running', 'restarted') else 'Stopped'),
                         manualPortFallbackUsed=False)
                    for stage in ('running', 'stopped', 'restarted', 'stopped')],
            actualPackagedProcessObservations=[dict(stage='running', pids=[101, 102]),
                                              dict(stage='restarted', pids=[201, 202])],
            sandboxedRendererPids=[dict(seccomp=2, noNewPrivs=1, ancestryToBrowser=[310, 300])],
            requestedAssets=['/headset', '/framey/panel/64', '/framey-runtime/host.js'],
            screenshots=dict.fromkeys(('running1', 'stopped2', 'restarted3', 'stopped4'), 'placeholder'),
            httpRequests=[dict(method='get_settings_json', httpStatus=200),
                          dict(method='set_setting', httpStatus=200)] + [
                dict(method='framey_http_fetch', path='/__decky-watchdog/'+path, httpStatus=200,
                     backendStatus=200 if path=='state' else 204) for path in ('start', 'stop', 'state')])
        for entry in report['httpRequests']:
            entry.update(startedAfterSeconds=0.0, elapsedSeconds=0.1)
        return report

    def test_verifier_requires_real_service_and_unchanged_parent_without_injected_state(self):
        driver = self.driver(); report = self.evidence()
        driver.verify_http_parent(report)
        for key, invalid in [('actualDeckyUserService', False), ('productionParentUnchanged', False),
                             ('bootstrapStateInjected', True), ('realSteamCef', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                driver.verify_http_parent({**report, key: invalid})

    def test_verifier_rejects_visible_error_despite_successful_stage_and_http(self):
        report = self.evidence()
        report['stages'][0]['text'] += '\nError: Too many Syncthing requests'
        with self.assertRaisesRegex(ValueError, 'browser lifecycle'):
            self.driver().verify_http_parent(report)

    def test_verifier_rejects_running_or_restarted_loading_placeholders(self):
        for index in (0, 2):
            with self.subTest(stage=index):
                report = self.evidence()
                report['stages'][index]['text'] = 'Running\nFolders\nDevices'
                with self.assertRaisesRegex(ValueError, 'browser lifecycle'):
                    self.driver().verify_http_parent(report)

    def test_verifier_rejects_reused_pid_missing_assets_and_backend_failure(self):
        driver = self.driver()
        changes = [lambda r:r['httpRequests'][0].update(elapsedSeconds=-1),
                   lambda r:r['childHarness'].update(universalAccessGranted=True),
                   lambda r:r['actualPackagedProcessObservations'][1].update(pids=[101, 202]),
                   lambda r:r.update(requestedAssets=['/headset']),
                   lambda r:r['httpRequests'][-1].update(backendStatus=500)]
        for change in changes:
            report = copy.deepcopy(self.evidence()); change(report)
            with self.assertRaises(ValueError):
                driver.verify_http_parent(report)


class ScopedChildHarness(unittest.TestCase):
    def parent(self):
        return load('scoped_parent_harness', ROOT/'tests/decky-runtime/syncthing_http_parent.py')

    def test_out_of_process_child_is_exact_url_scoped_and_detached(self):
        parent = self.parent()
        url = 'http://127.0.0.1:42/framey/panel/64?session=owned#owned'
        calls = []
        def command(_page, method, params, session_id=None):
            calls.append((method, params, session_id))
            if method == 'Target.getTargets':
                return {'targetInfos': [dict(type='iframe', url=url, targetId='owned'),
                    dict(type='iframe', url=url+'/other', targetId='unrelated')]}
            if method == 'Target.attachToTarget':
                self.assertEqual(params, dict(targetId='owned', flatten=True))
                return {'sessionId': 'owned-session'}
            if method == 'Runtime.evaluate':
                self.assertEqual(session_id, 'owned-session')
                return {'result': {'value': True}}
            self.assertEqual(method, 'Target.detachFromTarget')
            self.assertEqual(params, {'sessionId': 'owned-session'})
            return {}
        with patch.object(parent, 'command', command):
            result = parent.install_child_harness(None, url, '/* DOM driver */')
        self.assertEqual(result, dict(installed=True, mode='owned-iframe-target', universalAccessGranted=False))
        self.assertEqual(calls[-1][0], 'Target.detachFromTarget')

    def test_local_child_uses_its_frame_world_without_universal_access(self):
        parent = self.parent(); calls = []
        url = 'http://127.0.0.1:42/framey/panel/64'
        def command(_page, method, params, session_id=None):
            calls.append((method, params))
            if method == 'Target.getTargets': return {'targetInfos': []}
            if method == 'Page.getFrameTree':
                return {'frameTree': {'frame': {'id': 'parent', 'url': 'http://127.0.0.1:42/headset'},
                    'childFrames': [{'frame': {'id': 'child', 'url': url}}]}}
            if method == 'Page.createIsolatedWorld':
                self.assertEqual(params, dict(frameId='child', worldName='owned-panel-dom-driver'))
                return {'executionContextId': 8}
            self.assertEqual(method, 'Runtime.evaluate')
            self.assertEqual(params['contextId'], 8)
            return {'result': {'value': True}}
        with patch.object(parent, 'command', command):
            self.assertEqual(parent.install_child_harness(None, url, '/* DOM driver */')['mode'],
                             'owned-frame-isolated-world')

    def test_child_script_failure_still_detaches_owned_session(self):
        parent = self.parent(); url = 'http://127.0.0.1:42/framey/panel/64'
        command = Mock(side_effect=[{'targetInfos': [dict(type='iframe', url=url, targetId='owned')]},
            {'sessionId': 'owned-session'}, {'exceptionDetails': {'text': 'fixture script failed'}}, {}])
        with patch.object(parent, 'command', command), self.assertRaises(AssertionError):
            parent.install_child_harness(None, url, '/* DOM driver */')
        self.assertEqual(command.call_args.args[1:],
                         ('Target.detachFromTarget', {'sessionId': 'owned-session'}))


class PrivateSshDiagnostics(unittest.TestCase):
    def gateway(self):
        return load('private_ssh_diagnostics', ROOT/'tests/decky-runtime/syncthing_http.py')

    def test_observer_passes_arguments_and_result_without_retaining_credentials(self):
        import threading
        module = self.gateway(); records = []; result = object(); call = Mock(return_value=result)
        options = dict(stdin='private-fixture-credential', timeout=15, text=False)
        self.assertIs(module.observe_ssh(call, records, threading.Lock(), module.time.monotonic(),
                                        'decky-status', 'python3 -', **options), result)
        call.assert_called_once_with('python3 -', **options)
        self.assertEqual(records[0]['outcome'], 'success')
        self.assertNotIn('private-fixture-credential', json.dumps(records))
        self.assertNotIn('python3 -', json.dumps(records))

    def test_observer_reraises_same_error_and_retains_only_fixed_category(self):
        import threading
        module = self.gateway(); records = []
        error = RuntimeError('Timed out talking to private-fixture-credential')
        with self.assertRaises(RuntimeError) as caught:
            module.observe_ssh(Mock(side_effect=error), records, threading.Lock(),
                               module.time.monotonic(), 'panel-method', 'unused')
        self.assertIs(caught.exception, error)
        self.assertEqual(records[0]['errorCategory'], 'ssh-timeout')
        self.assertEqual(records[0]['outcome'], 'failure')
        self.assertNotIn('private-fixture-credential', json.dumps(records))

    def test_response_categories_do_not_expose_raw_error_or_detail(self):
        module = self.gateway()
        self.assertEqual(module.safe_error_category({'error':'Timed out talking to private-host',
                          'detail':'private-fixture-key', 'offline':True}), 'ssh-timeout')
        self.assertEqual(module.safe_error_category({'error':'unknown private-fixture-key'}), 'other')

    def test_shipped_method_and_event_templates_with_common_preamble_have_distinct_kinds(self):
        import sys
        with patch.object(sys, 'path', [str(ROOT/'ui'), *sys.path]):
            import framey_panel
        module = self.gateway()
        method = framey_panel.METHOD_SCRIPT.replace('__FRAMEY_METHOD_PAYLOAD__', repr('{}'))
        event = framey_panel.EVENT_SCRIPT.replace('__FRAMEY_EVENTS_SOURCE__', repr('fixture'))
        # The earlier prefix-only observer incorrectly called both a method.
        prefix = framey_panel.METHOD_SCRIPT.partition('__FRAMEY_METHOD_PAYLOAD__')[0]
        self.assertTrue(method.startswith(prefix) and event.startswith(prefix))
        self.assertEqual(module.panel_command_kind(method, framey_panel), 'panel-method')
        self.assertEqual(module.panel_command_kind(event, framey_panel), 'panel-events')
        for unrelated in (None, b'private-fixture-credential', framey_panel.STEAM_READ_SCRIPT,
                          prefix+'private-fixture-credential'):
            self.assertIsNone(module.panel_command_kind(unrelated, framey_panel))


class StatusProcessDiagnostics(unittest.TestCase):
    def gateway(self):
        return load('status_process_diagnostics', ROOT/'tests/decky-runtime/syncthing_http.py')

    def process(self, root, pid, parent, command='python3', children='', channel='0'):
        folder = root/str(pid)
        (folder/'task'/str(pid)).mkdir(parents=True)
        fields = ['0'] * 22
        fields[0], fields[1], fields[11], fields[12], fields[21] = 'S', str(parent), '17', '3', '12'
        (folder/'stat').write_text(str(pid)+' ('+command+') '+' '.join(fields))
        (folder/'wchan').write_text(channel)
        (folder/'task'/str(pid)/'children').write_text(children)
        (folder/'cmdline').write_text('private-fixture-credential')
        (folder/'environ').write_text('private-fixture-credential')

    def tree(self, root, children):
        folder = root/'self/task/313'
        folder.mkdir(parents=True)
        (folder/'children').write_text(children)

    def test_samples_only_owned_descendants_and_never_retains_commands_or_unknown_names(self):
        import tempfile
        module = self.gateway()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.tree(root, '101 103')
            self.process(root, 101, 900, 'bash', '102', 'do_wait')
            self.process(root, 102, 101, 'private-secret', channel='private-secret')
            self.process(root, 103, 999, 'python3')  # PID reused outside our tree.
            result = module.status_process_tree(313, root, owner_pid=900)
        self.assertEqual([v['pid'] for v in result['processes']], [101, 102])
        self.assertEqual([v['command'] for v in result['processes']], ['bash', 'other'])
        self.assertEqual([v['waitChannel'] for v in result['processes']], ['do_wait', 'other'])
        self.assertTrue(all(v['cpuTicks'] == 20 and v['residentPages'] == 12 for v in result['processes']))
        self.assertFalse(result['truncated'])
        self.assertNotIn('private', json.dumps(result))
        self.assertTrue(all(set(v) == {'pid', 'parentPid', 'command', 'state', 'cpuTicks',
                                      'residentPages', 'waitChannel'} for v in result['processes']))

    def test_process_tree_is_bounded_without_changing_or_signalling_any_process(self):
        import tempfile
        module = self.gateway()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.tree(root, ' '.join(str(pid) for pid in range(101, 121)))
            for pid in range(101, 121):
                self.process(root, pid, 900)
            result = module.status_process_tree(313, root, owner_pid=900)
        self.assertEqual(len(result['processes']), 12)
        self.assertTrue(result['truncated'])

    def test_sampler_uses_three_fixed_observations_and_stops_on_cancellation(self):
        module = self.gateway(); sampler = module.StatusProcessSampler(10)
        sampler.cancel = Mock()
        sampler.cancel.wait.side_effect = [False, False, True]
        with patch.object(module, 'status_process_tree', side_effect=[
                dict(processes=[], truncated=False), dict(processes=[], truncated=False)]), \
                patch.object(module.time, 'monotonic', side_effect=[12, 18]):
            sampler.run()
        self.assertEqual([v['elapsedSeconds'] for v in sampler.samples], [2, 8])
        self.assertEqual([v.args[0] for v in sampler.cancel.wait.call_args_list], [2, 6, 6])

    def test_unavailable_proc_samples_do_not_retain_raw_errors(self):
        module = self.gateway(); sampler = module.StatusProcessSampler(0)
        sampler.cancel = Mock(); sampler.cancel.wait.return_value = False
        with patch.object(module, 'status_process_tree', side_effect=OSError('private-fixture-credential')):
            sampler.run()
        self.assertEqual(sampler.errors, 3)
        self.assertEqual(sampler.samples, [])
        self.assertNotIn('private', json.dumps(sampler.samples))

    def test_owned_sampler_thread_is_reaped_without_waiting_for_a_sample(self):
        module = self.gateway(); sampler = module.StatusProcessSampler(module.time.monotonic())
        sampler.cancel.set(); sampler.start(); result = sampler.finish()
        self.assertTrue(result['observerStopped'])
        self.assertEqual(result['samples'], [])

    def test_profiled_observer_preserves_exact_call_result_error_and_arguments(self):
        import threading
        module = self.gateway()
        for kind, error in ((kind, error) for kind in ('decky-status', 'panel-method', 'panel-events')
                            for error in (None, RuntimeError('private-fixture-credential'))):
            records = []; profiles = dict(records=[], overflow=False); result = object()
            call = Mock(return_value=result, side_effect=error)
            sampler = Mock(); sampler.finish.return_value = dict(samples=[], unavailableSamples=0,
                                                                  observerStopped=True)
            with patch.object(module, 'StatusProcessSampler', return_value=sampler):
                def run():
                    return module.observe_ssh(call, records, threading.Lock(), module.time.monotonic(),
                        kind, 'python3 -', stdin='private-fixture-credential', timeout=15,
                        process_profiles=profiles)
                if error:
                    with self.assertRaises(RuntimeError) as caught:
                        run()
                    self.assertIs(caught.exception, error)
                else:
                    self.assertIs(run(), result)
            call.assert_called_once_with('python3 -', stdin='private-fixture-credential', timeout=15)
            sampler.start.assert_called_once_with(); sampler.finish.assert_called_once_with()
            self.assertEqual(len(profiles['records']), 1)
            self.assertTrue(profiles['records'][0]['observerStopped'])
            self.assertEqual(profiles['records'][0]['kind'], kind)
            self.assertNotIn('private', json.dumps(profiles))

    def test_profile_overflow_never_drops_an_actual_ssh_call(self):
        import threading
        module = self.gateway(); profiles = dict(records=[{} for _ in range(128)], overflow=False)
        call = Mock(return_value='unchanged'); sampler = Mock()
        sampler.finish.return_value = dict(samples=[], unavailableSamples=0, observerStopped=True)
        with patch.object(module, 'StatusProcessSampler', return_value=sampler):
            result = module.observe_ssh(call, [], threading.Lock(), module.time.monotonic(),
                                       'decky-status', 'owned', process_profiles=profiles)
        self.assertEqual(result, 'unchanged'); call.assert_called_once_with('owned')
        self.assertEqual(len(profiles['records']), 128)
        self.assertTrue(profiles['overflow'])

    def test_unavailable_sampler_thread_cannot_replace_the_actual_ssh_call(self):
        import threading
        module = self.gateway(); profiles = dict(records=[], overflow=False)
        call = Mock(return_value='unchanged'); sampler = Mock()
        sampler.start.side_effect = RuntimeError('private-fixture-credential')
        with patch.object(module, 'StatusProcessSampler', return_value=sampler):
            result = module.observe_ssh(call, [], threading.Lock(), module.time.monotonic(),
                                       'decky-status', 'owned', process_profiles=profiles)
        self.assertEqual(result, 'unchanged'); call.assert_called_once_with('owned')
        sampler.finish.assert_not_called()
        self.assertEqual(profiles['records'][0]['unavailableSamples'], 1)
        self.assertNotIn('private', json.dumps(profiles))


class AuthenticatedRuntimeReadiness(unittest.TestCase):
    def gateway(self):
        return load('gateway_readiness', ROOT/'tests/decky-runtime/syncthing_http.py')

    def test_too_early_and_bad_gateway_require_eventual_authenticated_success(self):
        fetch = Mock(side_effect=[{'status': 425}, {'status': 502},
                                  {'status': 200, 'body': '{"myID":"owned-fixture"}'}])
        def wait(ready, _description):
            self.assertIs(ready(), False)
            self.assertIs(ready(), False)
            return ready()
        result = self.gateway().wait_authenticated_rest(fetch, 'private-fixture-key', wait)
        self.assertEqual(result['status'], 200)
        fetch.assert_called_with('GET', '/rest/system/status', {'X-API-Key': 'private-fixture-key'})

    def test_authentication_or_unknown_http_failure_is_not_readiness(self):
        for status in (401, 403, 500, 503):
            with self.subTest(status=status), self.assertRaises(AssertionError):
                self.gateway().wait_authenticated_rest(lambda *_args: {'status': status},
                                                       'fixture', lambda ready, _description: ready())

    def test_http_success_requires_actual_runtime_identity(self):
        with self.assertRaises((AssertionError, KeyError)):
            self.gateway().wait_authenticated_rest(lambda *_args: {'status': 200, 'body': '{}'},
                                                   'fixture', lambda ready, _description: ready())


class PrivateCefDiagnostics(unittest.TestCase):
    def run_fixture(self, scenario):
        import re
        import shutil
        import subprocess
        executable = shutil.which('node')
        if executable is None:
            self.skipTest('Node is required for fixture JavaScript behavior')
        gateway = load('private_cef_diagnostics', ROOT/'tests/decky-runtime/syncthing_http.py')
        source = re.search(r'<script>(.*)</script>', gateway.CEF, re.S).group(1)
        source = source.replace('__FIXTURE_TOKEN__', json.dumps('private-fixture-auth'))
        harness = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const sockets=[],timers=[];let now=0;
class Socket {
 constructor(url){this.url=url;this.sent=[];this.readyState=0;sockets.push(this);}
 send(value){assert.equal(this.readyState,1);this.sent.push(JSON.parse(value));}
 close(){this.closed=true;this.readyState=3;this.onclose?.();}
}
const open=socket=>{socket.readyState=1;socket.onopen();};
const answer=(socket,id,type,result)=>socket.onmessage({data:JSON.stringify({id,type,result})});
const context={WebSocket:Socket,performance:{now:()=>now},
 setTimeout:(callback,budget)=>{timers.push({callback,budget});return timers.length;},
 clearTimeout:id=>{timers[id-1].cleared=true;}};
context.window=context;vm.createContext(context);
vm.runInContext(SOURCE,context);
(async()=>{SCENARIO
const trace=JSON.stringify(context.fixtureRpcTrace);
assert(!trace.includes('private-fixture-auth')&&!trace.includes('private-fixture-argument'));
assert(!trace.includes('private-response')&&!trace.includes('ws://'));
for(const entry of context.fixtureRpcTrace){
 assert(Object.keys(entry).every(key=>['requestId','method','startedAfterMilliseconds','outcome',
 'elapsedMilliseconds','openElapsedMilliseconds'].includes(key)));
}
console.log(JSON.stringify({records:context.fixtureRpcTrace,overflow:context.fixtureTraceOverflow,
 socketCount:context.fixtureSocketCount,requestCount:context.fixtureRequestCount}));
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        script = harness.replace('SOURCE', json.dumps(source)).replace('SCENARIO', scenario)
        result = subprocess.run([executable], input=script, capture_output=True, text=True,
                                timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_one_socket_multiplexes_concurrent_requests_with_unique_ids(self):
        result = self.run_fixture(r'''
const first=context.DeckyBackend.call('loader/call_legacy_plugin_method','Syncthing',
 'set_setting',{value:'private-fixture-argument'});
now=5;const second=context.DeckyBackend.call('loader/call_legacy_plugin_method','Syncthing',
 'get_settings_json',{value:'private-fixture-argument'});
assert.equal(sockets.length,1);now=10;open(sockets[0]);
const sync=sockets[0].sent[0];assert.equal(sync.type,4);assert.equal(sync.messages.length,0);
const [a,b]=sockets[0].sent.filter(message=>message.type===0);assert(a.id!==b.id);
assert.equal(a.args[2].value,'private-fixture-argument');
// Events and unknown response IDs must not resolve another call.
sockets[0].onmessage({data:JSON.stringify({type:5,event:'fixture-event',args:[]})});
now=25;answer(sockets[0],b.id,1,'private-response-two');
now=35;answer(sockets[0],a.id,1,'private-response-one');
assert.equal(await first,'private-response-one');assert.equal(await second,'private-response-two');
assert.equal(sockets[0].sent.filter(message=>message.type===3).length,2);
assert(timers.every(timer=>timer.budget===20000&&timer.cleared));
assert(!sockets[0].closed);
''')
        self.assertEqual([v['method'] for v in result['records']],
                         ['set_setting', 'get_settings_json'])
        self.assertEqual([v['elapsedMilliseconds'] for v in result['records']], [35, 20])
        self.assertEqual([v['outcome'] for v in result['records']], ['succeeded', 'succeeded'])
        self.assertFalse(result['overflow'])
        self.assertEqual(result['socketCount'], 1)
        self.assertEqual(result['requestCount'], 2)
        self.assertEqual([v['requestId'] for v in result['records']], [1, 2])

    def test_timeout_rejection_and_socket_failure_keep_individual_outcomes(self):
        result = self.run_fixture(r'''
const make=()=>context.DeckyBackend.call('loader/call_legacy_plugin_method',
 'Syncthing','framey_http_fetch',{headers:{key:'private-fixture-argument'}});
const timeout=make();open(sockets[0]);now=20000;timers[0].callback();
await assert.rejects(timeout,/Fixture Decky RPC timeout/);assert(!sockets[0].closed);
const rejected=make();let message=sockets[0].sent.at(-1);
answer(sockets[0],message.id,-1,'private-response');
await assert.rejects(rejected,/Fixture Decky RPC rejected/);
const broken=make();sockets[0].onerror();
await assert.rejects(broken,/Fixture Decky WebSocket failed/);
assert.equal(sockets.length,1);
''')
        self.assertEqual([v['outcome'] for v in result['records']],
                         ['timed-out', 'rejected', 'transport-error'])

    def test_shared_socket_close_rejects_every_pending_call_without_retry(self):
        result = self.run_fixture(r'''
const calls=[context.DeckyBackend.call('loader/get_plugins'),
 context.DeckyBackend.call('loader/get_plugins')];open(sockets[0]);sockets[0].close();
for(const call of calls)await assert.rejects(call,/Fixture Decky WebSocket failed/);
await assert.rejects(context.DeckyBackend.call('loader/get_plugins'),/Fixture Decky WebSocket failed/);
assert.equal(sockets.length,1);assert(timers.every(timer=>timer.cleared));
''')
        self.assertTrue(all(v['outcome'] == 'transport-error' for v in result['records']))

    def test_trace_capacity_never_drops_or_blocks_actual_rpc_calls(self):
        result = self.run_fixture(r'''
const calls=[];for(let i=0;i<501;i++)calls.push(context.DeckyBackend.call('loader/get_plugins'));
assert.equal(sockets.length,1);open(sockets[0]);const messages=sockets[0].sent.filter(message=>message.type===0);
assert.equal(messages.length,501);assert.equal(new Set(messages.map(m=>m.id)).size,501);
for(const message of messages.toReversed())answer(sockets[0],message.id,1,'private-response');
assert.equal((await Promise.all(calls)).length,501);
''')
        self.assertEqual(len(result['records']), 500)
        self.assertTrue(result['overflow'])
