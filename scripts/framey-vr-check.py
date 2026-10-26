#!/usr/bin/env python3
"""Bounded real-Frame VR diagnostics. No device writes without the shared lock.

Default: inspect only. --wake: reversible wake + stereo capture. --exercise:
temporary clean user-service install, live sample settings and OpenVR input.
Exit 0 means requested machine checks passed, never a worn/controller verdict.
"""
import argparse
import base64
import datetime
import hashlib
import io
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tarfile
import time
import signal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import frame_decky
import frame_headset

LOCK = '/tmp/frame-test.lock'
VRCMD = '/opt/steamvr/bin/linuxarm64/vrcmd'
KEY = 'valve.steam.desktopgame.2001947813'


class Remote:
    def __init__(self, host, via=None):
        self.argv = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                     '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2', host]
        self.via = via

    def __call__(self, command, stdin=None, text=True, timeout=30):
        argv = self.argv + [command]
        if self.via:
            argv = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', self.via,
                    shlex.join(argv)]
        result = subprocess.run(argv, input=stdin, capture_output=True, text=text, timeout=timeout)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip())
        return result.stdout

    def python(self, source, timeout=30):
        return json.loads(self('python3 -', stdin=source, timeout=timeout))


PROBE = '''
import json,pathlib,subprocess,ctypes as C
lib=C.CDLL('/opt/steamvr/bin/linuxarm64/libopenvr_api.so')
lib.VR_InitInternal2.argtypes=[C.POINTER(C.c_int),C.c_int,C.c_char_p]
lib.VR_GetGenericInterface.argtypes=[C.c_char_p,C.POINTER(C.c_int)]
lib.VR_GetGenericInterface.restype=C.c_void_p
error=C.c_int();lib.VR_InitInternal2(C.byref(error),3,None)
if error.value: raise RuntimeError('OpenVR unavailable')
try:
 table=lib.VR_GetGenericInterface(b'FnTable:IVROverlay_027',C.byref(error))
 if error.value or not table: raise RuntimeError('Overlay ABI unavailable')
 dashboard=bool(C.CFUNCTYPE(C.c_bool)(C.cast(table,C.POINTER(C.c_void_p))[66])())
finally: lib.VR_ShutdownInternal()
battery=[]
for p in pathlib.Path('/sys/class/power_supply').glob('*/capacity'):
    if (p.parent/'type').read_text().strip()=='Battery': battery.append(int(p.read_text()))
proximity=[]
for p in pathlib.Path('/sys/bus/iio/devices').glob('iio:device*/in_proximity_raw'):
    try: proximity.append(float(p.read_text().strip()))
    except (OSError,ValueError): pass
def cmd(*args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=8)
    if p.returncode: raise RuntimeError(p.stderr or p.stdout)
    return p.stdout.strip()
vr='/opt/steamvr/bin/linuxarm64/vrcmd'
print(json.dumps({'battery':battery,'proximity':proximity,'dashboardVisible':dashboard,'stats':json.loads(cmd(vr,'--stats')),
 'overlays':cmd(vr,'--overlays'),
 'pause':cmd(vr,'--settings-bool','power.pauseCompositorOnStandby'),
 'timeout':cmd(vr,'--settings-float','power.turnOffScreensTimeout')}))
'''


def settings(state):
    pause = state['pause'].split('=', 1)[1]
    timeout = state['timeout'].split('=', 1)[1]
    if pause not in ('true', 'false') or not 0 <= float(timeout) <= 86400:
        raise RuntimeError('Cannot safely save original SteamVR power values')
    return pause, timeout


def steamvr_activity(rows):
    """Read the unique status row; metrics can precede it in --stats output."""
    if not isinstance(rows, list):
        return None
    levels = [row.get('activity_level') for row in rows
              if isinstance(row, dict) and row.get('operation') == 'status']
    return levels[0] if len(levels) == 1 and type(levels[0]) is int else None


def diagnostic_source():
    return (ROOT / 'scripts/framey_openvr.py').read_text() + '''
import json
vr=Overlay()
try: print(json.dumps({'state':vr.snapshot(),'imageRead':vr.image_hash()}))
finally: vr.close()
'''


def wait_overlay(remote, attempts=8):
    """Give SteamVR a bounded moment to expose its newly registered panel."""
    for attempt in range(attempts):
        snapshot = remote.python(diagnostic_source())
        if snapshot['state']['visible']:
            return snapshot
        if attempt < attempts - 1:
            time.sleep(1)
    return snapshot


HIDDEN_OVERLAY_DIAGNOSTIC = '''
import json,pathlib,subprocess
key='valve.steam.desktopgame.2001947813'
p=subprocess.run(['/opt/steamvr/bin/linuxarm64/vrcmd','--overlays'],
                 capture_output=True,text=True,timeout=8)
lines=[line.strip() for line in p.stdout.splitlines() if "'"+key+"'" in line]
service=subprocess.run(['systemctl','--user','is-active','frame-control-headset.service'],
                       capture_output=True,text=True,timeout=8)
state=pathlib.Path.home()/'.local/share/frame-control/headset/state.json'
try: window=json.loads(state.read_text()).get('window')
except (OSError,ValueError): window=None
print(json.dumps({'overlayLines':lines[:2], 'overlayCommandExit':p.returncode,
                  'serviceActive':service.stdout.strip()=='active', 'windowRegistered':bool(window)}))
'''


def debug_bundle(original, profile):
    """Only the test-owned browser gets CDP and a disposable profile."""
    out = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(original), mode='r:gz') as src, tarfile.open(fileobj=out, mode='w:gz') as dst:
        for item in src.getmembers():
            data = src.extractfile(item).read()
            if item.name == 'ui/frame_headset_runtime.py':
                code = data.decode()
                needle = "'--noerrdialogs', '--window-size=1200,800',"
                if needle not in code:
                    raise RuntimeError('Runtime changed; review test browser setup')
                code = code.replace(needle, "'--noerrdialogs', '--remote-debugging-port=0', '--window-size=1200,800',")
                code = code.replace("str(BASE / 'profile')", repr(profile))
                data = code.encode()
            item.size = len(data)
            dst.addfile(item, io.BytesIO(data))
    return out.getvalue()


def exercise_source(profile, plugin_id, folder):
    # Runs entirely on the headset. The normal iframe, HTTP handler, CEF bridge
    # and Decky Python backend are used. CDP observes DOM/coordinates; OpenVR
    # delivers clicks. No JS .click() or backend stubs.
    return (ROOT/'scripts/framey_openvr.py').read_text() + '\n' + (ROOT/'scripts/framey_vr_input.py').read_text() + '\n' + (
        'print(json.dumps(exercise(%r,%r,%r)))\n' % (profile, plugin_id, folder))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='frame')
    parser.add_argument('--via', help='Existing paired SSH host, e.g. lxso2')
    parser.add_argument('--wake', action='store_true')
    parser.add_argument('--exercise', action='store_true', help='Temporary user installs; requires no managed panel/Decky install')
    parser.add_argument('--output', type=Path, required=True, help='Private evidence folder (screenshots may contain room pixels)')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    report = {'schema': 1, 'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'controllerHardwareVerified': False, 'wornVisualComfortVerified': False}
    git = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True)
    report['sourceCommit'] = git.stdout.strip() if git.returncode == 0 else None
    remote = Remote(args.host, args.via)
    token = 'framey-vr-' + secrets.token_hex(8)
    folder = token
    profile = '/tmp/' + token + '-profile'
    locked = power_changed = plugin_created = decky_created = panel_created = watchdog = False
    original_bundle = frame_headset.bundle
    before = None
    previous_term = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(RuntimeError('Terminated; cleaning up')))
    try:
        remote('mkdir ' + LOCK + ' && { printf %s ' + shlex.quote(token) + ' > ' + LOCK + '/owner || { rmdir ' + LOCK + '; exit 1; }; }')
        locked = True
        before = remote.python(PROBE)
        report['before'] = before
        pause, timeout = settings(before)
        if not before['battery'] or min(before['battery']) < 20:
            raise RuntimeError('Battery unknown or below 20%')
        if args.wake or args.exercise:
            if steamvr_activity(before.get('stats')) != 3:
                raise RuntimeError('Frame is awake or SteamVR activity is unknown; active session untouched')
        if args.wake or args.exercise:
            # Independent systemd timer restores power even if the controller is
            # killed or SSH disappears. It retains the test lock for recovery.
            recovery = '/tmp/' + token + '-restore.py'
            restore_source = ("import pathlib,subprocess\n"
                "p=pathlib.Path('/tmp/frame-test.lock/owner')\n"
                "if p.exists() and p.read_text()==" + repr(token) + ":\n"
                " subprocess.run([" + repr(VRCMD) + ", '--set-settings-bool','power.pauseCompositorOnStandby'," + repr('1' if pause == 'true' else '0') + "],check=True)\n"
                " subprocess.run([" + repr(VRCMD) + ", '--set-settings-float','power.turnOffScreensTimeout'," + repr(timeout) + "],check=True)\n")
            remote('umask 077; cat > ' + shlex.quote(recovery), stdin=restore_source)
            remote('systemd-run --user --quiet --unit=' + token + '-restore --on-active=240s /usr/bin/python3 ' + shlex.quote(recovery))
            watchdog = True
            report['powerRecovery'] = {'timer':token+'-restore.timer','script':recovery,
                                       'originalPause':pause,'originalTimeout':timeout}
            (args.output/'recovery.json').write_text(json.dumps({'host':args.host,'via':args.via,'lockOwner':token,**report['powerRecovery']},indent=2)+'\n')
        if args.exercise:
            d, h = frame_decky.status(remote), frame_headset.status(remote)
            if d['managed'] or h['managed'] or d['upstreamInstall']:
                raise RuntimeError('Exercise needs absent managed services; existing installs left intact')
            # Refuse every collision, including retained plugin settings.
            files = {name: base64.b64encode((ROOT/'examples/framey-settings'/name).read_bytes()).decode()
                     for name in ('plugin.json', 'main.py', 'dist/index.js')}
            source = '''
import base64,hashlib,json,pathlib
base=pathlib.Path.home()/'.local/share/frame-control/decky'
folder=%r
p=base/'plugins'/folder
if p.exists() or (base/'settings'/folder).exists(): raise RuntimeError('Test path collision')
p.mkdir(parents=True); (p/'dist').mkdir()
for name,data in %r.items(): (p/name).write_bytes(base64.b64decode(data))
manifest=json.loads((p/'plugin.json').read_text());manifest['name']='Framey VR Check '+folder
(p/'plugin.json').write_text(json.dumps(manifest))
digest=hashlib.sha256()
for name in ('plugin.json','main.py','dist/index.js'):
 digest.update(name.encode()+b'\\0'+(p/name).read_bytes())
(p/'.frame-control-store.json').write_text(json.dumps({'storeId':2000000001,'version':'local-vr-check','sha256':digest.hexdigest()}))
print(json.dumps({'created':True}))
''' % (folder, files)
            remote.python(source)
            plugin_created = True
            decky_created = True
            report['deckyInstall'] = frame_decky.change(remote, 'install')
            # Decky reloads its Steam frontend; install the panel afterwards.
            time.sleep(3)
            frame_headset.bundle = lambda: debug_bundle(original_bundle(), profile)
            panel_created = True
            report['panelInstall'] = frame_headset.change(remote, 'install')
        if args.wake or args.exercise:
            power_changed = True  # before first setter, so partial failure restores
            remote(VRCMD + ' --set-settings-bool power.pauseCompositorOnStandby 0')
            remote(VRCMD + ' --set-settings-float power.turnOffScreensTimeout 120')
            remote(VRCMD + ' --handlewakeup')
            remote(VRCMD + ' --showdashboard ' + KEY)
            time.sleep(2)
        report['overlay'] = wait_overlay(remote) if args.wake or args.exercise else remote.python(diagnostic_source())
        if args.exercise and not report['overlay']['state']['visible']:
            report['retaggedTestWindow'] = True
            remote.python('''
import json,pathlib,subprocess,time,os
p=pathlib.Path.home()/'.local/share/frame-control/headset/state.json'
w=json.loads(p.read_text())['window'];env={**os.environ,'DISPLAY':':0'}
subprocess.run(['xprop','-id',w,'-remove','STEAM_GAME'],env=env,check=True)
time.sleep(1)
subprocess.run(['xprop','-id',w,'-f','STEAM_GAME','32c','-set','STEAM_GAME','2001947813'],env=env,check=True)
time.sleep(1)
subprocess.run(['/opt/steamvr/bin/linuxarm64/vrcmd','--showdashboard','valve.steam.desktopgame.2001947813'],capture_output=True,check=True)
time.sleep(2)
print('{}')
''')
            report['overlay'] = wait_overlay(remote)
        if args.exercise and not report['overlay']['state']['visible']:
            try:
                report['hiddenOverlay'] = remote.python(HIDDEN_OVERLAY_DIAGNOSTIC)
            except Exception as exc:
                report['hiddenOverlayError'] = str(exc)
            raise RuntimeError('Frame Control overlay stayed hidden after focus retry; no input sent')
        if args.exercise:
            lines = remote(VRCMD + ' --overlays').splitlines()
            report['testOverlayListing'] = [line.strip() for index, line in enumerate(lines)
                                            if line.startswith("'" + KEY + "'") or
                                            (index and lines[index - 1].startswith("'" + KEY + "'"))]
        if args.wake or args.exercise:
            shot = remote.python((ROOT/'ui/frame_vrshot.py').read_text(), timeout=20)['path']
            try:
                image = remote('cat ' + shlex.quote(shot), text=False, timeout=20)
                (args.output/'before-stereo-private.png').write_bytes(image)
                report['beforeStereoSha256'] = hashlib.sha256(image).hexdigest()
            finally:
                remote('rm -f ' + shlex.quote(shot))
        if args.exercise:
            report['input'] = remote.python(exercise_source(profile, 2000000001, folder), timeout=100)
        if args.wake or args.exercise:
            shot = remote.python((ROOT/'ui/frame_vrshot.py').read_text(), timeout=20)['path']
            try:
                image = remote('cat ' + shlex.quote(shot), text=False, timeout=20)
                (args.output/'stereo-private.png').write_bytes(image)
                report['stereoSha256'] = hashlib.sha256(image).hexdigest()
                report['compositorChanged'] = report['stereoSha256'] != report.get('beforeStereoSha256')
            finally:
                remote('rm -f ' + shlex.quote(shot))
            # Same SteamVR mirror used by OBS; FFmpeg is already on the Frame.
            mirror = remote("ffmpeg -hide_banner -loglevel error -f v4l2 -i /dev/video99 -vf 'select=gte(n\\,60)' -frames:v 1 -f image2pipe -vcodec png -", text=False, timeout=20)
            (args.output/'mirror-private.png').write_bytes(mirror)
            report['mirrorSha256'] = hashlib.sha256(mirror).hexdigest()
        report['passed'] = bool(report['overlay']['state']['visible'])
        if args.exercise:
            report['passed'] = report['passed'] and report['input']['passed'] and report.get('compositorChanged',False)
    except Exception as exc:
        report['error'] = str(exc)
        report['passed'] = False
    finally:
        frame_headset.bundle = original_bundle
        cleanup = []
        def clean(name, action):
            try: action()
            except Exception as exc: cleanup.append({'step':name,'error':str(exc)})
        if locked:
            if panel_created:
                clean('remove test panel', lambda: frame_headset.change(remote, 'remove') if frame_headset.status(remote)['managed'] else None)
            if decky_created:
                clean('remove test Decky', lambda: frame_decky.change(remote, 'remove') if frame_decky.status(remote)['managed'] else None)
            if plugin_created:
                # Only random per-run paths created after collision checks.
                clean('remove test files', lambda: remote.python('''
import pathlib,shutil,json
base=pathlib.Path.home()/'.local/share/frame-control/decky'
for parent in ('plugins','settings','data','logs'):
 p=base/parent/%r
 if p.is_dir() and not p.is_symlink(): shutil.rmtree(p)
p=pathlib.Path(%r)
if p.is_dir() and not p.is_symlink(): shutil.rmtree(p)
print('{}')
''' % (folder, profile)))
            if power_changed:
                clean('restore compositor pause', lambda: remote(VRCMD + ' --set-settings-bool power.pauseCompositorOnStandby ' + ('1' if pause == 'true' else '0')))
                clean('restore screen timeout', lambda: remote(VRCMD + ' --set-settings-float power.turnOffScreensTimeout ' + shlex.quote(timeout)))
                clean('restore dashboard visibility', lambda: remote(VRCMD + ' --hidedashboard') if not before['dashboardVisible'] else None)
            try:
                report['after'] = remote.python(PROBE)
                if power_changed and settings(report['after']) != settings(before):
                    cleanup.append({'step':'read back power settings','error':'Original values not restored'})
            except Exception as exc: cleanup.append({'step':'after probe','error':str(exc)})
            if watchdog and not cleanup:
                clean('stop power recovery timer', lambda: remote.python('''
import subprocess,json
unit=%r
timer=subprocess.run(['systemctl','--user','show',unit+'.timer','--property=LoadState','--value'],capture_output=True,text=True)
if timer.stdout.strip()=='loaded': subprocess.run(['systemctl','--user','stop',unit+'.timer'],check=True,capture_output=True)
p=subprocess.run(['systemctl','--user','show',unit+'.service','--property=LoadState','--value'],capture_output=True,text=True)
if p.stdout.strip()=='loaded': subprocess.run(['systemctl','--user','stop',unit+'.service'],check=True,capture_output=True)
print('{}')
''' % (token+'-restore')))
                if not cleanup:
                    clean('remove power recovery script', lambda: remote('rm -f ' + shlex.quote(recovery)))
                    report['powerRecoveryRemoved'] = not cleanup
                    if not cleanup: (args.output/'recovery.json').unlink(missing_ok=True)
            if not cleanup:
                clean('release owned lock', lambda: remote('test "$(cat ' + LOCK + '/owner)" = ' + shlex.quote(token) + ' && rm ' + LOCK + '/owner && rmdir ' + LOCK))
                report['lockReleased'] = not cleanup
            else:
                report['lockRetainedForRecovery'] = token
        report['cleanupErrors'] = cleanup
        report['passed'] = bool(report.get('passed') and not cleanup)
        (args.output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    signal.signal(signal.SIGTERM, previous_term)
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
