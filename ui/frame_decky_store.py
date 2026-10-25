"""Verified official-store archives for the opt-in Frame Decky user service.

Only Frame Control owned plugin folders can be updated or removed. The store
digest validates transport, not plugin trust; store plugins run as the user.
"""
import hashlib
import io
import json
import os
import re
import secrets
import urllib.request
import zipfile

import frame_decky


STORE_URL = 'https://plugins.deckbrew.xyz/plugins'
CDN = 'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/'
MAX_STORE = 4 * 1024 * 1024
MAX_ZIP = 50 * 1024 * 1024
MAX_UNPACKED = 150 * 1024 * 1024
SAFE_FOLDER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
VERSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+\-]{0,39}\Z')


def _urls():
    # Deterministic fixture URLs exist only inside the disposable fake Frame host.
    if os.environ.get('FRAME_E2E_CONTAINER') == '1':
        return (os.environ.get('FRAMEY_STORE_URL', STORE_URL),
                os.environ.get('FRAMEY_CDN_URL', CDN))
    return STORE_URL, CDN


def catalog():
    request = urllib.request.Request(_urls()[0], headers={'User-Agent': 'Frame-Control'})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(MAX_STORE + 1)
    if len(raw) > MAX_STORE:
        raise ValueError('Decky store response is too large')
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError('Invalid Decky store response')
    result = []
    for item in records:
        if not isinstance(item, dict) or item.get('visible') is False:
            continue
        versions = item.get('versions')
        if type(item.get('id')) is not int or item['id'] <= 0 or not isinstance(item.get('name'), str) or not isinstance(versions, list):
            continue
        latest = next((v for v in versions if isinstance(v, dict) and isinstance(v.get('name'), str)
                       and VERSION.fullmatch(v['name']) and isinstance(v.get('hash'), str) and SHA.fullmatch(v['hash'])), None)
        if not latest:
            continue
        tags = item.get('tags') if isinstance(item.get('tags'), list) else []
        author = item.get('author') if isinstance(item.get('author'), str) else ''
        result.append({'id': item['id'], 'name': item['name'][:100],
                       'description': str(item.get('description') or '')[:300],
                       'author': author[:100],
                       'version': latest['name'][:40], 'sha256': latest['hash'],
                       'root': 'root' in tags or '_root' in tags})
    # A repeated store ID makes a clicked row ambiguous: change() resolves by ID
    # and could install a different archive than the one the user reviewed.
    counts = {}
    for item in result:
        counts[item['id']] = counts.get(item['id'], 0) + 1
    return [item for item in result if counts[item['id']] == 1]


def archive_info(data, expected_hash, expected_name):
    if not 1024 < len(data) <= MAX_ZIP or hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError('Plugin archive size or SHA-256 did not match the store')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = archive.infolist()
        if not files or len(files) > 3000 or sum(f.file_size for f in files) > MAX_UNPACKED:
            raise ValueError('Plugin archive exceeds the file or size limit')
        names = [f.filename for f in files]
        manifests = [n for n in names if n.count('/') == 1 and n.endswith('/plugin.json')]
        if len(manifests) != 1:
            raise ValueError('Plugin archive needs one top-level manifest')
        folder = manifests[0].split('/')[0]
        if not SAFE_FOLDER.fullmatch(folder):
            raise ValueError('Invalid plugin folder')
        seen = set()
        for entry in files:
            name = entry.filename
            mode = entry.external_attr >> 16
            kind = mode & 0o170000
            parts = name.split('/')
            if entry.is_dir() and parts[-1] == '':
                parts = parts[:-1]
            if ('\\' in name or name.startswith('/') or
                any(part in ('', '.', '..') for part in parts) or name in seen or
                parts[0] != folder or entry.file_size > 30 * 1024 * 1024 or
                kind not in (0, 0o040000, 0o100000)):
                raise ValueError('Unsafe plugin archive member')
            seen.add(name)
            if entry.is_dir():
                continue
            with archive.open(entry) as source:
                header = source.read(20)
            if header[:4] == b'\x7fELF' and int.from_bytes(header[18:20], 'little') != 183:
                raise ValueError('Plugin contains a non-ARM64 Linux binary: ' + name)
            if header[:2] == b'MZ':
                raise ValueError('Plugin contains a Windows binary: ' + name)
        manifest = json.loads(archive.read(manifests[0]))
        if not isinstance(manifest, dict):
            raise ValueError('Invalid plugin manifest')
        if manifest.get('name') != expected_name:
            raise ValueError('Plugin name differs from the official store')
        flags = manifest.get('flags', [])
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            raise ValueError('Invalid plugin flags')
        if 'root' in flags or '_root' in flags:
            raise ValueError('This plugin needs root and is not supported by the Frame user service')
        return folder


APPLY = r'''
import fcntl,hashlib,json,os,pathlib,shutil,subprocess,sys,zipfile
action,token,plugin_id,digest,folder,version = sys.argv[1:]
base=pathlib.Path.home()/'.local/share/frame-control/decky/plugins'
unit=pathlib.Path.home()/'.config/systemd/user/frame-control-decky.service'
target=base/folder
archive=pathlib.Path('/tmp/frame-control-decky-plugin-'+token)
stage=base/('.frame-control-stage-'+token)
backup=base/('.frame-control-old-'+token)
marker='.frame-control-store.json'
transaction_lock=None
def owned():
    if target.is_symlink() or not target.is_dir(): return False
    try: return json.loads((target/marker).read_text()).get('storeId') == int(plugin_id)
    except (OSError,ValueError): return False
def service(*args):
    p=subprocess.run(['systemctl','--user',*args],capture_output=True,text=True,timeout=25)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip()[-400:] or 'Decky service failed')
try:
    # A desktop request and a headset-panel request must not change the same
    # Decky user service at once. Keep this lock until rollback/cleanup ends.
    base.parent.parent.mkdir(parents=True,exist_ok=True)
    lock_path=base.parent.parent/'decky-transaction.lock'
    transaction_lock=os.fdopen(os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600),'r+b')
    try: fcntl.flock(transaction_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: raise RuntimeError('Another Decky change is in progress; try again after it finishes')
    if not unit.is_file(): raise RuntimeError('Install Frame Control managed Decky first')
    if action not in ('install','update','remove'): raise RuntimeError('Invalid plugin action')
    if action=='install' and (target.exists() or target.is_symlink()): raise RuntimeError('Plugin folder already exists')
    if action in ('update','remove') and not owned(): raise RuntimeError('Only a Frame Control store plugin can be changed')
    running=subprocess.run(['systemctl','--user','is-active','--quiet','frame-control-decky.service']).returncode==0
    if action!='remove':
        data=archive.read_bytes()
        if not 1024<len(data)<=50*1024*1024 or hashlib.sha256(data).hexdigest()!=digest:
            raise RuntimeError('Plugin archive digest mismatch on Frame')
        with zipfile.ZipFile(archive) as z:
            files=z.infolist()
            if not files or len(files)>3000 or sum(f.file_size for f in files)>150*1024*1024:
                raise RuntimeError('Plugin archive too large')
            seen=set()
            for f in files:
                parts=f.filename.split('/')
                if f.is_dir() and parts[-1]=='': parts=parts[:-1]
                kind=f.external_attr>>16&0o170000
                if (not parts or parts[0]!=folder or f.filename.startswith('/') or
                    any(part in ('','.','..') for part in parts) or '\\' in f.filename or
                    f.filename in seen or f.file_size>30*1024*1024 or
                    kind not in (0,0o040000,0o100000)):
                    raise RuntimeError('Unsafe plugin archive')
                seen.add(f.filename)
            stage.mkdir(mode=0o700)
            z.extractall(stage)
            unpacked=stage/folder
            if not unpacked.is_dir(): raise RuntimeError('Missing plugin folder')
            (unpacked/marker).write_text(json.dumps({'storeId':int(plugin_id),'sha256':digest,'version':version})+'\n')
    # Stop even a failed unit before removal to cancel any pending auto-restart.
    if running or action=='remove': service('stop','frame-control-decky.service')
    try:
        if action!='install': target.rename(backup)
        if action!='remove': (stage/folder).rename(target)
        if running: service('start','frame-control-decky.service')
    except Exception:
        if target.exists(): shutil.rmtree(target)
        if backup.exists(): backup.rename(target)
        if running: subprocess.run(['systemctl','--user','start','frame-control-decky.service'],timeout=25)
        raise
    if backup.exists(): shutil.rmtree(backup)
    past={'install':'Installed','update':'Updated','remove':'Removed'}[action]
    print(json.dumps({'message':f'{past} {folder}. Plugin UI in VR is not yet verified.'}))
finally:
    archive.unlink(missing_ok=True)
    if stage.exists(): shutil.rmtree(stage)
    if transaction_lock is not None: transaction_lock.close()
'''


def change(ssh, action, plugin_id, report=lambda stage, percent=None: None):
    if action not in ('install', 'update', 'remove') or type(plugin_id) is not int or plugin_id <= 0:
        raise ValueError('Choose a valid store plugin action')
    report('Checking installed plugins', 5)
    state = frame_decky.status(ssh)
    if not state['managed']:
        raise ValueError('Install Frame Control managed Decky before changing plugins')
    if action != 'remove' and not state['running']:
        raise ValueError('Start Frame Control managed Decky before installing or updating plugins')
    installed = [p for p in state['plugins'] if p.get('storeId') == plugin_id]
    if action == 'install' and installed:
        raise ValueError('This store plugin is already installed; use Update or Remove')
    if action == 'remove':
        if len(installed) != 1:
            raise ValueError('Only an installed Frame Control store plugin can be removed')
        folder = installed[0]['folder']
        plugin = {'sha256': '0' * 64, 'version': 'removed'}
    else:
        report('Reading official store', 15)
        plugin = next((item for item in catalog() if item['id'] == plugin_id), None)
        if not plugin:
            raise ValueError('Plugin is not in the official Decky store')
        if plugin['root']:
            raise ValueError('Root plugins are not supported by the Frame user service')
        existing_name = [p for p in state['plugins'] if p.get('name') == plugin['name']]
        if action == 'install' and existing_name:
            raise ValueError('A plugin with this name is already installed')
        if action == 'update' and len(installed) != 1:
            raise ValueError('Only an installed Frame Control store plugin can be updated')
    data = None
    if action != 'remove':
        report('Downloading plugin archive', 30)
        url = _urls()[1] + plugin['sha256'] + '.zip'
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Frame-Control'}), timeout=35) as response:
            data = response.read(MAX_ZIP + 1)
        report('Verifying plugin archive', 50)
        folder = archive_info(data, plugin['sha256'], plugin['name'])
        if action == 'update' and installed[0]['folder'] != folder:
            raise ValueError('The store changed its plugin folder; remove the old version before installing')
    if not SAFE_FOLDER.fullmatch(folder):
        raise ValueError('Unsafe installed plugin folder')
    token = secrets.token_hex(12)
    remote = '/tmp/frame-control-decky-plugin-' + token
    try:
        if data is not None:
            report('Sending archive to Frame', 65)
            ssh('umask 077; cat > ' + remote, stdin=data, text=False, timeout=120)
        report({'install':'Installing', 'update':'Updating', 'remove':'Removing'}[action] + ' plugin on Frame', 80)
        return json.loads(ssh(f'python3 - {action} {token} {plugin_id} {plugin["sha256"]} {folder} {plugin["version"]}',
                              stdin=APPLY, timeout=90))
    finally:
        if data is not None:
            try: ssh('rm -f ' + remote, timeout=10)
            except Exception: pass
