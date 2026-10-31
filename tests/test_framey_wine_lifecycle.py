"""Managed Wine Cellar owns and reaps real children within Decky's plugin-stop deadline."""
import sandbox  # noqa: F401
import ast
import asyncio
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import types
import typing
import unittest

SOURCE = Path(__file__).resolve().parents[1]/'ui/vendor/wine-cellar-0.2.1/main.py'


def plugin_class():
    node = next(n for n in ast.parse(SOURCE.read_text()).body
                if isinstance(n, ast.ClassDef) and n.name == 'Plugin')
    scope = dict(asyncio=asyncio, subprocess=subprocess, time=time, socket=socket,
                 typing=typing, PLUGIN_DIR='', FrameySocket=types.SimpleNamespace(PORT=0),
                 logger=logging.getLogger('wine-lifecycle-test'))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), scope)
    return scope['Plugin']


@unittest.skipUnless(sys.platform == 'linux', 'owned Linux native helper lifecycle')
class WineLifecycle(unittest.IsolatedAsyncioTestCase):
    async def helper(self, ignore_term=False):
        temp = tempfile.TemporaryDirectory(prefix='wine-child-test-')
        self.addCleanup(temp.cleanup)
        path = Path(temp.name)/'helper'
        ready = Path(temp.name)/'ready'
        path.write_text('#!'+sys.executable+'\n'+
                        'import signal,time\nfrom pathlib import Path\n'+
                        ('signal.signal(signal.SIGTERM, signal.SIG_IGN)\n' if ignore_term else '')+
                        'Path('+repr(str(ready))+').write_text("ready")\n'+
                        'while True: time.sleep(.01)\n')
        path.chmod(0o700)
        cls = plugin_class()
        cls.BACKEND_PATH = str(path)
        await cls._spawn_backend()
        process = cls.BACKEND_PROC

        async def cleanup():
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 3)
        self.addAsyncCleanup(cleanup)
        deadline = time.monotonic()+3
        while not ready.exists():
            self.assertLess(time.monotonic(), deadline, 'owned helper readiness')
            await asyncio.sleep(.01)
        return cls, process

    def assert_reaped(self, process):
        self.assertIsNotNone(process.returncode)
        with self.assertRaises(ChildProcessError):
            os.waitpid(process.pid, os.WNOHANG)

    async def test_unload_reaps_the_exact_child_and_leaves_sibling_alive(self):
        cls, process = await self.helper()
        sibling = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(lambda: (sibling.kill(), sibling.wait(timeout=3)))
        # A concurrent waiter exercises the same shared child wait as the supervisor.
        task = asyncio.create_task(process.wait())
        cls.BACKEND_WATCH_TASK = task
        await cls._unload()
        self.assertEqual(process.returncode, -signal.SIGTERM)
        self.assert_reaped(process)
        self.assertIsNone(sibling.poll())
        self.assertTrue(task.done())
        self.assertIsNone(cls.BACKEND_PROC)
        self.assertIsNone(cls.BACKEND_WATCH_TASK)

    async def test_uncooperative_child_is_killed_and_reaped_inside_decky_budget(self):
        cls, process = await self.helper(ignore_term=True)
        started = time.monotonic()
        await cls._unload()
        self.assertLess(time.monotonic()-started, 4.5)
        self.assertEqual(process.returncode, -signal.SIGKILL)
        self.assert_reaped(process)

    async def test_supervisor_restarts_after_exit_then_unload_stops_replacement(self):
        cls, first = await self.helper()
        await cls._unload()
        cls.BACKEND_STOPPING = False
        cls.BACKEND_RESTART_DELAY_SECONDS = .01
        task = asyncio.create_task(cls._backend_supervisor())
        cls.BACKEND_WATCH_TASK = task
        processes = []
        try:
            deadline = time.monotonic()+3
            while cls.BACKEND_PROC is None:
                self.assertLess(time.monotonic(), deadline)
                await asyncio.sleep(.01)
            second = cls.BACKEND_PROC
            processes.append(second)
            second.terminate()
            while cls.BACKEND_PROC is second or cls.BACKEND_PROC is None:
                self.assertLess(time.monotonic(), deadline)
                await asyncio.sleep(.01)
            third = cls.BACKEND_PROC
            processes.append(third)
            await cls._unload()
            self.assertTrue(task.done())
            for process in [first, second, third]:
                self.assert_reaped(process)
        finally:
            cls.BACKEND_STOPPING = True
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            for process in processes:
                if process.returncode is None:
                    process.kill()
                await asyncio.wait_for(process.wait(), 3)
