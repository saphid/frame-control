"""Verified official-store archives for the opt-in Frame Decky user service.

Only Frame Control owned plugin folders can be updated or removed. The store
digest validates transport, not plugin trust; store plugins run as the user.
"""
import base64
import gzip
import hashlib
import io
import json
import os
import re
import secrets
import urllib.request
import zipfile
from pathlib import Path

import frame_decky
import framey_compatibility


STORE_URL = 'https://plugins.deckbrew.xyz/plugins'
CDN = 'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/'
MAX_STORE = 4 * 1024 * 1024
MAX_ZIP = 50 * 1024 * 1024
MAX_UNPACKED = 150 * 1024 * 1024
SAFE_FOLDER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
FILESERVER_DIGEST = '7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0'
FILESERVER_BINARIES = {
    'x86_64': '5e90efd1bf5163bef1686045f4714ad0e4fd0f54edb037fce8cdb06c58177bcb',
    'aarch64': '86b80021ebd62ed619eba065757c1122defa5a74b2c045aa44a0c6b4403a508a',
}
FILESERVER_ORIGINAL = 'd9eab8559c87c01736188bc676f3b4b44dee47cf952b6e571c770d1ea61733e9'

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
    unique = [item for item in result if counts[item['id']] == 1]
    for item in unique:
        if item['id'] == 60 and item['name'] == 'DeckyFileServer' and item['sha256'] == FILESERVER_DIGEST:
            item['root'] = False  # Exact managed adaptation runs as the Frame user.
        item['compatibility'] = framey_compatibility.lookup(item['id'], item['sha256'], item['version'])
    return unique


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
        fileserver = (expected_hash == FILESERVER_DIGEST and expected_name == 'DeckyFileServer'
                      and folder == 'DeckyFileServer')
        seen = {}
        for entry in files:
            name = entry.filename
            mode = entry.external_attr >> 16
            kind = mode & 0o170000
            parts = name.split('/')
            if entry.is_dir() and parts[-1] == '':
                parts = parts[:-1]
            if ('\\' in name or name.startswith('/') or
                any(part in ('', '.', '..') for part in parts) or
                parts[0] != folder or entry.file_size > 30 * 1024 * 1024 or
                kind not in (0, 0o040000, 0o100000)):
                raise ValueError('Unsafe plugin archive member')
            prior = seen.get(name)
            if prior is not None:
                # Some official ZIPs repeat unchanged files with execute-bit
                # differences. Reject any content or other mode ambiguity.
                old_mode = prior.external_attr >> 16
                if (prior.file_size != entry.file_size or
                    ((old_mode ^ mode) & ~0o111) or
                    archive.read(prior) != archive.read(entry)):
                    raise ValueError('Unsafe plugin archive member')
            else:
                seen[name] = entry
            if entry.is_dir():
                continue
            with archive.open(entry) as source:
                header = source.read(20)
            if header[:4] == b'\x7fELF' and int.from_bytes(header[18:20], 'little') != 183:
                if not (fileserver and name == 'DeckyFileServer/bin/backend'
                        and hashlib.sha256(archive.read(entry)).hexdigest() == FILESERVER_ORIGINAL):
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
        if ('root' in flags or '_root' in flags) and not fileserver:
            raise ValueError('This plugin needs root and is not supported by the Frame user service')
        return folder


def apply_script(plugin_id, digest):
    """Deliver offline native assets only to the exact managed adaptation."""
    if plugin_id != 60 or digest != FILESERVER_DIGEST:
        return APPLY
    assets = Path(__file__).parent/'vendor/deckyfileserver-1.2.0'
    payloads = {}
    for arch, expected in FILESERVER_BINARIES.items():
        packed = (assets/f'{arch}.gz').read_bytes()
        data = gzip.decompress(packed)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Bundled DeckyFileServer SHA-256 mismatch')
        payloads[arch] = base64.b64encode(packed).decode('ascii')
    # Python stdin, never shell arguments. The Frame rechecks hash and ELF machine.
    return ('FRAMEY_FILESERVER_BINARIES = '+repr(payloads)+'\n'
            +'FRAMEY_FILESERVER_HASHES = '+repr(FILESERVER_BINARIES)+'\n'+APPLY)


APPLY = r'''
import base64,fcntl,gzip,hashlib,json,os,pathlib,platform,shutil,subprocess,sys,zipfile
action,token,plugin_id,digest,folder,version,expected_installed = sys.argv[1:]
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
    if action in ('update','remove') and expected_installed!='-':
        current=json.loads((target/marker).read_text()).get('sha256')
        if current!=expected_installed:
            raise RuntimeError('Installed plugin changed; refresh the installed list and try again')
    running=subprocess.run(['systemctl','--user','is-active','--quiet','frame-control-decky.service']).returncode==0
    if action!='remove':
        data=archive.read_bytes()
        if not 1024<len(data)<=50*1024*1024 or hashlib.sha256(data).hexdigest()!=digest:
            raise RuntimeError('Plugin archive digest mismatch on Frame')
        with zipfile.ZipFile(archive) as z:
            files=z.infolist()
            if not files or len(files)>3000 or sum(f.file_size for f in files)>150*1024*1024:
                raise RuntimeError('Plugin archive too large')
            fileserver=(int(plugin_id)==60 and digest=='7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0' and folder=='DeckyFileServer')
            manifest=json.loads(z.read(folder+'/plugin.json'))
            if not isinstance(manifest,dict): raise RuntimeError('Invalid plugin manifest')
            flags=manifest.get('flags',[])
            if not isinstance(flags,list) or not all(isinstance(flag,str) for flag in flags):
                raise RuntimeError('Invalid plugin flags')
            if ('root' in flags or '_root' in flags) and not fileserver:
                raise RuntimeError('Root plugins are not supported by the Frame user service')
            seen={}
            for f in files:
                parts=f.filename.split('/')
                if f.is_dir() and parts[-1]=='': parts=parts[:-1]
                kind=f.external_attr>>16&0o170000
                if (not parts or parts[0]!=folder or f.filename.startswith('/') or
                    any(part in ('','.','..') for part in parts) or '\\' in f.filename or
                    f.file_size>30*1024*1024 or
                    kind not in (0,0o040000,0o100000)):
                    raise RuntimeError('Unsafe plugin archive')
                prior=seen.get(f.filename)
                if prior is not None:
                    # Match desktop validation before zipfile overwrites a
                    # repeated member during extraction.
                    old_mode=prior.external_attr>>16
                    if (prior.file_size!=f.file_size or
                        ((old_mode^ (f.external_attr>>16)) & ~0o111) or
                        z.read(prior)!=z.read(f)):
                        raise RuntimeError('Unsafe plugin archive')
                else: seen[f.filename]=f
                if not f.is_dir():
                    with z.open(f) as source: header=source.read(20)
                    if header[:4]==b'\x7fELF' and int.from_bytes(header[18:20],'little')!=183:
                        if not (fileserver and f.filename==folder+'/bin/backend' and
                                hashlib.sha256(z.read(f)).hexdigest()=='d9eab8559c87c01736188bc676f3b4b44dee47cf952b6e571c770d1ea61733e9'):
                            raise RuntimeError('Plugin contains a non-ARM64 Linux binary')
                    if header[:2]==b'MZ': raise RuntimeError('Plugin contains a Windows binary')
            stage.mkdir(mode=0o700)
            z.extractall(stage)
            # zipfile drops execute bits. Legacy plugins also publish shebang
            # entrypoints as 0644 because Decky's installer chmods recursively.
            # Grant only owner execute for scripts or declared executables;
            # never restore archive privilege/write bits or mark other data executable.
            for member in files:
                if member.is_dir(): continue
                entry=stage/member.filename
                with entry.open('rb') as source: script=source.read(2)==b'#!'
                if script or (member.external_attr>>16)&0o111:
                    entry.chmod(entry.stat().st_mode|0o100)
            unpacked=stage/folder
            if not unpacked.is_dir(): raise RuntimeError('Missing plugin folder')
            compat_shims=[]
            # GPL source and reproducible build recipe ship with Frame Control.
            # The exact official helper is x86_64; this plugin needs no root.
            if int(plugin_id)==60 and digest=='7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0' and folder=='DeckyFileServer':
                helper=unpacked/'bin/backend'
                source=unpacked/'main.py'
                if hashlib.sha256(helper.read_bytes()).hexdigest()!='d9eab8559c87c01736188bc676f3b4b44dee47cf952b6e571c770d1ea61733e9':
                    raise RuntimeError('DeckyFileServer original helper mismatch')
                if hashlib.sha256(source.read_bytes()).hexdigest()!='4fb60745c083465d198d84e1abb0afdb59695d9eec3c873b0b35247676af05c3':
                    raise RuntimeError('DeckyFileServer Python source mismatch')
                arch=platform.machine()
                machine={'aarch64':183,'x86_64':62}.get(arch)
                hashes=globals().get('FRAMEY_FILESERVER_HASHES',{})
                packed=globals().get('FRAMEY_FILESERVER_BINARIES',{}).get(arch)
                if not machine or not packed: raise RuntimeError('Missing native DeckyFileServer helper')
                native=gzip.decompress(base64.b64decode(packed,validate=True))
                if (hashlib.sha256(native).hexdigest()!=hashes.get(arch) or native[:4]!=b'\x7fELF'
                    or int.from_bytes(native[18:20],'little')!=machine):
                    raise RuntimeError('DeckyFileServer native helper mismatch')
                helper.write_bytes(native)
                helper.chmod(0o700)
                manifest_path=unpacked/'plugin.json'
                manifest=json.loads(manifest_path.read_text())
                if manifest.get('name')!='DeckyFileServer' or manifest.get('api_version')!=1 or manifest.get('flags')!=['_root']:
                    raise RuntimeError('DeckyFileServer manifest mismatch')
                manifest['flags']=[]
                manifest['publish']['tags']=[tag for tag in manifest['publish']['tags'] if tag not in ('root','_root')]
                manifest_path.write_text(json.dumps(manifest)+'\n')
                text=source.read_text()
                # Go flag parsing stops at an empty positional argument. Filter
                # omitted boolean flags so -disablethumbnails actually takes effect.
                text=text.replace('                    ],\n                    stdout=PIPE,',
                                  '                    ] if arg],\n                    stdout=PIPE,')
                text=text.replace('                    [\n                        f"{decky.DECKY_PLUGIN_DIR}',
                                  '                    [arg for arg in [\n                        f"{decky.DECKY_PLUGIN_DIR}')
                # Hostname DNS is not guaranteed on Frame OS. A UDP connect
                # selects the kernel source address without sending any packet.
                text=text.replace('        return socket.gethostbyname(socket.gethostname())',
                    '        try:\n            return socket.gethostbyname(socket.gethostname())\n'
                    '        except OSError:\n            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:\n'
                    '                try:\n                    probe.connect(("192.0.2.1", 9))\n'
                    '                    return probe.getsockname()[0]\n'
                    '                except OSError:\n                    return "127.0.0.1"')
                # Configure thumbnail policy before launching the helper.
                old='            if "server_running" in status:\n                await Plugin.set_server_running(self, status["server_running"])\n            if "disable_thumbnails" in status:\n                await Plugin.set_disable_thumbnails(self, status["disable_thumbnails"])'
                new='            if "disable_thumbnails" in status:\n                await Plugin.set_disable_thumbnails(self, status["disable_thumbnails"])\n            if "server_running" in status:\n                await Plugin.set_server_running(self, status["server_running"])'
                if old not in text: raise RuntimeError('DeckyFileServer start configuration changed')
                source.write_text(text.replace(old,new))
                compat_shims.append('deckyfileserver-user-native')
            # Shotty 0.1.0 imports click.get_app_dir but never calls it. Its
            # official ZIP omits click and Decky's bundled Python lacks it.
            # Supply the Linux function only inside this exact plugin's
            # py_modules path; other plugins keep their original imports.
            if int(plugin_id)==53 and digest=='ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe' and folder=='Shotty':
                compat=unpacked/'py_modules/click.py'
                if compat.exists(): raise RuntimeError('Shotty compatibility module collides with archive')
                compat.parent.mkdir(parents=True,exist_ok=True)
                compat.write_text(
                    '"""Frame Control Linux compatibility for Shotty 0.1.0."""\n'
                    'import os\n'
                    'def get_app_dir(app_name, roaming=True, force_posix=False):\n'
                    '    if not isinstance(app_name, str) or not app_name:\n'
                    '        raise ValueError("app_name must be a nonempty string")\n'
                    '    base = os.environ.get("XDG_CONFIG_HOME")\n'
                    '    if not base or not os.path.isabs(base):\n'
                    '        base = os.path.join(os.path.expanduser("~"), ".config")\n'
                    '    return os.path.join(base, app_name)\n',encoding='utf-8')
                compat_shims.append('shotty-click-app-dir')
            # These legacy backends launch system dbus-send (1.1.6 via /bin/sh).
            # Decky's PyInstaller LD_LIBRARY_PATH selects bundled libtinfo built
            # against newer glibc than Frame OS. Restore its saved system path
            # only in the copied subprocess environment; retain legacy self calls.
            music_digests={
                12:'246b89fd653c60a735b1cc401d1b0937d5cb969eea9024561661ff741f081d62',
                111:'3f56a3f56034b277ea74a2c37cc84133b69e382aa6bcb0b43876776aac737ed9',
            }
            if digest==music_digests.get(int(plugin_id)) and folder=='MusicControl':
                main=unpacked/'main.py'
                source=main.read_text(encoding='utf-8')
                old='        env = os.environ.copy()\n'
                if source.count(old)!=1:
                    raise RuntimeError('Music Control compatibility source changed')
                source=source.replace(old,old+'        env["LD_LIBRARY_PATH"] = env.get("LD_LIBRARY_PATH_ORIG", "")\n')
                main.write_text(source,encoding='utf-8')
                compat_shims.append('music-control-system-dbus-env')
            # Recheck under the transaction lock. Another store operation may
            # have installed a colliding name while this archive downloaded.
            proposed_name=json.loads((unpacked/'plugin.json').read_text()).get('name')
            for peer in base.iterdir():
                if peer==target or peer.is_symlink() or not peer.is_dir(): continue
                manifest=peer/'plugin.json'
                if manifest.is_symlink() or not manifest.is_file(): continue
                try:
                    if manifest.stat().st_size>16384: continue
                    peer_data=json.loads(manifest.read_text())
                    if isinstance(peer_data,dict) and peer_data.get('name')==proposed_name:
                        raise RuntimeError('A different plugin with this name is already installed')
                except (OSError,ValueError,UnicodeError): continue
            record={'storeId':int(plugin_id),'sha256':digest,'version':version}
            if compat_shims: record['compatShims']=compat_shims
            (unpacked/marker).write_text(json.dumps(record)+'\n')
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


def change(ssh, action, plugin_id, report=lambda stage, percent=None: None, reviewed_hash=None):
    if action not in ('install', 'update', 'remove') or type(plugin_id) is not int or plugin_id <= 0:
        raise ValueError('Choose a valid store plugin action')
    if reviewed_hash is not None and (action == 'remove' or not isinstance(reviewed_hash, str)
                                      or not SHA.fullmatch(reviewed_hash)):
        raise ValueError('Invalid reviewed store version')
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
        if reviewed_hash is not None and plugin['sha256'] != reviewed_hash:
            raise ValueError('The official store version changed; refresh the store and review it again')
        if plugin['root']:
            raise ValueError('Root plugins are not supported by the Frame user service')
        if plugin.get('compatibility', {}).get('blockInstall'):
            raise ValueError(plugin['compatibility']['reason'])
        # Decky routes backend calls by plugin name. A store update may rename
        # its plugin, so check names for updates as well as fresh installs.
        existing_name = [p for p in state['plugins'] if p.get('name') == plugin['name']
                         and (action == 'install' or p.get('storeId') != plugin_id)]
        if existing_name:
            raise ValueError('A different plugin with this name is already installed')
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
    previous = installed[0].get('sha256') if action != 'install' else None
    expected_installed = previous if isinstance(previous, str) and SHA.fullmatch(previous) else '-'
    token = secrets.token_hex(12)
    remote = '/tmp/frame-control-decky-plugin-' + token
    try:
        if data is not None:
            report('Sending archive to Frame', 65)
            ssh('umask 077; cat > ' + remote, stdin=data, text=False, timeout=120)
        report({'install':'Installing', 'update':'Updating', 'remove':'Removing'}[action] + ' plugin on Frame', 80)
        return json.loads(ssh(f'python3 - {action} {token} {plugin_id} {plugin["sha256"]} {folder} {plugin["version"]} {expected_installed}',
                              stdin=apply_script(plugin_id, plugin["sha256"]), timeout=90))
    finally:
        if data is not None:
            try: ssh('rm -f ' + remote, timeout=10)
            except Exception: pass
