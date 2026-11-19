"""Passive startup observations cannot change the operation they measure."""
import ast
import asyncio
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def candidate():
    path = ROOT/'tests/decky-runtime/terminal_candidate.py'
    spec = importlib.util.spec_from_file_location('terminal_startup_candidate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lifecycle_helpers():
    path = ROOT/'tests/decky-runtime/terminal_lifecycle.py'
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name in ('startup_events', 'timed_call')]
    import time
    scope = dict(json=json, time=time)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return scope


class TerminalStartupObserver(unittest.TestCase):
    def helper(self):
        scope = {}
        exec(compile(candidate().STARTUP_DIAGNOSTICS, 'generated-terminal-observer', 'exec'), scope)
        return scope

    def test_wrappers_preserve_arguments_results_and_socket_setup(self):
        scope = self.helper()
        seen = []
        marker = object()
        async def original(*args, **kwargs):
            seen.append((args, kwargs))
            return marker
        observed = scope['wrap'](original, 'socket-setup-started', 'socket-listening')
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertIs(asyncio.run(observed('callback', limit=17)), marker)
        self.assertEqual(seen, [(('callback',), dict(limit=17))])
        events = [json.loads(line.split('=', 1)[1]) for line in output.getvalue().splitlines()]
        self.assertEqual([event['phase'] for event in events],
                         ['socket-setup-started', 'socket-listening'])
        self.assertLessEqual(events[0]['monotonicNs'], events[1]['monotonicNs'])
        self.assertEqual(events[0]['pid'], events[1]['pid'])

    def test_plugin_hooks_keep_migration_main_and_method_behavior(self):
        scope = self.helper()
        results = [object(), object(), object()]
        class Plugin:
            async def _migration(self): return results[0]
            async def _main(self): return results[1]
            async def get_terminals(self): return results[2]
        output = io.StringIO()
        with redirect_stdout(output):
            scope['loaded'](Plugin)
            instance = Plugin()
            self.assertIs(asyncio.run(instance._migration()), results[0])
            self.assertIs(asyncio.run(instance._main()), results[1])
            self.assertIs(asyncio.run(instance.get_terminals()), results[2])
        phases = [json.loads(line.split('=', 1)[1])['phase'] for line in output.getvalue().splitlines()]
        self.assertEqual(phases, ['module-import-finished', 'migration-started', 'migration-finished',
                                 'main-started', 'main-finished', 'get-terminals-started', 'get-terminals-finished'])

    def test_error_and_cancellation_propagate_without_argument_or_error_text(self):
        for error in (RuntimeError('private fixture error body'), asyncio.CancelledError()):
            with self.subTest(error=type(error).__name__):
                scope = self.helper()
                async def original(value): raise error
                observed = scope['wrap'](original, 'migration-started', 'migration-finished')
                output = io.StringIO()
                async def check_propagation():
                    # Python 3.9's Task.result() replaces cancellation errors.
                    # Check the observer directly, before the runner boundary.
                    with self.assertRaises(type(error)) as caught:
                        await observed('private fixture argument')
                    self.assertIs(caught.exception, error)
                with redirect_stdout(output):
                    asyncio.run(check_propagation())
                self.assertNotIn('private fixture', output.getvalue())
                event = json.loads(output.getvalue().splitlines()[-1].split('=', 1)[1])
                self.assertEqual(event['phase'], 'migration-started-error')
                self.assertEqual(event['errorType'], type(error).__name__)


class TerminalRpcTiming(unittest.TestCase):
    def test_request_is_visible_while_pending_and_original_reply_is_preserved(self):
        call = lifecycle_helpers()['timed_call']
        timings = []
        marker = object()
        async def run():
            entered, release = asyncio.Event(), asyncio.Event()
            async def backend(method, *args):
                self.assertEqual((method, args), ('get_terminals', ('private argument',)))
                entered.set()
                await release.wait()
                return marker
            client = SimpleNamespace(sequence=6, call=backend)
            task = asyncio.create_task(call(client, 'get_terminals', ('private argument',), timings))
            await entered.wait()
            self.assertEqual(timings[0]['outcome'], 'pending')
            self.assertEqual(timings[0]['requestId'], 7)
            self.assertNotIn('finishedMonotonicNs', timings[0])
            release.set()
            self.assertIs(await task, marker)
        asyncio.run(run())
        self.assertEqual(timings[0]['outcome'], 'succeeded')
        self.assertGreaterEqual(timings[0]['finishedMonotonicNs'], timings[0]['startedMonotonicNs'])
        self.assertNotIn('private argument', json.dumps(timings))

    def test_timeout_stays_failed_and_is_not_retried(self):
        call = lifecycle_helpers()['timed_call']
        timings, attempts = [], []
        failure = TimeoutError('private fixture timeout')
        async def backend(method):
            attempts.append(method)
            raise failure
        with self.assertRaises(TimeoutError) as caught:
            asyncio.run(call(SimpleNamespace(sequence=0, call=backend), 'get_terminals', (), timings))
        self.assertIs(caught.exception, failure)
        self.assertEqual(attempts, ['get_terminals'])
        self.assertEqual(timings[0]['outcome'], 'failed')
        self.assertEqual(timings[0]['errorType'], 'TimeoutError')
        self.assertNotIn('private fixture timeout', json.dumps(timings))

    def test_full_diagnostic_buffer_does_not_block_the_next_operation(self):
        call = lifecycle_helpers()['timed_call']
        timings = [dict(previous=True)]*64
        async def backend(method): return 'original result'
        self.assertEqual(asyncio.run(call(SimpleNamespace(sequence=64, call=backend),
                                         'get_terminals', (), timings)), 'original result')
        self.assertEqual(len(timings), 64)

    def test_log_reader_bounds_records_and_discards_other_plugin_output(self):
        read = lifecycle_helpers()['startup_events']
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'runtime.log'
            lines = ['x'*70000, 'FRAMEY_TERMINAL_STARTUP_JSON={']
            for i in range(20):
                event = dict(phase='migration-'+str(i), pid=42, monotonicNs=i,
                             privateValue='never retain this field')
                lines.append('FRAMEY_TERMINAL_STARTUP_JSON='+json.dumps(event))
            path.write_text('\n'.join(lines)+'\n')
            report = read(path)
        self.assertTrue(report['logTailTruncated'])
        self.assertTrue(report['eventsTruncated'])
        self.assertTrue(report['incompleteRecord'])
        self.assertEqual(len(report['events']), 16)
        self.assertEqual(report['events'][0]['phase'], 'migration-4')
        self.assertNotIn('never retain', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
