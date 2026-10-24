"""PC in the headset (Experimental, Windows only), behind the existing MacView
tunnel/panel controller.

The public /api/macview name and viewer URL are the Mac feature's. Only helper
launch, platform availability and source validation are different. No second
viewer, SSH supervisor or benchmark launcher.

It is off until the person turns it on in Tools: until then nothing starts,
no native library is loaded and no window is listed. The Linux adapter from
PR #38 is in the tree but never offered (host_view only picks this on Windows).
"""
import os
import sys
import subprocess
from frame_macview import MacView, MacViewError, ROOT
from frame_pc_capture import LIBRARY, NATIVE


def prepend(env, name, path):
    """An empty entry means the current directory to the loader; never add one."""
    rest = env.get(name, '')
    env[name] = str(path) + (os.pathsep + rest if rest else '')


OFF = 'Off. Turn it on to list your windows and screens.'


class PCView(MacView):
    viewer_profile = 'pc-view'
    host = 'windows' if sys.platform == 'win32' else 'linux'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefer_usb = False  # Mac networksetup probe is platform-specific
        self.enabled = False

    def unavailable(self):
        if sys.platform != 'win32':
            return 'PC in the headset is only available on Windows for now.'
        if not self.enabled:
            return OFF
        if not LIBRARY.is_file():
            return 'The PC streaming libraries are missing from this build. See docs/pc-in-headset.md.'
        return None

    def state(self):
        result = super().state()
        result.update(host=self.host, experimental=True, enabled=self.enabled)
        return result

    def set_enabled(self, on):
        """Turning it off ends every stream and the helper; nothing restarts
        it until it's turned on again (ensure_agent asks unavailable())."""
        if on:
            with self.lock:
                self.enabled = True
            return self.state()
        try:
            self.stop()  # while still enabled, so the viewers on the Frame close too
        except MacViewError:
            pass
        with self.lock:
            self.enabled = False
            self._drop_tunnel()
            agent, self.agent = self.agent, None
        if agent and agent.poll() is None:
            # EOF gives the host a chance to release held input, including on
            # Windows where terminate is uncatchable.
            if agent.stdin:
                agent.stdin.close()
            try:
                agent.wait(10)
            except subprocess.TimeoutExpired:
                agent.kill()
                agent.wait(5)
        return self.state()

    def build(self):
        pass  # native libraries are built and bundled with the app

    def agent_command(self):
        return [sys.executable, str(ROOT / 'ui' / 'frame_pc_agent.py')]

    def agent_environment(self):
        env = super().agent_environment()
        env['GST_PLUGIN_PATH_1_0'] = str(NATIVE / 'lib' / 'gstreamer-1.0')
        env['GST_PLUGIN_SYSTEM_PATH_1_0'] = ''
        cache = os.path.join(os.path.expanduser('~'), '.cache', 'frame-control')
        os.makedirs(cache, exist_ok=True)
        env['GST_REGISTRY_1_0'] = os.path.join(cache, 'gstreamer-registry.bin')
        env['GST_REGISTRY_FORK'] = 'no'
        if sys.platform == 'win32':
            prepend(env, 'PATH', NATIVE / 'bin')
        else:
            prepend(env, 'LD_LIBRARY_PATH', NATIVE / 'lib')
            env['PIPEWIRE_MODULE_DIR'] = str(NATIVE / 'lib' / 'pipewire-0.3')
            env['SPA_PLUGIN_DIR'] = str(NATIVE / 'lib' / 'spa-0.2')
            env['PIPEWIRE_CONFIG_DIR'] = str(NATIVE / 'share' / 'pipewire')
            env['PIPEWIRE_CONFIG_NAME'] = 'client.conf'
        return env

    def shutdown(self):
        self.closing = True
        try:
            self.stop()
        except MacViewError:
            pass
        if self.tunnel and self.tunnel.poll() is None:
            self.tunnel.terminate()
        if self.agent and self.agent.poll() is None:
            # EOF gives the host a chance to release held input and portal
            # sessions, including on Windows where terminate is uncatchable.
            if self.agent.stdin:
                self.agent.stdin.close()
            try:
                self.agent.wait(10)
            except subprocess.TimeoutExpired:
                self.agent.kill()
                self.agent.wait(5)

    def _show(self, src, quality, width, height):
        if src.startswith('separate:'):
            raise MacViewError('Separate virtual displays are a Mac-only feature. Choose a window or screen.')
        return super()._show(src, quality, width, height)


def host_view(*args, **kwargs):
    """Windows gets the PC host; everywhere else keeps the Mac view, which
    reports itself unavailable off macOS."""
    return (PCView if sys.platform == 'win32' else MacView)(*args, **kwargs)
