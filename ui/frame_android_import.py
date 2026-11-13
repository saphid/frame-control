"""Import a local Android backup: one APK and its matching expansion files."""
import re
import time
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import zipfile
import zlib

import frame_apk

import frame_android as android
import frame_quest as quest

OBB = re.compile(r'(main|patch)\.[0-9]+\.([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)\.obb')

ARCHIVES = {'.xapk', '.apks', '.apkm'}
MAX_BYTES = 16 * 1024**3
MAX_FILES = 4096
METADATA = {'manifest.json', 'info.json', 'icon.png', 'toc.pb', 'meta.sai_v1.json', 'meta.sai_v2.json'}
WINDOWS_DEVICE = re.compile(r'(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', re.I)


def _finder_metadata(name):
    parts = PurePosixPath(name).parts
    return bool(parts) and (parts[0] == '__MACOSX' or parts[-1] == '.DS_Store' or parts[-1].startswith('._'))


def _members(archive):
    """Ignore Finder sidecars and strip at most one shared enclosing folder.

    Original member names are still checked by _unpack before extraction.
    Android itself is a payload root, never an enclosing folder.
    """
    members = archive.infolist()
    names = [m.filename for m in members if not m.is_dir() and not _finder_metadata(m.filename)]
    first = names[0].split('/')[0] if names else ''
    prefix = first + '/' if first and first != 'Android' and all(n.startswith(first + '/') for n in names) else ''
    return [(m, m.filename[len(prefix):] if prefix and m.filename.startswith(prefix) else m.filename)
            for m in members]


def _path(name):
    parts = PurePosixPath(name.rstrip('/')).parts
    if (not parts or len(name) > 512 or len(parts) > 32 or name.startswith('/') or '\\' in name or
            any(p in ('.', '..') or ':' in p or p.rstrip(' .') != p or WINDOWS_DEVICE.fullmatch(p)
                for p in parts) or
            '/'.join(parts) != name.rstrip('/')):
        raise android.FrameError('unsafe path in Android bundle: ' + name[:200])
    return parts


def _kind(name):
    parts = _path(name)
    if len(parts) >= 4 and parts[:2] == ('Android', 'data') and android.PKG_RE.fullmatch(parts[2]):
        raise android.FrameError('Android/data restore is not supported by this importer; choose an APK/OBB-only backup')
    if name.lower().endswith('.apk'):
        return 'apk', None, None
    if name.lower().endswith('.obb'):
        match = OBB.fullmatch(parts[-1])
        if not match or not (len(parts) == 1 or
                len(parts) == 2 and parts[0] == match[2] or
                len(parts) == 4 and parts[:2] == ('Android', 'obb') and parts[2] == match[2]):
            raise android.FrameError('OBB needs its standard main/patch.<version>.<package>.obb name and Android/obb/<package> location')
        return 'obb', match[2], None
    if (len(parts) == 1 and name in METADATA) or name.lower().endswith('.apk.idsig'):
        return 'metadata', None, None
    raise android.FrameError('Unsupported Android bundle file: ' + name + '; no files were installed')


def _unpack(path, root, budget):
    output, seen = [], set()
    with zipfile.ZipFile(path) as archive:
        members = _members(archive)
        if len(members) + budget['files'] > MAX_FILES:
            raise android.FrameError('Android import has too many files')
        declared = sum(m.file_size for m, _ in members)
        if declared + budget['bytes'] > MAX_BYTES or declared > max(0, shutil.disk_usage(root).free - 64 * 1024**2):
            raise android.FrameError('Android bundle exceeds the size limit or available staging space')
        # Validate the entire directory before creating any file.
        for member, name in members:
            _path(member.filename)
            key = member.filename.rstrip('/').casefold()
            mode = stat.S_IFMT(member.external_attr >> 16)
            if key in seen or member.flag_bits & 1 or mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise android.FrameError('Android bundle contains duplicate paths, encrypted files, links or special files')
            seen.add(key)
            if not member.is_dir() and not _finder_metadata(member.filename):
                _kind(name)
        for member, name in members:
            if member.is_dir():
                continue
            if _finder_metadata(member.filename):
                budget['bytes'] += member.file_size
                continue
            kind, pkg, rel = _kind(name)
            target = root.joinpath(*_path(member.filename))
            target.parent.mkdir(parents=True, exist_ok=True)
            size = 0
            with archive.open(member) as src, target.open('xb') as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    budget['bytes'] += len(chunk)
                    if budget['bytes'] > MAX_BYTES or size > member.file_size:
                        raise android.FrameError('Android bundle exceeds the size limit')
                    dst.write(chunk)
            if size != member.file_size:
                raise android.FrameError('Incomplete file in Android bundle: ' + member.filename)
            if kind != 'metadata':
                output.append((target, kind, pkg, rel))
        budget['files'] += len(members)
    return output


def unpack_bundle(path, root):
    """Extract a single explicit Android bundle into caller-owned staging.

    Reuse the regular backup inspector and installer; no archive metadata is
    trusted as package identity, and ordinary PC ZIPs keep their existing route.
    """
    try:
        entries = _unpack(Path(path), Path(root), {'bytes': 0, 'files': 0})
    except android.FrameError:
        raise
    except (OSError, ValueError, RuntimeError, EOFError, struct.error, zlib.error,
            zipfile.BadZipFile) as error:
        raise android.FrameError('Could not read Android bundle: ' + str(error)) from error
    paths = [str(local) for local, _, _, _ in entries]
    if not any(Path(p).suffix.lower() == '.apk' for p in paths):
        raise android.FrameError('Android bundles must contain a base APK and optional supported splits or OBB files.')
    return paths


def _apk_identity(path):
    """Use the manifest, not the filename, to identify a base or split APK."""
    try:
        with zipfile.ZipFile(path) as archive:
            elements = frame_apk.manifest_elements(
                frame_apk._read(archive, 'AndroidManifest.xml', frame_apk.MAX_MANIFEST))
        attrs = next((attrs for tag, attrs in elements if tag == 'manifest'), {})
        package = (attrs.get('package') or (None, None, None))[2]
        split = (attrs.get('split') or (None, None, None))[2]
        code = (attrs.get('versionCode') or (None, None, None))[1]
        major = (attrs.get('versionCodeMajor') or (None, 0, None))[1]
        if not package or not android.PKG_RE.fullmatch(package):
            raise android.FrameError(f'{path.name}: no valid package in APK manifest')
        return package, split, (major, code) if code is not None else None
    except (zipfile.BadZipFile, frame_apk.ApkError, OSError, UnicodeError,
            ValueError, RuntimeError, EOFError, zlib.error, struct.error,
            IndexError) as error:
        raise android.FrameError(f'Could not read APK manifest in {path.name}: {error}') from error


def _check_standalone(path):
    try:
        with zipfile.ZipFile(path) as archive:
            elements = frame_apk.manifest_elements(
                frame_apk._read(archive, 'AndroidManifest.xml', frame_apk.MAX_MANIFEST))
        if any((tag == 'manifest' and attrs.get('split', (None, None, None))[2]) or
               (tag == 'application' and attrs.get('isSplitRequired', (None, 0, None))[1])
               for tag, attrs in elements):
            raise android.FrameError('This backup needs split APKs. This importer accepts only a standalone APK; '
                                     'use the documented Quest/CLI split workflow for supported library/asset splits.')
    except (zipfile.BadZipFile, frame_apk.ApkError, OSError, ValueError, struct.error, IndexError) as error:
        raise android.FrameError('Could not read APK manifest: ' + str(error)) from error


def inspect(paths, discover=False):
    """Inspect selected files before installing anything. Desktop APK drops can find
    sibling OBBs; browser uploads include only files explicitly selected by the user."""
    if not isinstance(paths, list) or not paths or len(paths) > 100:
        raise android.FrameError('Choose one game APK and its .obb game-data files together.')
    files = []
    for value in paths:
        path = Path(value).expanduser().absolute()
        if path.is_dir():
            files.extend(p for p in sorted(path.iterdir()) if p.suffix.lower() in ('.apk', '.obb'))
        else:
            files.append(path)
    files = list(dict.fromkeys(files))
    if not files or len(files) > 100:
        raise android.FrameError('No Android backup found. Choose a folder containing one APK and its game data.')
    for path in files:
        if path.suffix.lower() not in ('.apk', '.obb') or not path.is_file() or path.stat().st_size == 0:
            raise android.FrameError(f'{path.name}: choose a nonempty APK or .obb game-data file.')
    apks = [p for p in files if p.suffix.lower() == '.apk']
    apk, splits = None, []
    if apks:
        identities = [(p, *_apk_identity(p)) for p in apks]
        bases = [p for p, _, split, _ in identities if not split]
        if len(bases) != 1:
            raise android.FrameError('Choose one game at a time: exactly one base APK is required.')
        apk = bases[0]
        package, version = next((pkg, code) for p, pkg, _, code in identities if p == apk)
        split_names = set()
        for path, pkg, split, code in identities:
            if path == apk:
                continue
            if pkg != package or split in split_names:
                raise android.FrameError('Split APKs must have the same package and distinct split names.')
            if version is None or code is None or code != version:
                raise android.FrameError('Split APK version cannot be verified against the base APK.')
            split_names.add(split)
            splits.append(path)
    if apk:
        if not splits:
            _check_standalone(apk)
        info = android.apk_info(str(apk))
        if not splits:
            try:
                android.check_installable(info)
            except android.FrameError as error:
                error.apk = {'package': info['package'], 'version_code': info.get('version_code'),
                             'blocker': str(error)}
                raise
        if splits:
            added = android.split_entries(str(apk), [str(p) for p in splits])
            if any(name.startswith('lib/') and not name.startswith('lib/arm64-v8a/') for name in added):
                raise android.FrameError('This split set includes native libraries for another device. '
                                         'Choose only the arm64-v8a split for the Frame.')
        checked = quest.inspect(info['package'], str(apk), [str(p) for p in splits])
        pkg = checked['package']
        if discover and len(files) == 1:
            files.extend(p for p in sorted(apk.parent.iterdir())
                         if p not in files and OBB.fullmatch(p.name) and OBB.fullmatch(p.name)[2] == pkg)
    else:
        packages = {OBB.fullmatch(p.name)[2] for p in files if OBB.fullmatch(p.name)}
        if len(packages) != 1:
            raise android.FrameError('Choose the APK and game-data files for one game together.')
        pkg = packages.pop()
        if not android.PKG_RE.fullmatch(pkg):
            raise android.FrameError('The game-data filename has an invalid Android package name.')
        meta = android.read_meta(pkg)
        if not meta:
            raise android.FrameError('This game is not installed. Add its APK alongside these game-data files.')
        checked = {k: meta.get(k) for k in ('package', 'label', 'version', 'version_code')}
        checked['version_code'] = quest._installed_code(pkg, meta)
        if checked['version_code'] is None:
            raise android.FrameError('Add the matching APK so Frame Control can check which game version this data belongs to.')
        checked['warnings'] = []
    obb = [p for p in files if p.suffix.lower() == '.obb']
    if len(obb) > 99:
        raise android.FrameError('Choose one APK and at most 99 game-data files.')
    if obb and checked['version_code'] is None:
        raise android.FrameError('The APK has no readable version code, so its game-data target cannot be checked.')
    names = set()
    for path in obb:
        match = OBB.fullmatch(path.name)
        if not match or match[2] != pkg:
            raise android.FrameError(f'{path.name} does not belong to {checked["label"]}. Choose matching game data.')
        if not path.is_file() or not path.stat().st_size or path.name in names:
            raise android.FrameError(f'{path.name}: game-data files must be nonempty and have unique names.')
        names.add(path.name)
    return {'apk': apk, 'splits': splits, 'obb': obb, 'checked': checked,
            'signatures': {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in [*apks, *obb]}}


def public(plan):
    checked = plan['checked']
    return {**checked, 'apk': plan['apk'].name if plan['apk'] else None,
            'splits': [p.name for p in plan['splits']],
            'obb': [{'name': p.name, 'size': p.stat().st_size} for p in plan['obb']],
            'size': sum(size for size, _ in plan['signatures'].values())}


def install(plan, display='auto', progress=None):
    """The explicit Import button authorizes starting the game to add its data.
    Reuse the Quest import's instance/version checks, verified transfer and close."""
    report = progress or (lambda *_: None)
    if display not in ('auto', 'flat', 'vr'):
        raise android.FrameError('Invalid Android display mode.')
    for path, signature in plan['signatures'].items():
        p = Path(path)
        if not p.is_file() or (p.stat().st_size, p.stat().st_mtime_ns) != signature:
            raise android.FrameError('The backup changed after it was read. Choose the files again.')
    checked = plan['checked']
    pkg, label = checked['package'], checked['label']
    with android._install_lock:
        if plan['apk']:
            if quest._running(pkg):
                raise android.FrameError(f'Close {label} on the Frame, then try importing again.')
            quest._check_downgrade(android.read_meta(pkg), checked, False)
            report('Installing the game app', 15)
            meta = android.install(str(plan['apk']), source=plan['apk'].name,
                                   flatscreen=None if display == 'auto' else display == 'flat',
                                   splits=[str(p) for p in plan['splits']])
        else:
            meta = android._meta_or_fail(pkg)
        if not plan['obb']:
            report('Done', 100)
            warnings = list(checked['warnings']) + list(meta.get('vr_issues') or [])
            return {'message': f'Installed {label}. Open it from your Steam library.', 'app': meta,
                    'needs_game_data': False, 'warnings': warnings}
        try:
            if not quest._running(pkg):
                report('Starting the game to add its data', 55)
                android.launch(pkg)
                deadline = time.monotonic() + 90
                while not quest._running(pkg):
                    if time.monotonic() >= deadline:
                        raise android.FrameError('The game did not start. Check that Steam is open on the Frame.')
                    time.sleep(2)
            report('Preparing Android for game data', 65)
            quest._wait_ready(meta)
            # Android can be booted before Lepton has installed the APK.
            deadline = time.monotonic() + 90
            while True:
                try:
                    quest._check_android_package(meta, checked['version_code'])
                    break
                except quest.QuestError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(2)
            result = quest.add_game_data(pkg, checked, plan['obb'], None, report,
                                         checked['warnings'], source='your backup')
            if result['closed']:
                result['message'] = (f'Imported {label} and {len(plan["obb"])} game-data '
                                     f'file{"s" if len(plan["obb"]) != 1 else ""}. '
                                     'Ready to open from your Steam library.')
            return result
        except Exception as error:
            closed, why = quest._close(pkg)
            detail = ('The game is closed.' if closed else f'Close the game on the Frame ({why}).')
            raise android.FrameError(f'{label} is installed, but its game-data setup did not finish: {error}. '
                                     f'{detail} Import the same backup again to retry.') from error
