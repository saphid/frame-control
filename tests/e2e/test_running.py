"""Force quit (ui/frame_running.py) through the server's HTTP API, against games the
fake Steam client really runs under its stand-in reaper (fakesteam.REAPER)."""
import os
import unittest

import harness
from harness import api, install_title, launches, ok, ssh, state, wait_for

harness.require()


class Running(harness.FrameTestCase):
    def script_title(self, name, body):
        folder = self.path(name)
        os.makedirs(folder)
        with open(os.path.join(folder, 'run.sh'), 'w') as f:
            f.write('#!/bin/sh\n' + body)
        os.chmod(os.path.join(folder, 'run.sh'), 0o755)
        plan, job = install_title(folder)
        self.assertIsNone(job['error'], job)
        return plan['id'], plan['name']

    def running(self, match):
        return next((g for g in ok('GET', '/api/running')['running'] if match(g)), None)

    def launch_title(self, gid):
        ok('POST', '/api/titles', {'action': 'launch', 'id': gid})
        game = wait_for(lambda: self.running(lambda g: g.get('title') == gid), 20, f'{gid} to be running')
        # The fake's reset doesn't stop programs: don't leave one running for the next test.
        self.addCleanup(ssh, f"pkill -KILL -f '[d]evkit-game/{gid}/' || true", check=False)
        return game

    def assert_steam_alive(self, pid):
        self.assertEqual(ssh(f'kill -0 {pid} && echo alive').strip(), 'alive')

    def test_nothing_running(self):
        self.assertEqual(ok('GET', '/api/running'), {'running': [], 'message': 'Nothing is running on the Frame'})
        status, out, _ = api('POST', '/api/running', {'action': 'quit', 'appid': '620'})
        self.assertEqual(status, 409, out)

    def test_sigterm_quits_a_sideloaded_game(self):
        gid, name = self.script_title('Hang Game', 'sleep 600 &\nwait\n')
        steam = ssh('cat ~/.steam/steam.pid').strip()
        game = self.launch_title(gid)
        self.assertEqual((game['kind'], game['name']), ('devkit', name))
        self.assertGreaterEqual(game['processes'], 3)          # reaper, run.sh, sleep
        out = ok('POST', '/api/running', {'action': 'quit', 'appid': str(game['appid'])})
        self.assertEqual(out['method'], 'term', out)
        self.assertEqual(out['message'], f'Force quit {name}')
        # Steam was asked first, with the shortcut's game id.
        self.assertEqual(state()['steam']['last_terminate'], game['gameid'])
        self.assertIsNone(self.running(lambda g: g['appid'] == game['appid']))
        self.assertEqual(ssh("pgrep -fc '[s]leep 600' || true").strip(), '0')
        self.assert_steam_alive(steam)
        done = wait_for(lambda: launches('devkit')[-1].get('exit') is not None and launches('devkit')[-1],
                        10, 'the reaper to report the exit')
        self.assertIsNotNone(done['exit'])

    def test_sigkill_when_it_ignores_sigterm(self):
        gid, name = self.script_title('Stuck Game', "trap '' TERM\nsleep 600 &\nwait\n")
        steam = ssh('cat ~/.steam/steam.pid').strip()
        game = self.launch_title(gid)
        out = ok('POST', '/api/running', {'action': 'quit', 'appid': str(game['appid'])})
        self.assertEqual(out['method'], 'kill', out)
        self.assertEqual(out['message'], f'Force quit {name} (it had to be killed)')
        self.assertIsNone(self.running(lambda g: g['appid'] == game['appid']))
        self.assertEqual(ssh("pgrep -fc '[s]leep 600' || true").strip(), '0')
        self.assert_steam_alive(steam)

    def test_steam_game_quits_through_steam(self):
        ok('POST', '/api/launch', {'appid': 620980})
        game = wait_for(lambda: self.running(lambda g: g['appid'] == 620980), 20, 'the Steam game to be running')
        self.assertEqual((game['kind'], game['gameid']), ('steam', '620980'))
        out = ok('POST', '/api/running', {'action': 'quit', 'appid': '620980'})
        self.assertEqual(out['method'], 'steam', out)
        self.assertEqual(state()['steam']['last_terminate'], '620980')
        self.assertEqual(launches('rungameid')[-1]['exit'], 'terminated')
        self.assertEqual(ok('GET', '/api/running')['running'], [])


if __name__ == '__main__':
    unittest.main()
