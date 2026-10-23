"""Backup and restore on the Frame: what to save, packing it and putting it back. Stdlib only.

Runs on the headset as `python3 -c <this file> <command> ...` (ui/frame_backup.py sends it),
so stdin is free for the archive or file list. Commands:

  plan                 JSON: the headset's build and every part worth saving, with sizes
  pack PART            a tar.gz of that part's files on stdout (reads only)
  check                stdin JSON {"parts": [{"id", "files": [paths]}]}: what a restore would do
  restore PART STAMP   stdin tar.gz: write that part's restorable files, keeping replaced ones
  session              JSON: Game Mode or Desktop Mode, and the switch command on this image

Paths are relative to the home folder, with '/' separators, everywhere: in archives, in the
manifest and in `check`. Nothing here deletes a file. `restore` replaces only files named in
its archive, and first copies each one it replaces under PREVIOUS/<stamp>/.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

# FRAME_BACKUP_HOME: the tests point this at a folder laid out like the Frame's home.
HOME = Path(os.environ.get('FRAME_BACKUP_HOME') or Path.home())
STEAM = '.local/share/Steam'
COMPAT = STEAM + '/steamapps/compatdata'
PREFIX_USER = 'pfx/drive_c/users/steamuser'
# Where Windows games keep saves inside a Proton prefix. Steam Cloud covers many games, not all.
SAVE_DIRS = ('AppData/Roaming', 'AppData/Local', 'AppData/LocalLow', 'Documents', 'Saved Games')
# Wine's and Windows' own folders inside those: caches, not saves.
SAVE_SKIP = ('AppData/Local/Temp', 'AppData/Local/Microsoft', 'AppData/Roaming/Microsoft',
             'AppData/Local/D3DSCache', 'AppData/Local/NVIDIA', 'AppData/Local/CrashDumps',
             'AppData/LocalLow/Microsoft')
# Native Linux games: the engines' standard save folders.
LINUX_SAVES = ('.config/unity3d', '.local/share/godot/app_userdata')
# Steam settings. Controller layouts go back; the rest is kept so you can look things up.
STEAM_RESTORE = ('241100/remote/controller_config',)  # under userdata/<account>/
STEAM_REFERENCE = ('config/localconfig.vdf', 'config/shortcuts.vdf', 'config/grid')
STEAM_CONTROLLER = STEAM + '/steamapps/common/Steam Controller Configs'  # <account>/config/
# Desktop settings worth keeping. Steam rewrites steamvr.vrsettings while SteamVR runs, so
# it's only for reference.
SYSTEM_RESTORE = ('.config/kdeglobals', '.config/kwinrc', '.config/kxkbrc', '.config/konsolerc',
                  '.config/dolphinrc')
SYSTEM_REFERENCE = ('.config/openvr/config/steamvr.vrsettings',)
PREVIOUS = '.local/share/frame-control/restore-previous'
MAX_FILE = 2 * 1024 ** 3      # a bigger "save" is a cache or a video; listed as skipped
MAX_PART = 20 * 1024 ** 3
MAX_FILES = 100000
SHORTCUT_IDS = 2 ** 31        # non-Steam shortcuts and Lepton instances use ids above this

# Never copied, whatever folder they turn up in. Checked on every path, packing and restoring.
SECRET_NAMES = {'steam.token', 'loginusers.vdf', 'registry.vdf', 'config.vdf', 'secrets.env',
                'authorized_keys', 'known_hosts', 'credentials', 'credentials.json'}
SECRET_DIRS = {'.ssh', '.gnupg', '.pki', 'keyrings', 'kwalletd', 'cliproxyapi', 'tailscale'}
SECRET_SUFFIXES = ('.token', '.pem', '.key', '.kwl')
EXCLUDED = [
    'Steam sign-in: steam.token, config/config.vdf, loginusers.vdf, registry.vdf, ssfn files',
    'Keys and passwords: ~/.ssh, ~/.gnupg, keyrings and KWallet, *.token/*.key/*.pem files, '
    'Tailscale and proxy settings (secrets.env)',
    'Games themselves, Proton and runtimes (reinstall them from Steam), shader caches, Steam '
    'Cloud folders under userdata/<account>/<appid>, screenshots (Tools → Capture & Live saves them)',
    'Android apps themselves and their shared storage (/sdcard); only private app data is saved',
    'Symbolic links, and single files over 2 GiB',
]


def is_secret(rel):
    parts = PurePosixPath(rel).parts
    name = parts[-1].lower() if parts else ''
    return (name in SECRET_NAMES or name.startswith('ssfn') or name.startswith('id_rsa') or
            name.startswith('id_ed25519') or name.startswith('id_ecdsa') or
            name.endswith(SECRET_SUFFIXES) or any(p.lower() in SECRET_DIRS for p in parts[:-1]))


def safe_rel(rel):
    """A relative '/' path with no '..', '.', empty or absolute parts."""
    if not isinstance(rel, str) or not rel or '\\' in rel or '\0' in rel or rel.startswith('/'):
        return False
    parts = rel.split('/')
    return all(p not in ('', '.', '..') for p in parts) and not re.match(r'^[A-Za-z]:', rel)


def _under(rel, root):
    return rel == root or rel.startswith(root + '/')


def _walk(rel_root, skip=()):
    """Regular files under HOME/rel_root, never following links: [(rel, size)], [skipped]."""
    files, skipped = [], []
    base = HOME / rel_root
    if base.is_symlink() or not base.is_dir():
        if base.is_file() and not base.is_symlink():
            return [(rel_root, base.stat().st_size)], skipped
        return files, skipped
    for top, dirs, names in os.walk(str(base)):
        rel_top = PurePosixPath(rel_root, *Path(top).relative_to(base).parts).as_posix()
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(top, d)) and
                         not any(_under(rel_top + '/' + d, s) for s in skip) and
                         not is_secret(rel_top + '/' + d + '/x'))
        for name in sorted(names):
            path, rel = os.path.join(top, name), rel_top + '/' + name
            if os.path.islink(path) or is_secret(rel):
                continue
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if not os.path.isfile(path):
                continue
            if st.st_size > MAX_FILE:
                skipped.append({'path': rel, 'reason': 'over 2 GiB'})
                continue
            files.append((rel, st.st_size))
    return files, skipped


def _manifest_field(text, key):
    m = re.search(r'"%s"\s+"([^"]*)"' % key, text)
    return m.group(1) if m else None


def game_name(appid):
    try:
        text = (HOME / STEAM / 'steamapps' / ('appmanifest_%s.acf' % appid)).read_text(errors='replace')
    except OSError:
        return None
    return _manifest_field(text, 'name')


def accounts():
    root = HOME / STEAM / 'userdata'
    try:
        return sorted(p.name for p in root.iterdir() if p.name.isdigit() and p.is_dir()
                      and not p.is_symlink() and p.name != '0')
    except OSError:
        return []


def _prefixes():
    try:
        return sorted((p.name for p in (HOME / COMPAT).iterdir()
                       if p.name.isdigit() and (p / PREFIX_USER).is_dir()), key=int)
    except OSError:
        return []


def part_roots(part):
    """(roots to save, roots that a restore may write) for a part id, or None if unknown."""
    if part.startswith('saves:') and part[6:].isdigit():
        user = '%s/%s/%s' % (COMPAT, part[6:], PREFIX_USER)
        roots = tuple(user + '/' + d for d in SAVE_DIRS)
        return roots, roots
    if part == 'saves:linux':
        return LINUX_SAVES, LINUX_SAVES
    if part == 'settings:steam':
        save, restore = [], []
        for acct in accounts():
            base = '%s/userdata/%s/' % (STEAM, acct)
            restore += [base + r for r in STEAM_RESTORE] + ['%s/%s/config' % (STEAM_CONTROLLER, acct)]
            save += [base + r for r in STEAM_REFERENCE]
        return tuple(save + restore), tuple(restore)
    if part == 'settings:system':
        return SYSTEM_RESTORE + SYSTEM_REFERENCE, SYSTEM_RESTORE
    return None


def restore_roots(part, rel):
    """The restore roots for rel within part; the Steam ones don't depend on today's accounts."""
    if part == 'settings:steam':
        m = re.match(r'^(?:%s/userdata/(\d+)/|%s/(\d+)/)' % (re.escape(STEAM), re.escape(STEAM_CONTROLLER)), rel)
        acct = m and (m.group(1) or m.group(2))
        if not acct:
            return ()
        base = '%s/userdata/%s/' % (STEAM, acct)
        return tuple(base + r for r in STEAM_RESTORE) + ('%s/%s/config' % (STEAM_CONTROLLER, acct),)
    roots = part_roots(part)
    return roots[1] if roots else ()


def part_files(part):
    roots = part_roots(part)
    if roots is None:
        raise ValueError('unknown backup part %r' % part)
    skip = ()
    if part.startswith('saves:') and part != 'saves:linux':
        skip = tuple('%s/%s/%s/%s' % (COMPAT, part[6:], PREFIX_USER, s) for s in SAVE_SKIP)
    files, skipped = [], []
    for root in roots[0]:
        f, s = _walk(root, skip)
        files += f
        skipped += s
    return files, skipped


def part_label(part):
    if part == 'saves:linux':
        return 'Linux game saves (Unity and Godot games)'
    if part == 'settings:steam':
        return 'Steam settings and controller layouts'
    if part == 'settings:system':
        return 'Desktop and SteamVR settings'
    appid = part[6:]
    name = game_name(appid)
    if name:
        return name + ' saves'
    return ('Non-Steam game %s saves' if int(appid) >= SHORTCUT_IDS else 'Game %s saves') % appid


def plan():
    parts = []
    ids = ['saves:' + a for a in _prefixes()] + ['saves:linux', 'settings:steam', 'settings:system']
    for part in ids:
        files, skipped = part_files(part)
        if not files:
            continue
        parts.append({'id': part, 'kind': part.split(':')[0], 'label': part_label(part),
                      'files': len(files), 'bytes': sum(s for _, s in files), 'skipped': skipped,
                      'appid': part[6:] if part[6:].isdigit() else None,
                      'restorable': sum(1 for rel, _ in files
                                        if any(_under(rel, r) for r in restore_roots(part, rel)))})
    return {'build': os_release().get('BUILD_ID'), 'version': os_release().get('VERSION_ID'),
            'parts': parts, 'excluded': EXCLUDED}


def os_release():
    out = {}
    try:
        for line in Path(os.environ.get('FRAME_BACKUP_OS_RELEASE') or '/etc/os-release').read_text().splitlines():
            k, _, v = line.partition('=')
            out[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return out


def pack(part, output):
    files, _ = part_files(part)
    if len(files) > MAX_FILES or sum(s for _, s in files) > MAX_PART:
        raise ValueError('this part is too big to back up (over 100,000 files or 20 GiB)')
    with tarfile.open(fileobj=output, mode='w|gz') as archive:
        for rel, _ in files:
            path = HOME / rel
            try:
                with open(str(path), 'rb') as src:
                    st = os.fstat(src.fileno())
                    member = tarfile.TarInfo(rel)
                    member.size, member.mtime, member.mode = st.st_size, int(st.st_mtime), st.st_mode & 0o755
                    archive.addfile(member, src)
            except OSError:
                continue  # gone since the walk (a game wrote it); the manifest lists what's in the archive


def target_status(part, rel):
    """None if rel may be restored now, else why not (a short code)."""
    if is_secret(rel) or not safe_rel(rel):
        return 'refused'
    if not any(_under(rel, r) for r in restore_roots(part, rel)):
        return 'reference'
    if part.startswith('saves:') and part != 'saves:linux':
        appid = part[6:]
        if int(appid) < SHORTCUT_IDS and \
                not (HOME / STEAM / 'steamapps' / ('appmanifest_%s.acf' % appid)).is_file():
            return 'not_installed'
        if not (HOME / COMPAT / appid / PREFIX_USER).is_dir():
            return 'no_prefix'
    if part == 'settings:steam':
        acct = re.search(r'/(\d+)/', rel[len(STEAM):])
        if not acct or not (HOME / STEAM / 'userdata' / acct.group(1)).is_dir():
            return 'no_account'
    # A link anywhere on the way could send the write somewhere else.
    path = HOME
    for p in rel.split('/')[:-1]:
        path = path / p
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            return 'refused'
    if (HOME / rel).is_symlink() or ((HOME / rel).exists() and not (HOME / rel).is_file()):
        return 'refused'
    return None


def check(request):
    out = []
    for item in request.get('parts', []):
        part, files = item.get('id'), item.get('files') or []
        if not isinstance(part, str) or part_roots(part) is None:
            out.append({'id': part, 'status': 'unknown'})
            continue
        counts = {}
        replace = new = 0
        for rel in files:
            why = target_status(part, rel)
            if why:
                counts[why] = counts.get(why, 0) + 1
            elif (HOME / rel).exists():
                replace += 1
            else:
                new += 1
        status = 'ok' if replace + new else next(
            (c for c in ('not_installed', 'no_prefix', 'no_account', 'reference', 'refused') if c in counts), 'empty')
        out.append({'id': part, 'status': status, 'replace': replace, 'new': new, 'held': counts})
    return {'parts': out}


def _sha256(path):
    digest = hashlib.sha256()
    with open(str(path), 'rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def restore(part, stamp, source):
    if part_roots(part) is None:
        raise ValueError('unknown backup part %r' % part)
    if not re.fullmatch(r'\d{8}-\d{6}', stamp):
        raise ValueError('bad restore stamp')
    # Spool first: everything is checked before anything is written.
    spool_dir = HOME / '.cache/frame-control'
    spool_dir.mkdir(parents=True, exist_ok=True)
    written, replaced, held = [], [], {}
    with tempfile.TemporaryDirectory(prefix='restore-', dir=str(spool_dir)) as tmp:
        spool = Path(tmp) / 'part.tar.gz'
        with open(str(spool), 'wb') as dst:
            shutil.copyfileobj(source, dst, 1024 * 1024)
        todo, names, total = [], set(), 0
        with tarfile.open(str(spool), 'r:gz') as archive:
            for member in archive:
                if not member.isfile() or not safe_rel(member.name) or member.name in names:
                    raise ValueError('backup has an unsafe, duplicate or non-file entry: %r' % member.name[:200])
                names.add(member.name)
                total += member.size
                if len(names) > MAX_FILES or total > MAX_PART:
                    raise ValueError('backup part is too big')
                why = target_status(part, member.name)
                if why:
                    held[why] = held.get(why, 0) + 1
                else:
                    todo.append(member.name)
        previous = HOME / PREVIOUS / stamp
        keep = set(todo)
        with tarfile.open(str(spool), 'r:gz') as archive:
            for member in archive:
                if member.name not in keep:
                    continue
                target = HOME / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                part_file = target.parent / ('.frame-restore-%d.part' % os.getpid())
                with archive.extractfile(member) as src, open(str(part_file), 'wb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                os.chmod(str(part_file), (member.mode & 0o755) | 0o600)
                os.utime(str(part_file), (member.mtime, member.mtime))
                if target.exists():
                    if _sha256(target) == _sha256(part_file):
                        os.unlink(str(part_file))
                        held['same'] = held.get('same', 0) + 1
                        continue
                    keep_copy = previous / member.name
                    keep_copy.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(target), str(keep_copy))
                    replaced.append(member.name)
                os.replace(str(part_file), str(target))
                written.append(member.name)
    return {'id': part, 'written': len(written), 'replaced': len(replaced), 'held': held,
            'previous': (PREVIOUS + '/' + stamp) if replaced else None}


# ---- Game Mode and Desktop Mode --------------------------------------------
#
# The Frame normally runs gamescope (Game Mode) with Plasma nested inside it as one panel
# (steamos-nested-desktop). A full Desktop Mode session is SDDM autologin into Plasma
# instead. Valve's own devkit tools (frame/devkit-utils: steamos-get-status, steamos-delete)
# read the session from these files and switch with holo-session-select or
# steamos-session-select, so that's what this reads and suggests.

SDDM_CONFS = ('/etc/sddm.conf.d/zz-steamos-autologin.conf', '/etc/sddm.conf.d/steamos.conf')


def _running(name, full=False):
    try:
        return subprocess.call(['pgrep', '-f' if full else '-x', name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0
    except OSError:
        return False


def session():
    configured, conf = None, None
    for path in SDDM_CONFS:
        try:
            text = Path(path).read_text(errors='replace')
        except OSError:
            continue
        m = re.search(r'^\s*Session\s*=\s*(\S+)', text, re.M)
        conf, configured = path, (m.group(1) if m else None)
        break
    selector = next((s for s in ('holo-session-select', 'steamos-session-select') if shutil.which(s)), None)
    gamescope, plasma = _running('gamescope'), _running('plasmashell')
    nested = _running('steamos-nested-desktop', full=True)  # a script: its process name is the shell's
    if gamescope:
        mode = 'game'
    elif plasma or (configured and 'plasma' in configured):
        mode = 'desktop'
    else:
        mode = 'unknown'
    return {'mode': mode, 'gamescope': gamescope, 'plasma': plasma, 'nested_desktop': nested,
            'configured': configured, 'config_file': conf, 'selector': selector}


def main(argv):
    cmd, args = (argv[0] if argv else ''), argv[1:]
    try:
        if cmd == 'plan':
            print(json.dumps(plan()))
        elif cmd == 'pack' and len(args) == 1:
            out = sys.stdout.buffer
            pack(args[0], out)
            out.flush()
        elif cmd == 'check':
            print(json.dumps(check(json.load(sys.stdin))))
        elif cmd == 'restore' and len(args) == 2:
            print(json.dumps(restore(args[0], args[1], sys.stdin.buffer)))
        elif cmd == 'session':
            print(json.dumps(session()))
        else:
            sys.stderr.write('usage: plan | pack PART | check | restore PART STAMP | session\n')
            return 2
    except (OSError, ValueError, tarfile.TarError) as error:
        sys.stderr.write(str(error) + '\n')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
