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
from pathlib import Path
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
LOCALSEND_DIGEST = 'e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7'
LOCALSEND_ORIGINAL = 'd448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843'
LOCALSEND_MAIN = 'db03f9201fe50b75dea99a7a05b54ec3f352d1bdfe174115b0e569154198d8ad'
LOCALSEND_AARCH64 = 'e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae'
NETWORK_SENTINEL_DIGEST = 'd3e07f40a0c800e72d15594e03c8c61e9bf3092524a578a0260520e735b971a5'
NETWORK_SENTINEL_MAIN = '2baa390cb66dc267e8f04e61ba1edc43af75115ad5e453d308f6bf26ed70b6b9'
BATTERY_TRACKER_DIGEST = '91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94'
BATTERY_TRACKER_MAIN = '2303ec70c262f1cbfe1c8c138770c6e7c3496827e748e679c94ca43ff9f28725'
RADIYO_DIGEST = '647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43'
RADIYO_MAIN = '868332dbe3feb1e7a81e35a0c01fdc0a6b68421ec1f84e238564bfad4946e87e'
STORAGE_CLEANER_DIGEST = '1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591'
STORAGE_CLEANER_MAIN = '6fd4d012568edae22ba421495455b3c02899155e4c7484f5aa5be6ce9b14dd5f'

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
        if ((item['id'] == 60 and item['name'] == 'DeckyFileServer' and item['sha256'] == FILESERVER_DIGEST)
            or (item['id'] == 114 and item['name'] == 'Network Sentinel' and item['sha256'] == NETWORK_SENTINEL_DIGEST)
            or (item['id'] == 67 and item['name'] == 'Battery Tracker' and item['sha256'] == BATTERY_TRACKER_DIGEST)):
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
        localsend = (expected_hash == LOCALSEND_DIGEST and expected_name == 'Decky Localsend'
                     and folder == 'decky-localsend')
        network_sentinel = (expected_hash == NETWORK_SENTINEL_DIGEST and expected_name == 'Network Sentinel'
                            and folder == 'network-sentinel')
        battery_tracker = (expected_hash == BATTERY_TRACKER_DIGEST and expected_name == 'Battery Tracker'
                           and folder == 'steam-deck-battery-tracker')
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
                if not ((fileserver and name == 'DeckyFileServer/bin/backend'
                         and hashlib.sha256(archive.read(entry)).hexdigest() == FILESERVER_ORIGINAL)
                        or (localsend and name == 'decky-localsend/bin/localsend-core'
                            and hashlib.sha256(archive.read(entry)).hexdigest() == LOCALSEND_ORIGINAL)):
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
        if ('root' in flags or '_root' in flags) and not (fileserver or network_sentinel or battery_tracker):
            raise ValueError('This plugin needs root and is not supported by the Frame user service')
        if localsend and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != LOCALSEND_MAIN:
            raise ValueError('LocalSend Python source differs from the pinned archive')
        if network_sentinel and (flags != ['debug', '_root'] or manifest.get('api_version') != 1
                                 or hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != NETWORK_SENTINEL_MAIN):
            raise ValueError('Network Sentinel manifest or source differs from the pinned archive')
        if battery_tracker and (flags != ['_root'] or 'api_version' in manifest
                                or hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != BATTERY_TRACKER_MAIN):
            raise ValueError('Battery Tracker manifest or source differs from the pinned archive')
        if (expected_hash == RADIYO_DIGEST and expected_name == 'RadiYo!' and folder == 'radiyo-steam-deck'
                and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != RADIYO_MAIN):
            raise ValueError('RadiYo source differs from the pinned archive')
        if (expected_hash == STORAGE_CLEANER_DIGEST and expected_name == 'Storage Cleaner'
                and folder == 'decky-storage-cleaner'
                and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != STORAGE_CLEANER_MAIN):
            raise ValueError('Storage Cleaner source differs from the pinned archive')
        return folder


DECKYSPY_DIGEST = '2d431a89826ed5cf3fd37258373eb3b46c841c39795aa8b25f83e59f4eee87c7'
PSUTIL_DIGESTS = {
    'x86_64': '076a2d2f923fd4821644f5ba89f059523da90dc9014e85f8e45a5774ca5bc6f9',
    'aarch64': 'b0726cecd84f9474419d67252add4ac0cd9811b04d61123054b9fb6f57df6e9e',
}


def apply_script(plugin_id, digest):
    """Deliver verified offline dependencies only to exact managed archives."""
    if plugin_id == 125 and digest == LOCALSEND_DIGEST:
        packed = (Path(__file__).parent/'vendor/localsend-0.4.5/aarch64.gz').read_bytes()
        data = gzip.decompress(packed)
        if hashlib.sha256(data).hexdigest() != LOCALSEND_AARCH64:
            raise ValueError('Bundled LocalSend ARM64 helper SHA-256 mismatch')
        return ('FRAMEY_LOCALSEND_AARCH64 = '+repr(base64.b64encode(packed).decode('ascii'))+'\n'+APPLY)
    if plugin_id == 60 and digest == FILESERVER_DIGEST:
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
    if not ((plugin_id == 89 and digest == DECKYSPY_DIGEST)
            or (plugin_id == 114 and digest == NETWORK_SENTINEL_DIGEST)):
        return APPLY
    wheels = {}
    for arch, expected in PSUTIL_DIGESTS.items():
        data = (Path(__file__).parent/'vendor/psutil-7.2.2'/f'{arch}.whl').read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Bundled psutil dependency SHA-256 mismatch')
        wheels[arch] = base64.b64encode(data).decode('ascii')
    # stdin is Python source, never shell arguments or a shared remote temp file.
    source = 'FRAMEY_BACKEND_WHEELS = '+repr(wheels)+'\n'
    if plugin_id == 89:
        battery = (Path(__file__).parent/'framey_battery.py').read_text(encoding='utf-8')
        source += 'FRAMEY_BACKEND_BATTERY_SOURCE = '+repr(battery)+'\n'
    return source+APPLY


APPLY = r'''
import base64,fcntl,gzip,hashlib,io,json,os,pathlib,platform,shutil,subprocess,sys,zipfile
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
            localsend=(int(plugin_id)==125 and digest=='e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7' and folder=='decky-localsend')
            network_sentinel=(int(plugin_id)==114 and digest=='d3e07f40a0c800e72d15594e03c8c61e9bf3092524a578a0260520e735b971a5' and folder=='network-sentinel')
            battery_tracker=(int(plugin_id)==67 and digest=='91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94' and folder=='steam-deck-battery-tracker')
            manifest=json.loads(z.read(folder+'/plugin.json'))
            if not isinstance(manifest,dict): raise RuntimeError('Invalid plugin manifest')
            flags=manifest.get('flags',[])
            if not isinstance(flags,list) or not all(isinstance(flag,str) for flag in flags):
                raise RuntimeError('Invalid plugin flags')
            if ('root' in flags or '_root' in flags) and not (fileserver or network_sentinel or battery_tracker):
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
                        if not ((fileserver and f.filename==folder+'/bin/backend' and
                                 hashlib.sha256(z.read(f)).hexdigest()=='d9eab8559c87c01736188bc676f3b4b44dee47cf952b6e571c770d1ea61733e9')
                                or (localsend and f.filename==folder+'/bin/localsend-core' and
                                    hashlib.sha256(z.read(f)).hexdigest()=='d448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843')):
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
            if localsend:
                helper=unpacked/'bin/localsend-core'
                source=unpacked/'main.py'
                if hashlib.sha256(helper.read_bytes()).hexdigest()!='d448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843':
                    raise RuntimeError('LocalSend original helper mismatch')
                if hashlib.sha256(source.read_bytes()).hexdigest()!='db03f9201fe50b75dea99a7a05b54ec3f352d1bdfe174115b0e569154198d8ad':
                    raise RuntimeError('LocalSend Python source mismatch')
                if manifest.get('name')!='Decky Localsend' or manifest.get('api_version')!=1 or manifest.get('flags')!=[]:
                    raise RuntimeError('LocalSend manifest mismatch')
                arch=platform.machine()
                if arch=='aarch64':
                    packed=globals().get('FRAMEY_LOCALSEND_AARCH64')
                    if not isinstance(packed,str): raise RuntimeError('Missing LocalSend ARM64 helper')
                    native=gzip.decompress(base64.b64decode(packed,validate=True))
                    if (hashlib.sha256(native).hexdigest()!='e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae'
                        or native[:4]!=b'\x7fELF' or int.from_bytes(native[18:20],'little')!=183):
                        raise RuntimeError('LocalSend ARM64 helper mismatch')
                    helper.write_bytes(native)
                elif arch!='x86_64':
                    raise RuntimeError('Unsupported LocalSend helper architecture')
                helper.chmod(0o700)
                compat_shims.append('localsend-digest-native')
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
                # The helper always calls ListenAndServeTLS. The published panel
                # prints HTTP when uploads are disabled and hard-codes a Deck
                # hostname that the Frame does not provide. Keep only the
                # actual address returned by this backend.
                frontend=unpacked/'dist/index.js'
                original=frontend.read_bytes()
                if hashlib.sha256(original).hexdigest()!='791015d8b3f234fad89ce422b09fb32bbad05e7c867d501706cfbcf9f7c6187f':
                    raise RuntimeError('DeckyFileServer frontend source changed')
                bundle=original.decode('utf-8')
                old_url="""            window.SP_REACT.createElement(DFL.Field, { inlineWrap: "shift-children-below", label: "Server Address", bottomSeparator: "none" },
                "http",
                state.allow_uploads ? "s" : "",
                "://steamdeck:",
                state.port),
            window.SP_REACT.createElement(DFL.Field, { inlineWrap: "shift-children-below" },
                "http",
                state.allow_uploads ? "s" : "",
                "://",
                state.ip_address,
                ":",
                state.port),
"""
                new_url="""            window.SP_REACT.createElement(DFL.Field, { inlineWrap: "shift-children-below", label: "Server Address", bottomSeparator: "none" },
                "https://",
                state.ip_address,
                ":",
                state.port),
"""
                if bundle.count(old_url)!=1: raise RuntimeError('DeckyFileServer address UI changed')
                frontend.write_text(bundle.replace(old_url,new_url),encoding='utf-8')
                compat_shims.append('deckyfileserver-user-native')
                compat_shims.append('deckyfileserver-https-address')
            # Simple Timer 1.0.0 has annotation-only task state, orphaned
            # replacement tasks and canceled deadlines that resume on restart.
            # Preserve its API1 instance convention and upstream license.
            if int(plugin_id)==96 and digest=='973d927e9d9a1feec04679c564af7e389a729b6735d2a988ffc2cb46ce4eb312' and folder=='simple-timer':
                main=unpacked/'main.py'
                source=main.read_text(encoding='utf-8')
                start='    async def start_timer('; end='    async def load_recents('
                if source.count(start)!=1 or source.count(end)!=1: raise RuntimeError('Simple Timer compatibility source changed')
                a=source.index(start); b=source.index(end,a)
                source=source[:a]+"""    async def _stop_timer(self):
        # Call only under timer_lock. Joining prevents a replaced task from
        # updating the new timer or sending a stale completion notification.
        task, self.timer_task = self.timer_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def start_timer(self, seconds: int):
        async with self.timer_lock:
            await self._stop_timer()
            recent = await self.settings_getSetting(settings_key_recent_timers, [])
            await self.settings_setSetting(settings_key_recent_timers, [seconds] + recent[:4])
            deadline = time.time() + seconds
            await self.settings_setSetting(settings_key_timer_end, deadline)
            await self.settings_commit()
            self.seconds_remaining = seconds
            self.timer_task = self.loop.create_task(self.timer_handler(datetime.fromtimestamp(deadline)))
            await self.load_recents()
            await self.load_remaining_seconds()

    async def timer_handler(self, timer_end: datetime):
        while True:
            remaining = timer_end.timestamp() - time.time()
            if remaining <= 0:
                break
            await asyncio.sleep(min(5, remaining))
            self.seconds_remaining = max(0, timer_end.timestamp() - time.time())
            await self.load_remaining_seconds()
        async with self.timer_lock:
            if self.timer_task is not asyncio.current_task():
                return
            self.timer_task = None
            self.seconds_remaining = 0
            await self.settings_setSetting(settings_key_timer_end, None)
            await self.settings_commit()
            await self.load_remaining_seconds()
            subtle = await self.settings_getSetting(settings_key_subtle_mode, False)
            if remaining <= -10:
                await decky.emit("simple_timer_event", "Your timer has expired!", True)
            else:
                await decky.emit("simple_timer_event", "Your session has ended!", subtle)

    async def cancel_timer(self):
        async with self.timer_lock:
            await self._stop_timer()
            self.seconds_remaining = 0
            await self.settings_setSetting(settings_key_timer_end, None)
            await self.settings_commit()
            await self.load_remaining_seconds()

"""+source[b:]
                start='    async def _main('; end='    async def _uninstall('
                if source.count(start)!=1 or source.count(end)!=1: raise RuntimeError('Simple Timer compatibility source changed')
                a=source.index(start); b=source.index(end,a)
                source=source[:a]+"""    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self.timer_task = None
        self.timer_lock = asyncio.Lock()
        self.seconds_remaining = 0
        await self.settings_read()
        deadline = await self.settings_getSetting(settings_key_timer_end, None)
        if deadline is not None:
            self.seconds_remaining = max(0, deadline - time.time())
            if self.seconds_remaining > 0:
                # Resume the exact deadline without adding another recent timer.
                self.timer_task = self.loop.create_task(self.timer_handler(datetime.fromtimestamp(deadline)))
            else:
                await self.cancel_timer()
        await self.load_recents()
        await self.load_subtle_mode()
        decky.logger.info("Simple Timer has been initialised.")

    async def _unload(self):
        async with self.timer_lock:
            # Backend unload is a pause; only explicit cancel clears the deadline.
            await self._stop_timer()
        decky.logger.info("Simple Timer has been unloaded.")

"""+source[b:]
                main.write_text(source,encoding='utf-8')
                compat_shims.append('simple-timer-lifecycle')
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
            # Both exact official archives omit psutil. Install the pinned BSD
            # native wheel in the plugin folder only; never use pip or system paths.
            deckyspy=(int(plugin_id)==89 and digest=='2d431a89826ed5cf3fd37258373eb3b46c841c39795aa8b25f83e59f4eee87c7' and folder=='decky-spy')
            if deckyspy or network_sentinel:
                arch=platform.machine()
                pins={
                    'x86_64':'076a2d2f923fd4821644f5ba89f059523da90dc9014e85f8e45a5774ca5bc6f9',
                    'aarch64':'b0726cecd84f9474419d67252add4ac0cd9811b04d61123054b9fb6f57df6e9e',
                }
                encoded=globals().get('FRAMEY_BACKEND_WHEELS',{}).get(arch)
                if arch not in pins or not encoded:
                    raise RuntimeError('Missing native psutil dependency')
                wheel_data=base64.b64decode(encoded,validate=True)
                if hashlib.sha256(wheel_data).hexdigest()!=pins[arch]:
                    raise RuntimeError('Native psutil dependency SHA-256 mismatch')
                modules=unpacked/'py_modules'
                for name in ('psutil','psutil-7.2.2.dist-info'):
                    if (modules/name).exists(): raise RuntimeError('Native psutil dependency collides with archive')
                with zipfile.ZipFile(io.BytesIO(wheel_data)) as wheel:
                    for member in wheel.infolist():
                        path=pathlib.PurePosixPath(member.filename)
                        if (path.is_absolute() or '..' in path.parts or not path.parts or
                            path.parts[0] not in ('psutil','psutil-7.2.2.dist-info')):
                            raise RuntimeError('Unsafe psutil dependency member')
                        if member.is_dir(): continue
                        payload=wheel.read(member)
                        if payload[:4]==b'\x7fELF' and int.from_bytes(payload[18:20],'little')!=({'x86_64':62,'aarch64':183}[arch]):
                            raise RuntimeError('Incorrect psutil native architecture')
                        dest=modules/member.filename
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        dest.write_bytes(payload)
                        dest.chmod(0o600)
            if network_sentinel:
                manifest_path=unpacked/'plugin.json'
                manifest=json.loads(manifest_path.read_text())
                main=unpacked/'main.py'
                if (manifest.get('name')!='Network Sentinel' or manifest.get('api_version')!=1
                    or manifest.get('flags')!=['debug','_root'] or
                    hashlib.sha256(main.read_bytes()).hexdigest()!='2baa390cb66dc267e8f04e61ba1edc43af75115ad5e453d308f6bf26ed70b6b9'):
                    raise RuntimeError('Network Sentinel manifest or source changed')
                manifest['flags']=['debug']
                manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
                source=main.read_text(encoding='utf-8')
                old='decky.DECKY_SETTINGS_DIR'
                ping='            cmd = [\'ping\', \'-c\', str(count), \'-W\', \'2\', host]\n'
                if (source.count(old)!=2 or source.count('    async def _migration(self):')!=1
                    or source.count(ping)!=1):
                    raise RuntimeError('Network Sentinel settings or migration source changed')
                source=source.replace(old,'decky.DECKY_PLUGIN_SETTINGS_DIR')
                source=source.replace(ping,'            jitter = 0\n'+ping)
                source=source.replace('    async def _migration(self):',
                                      '    async def _migration(self):\n        # Managed user service does not move legacy Decky paths.\n        return\n')
                main.write_text(source,encoding='utf-8')
                compat_shims.append('network-sentinel-user-psutil')
            if battery_tracker:
                manifest_path=unpacked/'plugin.json'
                manifest=json.loads(manifest_path.read_text())
                main=unpacked/'main.py'
                if (manifest.get('name')!='Battery Tracker' or manifest.get('flags')!=['_root']
                    or 'api_version' in manifest or
                    hashlib.sha256(main.read_bytes()).hexdigest()!='2303ec70c262f1cbfe1c8c138770c6e7c3496827e748e679c94ca43ff9f28725'):
                    raise RuntimeError('Battery Tracker manifest or source changed')
                manifest['flags']=[]
                manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
                source=main.read_text(encoding='utf-8')
                split_start=source.index('def split_by_app(data):\n')
                split_end=source.index('\n\nclass Plugin:',split_start)
                source=source[:split_start]+"""def _framey_battery_path():
    # A normal user can read Frame's Battery-type supply; BAT1 remains first
    # on Steam Deck. The override is for a private, networkless runtime fixture.
    root = Path(os.environ.get('FRAMEY_BATTERY_ROOT', '/sys/class/power_supply'))
    if not root.is_absolute():
        raise ValueError('Battery supply root must be absolute')
    for candidate in [root / 'BAT1', *sorted(root.iterdir())]:
        try:
            if ((candidate / 'type').read_text().strip() == 'Battery' and
                all((candidate / field).is_file() for field in
                    ('capacity', 'status', 'voltage_now', 'current_now'))):
                return candidate
        except OSError:
            pass
    raise FileNotFoundError('No readable Battery-type power supply')


def split_by_app(data):
    if not data:
        return []
    groups = []
    start = 0
    app = data[0][4]
    for index, row in enumerate(data[1:], 1):
        if row[4] != app:
            groups.append((start, index, app))
            start, app = index, row[4]
    groups.append((start, len(data), app))
    return groups
"""+source[split_end:]
                old='            self.app = "Unknown"\n'
                if source.count(old)!=1: raise RuntimeError('Battery Tracker startup source changed')
                source=source.replace(old,old+'            self._pending_samples = []\n')
                unload_start=source.index('    async def _unload(self):\n')
                unload_end=source.index('    async def set_app(',unload_start)
                source=source[:unload_start]+"""    async def _unload(self):
        task = getattr(self, '_recorder_task', None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        pending = getattr(self, '_pending_samples', [])
        if pending:
            self.cursor.executemany('insert into battery values (?, ?, ?, ?, ?)', pending)
            self.con.commit()
            pending.clear()
        if hasattr(self, 'con'):
            self.con.close()

"""+source[unload_end:]
                old='            ).fetchall()\n'
                if source.count(old)!=2: raise RuntimeError('Battery Tracker query source changed')
                query='            data = self.cursor.execute(\n                "select * from battery where time > " + str(int(start_time))\n            ).fetchall()\n'
                if source.count(query)!=1: raise RuntimeError('Battery Tracker history source changed')
                source=source.replace(query,query+'            data.extend(row for row in self._pending_samples if row[0] > start_time)\n')
                recorder_start=source.index('    async def recorder(self):\n')
                source=source[:recorder_start]+"""    async def recorder(self):
        battery = _framey_battery_path()
        decky_plugin.logger.info('recorder started')
        while True:
            try:
                volt = int((battery / 'voltage_now').read_text().strip())
                curr = int((battery / 'current_now').read_text().strip())
                cap = int((battery / 'capacity').read_text().strip())
                status = (battery / 'status').read_text().strip()
                state = -1 if status == 'Discharging' else 1 if status == 'Charging' else 0
                power = int(volt * curr * 10.0**-11)
                self._pending_samples.append((int(time.time()), cap, state, power, self.app))
                if len(self._pending_samples) > 10:
                    self.cursor.executemany('insert into battery values (?, ?, ?, ?, ?)', self._pending_samples)
                    self.con.commit()
                    self._pending_samples.clear()
            except asyncio.CancelledError:
                raise
            except Exception:
                decky_plugin.logger.exception('recorder')
            await asyncio.sleep(5)
"""
                main.write_text(source,encoding='utf-8')
                compat_shims.append('battery-tracker-user-supply')
            if deckyspy:
                compat=modules/'framey_battery.py'
                if compat.exists(): raise RuntimeError('DeckySpy battery module collides with archive')
                battery_source=globals().get('FRAMEY_BACKEND_BATTERY_SOURCE')
                if not isinstance(battery_source,str) or not battery_source:
                    raise RuntimeError('Missing DeckySpy battery compatibility source')
                compat.write_text(battery_source,encoding='utf-8')
                main=unpacked/'main.py'
                source=main.read_text(encoding='utf-8')
                old='        battery = psutil.sensors_battery()\n'
                if source.count(old)!=1: raise RuntimeError('DeckySpy battery source changed')
                source=source.replace(old,'        from framey_battery import sensors_battery\n        battery = sensors_battery()\n')
                main.write_text(source,encoding='utf-8')
                compat_shims.append('deckyspy-psutil-and-battery')
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
            # RadiYo's exact 1.3 backend turns off certificate and hostname
            # checks for both outbound requests. Restore Python's default TLS
            # policy only for the pinned official source in this managed copy.
            if int(plugin_id)==24 and digest=='647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43' and folder=='radiyo-steam-deck':
                main=unpacked/'main.py'
                data=main.read_bytes()
                if hashlib.sha256(data).hexdigest()!='868332dbe3feb1e7a81e35a0c01fdc0a6b68421ec1f84e238564bfad4946e87e':
                    raise RuntimeError('RadiYo source differs from pinned archive')
                unsafe=b'        ctx.check_hostname = False\n        ctx.verify_mode = ssl.CERT_NONE\n'
                broken=b"'URL Error: ' + error.reason"
                if data.count(unsafe)!=2 or data.count(broken)!=2:
                    raise RuntimeError('RadiYo TLS source changed')
                data=data.replace(unsafe,b'').replace(broken,b"'URL Error: ' + str(error.reason)")
                main.write_bytes(data)
                compat_shims.append('radiyo-verified-tls')
            # The exact published backend awaits synchronous shutil.rmtree:
            # it deletes the cache then reports TypeError. Restrict deletion
            # to the two directories selected by its UI and their numeric app IDs.
            if int(plugin_id)==50 and digest=='1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591' and folder=='decky-storage-cleaner':
                main=unpacked/'main.py'
                data=main.read_bytes()
                if hashlib.sha256(data).hexdigest()!='6fd4d012568edae22ba421495455b3c02899155e4c7484f5aa5be6ce9b14dd5f':
                    raise RuntimeError('Storage Cleaner source differs from pinned archive')
                old=b"    @classmethod\n    async def delete_cache(cls, dirName):\n        await shutil.rmtree(homeDir + '/.steam/steam/steamapps/' + dirName)"
                new=b"""    @classmethod
    async def delete_cache(cls, dirName):
        if not isinstance(dirName, str):
            raise ValueError('Invalid cache path')
        parts = dirName.split('/')
        if (len(parts) not in (1, 2) or parts[0] not in ('shadercache', 'compatdata')
                or (len(parts) == 2 and (not parts[1].isascii() or not parts[1].isdecimal()))):
            raise ValueError('Invalid cache path')
        root = os.path.realpath(os.path.join(homeDir, '.steam', 'steam', 'steamapps'))
        target = os.path.join(root, *parts)
        cursor = root
        for part in parts:
            cursor = os.path.join(cursor, part)
            if os.path.islink(cursor):
                raise ValueError('Cache path is a symbolic link')
        if os.path.commonpath((root, os.path.realpath(target))) != root:
            raise ValueError('Cache path escapes Steam apps')
        shutil.rmtree(target)"""
                if data.count(old)!=1: raise RuntimeError('Storage Cleaner delete source changed')
                main.write_bytes(data.replace(old,new))
                compat_shims.append('storage-cleaner-bounded-delete')
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
