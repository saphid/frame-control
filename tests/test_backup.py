"""Backup and recovery kit (ui/frame_backup.py, ui/frame_backup_remote.py) against a folder laid
out like the Frame's home. The headset-side script runs for real, locally; only SSH is faked."""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import frame_android as android  # noqa: E402
import frame_backup as backup  # noqa: E402
import frame_backup_remote as remote  # noqa: E402
import server  # noqa: E402

STEAM = '.local/share/Steam'
USER = STEAM + '/steamapps/compatdata/%s/pfx/drive_c/users/steamuser'
SECRETS = ['.steam/steam.token', STEAM + '/config/config.vdf', STEAM + '/config/loginusers.vdf',
           STEAM + '/ssfn123456', '.ssh/id_ed25519', '.ssh/authorized_keys',
           USER % 1234 + '/AppData/Roaming/Launcher/session.token',
           USER % 1234 + '/AppData/Roaming/Launcher/.ssh/id_rsa',
           '.config/cliproxyapi/secrets.env', '.local/share/keyrings/login.keyring']


def write(home, rel, data=b'x'):
    path = Path(home) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


def manifest(home, appid, name):
    write(home, '%s/steamapps/appmanifest_%s.acf' % (STEAM, appid),
          '"AppState"\n{\n\t"appid"\t\t"%s"\n\t"name"\t\t"%s"\n}\n' % (appid, name))


def frame_home(home):
    """A Frame before a reset: one Proton game, a Linux game, settings and secrets."""
    manifest(home, 1234, 'Test Game')
    write(home, USER % 1234 + '/AppData/Roaming/Studio/Game/save1.dat', b'save one')
    write(home, USER % 1234 + '/Documents/My Games/Game/profile.sav', b'profile')
    write(home, USER % 1234 + '/AppData/Local/Temp/junk.tmp', b'junk')
    write(home, USER % 1234 + '/AppData/Local/Microsoft/Windows/x.db', b'wine')
    write(home, USER % 999 + '/AppData/Local/Temp/only-cache', b'c')        # no saves: no part
    write(home, STEAM + '/steamapps/compatdata/2800000001/internal/org.example/x', b'android')
    write(home, STEAM + '/userdata/555/config/localconfig.vdf', b'local')
    write(home, STEAM + '/userdata/555/config/shortcuts.vdf', b'shortcuts')
    write(home, STEAM + '/userdata/555/241100/remote/controller_config/1234/layout.vdf', b'layout')
    write(home, STEAM + '/userdata/555/1234/remote/cloud.sav', b'cloud')    # Steam Cloud's own
    write(home, STEAM + '/userdata/555/760/remote/1234/screenshots/a.jpg', b'shot')
    write(home, '.config/kdeglobals', b'[General]')
    write(home, '.config/openvr/config/steamvr.vrsettings', b'{}')
    write(home, '.config/unity3d/Company/LinuxGame/prefs', b'prefs')
    write(home, '.bashrc', b'# mine')
    for rel in SECRETS:
        write(home, rel, b'SECRET')


class Remote(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        patcher = patch.object(remote, 'HOME', self.home)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def files(self, part):
        return [rel for rel, _ in remote.part_files(part)[0]]

    def test_plan_picks_saves_and_settings_and_never_secrets(self):
        frame_home(self.home)
        plan = remote.plan()
        ids = [p['id'] for p in plan['parts']]
        self.assertEqual(ids, ['saves:1234', 'saves:linux', 'settings:steam', 'settings:system'])
        self.assertEqual(plan['parts'][0]['label'], 'Test Game saves')
        saves = self.files('saves:1234')
        self.assertEqual(sorted(saves), [USER % 1234 + '/AppData/Roaming/Studio/Game/save1.dat',
                                         USER % 1234 + '/Documents/My Games/Game/profile.sav'])
        steam = self.files('settings:steam')
        self.assertIn(STEAM + '/userdata/555/241100/remote/controller_config/1234/layout.vdf', steam)
        self.assertIn(STEAM + '/userdata/555/config/localconfig.vdf', steam)
        self.assertFalse([f for f in steam if '/1234/remote/' in f or '/760/' in f])
        everything = sum((self.files(i) for i in ids), [])
        for rel in SECRETS + ['.bashrc']:
            self.assertNotIn(rel, everything)
        self.assertFalse([f for f in everything if remote.is_secret(f)])
        self.assertTrue(any('steam.token' in x for x in plan['excluded']))
        # The controller layout goes back; localconfig.vdf and shortcuts.vdf are for reference.
        steam_part = plan['parts'][2]
        self.assertEqual((steam_part['files'], steam_part['restorable']), (3, 1))

    def test_secret_names(self):
        for rel in SECRETS + ['a/b/ID_RSA.pub', 'x/kwalletd/k', 'x/cert.PEM']:
            self.assertTrue(remote.is_secret(rel), rel)
        for rel in ['saves/game.sav', 'Documents/tokens-collected.txt', 'config/localconfig.vdf']:
            self.assertFalse(remote.is_secret(rel), rel)

    @unittest.skipIf(os.name == 'nt', 'symlinks need privileges on Windows')
    def test_links_are_never_followed(self):
        frame_home(self.home)
        outside = write(self.home, 'elsewhere/private.txt', b'p')
        base = self.home / (USER % 1234) / 'Documents'
        os.symlink(str(outside.parent), str(base / 'linked-dir'))
        os.symlink(str(outside), str(base / 'linked-file'))
        self.assertFalse([f for f in self.files('saves:1234') if 'linked' in f])

    def test_big_files_are_listed_as_skipped(self):
        frame_home(self.home)
        with patch.object(remote, 'MAX_FILE', 3):
            files, skipped = remote.part_files('saves:1234')
        self.assertEqual(files, [])
        self.assertEqual({s['reason'] for s in skipped}, {'over 2 GiB'})

    def test_pack_holds_exactly_the_planned_files(self):
        frame_home(self.home)
        out = io.BytesIO()
        remote.pack('saves:1234', out)
        out.seek(0)
        with tarfile.open(fileobj=out, mode='r:gz') as archive:
            names = sorted(m.name for m in archive)
        self.assertEqual(names, sorted(self.files('saves:1234')))
        with self.assertRaises(ValueError):
            remote.pack('saves:../../etc', io.BytesIO())

    def archive(self, members):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w:gz') as tar:
            for name, data in members:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        out.seek(0)
        return out

    def test_check_after_a_reset(self):
        save = USER % 1234 + '/AppData/Roaming/Studio/Game/save1.dat'
        ask = {'parts': [{'id': 'saves:1234', 'files': [save]},
                         {'id': 'settings:steam', 'files': [STEAM + '/userdata/555/241100/remote/controller_config/1/a.vdf']},
                         {'id': 'settings:system', 'files': ['.config/openvr/config/steamvr.vrsettings']},
                         {'id': 'saves:../x', 'files': []}]}
        states = lambda: [p['status'] for p in remote.check(ask)['parts']]  # noqa: E731
        self.assertEqual(states(), ['not_installed', 'no_account', 'reference', 'unknown'])
        manifest(self.home, 1234, 'Test Game')
        (self.home / STEAM / 'userdata/555').mkdir(parents=True)
        self.assertEqual(states()[:2], ['no_prefix', 'ok'])
        (self.home / (USER % 1234)).mkdir(parents=True)
        result = remote.check(ask)['parts'][0]
        self.assertEqual((result['status'], result['new'], result['replace']), ('ok', 1, 0))
        write(self.home, save, b'newer')
        self.assertEqual(remote.check(ask)['parts'][0]['replace'], 1)

    def test_restore_replaces_only_its_files_and_keeps_the_old_ones(self):
        manifest(self.home, 1234, 'Test Game')
        save = USER % 1234 + '/AppData/Roaming/Studio/Game/save1.dat'
        write(self.home, save, b'played since')
        other = write(self.home, USER % 1234 + '/AppData/Roaming/Studio/Game/other.dat', b'untouched')
        bashrc = write(self.home, '.bashrc', b'# mine')
        source = self.archive([(save, b'from backup'), (USER % 1234 + '/Documents/new.sav', b'new'),
                               ('.bashrc', b'# replaced?')])
        result = remote.restore('saves:1234', '20261023-120000', source)
        self.assertEqual((result['written'], result['replaced']), (2, 1))
        self.assertEqual(result['held'], {'reference': 1})
        self.assertEqual((self.home / save).read_bytes(), b'from backup')
        self.assertEqual(other.read_bytes(), b'untouched')
        self.assertEqual(bashrc.read_bytes(), b'# mine')
        kept = self.home / remote.PREVIOUS / '20261023-120000' / save
        self.assertEqual(kept.read_bytes(), b'played since')
        self.assertFalse([p for p in (self.home / save).parent.iterdir() if p.name.endswith('.part')])

    def test_unsafe_archives_write_nothing(self):
        manifest(self.home, 1234, 'Test Game')
        (self.home / (USER % 1234)).mkdir(parents=True)
        good = (USER % 1234 + '/Documents/a.sav', b'a')
        for bad in ('../escape', '/etc/passwd', USER % 1234 + '/Documents/../../../../../../x',
                    USER % 1234 + '/Documents/a.sav'):
            with self.assertRaises(ValueError, msg=bad):
                remote.restore('saves:1234', '20261023-120000', self.archive([good, (bad, b'evil')]))
            self.assertFalse((self.home / good[0]).exists(), bad)
        link = io.BytesIO()
        with tarfile.open(fileobj=link, mode='w:gz') as tar:
            info = tarfile.TarInfo(USER % 1234 + '/Documents/l')
            info.type, info.linkname = tarfile.SYMTYPE, '/etc/passwd'
            tar.addfile(info)
        link.seek(0)
        with self.assertRaises(ValueError):
            remote.restore('saves:1234', '20261023-120000', link)
        with self.assertRaises(ValueError):
            remote.restore('saves:1234', '../stamp', self.archive([good]))

    def test_restore_refuses_secrets_and_other_games(self):
        manifest(self.home, 1234, 'Test Game')
        (self.home / (USER % 1234)).mkdir(parents=True)
        result = remote.restore('saves:1234', '20261023-120000', self.archive([
            (USER % 1234 + '/AppData/Roaming/L/auth.token', b't'), (USER % 5678 + '/Documents/x.sav', b'x')]))
        self.assertEqual(result['written'], 0)
        self.assertEqual(result['held'], {'refused': 1, 'reference': 1})


class Session(unittest.TestCase):
    def state(self, targets, running=(), configured=None):
        with tempfile.TemporaryDirectory() as folder:
            conf = write(folder, 'sddm.conf', 'Session=%s\n' % (configured or 'gamescope.desktop'))
            with patch.object(remote, 'SDDM_CONFS', (str(conf),)), \
                    patch.object(remote, '_session_target', side_effect=targets), \
                    patch.object(remote, '_running', side_effect=lambda n, full=False: n in running), \
                    patch.object(remote.shutil, 'which', return_value='/usr/bin/steamosctl'):
                return remote.session()

    def test_full_plasma_with_vr_gamescope_is_desktop(self):
        # Issue #142, SteamOS 0.5.6: steamvr-plasma also starts nested scripts.
        state = self.state(['inactive', 'active'],
                           {'gamescope-wl', 'plasmashell', 'steamos-nested-desktop'},
                           configured='gamescope.desktop')
        self.assertEqual(state['mode'], 'desktop')
        self.assertTrue(state['gamescope'])
        self.assertTrue(state['nested_desktop'])
        self.assertEqual(state['selector'], 'steamosctl')
        self.assertEqual(state['session_targets']['plasma-workspace-wayland.target'], 'active')
        with patch.object(backup, 'session_status', return_value=state), patch.object(backup, '_ssh') as ssh:
            self.assertTrue(backup.return_to_game_mode(confirmed=True)['switched'])
            ssh.assert_called_once_with('steamosctl switch-to-game-mode', timeout=60)

    def test_game_target_wins_with_or_without_nested_desktop(self):
        for running in ((), {'gamescope-wl'}, {'gamescope', 'plasmashell', 'steamos-nested-desktop'}):
            state = self.state(['active', 'inactive'], running, configured='plasma.desktop')
            self.assertEqual(state['mode'], 'game')
            with patch.object(backup, 'session_status', return_value=state), patch.object(backup, '_ssh') as ssh:
                self.assertFalse(backup.return_to_game_mode(confirmed=True)['switched'])
                ssh.assert_not_called()

    def test_conflicting_incomplete_and_transitional_targets_block_return(self):
        for targets in (['active', 'active'], ['inactive', 'inactive'], ['active', 'unknown'],
                        ['not-found', 'active'], ['unknown', 'unknown'], ['inactive', 'activating'],
                        ['deactivating', 'active'], ['failed', 'active']):
            with self.subTest(targets=targets):
                state = self.state(targets, {'gamescope', 'plasmashell'}, 'plasma.desktop')
                self.assertEqual(state['mode'], 'unknown')
                with patch.object(backup, 'session_status', return_value=state), patch.object(backup, '_ssh') as ssh:
                    with self.assertRaisesRegex(backup.BackupError, 'nothing was changed'):
                        backup.return_to_game_mode(confirmed=True)
                    ssh.assert_not_called()

    def test_older_builds_use_only_unambiguous_running_processes(self):
        cases = [((), 'unknown'), ({'plasmashell'}, 'desktop'),
                 ({'gamescope'}, 'game'), ({'gamescope-wl'}, 'game'),
                 ({'start-gamescope-session'}, 'game'),
                 ({'gamescope', 'plasmashell'}, 'unknown'),
                 ({'gamescope', 'steamos-nested-desktop'}, 'unknown')]
        for running, expected in cases:
            with self.subTest(running=running):
                state = self.state(['not-found', 'not-found'], running, 'plasma.desktop')
                self.assertEqual(state['mode'], expected)
                self.assertEqual(state['mode_source'], 'legacy-processes')

    def test_target_probe_parses_systemd_and_uses_main_user_bus(self):
        cases = [('LoadState=loaded\nActiveState=active\n', 0, 'active'),
                 ('ActiveState=inactive\nLoadState=loaded\n', 0, 'inactive'),
                 ('LoadState=not-found\nActiveState=inactive\n', 0, 'not-found'),
                 ('LoadState=error\nActiveState=active\n', 0, 'unknown'),
                 ('garbage', 0, 'unknown'), ('LoadState=loaded\nActiveState=active', 1, 'unknown')]
        for stdout, code, expected in cases:
            with self.subTest(stdout=stdout, code=code), \
                    patch.object(remote.os, 'getuid', return_value=1000, create=True), \
                    patch.object(remote.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, stdout)) as run:
                self.assertEqual(remote._session_target('gamescope-session.target'), expected)
                self.assertEqual(run.call_args.args[0], ['systemctl', '--user', 'show',
                                 'gamescope-session.target', '--property=LoadState', '--property=ActiveState'])
                self.assertEqual(run.call_args.kwargs['timeout'], 5)
                self.assertEqual(run.call_args.kwargs['env']['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=/run/user/1000/bus')
                self.assertEqual(run.call_args.kwargs['env']['XDG_RUNTIME_DIR'], '/run/user/1000')
        for error in (OSError('no systemctl'), subprocess.TimeoutExpired('systemctl', 5)):
            with patch.object(remote.os, 'getuid', return_value=1000, create=True), \
                    patch.object(remote.subprocess, 'run', side_effect=error):
                self.assertEqual(remote._session_target('gamescope-session.target'), 'unknown')

    def test_selector_preference_and_older_builds(self):
        for available, expected in [({'steamosctl', 'steamos-session-select'}, 'steamosctl'),
                                    ({'holo-session-select', 'steamos-session-select'}, 'holo-session-select'),
                                    ({'steamos-session-select'}, 'steamos-session-select'), (set(), None)]:
            with patch.object(remote, 'SDDM_CONFS', ()), \
                    patch.object(remote, '_session_target', return_value='unknown'), \
                    patch.object(remote, '_running', return_value=False), \
                    patch.object(remote.shutil, 'which', side_effect=lambda n: '/usr/bin/' + n if n in available else None):
                self.assertEqual(remote.session()['selector'], expected)

    def test_script_probe_does_not_match_names_in_transmitted_python_source(self):
        with patch.object(remote.subprocess, 'call', return_value=1) as call:
            self.assertFalse(remote._running('steamos-nested-desktop', full=True))
            pattern = call.call_args.args[0][-1]
        for command in ('/usr/bin/steamos-nested-desktop',
                        '/bin/sh /usr/bin/steamos-nested-desktop',
                        'bash steamos-nested-desktop --flag'):
            self.assertIsNotNone(re.search(pattern, command), command)
        for command in ('python3 -c ' + backup.REMOTE.read_text(),
                        '/bin/sh -c pgrep -f steamos-nested-desktop',
                        '/usr/bin/steamos-nested-desktop-other'):
            self.assertIsNone(re.search(pattern, command), command)


def fake_ssh(home, os_release):
    """Runs the headset-side command locally, as the Frame's python3 would."""
    def run(command, src=None, dst=None, timeout=None):
        argv = shlex.split(command)
        assert argv[:2] == ['python3', '-c'], argv
        data = src if isinstance(src, bytes) else src.read() if src is not None else b''
        env = dict(os.environ, FRAME_BACKUP_HOME=str(home), FRAME_BACKUP_OS_RELEASE=str(os_release))
        r = subprocess.run([sys.executable, *argv[1:]], input=data, capture_output=True, env=env)
        if r.returncode:
            raise backup.BackupError(r.stderr.decode(errors='replace'))
        if dst is not None:
            dst.write(r.stdout)
            return None
        return r.stdout
    return run


class Local(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.home, self.store = base / 'frame', base / 'backups'
        self.release = write(base, 'os-release', 'ID=steamos\nVERSION_ID=0.4.1\nBUILD_ID=20260925.6191901\n')
        frame_home(self.home)
        for p in (patch.dict(os.environ, FRAME_BACKUP_DIR=str(self.store)),
                  patch.object(backup, '_ssh', side_effect=fake_ssh(self.home, self.release))):
            p.start()
            self.addCleanup(p.stop)

    def android_backup(self, package, destination):
        write(Path(destination).parent, Path(destination).name, b'android archive ' + package.encode())
        return {'package': package, 'instance': android.instance_id(package), 'files': 3, 'bytes': 42,
                'path': str(destination), 'sha256': backup._sha256(destination)}

    def make(self):
        apps = [{'package': 'org.example.open', 'label': 'Open app', 'running': True},
                {'package': 'org.example.game', 'label': 'Game', 'running': False}]
        with patch.object(android, 'list_apps', return_value=apps), \
                patch.object(android, 'backup_data', side_effect=self.android_backup) as data, \
                patch.object(backup.time, 'strftime', side_effect=lambda f: '2026-10-23-120000' if f == '%Y-%m-%d-%H%M%S'
                             else '2026-10-23T12:00:00+0100'):
            result = backup.backup(headset='My Frame')
        data.assert_called_once()
        return result

    def test_backup_writes_a_manifest_with_checksums(self):
        result = self.make()
        folder = backup.backup_path('2026-10-23-120000')  # resolved: macOS's temp folder is a link
        self.assertEqual(result['path'], str(folder))
        self.assertEqual(sorted(p.name for p in self.store.iterdir()), ['2026-10-23-120000'])  # no .partial left
        m = json.loads((folder / 'manifest.json').read_text())
        self.assertEqual(m['headset'], {'name': 'My Frame', 'build': '20260925.6191901', 'version': '0.4.1'})
        self.assertEqual([p['id'] for p in m['parts']],
                         ['saves:1234', 'saves:linux', 'settings:steam', 'settings:system', 'android:org.example.game'])
        for part in m['parts']:
            self.assertEqual(backup._sha256(folder / part['archive']), part['sha256'])
        saves = m['parts'][0]
        self.assertEqual(saves['archive'], 'saves/saves-1234.tar.gz')
        self.assertEqual(sum(f['bytes'] for f in saves['files']), saves['bytes'])
        self.assertEqual(saves['files'][0]['sha256'], __import__('hashlib').sha256(b'save one').hexdigest())
        self.assertEqual([s['id'] for s in m['skipped']], ['android:org.example.open'])
        for part in m['parts'][:-1]:
            with tarfile.open(str(folder / part['archive'])) as tar:
                for member in tar:
                    self.assertFalse(remote.is_secret(member.name), member.name)
                    self.assertNotEqual(tar.extractfile(member).read(), b'SECRET', member.name)

    def test_a_failed_backup_leaves_nothing_behind(self):
        with patch.object(backup, 'inspect_archive', side_effect=backup.BackupError('cut off')), \
                patch.object(android, 'list_apps', return_value=[]):
            with self.assertRaises(backup.BackupError):
                backup.backup(kinds=['saves'])
        self.assertEqual(list(self.store.iterdir()), [])

    def test_backup_names_cannot_leave_the_folder(self):
        for name in ('../2026-10-23-120000', '2026-10-23-120000/..', '..', '/etc', 'C:\\x', '',
                     '2026-10-23-120000/../../x', '2026-10-23-12000', None, 5):
            with self.assertRaises(backup.BackupError, msg=repr(name)):
                backup.backup_path(name)
        self.assertEqual(backup.backup_path('2026-10-23-120000'), (self.store / '2026-10-23-120000').resolve())

    def test_manifest_entries_cannot_point_outside_the_backup(self):
        self.make()
        path = self.store / '2026-10-23-120000' / 'manifest.json'
        m = json.loads(path.read_text())
        for archive in ('../../secret.tar.gz', '/etc/passwd', 'saves/saves-5678.tar.gz'):
            m['parts'][0]['archive'] = archive
            path.write_text(json.dumps(m))
            with self.assertRaises(backup.BackupError, msg=archive):
                backup.read_manifest('2026-10-23-120000')

    def reset(self):
        """A factory reset: the home folder is empty again."""
        import shutil
        shutil.rmtree(str(self.home))
        self.home.mkdir()

    def test_restore_after_a_reset_skips_what_is_not_back_yet(self):
        self.make()
        self.reset()
        manifest(self.home, 1234, 'Test Game')
        (self.home / (USER % 1234)).mkdir(parents=True)  # started once
        with patch.object(android, 'list_apps', return_value=[]):
            plan = {p['id']: p for p in backup.restore_plan('2026-10-23-120000')['parts']}
            self.assertEqual(plan['saves:1234']['status'], 'ok')
            self.assertEqual(plan['settings:steam']['status'], 'no_account')
            self.assertEqual(plan['android:org.example.game']['status'], 'not_installed')
            with self.assertRaises(backup.BackupError):
                backup.restore('2026-10-23-120000', ['saves:1234'])  # not confirmed
            self.assertFalse((self.home / (USER % 1234) / 'AppData').exists())
            result = backup.restore('2026-10-23-120000', ['saves:1234', 'settings:steam', 'android:org.example.game'],
                                    confirmed=True)
        self.assertEqual([r['id'] for r in result['restored']], ['saves:1234'])
        self.assertEqual({s['id'] for s in result['skipped']}, {'settings:steam', 'android:org.example.game'})
        self.assertEqual((self.home / (USER % 1234) / 'AppData/Roaming/Studio/Game/save1.dat').read_bytes(), b'save one')

    def test_android_data_goes_back_through_the_existing_helper(self):
        self.make()
        apps = [{'package': 'org.example.game', 'label': 'Game', 'running': False}]
        with patch.object(android, 'list_apps', return_value=apps), \
                patch.object(android, 'restore_data', return_value={'restored': True}) as restore:
            result = backup.restore('2026-10-23-120000', ['android:org.example.game'], confirmed=True)
        restore.assert_called_once_with('org.example.game', str(backup.backup_path('2026-10-23-120000') /
                                                                 'android' / 'org.example.game.tar.gz'))
        self.assertEqual(len(result['restored']), 1)
        apps[0]['running'] = True
        with patch.object(android, 'list_apps', return_value=apps), patch.object(android, 'restore_data') as restore:
            result = backup.restore('2026-10-23-120000', ['android:org.example.game'], confirmed=True)
        restore.assert_not_called()
        self.assertEqual(result['skipped'][0]['reason'], 'Close the app first')

    def test_a_damaged_archive_is_skipped(self):
        self.make()
        with open(str(self.store / '2026-10-23-120000/saves/saves-1234.tar.gz'), 'ab') as f:
            f.write(b'tampered')
        with patch.object(android, 'list_apps', return_value=[]):
            result = backup.restore('2026-10-23-120000', ['saves:1234'], confirmed=True)
        self.assertEqual(result['restored'], [])
        self.assertIn('checksum', result['skipped'][0]['reason'])

    def test_list_backups(self):
        self.make()
        (self.store / '.2026-10-23-130000.partial').mkdir()
        (self.store / 'notes').mkdir()
        listed = backup.list_backups()['backups']
        self.assertEqual([b['name'] for b in listed], ['2026-10-23-120000'])
        self.assertEqual(listed[0]['build'], '20260925.6191901')


class Ssh(unittest.TestCase):
    def test_bytes_go_as_input_and_files_as_stdin(self):
        done = subprocess.CompletedProcess([], 0, b'{}', b'')
        with patch.object(backup.frame_host, 'run_ssh', return_value=done) as run:
            backup._ssh('true', src=b'{"parts": []}')
            self.assertEqual(run.call_args.kwargs['input'], b'{"parts": []}')
            self.assertNotIn('stdin', run.call_args.kwargs)
            with tempfile.TemporaryFile() as f:
                backup._ssh('true', src=f)
                self.assertIs(run.call_args.kwargs['stdin'], f)
            backup._ssh('true')
            self.assertIs(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
            self.assertEqual(run.call_args.args[0][-1], 'true')
        with patch.object(backup.frame_host, 'run_ssh',
                          return_value=subprocess.CompletedProcess([], 1, b'', b'Permission denied')):
            with self.assertRaisesRegex(backup.BackupError, 'Permission denied'):
                backup._ssh('true')


class GameMode(unittest.TestCase):
    def test_command_is_only_ever_the_session_switch(self):
        self.assertEqual(backup.session_command('steamosctl'), 'steamosctl switch-to-game-mode')
        self.assertEqual(backup.session_command('steamos-session-select'), 'steamos-session-select gamescope')
        self.assertEqual(backup.session_command('holo-session-select'), 'holo-session-select gamescope')
        for bad in (None, '', 'rm -rf ~', '/tmp/steamos-session-select', 'steamos-session-select; reboot',
                    'steamosctl switch-to-desktop-mode', 'steamosctl; reboot'):
            with self.assertRaises(backup.BackupError):
                backup.session_command(bad)

    def test_switch_needs_confirmation_and_desktop_mode(self):
        with patch.object(backup, '_ssh') as ssh:
            with self.assertRaises(backup.BackupError):
                backup.return_to_game_mode()
            ssh.assert_not_called()
        with patch.object(backup, 'session_status', return_value={'mode': 'game', 'selector': 'steamos-session-select'}), \
                patch.object(backup, '_ssh') as ssh:
            self.assertFalse(backup.return_to_game_mode(confirmed=True)['switched'])
            ssh.assert_not_called()
        with patch.object(backup, 'session_status', return_value={'mode': 'unknown', 'selector': 'steamos-session-select'}), \
                patch.object(backup, '_ssh') as ssh:
            with self.assertRaisesRegex(backup.BackupError, 'nothing was changed'):
                backup.return_to_game_mode(confirmed=True)
            ssh.assert_not_called()
        with patch.object(backup, 'session_status', return_value={'mode': 'desktop', 'selector': 'steamos-session-select'}), \
                patch.object(backup, '_ssh') as ssh:
            self.assertTrue(backup.return_to_game_mode(confirmed=True)['switched'])
            ssh.assert_called_once_with('steamos-session-select gamescope', timeout=60)
            ssh.side_effect = backup.BackupError('the headset took too long to answer')  # the session restarted
            self.assertTrue(backup.return_to_game_mode(confirmed=True)['switched'])
            ssh.side_effect = backup.BackupError('Interactive authentication required')
            with self.assertRaisesRegex(backup.BackupError, 'manual steps'):
                backup.return_to_game_mode(confirmed=True)
        with patch.object(backup, 'session_status', return_value={'mode': 'desktop', 'selector': None}), \
                patch.object(backup, '_ssh') as ssh:
            with self.assertRaises(backup.BackupError):
                backup.return_to_game_mode(confirmed=True)
            ssh.assert_not_called()


class Endpoint(unittest.TestCase):
    def test_guards_run_before_the_headset(self):
        with patch.object(backup, '_ssh') as ssh, patch.object(server, 'start_job') as job:
            for body in ({'action': 'plan', 'name': '../x'}, {'action': 'open', 'name': '..'},
                         {'action': 'restore', 'name': '2026-10-23-120000', 'parts': ['saves:1234']},
                         {'action': 'restore', 'name': '2026-10-23-120000', 'parts': ['saves:x'], 'confirm': True},
                         {'action': 'gamemode'}, {'action': 'backup', 'kinds': ['ssh-keys']}, {'action': 'nope'}):
                with self.assertRaises(server.Failure, msg=body) as caught:
                    server.backup_action(body)
                self.assertEqual(caught.exception.status, 400)
            ssh.assert_not_called()
            job.assert_not_called()
            with patch.object(server, 'LOCAL', True):
                with self.assertRaises(server.Failure):
                    server.backup_action({'action': 'list'})


if __name__ == '__main__':
    unittest.main()
