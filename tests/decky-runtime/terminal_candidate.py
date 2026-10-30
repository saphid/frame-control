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
    # Decky 3.3.0's EOF listener can starve the event loop after the
    # parent closes the plugin socket. Keep owned cleanup synchronous
    # inside this private candidate; never signal or reap another PID.
    replacement = """    async def shutdown(self):
        import time
        decky.logger.info("FRAMEY_SHUTDOWN_BEGIN")
        self._kill_process()
        if self.process is not None:
            deadline = time.monotonic()+3
            while True:
                try:
                    waited, _status = os.waitpid(self.process.pid, os.WNOHANG)
                except ChildProcessError:
                    waited = self.process.pid
                if waited == self.process.pid:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Owned child not reaped before unload deadline")
                time.sleep(0.01)
        decky.logger.info("FRAMEY_SHUTDOWN_REAPED")"""
    terminal.write_text(terminal.read_text().replace(original, replacement))

    with (plugin/'main.py').open('a') as main:
        main.write('''
import sys as _framey_sys, os as _framey_os, json as _framey_json
from pathlib import Path as _framey_Path
from framey_terminal_stdlib import termios as _framey_termios
_framey_Path('/home/tester/terminal-candidate-abi.json').write_text(_framey_json.dumps(dict(
    versionInfo=list(_framey_sys.version_info), cacheTag=_framey_sys.implementation.cache_tag,
    architecture=_framey_os.uname().machine, termiosPath=_framey_termios.__file__)))
''')

    return dict(developmentOnly=True, installedByProduction=False,
                architecture=arch, dependencies=expected,
                patchedSourceSha256={str(p.relative_to(plugin)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(plugin.rglob('*')) if p.is_file()})
