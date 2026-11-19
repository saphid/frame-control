"""Exercise the VM browser's actual startup loop without a browser or headset."""
import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class BrowserReadiness(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).parent/'decky-runtime/syncthing_browser.py'
        tree = ast.parse(source.read_text())
        exercise = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'exercise')
        block = next(n for n in ast.walk(exercise) if isinstance(n, ast.With)
                     and any(isinstance(s, ast.While) for s in n.body))
        start = next(i for i, n in enumerate(block.body) if isinstance(n, ast.Assign)
                     and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'deadline')
        end = next(i for i, n in enumerate(block.body[start:], start) if isinstance(n, ast.Assert))
        wrapper = ast.parse('def wait(browser, profile, report):\n page = None\n pending_pages = []\n return page').body[0]
        wrapper.body[2:2] = block.body[start:end+1]
        self.now = 0
        self.on_sleep = lambda: None
        def sleep(seconds):
            self.now += seconds
            self.on_sleep()
        self.backend = SimpleNamespace(Fail=RuntimeError, Page=Mock())
        scope = dict(time=SimpleNamespace(monotonic=lambda: self.now, sleep=sleep),
                     frame_steam=self.backend, bridge_started=0, clock={})
        helpers = [n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == 'ready_page']
        exec(compile(ast.fix_missing_locations(ast.Module(body=helpers+[wrapper], type_ignores=[])),
                     str(source), 'exec'), scope)
        self.wait = scope['wait']
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.profile = Path(self.temporary.name)
        self.port = self.profile/'DevToolsActivePort'
        self.browser = Mock(poll=lambda: None)
        self.report = {'startupClock': scope['clock']}

    def ready_page(self):
        page = Mock()
        page.eval.return_value = dict(ready=True)
        self.backend.Page.return_value = page
        return page

    def test_empty_port_file_is_retried_until_chromium_publishes_port(self):
        self.port.touch()
        page = self.ready_page()
        self.on_sleep = lambda: self.port.write_text('12345\nfixture')
        self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        self.assertGreater(self.now, 0)
        self.assertEqual(self.report['startupClock']['readinessDeadlineAfterSeconds'], 60)
        self.assertTrue(self.report['startupClock']['readinessPassed'])
        self.assertEqual(self.backend.CDP, 'http://127.0.0.1:12345/json')
        self.backend.Page.assert_called_once()

    def test_file_disappearing_during_read_is_retried(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        with patch.object(Path, 'read_text', side_effect=[FileNotFoundError('port moved'), '12345\nfixture']):
            self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        self.assertEqual(self.report['lastReadinessError'], 'port moved')
        self.assertGreater(self.now, 0)

    def test_permanently_empty_file_keeps_bounded_readiness_failure(self):
        self.port.touch()
        with self.assertRaisesRegex(AssertionError, 'Browser CDP/panel readiness unavailable'):
            self.wait(self.browser, self.profile, self.report)
        self.assertGreaterEqual(self.now, 60)
        self.assertLess(self.now, 61)
        self.assertEqual(self.report['startupClock']['readinessDeadlineAfterSeconds'], 60)
        self.assertFalse(self.report['startupClock']['readinessPassed'])
        self.assertGreaterEqual(self.report['startupClock']['readinessFinishedAfterSeconds'], 60)
        self.backend.Page.assert_not_called()

    def test_exited_browser_keeps_distinct_failure(self):
        self.browser.poll = lambda: 7
        self.browser.returncode = 7
        with self.assertRaisesRegex(RuntimeError, 'Sandboxed browser exited: 7'):
            self.wait(self.browser, self.profile, self.report)
        self.assertEqual(self.now, 0)

    def test_ready_probe_finishing_after_deadline_is_closed_and_rejected(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        def finish_late(_expression):
            self.now = 60.5
            return dict(ready=True)
        page.eval.side_effect = finish_late
        with self.assertRaisesRegex(AssertionError, 'Browser CDP/panel readiness unavailable'):
            self.wait(self.browser, self.profile, self.report)
        page.sock.close.assert_called_once()
        self.backend.Page.assert_called_once()
        self.assertFalse(self.report['startupClock']['readinessPassed'])
        self.assertEqual(self.report['startupClock']['readinessFinishedAfterSeconds'], 60.5)
        self.assertTrue(self.report['startupClock']['lateReadyPageRejected'])

    def test_ready_probe_finishing_at_deadline_is_accepted(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        def finish_at_deadline(_expression):
            self.now = 60
            return dict(ready=True)
        page.eval.side_effect = finish_at_deadline
        self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        page.sock.close.assert_not_called()
        self.assertTrue(self.report['startupClock']['readinessPassed'])

    def test_ready_probe_finishing_before_deadline_is_accepted(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        def finish_before_deadline(_expression):
            self.now = 59.9
            return dict(ready=True)
        page.eval.side_effect = finish_before_deadline
        self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        page.sock.close.assert_not_called()
        self.assertTrue(self.report['startupClock']['readinessPassed'])

    def test_incomplete_page_is_closed_before_ready_page_is_accepted(self):
        self.port.write_text('12345\nfixture')
        pending, ready = Mock(), Mock()
        pending.eval.side_effect = [dict(ready=False, errors=['loading'], state=None,
                                               documentState='loading', iframeAssigned=False),
                                    OSError('owned CDP connection closed')]
        ready.eval.return_value = dict(ready=True)
        self.backend.Page.side_effect = [RuntimeError('page not listed yet'), pending, ready]
        self.assertIs(self.wait(self.browser, self.profile, self.report), ready)
        pending.sock.close.assert_called_once()
        self.assertEqual(self.backend.Page.call_count, 3)
        ready.sock.close.assert_not_called()
        self.assertEqual(self.report['startupErrors'], ['loading'])
        self.assertEqual(self.report['startupState'], dict(state=None,
                         documentState='loading', iframeAssigned=False))
        attempts = self.report['readinessAttempts']
        self.assertEqual(attempts[0]['error'], 'page not listed yet')
        self.assertEqual(attempts[1]['outcome'], 'not-ready')
        self.assertNotIn('error', attempts[1])
        self.assertEqual(self.report['lastReadinessAttempt']['outcome'], 'ready')
        self.assertNotIn('error', self.report['lastReadinessAttempt'])

    def test_pending_connection_is_reused_until_its_page_becomes_ready(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        page.eval.side_effect = [dict(ready=False, errors=[], state=None,
            documentState='loading', iframeAssigned=False), dict(ready=True)]
        self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        self.backend.Page.assert_called_once()
        page.sock.close.assert_not_called()
        # The first pending snapshot and the accepted snapshot each use one
        # round trip; diagnostics must not add another startup evaluation.
        self.assertEqual(page.eval.call_count, 2)
        self.assertEqual([a['connectionReused'] for a in self.report['readinessAttempts']],
                         [False, True])

    def test_pending_connection_is_closed_once_when_readiness_expires(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        page.eval.return_value = dict(ready=False,
            errors=[], state=None, documentState='loading', iframeAssigned=False)
        with self.assertRaisesRegex(AssertionError, 'Browser CDP/panel readiness unavailable'):
            self.wait(self.browser, self.profile, self.report)
        self.backend.Page.assert_called_once()
        page.sock.close.assert_called_once()
        self.assertFalse(self.report['startupClock']['readinessPassed'])

    def test_reused_connection_cannot_accept_readiness_after_deadline(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        probes = 0
        def evaluate(expression):
            nonlocal probes
            probes += 1
            if probes == 1:
                return dict(ready=False, errors=[], state=None,
                            documentState='loading', iframeAssigned=False)
            self.now = 60.5
            return dict(ready=True)
        page.eval.side_effect = evaluate
        with self.assertRaisesRegex(AssertionError, 'Browser CDP/panel readiness unavailable'):
            self.wait(self.browser, self.profile, self.report)
        self.backend.Page.assert_called_once()
        page.sock.close.assert_called_once()
        self.assertFalse(self.report['startupClock']['readinessPassed'])
        self.assertTrue(self.report['startupClock']['lateReadyPageRejected'])
        self.assertTrue(self.report['lastReadinessAttempt']['connectionReused'])


    def execute_snapshot_javascript(self, expression, *, initial_ready=False, event='ready'):
        import json
        import shutil
        import subprocess
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node is unavailable')
        script = r"""
const vm=require('node:vm');
const handlers=new Set();
let budgetExpired=false;
const context={ready:INITIAL_READY,startupErrors:[],startupEvents:[],
 startupState:{readyMessages:INITIAL_READY?1:0},
 document:{readyState:'complete',getElementById:()=>({getAttribute:()=>'/panel'})},
 setTimeout:(fn,ms)=>setTimeout(()=>{if(ms>20)budgetExpired=true;fn();},ms),clearTimeout,queueMicrotask,
 addEventListener:(type,fn)=>{if(type==='message')handlers.add(fn);},
 removeEventListener:(type,fn)=>{if(type==='message')handlers.delete(fn);}};
context.window=context;
const event=EVENT;
const timer=event==='never'?null:setTimeout(async ()=>{
 if(event==='ready'){context.ready=true;context.startupState.readyMessages++;}
 for(const fn of handlers){
  fn({data:{type:'framey:ready'}});
  if(event==='browser-handler-after')await Promise.resolve();
 }
 if(event==='handler-after'||event==='browser-handler-after'){context.ready=true;context.startupState.readyMessages++;}
},10);
(async()=>{
 const value=await vm.runInNewContext(EXPRESSION,context);
 if(timer!==null)clearTimeout(timer);
 console.log(JSON.stringify({value,remainingMessageListeners:handlers.size,budgetExpired}));
})().catch(error=>{console.error(error);process.exitCode=1;});
""".replace('INITIAL_READY', json.dumps(initial_ready)).replace('EVENT', json.dumps(event)).replace('EXPRESSION', json.dumps(expression))
        result = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response['remainingMessageListeners'], 0)
        if event == 'browser-handler-after':
            self.assertFalse(response['budgetExpired'],
                             'native listener checkpoints must not delay readiness until budget expiry')
        return response['value']

    def load_readiness_probe(self):
        source = Path(__file__).parent/'decky-runtime/syncthing_browser.py'
        node = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'ready_page')
        scope = dict(time=SimpleNamespace(monotonic=lambda: self.now), frame_steam=self.backend)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
        return scope['ready_page']

    def test_async_ready_message_needs_only_one_cdp_evaluation(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        page.sock.gettimeout.return_value = 5
        page.eval.side_effect = lambda expression: self.execute_snapshot_javascript(
            expression, initial_ready=self.now >= .2)
        self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        self.assertEqual(page.eval.call_count, 1,
                         'asynchronous readiness must not require repeated CDP evaluations')
        self.assertEqual(page.sock.settimeout.call_args_list[-1].args, (5,))
        self.assertEqual(self.report['startupClock']['readinessDeadlineAfterSeconds'], 60)

    def test_browser_wait_expires_without_promoting_an_unready_page(self):
        page = self.ready_page()
        page.sock.gettimeout.return_value = 5
        page.eval.side_effect = lambda expression: self.execute_snapshot_javascript(expression, event='never')
        report, pending = {}, []
        probe = self.load_readiness_probe()
        self.assertIsNone(probe(report, clock_start=0, pending=pending, deadline=.02))
        self.assertEqual(pending, [page])
        self.assertEqual(page.eval.call_count, 1)
        self.assertFalse(report['startupState']['state']['readyMessages'])
        self.assertEqual(page.sock.settimeout.call_args_list[0].args, (.02,))
        self.assertEqual(page.sock.settimeout.call_args_list[-1].args, (5,))
        page.sock.close.assert_not_called()

    def test_message_without_ready_state_cannot_promote_a_page(self):
        page = self.ready_page()
        page.sock.gettimeout.return_value = 5
        page.eval.side_effect = lambda expression: self.execute_snapshot_javascript(expression, event='progress-only')
        report, pending = {}, []
        self.assertIsNone(self.load_readiness_probe()(report, pending=pending, deadline=.02))
        self.assertEqual(report['lastReadinessAttempt']['outcome'], 'not-ready')
        self.assertEqual(report['startupState']['state']['readyMessages'], 0)
        self.assertEqual(page.eval.call_count, 1)
        self.assertEqual(pending, [page])


    def test_ready_handler_running_after_wait_listener_is_observed_after_dispatch(self):
        page = self.ready_page()
        page.sock.gettimeout.return_value = 5
        page.eval.side_effect = lambda expression: self.execute_snapshot_javascript(expression, event='handler-after')
        report, pending = {}, []
        self.assertIs(self.load_readiness_probe()(report, pending=pending, deadline=.1), page)
        self.assertEqual(report['lastReadinessAttempt']['browserEventWaitBudgetSeconds'], .1)
        self.assertEqual(page.eval.call_count, 1)
        page.sock.close.assert_not_called()


    def test_native_checkpoint_before_later_parent_listener_does_not_miss_readiness(self):
        page = self.ready_page()
        page.sock.gettimeout.return_value = 5
        page.eval.side_effect = lambda expression: self.execute_snapshot_javascript(
            expression, event='browser-handler-after')
        report, pending = {}, []
        self.assertIs(self.load_readiness_probe()(report, pending=pending, deadline=.1), page)
        self.assertEqual(page.eval.call_count, 1)
        page.sock.close.assert_not_called()

    def test_wait_transport_error_restores_timeout_and_closes_only_owned_candidate(self):
        page = self.ready_page()
        page.sock.gettimeout.return_value = 5
        page.eval.side_effect = OSError('owned wait transport closed')
        report, pending = {}, []
        self.assertIsNone(self.load_readiness_probe()(report, pending=pending, deadline=.1))
        self.assertEqual(report['lastReadinessAttempt']['outcome'], 'failure')
        self.assertEqual(page.sock.settimeout.call_args_list[0].args, (.1,))
        self.assertEqual(page.sock.settimeout.call_args_list[-1].args, (5,))
        self.assertEqual(pending, [])
        page.sock.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
