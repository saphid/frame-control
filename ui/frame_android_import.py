"""Local APK sets, ZIP-based Android bundles and companion data. Stdlib only.

Unpack into private staging, check every package before installing any, and use
the same installer and running-instance data copy as Quest import. No game is
started here. A data-bearing import takes two drops, as Quest takes two imports.
"""
from pathlib import Path, PurePosixPath
import os
import re
import shutil
import stat
import struct
import tempfile
import time
import zipfile

import frame_android as android
import frame_apk
import frame_quest as quest

ARCHIVES = {'.xapk', '.apks', '.apkm', '.zip'}
EXTENSIONS = ARCHIVES | {'.apk', '.obb'}
MAX_BYTES = 16 * 1024**3
MAX_FILES = 4096
TMP_PREFIX = 'frame-android-import-'
OBB = re.compile(r'(?:main|patch)\.[0-9]+\.([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)\.obb')
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


def is_bundle(path):
    """Sniff ZIPs so PC-game ZIPs retain their existing route. No extraction."""
    try:
        with zipfile.ZipFile(path) as archive:
            members = [(m, n) for m, n in _members(archive)
                       if not m.is_dir() and not _finder_metadata(m.filename)]
            # A PC distribution may include an optional Android build too.
            for member, name in members:
                # External app data is opaque, even if a file resembles a PC program.
                if name.startswith(('Android/data/', 'Android/obb/')):
                    continue
                if name.lower().endswith(('.exe', '.appimage', '.sh')):
                    return False
                if not name.lower().endswith(('.apk', '.obb', '.apk.idsig')):
                    with archive.open(member) as src:
                        if src.read(4) == b'\x7fELF':
                            return False
            return any(n.lower().endswith(('.apk', '.obb')) or n.startswith('Android/data/') for _, n in members)
    except (OSError, ValueError, RuntimeError, NotImplementedError, zipfile.BadZipFile):
        return False


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
        return 'data', parts[2], parts[3:]
    if name.lower().endswith('.apk'):
        return 'apk', None, None
    if name.lower().endswith('.obb'):
        match = OBB.fullmatch(parts[-1])
        if not match or not (len(parts) == 1 or
                len(parts) == 2 and parts[0] == match[1] or
                len(parts) == 4 and parts[:2] == ('Android', 'obb') and parts[2] == match[1]):
            raise android.FrameError('OBB needs its standard main/patch.<version>.<package>.obb name and Android/obb/<package> location')
        return 'obb', match[1], None
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


def prepare(paths, root):
    """Validate and group files by manifest package; return private install plans."""
    groups, budget = {}, {'bytes': 0, 'files': 0}
    if not paths or len(paths) > 128:
        raise android.FrameError('Choose between 1 and 128 Android files')
    for i, path in enumerate(paths):
        path = Path(path)
        if path.suffix.lower() not in EXTENSIONS or not path.is_file() or path.stat().st_size == 0:
            raise android.FrameError('Choose a nonempty APK, OBB, XAPK, APKS, APKM or Android ZIP file')
        if path.suffix.lower() in ARCHIVES:
            directory = root / str(i)
            directory.mkdir()
            try:
                entries = _unpack(path, directory, budget)
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as e:
                raise android.FrameError('Could not read Android bundle: ' + str(e)) from e
        else:
            budget['bytes'] += path.stat().st_size
            budget['files'] += 1
            entries = [(path, *_kind(path.name))]
        if budget['bytes'] > MAX_BYTES or budget['files'] > MAX_FILES:
            raise android.FrameError('Android import exceeds its size or file limit')
        packages = set()
        for local, kind, pkg, rel in entries:
            split = None
            if kind == 'apk':
                started = time.time()
                try:
                    with zipfile.ZipFile(local) as archive:
                        elements = frame_apk.manifest_elements(
                            frame_apk._read(archive, 'AndroidManifest.xml', frame_apk.MAX_MANIFEST))
                        attrs = next(a for tag, a in elements if tag == 'manifest')
                    pkg = attrs.get('package', (None, None, None))[2]
                    split = attrs.get('split', (None, None, None))[2]
                except (OSError, ValueError, StopIteration, struct.error, IndexError, KeyError,
                        frame_apk.ApkError, zipfile.BadZipFile) as e:
                    error = android.FrameError('Could not read APK manifest: ' + str(e))
                    android._after_install(None, None, error, started)
                    raise error from e
            if not pkg or not android.PKG_RE.fullmatch(pkg):
                raise android.FrameError('Invalid Android package in import')
            packages.add(pkg)
            group = groups.setdefault(pkg, {'package': pkg, 'base': None, 'splits': [], 'obb': [],
                                             'data': None, 'required': False,
                                             'split_names': set(), 'data_names': set()})
            if kind == 'apk':
                if split:
                    if split in group['split_names']:
                        raise android.FrameError('Duplicate split APK: ' + split)
                    group['split_names'].add(split)
                    group['splits'].append(local)
                elif group['base']:
                    raise android.FrameError('Several base APKs for ' + pkg + '; choose one build or device variant')
                else:
                    group['base'] = local
                    group['required'] = any(bool(a.get('isSplitRequired', (None, 0, None))[1])
                                            for tag, a in elements if tag == 'application')
            elif kind == 'obb':
                if local.stat().st_size == 0:
                    raise android.FrameError('OBB game data must not be empty')
                if local.name in {p.name for p in group['obb']}:
                    raise android.FrameError('Duplicate OBB: ' + local.name)
                group['obb'].append(local)
            elif kind == 'data':
                name = '/'.join(rel).casefold()
                if name in group['data_names']:
                    raise android.FrameError('Duplicate Android/data file')
                group['data_names'].add(name)
                # Private destination, unrelated to archive paths or package-controlled symlinks.
                group['data'] = root / ('data-' + pkg)
                target = group['data'].joinpath(*rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                local.rename(target)
        if path.suffix.lower() in ARCHIVES and len(packages) != 1:
            raise android.FrameError('An Android bundle must contain one matching app and its data')
    for group in groups.values():
        base, splits = group['base'], group['splits']
        if splits and not base:
            raise android.FrameError('Split APK set is missing its base APK')
        if group['required'] and not splits:
            raise android.FrameError('This base APK requires splits; select the complete APK set together')
        if base:
            started = time.time()
            try:
                checked = quest.inspect(group['package'], str(base), [str(p) for p in splits])
            except android.FrameError as error:
                # Retain the older-build lookup offered by the original single-APK uploader.
                info = android.apk_info(base)
                abis = set(info['abis'])
                for split in splits:
                    abis.update(android.apk_info(split)['abis'])
                try:
                    android.check_installable(dict(info, abis=sorted(abis)))
                except android.FrameError as incompatible:
                    incompatible.apk = {'package': info['package'], 'version_code': info.get('version_code'),
                                        'blocker': str(incompatible)}
                    android._after_install(info, None, incompatible, started)
                    raise incompatible from error
                raise
            if splits and (checked['version_code'] is None or any(
                    android.apk_info(p).get('version_code') != checked['version_code'] for p in splits)):
                raise android.FrameError('Base and split APKs must have the same version code')
            group['checked'] = checked
    if not groups:
        raise android.FrameError('No Android app or game data found')
    return list(groups.values())


def import_files(paths, display='auto', progress=None):
    if display not in ('auto', 'flat', 'vr'):
        raise android.FrameError('invalid APK display mode')
    report = progress or (lambda *args: None)
    with tempfile.TemporaryDirectory(prefix=f'{TMP_PREFIX}{os.getpid()}-') as directory:
        report('Checking Android files', 5)
        plans = prepare(paths, Path(directory))
        results, pending = [], False
        with android._install_lock:
            # Preflight every target before changing any of them.
            for plan in plans:
                pkg = plan['package']
                meta = android.read_meta(pkg)
                plan['existing'], plan['running'] = meta, quest._running(pkg)
                if not plan['base']:
                    if not meta:
                        raise android.FrameError('Install the APK first for ' + pkg + '; no game data was copied')
                    plan['checked'] = {'package': pkg, 'label': meta['label'], 'version': meta.get('version'),
                                       'version_code': quest._installed_code(pkg, meta), 'warnings': []}
                checked = plan['checked']
                if plan['running']:
                    quest._check_target(pkg, meta, checked)
                    if not (plan['obb'] or plan['data']):
                        raise android.FrameError('Close ' + checked['label'] + ' before installing it again')
                elif meta and plan['base'] and (plan['splits'] or plan['obb'] or plan['data']):
                    have, new = quest._installed_code(pkg, meta), checked['version_code']
                    if have is None or new is None or int(new) < int(have):
                        raise android.FrameError('Cannot replace ' + checked['label'] + ' with an older or unknown version')
            for i, plan in enumerate(plans):
                pkg, checked = plan['package'], plan['checked']
                report('Importing ' + checked['label'], 20 + i * 60 // len(plans))
                if plan['running']:
                    result = quest.add_game_data(pkg, checked, plan['obb'], plan['data'], report,
                                                 checked['warnings'], source='your files')
                else:
                    meta = plan['existing']
                    if plan['base']:
                        meta = android.install(str(plan['base']), splits=[str(p) for p in plan['splits']],
                                               source=plan['base'].name,
                                               flatscreen=None if display == 'auto' else display == 'flat')
                    needs = bool(plan['obb'] or plan['data'])
                    pending |= needs
                    message = (f"Installed {meta['label']} in the Steam library." if plan['base'] else
                               f"{meta['label']}'s game data has not been copied yet.")
                    if needs:
                        message += (f" Start {meta['label']} from Steam, leave it open, then drop the same files "
                                    'again to add game data and close it. Relaunch afterwards. '
                                    'If it exits immediately, this data-copy path cannot be used yet.')
                    warnings = list(checked['warnings']) + list(meta.get('vr_issues', []))
                    result = {'app': meta, 'message': ' '.join([message, *dict.fromkeys(warnings)])}
                results.append(result)
        report('Done', 100)
        return {'message': ' '.join(r['message'] for r in results),
                'apps': [r['app'] for r in results], 'app': results[0]['app'] if len(results) == 1 else None,
                'needs_game_data': pending}
