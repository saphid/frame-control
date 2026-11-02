"""Owned filter-chain lifetime for the exact Virtual Surround Sound 0.0.5 archive.

No systemd unit, shared HRIR, PID file, shell command or process-name cleanup.
The published filter graphs are retained; only their file path and node lifetime
are changed. PipeWire/Pulse remain the user's existing audio server.
"""
import asyncio
from contextlib import suppress
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

MAX_HRIR = 8 * 1024 * 1024


def read_file(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Expected a bounded regular audio file')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(limit + 1)
        if len(data) > limit or os.fstat(fd).st_mtime_ns != info.st_mtime_ns:
            raise ValueError('Audio file changed while reading')
        return data
    finally:
        os.close(fd)


def channels(data):
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('Expected a WAV HRIR preset')
    offset = 12
    while offset + 8 <= len(data):
        size, = struct.unpack_from('<I', data, offset + 4)
        if data[offset:offset + 4] == b'fmt ':
            if size < 16 or offset + 8 + size > len(data):
                break
            format_, count = struct.unpack_from('<HH', data, offset + 8)
            if format_ in (1, 3) and count in (7, 14):
                return 8 if count == 14 else 6
            raise ValueError('This preset needs a supported 7- or 14-channel HRIR')
        offset += 8 + size + (size & 1)
    raise ValueError('Missing WAV format chunk')


def directory(path):
    """Create only owned directories, refusing symlink parents."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Decky runtime path must be absolute')
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('Audio runtime directory must not use symlinks')
    if path.stat().st_uid != os.getuid():
        raise ValueError('Audio runtime directory must belong to the plugin user')
    return path


class Runtime:
    def __init__(self, namespace):
        self.ns = namespace
        self.folder = Path(namespace['script_directory'])
        self.presets = self.folder / 'hrir-audio'
        self.process = None
        self.children = set()
        self.test_task = None
        self.selected = None
        self.channel_count = 8
        self.log = None
        self.lock = asyncio.Lock()

    def preset(self, selected):
        path = Path(selected)
        # The RPC can select a bundled preset, never an arbitrary user file.
        if path.parent != self.presets or path.suffix != '.wav' or path.name in ('.', '..'):
            raise ValueError('Choose a bundled HRIR preset')
        if self.presets.is_symlink():
            raise ValueError('HRIR preset directory must not be a symlink')
        data = read_file(path, MAX_HRIR)
        count = channels(data)
        root = directory(Path(os.environ['DECKY_PLUGIN_RUNTIME_DIR']) / 'frame-control-surround')
        target = root / (hashlib.sha256(data).hexdigest() + '.wav')
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            if read_file(target, MAX_HRIR) != data:
                raise ValueError('Private HRIR copy was changed; retain it for inspection')
        else:
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
            except BaseException:
                target.unlink()
                raise
        return target, count

    def graph(self, target, count):
        source = read_file(self.folder / 'service.sh', 64 * 1024).decode('utf-8')
        match = re.search(r"args_" + str(count) + r"='(.*?)'\n#", source, re.S)
        if not match:
            raise ValueError('Published filter graph is missing')
        graph = match[1].replace("'${virtual_surround_sink_name:?}'", 'virtual-surround-sound')
        graph = graph.replace("'${virtual_surround_sink_description:?}'", 'Virtual Surround Sound')
        graph = graph.replace('"/home/deck/.config/pipewire/hrir.wav"', json.dumps(str(target)))
        graph = graph.replace('"node.linger": true', '"node.linger": false')
        if '/home/deck/' in graph or '$' in graph:
            raise ValueError('Unresolved filter graph template')
        return graph

    def env(self):
        return dict(self.ns['subprocess_exec_env'](), LC_ALL='C')

    async def command(self, *args):
        process = await asyncio.create_subprocess_exec(*args, env=self.env(),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.children.add(process)
        try:
            out, err = await asyncio.wait_for(process.communicate(), 8)
        except BaseException:
            if process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            raise
        finally:
            self.children.discard(process)
        if process.returncode:
            raise RuntimeError('Audio command failed: ' + err.decode(errors='replace')[-1000:])
        return out.decode()

    @staticmethod
    async def terminate(process):
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.wait(), 3)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

    async def stop(self):
        if self.test_task is not None:
            task, self.test_task = self.test_task, None
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        for child in list(self.children):
            await self.terminate(child)
        if self.process is not None:
            process, self.process = self.process, None
            await self.terminate(process)
        if self.log is not None:
            self.log.close()
            self.log = None

    async def start(self, selected, *, recover=True):
        target, count = self.preset(selected)
        graph = self.graph(target, count)
        # Never steal an existing sink (including an older unmanaged service).
        if self.process is None or self.process.returncode is not None:
            nodes = await self.command('pw-cli', 'ls', 'Node')
            if '"input.virtual-surround-sound"' in nodes:
                raise RuntimeError('An existing Virtual Surround Sound sink is running; it was left untouched')
        previous = self.selected
        await self.stop()
        log_path = target.parent / 'filter.log'
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        self.log = os.fdopen(fd, 'ab', buffering=0)
        try:
            self.process = await asyncio.create_subprocess_exec('pw-cli', '-m', 'load-module',
                'libpipewire-module-filter-chain', graph, env=self.env(),
                stdout=self.log, stderr=self.log)
            for _ in range(30):
                if self.process.returncode is not None:
                    raise RuntimeError('PipeWire filter failed; see ' + str(log_path))
                nodes = await self.command('pw-cli', 'ls', 'Node')
                if '"input.virtual-surround-sound"' in nodes:
                    self.selected = selected
                    self.channel_count = count
                    return True
                await asyncio.sleep(.1)
            raise RuntimeError('PipeWire did not expose the surround sink; see ' + str(log_path))
        except BaseException as error:
            await self.stop()
            if isinstance(error, Exception) and recover and previous is not None and previous != selected:
                await self.start(previous, recover=False)
            raise

    async def sound_test(self, sink):
        if sink not in ('virtual-surround-sound', 'virtual-sink'):
            raise ValueError('Choose one of the plugin audio sinks')
        if self.test_task is not None and not self.test_task.done():
            raise RuntimeError('A surround sound test is already running')

        async def sequence():
            try:
                # Each single-channel pass is bounded; unload cancels and reaps it.
                for channel in range(1, self.channel_count + 1):
                    await self.command('speaker-test', '-D', 'pulse:input.' + sink,
                                       '-c', str(self.channel_count), '-t', 'sine', '-s', str(channel))
            except (OSError, RuntimeError, asyncio.TimeoutError) as error:
                self.ns['decky'].logger.error('Surround sound test failed: %s', error)

        self.test_task = asyncio.create_task(sequence())
        return True


def install(namespace):
    runtime = Runtime(namespace)
    plugin = namespace['Plugin']
    old_unload = plugin._unload
    old_check = plugin.check_state
    old_env = namespace['subprocess_exec_env']
    namespace['subprocess_exec_env'] = lambda: dict(old_env(), LC_ALL='C')

    async def init_config(self):
        selected = namespace['settings'].getSetting('frame_control_hrir', namespace['default_hrir_file'])
        async with runtime.lock:
            await runtime.start(str(runtime.presets / selected))

    async def set_hrir_file(self, selected_hrir_path):
        try:
            async with runtime.lock:
                await runtime.start(selected_hrir_path)
                namespace['settings'].setSetting('frame_control_hrir', Path(selected_hrir_path).name)
            return True
        except (OSError, ValueError, RuntimeError) as error:
            namespace['decky'].logger.error('Surround preset refused: %s', error)
            return False

    async def unload(self):
        try:
            await old_unload(self)
        finally:
            async with runtime.lock:
                await runtime.stop()

    async def check_state(self):
        async with runtime.lock:
            if runtime.selected is not None and (runtime.process is None or runtime.process.returncode is not None):
                await runtime.start(runtime.selected)
        return await old_check(self)

    async def migration(self):
        # The published template migration moves unrelated decky-template files.
        # Managed audio state uses Decky's existing plugin-specific directories.
        pass

    async def uninstall(self):
        await unload(self)
        # Keep plugin runtime/settings. Never remove shared HRIRs or user units.

    async def sound_test(self, sink):
        return await runtime.sound_test(sink)

    plugin.init_config = init_config
    plugin.check_state = check_state
    plugin._migration = migration
    plugin.set_hrir_file = set_hrir_file
    plugin._unload = unload
    plugin._uninstall = uninstall
    plugin.run_sound_test = sound_test
    namespace['_framey_surround_runtime'] = runtime
