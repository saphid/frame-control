"""Experimental, removable per-user Decky Loader for Steam Frame (ARM64)."""
import hashlib
import json
import re
import secrets
import urllib.request


REPO = "SteamDeckHomebrew/decky-loader"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
MAX_BINARY = 80 * 1024 * 1024
TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[-.][A-Za-z0-9.-]+)?\Z")


PROBE = r'''
import json, os, pathlib, platform, subprocess, urllib.request
home = pathlib.Path.home()
managed = home / '.local/share/frame-control/decky'
service = home / '.config/systemd/user/frame-control-decky.service'
release = managed / '.frame-control/receipt.json'
legacy = managed / 'settings/release.json'
def active(name, user=False):
    cmd = ['systemctl'] + (['--user'] if user else []) + ['is-active', name]
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
def plugins(folder):
    found = []
    if folder.is_dir() and not folder.is_symlink():
        for child in sorted(folder.iterdir()):
            if child.is_symlink() or not child.is_dir(): continue
            info = child / 'plugin.json'
            if info.is_symlink() or not info.is_file() or info.stat().st_size > 16384: continue
            try:
                data = json.loads(info.read_text())
                marker = child / '.frame-control-store.json'
                try:
                    owned = json.loads(marker.read_text()) if marker.is_file() and not marker.is_symlink() else {}
                except (OSError, ValueError): owned = {}
                found.append({'folder': child.name, 'name': str(data.get('name', child.name))[:80],
                              'author': str(data.get('author', ''))[:80],
                              'storeId': owned.get('storeId') if isinstance(owned.get('storeId'), int) else None,
                              'version': str(owned.get('version', ''))[:40]})
            except (ValueError, OSError, UnicodeError): pass
    return found
os_release = {}
for line in pathlib.Path('/etc/os-release').read_text().splitlines():
    if '=' in line:
        k,v = line.split('=',1); os_release[k] = v.strip('"')
try:
    with urllib.request.urlopen('http://127.0.0.1:8080/json/list', timeout=2) as reply:
        targets = json.load(reply)
    cef = any(x.get('title') == 'SharedJSContext' and 'steamloopback.host' in x.get('url','') for x in targets)
except (OSError, ValueError): cef = False
try:
    metadata = json.loads((release if release.exists() else legacy).read_text())
    version = metadata.get('version') if metadata.get('managedBy') == 'Frame Control' else None
except (OSError, ValueError): version = None
print(json.dumps({'arch':platform.machine(), 'frameOS':os_release.get('VERSION_ID'),
    'variant':os_release.get('VARIANT_ID'), 'build':os_release.get('BUILD_ID'), 'cef':cef,
    'managed':service.is_file() and version is not None, 'running':active('frame-control-decky.service', True),
    'version':version, 'upstreamInstall':pathlib.Path('/etc/systemd/system/plugin_loader.service').exists(),
    'plugins':plugins(managed/'plugins'), 'upstreamPlugins':plugins(home/'homebrew/plugins')}))
'''


APPLY = r'''
import fcntl, hashlib, json, os, pathlib, subprocess, sys
action, token, digest, version = sys.argv[1:]
home = pathlib.Path.home()
base = home / '.local/share/frame-control/decky'
service = home / '.config/systemd/user/frame-control-decky.service'
binary = base / 'PluginLoader'
receipt = base / '.frame-control/receipt.json'
legacy = base / 'settings/release.json'
stage = pathlib.Path('/tmp/frame-control-decky-' + token)
transaction_lock = None
def systemd(*args):
    p = subprocess.run(['systemctl','--user',*args], capture_output=True, text=True, timeout=20)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip() or 'systemd failed')
def owned():
    try: return json.loads((receipt if receipt.exists() else legacy).read_text()).get('managedBy') == 'Frame Control' and service.is_file()
    except (OSError, ValueError): return False
try:
    # The desktop and headset servers are separate processes. Lock the shared
    # user-service transaction on the Frame before inspecting or changing it.
    base.parent.mkdir(parents=True, exist_ok=True)
    lock_path = base.parent / 'decky-transaction.lock'
    transaction_lock = os.fdopen(os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), 'r+b')
    try: fcntl.flock(transaction_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: raise RuntimeError('Another Decky change is in progress; try again after it finishes')
    if action == 'remove':
        if not owned(): raise RuntimeError('No Frame Control managed Decky install to remove')
        systemd('disable','--now','frame-control-decky.service')
        service.unlink()
        systemd('daemon-reload')
        binary.unlink(missing_ok=True)
        receipt.unlink(missing_ok=True)
        if legacy.exists() and json.loads(legacy.read_text()).get('managedBy') == 'Frame Control': legacy.unlink()
        print(json.dumps({'message':'Removed Frame Control managed Decky service and binary. Plugin files were kept. Restart Steam or the headset to clear its menu.'}))
    else:
        if action not in ('install','update'): raise RuntimeError('Invalid Decky action')
        if (home/'homebrew/services/PluginLoader').exists() or pathlib.Path('/etc/systemd/system/plugin_loader.service').exists():
            raise RuntimeError('An upstream Decky installation exists; remove it with its own installer first')
        if action == 'update' and not owned(): raise RuntimeError('No Frame Control managed Decky install to update')
        if action == 'install' and (service.exists() or receipt.exists() or legacy.exists() or binary.exists()):
            raise RuntimeError('Decky files already exist at the managed path')
        data = stage.read_bytes()
        if len(data) > 80*1024*1024 or len(data) < 1024 or hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('Decky binary digest or size did not match')
        if data[:4] != b'\x7fELF' or int.from_bytes(data[18:20], 'little') != 183:
            raise RuntimeError('Decky release is not an ARM64 Linux binary')
        base.mkdir(parents=True, exist_ok=True)
        (base/'plugins').mkdir(exist_ok=True)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        service.parent.mkdir(parents=True, exist_ok=True)
        old_binary = binary.read_bytes() if binary.exists() else None
        old_receipt = receipt.read_bytes() if receipt.exists() else legacy.read_bytes() if legacy.exists() else None
        old_service = service.read_bytes() if service.exists() else None
        if old_service: systemd('stop','frame-control-decky.service')
        try:
            next_binary = base / 'PluginLoader.next'
            next_binary.write_bytes(data)
            os.replace(next_binary, binary)
            binary.chmod(0o700)
            text = ('[Unit]\nDescription=Decky Loader (Frame Control experimental user install)\n'
              'After=default.target\n[Service]\nType=simple\nRestart=on-failure\n'
              'RestartSec=5\nExecStart='+str(binary)+'\n'
              'Environment=UNPRIVILEGED_PATH='+str(base)+'\n'
              'Environment=PRIVILEGED_PATH='+str(base)+'\n'
              'Environment=CHOWN_PLUGIN_PATH=0\nEnvironment=LIVE_RELOAD=0\n'
              'Environment=USE_CEF_CLOSE_WORKAROUND=0\nEnvironment=KEEP_SYSTEMD_SERVICE=1\n'
              '[Install]\nWantedBy=default.target\n')
            service.write_text(text)
            receipt.write_text(json.dumps({'managedBy':'Frame Control','version':version,'sha256':digest})+'\n')
            if legacy.exists() and json.loads(legacy.read_text()).get('managedBy') == 'Frame Control': legacy.unlink()
            systemd('daemon-reload')
            systemd('enable','--now','frame-control-decky.service')
            systemd('is-active','frame-control-decky.service')
        except Exception:
            (base/'PluginLoader.next').unlink(missing_ok=True)
            if old_binary is None: binary.unlink(missing_ok=True)
            else: binary.write_bytes(old_binary); binary.chmod(0o700)
            if old_receipt is None: receipt.unlink(missing_ok=True)
            else: receipt.write_bytes(old_receipt)
            if old_service is None: service.unlink(missing_ok=True)
            else: service.write_bytes(old_service)
            subprocess.run(['systemctl','--user','daemon-reload'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if old_service: subprocess.run(['systemctl','--user','start','frame-control-decky.service'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            raise
        print(json.dumps({'message':'Decky Loader '+version+' is running as a user service. The VR menu is experimental.'}))
finally:
    stage.unlink(missing_ok=True)
    if transaction_lock is not None: transaction_lock.close()
'''


def status(ssh):
    return json.loads(ssh('python3 -', stdin=PROBE, timeout=15))


def release_binary():
    request = urllib.request.Request(API, headers={'User-Agent': 'Frame-Control'})
    with urllib.request.urlopen(request, timeout=20) as response:
        info = json.load(response)
    version = info.get('tag_name')
    if not isinstance(version, str) or not TAG.fullmatch(version):
        raise ValueError('Invalid Decky release version')
    asset = next((a for a in info.get('assets', []) if a.get('name') == 'PluginLoader-arm64'), None)
    expected_url = f'https://github.com/{REPO}/releases/download/{version}/PluginLoader-arm64'
    if not asset or asset.get('browser_download_url') != expected_url or not isinstance(asset.get('size'), int) or not 1024 < asset['size'] <= MAX_BINARY:
        raise ValueError('Decky release has no valid ARM64 asset')
    digest = asset.get('digest', '')
    if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('Decky release has no published SHA-256 digest')
    with urllib.request.urlopen(urllib.request.Request(expected_url, headers={'User-Agent': 'Frame-Control'}), timeout=45) as response:
        data = response.read(MAX_BINARY + 1)
    if len(data) != asset['size'] or hashlib.sha256(data).hexdigest() != digest[7:]:
        raise ValueError('Decky download did not match its published digest')
    if data[:4] != b'\x7fELF' or int.from_bytes(data[18:20], 'little') != 183:
        raise ValueError('Decky download is not an ARM64 Linux binary')
    return version, digest[7:], data


def change(ssh, action):
    if action not in ('install', 'update', 'remove'):
        raise ValueError('Invalid Decky action')
    current = status(ssh)
    if action == 'remove':
        if not current['managed']:
            raise ValueError('No Frame Control managed Decky install to remove')
        return json.loads(ssh('python3 - remove none none none', stdin=APPLY, timeout=45))
    if current['arch'] != 'aarch64' or current['variant'] != 'vr' or not current['cef']:
        raise ValueError('Decky needs a Steam Frame with an active Steam CEF debug page')
    if current['upstreamInstall']:
        raise ValueError('An upstream Decky installation exists; use its own installer')
    if action == 'install' and current['managed']:
        raise ValueError('Decky is already installed; use Update')
    if action == 'update' and not current['managed']:
        raise ValueError('Decky is not installed by Frame Control')
    version, digest, data = release_binary()
    token = secrets.token_hex(12)
    remote = '/tmp/frame-control-decky-' + token
    try:
        ssh('umask 077; cat > ' + remote, stdin=data, text=False, timeout=120)
        result = ssh(f'python3 - {action} {token} {digest} {version}', stdin=APPLY, timeout=50)
        return json.loads(result)
    finally:
        try: ssh('rm -f ' + remote, timeout=10)
        except Exception: pass
