"""Preserve shared shaders and apply only an explicit, bounded user selection."""
import asyncio
import os
from pathlib import Path
import stat
import tempfile

PROPERTY = 'GAMESCOPE_RESHADE_EFFECT'
MAX_SHADER = 8 * 1024 * 1024


def directory(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Shader directory must be absolute')
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        if not stat.S_ISDIR(current.lstat().st_mode):
            raise ValueError('Shader directory must not use symlinks')
    return path


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SHADER:
        raise ValueError('Expected a bounded regular shader file')


class Runtime:
    def __init__(self, namespace):
        self.ns = namespace
        self.destination = Path(namespace['destination_folder'])
        self.source = Path(namespace['shaders_folder'])
        self.lock = asyncio.Lock()
        self.closed = False
        self.process = None

    def deploy(self):
        directory(self.destination)
        if self.source.is_symlink():
            raise ValueError('Bundled shader directory must not be a symlink')
        for source in sorted(self.source.iterdir()):
            if source.suffix not in ('.fx', '.fxh'):
                continue
            regular(source)
            data = source.read_bytes()
            if len(data) > MAX_SHADER:
                raise ValueError('Shader grew while reading')
            # Publish complete bytes without replacing any existing name,
            # including symlinks, custom shaders and prior managed copies.
            with tempfile.NamedTemporaryFile(dir=self.destination, prefix='.frame-control-shader-') as stage:
                stage.write(data)
                stage.flush()
                os.fchmod(stage.fileno(), 0o644)
                try:
                    os.link(stage.name, self.destination/source.name)
                except FileExistsError:
                    pass

    def validate(self, name):
        if not isinstance(name, str) or not name or len(name) > 255 or any(ord(c) < 32 for c in name):
            raise ValueError('Choose an installed shader or disable it')
        if name == '0':
            return name
        if Path(name).name != name or Path(name).suffix != '.fx':
            raise ValueError('Choose an installed shader filename')
        directory(self.destination)
        regular(self.destination/name)
        return name

    async def reap(self):
        if self.process is None:
            return
        process, self.process = self.process, None
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.wait(), 1)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

    async def apply(self, name):
        self.validate(name)
        async with self.lock:
            if self.closed or not os.environ.get('DISPLAY'):
                return False
            try:
                self.process = await asyncio.create_subprocess_exec('xprop', '-root', '-f', PROPERTY,
                    '8u', '-set', PROPERTY, name, stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE)
                await asyncio.wait_for(self.process.communicate(), 2)
                return self.process.returncode == 0
            except (OSError, asyncio.TimeoutError):
                return False
            finally:
                await self.reap()


def install(namespace):
    runtime = Runtime(namespace)
    plugin = namespace['Plugin']

    async def main(self):
        # Startup deploys missing files, but must not clear an active effect.
        runtime.deploy()

    async def set_shader(self, shader_name):
        try:
            if await runtime.apply(shader_name):
                plugin._current = shader_name
                return True
        except (OSError, ValueError) as error:
            namespace['logger'].warning('Shader selection refused: %s', error)
        return False

    async def set_screensaver(self, shader_name):
        try:
            runtime.validate(shader_name)
            plugin._current_screensaver = shader_name
            return True
        except (OSError, ValueError) as error:
            namespace['logger'].warning('Screensaver selection refused: %s', error)
            return False

    async def apply_shader(self, screensaver):
        if type(screensaver) is not bool:
            return False
        name = plugin._current_screensaver if screensaver else plugin._current
        try:
            return await runtime.apply(name)
        except (OSError, ValueError) as error:
            namespace['logger'].warning('Shader selection refused: %s', error)
            return False

    async def unload(self):
        async with runtime.lock:
            runtime.closed = True
            await runtime.reap()
        # Retain shader files and the explicitly selected effect. No shared
        # file or compositor state belongs to the plugin to remove on unload.

    plugin._main = main
    plugin._unload = unload
    plugin.set_shader = set_shader
    plugin.set_screensaver = set_screensaver
    plugin.apply_shader = apply_shader
    namespace['_framey_reshadeck_runtime'] = runtime
