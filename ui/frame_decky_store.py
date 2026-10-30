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
SUGGESTME_DIGEST = '248294b5d6b9d5a5d635ce35f4b5185ce59d4e4fd59353e24df4b29d74c2ade4'
SUGGESTME_MAIN = '9c141daf754302698d3e3e9ced70e36e9a4beb0b04f794fb66e7e45bd3b8d6e3'
NOTIFICATIONS_DIGEST = '3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312'
NOTIFICATIONS_MAIN = '16e246a0a7950451c2a833f11ce5ce48e8ae2e2679348d03cad6870d36011004'
NOTIFICATIONS_CRYPTO = 'b424d5ff2b7be09a0a31d844f86368802c15bc38b627b0812fe5ba29d11b72bf'
EMU_DIGEST = '98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89'
EMU_ORIGINAL_MAIN = 'd4e72f136c94e48919575937ec4190f28864cc259eb111ef47f0df99f5912645'
EMU_ORIGINAL_HELPER = '19de50ce746e5a312495e9c1cf5daad5ef37ad021a98c5af2c5922fec392e51e'
EMU_MANAGED_MAIN = '2a99670f10d43008af66d760aaab51f4c44b1ff2e8de73627df38b1bd30cdb90'
EMU_BINARIES = {
    'x86_64': '7a3430fa47d2321b93e0a9d1346c70ea920ae4d6f0766c04d5044122fed25e07',
    'aarch64': 'c492ed3b3ea3bdacbd5d530958c455a0d6928e8c51ae28a739b616ce164874b6',
}
STORAGE_CLEANER_DIGEST = '1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591'
STORAGE_CLEANER_MAIN = '6fd4d012568edae22ba421495455b3c02899155e4c7484f5aa5be6ce9b14dd5f'
PREFIX_MANAGER_DIGEST = 'ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473'
PREFIX_MANAGER_MAIN = '2cead9898de712fa32fe8a217b8b5be6b043927ada28667fe696191429589896'
# Upstream GitHub v1.0.2 release asset. The live Decky store still serves 1.0.1.
PREFIX_MANAGER_102_DIGEST = '12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6'
PREFIX_MANAGER_102_MAIN = '265e64b688f55d5468a29c484462d277a6a06d72ba6d6ea0920790dc34ca79fd'
WINE_CELLAR_DIGEST = '7e077b933c234414d172b5c6d1c804b026bf39fa4e18e6663495a282637031e8'
WINE_CELLAR_ORIGINAL = '7796bfc96d466824617b2fee96dc1bc4beda30c776a9c61e0cc168d3473d29fe'
WINE_CELLAR_MAIN = '87fe4422b8aa19660da994c7c4a2c2132dd0ec411313629b8259ee9145c6be97'
WINE_CELLAR_FRONTEND = '51ffdf606e0e307f46ea45828eb94f24ce75c44ccce5f55f696aa7aec89924b6'
WINE_CELLAR_AARCH64 = 'd668a9ac02ccce97cf601bcff86f0b2104ee85e6a1105499e66178d9d19b64a8'
WINE_CELLAR_MANAGED_MAIN = '44841fea9318bb975aebaf1024ad14c912e5d5fe8b6fef561671e6a0e9559411'
DOWNLOAD_ALL_DIGEST = '0641231eec139e3231e7b5369d0dbacefd686b52e3f2fffb39384876881408da'
SYNCTHING_DIGEST = '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'

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
            or (item['id'] == 67 and item['name'] == 'Battery Tracker' and item['sha256'] == BATTERY_TRACKER_DIGEST)
            or (item['id'] == 130 and item['name'] == 'Games Prefix Manager'
                and item['sha256'] in (PREFIX_MANAGER_DIGEST, PREFIX_MANAGER_102_DIGEST))):
            item['root'] = False  # Exact managed adaptation runs as the Frame user.
        item['compatibility'] = framey_compatibility.lookup(item['id'], item['sha256'], item['version'])
    return unique


def archive_info(data, expected_hash, expected_name):
    if len(data) <= 1024:
        raise ValueError('Plugin archive is too small')
    if len(data) > MAX_ZIP:
        raise ValueError(f'Plugin archive exceeds the {MAX_ZIP // (1024 * 1024)} MiB download limit')
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError('Plugin archive SHA-256 did not match the store')
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
        emuchievements = (expected_hash == EMU_DIGEST and expected_name == 'Emuchievements'
                          and folder == 'Emuchievements')
        network_sentinel = (expected_hash == NETWORK_SENTINEL_DIGEST and expected_name == 'Network Sentinel'
                            and folder == 'network-sentinel')
        battery_tracker = (expected_hash == BATTERY_TRACKER_DIGEST and expected_name == 'Battery Tracker'
                           and folder == 'steam-deck-battery-tracker')
        prefix_manager = (expected_name == 'Games Prefix Manager' and
                          ((expected_hash == PREFIX_MANAGER_DIGEST and folder == 'GamesPrefixManager') or
                           (expected_hash == PREFIX_MANAGER_102_DIGEST and folder == 'games-prefix-manager')))
        wine_cellar = (expected_hash == WINE_CELLAR_DIGEST and expected_name == 'Wine Cellar'
                       and folder == 'decky-wine-cellar')
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
                            and hashlib.sha256(archive.read(entry)).hexdigest() == LOCALSEND_ORIGINAL)
                        or (emuchievements and name == 'Emuchievements/bin/hash'
                            and hashlib.sha256(archive.read(entry)).hexdigest() == EMU_ORIGINAL_HELPER)
                        or (wine_cellar and name == 'decky-wine-cellar/bin/backend'
                            and hashlib.sha256(archive.read(entry)).hexdigest() == WINE_CELLAR_ORIGINAL)):
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
        if ('root' in flags or '_root' in flags) and not (fileserver or network_sentinel or battery_tracker or prefix_manager):
            raise ValueError('This plugin needs root and is not supported by the Frame user service')
        if localsend and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != LOCALSEND_MAIN:
            raise ValueError('LocalSend Python source differs from the pinned archive')
        if emuchievements and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != EMU_ORIGINAL_MAIN:
            raise ValueError('Emuchievements Python source differs from the pinned archive')
        if network_sentinel and (flags != ['debug', '_root'] or manifest.get('api_version') != 1
                                 or hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != NETWORK_SENTINEL_MAIN):
            raise ValueError('Network Sentinel manifest or source differs from the pinned archive')
        if battery_tracker and (flags != ['_root'] or 'api_version' in manifest
                                or hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != BATTERY_TRACKER_MAIN):
            raise ValueError('Battery Tracker manifest or source differs from the pinned archive')
        if prefix_manager and (flags != ['root'] or 'api_version' in manifest
                               or hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() !=
                               (PREFIX_MANAGER_MAIN if expected_hash == PREFIX_MANAGER_DIGEST else PREFIX_MANAGER_102_MAIN)):
            raise ValueError('Games Prefix Manager manifest or source differs from the pinned archive')
        if (expected_hash == RADIYO_DIGEST and expected_name == 'RadiYo!' and folder == 'radiyo-steam-deck'
                and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != RADIYO_MAIN):
            raise ValueError('RadiYo source differs from the pinned archive')
        if (expected_hash == SUGGESTME_DIGEST and expected_name == 'SuggestMe' and folder == 'SuggestMe-decky-plugin'
                and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != SUGGESTME_MAIN):
            raise ValueError('SuggestMe source differs from the pinned archive')
        if expected_hash == NOTIFICATIONS_DIGEST and expected_name == 'Decky Notifications' and folder == 'decky-notifications':
            if (hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != NOTIFICATIONS_MAIN
                    or hashlib.sha256(archive.read(folder+'/py_modules/connector/crypto.py')).hexdigest() != NOTIFICATIONS_CRYPTO):
                raise ValueError('Decky Notifications source differs from the pinned archive')
        if (expected_hash == STORAGE_CLEANER_DIGEST and expected_name == 'Storage Cleaner'
                and folder == 'decky-storage-cleaner'
                and hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != STORAGE_CLEANER_MAIN):
            raise ValueError('Storage Cleaner source differs from the pinned archive')
        if wine_cellar and (manifest.get('api_version') != 1 or flags != ['debug']
                or hashlib.sha256(archive.read(folder+'/main.py')).hexdigest() != WINE_CELLAR_MAIN
                or hashlib.sha256(archive.read(folder+'/dist/index.js')).hexdigest() != WINE_CELLAR_FRONTEND):
            raise ValueError('Wine Cellar manifest, Python or frontend differs from the pinned archive')
        return folder


DECKYSPY_DIGEST = '2d431a89826ed5cf3fd37258373eb3b46c841c39795aa8b25f83e59f4eee87c7'
PSUTIL_DIGESTS = {
    'x86_64': '076a2d2f923fd4821644f5ba89f059523da90dc9014e85f8e45a5774ca5bc6f9',
    'aarch64': 'b0726cecd84f9474419d67252add4ac0cd9811b04d61123054b9fb6f57df6e9e',
}


def apply_script(plugin_id, digest):
    """Deliver verified offline dependencies only to exact managed archives."""
    if plugin_id == 53 and digest == 'ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe':
        source = Path(__file__).with_name('framey_shotty.py').read_text(encoding='utf-8')
        return 'FRAMEY_SHOTTY_SOURCE = '+repr(source)+'\n'+APPLY
    if plugin_id == 28 and digest == EMU_DIGEST:
        assets = Path(__file__).parent/'vendor/emuchievements-2.0.5'
        payloads = {}
        for arch, expected in EMU_BINARIES.items():
            packed = (assets/f'{arch}.gz').read_bytes()
            if hashlib.sha256(gzip.decompress(packed)).hexdigest() != expected:
                raise ValueError('Bundled Emuchievements helper SHA-256 mismatch')
            payloads[arch] = base64.b64encode(packed).decode('ascii')
        main = (assets/'main.py.gz').read_bytes()
        if hashlib.sha256(gzip.decompress(main)).hexdigest() != EMU_MANAGED_MAIN:
            raise ValueError('Bundled Emuchievements Python SHA-256 mismatch')
        return ('FRAMEY_EMU_BINARIES = '+repr(payloads)+'\n'
                +'FRAMEY_EMU_MAIN = '+repr(base64.b64encode(main).decode('ascii'))+'\n'+APPLY)
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
    if plugin_id == 68 and digest == WINE_CELLAR_DIGEST:
        assets = Path(__file__).parent/'vendor/wine-cellar-0.2.1'
        packed = (assets/'aarch64.gz').read_bytes()
        if hashlib.sha256(gzip.decompress(packed)).hexdigest() != WINE_CELLAR_AARCH64:
            raise ValueError('Bundled Wine Cellar ARM64 helper SHA-256 mismatch')
        managed = (assets/'main.py.gz').read_bytes()
        if hashlib.sha256(gzip.decompress(managed)).hexdigest() != WINE_CELLAR_MANAGED_MAIN:
            raise ValueError('Bundled Wine Cellar Python SHA-256 mismatch')
        return ('FRAMEY_WINE_CELLAR_AARCH64 = '+repr(base64.b64encode(packed).decode('ascii'))+'\n'
                +'FRAMEY_WINE_CELLAR_MAIN = '+repr(base64.b64encode(managed).decode('ascii'))+'\n'+APPLY)
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
STORAGE_CLEANER_FRONTEND='8252cfcd2182546f715cc0e4116a887fcf40af1b8b9d132bd1761c8b9ff46fdb'
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
            emuchievements=(int(plugin_id)==28 and digest=='98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89' and folder=='Emuchievements')
            network_sentinel=(int(plugin_id)==114 and digest=='d3e07f40a0c800e72d15594e03c8c61e9bf3092524a578a0260520e735b971a5' and folder=='network-sentinel')
            battery_tracker=(int(plugin_id)==67 and digest=='91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94' and folder=='steam-deck-battery-tracker')
            prefix_manager=(int(plugin_id)==130 and
                ((digest=='ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473' and folder=='GamesPrefixManager') or
                 (digest=='12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6' and folder=='games-prefix-manager')))
            wine_cellar=(int(plugin_id)==68 and digest=='7e077b933c234414d172b5c6d1c804b026bf39fa4e18e6663495a282637031e8' and folder=='decky-wine-cellar')
            manifest=json.loads(z.read(folder+'/plugin.json'))
            if not isinstance(manifest,dict): raise RuntimeError('Invalid plugin manifest')
            flags=manifest.get('flags',[])
            if not isinstance(flags,list) or not all(isinstance(flag,str) for flag in flags):
                raise RuntimeError('Invalid plugin flags')
            if ('root' in flags or '_root' in flags) and not (fileserver or network_sentinel or battery_tracker or prefix_manager):
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
                                    hashlib.sha256(z.read(f)).hexdigest()=='d448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843')
                                or (emuchievements and f.filename==folder+'/bin/hash' and
                                    hashlib.sha256(z.read(f)).hexdigest()=='19de50ce746e5a312495e9c1cf5daad5ef37ad021a98c5af2c5922fec392e51e')
                                or (wine_cellar and f.filename==folder+'/bin/backend' and
                                    hashlib.sha256(z.read(f)).hexdigest()=='7796bfc96d466824617b2fee96dc1bc4beda30c776a9c61e0cc168d3473d29fe')):
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
            if (int(plugin_id)==131 and digest=='0641231eec139e3231e7b5369d0dbacefd686b52e3f2fffb39384876881408da'
                    and folder=='decky-download-all'):
                frontend=unpacked/'dist/index.js'
                bundle=frontend.read_bytes()
                if (manifest.get('name')!='Download All' or manifest.get('api_version')!=1 or flags!=[]
                        or hashlib.sha256(bundle).hexdigest()!='af34a036e8a68e0700fd924bc4f35655df0dd6daba59cd950c60c7bb8d42c9de'):
                    raise RuntimeError('Download All frontend differs from pinned archive')
                bundle=bundle.replace(b'const handleDownloadAll = () => {',b'const handleDownloadAll = async () => {')
                start=bundle.index(b'        // Find the end of the current queue')
                end=bundle.index(b'        toaster.toast({',start)
                # Await one bounded batch. Never report success while Steam
                # operations are still pending or after a partial failure.
                batch=b"""        try {
            await SteamClient.Downloads.FrameyQueueDownloads(items.map(item => item.appid));
        } catch (error) {
            toaster.toast({title: "Download queue stopped", body: String(error.message || error)});
            return;
        }
"""
                managed=bundle[:start]+batch+bundle[end:]
                managed=managed.replace(b'Added ${items.length} downloads to queue (smallest first)',
                                        b'Submitted ${items.length} downloads to Steam (smallest first)')
                frontend.write_bytes(managed)
                compat_shims.append('download-all-local-queue')
            if prefix_manager:
                main=unpacked/'main.py'
                data=main.read_bytes()
                if (manifest.get('name')!='Games Prefix Manager' or flags!=['root']
                        or 'api_version' in manifest
                        or hashlib.sha256(data).hexdigest()!=('2cead9898de712fa32fe8a217b8b5be6b043927ada28667fe696191429589896'
                            if digest=='ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473'
                            else '265e64b688f55d5468a29c484462d277a6a06d72ba6d6ea0920790dc34ca79fd')):
                    raise RuntimeError('Games Prefix Manager manifest or source differs from pinned archive')
                # Keep the published legacy calling convention. All reads and
                # writes run as Decky's user; no root or Steam process changes.
                adaptation=br"""

# Frame Control adaptation for the exact official 1.0.1 archive.
import decky
import pathlib
import stat
import tempfile
import zipfile

DECK_HOME = decky.DECKY_USER_HOME
BACKUP_DIR = os.path.join(DECK_HOME, "Documents", "PrefixBackups")

def get_steam_library_folders():
    internal = pathlib.Path(DECK_HOME) / ".local/share/Steam"
    candidates = [internal]
    media = pathlib.Path("/run/media") / decky.DECKY_USER
    if media.is_dir():
        candidates.extend(media.iterdir())
    vdf = internal / "steamapps/libraryfolders.vdf"
    if vdf.is_file():
        # Current Steam uses nested entries with a path key, rather than the
        # obsolete numeric-key/string-value format in the published plugin.
        for value in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', vdf.read_text(errors="replace")):
            candidates.append(pathlib.Path(value.replace('\\\\', '\\').replace('\\"', '"')))
    result = []
    for candidate in candidates:
        if candidate.is_absolute() and candidate.is_dir():
            resolved = str(candidate.resolve())
            if resolved not in result:
                result.append(resolved)
    return result

async def _framey_get_games(self):
    SIZE_CACHE.clear()
    steam = parse_steam_games()
    # The published shortcut parser reads only one user and swallows errors.
    # Missing metadata is never evidence that a prefix is unused. Do not use
    # that parser or expose the scanner's unproven "Orphan" classification.
    unidentified = find_orphans({g["appid"] for g in steam})
    for game in unidentified:
        game["name"] = "Unidentified prefix (may still be in use)"
        game["type"] = "Unidentified"
    self.games = steam + unidentified
    return self.games

def _framey_prefix(game):
    appid = str(game["appid"])
    if not appid.isascii() or not appid.isdecimal():
        raise ValueError("Invalid prefix app ID")
    path = pathlib.Path(game["prefix_path"])
    roots = [(pathlib.Path(lib) / "steamapps/compatdata").resolve()
             for lib in get_steam_library_folders()]
    if (not path.is_absolute() or path.name != appid or path.parent.resolve() not in roots
            or path.parent.is_symlink() or path.parent.parent.is_symlink()
            or path.is_symlink() or not path.is_dir()):
        raise ValueError("Prefix must be a regular directory in a current Steam library; symlinks are unsupported")
    return path

def _framey_backup(path):
    destination = pathlib.Path(BACKUP_DIR)
    destination.mkdir(parents=True, exist_ok=True)
    # Refuse an accidental backup loop and refuse symlinks/special files so a
    # backup cannot read files outside the selected prefix. Failure keeps it.
    if destination.resolve().is_relative_to(path.resolve()):
        raise ValueError("Backup directory is inside the selected prefix")
    members = []
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            member = pathlib.Path(root) / name
            mode = member.lstat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError("Prefix backup does not support symlinks or special files")
            members.append(member)
    fd, name = tempfile.mkstemp(prefix=path.name+"-", suffix=".zip", dir=destination)
    try:
        with os.fdopen(fd, "wb") as output:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for member in members:
                    bundle.write(member, member.relative_to(path))
    except BaseException:
        os.unlink(name)
        raise

async def _framey_delete_prefix(self, appid, do_backup):
    matches = [g for g in self.games if g["appid"] == str(appid)]
    if not matches:
        return False, "Prefix not found in cache; refresh the list"
    # The official frontend sends an app ID, not an exact library/row path.
    # Never guess which row the user selected when that ID is ambiguous.
    if len(matches) != 1:
        return False, "Ambiguous prefix app ID in multiple rows; no prefix changed"
    game = matches[0]
    try:
        path = _framey_prefix(game)
        if do_backup:
            _framey_backup(path)
        # Revalidate after the backup; never follow a changed root symlink.
        shutil.rmtree(_framey_prefix(game))
        SIZE_CACHE.clear()
        self.games = [g for g in self.games if g["appid"] != str(appid)]
        return True, "Success"
    except (OSError, ValueError) as error:
        return False, str(error)

async def _framey_cleanup_orphans(self, do_backup):
    # Refuse even direct RPC or stale cached rows. Do not create backups or
    # delete anything until complete non-Steam shortcut coverage is proven.
    return 0, "Orphan cleanup is disabled on Frame: non-Steam shortcut coverage is incomplete; unidentified prefixes may still be in use"

Plugin.get_games = _framey_get_games
Plugin.delete_prefix = _framey_delete_prefix
Plugin.cleanup_orphans = _framey_cleanup_orphans
"""
                if digest=='12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6':
                    adaptation=adaptation.replace(b'exact official 1.0.1 archive',b'exact upstream v1.0.2 release asset')
                    adaptation=adaptation.replace(
                        b'async def _framey_delete_prefix(self, appid, do_backup):\n',
                        b'async def _framey_delete_prefix(self, appid, do_backup, delete_game_folder=False):\n'
                        b'    if delete_game_folder:\n'
                        b'        return False, "Game data deletion is unavailable on Frame; no files changed"\n')
                main.write_bytes(data+adaptation)
                frontend=unpacked/'dist/index.js'
                bundle=frontend.read_bytes()
                if hashlib.sha256(bundle).hexdigest()!=('2812dfe99594f64d76f7978961844bbd8431356ac649763a4a10bfdf23205ca5'
                    if digest=='ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473'
                    else '1ab8001b6f244319a37e721c37ed8520bb3d6e2b0b3aca1ac09b09012ed0ecd4'):
                    raise RuntimeError('Games Prefix Manager frontend differs from pinned archive')
                if digest=='12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6':
                    # Its new game-data deletion uses an unbounded install_path.
                    # Hide the toggle, and also refuse a forged direct RPC above.
                    for old in (b'showDeleteGameFolder: true',
                                b'showDeleteGameFolder: game.install_path !== "-" && !!game.install_path'):
                        if bundle.count(old)!=1: raise RuntimeError('Games Prefix Manager game-data source changed')
                        bundle=bundle.replace(old,b'showDeleteGameFolder: false')
                helper=b"""    const frameyPrefixAction = async (serverAPI, method, args) => {
        try {
            const response = await serverAPI.callPluginMethod(method, args);
            if (response?.success === false) throw Error(String(response.result));
            const result = response?.result ?? response;
            if (!Array.isArray(result) || result.length !== 2) throw Error('Invalid backend reply');
            if (result[0] === false || (method === 'cleanup_orphans' &&
                    !['Success', 'No orphans found'].includes(result[1]))) throw Error(String(result[1]));
            return true;
        } catch (error) {
            serverAPI.toaster.toast({title: 'Prefix action stopped', body: String(error.message || error)});
            return false;
        }
    };

"""
                for method,count in ((b'delete_prefix',2),(b'cleanup_orphans',1)):
                    old=b'await serverAPI.callPluginMethod("'+method+b'", {'
                    if bundle.count(old)!=count: raise RuntimeError('Games Prefix Manager action source changed')
                    bundle=bundle.replace(old,b'await frameyPrefixAction(serverAPI, "'+method+b'", {')
                replacements=(
                    (b'onClick: handleCleanupOrphans, disabled: loading',
                     b'onClick: handleCleanupOrphans, disabled: true'),
                    (b'"Clean Orphans"', b'"Orphan Cleanup Unavailable"'),
                    (b' Scan for all game prefixes and orphans.',
                     b' Scan Steam and unidentified prefixes. Unidentified prefixes may still be in use.'),
                    (b' Automatically find and delete prefixes for uninstalled games.',
                     b' Disabled on Frame: non-Steam shortcut coverage is incomplete. Unidentified prefixes may still be in use.'),
                )
                for old,new in replacements:
                    if bundle.count(old)!=1: raise RuntimeError('Games Prefix Manager cleanup source changed')
                    bundle=bundle.replace(old,new)
                anchor=b'    const ConfirmModal = '
                if bundle.count(anchor)!=1: raise RuntimeError('Games Prefix Manager modal source changed')
                frontend.write_bytes(bundle.replace(anchor,helper+anchor))
                manifest['flags']=[]
                (unpacked/'plugin.json').write_text(json.dumps(manifest))
                compat_shims.append('prefix-manager-user-paths')
            if wine_cellar:
                helper=unpacked/'bin/backend'
                source=unpacked/'main.py'
                frontend=unpacked/'dist/index.js'
                if (manifest.get('name')!='Wine Cellar' or manifest.get('api_version')!=1 or manifest.get('flags')!=['debug']
                    or hashlib.sha256(helper.read_bytes()).hexdigest()!='7796bfc96d466824617b2fee96dc1bc4beda30c776a9c61e0cc168d3473d29fe'
                    or hashlib.sha256(source.read_bytes()).hexdigest()!='87fe4422b8aa19660da994c7c4a2c2132dd0ec411313629b8259ee9145c6be97'
                    or hashlib.sha256(frontend.read_bytes()).hexdigest()!='51ffdf606e0e307f46ea45828eb94f24ce75c44ccce5f55f696aa7aec89924b6'):
                    raise RuntimeError('Wine Cellar official source mismatch')
                arch=platform.machine()
                if arch=='aarch64':
                    packed=globals().get('FRAMEY_WINE_CELLAR_AARCH64')
                    if not isinstance(packed,str): raise RuntimeError('Missing Wine Cellar ARM64 helper')
                    native=gzip.decompress(base64.b64decode(packed,validate=True))
                    if (hashlib.sha256(native).hexdigest()!='d668a9ac02ccce97cf601bcff86f0b2104ee85e6a1105499e66178d9d19b64a8'
                        or native[:4]!=b'\x7fELF' or int.from_bytes(native[18:20],'little')!=183):
                        raise RuntimeError('Wine Cellar ARM64 helper mismatch')
                    helper.write_bytes(native)
                elif arch!='x86_64': raise RuntimeError('Unsupported Wine Cellar helper architecture')
                helper.chmod(0o700)
                packed_main=globals().get('FRAMEY_WINE_CELLAR_MAIN')
                if not isinstance(packed_main,str): raise RuntimeError('Missing Wine Cellar managed Python')
                managed=gzip.decompress(base64.b64decode(packed_main,validate=True))
                if hashlib.sha256(managed).hexdigest()!='44841fea9318bb975aebaf1024ad14c912e5d5fe8b6fef561671e6a0e9559411':
                    raise RuntimeError('Wine Cellar managed Python mismatch')
                source.write_bytes(managed)
                compat_shims.append('wine-cellar-native-bridge')
            if emuchievements:
                helper=unpacked/'bin/hash'
                source=unpacked/'main.py'
                if manifest.get('name')!='Emuchievements' or manifest.get('flags')!=[]:
                    raise RuntimeError('Emuchievements manifest mismatch')
                if hashlib.sha256(helper.read_bytes()).hexdigest()!='19de50ce746e5a312495e9c1cf5daad5ef37ad021a98c5af2c5922fec392e51e':
                    raise RuntimeError('Emuchievements original helper mismatch')
                if hashlib.sha256(source.read_bytes()).hexdigest()!='d4e72f136c94e48919575937ec4190f28864cc259eb111ef47f0df99f5912645':
                    raise RuntimeError('Emuchievements original Python mismatch')
                arch=platform.machine()
                expected={
                    'x86_64':'7a3430fa47d2321b93e0a9d1346c70ea920ae4d6f0766c04d5044122fed25e07',
                    'aarch64':'c492ed3b3ea3bdacbd5d530958c455a0d6928e8c51ae28a739b616ce164874b6',
                }.get(arch)
                machine={'x86_64':62,'aarch64':183}.get(arch)
                packed=globals().get('FRAMEY_EMU_BINARIES',{}).get(arch)
                main_packed=globals().get('FRAMEY_EMU_MAIN')
                if not expected or not isinstance(packed,str) or not isinstance(main_packed,str):
                    raise RuntimeError('Missing Emuchievements native assets')
                native=gzip.decompress(base64.b64decode(packed,validate=True))
                managed=gzip.decompress(base64.b64decode(main_packed,validate=True))
                if (hashlib.sha256(native).hexdigest()!=expected or native[:4]!=b'\x7fELF'
                        or int.from_bytes(native[18:20],'little')!=machine):
                    raise RuntimeError('Emuchievements native helper mismatch')
                if hashlib.sha256(managed).hexdigest()!='2a99670f10d43008af66d760aaab51f4c44b1ff2e8de73627df38b1bd30cdb90':
                    raise RuntimeError('Emuchievements managed Python mismatch')
                helper.write_bytes(native)
                helper.chmod(0o700)
                source.write_bytes(managed)
                compat_shims.append('emuchievements-safe-arm64')
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
                # A typed value must never make the helper serve its process
                # working directory by accident. The original picker supplied
                # an existing absolute folder; preserve that start condition.
                old_start="""            if enable:
                if is_port_in_use(await Plugin.get_port(self)):
"""
                new_start="""            if enable:
                directory = await Plugin.get_directory(self)
                if not isinstance(directory, str) or not os.path.isabs(directory) or not os.path.isdir(directory):
                    Plugin.set_error(self, "Choose an existing absolute directory before starting the server.")
                    return False
                if is_port_in_use(await Plugin.get_port(self)):
"""
                if text.count(old_start)!=1: raise RuntimeError('DeckyFileServer start guard changed')
                text=text.replace(old_start,new_start)
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
                bundle=bundle.replace(old_url,new_url)
                # Chromium cannot disclose a native absolute path through a
                # directory picker. Keep the choice explicit in this exact
                # plugin's settings, without granting a general file API.
                old_picker="""    const handleDestinationClick = async (e) => {
        e.stopPropagation();
        e.preventDefault();
        const file = await openFilePicker(1 /* FileSelectionType.FOLDER */, directory, false);
        if (file.path) {
            setForm({
                ...form,
                directory: file.path,
            });
        }
    };
"""
                new_picker="""    const handleDirectoryChange = (e) => {
        setForm({ ...form, directory: e.currentTarget.value });
    };
"""
                old_button="""                window.SP_REACT.createElement(DFL.DialogButton
                // @ts-ignore
                , {\x20
                    // @ts-ignore
                    onClick: handleDestinationClick, style: { flex: 1, textAlign: "left" } }, form.directory),
"""
                new_field="""                window.SP_REACT.createElement(DFL.TextField, {
                    label: "Directory to share (absolute path)",
                    value: form.directory,
                    placeholder: "/home/steamos/Downloads",
                    onChange: handleDirectoryChange }),
"""
                if bundle.count(old_picker)!=1 or bundle.count(old_button)!=1:
                    raise RuntimeError('DeckyFileServer directory control changed')
                bundle=bundle.replace(old_picker,new_picker).replace(old_button,new_field)
                frontend.write_text(bundle,encoding='utf-8')
                compat_shims.append('deckyfileserver-user-native')
                compat_shims.append('deckyfileserver-https-address')
                compat_shims.append('deckyfileserver-directory-entry')
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
            # Game Sync's selection count must stay inside its configured root,
            # including when a selected file or walked directory is a symlink.
            if int(plugin_id)==104 and digest=='65e021ebb37d2ebfbfbe3dbc8af95aef9556cf484730362c6b26c4ecc3e62ccd' and folder=='SDH-GameSync':
                utility=unpacked/'py_modules/utils.py'
                source=utility.read_text(encoding='utf-8')
                if hashlib.sha256(source.encode()).hexdigest()!='f17be1aabb2cf2a886a96ea4b57ad3390871979db398d48824e45dbc1113404b':
                    raise RuntimeError('Game Sync utility source mismatch')
                a=source.index('def test_syncpath(')
                b=source.index('\ndef delete_lock_files(',a)
                source=source[:a]+"""def test_syncpath(syncpath: str) -> int:
    if not isinstance(syncpath, str) or not syncpath:
        raise ValueError("A sync path is required")
    root = Path(Config.get_config_item("sync_root")).expanduser().resolve(strict=True)
    recursive = syncpath.endswith("/**")
    directory = recursive or syncpath.endswith("/*")
    selected = syncpath[:-3] if recursive else syncpath[:-2] if directory else syncpath

    def bounded(path):
        try:
            resolved = path.expanduser().resolve()
            resolved.relative_to(root)
            return resolved
        except (OSError, RuntimeError, ValueError) as error:
            raise ValueError("Selection is outside the sync root or cannot be resolved") from error

    selected = bounded(Path(selected))
    if not directory:
        return int(selected.is_file())
    if not selected.is_dir():
        return 0
    count = 0
    pending = [(selected, frozenset())]
    while pending:
        current, ancestors = pending.pop()
        current = bounded(current)
        stat = current.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity in ancestors:
            raise ValueError("Recursive directory link in sync selection")
        ancestors = ancestors | {identity}
        with os.scandir(current) as entries:
            for entry in entries:
                if not recursive and entry.is_dir():
                    continue
                target = bounded(Path(entry.path))
                if target.is_dir():
                    pending.append((target, ancestors))
                elif target.is_file():
                    count += 1
                    if count > 9000:
                        return -1
    return count

"""+source[b:]
                compile(source,str(utility),'exec')
                utility.write_text(source,encoding='utf-8')
                compat_shims.append('game-sync-bounded-selection')
            # The exact DeckyParty archive already runs as the service user.
            # Invoke its original helper with system Python, without sudo, and
            # keep ownership until its process has exited and been reaped.
            if int(plugin_id)==117 and digest=='193fb3aa0446fbc3c6bae0ae15700b5f04acebfa917b8e1791988c6ce832dddf' and folder=='Decky-CP':
                main=unpacked/'main.py'
                source=main.read_text(encoding='utf-8')
                if hashlib.sha256(source.encode()).hexdigest()!='807abacba8359bfd87763bc4e32a40b89ca6ca84bb778d29bc062fbd4f0686b2':
                    raise RuntimeError('DeckyParty Python source mismatch')
                source='from __future__ import annotations\nimport pwd\nimport signal\n'+source
                a=source.index('    @staticmethod\n    def _get_home_dir(')
                b=source.index('    @staticmethod\n    def _get_sd_mounts(',a)
                source=source[:a]+"""    @staticmethod
    def _get_home_dir():
        return str(Path.home())

    @staticmethod
    def _get_user():
        return pwd.getpwuid(os.getuid()).pw_name

"""+source[b:]
                source=source.replace('            "sudo",\n            "-u",\n            user,\n            "-E",',
                                      '            "/usr/bin/python3",')
                a=source.index('    @staticmethod\n    def _stop_process(')
                b=source.index('    @staticmethod\n    def _start_process(',a)
                source=source[:a]+"""    @staticmethod
    def _stop_process():
        process = Plugin._proc
        if process is None:
            return
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=1)
        else:
            process.wait()
        Plugin._proc = None

"""+source[b:]
                source=source.replace('        env = os.environ.copy()',
                    '        env = os.environ.copy()\n'
                    '        for key in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"):\n'
                    '            env.pop(key, None)\n'
                    '        temporary = Path(decky_plugin.DECKY_PLUGIN_RUNTIME_DIR) / "copyparty-tmp"\n'
                    '        temporary.mkdir(mode=0o700, parents=True, exist_ok=True)\n'
                    '        if temporary.is_symlink() or temporary.stat().st_uid != os.getuid():\n'
                    '            raise ValueError("Copyparty temporary directory must be owned")\n'
                    '        env["TMPDIR"] = str(temporary)')
                source=source.replace('            env=env,\n', '            env=env,\n            start_new_session=True,\n')
                source=source.replace('    async def set_enabled(self, enabled):',
                    '    async def set_enabled(self, enabled):\n'
                    '        if type(enabled) is not bool:\n'
                    '            raise ValueError("Enable must be a boolean")')
                source=source.replace('_runner_task: asyncio.Task | None = None', '_runner_handle = None')
                a=source.index('    async def copyparty_runner(self):')
                source=source[:a]+"""    @staticmethod
    def copyparty_runner():
        if Plugin._runner_handle is None:
            return
        try:
            if Plugin._enabled:
                if Plugin._proc is None or Plugin._proc.poll() is not None:
                    Plugin._start_process()
            else:
                Plugin._stop_process()
        except Exception:
            logger.info(traceback.format_exc())
        Plugin._runner_handle = asyncio.get_running_loop().call_later(1, Plugin.copyparty_runner)

    async def _main(self):
        if Plugin._runner_handle is None:
            Plugin._runner_handle = asyncio.get_running_loop().call_later(1, Plugin.copyparty_runner)
        logger.info("Initialized")

    async def _unload(self):
        Plugin._enabled = False
        handle = Plugin._runner_handle
        Plugin._runner_handle = None
        logger.info("Stopping owned Copyparty runner")
        if handle is not None:
            handle.cancel()
        logger.info("Stopping owned Copyparty process")
        Plugin._stop_process()
        Plugin._password = None
        logger.info("Owned Copyparty process stopped")
"""
                compile(source,str(main),'exec')
                main.write_text(source,encoding='utf-8')
                compat_shims.append('deckyparty-user-lifecycle')
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
                main=unpacked/'main.py'
                source=main.read_text(encoding='utf-8')
                if hashlib.sha256(source.encode()).hexdigest()!='7c58aa5e273dca65ccfb59746f24b4d20edfd478b280fc8e08ff92dbe7d0d1be':
                    raise RuntimeError('Shotty source differs from pinned archive')
                safe=globals().get('FRAMEY_SHOTTY_SOURCE')
                if not isinstance(safe,str) or not safe: raise RuntimeError('Missing Shotty copy compatibility source')
                helper=compat.parent/'framey_shotty.py'
                if helper.exists(): raise RuntimeError('Shotty copy helper collides with archive')
                compile(safe,str(helper),'exec')
                helper.write_text(safe,encoding='utf-8')
                source='from framey_shotty import app_id, filename, destination, sources, copy_file, read_source, write_image\n'+source
                start=source.index('    async def copy_screenshot(')
                end=source.index('    def get_app_name(',start)
                source=source[:start]+"""    async def copy_screenshot(self, app_id=0, url=""):
        try:
            # Validate the entire selection before writing any destination.
            from framey_shotty import app_id as checked_id
            checked_id(app_id)
            if not isinstance(url, str): raise ValueError("Invalid screenshot URL")
            leaf = filename(url.rsplit("/", 1)[-1])
            found = sources(app_id, leaf)
            if len(found) != 1: return False
            path = Plugin.make_path(self, app_id, leaf)
            image = read_source(found[0])
            write_image(image, path)
            write_image(image, self._dump_folder / "most_recent.jpg", replace=True)
            return True
        except Exception:
            decky_plugin.logger.exception("Screenshot copy refused")
            return False

    async def sdsa_classic(self):
        total = 0
        for source in sources():
            identifier = app_id(int(source.parent.parent.name))
            target = Plugin.make_path(self, identifier, source.name)
            total += int(copy_file(source, target))
        return total

"""+source[end:]
                start=source.index('    def make_path(')
                end=source.index('    async def _main(',start)
                source=source[:start]+"""    def make_path(self, app_id, fname):
        return destination(self._dump_folder, Plugin.get_app_name(self, app_id) or str(app_id), fname)

"""+source[end:]
                start=source.index('                        path = (')
                end=source.index('                        os.unlink(png_path)',start)
                source=source[:start]+"""                        path = destination(Plugin._dump_folder, Plugin._current_app_name,
                                           str(int(time.time())) + ".png")
                        image = read_source(png_path)
                        write_image(image, path)
                        write_image(image, self._dump_folder / "most_recent.jpg", replace=True)
"""+source[end:]
                source+="""
    async def _unload(self):
        task = Plugin._rescuer_task
        Plugin._rescuer_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
"""
                compile(source,str(main),'exec')
                main.write_text(source,encoding='utf-8')
                compat_shims.append('shotty-bounded-copies')
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
            # Steam Status 1.2.3 disables TLS checks for its Steam CM-list and
            # speed-test downloads. Keep the default verified contexts in the
            # exact managed archive, including both indentation variants.
            if int(plugin_id)==123 and digest=='9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e' and folder=='steamstatus-decky':
                main=unpacked/'main.py'
                data=main.read_bytes()
                if hashlib.sha256(data).hexdigest()!='3b0d2daa28f9f59b81bd0e7e11528e5b3522bd3287dc6bcd1ad8f7a92086858a':
                    raise RuntimeError('Steam Status source differs from pinned archive')
                for indent in (b'                ', b'                    '):
                    unsafe=(indent+b'ssl_context.check_hostname = False\n'
                            +indent+b'ssl_context.verify_mode = ssl.CERT_NONE\n')
                    if data.count(unsafe)!=1:
                        raise RuntimeError('Steam Status TLS source changed')
                    data=data.replace(unsafe,b'')
                main.write_bytes(data)
                compat_shims.append('steam-status-verified-tls')
            # Deck Settings' exact 1.2.6 image uploader sends a bearer token
            # over HTTPS while disabling both certificate and hostname checks.
            # Retain Python's verified default context in this managed copy.
            if int(plugin_id)==93 and digest=='23c2a933a6883e2622f0184c33a76ce4a4e88c0a7dcd730f9bab71b8c3702132' and folder=='decky-game-settings':
                main=unpacked/'main.py'
                data=main.read_bytes()
                if hashlib.sha256(data).hexdigest()!='598ef3e05bb5154031988601f6f1041929f83e8b48549f72ffc24e873dcdaea0':
                    raise RuntimeError('Deck Settings source differs from pinned archive')
                unsafe=b'        ctx.check_hostname = False\n        ctx.verify_mode = ssl.CERT_NONE\n'
                if data.count(unsafe)!=1:
                    raise RuntimeError('Deck Settings TLS source changed')
                main.write_bytes(data.replace(unsafe,b''))
                compat_shims.append('deck-settings-verified-tls')
            # The exact SuggestMe archive disables hostname and certificate
            # checks if certifi context creation fails. Keep the system CA
            # fallback verified before any credential-bearing API request.
            if int(plugin_id)==132 and digest=='248294b5d6b9d5a5d635ce35f4b5185ce59d4e4fd59353e24df4b29d74c2ade4' and folder=='SuggestMe-decky-plugin':
                main=unpacked/'main.py'
                data=main.read_bytes()
                if hashlib.sha256(data).hexdigest()!='9c141daf754302698d3e3e9ced70e36e9a4beb0b04f794fb66e7e45bd3b8d6e3':
                    raise RuntimeError('SuggestMe source differs from pinned archive')
                old=b'    except Exception:\r\n        ctx = ssl.create_default_context()\r\n        ctx.check_hostname = False\r\n        ctx.verify_mode = ssl.CERT_NONE\r\n        return ctx\r\n'
                new=b'    except Exception:\r\n        return ssl.create_default_context()\r\n'
                if data.count(old)!=1: raise RuntimeError('SuggestMe TLS source changed')
                main.write_bytes(data.replace(old,new))
                compat_shims.append('suggestme-verified-tls')
            # The exact Decky Notifications archive writes a shared /tmp log
            # and dumps every environment variable if openssl fails.
            # Use Decky's captured stderr and keep credentials out of logs.
            if int(plugin_id)==79 and digest=='3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312' and folder=='decky-notifications':
                main=unpacked/'main.py'
                crypto=unpacked/'py_modules/connector/crypto.py'
                main_data=main.read_bytes()
                crypto_data=crypto.read_bytes()
                if (hashlib.sha256(main_data).hexdigest()!='16e246a0a7950451c2a833f11ce5ce48e8ae2e2679348d03cad6870d36011004'
                        or hashlib.sha256(crypto_data).hexdigest()!='b424d5ff2b7be09a0a31d844f86368802c15bc38b627b0812fe5ba29d11b72bf'):
                    raise RuntimeError('Decky Notifications source differs from pinned archive')
                old=b'logging.basicConfig(filename="/tmp/notifications.log", level=logging.INFO,'
                new=b'logging.basicConfig(level=logging.INFO,'
                env_dump=(b'        logger.error("=== ENVIRON ===")\r\n'
                          b'        for k, v in clear_env.items():\r\n'
                          b'            logger.error(f"{k}: {v}")\r\n')
                if main_data.count(old)!=1 or crypto_data.count(env_dump)!=1:
                    raise RuntimeError('Decky Notifications logging source changed')
                main.write_bytes(main_data.replace(old,new))
                crypto.write_bytes(crypto_data.replace(env_dump,b''))
                compat_shims.append('notifications-private-logs')
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
                frontend=unpacked/'dist/index.js'
                bundle=frontend.read_bytes()
                if hashlib.sha256(bundle).hexdigest()!=STORAGE_CLEANER_FRONTEND:
                    raise RuntimeError('Storage Cleaner frontend differs from pinned archive')
                old_frontend=b"""            appidArr.forEach(async (appid) => await call("delete_cache", `${cacheDirName}/${appid}`));"""
                new_frontend=b"""            for (const appid of appidArr) {
                await call("delete_cache", `${cacheDirName}/${appid}`);
            }"""
                if bundle.count(old_frontend)!=1: raise RuntimeError('Storage Cleaner selected delete source changed')
                frontend.write_bytes(bundle.replace(old_frontend,new_frontend))
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
