"""Backup and recovery kit through the server against the fake Frame: a Proton game's save
goes to this computer and back, Steam's sign-in token never leaves the headset."""
import json
import shutil
import tarfile
import unittest
from pathlib import Path

import harness
from harness import api, finished, ok, ssh

harness.require()

SAVE = '.local/share/Steam/steamapps/compatdata/620980/pfx/drive_c/users/steamuser/AppData/LocalLow/Beat Games/Beat Saber/PlayerData.dat'


class Backup(harness.FrameTestCase):
    def test_saves_round_trip_and_secrets_stay(self):
        ssh(f"mkdir -p ~/'{Path(SAVE).parent}' && printf 'level 7' > ~/'{SAVE}' && "
            "mkdir -p ~/.steam && printf SECRET > ~/.steam/steam.token")
        job = finished(ok('POST', '/api/backup', {'action': 'backup', 'kinds': ['saves', 'settings']}), 120)
        self.assertIsNone(job['error'], job)
        folder = Path(job['result']['path'])
        self.addCleanup(shutil.rmtree, str(folder), True)
        manifest = json.loads((folder / 'manifest.json').read_text())
        self.assertEqual(manifest['headset']['build'], '20260922.6101926')
        saves = next(p for p in manifest['parts'] if p['id'] == 'saves:620980')
        self.assertEqual(saves['label'], 'Beat Saber saves')
        self.assertEqual([f['path'] for f in saves['files']], [SAVE])
        for part in manifest['parts']:
            with tarfile.open(str(folder / part['archive'])) as tar:
                self.assertFalse([m.name for m in tar if 'steam.token' in m.name])
        self.assertEqual(ssh('cat ~/.steam/steam.token'), 'SECRET')  # read-only on the headset

        ssh(f"rm ~/'{SAVE}'")
        name = folder.name
        plan = {p['id']: p for p in ok('POST', '/api/backup', {'action': 'plan', 'name': name})['parts']}
        self.assertEqual((plan['saves:620980']['status'], plan['saves:620980']['new']), ('ok', 1))
        status, out, _ = api('POST', '/api/backup', {'action': 'restore', 'name': name, 'parts': ['saves:620980']})
        self.assertEqual(status, 400, out)  # not confirmed
        job = finished(ok('POST', '/api/backup', {'action': 'restore', 'name': name, 'parts': ['saves:620980'],
                                                  'confirm': True}), 120)
        self.assertIsNone(job['error'], job)
        self.assertEqual(ssh(f"cat ~/'{SAVE}'"), 'level 7')

    def test_bad_names_and_session(self):
        status, out, _ = api('POST', '/api/backup', {'action': 'plan', 'name': '../../etc'})
        self.assertEqual(status, 400, out)
        state = ok('POST', '/api/backup', {'action': 'session'})
        self.assertIn(state['mode'], ('game', 'desktop', 'unknown'))
        self.assertIsNone(state['selector'])  # the fake has no session switch command


if __name__ == '__main__':
    unittest.main()
