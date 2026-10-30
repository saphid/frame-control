"""The optional HTTP gateway must stay inside its marked disposable VM."""
import importlib.util
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
