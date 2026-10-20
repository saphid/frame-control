"""Import a local Android backup: one APK and its matching expansion files."""
import re
import time
from pathlib import Path

import frame_android as android
import frame_quest as quest

OBB = re.compile(r'(main|patch)\.[0-9]+\.([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)\.obb')


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
    if len(apks) > 1:
        raise android.FrameError('Choose one game at a time. Split APK backups are not supported by this importer.')
    apk = apks[0] if apks else None
    if apk:
        info = android.apk_info(str(apk))
        try:
            android.check_installable(info)
        except android.FrameError as error:
            error.apk = {'package': info['package'], 'version_code': info.get('version_code'),
                         'blocker': str(error)}
            raise
        checked = quest.inspect(info['package'], str(apk))
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
    return {'apk': apk, 'obb': obb, 'checked': checked,
            'signatures': {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in [*apks, *obb]}}


def public(plan):
    checked = plan['checked']
    return {**checked, 'apk': plan['apk'].name if plan['apk'] else None,
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
                                   flatscreen=None if display == 'auto' else display == 'flat')
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
