"""Backup and recovery kit: copy game saves, settings and Android app data off the Frame,
put them back after a factory reset, and get out of Desktop Mode. Python stdlib only.

A backup is a folder in ~/Documents/Frame Control Backups/<YYYY-MM-DD-HHMMSS>/ on this
computer: one tar.gz per part (saves/, settings/, android/) and manifest.json listing every
file with its size and SHA-256, the archives' checksums and the headset's BUILD_ID. What the
parts hold, and what is never copied, is decided on the headset by frame_backup_remote.py.
Backing up only reads the headset. See docs/backup-and-recovery.md.

CLI: python3 ui/frame_backup.py backup | list | plan NAME | restore NAME PART... | session | game-mode
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time

import frame_android as android
import frame_host

REMOTE = Path(__file__).resolve().parent / 'frame_backup_remote.py'
NAME = re.compile(r'^\d{4}-\d{2}-\d{2}-\d{6}$')
ARCHIVE = re.compile(r'^(saves|settings|android)/[A-Za-z0-9._-]{1,200}\.tar\.gz$')
PART = re.compile(r'^(saves:(\d{1,10}|linux)|settings:(steam|system)|android:[A-Za-z][\w]*(\.[A-Za-z_][\w]*)+)$')
KINDS = ('saves', 'settings', 'android')
FORMAT = 1
# The switch Valve's own devkit tools use (frame/devkit-utils/steamos-delete). Nothing else
# is ever run as a session command.
SELECTORS = ('holo-session-select', 'steamos-session-select')
REASONS = {
    'not_installed': 'Install the game first, then restore its saves',
    'no_prefix': 'Start the game once so Proton sets up its folders, then restore',
    'no_account': 'Sign in to Steam on the headset first',
    'reference': 'Kept for reference only; copy by hand if you need it',
    'refused': 'Not restored: the path is not safe to write',
    'running': 'Close the app first',
    'damaged': "The backup file doesn't match its checksum",
    'missing': 'The backup file is missing',
    'empty': 'Nothing to restore',
    'unknown': 'Not something this version of Frame Control can restore',
}


class BackupError(android.FrameError):
    pass


def backup_root():
    return Path(os.environ.get('FRAME_BACKUP_DIR') or Path.home() / 'Documents' / 'Frame Control Backups')


def backup_path(name):
    """The folder for a backup name; refuses anything that isn't one of ours."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise BackupError('not a backup name')
    root = backup_root().resolve()
    path = (root / name).resolve()
    if path.parent != root:
        raise BackupError('not a backup name')
    return path


def archive_name(part):
    kind, _, rest = part.partition(':')
    return '%s/%s.tar.gz' % (kind, rest if kind == 'android' else part.replace(':', '-'))


def remote_command(cmd, *args):
    return shlex.join(['python3', '-c', REMOTE.read_text(), cmd, *args])


def _ssh(command, src=None, dst=None, timeout=1800):
    try:
        # src: bytes, or a file to stream (an archive can be larger than memory).
        feed = {'input': src} if isinstance(src, bytes) else {
            'stdin': src if src is not None else subprocess.DEVNULL}
        result = frame_host.run_ssh(['ssh', *android.SSH_OPTS, android.FRAME, command], **feed,
                                    stdout=dst if dst is not None else subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise BackupError('the headset took too long to answer')
    except OSError as error:
        raise BackupError('could not reach the headset: ' + str(error))
    if result.returncode:
        raise BackupError(result.stderr.decode(errors='replace').strip()[-600:] or
                          'the headset command failed')
    return result.stdout


def remote_json(cmd, *args, src=None, timeout=120):
    out = _ssh(remote_command(cmd, *args), src=src, timeout=timeout)
    try:
        return json.loads(out)
    except (ValueError, TypeError):
        raise BackupError('unexpected answer from the headset')


def _sha256(path):
    digest = hashlib.sha256()
    with open(str(path), 'rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_archive(path):
    """Every file in one of our part archives, with its size and SHA-256; refuses anything else."""
    files, names = [], set()
    try:
        with tarfile.open(str(path), 'r:gz') as archive:
            for member in archive:
                name = member.name
                parts = name.split('/')
                if (not member.isfile() or name.startswith('/') or '\\' in name or name in names
                        or any(p in ('', '.', '..') for p in parts)):
                    raise BackupError('backup archive has an unsafe entry: %r' % name[:200])
                names.add(name)
                digest = hashlib.sha256()
                src = archive.extractfile(member)
                for chunk in iter(lambda: src.read(1024 * 1024), b''):
                    digest.update(chunk)
                files.append({'path': name, 'bytes': member.size, 'sha256': digest.hexdigest()})
    except (OSError, EOFError, tarfile.TarError) as error:
        raise BackupError('could not read the backup archive: ' + str(error))
    return files


def preview():
    """What a backup would hold, before making one."""
    plan = remote_json('plan')
    apps, error = _android_apps()
    return {'build': plan.get('build'), 'version': plan.get('version'), 'parts': plan.get('parts', []),
            'android': apps, 'android_error': error, 'excluded': plan.get('excluded', []), 'folder': str(backup_root())}


def _android_apps():
    """(installed Android apps, None) or ([], why they couldn't be listed)."""
    try:
        return [{'package': a['package'], 'label': a.get('label') or a['package'],
                 'running': bool(a.get('running'))} for a in android.list_apps()], None
    except android.FrameError as error:
        return [], str(error)


def backup(report=lambda stage, percent=None: None, kinds=KINDS, headset=None):
    kinds = [k for k in KINDS if k in kinds]
    if not kinds:
        raise BackupError('choose something to back up')
    report('Reading what is on the headset', 1)
    plan = remote_json('plan')
    parts = [p for p in plan.get('parts', []) if p.get('kind') in kinds and PART.fullmatch(str(p.get('id')))]
    apps, error = _android_apps() if 'android' in kinds else ([], None)
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    name = time.strftime('%Y-%m-%d-%H%M%S')
    final = backup_path(name)
    if final.exists():
        raise BackupError('a backup was started this second already; try again')
    # Built under a hidden name and renamed when complete, so a cut-off backup is never listed.
    staging = root / ('.' + name + '.partial')
    staging.mkdir()
    entries = []
    skipped = [{'id': 'android', 'label': 'Android apps', 'reason': error}] if error else []
    total = len(parts) + len(apps) or 1
    try:
        for i, part in enumerate(parts):
            report('Copying ' + part['label'], 2 + 90 * i / total)
            rel = archive_name(part['id'])
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(str(dest), 'wb') as dst:
                _ssh(remote_command('pack', part['id']), dst=dst)
            files = inspect_archive(dest)
            entries.append({'id': part['id'], 'kind': part['kind'], 'label': part['label'],
                            'appid': part.get('appid'), 'archive': rel, 'sha256': _sha256(dest),
                            'archive_bytes': dest.stat().st_size, 'files': files,
                            'bytes': sum(f['bytes'] for f in files)})
            skipped += [{'id': part['id'], 'label': part['label'], 'path': s['path'], 'reason': s['reason']}
                        for s in part.get('skipped', [])]
        for j, app in enumerate(apps):
            report('Copying ' + app['label'] + ' (Android app data)', 2 + 90 * (len(parts) + j) / total)
            part_id = 'android:' + app['package']
            if app['running']:
                skipped.append({'id': part_id, 'label': app['label'], 'reason': 'It was open; close it and back up again'})
                continue
            rel = archive_name(part_id)
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                result = android.backup_data(app['package'], dest)
            except android.FrameError as error:
                skipped.append({'id': part_id, 'label': app['label'], 'reason': str(error)})
                continue
            entries.append({'id': part_id, 'kind': 'android', 'label': app['label'] + ' (Android app data)',
                            'package': app['package'], 'instance': result.get('instance'), 'archive': rel,
                            'sha256': result['sha256'], 'archive_bytes': dest.stat().st_size,
                            'files': result.get('files'), 'bytes': result.get('bytes')})
        report('Writing the manifest', 95)
        manifest = {'format': FORMAT, 'app': 'Frame Control', 'name': name,
                    'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    'headset': {'name': headset or android.FRAME, 'build': plan.get('build'),
                                'version': plan.get('version')},
                    'parts': entries, 'skipped': skipped, 'excluded': plan.get('excluded', [])}
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=1))
        os.rename(str(staging), str(final))
    except BaseException:
        shutil.rmtree(str(staging), ignore_errors=True)
        raise
    size = sum(e['archive_bytes'] for e in entries)
    message = 'Backed up %d part%s (%s) to %s' % (len(entries), '' if len(entries) == 1 else 's',
                                                   human(size), final)
    if skipped:
        message += '; %d skipped' % len(skipped)
    return {'message': message, 'name': name, 'path': str(final), 'parts': len(entries),
            'bytes': size, 'skipped': skipped}


def human(n):
    for unit in ('bytes', 'KB', 'MB', 'GB'):
        if n < 1000 or unit == 'GB':
            return ('%d %s' % (n, unit)) if unit == 'bytes' else '%.1f %s' % (n, unit)
        n /= 1000.0


def read_manifest(name):
    path = backup_path(name)
    try:
        manifest = json.loads((path / 'manifest.json').read_text())
    except (OSError, ValueError):
        raise BackupError('that backup has no readable manifest')
    if not isinstance(manifest, dict) or manifest.get('format') != FORMAT or \
            not isinstance(manifest.get('parts'), list):
        raise BackupError('that backup was made by a newer or unknown version')
    for part in manifest['parts']:
        if (not isinstance(part, dict) or not PART.fullmatch(str(part.get('id'))) or
                not ARCHIVE.fullmatch(str(part.get('archive'))) or part['archive'] != archive_name(part['id'])):
            raise BackupError('that backup manifest lists something unexpected')
    return path, manifest


def list_backups():
    root = backup_root()
    out = []
    try:
        names = sorted((p.name for p in root.iterdir() if NAME.fullmatch(p.name) and p.is_dir()), reverse=True)
    except OSError:
        names = []
    for name in names:
        try:
            _, m = read_manifest(name)
        except BackupError as error:
            out.append({'name': name, 'error': str(error)})
            continue
        out.append({'name': name, 'created': m.get('created'), 'build': (m.get('headset') or {}).get('build'),
                    'headset': (m.get('headset') or {}).get('name'), 'parts': len(m['parts']),
                    'bytes': sum(p.get('archive_bytes') or 0 for p in m['parts'])})
    return {'backups': out, 'folder': str(root)}


def restore_plan(name):
    """Each part of a backup and whether it can go back now; reads only."""
    path, manifest = read_manifest(name)
    plans, check = {}, []
    for part in manifest['parts']:
        archive = path / part['archive']
        state = None
        if not archive.is_file():
            state = 'missing'
        elif _sha256(archive) != part.get('sha256'):
            state = 'damaged'
        plans[part['id']] = {'id': part['id'], 'kind': part.get('kind'), 'label': part.get('label'),
                             'bytes': part.get('bytes'), 'status': state}
        if state is None and part['kind'] != 'android':
            check.append({'id': part['id'], 'files': [f['path'] for f in part.get('files') or []]})
    if check:
        answer = remote_json('check', src=json.dumps({'parts': check}).encode())
        for result in answer.get('parts', []):
            plan = plans.get(result.get('id'))
            if plan:
                plan.update(status=result.get('status'), replace=result.get('replace', 0),
                            new=result.get('new', 0), held=result.get('held', {}))
    android_parts = [p for p in plans.values() if p['kind'] == 'android' and p['status'] is None]
    if android_parts:
        installed = {a['package']: a for a in android.list_apps()}
        for plan in android_parts:
            app = installed.get(plan['id'].split(':', 1)[1])
            plan['status'] = 'not_installed' if not app else 'running' if app.get('running') else 'ok'
            if plan['status'] == 'not_installed':
                plan['reason'] = 'Install the app first, then restore its data'
            elif plan['status'] == 'ok':
                plan['replace'] = 1  # the app's whole private data folder, kept beside it
    for plan in plans.values():
        plan.setdefault('reason', REASONS.get(plan['status']) if plan['status'] != 'ok' else None)
    return {'name': name, 'headset': manifest.get('headset'), 'parts': list(plans.values())}


def restore(name, ids, confirmed=False, report=lambda stage, percent=None: None):
    """Restore the chosen parts that can go back now; the rest are skipped, not failed."""
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and PART.fullmatch(i) for i in ids):
        raise BackupError('choose what to restore')
    if confirmed is not True:
        raise BackupError('confirm the restore first: it replaces files on the headset')
    path, manifest = read_manifest(name)
    by_id = {p['id']: p for p in manifest['parts']}
    plan = {p['id']: p for p in restore_plan(name)['parts']}
    stamp = time.strftime('%Y%m%d-%H%M%S')
    done, skipped = [], []
    for i, part_id in enumerate(ids):
        part, state = by_id.get(part_id), plan.get(part_id)
        if not part or not state:
            skipped.append({'id': part_id, 'reason': 'Not in this backup'})
            continue
        if state['status'] != 'ok':
            skipped.append({'id': part_id, 'label': state['label'], 'reason': state.get('reason') or state['status']})
            continue
        report('Restoring ' + state['label'], 5 + 90 * i / len(ids))
        archive = path / part['archive']
        try:
            if part['kind'] == 'android':
                result = android.restore_data(part_id.split(':', 1)[1], str(archive))
            else:
                with open(str(archive), 'rb') as src:
                    result = remote_json('restore', part_id, stamp, src=src, timeout=1800)
        except android.FrameError as error:
            skipped.append({'id': part_id, 'label': state['label'], 'reason': str(error)})
            continue
        done.append(dict(result, id=part_id, label=state['label']))
    message = 'Restored %d part%s' % (len(done), '' if len(done) == 1 else 's')
    if skipped:
        message += ', skipped %d' % len(skipped)
    return {'message': message, 'restored': done, 'skipped': skipped}


# ---- Game Mode ---------------------------------------------------------------

def session_status():
    return remote_json('session', timeout=30)


def session_command(selector):
    """The switch to Game Mode, exactly as Valve's devkit tools run it."""
    if selector not in SELECTORS:
        raise BackupError('this SteamOS build has no session switch command; use the steps in the guide')
    return shlex.join([selector, 'gamescope'])


def return_to_game_mode(confirmed=False):
    if confirmed is not True:
        raise BackupError('confirm first: switching closes the desktop and any apps open in it')
    state = session_status()
    if state.get('mode') == 'game':
        return {'message': 'The headset is already in Game Mode. The desktop you see is a panel: '
                           'close it from the Steam dashboard.', 'state': state, 'switched': False}
    command = session_command(state.get('selector'))
    try:
        # The session restarts under it, so the command may not get to answer.
        _ssh(command, timeout=60)
    except BackupError as error:
        if 'took too long' not in str(error):
            raise BackupError('the switch was refused: %s. Use the manual steps in the guide.' % error)
    return {'message': 'Asked the headset to return to Game Mode; it restarts its session in a few seconds',
            'state': state, 'switched': True, 'command': command}


def main():
    cmd, *args = sys.argv[1:] or ['help']
    try:
        if cmd == 'backup':
            r = backup(lambda stage, percent=None: print(stage, file=sys.stderr))
        elif cmd == 'list':
            r = list_backups()
        elif cmd == 'plan' and len(args) == 1:
            r = restore_plan(args[0])
        elif cmd == 'restore' and len(args) >= 2:
            r = restore(args[0], args[1:], confirmed=True)
        elif cmd == 'session':
            r = session_status()
        elif cmd == 'game-mode':
            r = return_to_game_mode(confirmed=True)
        else:
            print(__doc__.strip().splitlines()[-1], file=sys.stderr)
            return 2
    except android.FrameError as error:
        print('error:', error, file=sys.stderr)
        return 1
    print(json.dumps(r, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
