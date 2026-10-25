"""Install and control the removable SteamVR Frame Control panel on the Frame.

The companion sends a deterministic app bundle over SSH. The Frame owns a user
service and a browser profile; nothing is installed under /etc or as root.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import secrets
import tarfile


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIRS = ('ui', 'apk-catalog', 'frame/android', 'frame/devkit-utils', 'frame/openxr-compat', 'scripts')
MAX_ARCHIVE = 32 * 1024 * 1024


PROBE = r'''
import json, os, pathlib, platform, subprocess
home = pathlib.Path.home()
base = home / '.local/share/frame-control/headset'
unit = home / '.config/systemd/user/frame-control-headset.service'
try: receipt = json.loads((base/'receipt.json').read_text())
except (OSError, ValueError): receipt = {}
try: state = json.loads((base/'state.json').read_text())
except (OSError, ValueError): state = {}
release = {}
for line in pathlib.Path('/etc/os-release').read_text().splitlines():
    if '=' in line:
        k, v = line.split('=', 1); release[k] = v.strip('"')
active = subprocess.run(['systemctl','--user','is-active','frame-control-headset.service'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
overlay = 'valve.steam.desktopgame.2001947813'
try:
    p = subprocess.run(['/opt/steamvr/bin/linuxarm64/vrcmd','--overlays'],
                       capture_output=True, text=True, timeout=5)
    registered = p.returncode == 0 and ("'"+overlay+"'") in p.stdout
except (OSError, subprocess.TimeoutExpired): registered = False
print(json.dumps({'arch':platform.machine(),'variant':release.get('VARIANT_ID'),
    'os':release.get('VERSION_ID'),'build':release.get('BUILD_ID'),
    'managed':unit.is_file() and receipt.get('managedBy') == 'Frame Control',
    'version':receipt.get('version'),'running':active,'overlayRegistered':registered,
    'window':state.get('window') if active else None,
    'extensionsFolder':str(home/'.local/share/frame-control/extensions')}))
'''


APPLY = r'''
import hashlib, io, json, os, pathlib, platform, shutil, subprocess, sys, tarfile, time
action, token, digest = sys.argv[1:]
home = pathlib.Path.home()
base = home / '.local/share/frame-control/headset'
bundle = base / 'bundle'
receipt = base / 'receipt.json'
unit = home / '.config/systemd/user/frame-control-headset.service'
upload = pathlib.Path('/tmp/frame-control-headset-' + token)
stage = base / ('stage-' + token)
old = base / ('old-' + token)
overlay = 'valve.steam.desktopgame.2001947813'
def systemd(*args):
    p = subprocess.run(['systemctl','--user',*args], capture_output=True, text=True, timeout=55)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip()[-400:] or 'user service failed')
def managed():
    try: return unit.is_file() and json.loads(receipt.read_text()).get('managedBy') == 'Frame Control'
    except (OSError, ValueError): return False
def show():
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if (base/'state.json').is_file():
            p = subprocess.run(['/opt/steamvr/bin/linuxarm64/vrcmd','--showdashboard',overlay],
                               capture_output=True, text=True, timeout=10)
            if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip()[-400:] or 'dashboard rejected panel')
            return {'message':'Asked SteamVR to show Frame Control. Select its panel in the dashboard if it is hidden.',
                    'overlay':overlay}
        time.sleep(.25)
    raise RuntimeError('The headset panel did not register within 45 seconds; check the user service log')
try:
    if action == 'remove':
        if not managed(): raise RuntimeError('No Frame Control managed headset panel to remove')
        systemd('stop','frame-control-headset.service')
        unit.unlink()
        systemd('daemon-reload')
        shutil.rmtree(bundle)
        receipt.unlink()
        (base/'server.log').unlink(missing_ok=True)
        print(json.dumps({'message':'Removed the Frame Control headset service and app bundle. Extensions and browser profile were kept.'}))
    elif action == 'close':
        if not managed(): raise RuntimeError('The headset panel is not installed by Frame Control')
        systemd('stop','frame-control-headset.service')
        print(json.dumps({'message':'Closed the Frame Control headset panel.'}))
    elif action == 'open':
        if not managed(): raise RuntimeError('Install the headset panel first')
        systemd('start','frame-control-headset.service')
        print(json.dumps(show()))
    else:
        if action not in ('install','update'): raise RuntimeError('Invalid headset panel action')
        if platform.machine() != 'aarch64': raise RuntimeError('This headset panel needs the Frame ARM64 build')
        if action == 'install' and (unit.exists() or receipt.exists() or bundle.exists()):
            raise RuntimeError('Headset panel files already exist; no existing installation was changed')
        if action == 'update' and not managed(): raise RuntimeError('No Frame Control managed panel to update')
        data = upload.read_bytes()
        if not 1024 < len(data) <= 32*1024*1024 or hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('Headset bundle size or digest did not match')
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        stage.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            members = archive.getmembers()
            if not members or any(not m.isfile() or not m.name.startswith(('ui/','apk-catalog/','frame/android/',
                   'frame/devkit-utils/','frame/openxr-compat/','scripts/')) or '..' in pathlib.PurePosixPath(m.name).parts
                   or m.size > 8*1024*1024 for m in members):
                raise RuntimeError('Invalid headset bundle member')
            archive.extractall(stage, members=members, filter='data')
        if not (stage/'ui/server.py').is_file() or not (stage/'ui/frame_headset_runtime.py').is_file():
            raise RuntimeError('Incomplete headset bundle')
        unit.parent.mkdir(parents=True, exist_ok=True)
        previous_unit = unit.read_bytes() if unit.exists() else None
        previous_receipt = receipt.read_bytes() if receipt.exists() else None
        if action == 'update':
            systemd('stop','frame-control-headset.service')
            bundle.rename(old)
        try:
            stage.rename(bundle)
            unit.write_text('[Unit]\nDescription=Frame Control headset panel\nAfter=gamescope-session.target steamvr.service\n'
              '[Service]\nType=simple\nExecStart=/usr/bin/python3 -I -u '+str(bundle/'ui/frame_headset_runtime.py')+'\n'
              'Restart=no\nKillMode=control-group\nTimeoutStopSec=45\n')
            receipt.write_text(json.dumps({'managedBy':'Frame Control','version':digest[:16]})+'\n')
            systemd('daemon-reload')
            systemd('start','frame-control-headset.service')
            result = show()
        except Exception:
            subprocess.run(['systemctl','--user','stop','frame-control-headset.service'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if bundle.exists(): shutil.rmtree(bundle)
            if old.exists(): old.rename(bundle)
            if previous_unit is None: unit.unlink(missing_ok=True)
            else: unit.write_bytes(previous_unit)
            if previous_receipt is None: receipt.unlink(missing_ok=True)
            else: receipt.write_bytes(previous_receipt)
            subprocess.run(['systemctl','--user','daemon-reload'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if previous_unit: subprocess.run(['systemctl','--user','start','frame-control-headset.service'],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            raise
        if old.exists(): shutil.rmtree(old)
        print(json.dumps({'message':'Installed Frame Control on the headset. '+result['message'],
                          'version':digest[:16],'overlay':overlay}))
finally:
    upload.unlink(missing_ok=True)
    if stage.exists(): shutil.rmtree(stage)
'''


def bundle():
    """Pack app code shipped with the desktop app; never include user data."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w') as archive:
        for dirname in ARCHIVE_DIRS:
            folder = ROOT / dirname
            if not folder.is_dir():
                continue
            for path in sorted(folder.rglob('*')):
                if not path.is_file() or path.is_symlink() or '__pycache__' in path.parts:
                    continue
                if path.suffix not in ('.py', '.html', '.js', '.css', '.json', '.sh', '.gz', '.zst', '.so', '.txt', '.md') and path.name not in ('ssh',):
                    continue
                data = path.read_bytes()
                info = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
                info.size, info.mtime, info.uid, info.gid = len(data), 0, 0, 0
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(info, io.BytesIO(data))
    with io.BytesIO() as out:
        with gzip.GzipFile(fileobj=out, mode='wb', mtime=0) as gz:
            gz.write(raw.getvalue())
        data = out.getvalue()
    if len(data) > MAX_ARCHIVE:
        raise ValueError('Headset app bundle is too large')
    return data


def status(ssh):
    return json.loads(ssh('python3 -', stdin=PROBE, timeout=15))


def change(ssh, action):
    if action not in ('install', 'update', 'open', 'close', 'remove'):
        raise ValueError('Invalid headset panel action')
    current = status(ssh)
    if action in ('install', 'update', 'open') and (current['arch'] != 'aarch64' or current['variant'] != 'vr'):
        raise ValueError('This feature needs a Steam Frame running Frame OS')
    data = bundle() if action in ('install', 'update') else None
    digest = hashlib.sha256(data or b'').hexdigest()
    token = secrets.token_hex(12)
    remote = '/tmp/frame-control-headset-' + token
    try:
        if data is not None:
            ssh('umask 077; cat > ' + remote, stdin=data, text=False, timeout=120)
        return json.loads(ssh(f'python3 - {action} {token} {digest}', stdin=APPLY, timeout=100))
    finally:
        if data is not None:
            try: ssh('rm -f ' + remote, timeout=10)
            except Exception: pass
