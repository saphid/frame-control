"""Terminal failure observations never change RPC results or startup gates."""
import ast
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def helpers():
    path = ROOT/'tests/decky-runtime/terminal_lifecycle.py'
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    import time
    scope = dict(json=json, time=time, asyncio=asyncio, Path=Path)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return scope


def observer():
    path = ROOT/'tests/decky-runtime/terminal_candidate.py'
    spec = importlib.util.spec_from_file_location('terminal_connection_observer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scope = {}
    exec(compile(module.STARTUP_DIAGNOSTICS, 'terminal-connection-observer', 'exec'), scope)
    return scope


class TerminalConnectionObservation(unittest.TestCase):
    def test_connection_and_dispatch_hooks_preserve_arguments_results_and_errors(self):
        scope = observer()
        calls = []
        connection_result, dispatch_result = object(), object()
        failure = RuntimeError('private message body')
        class Socket:
            async def setup_server(self, callback):
                calls.append(('setup', callback))
                return connection_result
            async def _listen_for_method_call(self, reader, writer):
                calls.append(('connection', reader, writer))
                return connection_result
        class Sandbox:
            async def on_new_message(self, line):
                calls.append(('dispatch', line))
                if line is failure:
                    raise failure
                return dispatch_result
        def imported(name):
            if name == 'decky_loader.localplatform.localsocket':
                return SimpleNamespace(UnixSocket=Socket)
            self.assertEqual(name, 'decky_loader.plugin.sandboxed_plugin')
            return SimpleNamespace(SandboxedPlugin=Sandbox)
        output = io.StringIO()
        with patch.object(scope['importlib'], 'import_module', imported), redirect_stdout(output):
            scope['begin']()
            first = (Socket.setup_server, Socket._listen_for_method_call, Sandbox.on_new_message)
            scope['begin']()
            self.assertEqual(first, (Socket.setup_server, Socket._listen_for_method_call, Sandbox.on_new_message))
            self.assertIs(asyncio.run(Socket().setup_server('private callback')), connection_result)
            self.assertIs(asyncio.run(Socket()._listen_for_method_call('private reader', 'private writer')), connection_result)
            self.assertIs(asyncio.run(Sandbox().on_new_message('private line')), dispatch_result)
            with self.assertRaises(RuntimeError) as caught:
                asyncio.run(Sandbox().on_new_message(failure))
            self.assertIs(caught.exception, failure)
        events = [json.loads(line.split('=', 1)[1]) for line in output.getvalue().splitlines()]
        phases = [event['phase'] for event in events]
        self.assertEqual(phases.count('socket-connection-accepted'), 1)
        self.assertEqual(phases.count('message-received'), 2)
        self.assertIn('message-received-error', phases)
        self.assertNotIn('private', output.getvalue())
        self.assertEqual(calls[:3], [('setup', 'private callback'), ('connection', 'private reader', 'private writer'), ('dispatch', 'private line')])

    def test_connection_cancellation_is_propagated(self):
        scope = observer()
        failure = asyncio.CancelledError()
        async def original(reader, writer):
            raise failure
        wrapped = scope['wrap'](original, 'socket-connection-accepted', 'socket-connection-closed')
        output = io.StringIO()
        async def run():
            with self.assertRaises(asyncio.CancelledError) as caught:
                await wrapped('reader', 'writer')
            self.assertIs(caught.exception, failure)
        with redirect_stdout(output):
            asyncio.run(run())
        self.assertIn('socket-connection-accepted-error', output.getvalue())

    def test_preexisting_handled_event_is_observed_without_claiming_it_happened_after_timeout(self):
        scope = helpers()
        event = dict(phase='message-handled', pid=17, monotonicNs=1)
        scope['startup_events'] = lambda _: dict(events=[event])
        report = scope['observe_initial_timeout'](None, SimpleNamespace(poll=lambda: None))
        self.assertEqual(report['stopReason'], 'message-handled-observed')
        self.assertLess(event['monotonicNs'], report['startedMonotonicNs'])
        self.assertFalse(report['qualificationPassed'])
        self.assertFalse(report['newRpcIssued'])
        self.assertTrue(report['originalFailureRetained'])

    def test_absent_events_stop_at_existing_observation_budget_and_parent_exit_stops_early(self):
        for exited in (False, True):
            with self.subTest(exited=exited):
                scope = helpers()
                now = [1_000_000_000]
                sleeps = []
                def sleep(seconds):
                    sleeps.append(seconds)
                    now[0] += round(seconds*1_000_000_000)
                scope['time'] = SimpleNamespace(monotonic_ns=lambda: now[0], sleep=sleep)
                scope['startup_events'] = lambda _: dict(events=[])
                report = scope['observe_initial_timeout'](None, SimpleNamespace(poll=lambda: 0 if exited else None))
                self.assertLessEqual(now[0]-1_000_000_000, 2_500_000_000)
                self.assertEqual(report['stopReason'], 'parent-exited' if exited else 'observation-deadline')
                self.assertEqual(sum(round(seconds*1_000_000_000) for seconds in sleeps),
                                 0 if exited else 2_500_000_000)
                self.assertFalse(report['qualificationPassed'])

    def test_failure_observation_error_does_not_replace_or_retry_original_first_rpc_timeout(self):
        scope = helpers()
        failure = asyncio.TimeoutError('original private timeout')
        calls = []
        class Client:
            sequence = 0
            def __init__(self, name, transcript): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *_): calls.append('close')
            async def call(self, method):
                calls.append(method)
                self.sequence += 1
                raise failure
        def observe(*_):
            self.assertEqual(calls, ['get_terminals', 'close'])
            raise ValueError('private diagnostic error')
        scope.update(Client=Client, os=SimpleNamespace(getuid=lambda: 1100),
                     sys=SimpleNamespace(stderr=io.StringIO()),
                     startup_events=lambda _: dict(events=[]), observe_initial_timeout=observe)
        with patch.object(Path, 'exists', return_value=False):
            with self.assertRaises(asyncio.TimeoutError) as caught:
                scope['probe']('private fixture', Path('/home/tester'), SimpleNamespace(pid=17, poll=lambda: None), [])
        self.assertIs(caught.exception, failure)
        self.assertEqual(calls, ['get_terminals', 'close'])
        output = scope['sys'].stderr.getvalue()
        self.assertNotIn('private diagnostic error', output)
        line = next(line for line in output.splitlines() if line.startswith('FRAMEY_TERMINAL_LATE_CONNECTION_JSON='))
        report = json.loads(line.split('=', 1)[1])
        self.assertEqual(report['unavailable'], 'ValueError')
        self.assertFalse(report['qualificationPassed'])
        self.assertFalse(report['newRpcIssued'])
        self.assertTrue(report['originalFailureRetained'])


if __name__ == '__main__':
    unittest.main()
