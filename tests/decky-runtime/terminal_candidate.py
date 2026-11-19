"""Test-only Terminal candidate; never called by production installation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path('/repo')
DEPENDENCIES = {
    'x86_64': ('amd', 'python@sha256:ddec44f5ab04dd68aaee83d7dc9831c964a4bb9e950c89960e60760373fbf54f', 62),
    'aarch64': ('arm', 'python@sha256:eaecc1a821ac5f032c7cc29d6fdd2cca4199ca97f8d11ea79417e9f647dbd809', 183),
}

# Generated only inside the disposable Terminal candidate. Do not change the
# parent loader, await conditions, method results or timeout budgets.
STARTUP_DIAGNOSTICS = r'''
import functools
import importlib
import json
import os
import time

_events = 0

def record(phase, error=None):
    global _events
    if _events >= 64:
        return
    _events += 1
    event = dict(phase=phase, pid=os.getpid(), monotonicNs=time.monotonic_ns())
    if error is not None:
        event['errorType'] = type(error).__name__
    try:
        print('FRAMEY_TERMINAL_STARTUP_JSON='+json.dumps(event), flush=True)
    except OSError:
        pass

def wrap(original, started, finished):
    @functools.wraps(original)
    async def observed(*args, **kwargs):
        record(started)
        try:
            result = await original(*args, **kwargs)
        except BaseException as error:
            record(started+'-error', error)
            raise
        record(finished)
        return result
    observed._framey_startup_observer = True
    return observed

def begin():
    record('module-import-started')
    socket = importlib.import_module('decky_loader.localplatform.localsocket').UnixSocket
    if not getattr(socket.setup_server, '_framey_startup_observer', False):
        socket.setup_server = wrap(socket.setup_server, 'socket-setup-started', 'socket-listening')
    if not getattr(socket._listen_for_method_call, '_framey_startup_observer', False):
        socket._listen_for_method_call = wrap(socket._listen_for_method_call,
            'socket-connection-accepted', 'socket-connection-closed')
    sandbox = importlib.import_module('decky_loader.plugin.sandboxed_plugin').SandboxedPlugin
    if not getattr(sandbox.on_new_message, '_framey_startup_observer', False):
        sandbox.on_new_message = wrap(sandbox.on_new_message, 'message-received', 'message-handled')

def loaded(plugin):
    record('module-import-finished')
    for method, phase in (('_migration', 'migration'), ('_main', 'main'),
                          ('get_terminals', 'get-terminals')):
        original = getattr(plugin, method, None)
        if callable(original):
            setattr(plugin, method, wrap(original, phase+'-started', phase+'-finished'))
'''


def apply(plugin, record):
    assert record['id'] == 65 and sys.platform == 'linux'
    arch = os.uname().machine
    suffix, image, machine = DEPENDENCIES[arch]
    inputs = ROOT/f'tests/fixtures/framey-terminal-python314-{suffix}'
    expected = json.loads((inputs/'source.json').read_text())
    assert expected['image'] == image
    for name, digest in expected['files'].items():
        assert hashlib.sha256((inputs/name).read_bytes()).hexdigest() == digest
    package = plugin/'py_modules/framey_terminal_stdlib'
    assert not package.exists()
    package.mkdir()
    (package/'__init__.py').write_text('')
    extension = f'termios.cpython-314-{arch}-linux-gnu.so'
    binary = (inputs/extension).read_bytes()
    assert binary[:4] == b'\x7fELF' and int.from_bytes(binary[18:20], 'little') == machine
    for name in ('pty.py','tty.py','LICENSE',extension):
        shutil.copyfile(inputs/name, package/name)
    pty = package/'pty.py'
    pty.write_text(pty.read_text().replace('import tty\n','from . import tty\n')
                   .replace('from tty import ', 'from .tty import '))
    tty = package/'tty.py'
    tty.write_text(tty.read_text().replace('from termios import ', 'from .termios import '))
    terminal = plugin/'py_modules/decky_terminal/terminal.py'
    source = terminal.read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == '6324d71bfd1d74c06f8c45f4592eca16e84a0b8e2dd23de594353097d5b99238'
    terminal.write_text(source.replace('import pty\n','from framey_terminal_stdlib import pty\n')
                       .replace('import termios\n','from framey_terminal_stdlib import termios\n'))

    terminal = plugin/'py_modules/decky_terminal/terminal.py'
    source = terminal.read_text()
    assert source.count('await self.process.send_signal(signal.SIGWINCH)') == 1
    terminal.write_text(source.replace('await self.process.send_signal(signal.SIGWINCH)',
                                       'self.process.send_signal(signal.SIGWINCH)'))

    terminal = plugin/'py_modules/decky_terminal/terminal.py'
    lines = terminal.read_text().splitlines(keepends=True)
    rejected = [line for line in lines if '_write_stdin(f"' in line and '[8;' in line]
    assert len(rejected) == 1 and 'rows' in rejected[0] and 'cols' in rejected[0]
    terminal.write_text(''.join(line for line in lines if line not in rejected))

    source = plugin/'main.py'
    original = '    async def _unload(self):\n        pass'
    assert source.read_text().count(original) == 1
    source.write_text(source.read_text().replace(original,
        '    async def _unload(self):\n        await Plugin.decky_terminal._kill_all_terminals()'))
    terminal = plugin/'py_modules/decky_terminal/terminal.py'
    original = '    async def shutdown(self):\n        self._kill_process()'
    assert terminal.read_text().count(original) == 1
    # Let asyncio reap its own child; waitpid races the subprocess watcher.
    # The existing child-only IPC repair lets unload await without EOF starvation.
    replacement = """    async def shutdown(self):
        self._framey_closing = True
        self._kill_process()
        if self.process is not None:
            await asyncio.wait_for(self.process.wait(), timeout=3)
        tasks = getattr(self, "_framey_tasks", ())
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)"""
    text = terminal.read_text().replace(original, replacement)
    original = ('        asyncio.ensure_future(self._read_output_loop())\n'
                '        asyncio.ensure_future(self._process_subscriber())')
    assert text.count(original) == 1
    text = text.replace(original,
        '        self._framey_tasks = (asyncio.create_task(self._read_output_loop()),\n'
        '                              asyncio.create_task(self._process_subscriber()))')
    original = ('            except Exception as e:\n'
                '                decky.logger.exception("[terminal][EXCEPTION][%s] Exception during output read: %s", self.id, e)')
    assert text.count(original) == 1
    text = text.replace(original,
        '            except OSError as e:\n'
        '                if getattr(self, "_framey_closing", False) and e.errno in (5, 9):\n'
        '                    break\n'
        '                raise\n' + original)
    terminal.write_text(text)
    shutil.copyfile(ROOT/'ui/framey_decky_ipc.py', plugin/'py_modules/framey_decky_ipc.py')
    source = plugin/'main.py'
    source.write_text('from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                      '_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n' + source.read_text())

    with (plugin/'main.py').open('a') as main:
        main.write('''
import sys as _framey_sys, os as _framey_os, json as _framey_json
from pathlib import Path as _framey_Path
from framey_terminal_stdlib import termios as _framey_termios
_framey_Path('/home/tester/terminal-candidate-abi.json').write_text(_framey_json.dumps(dict(
    versionInfo=list(_framey_sys.version_info), cacheTag=_framey_sys.implementation.cache_tag,
    architecture=_framey_os.uname().machine, termiosPath=_framey_termios.__file__)))
''')

    (plugin/'py_modules/framey_terminal_startup.py').write_text(STARTUP_DIAGNOSTICS)
    source.write_text('from framey_terminal_startup import begin as _framey_startup_begin, loaded as _framey_startup_loaded\n'
                      '_framey_startup_begin()\n' + source.read_text() +
                      '\n_framey_startup_loaded(Plugin)\n'
                      'del _framey_startup_begin, _framey_startup_loaded\n')

    return dict(developmentOnly=True, installedByProduction=False,
                architecture=arch, dependencies=expected,
                patchedSourceSha256={str(p.relative_to(plugin)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(plugin.rglob('*')) if p.is_file()})
