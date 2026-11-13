"""The Frame simulator's own state, beside the fake Frame's (fakeframe_state).

The e2e fake has no SteamVR, proximity sensor or headset view. The simulator
adds stand-ins for those (vrcmd, libopenvr_api.so, an ffmpeg wrapper), and they
read this file: /var/lib/fakeframe/sim/state.json. frame-sim-ctl changes it.
The fake Frame's `fakeframe-ctl reset` doesn't touch it.
"""
import contextlib
import fcntl
import json
import os
import sys

sys.path.insert(0, '/usr/local/lib/fakeframe')
import fakeframe_state as fs  # noqa: E402,F401  (re-exported for the stubs)

DIR = '/var/lib/fakeframe/sim'
STATE = os.path.join(DIR, 'state.json')
LOCK = os.path.join(DIR, 'state.lock')
VR_OFF = os.path.join(DIR, 'vr-off')            # read by fake_openvr.c
SCREEN_TEXT = os.path.join(DIR, 'screen.txt')   # what the headset view shows, redrawn each frame
STREAM_DEVICE = '/dev/video99'                  # ui/server.py STREAM_DEVICE
IIO = '/var/lib/fakeframe/sim/iio'              # compose mounts it over /sys/bus/iio/devices
# What the proximity sensor reads. frame_smoke.py counts 0-10 as "nobody in it";
# the worn value is a guess above that range, not a recorded reading.
PROXIMITY = {False: 0, True: 120}
# OpenVR EDeviceActivityLevel: 1 UserInteraction (worn), 3 Standby (put down),
# the level frame_smoke.py's preflight requires before it touches the headset.
ACTIVITY = {False: 3, True: 1}


def default_state():
    return {
        'vr': True,             # SteamVR (vrserver) running
        'worn': False,          # someone wearing the headset
        # Dashboard panels for `vrcmd --overlays`. Keys and titles are made up;
        # the line format is the one ui/frame_panels.py parses.
        'overlays': [
            {'key': 'valve.steam.bigpicture', 'title': 'Steam', 'visible': True},
            {'key': 'valve.steam.desktop', 'title': 'Desktop', 'visible': False},
        ],
    }


@contextlib.contextmanager
def _locked(kind):
    os.makedirs(DIR, exist_ok=True)
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        os.fchmod(fd, 0o666)
    except OSError:
        pass
    try:
        fcntl.flock(fd, kind)
        yield
    finally:
        os.close(fd)


def _load():
    try:
        with open(STATE) as f:
            return {**default_state(), **json.load(f)}
    except (OSError, ValueError):
        return default_state()


def read():
    with _locked(fcntl.LOCK_SH):
        return _load()


@contextlib.contextmanager
def update():
    with _locked(fcntl.LOCK_EX):
        state = _load()
        yield state
        tmp = f'{STATE}.{os.getpid()}.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=1, sort_keys=True)
        os.chmod(tmp, 0o666)
        os.replace(tmp, STATE)


def running_title():
    """The newest launch that started and hasn't exited, by name, as Steam would show it."""
    state = fs.read()
    names = {a['appid']: a['display_name'] for a in state['steam']['apps']}
    names.update({s['appid']: s['name'] for s in state['steam']['shortcuts'] if 'appid' in s and 'name' in s})
    for launch in reversed(state['launches']):
        if launch.get('started') and launch.get('exit') is None:
            appid = launch.get('appid')
            return names.get(appid) or launch.get('name') or f'App {appid}'
    return None


SYSBUS = '/var/lib/fakeframe/sim/sysbus'        # compose mounts the same volume over /sys/bus


def apply():
    """Make the device files match the state: /dev/video99, the proximity sensor and
    the flag fake_openvr.c reads. Root only (the supervisor and frame-sim-ctl)."""
    state = read()
    for path, present in ((STREAM_DEVICE, state['vr']), (VR_OFF, not state['vr'])):
        if present and not os.path.exists(path):
            # A plain file is enough: ui/server.py only checks the device exists before
            # starting ffmpeg, and the ffmpeg wrapper never opens it.
            open(path, 'a').close()
            os.chmod(path, 0o666)
        elif not present and os.path.exists(path):
            os.unlink(path)
    # /sys/bus is read-only in a container, and /sys/bus/iio needn't exist on the host
    # to mount over, so compose mounts a volume over all of /sys/bus. Only iio is read
    # under it (frame_smoke.py, framey-worn-check.py, frame_power_sample.py).
    if os.path.isdir(SYSBUS):
        dev = os.path.join(SYSBUS, 'iio/devices/iio:device0')
        os.makedirs(dev, exist_ok=True)
        for name, value in (('name', 'proximity'), ('in_proximity_raw', PROXIMITY[state['worn']])):
            with open(os.path.join(dev, name), 'w') as f:
                f.write(f'{value}\n')
