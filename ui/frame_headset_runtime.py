"""Run Frame Control's opt-in headset panel as one bounded user service.

This process owns only its loopback server and Chromium profile. Steam, SteamVR,
gamescope, other browser profiles, and the user's extensions are never stopped.
"""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


BASE = Path.home() / '.local/share/frame-control/headset'
PORT = 47813
APPID = 2001947813
OVERLAY = f'valve.steam.desktopgame.{APPID}'
VRCMD = '/opt/steamvr/bin/linuxarm64/vrcmd'
TITLE = '[fc-headset]'


class RuntimeError_(RuntimeError):
    pass


def browser_command():
    chrome = Path.home() / 'chromium-xr/chrome'
    if chrome.is_file() and os.access(chrome, os.X_OK):
        return [str(chrome)]
    if Path('/usr/bin/chromium').is_file():
        return ['/usr/bin/chromium']
    if subprocess.run(['flatpak', 'info', 'org.chromium.Chromium'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0:
        return ['flatpak', 'run', 'org.chromium.Chromium']
    raise RuntimeError_('Chromium is needed on the Frame to show the headset panel')


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=5,
                            env={**os.environ, 'DISPLAY': ':0', 'LC_ALL': 'C.UTF-8'})
    if result.returncode:
        raise RuntimeError_((result.stderr or result.stdout).strip()[-400:] or f'{args[0]} failed')
    return result.stdout


def panel_window():
    for line in command('xwininfo', '-root', '-children').splitlines():
        match = re.match(r'\s*(0x[0-9a-fA-F]+) .*\[fc-headset\]', line)
        if match:
            return match[1]
    return None


def wait_for_server(proc):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/headset', timeout=.5) as response:
                if response.status == 200 and TITLE.encode() in response.read(200_000):
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.2)
    raise RuntimeError_('The headset loopback server did not start')


def terminate_owned(proc):
    if proc and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def serve():
    bundle = BASE / 'bundle/ui'
    key = os.urandom(24).hex()
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_file = BASE / 'state.json'
    env = {**os.environ, 'FRAME_LOCAL': '1', 'FRAME_DEVICE': 'headset',
           'FRAME_HEADSET_RUNTIME': '1', 'FRAME_UI_KEY': key}
    env.pop('WAYLAND_DISPLAY', None)
    env['DISPLAY'] = ':0'
    env['LD_PRELOAD'] = ''  # Steam's overlay preload crashes Chromium's zygote.
    server = browser = None
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        command('xprop', '-root', 'GAMESCOPE_FOCUSABLE_WINDOWS')
        with (BASE / 'server.log').open('ab') as log:
            server = subprocess.Popen([sys.executable, '-I', '-u', '-B', str(bundle / 'server.py'),
                                       '--port', str(PORT)], env=env, stdin=subprocess.DEVNULL,
                                      stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        wait_for_server(server)
        browser = subprocess.Popen([*browser_command(), '--ozone-platform=x11',
                                    '--user-data-dir=' + str(BASE / 'profile'),
                                    '--no-first-run', '--no-default-browser-check',
                                    '--password-store=basic', '--disable-session-crashed-bubble',
                                    '--noerrdialogs', '--window-size=1200,800',
                                    '--app=http://127.0.0.1:%d/headset#%s' % (PORT, key)],
                                   env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 30
        win = None
        while time.monotonic() < deadline and browser.poll() is None and not stopping:
            win = panel_window()
            if win:
                break
            time.sleep(.25)
        if not win:
            raise RuntimeError_('The Frame Control browser window did not appear')
        command('xprop', '-id', win, '-f', 'STEAM_GAME', '32c', '-set', 'STEAM_GAME', str(APPID))
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if OVERLAY in command(VRCMD, '--overlays'):
                break
            time.sleep(.25)
        else:
            raise RuntimeError_('SteamVR did not register the Frame Control panel')
        state_file.write_text(json.dumps({'port': PORT, 'window': win, 'overlay': OVERLAY,
                                          'started': time.time()}) + '\n')
        state_file.chmod(0o600)
        print('Frame Control headset panel registered as ' + OVERLAY, flush=True)
        while not stopping and server.poll() is None and browser.poll() is None:
            time.sleep(.5)
    finally:
        state_file.unlink(missing_ok=True)
        terminate_owned(browser)
        terminate_owned(server)


if __name__ == '__main__':
    try:
        serve()
    except (OSError, RuntimeError_, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
