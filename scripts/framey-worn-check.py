#!/usr/bin/env python3
"""Bounded, opt-in real Frame check. Run only while someone wears the headset.

Requires an already installed Frame Control VR panel, Decky user service, and
one Framey-managed plugin. It never installs, restarts, or removes a service.
"""
import datetime
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', 'frame']
LOCK = '/tmp/frame-test.lock'


def remote(command, stdin=None, timeout=15):
    run = subprocess.run([*SSH, command], input=stdin, capture_output=True,
                         text=True, timeout=timeout)
    if run.returncode:
        raise RuntimeError((run.stderr or run.stdout).strip() or f'SSH exited {run.returncode}')
    return run.stdout


PROBE = r'''
import json, pathlib, subprocess
power=[]
for item in pathlib.Path('/sys/class/power_supply').glob('*/capacity'):
    try:
        if (item.parent/'type').read_text().strip() == 'Battery':
            power.append({'name':item.parent.name,'percent':int(item.read_text().strip())})
    except (OSError,ValueError): pass
stats=subprocess.run(['/opt/steamvr/bin/linuxarm64/vrcmd','--stats'],capture_output=True,text=True,timeout=5)
try: activity=json.loads(stats.stdout)[0]['activity_level'] if stats.returncode == 0 else None
except (ValueError,KeyError,IndexError,TypeError): activity=None
panels=subprocess.run(['/opt/steamvr/bin/linuxarm64/vrcmd','--overlays'],capture_output=True,text=True,timeout=5)
panel=next((line.strip() for line in panels.stdout.splitlines() if 'valve.steam.desktopgame.2001947813' in line),None)
base=pathlib.Path.home()/'.local/share/frame-control/decky/plugins'
plugins=[]
if base.is_dir() and not base.is_symlink():
    for folder in base.iterdir():
        if folder.is_symlink(): continue
        try:
            p=json.loads((folder/'.frame-control-store.json').read_text())
            manifest=json.loads((folder/'plugin.json').read_text())
            if isinstance(p.get('storeId'),int): plugins.append({'id':p['storeId'],'name':manifest['name']})
        except (OSError,ValueError,KeyError): pass
service=subprocess.run(['systemctl','--user','is-active','frame-control-headset.service'],capture_output=True,text=True)
print(json.dumps({'battery':power,'activity':activity,'panel':panel,
                  'panelService':service.returncode==0,'plugins':plugins}))
'''

OVERLAY_PROBE = r'''
import ctypes as C, json
vr=C.CDLL('/opt/steamvr/bin/linuxarm64/libopenvr_api.so')
vr.VR_InitInternal2.argtypes=[C.POINTER(C.c_int),C.c_int,C.c_char_p]
vr.VR_GetGenericInterface.argtypes=[C.c_char_p,C.POINTER(C.c_int)]
vr.VR_GetGenericInterface.restype=C.c_void_p
error=C.c_int()
vr.VR_InitInternal2(C.byref(error),3,None)
result={'visible':None,'dashboardVisible':None,'error':error.value}
if not error.value:
    try:
        table=C.cast(vr.VR_GetGenericInterface(b'FnTable:IVROverlay_028',C.byref(error)),C.POINTER(C.c_void_p))
        if not error.value and table:
            handle=C.c_uint64()
            find=C.CFUNCTYPE(C.c_int,C.c_char_p,C.POINTER(C.c_uint64))(table[0])
            if find(b'valve.steam.desktopgame.2001947813',C.byref(handle))==0:
                result['visible']=bool(C.CFUNCTYPE(C.c_bool,C.c_uint64)(table[45])(handle))
                result['dashboardVisible']=bool(C.CFUNCTYPE(C.c_bool)(table[68])())
    finally: vr.VR_ShutdownInternal()
print(json.dumps(result))
'''


def probe():
    return json.loads(remote('python3 -', stdin=PROBE))


def check_file():
    code = "import pathlib;print((pathlib.Path.home()/'.local/share/frame-control/headset/worn-check.json').read_text())"
    return json.loads(remote('python3 -c ' + shlex.quote(code)))


def main():
    result = {'time':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'proof':'worn-headset check'}
    token = 'framey-' + secrets.token_hex(12)
    locked = False
    challenge = False
    try:
        before = probe()
        result['before'] = before
        if not before['battery'] or min(x['percent'] for x in before['battery']) < 20:
            raise RuntimeError('Battery capacity unavailable or below 20%; no device session started')
        if before['activity'] is None or before['activity'] >= 3:
            raise RuntimeError('SteamVR is in standby; no worn-headset check started')
        if not before['panelService'] or not before['plugins']:
            raise RuntimeError('Install and open the Frame Control panel and a Framey plugin before this check')
        remote('mkdir ' + LOCK + ' && printf %s ' + shlex.quote(token) + ' > ' + LOCK + '/owner')
        locked = True
        after_lock = probe()
        if after_lock['activity'] >= 3 or min(x['percent'] for x in after_lock['battery']) < 20:
            raise RuntimeError('Activity or battery changed after acquiring the lock')
        state = json.dumps({'nonce':token,'started':time.time()})
        code = "import pathlib; p=pathlib.Path.home()/'.local/share/frame-control/headset/worn-check.json'; p.write_text(" + repr(state) + ")"
        remote('python3 -c ' + shlex.quote(code))
        challenge = True
        print('In the worn headset: open SteamVR dashboard → Frame Control → a managed Decky plugin → Open panel. Touch a setting with the controller. Waiting up to 35 seconds.', flush=True)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            state = check_file()
            if state.get('nonce') == token and state.get('panel') and state.get('input'):
                break
            time.sleep(1)
        result['interaction'] = state
        result['after'] = probe()
        result['worn'] = isinstance(result['after']['activity'], int) and result['after']['activity'] < 3
        result['overlay'] = json.loads(remote('python3 -', stdin=OVERLAY_PROBE, timeout=15))
        result['panelVisible'] = result['overlay']['visible'] is True
        installed_ids = {p['id'] for p in before['plugins']}
        result['controllerInput'] = bool(state.get('input', {}).get('at', 0) > state.get('started', 0))
        result['pluginPanelReady'] = bool(state.get('panel', {}).get('at', 0) > state.get('started', 0)
                                          and state['panel'].get('pluginId') in installed_ids)
        if result['panelVisible'] and result['pluginPanelReady']:
            shot = json.loads(remote('python3 -', stdin=(ROOT/'ui/frame_vrshot.py').read_text(), timeout=20))['path']
            local = Path('/tmp')/('framey-worn-' + token + '.png')
            with local.open('wb') as out:
                copy = subprocess.run([*SSH, 'cat ' + shlex.quote(shot)], stdout=out, stderr=subprocess.PIPE, timeout=20)
            remote('rm -f ' + shlex.quote(shot))
            if copy.returncode: raise RuntimeError('Could not copy the SteamVR screenshot')
            result['screenshot'] = str(local)
            pixels = subprocess.run(['convert', str(local), '-resize', '64x64!', 'txt:-'],
                                    capture_output=True, text=True, timeout=15)
            result['screenshotColors'] = len(set(re.findall(r'#[0-9A-Fa-f]{6,8}', pixels.stdout))) if pixels.returncode == 0 else None
        result['passed'] = (result['worn'] and result['panelVisible'] and result['controllerInput'] and
                            result['pluginPanelReady'] and (result.get('screenshotColors') or 0) > 8)
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        if challenge:
            code = "import json,pathlib; p=pathlib.Path.home()/'.local/share/frame-control/headset/worn-check.json'; d=json.loads(p.read_text()); p.unlink() if d.get('nonce')==" + repr(token) + " else None"
            try: remote('python3 -c ' + shlex.quote(code))
            except Exception as exc: result['challengeCleanupError'] = str(exc)
        if locked:
            try:
                remote('test "$(cat ' + LOCK + '/owner)" = ' + shlex.quote(token) +
                       ' && rm ' + LOCK + '/owner && rmdir ' + LOCK)
                result['lockReleased'] = True
            except Exception as exc: result['lockCleanupError'] = str(exc)
    print(json.dumps(result, indent=2))
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    sys.exit(main())
