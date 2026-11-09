#!/usr/bin/env python3
"""Controlled Decky parent EOF reproduction; never contacts a headset.

Execute only the digest-pinned UnixSocket class and parent listener from
Decky 3.3.0. Each control owns its Python child and private Unix socket.
This diagnostic cannot establish the historical ARM64 shutdown cause.
"""
import argparse
import ast
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from typing import Any, Callable, Coroutine


COMMIT = '67196adfa9b299f20dfb0cc932e88a169417b7d5'
SOURCES = {
    'parent': ('backend/decky_loader/plugin/plugin.py',
               'a15487dabf4ac402c13b01c5673dc41ff7bef119103c2f7b21957eb1ab1e2214'),
    'socket': ('backend/decky_loader/localplatform/localsocket.py',
               'cbc62b1f142df0678de0996c00214c0e0fd9cce35cc032daaa40717e49710138'),
}


def verified_source(path, kind):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCES[kind][1]:
        raise ValueError('Unexpected pinned '+kind+' source digest')
    return ast.parse(raw)


def load_probe(parent, socket):
    """Keep upstream framing/listener code intact; skip module initialization."""
    parent_tree = verified_source(parent, 'parent')
    socket_tree = verified_source(socket, 'socket')
    unix = next(n for n in socket_tree.body
                if isinstance(n, ast.ClassDef) and n.name == 'UnixSocket')
    wrapper = next(n for n in parent_tree.body
                   if isinstance(n, ast.ClassDef) and n.name == 'PluginWrapper')
    listener = next(n for n in wrapper.body
                    if isinstance(n, ast.AsyncFunctionDef) and n.name == '_response_listener')
    scope = dict(asyncio=asyncio, time=time, Any=Any, Callable=Callable,
                 Coroutine=Coroutine, BUFFER_LIMIT=2**20,
                 CancelledError=asyncio.CancelledError, create_task=asyncio.create_task,
                 loads=json.loads,
                 SocketMessageType=SimpleNamespace(EVENT=SimpleNamespace(value=0),
                                                   RESPONSE=SimpleNamespace(value=1)))
    exec(compile(ast.Module(body=[unix], type_ignores=[]), str(socket), 'exec'), scope)
    exec(compile(ast.Module(body=[listener], type_ignores=[]), str(parent), 'exec'), scope)
    return scope


async def child_probe(scope, mode, address):
    writers = []
    peer_ready = asyncio.Event()
    peer_closed = asyncio.Event()

    async def peer(reader, writer):
        writers.append(writer)
        peer_ready.set()
        if mode == 'eof':
            writer.close()
            await writer.wait_closed()
            print('unix-peer-closed', flush=True)
            peer_closed.set()

    owned = scope['UnixSocket']()
    owned.socket_addr = address
    server = await asyncio.start_unix_server(peer, path=address, limit=2**20)
    obj = SimpleNamespace(_socket=owned, log=SimpleNamespace(info=lambda *a: None),
                          _method_call_requests={},
                          get_display_name=lambda: 'private parent EOF diagnostic')
    listener = asyncio.create_task(scope['_response_listener'](obj))
    await peer_ready.wait()
    if mode == 'eof':
        await peer_closed.wait()
        await asyncio.sleep(.025)
        print('after-eof-heartbeat', flush=True)
    else:
        await asyncio.sleep(.025)
        print('connected-heartbeat', flush=True)
        listener.cancel()
        try:
            await listener
        except asyncio.CancelledError:
            print('cancel-propagated', flush=True)
        assert owned.active is False
        for writer in writers:
            writer.close()
            await writer.wait_closed()
        server.close()
        await server.wait_closed()
        print('owned-socket-cleaned', flush=True)


def run_control(args, mode, address):
    command = [sys.executable, str(Path(__file__).resolve()),
               '--parent-source', str(args.parent_source.resolve()),
               '--socket-source', str(args.socket_source.resolve()),
               '--child', mode, '--address', address]
    # This child starts no subprocesses. communicate() drains the private pipes;
    # on deadline, kill and reap exactly the Popen child before removing its socket.
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        timed_out = False
        try:
            stdout, stderr = child.communicate(timeout=args.budget_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            child.kill()
            stdout, stderr = child.communicate(timeout=5)
        return dict(mode=mode, returncode=child.returncode, timedOut=timed_out,
                    stdout=stdout.decode(errors='replace'),
                    stderr=stderr.decode(errors='replace'), ownedProcessReaped=child.poll() is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-source', type=Path, required=True)
    parser.add_argument('--socket-source', type=Path, required=True)
    parser.add_argument('--budget-seconds', type=float, default=3)
    parser.add_argument('--child', choices=['cancel', 'eof'], help=argparse.SUPPRESS)
    parser.add_argument('--address', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error('the pinned upstream annotations require Python 3.10 or later')
    if not 2 <= args.budget_seconds <= 10:
        parser.error('budget must be between 2 and 10 seconds')
    scope = load_probe(args.parent_source, args.socket_source)
    if args.child:
        if not args.address:
            parser.error('private child needs its owned socket address')
        asyncio.run(child_probe(scope, args.child, args.address))
        return 0

    with tempfile.TemporaryDirectory(prefix='framey-parent-eof-') as folder:
        modes = ['cancel', 'eof']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda mode: run_control(args, mode, str(Path(folder)/(mode+'.sock'))), modes))
    cancel, eof = results
    control = (cancel['returncode'] == 0 and not cancel['timedOut'] and
               all(marker in cancel['stdout'] for marker in
                   ['connected-heartbeat', 'cancel-propagated', 'owned-socket-cleaned']))
    reproduced = (eof['timedOut'] and 'unix-peer-closed' in eof['stdout'] and
                  'after-eof-heartbeat' not in eof['stdout'])
    report = dict(schema=1, sourceCommit=COMMIT,
                  sourceSha256={kind: spec[1] for kind, spec in SOURCES.items()},
                  diagnosticSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  results=results, connectedCancellationControlPassed=control,
                  controlledParentEofStarvationReproduced=reproduced,
                  userSpaceStackCaptured=False, stackSamplingEnabled=False,
                  allOwnedProcessesReaped=all(r['ownedProcessReaped'] for r in results),
                  realFrameContacted=False, architecture=platform.machine(),
                  arm64Executed=platform.machine().lower() in ('aarch64', 'arm64'),
                  historicalArm64VmExecuted=False,
                  historicalCauseEstablished=False, releaseHoldCleared=False,
                  limit='Controlled local Unix EOF only; no historical failure or real-headset proof.')
    print(json.dumps(report, indent=2))
    return 0 if control and reproduced and report['allOwnedProcessesReaped'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
