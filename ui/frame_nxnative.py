"""User-owned NxNative sources and verified, portable Frame installations.

No game sources are supplied by Frame Control. Raw ROM catalogs are browseable;
only prepared Android/Vulkan builds can be installed by this adapter.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import frame_android
import frame_host

FORMAT = 'frame-control-nxnative-1'
BUNDLE_FORMAT = 'frame-control-nxnative-bundle-1'
MAX_INDEX = 8 * 1024**2
MAX_FILES = 50000
MAX_BYTES = 64 * 1024**3
RESERVE = 128 * 1024**2
ROM_SUFFIXES = {'.nsp', '.xci', '.nca', '.nsz', '.xcz'}
NOTE = ('Add your own catalog or a folder on this computer, including a mounted network share. '
        'Prepared NxNative builds install directly. Raw ROMs need a matching game profile, '
        'extracted inputs and a Mac preparation step; they cannot be installed directly.')
_lock = threading.RLock()


class NxNativeError(ValueError):
    pass


def _settings():
    return frame_host.data_dir('nxnative-sources.json')


def _cache():
    p = frame_host.cache_dir('nxnative')
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_state():
    try:
        value = json.loads(_settings().read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'sources': []}
    except (OSError, ValueError) as e:
        raise NxNativeError('Could not read your NxNative source settings') from e
    if not isinstance(value, dict) or not isinstance(value.get('sources'), list):
        raise NxNativeError('Your NxNative source settings are invalid')
    return value


def _save_state(value):
    p = _settings()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.nxnative-', dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False)
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _text(value, label, maximum=512):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise NxNativeError('Invalid ' + label)
    return value.strip()


def _url(value):
    try:
        p = urllib.parse.urlsplit(value)
        port = p.port
    except ValueError as e:
        raise NxNativeError('Invalid source URL') from e
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.fragment:
        raise NxNativeError('Use an HTTP(S) URL without embedded passwords or a local folder path')
    return value


def _remote(value):
    return urllib.parse.urlsplit(str(value)).scheme in ('http', 'https')


def _location(value):
    value = _text(value, 'source location', 4096)
    if _remote(value):
        return _url(value)
    if value.lower().startswith(('smb://', 'nfs://', 'webdav://', 'dav://', 'davs://')):
        raise NxNativeError('Mount this network share on your computer, then add its folder path; or use an HTTP(S) catalog')
    if '://' in value and not value.lower().startswith('file://'):
        raise NxNativeError('Unsupported source address')
    if value.lower().startswith('file://'):
        p = urllib.parse.urlsplit(value)
        if p.netloc not in ('', 'localhost'):
            raise NxNativeError('Mount the network share and add its local path')
        value = urllib.request.url2pathname(p.path)
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise NxNativeError('That folder or catalog file is not available on this computer')
    return str(path)


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _url(newurl)
        if urllib.parse.urlsplit(req.full_url).scheme == 'https' and urllib.parse.urlsplit(newurl).scheme != 'https':
            raise NxNativeError('The source redirected HTTPS to an insecure address')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url):
    try:
        return urllib.request.build_opener(_Redirect()).open(urllib.request.Request(
            _url(url), headers={'User-Agent': 'FrameControl-NxNative/1'}), timeout=60)
    except (OSError, urllib.error.URLError, ValueError) as e:
        if isinstance(e, NxNativeError):
            raise
        raise NxNativeError('Could not read this source; check its address, access and network connection') from e


def _read_index(location):
    if _remote(location):
        with _open(location) as f:
            data = f.read(MAX_INDEX + 1)
    else:
        with Path(location).open('rb') as f:
            data = f.read(MAX_INDEX + 1)
    if len(data) > MAX_INDEX:
        raise NxNativeError('The source catalog exceeds 8 MiB')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise NxNativeError('The catalog must be UTF-8 JSON, a URL list or gamelist.xml') from e


def _reference(base, value):
    value = _text(value, 'game location', 4096)
    if _remote(base):
        if '://' in value and not _remote(value):
            raise NxNativeError('An online catalog cannot reference local files')
        return _url(urllib.parse.urljoin(base, value))
    if _remote(value):
        return _url(value)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(base).parent / path
    return str(path.resolve())


def _sha(value, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not re.fullmatch('[0-9a-fA-F]{64}', value):
        raise NxNativeError('Prepared online builds need their SHA-256 checksum in the catalog')
    return value.lower()


def _title(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9A-Fa-f]{16}', value):
        raise NxNativeError('A prepared build needs its 16-digit title_id')
    return value.upper()


def _entry(raw, base, source_id):
    if isinstance(raw, str):
        raw = {'url': raw}
    if not isinstance(raw, dict):
        raise NxNativeError('Each catalog game must be an object or URL')
    ref = raw.get('bundle') or raw.get('build') or raw.get('url') or raw.get('path')
    ref = _reference(base, ref)
    parsed_path = urllib.parse.urlsplit(ref).path if _remote(ref) else ref
    name = _text(raw.get('name') or Path(urllib.parse.unquote(parsed_path)).name, 'game name', 200)
    bundle = parsed_path.lower().endswith('.nxnative.zip') or bool(raw.get('bundle'))
    build = bool(raw.get('build'))
    prepared = bundle or build
    checksum = _sha(raw.get('sha256'))
    installable = prepared and (not _remote(ref) or bool(checksum)) and not (build and _remote(ref))
    if installable:
        reason = ''
    elif build and _remote(ref):
        reason = 'Export this online build folder as a portable .nxnative.zip, then add it with its SHA-256 checksum'
    elif prepared:
        reason = 'Add a SHA-256 checksum for this prepared online build'
    else:
        reason = 'Preparation required: raw ROMs need matching extracted inputs and the Mac NxNative build tools'
    ident = str(raw.get('id') or hashlib.sha256(ref.encode()).hexdigest()[:20])
    _text(ident, 'game ID', 100)
    return {'id': ident, 'source_id': source_id, 'name': name,
            'title_id': _title(raw['title_id']) if raw.get('title_id') else None,
            'version': str(raw.get('version') or '')[:80], 'kind': 'prepared' if prepared else 'rom',
            'installable': installable, 'reason': reason, '_location': ref,
            '_sha256': checksum, '_build': build}


def _catalog(location, source_id):
    text = _read_index(location).strip()
    if not text:
        return []
    if text.startswith(('{', '[')):
        try:
            data = json.loads(text)
        except ValueError as e:
            raise NxNativeError('Invalid JSON catalog') from e
        if isinstance(data, dict):
            if data.get('format') not in (None, FORMAT):
                raise NxNativeError('Unsupported NxNative catalog format')
            data = data.get('games')
        if not isinstance(data, list):
            raise NxNativeError('A JSON catalog needs a games array')
    elif text.startswith('<'):
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise NxNativeError('XML declarations with entities are not supported')
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise NxNativeError('Invalid gamelist.xml') from e
        if root.tag != 'gameList':
            raise NxNativeError('Expected an EmulationStation gameList document')
        data = [{'path': game.findtext('path'), 'name': game.findtext('name')} for game in root.findall('game')]
    else:
        data = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if len(data) > MAX_FILES:
        raise NxNativeError('The catalog contains too many games')
    entries = [_entry(row, location, source_id) for row in data]
    if len({g['id'] for g in entries}) != len(entries):
        raise NxNativeError('The catalog contains duplicate game IDs')
    return entries


def _folder(path, source_id):
    path = Path(path)
    for name in ('nxnative-catalog.json', 'catalog.json', 'gamelist.xml', 'urls.txt'):
        if (path / name).is_file():
            return _catalog(str(path / name), source_id)
    if (path / 'game.apk').is_file() and (path / 'patched_android').is_dir():
        try:
            info = frame_android.apk_info(str(path / 'game.apk'))
        except frame_android.FrameError as e:
            raise NxNativeError('The prepared folder has an unreadable game.apk') from e
        return [_entry({'name': info.get('label') or path.name, 'version': info.get('version') or '',
                        'build': str(path)}, str(path / 'catalog.json'), source_id)]
    rows, inspected = [], 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith('.') and not (Path(root) / d).is_symlink()]
        for name in sorted(files):
            inspected += 1
            if inspected > 200000:
                raise NxNativeError('This folder is too large to scan; choose its game subfolder or add a catalog')
            local = Path(root) / name
            if local.is_symlink() or not (local.name.lower().endswith('.nxnative.zip') or local.suffix.lower() in ROM_SUFFIXES):
                continue
            rows.append(_entry({'path': str(local)}, str(path / 'catalog.json'), source_id))
            if len(rows) > MAX_FILES:
                raise NxNativeError('The folder contains too many games; use a smaller folder or a catalog')
    return rows


def status():
    with _lock:
        state = _read_state()
    sources, games = [], []
    for source in state['sources']:
        sources.append({k: v for k, v in source.items() if k != 'games'})
        games.extend({k: v for k, v in game.items() if not k.startswith('_')} for game in source.get('games', []))
    return {'sources': sources, 'games': games, 'note': NOTE, 'preparation': preparation(),
            'formats': ['JSON catalog', 'URL list', 'EmulationStation gamelist.xml', 'Local or mounted network folder']}


def preparation():
    return {
        'title': 'Prepare an NxNative game on a Mac',
        'requirements': ['A supported game version and matching NxNative profile',
                         'Your extracted ExeFS/RomFS, icon.jpg and control.nacp',
                         'Matching NxNative shader package and shader cache',
                         'Android NDK/SDK, JDK 21, .NET 10, Python fontTools, spirv-cross and Xcode Metal tools'],
        'steps': ['Use your own game files. When extraction is needed, use the pinned fork’s nx_extract tool with your own keys; Frame Control does not supply files or keys.',
                  'Prepare the matching shader package/cache using that game profile. ROM files alone are not enough, and unsupported versions need porting work.',
                  'Run the command below from a Frame Control source checkout on your Mac. Replace every /path/to value with your own local path.',
                  'Add the finished build folder on that Mac, or put its .nxnative.zip on your share or HTTPS catalog. Your phone can install a prepared online bundle without the Mac build tools.'],
        'command': ('python3 frame/nxnative/build.py --source /path/to/android-fork '
                    '--build /path/to/frame-build --extracted /path/to/extracted-game '
                    '--shader-package /path/to/shader/pkg --shader-cache /path/to/shader/cache '
                    '--ndk /path/to/android-ndk --bundle /path/to/game.nxnative.zip'),
        'currently_tested': 'Metroid Dread 2.1.0 (010093801237C000). Other games and versions are not promised.',
        'love': {
            'title': 'Prepare a compatible LÖVE game',
            'steps': ['Use your own extracted game folder containing main.lua and its assets. This separate runtime route requires a game compatible with LÖVE 11.5; it does not convert arbitrary ROMs.',
                      'Supply the pinned official LÖVE 11.5a Android embed runtime, JDK and Android SDK tools. Run the command below from a Frame Control source checkout on your build computer, replacing each /path/to value.',
                      'Keep the same Frame Control app-data directory and signing key for updates. The private APK contains your game assets; keep it in your own library.',
                      'Choose Install a prepared APK below, then Choose a file. On a computer you can select an APK from a mounted network share. The link option accepts public HTTPS downloads; private LAN APK URLs are not supported there.'],
            'command': ('python3 frame/love/package.py --runtime /path/to/love-11.5-android-embed-norecording.apk '
                        '--game /path/to/extracted/RomFS --output /path/to/MyGame.apk '
                        '--package com.example.mygame --label "My Game" '
                        '--android-jar /path/to/Android/sdk/platforms/android-36/android.jar '
                        '--d8 /path/to/Android/sdk/build-tools/36.0.0/d8'),
            'requirements': ['Your compatible game source (main.lua) and assets',
                             'Pinned official LÖVE 11.5a embed APK', 'Python 3, JDK and Android SDK']}}


def refresh(source_id=None):
    with _lock:
        state = _read_state()
        wanted = [dict(s) for s in state['sources'] if source_id is None or s['id'] == source_id]
    if source_id is not None and not wanted:
        raise NxNativeError('That source no longer exists')
    for source in wanted:
        try:
            location = source['location']
            entries = _folder(location, source['id']) if not _remote(location) and Path(location).is_dir() else _catalog(location, source['id'])
            source.update(games=entries, error=None, refreshed=int(time.time()))
        except (OSError, ValueError) as e:
            # A bad source must not hide healthy ones or keep its stale Install buttons active.
            source.update(games=[], error=str(e) if isinstance(e, NxNativeError) else 'This source is unavailable; check its folder or network connection')
        with _lock:
            current = _read_state()
            for i, existing in enumerate(current['sources']):
                if existing['id'] == source['id']:
                    current['sources'][i] = source
                    break
            _save_state(current)
    return status()


def add_source(location, name=''):
    location = _location(location)
    ident = hashlib.sha256(location.encode()).hexdigest()[:20]
    name = _text(name, 'source name', 120) if name else (urllib.parse.urlsplit(location).hostname if _remote(location) else Path(location).name) or 'My games'
    with _lock:
        state = _read_state()
        existing = next((s for s in state['sources'] if s['id'] == ident), None)
        if existing:
            existing['name'] = name
        else:
            state['sources'].append({'id': ident, 'name': name, 'location': location, 'games': []})
        _save_state(state)
    return refresh(ident)


def remove_source(source_id):
    with _lock:
        state = _read_state()
        state['sources'] = [s for s in state['sources'] if s['id'] != source_id]
        _save_state(state)
    return status()


def _helper():
    path = Path(__file__).resolve().parent.parent / 'frame/nxnative/stage.py'
    if not path.is_file():
        raise NxNativeError('NxNative staging tools are missing; reinstall Frame Control')
    spec = importlib.util.spec_from_file_location('_frame_nxnative_stage', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as src:
        for block in iter(lambda: src.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def _portable(name):
    p = PurePosixPath(name)
    parts = p.parts
    if (not parts or len(name) > 1024 or name != p.as_posix() or p.is_absolute() or '\\' in name or
            any(s in ('.', '..') or ':' in s or s.rstrip(' .') != s or '\0' in s or
                re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', s, re.I) or
                any(ord(c) < 32 for c in s) for s in parts)):
        raise NxNativeError('Unsafe filename in NxNative bundle')
    return parts


def _data_names(names):
    try:
        _helper().validate_data_names(names)
    except ValueError as error:
        raise NxNativeError('The bundle is missing rewritten modules, fonts, shader reflection or RomFS') from error


def _fetch(entry, report):
    location, expected = entry['_location'], entry.get('_sha256')
    if not _remote(location):
        path = Path(location)
        if not path.is_file():
            raise NxNativeError('The selected build is no longer available')
        if expected and _hash(path) != expected:
            raise NxNativeError('The prepared build checksum does not match; nothing was installed')
        return path
    _sha(expected, required=True)
    path = _cache() / (expected + '.nxnative.zip')
    if path.is_file() and _hash(path) == expected:
        return path
    fd, temp = tempfile.mkstemp(prefix='.download-', dir=_cache())
    try:
        h, total = hashlib.sha256(), 0
        with os.fdopen(fd, 'wb') as out, _open(location) as src:
            size = int(src.headers.get('Content-Length') or 0)
            if size > MAX_BYTES or size > shutil.disk_usage(_cache()).free - RESERVE:
                raise NxNativeError('Not enough space to download this prepared build')
            for block in iter(lambda: src.read(4 * 1024**2), b''):
                total += len(block)
                if total > MAX_BYTES or shutil.disk_usage(_cache()).free < len(block) + RESERVE:
                    raise NxNativeError('Not enough space to download this prepared build')
                out.write(block)
                h.update(block)
                report('Downloading your prepared build', round(total / size * 100) if size else None)
        if h.hexdigest() != expected:
            raise NxNativeError('The prepared build checksum does not match; nothing was installed')
        os.replace(temp, path)
        return path
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _unpack(path, destination):
    """Validate the whole ZIP directory, then stream and verify each listed file."""
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_FILES + 2:
            raise NxNativeError('Too many files in the prepared build')
        seen, declared = {}, 0
        for member in members:
            _portable(member.filename)
            mode = stat.S_IFMT(member.external_attr >> 16)
            key = member.filename.casefold()
            if key in seen or member.is_dir() or member.flag_bits & 1 or mode not in (0, stat.S_IFREG):
                raise NxNativeError('The prepared build contains duplicate paths, links, directories or encrypted files')
            seen[key] = member
            declared += member.file_size
        if declared > MAX_BYTES or declared > shutil.disk_usage(destination).free - RESERVE:
            raise NxNativeError('Not enough space to unpack this prepared build')
        manifest = seen.get('nxnative.json')
        if manifest is None or manifest.filename != 'nxnative.json' or manifest.file_size > MAX_INDEX:
            raise NxNativeError('Missing or oversized nxnative.json bundle manifest')
        try:
            meta = json.loads(archive.read(manifest))
        except (ValueError, UnicodeError) as e:
            raise NxNativeError('Invalid NxNative bundle manifest') from e
        if not isinstance(meta, dict) or meta.get('format') != BUNDLE_FORMAT:
            raise NxNativeError('Unsupported NxNative bundle format')
        meta['title_id'] = _title(meta.get('title_id'))
        meta['name'] = _text(meta.get('name'), 'game name', 200)
        records = meta.get('files')
        if not isinstance(records, list) or len(records) > MAX_FILES:
            raise NxNativeError('Invalid NxNative bundle file manifest')
        files, listed = [], set()
        for rec in records:
            if not isinstance(rec, dict):
                raise NxNativeError('Invalid NxNative bundle file record')
            name = rec.get('path')
            if not isinstance(name, str):
                raise NxNativeError('Invalid bundle filename')
            _portable(name)
            _sha(rec.get('sha256'), required=True)
            m = seen.get(name.casefold())
            if name in listed or m is None or m.filename != name or type(rec.get('size')) is not int or rec['size'] != m.file_size:
                raise NxNativeError('The bundle file manifest does not match its contents')
            if name != 'game.apk' and not (name.startswith('data/') and name.split('/')[1] in ('dm', 'vk', 'font', 'romfs')):
                raise NxNativeError('Unexpected file in the prepared build')
            listed.add(name)
        if set(seen) != {n.casefold() for n in listed | {'nxnative.json'}} or 'game.apk' not in listed:
            raise NxNativeError('Unlisted or missing files in the prepared build')
        _data_names({n[5:] for n in listed if n.startswith('data/')})
        for rec in records:
            name = rec['path']
            target = destination.joinpath(*_portable(name))
            target.parent.mkdir(parents=True, exist_ok=True)
            h, count = hashlib.sha256(), 0
            with archive.open(name) as src, target.open('xb') as out:
                for block in iter(lambda: src.read(4 * 1024**2), b''):
                    count += len(block)
                    if count > rec['size']:
                        raise NxNativeError('A bundle file exceeds its declared size')
                    out.write(block)
                    h.update(block)
            if count != rec['size'] or h.hexdigest() != rec['sha256'].lower():
                raise NxNativeError('A bundle file checksum does not match; nothing was installed')
            if name.startswith('data/'):
                files.append((name[5:], target, count, h.hexdigest()))
        return meta, destination / 'game.apk', sorted(files)


def _stage(title, files, meta, report):
    helper = _helper()
    package = 'com.nxnative.t' + title.lower()
    container = 'lepton-steamlaunch-' + str(int(meta['instance']))
    report('Opening the game’s persistent Android instance', None)
    # Updating host app.apk requires a fresh instance so Android installs the new APK.
    frame_android.stop(package)
    frame_android.launch(package)
    # A container shell is available before Android mounts emulated storage and
    # installs the persistent APK. Waiting for `true` races that boot sequence.
    ready = ('test "$(getprop sys.boot_completed)" = 1 && '
             'test -d /sdcard/Android && pm path ' + package + " | grep -q '^package:'")
    for attempt in range(90):
        try:
            frame_android.ssh(shlex.join(['podman', 'exec', container, '/system/bin/sh', '-c', ready]), timeout=10)
            break
        except frame_android.FrameError:
            if attempt == 89:
                raise NxNativeError('The Android instance did not start; reopen the game from Steam and try again')
            time.sleep(1)
    frame_android.ssh(shlex.join(['podman', 'exec', container, '/system/bin/sh', '-c',
                                 'am force-stop ' + package]), timeout=30)
    manifest = json.dumps({'title': title, 'files': [
        {'path': n, 'size': size, 'sha256': digest} for n, _, size, digest in files
    ]}, sort_keys=True).encode()
    digest = hashlib.sha256(manifest).hexdigest()
    ext = '/sdcard/Android/data/' + package + '/files'
    temporary = ext + '/frame-data/.stage-app-' + os.urandom(8).hex()
    final = ext + '/frame-data/' + digest
    script = helper.publish_script(package, ext, temporary, final, digest)
    ssh = ['ssh', *frame_android.SSH_OPTS, frame_android.FRAME]
    command = shlex.join(['podman', 'exec', '-i', container, '/system/bin/sh', '-c', script])
    report('Copying and verifying game data on the Frame', None)
    helper.send_archive(ssh, command, files, [('frame-data.json', manifest), ('frame-data.sha256', ''.join(
        f'{h}  {n}\n' for n, _, _, h in files).encode())])
    report('Adding the ready game to Steam', None)
    frame_android.ssh(shlex.join(['podman', 'exec', container, '/system/bin/sh', '-c',
                                 'am start -n ' + package + '/com.nxnative.MenuActivity']), timeout=30)
    return digest


def install(source_id, game_id, report=None):
    report = report or (lambda stage, percent=None: None)
    with _lock:
        state = _read_state()
        source = next((s for s in state['sources'] if s['id'] == source_id), None)
        entry = next((g for g in (source or {}).get('games', []) if g['id'] == game_id), None)
    if not entry or not entry.get('installable'):
        raise NxNativeError('Refresh your source and choose a prepared NxNative build')
    with tempfile.TemporaryDirectory(prefix='install-', dir=_cache()) as temp:
        if entry.get('_build'):
            report('Verifying your prepared build', None)
            build = Path(entry['_location'])
            apk = build / 'game.apk'
            info = frame_android.apk_info(str(apk))
            match = re.fullmatch(r'com\.nxnative\.t([0-9a-f]{16})', info.get('package', ''))
            if not match:
                raise NxNativeError('This APK is not a per-game NxNative Android build')
            meta = {'title_id': match[1].upper(), 'name': entry['name']}
            files = _helper().source_files(build)
        else:
            path = _fetch(entry, report)
            report('Verifying your prepared build', None)
            try:
                meta, apk, files = _unpack(path, Path(temp))
            except (zipfile.BadZipFile, RuntimeError, OSError) as e:
                raise NxNativeError('Could not unpack this prepared build; nothing was installed') from e
            info = frame_android.apk_info(str(apk))
        title = _title(meta['title_id'])
        expected = 'com.nxnative.t' + title.lower()
        if info.get('package') != expected or entry.get('title_id') not in (None, title):
            raise NxNativeError('The APK or bundle title does not match the selected game; nothing was installed')
        frame_android.check_installable(info)
        report('Installing the NxNative host', None)
        installed = frame_android.install(str(apk), flatscreen=True, name=entry['name'], source='My NxNative source')
        dataset = _stage(title, files, installed, report)
        return {'message': entry['name'] + ' is ready in your Steam library',
                'package': expected, 'dataset': dataset, 'instance': installed['instance']}


def export_bundle(build, output, title, name, version=''):
    """Package only prepared Android outputs; never extract/decrypt a raw ROM."""
    build, output, title = Path(build).resolve(), Path(output).resolve(), _title(title)
    name = _text(name, 'game name', 200)
    apk = build / 'game.apk'
    info = frame_android.apk_info(str(apk))
    if info.get('package') != 'com.nxnative.t' + title.lower():
        raise NxNativeError('game.apk does not match this title ID')
    source = [('game.apk', apk, apk.stat().st_size, _hash(apk))]
    source += [('data/' + n, p, size, digest) for n, p, size, digest in _helper().source_files(build)]
    if len(source) > MAX_FILES:
        raise NxNativeError('The prepared build has too many files')
    total = sum(size for _, _, size, _ in source)
    if total > MAX_BYTES:
        raise NxNativeError('The prepared build exceeds the 64 GiB bundle limit')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise NxNativeError('The output file already exists; choose another filename')
    if shutil.disk_usage(output.parent).free < total + RESERVE:
        raise NxNativeError('Not enough free space to export this prepared build')
    meta = {'format': BUNDLE_FORMAT, 'title_id': title, 'name': name, 'version': str(version),
            'files': [{'path': n, 'size': size, 'sha256': h} for n, _, size, h in source]}
    fd, temporary = tempfile.mkstemp(prefix='.nxnative-export-', dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            archive.writestr('nxnative.json', json.dumps(meta, sort_keys=True))
            for n, path, _, _ in source:
                _portable(n)
                archive.write(path, n)
        # Never overwrite another exporter that completed during this one.
        try:
            os.link(temporary, output)
        except FileExistsError as e:
            raise NxNativeError('The output file already exists') from e
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'path': str(output), 'sha256': _hash(output), 'bytes': output.stat().st_size, 'title_id': title}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    export = sub.add_parser('export')
    for arg in ('build', 'output', 'title', 'name'):
        export.add_argument('--' + arg, required=True)
    export.add_argument('--version', default='')
    args = parser.parse_args()
    print(json.dumps(export_bundle(args.build, args.output, args.title, args.name, args.version)))
