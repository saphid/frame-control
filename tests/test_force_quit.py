"""Force quit (ui/frame_running.py and /api/running) without a headset: running-game
detection, which processes may be signalled, SIGTERM-then-SIGKILL, and the Android path.

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ui"))

import frame_running  # noqa: E402
import test_server  # noqa: E402  (not `from … import`, or unittest runs ServerGuards twice)

ME, OTHER = 1000, 0
HOME = frame_running.HOME
REAPER = f"{HOME}/.local/share/Steam/ubuntu12_32/reaper"


def proc(ppid, comm, argv=None, uid=ME, start=None, state="S"):
    return {"ppid": ppid, "comm": comm, "argv": argv if argv is not None else [comm], "uid": uid,
            "start": start or 1000 + ppid, "state": state}


def frame():
    """A Frame's processes, as Steam on Linux launches games: Steam's reaper with
    AppId= is the parent of the game (Portal 2 here, appid 620)."""
    return {
        1: proc(0, "systemd", uid=OTHER),
        200: proc(1, "sshd", uid=OTHER),
        201: proc(200, "sshd-session"),
        202: proc(201, "bash"),
        203: proc(202, "python3", ["python3", "-", "quit", "620"]),        # this helper
        300: proc(1, "systemd", ["/usr/lib/systemd/systemd", "--user"]),
        301: proc(300, "gamescope-session"),
        302: proc(301, "gamescope"),
        303: proc(302, "steam", [f"{HOME}/.local/share/Steam/ubuntu12_32/steam", "-cef-enable-debugging"]),
        304: proc(303, "steamwebhelper"),
        305: proc(300, "vrserver"),
        306: proc(300, "plasmashell"),
        307: proc(300, "pipewire"),
        400: proc(303, "reaper", [REAPER, "SteamLaunch", "AppId=620", "--", "steam-launch-wrapper", "--", "portal2.sh"]),
        401: proc(400, "steam-launch-wr", ["steam-launch-wrapper", "--", "portal2.sh"]),
        402: proc(401, "portal2.sh", ["/bin/sh", "portal2.sh"]),
        403: proc(402, "portal2_linux", ["./portal2_linux", "-game", "portal2"]),
        404: proc(403, "steam", ["steam"]),                                 # a child named like Steam: left alone
        405: proc(404, "crashhandler"),                                     # and so is anything under it
        # Another game, and processes that only look like launches.
        500: proc(303, "reaper", [REAPER, "SteamLaunch", "AppId=999", "--", "other"]),
        501: proc(500, "other"),
        600: proc(1, "reaper", [REAPER, "SteamLaunch", "AppId=620", "--", "x"], uid=OTHER),
        601: proc(300, "bash", ["bash", "-c", "echo reaper SteamLaunch AppId=620"]),
        602: proc(300, "fakereaper", ["/tmp/notreaper", "SteamLaunch", "AppId=620"]),
    }


class Parsing(unittest.TestCase):
    def test_launch_appid(self):
        cases = [
            ([REAPER, "SteamLaunch", "AppId=620", "--", "game"], 620),
            (["reaper", "SteamLaunch", "AppId=3346865537", "--", "lepton-app.sh"], 3346865537),
            ([REAPER, "AppId=620", "--", "game"], None),                       # no SteamLaunch
            ([REAPER, "SteamLaunch", "--", "game", "AppId=620"], None),         # the game's own arguments
            (["/usr/bin/steam", "SteamLaunch", "AppId=620"], None),             # not the reaper
            (["/tmp/reaper-ish", "SteamLaunch", "AppId=620"], None),
            ([REAPER, "SteamLaunch", "AppId=62x0"], None),
            ([REAPER, "SteamLaunch", "AppId=12345678901"], None),               # more than 10 digits
            ([], None),
        ]
        for argv, want in cases:
            with self.subTest(argv=argv):
                self.assertEqual(frame_running.launch_appid(argv), want)

    def test_reapers_are_this_users_live_launches(self):
        procs = frame()
        procs[700] = proc(303, "reaper", [REAPER, "SteamLaunch", "AppId=777"], state="Z")
        self.assertEqual(frame_running.reapers(procs, ME), {620: [400], 999: [500]})

    def test_steamvr_is_never_a_game(self):
        procs = frame()
        procs[710] = proc(303, "reaper", [REAPER, "SteamLaunch", "AppId=250820", "--", "vrstartup"])
        procs[711] = proc(710, "vrcompositor-launcher")
        self.assertNotIn(250820, frame_running.reapers(procs, ME))
        found = frame_running.running(procs, ME, steam=lambda ids: ([250820], {}),
                                      android=dict, containers=set)
        self.assertNotIn(250820, [a["appid"] for a in found])

    def test_gameid(self):
        self.assertEqual(frame_running.gameid(620), "620")
        # A non-Steam shortcut: (appid << 32) | 0x02000000, as steam_shortcuts.py stop sends.
        self.assertEqual(frame_running.gameid(3346865537), str((3346865537 << 32) | 0x02000000))

    def test_snapshot_reads_proc(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(f"{tmp}/42")
            os.makedirs(f"{tmp}/self")
            fields = " ".join(["S", "7"] + ["0"] * 17 + ["123456"])
            Path(f"{tmp}/42/stat").write_text(f"42 (my (game) x) {fields} 0 0\n")
            Path(f"{tmp}/42/cmdline").write_bytes(b"reaper\0SteamLaunch\0AppId=5\0--\0g\0")
            os.makedirs(f"{tmp}/43")                       # vanished between listdir and read
            got = frame_running.snapshot(tmp)
        self.assertEqual(list(got), [42])
        self.assertEqual(got[42]["comm"], "my (game) x")
        self.assertEqual((got[42]["ppid"], got[42]["start"], got[42]["state"]), (7, 123456, "S"))
        self.assertEqual(got[42]["argv"], ["reaper", "SteamLaunch", "AppId=5", "--", "g"])


class Detection(unittest.TestCase):
    def run_list(self, procs, steam=(None, {}), android=None, containers=()):
        return frame_running.running(procs, ME, steam=lambda ids: steam, android=lambda: android or {},
                                     containers=lambda: set(containers))

    def test_steam_game_named_by_steam(self):
        got = self.run_list(frame(), steam=([620], {620: "Portal 2", 999: "Other"}))
        self.assertEqual([(a["appid"], a["kind"], a["name"]) for a in got],
                         [(620, "steam", "Portal 2"), (999, "steam", "Other")])
        self.assertEqual(got[0]["gameid"], "620")
        self.assertEqual(got[0]["processes"], 6)

    def test_without_steam_the_manifest_names_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(f"{tmp}/steamapps")
            Path(f"{tmp}/steamapps/appmanifest_620.acf").write_text('"AppState"\n{\n\t"appid"\t"620"\n\t"name"\t"Portal 2"\n}')
            with mock.patch.object(frame_running, "STEAM", tmp):
                got = self.run_list(frame())
        self.assertEqual([(a["appid"], a["name"]) for a in got], [(620, "Portal 2"), (999, "App 999")])

    def test_nothing_running(self):
        procs = {pid: p for pid, p in frame().items() if pid < 400}
        self.assertEqual(self.run_list(procs), [])

    def test_steam_only_listing_counts(self):
        # Steam says it's running but no reaper was found: listed, with no processes.
        got = self.run_list({1: proc(0, "systemd", uid=OTHER)}, steam=([620], {620: "Portal 2"}))
        self.assertEqual(got, [{"appid": 620, "gameid": "620", "processes": 0, "kind": "steam", "name": "Portal 2"}])

    def test_devkit_title_and_shortcut(self):
        sid, other = 0x80001234, 0x80005678
        procs = {1: proc(0, "systemd", uid=OTHER),
                 10: proc(1, "reaper", [REAPER, "SteamLaunch", f"AppId={sid}", "--", f'"{HOME}/devkit-game/Cool_Game/run.sh"']),
                 11: proc(10, "run.sh", ["/bin/sh", f"{HOME}/devkit-game/Cool_Game/run.sh"]),
                 20: proc(1, "reaper", [REAPER, "SteamLaunch", f"AppId={other}", "--", "/usr/bin/flatpak", "run", "x"])}
        got = self.run_list(procs)
        self.assertEqual([(a["kind"], a.get("title"), a["name"]) for a in got],
                         [("devkit", "Cool_Game", "Cool_Game"), ("shortcut", None, f"Shortcut {other}")])
        self.assertEqual(got[0]["gameid"], str((sid << 32) | 0x02000000))

    def test_android_app_from_its_container(self):
        meta = {"package": "org.example.game", "label": "Example", "shortcut": 3346865537, "instance": 2812345678}
        apps = {3346865537: meta, 2812345678: meta}
        got = self.run_list({1: proc(0, "systemd", uid=OTHER)}, android=apps,
                            containers={"lepton-steamlaunch-2812345678"})
        self.assertEqual(got, [{"appid": 3346865537, "gameid": str((3346865537 << 32) | 0x02000000), "processes": 0,
                                "kind": "android", "package": "org.example.game", "name": "Example"}])
        # Its container stopped: not running.
        self.assertEqual(self.run_list({1: proc(0, "systemd", uid=OTHER)}, android=apps, containers=()), [])

    def test_android_meta_reads_shortcut_and_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(f"{tmp}/org.example.game")
            Path(f"{tmp}/org.example.game/meta.json").write_text(json.dumps(
                {"package": "org.example.game", "shortcut": 3346865537, "instance": 2812345678}))
            os.makedirs(f"{tmp}/broken")
            Path(f"{tmp}/broken/meta.json").write_text("{")
            with mock.patch.object(frame_running, "ANDROID", tmp):
                self.assertEqual(sorted(frame_running.android_apps()), [2812345678, 3346865537])


class World:
    """Processes that react to signals: kill() removes them, unless they ignore it."""

    def __init__(self, procs, ignore=(), unkillable=()):
        self.procs, self.ignore, self.unkillable = dict(procs), set(ignore), set(unkillable)
        self.sent, self.now = [], 0.0

    def scan(self):
        return dict(self.procs)

    def kill(self, pid, sig):
        if pid not in self.procs:
            raise ProcessLookupError
        self.sent.append((pid, sig))
        if pid in self.unkillable or (sig == frame_running.SIGTERM and pid in self.ignore):
            return
        self.procs.pop(pid)
        # A reaper exits once its last child has.
        for rid, p in list(self.procs.items()):
            if p["comm"] == "reaper" and not any(c["ppid"] == rid for c in self.procs.values()):
                self.procs.pop(rid)

    def sleep(self, seconds):
        self.now += seconds

    def escalate(self, appid=620):
        return frame_running.escalate(appid, me=203, uid=ME, scan=self.scan, kill=self.kill,
                                      sleep=self.sleep, clock=lambda: self.now)


class Escalation(unittest.TestCase):
    GAME = {401, 402, 403}

    def assert_only_game(self, world, allowed=GAME | {400}):
        signalled = {pid for pid, _ in world.sent}
        self.assertTrue(signalled, "nothing was signalled")
        self.assertLessEqual(signalled, allowed)
        protected = frame_running.protected(frame(), 203, ME)
        for pid in (1, 200, 201, 202, 203, 300, 301, 302, 303, 304, 305, 306, 307, 404, 405, 500, 501, 600, 601, 602):
            self.assertNotIn(pid, signalled)
        self.assertTrue({1, 201, 202, 203, 302, 303, 304, 305, 306, 307, 404, 600}.issubset(protected))

    def test_sigterm_ends_it(self):
        world = World(frame())
        self.assertEqual(world.escalate(), "term")
        self.assert_only_game(world)
        self.assertEqual({pid for pid, sig in world.sent}, self.GAME)
        self.assertTrue(all(sig == frame_running.SIGTERM for _, sig in world.sent))
        # Deepest first, and the reaper isn't signalled while its children are alive.
        self.assertEqual([pid for pid, _ in world.sent], [403, 402, 401])
        self.assertNotIn(400, world.procs)
        self.assertIn(404, world.procs)         # the "steam" child under the game is never touched

    def test_sigkill_after_a_grace_period(self):
        world = World(frame(), ignore={403})
        self.assertEqual(world.escalate(), "kill")
        self.assert_only_game(world)
        self.assertIn((403, frame_running.SIGTERM), world.sent)
        self.assertIn((403, frame_running.SIGKILL), world.sent)
        self.assertGreaterEqual(world.now, frame_running.TERM_WAIT)
        kills = [pid for pid, sig in world.sent if sig == frame_running.SIGKILL]
        self.assertEqual(kills[0], 403)

    def test_survivor_is_an_error(self):
        world = World(frame(), unkillable={403})
        with self.assertRaisesRegex(frame_running.Fail, "still running after SIGKILL"):
            world.escalate()
        self.assert_only_game(world)

    def test_reused_pid_is_not_signalled(self):
        world = World(frame(), ignore={402, 403})
        real_scan = world.scan

        def scan():
            procs = real_scan()
            if world.sent and 402 in procs:     # 402 exits and its pid goes to an unrelated program
                procs[402] = proc(300, "editor", start=99999)
                world.procs[402] = procs[402]
            return procs
        world.scan = scan
        world.escalate()
        self.assertNotIn((402, frame_running.SIGKILL), world.sent)

    def test_nothing_left(self):
        world = World({pid: p for pid, p in frame().items() if pid < 400})
        self.assertEqual(world.escalate(), "gone")
        self.assertEqual(world.sent, [])

    def test_lingering_reaper_alone(self):
        procs = {pid: p for pid, p in frame().items() if pid not in self.GAME and pid not in (404, 405)}
        world = World(procs)
        self.assertEqual(world.escalate(), "term")
        self.assertEqual(world.sent, [(400, frame_running.SIGTERM)])

    def test_protected_never_signalled_even_as_the_root(self):
        # A reaper whose only children are protected: nothing to signal but the reaper itself.
        procs = frame()
        procs[402]["comm"] = "gamescope"
        world = World(procs)
        world.escalate()
        self.assertNotIn(402, {pid for pid, _ in world.sent})
        self.assertNotIn(403, {pid for pid, _ in world.sent})


class Quit(unittest.TestCase):
    def setUp(self):
        self.page = mock.MagicMock()
        patches = [mock.patch.object(frame_running, "Page", return_value=self.page),
                   mock.patch.object(frame_running, "running", return_value=[
                       {"appid": 620, "gameid": "620", "name": "Portal 2", "kind": "steam", "processes": 4}]),
                   mock.patch.object(frame_running.os, "getuid", return_value=ME, create=True)]  # none on Windows
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_steam_terminate_first(self):
        scans = iter([frame(), {}])
        self.page.eval.return_value = {"running": [], "names": {}}
        with mock.patch.object(frame_running, "snapshot", side_effect=lambda: next(scans)), \
             mock.patch.object(frame_running, "escalate") as escalate:
            out = frame_running.quit_game(620, sleep=lambda s: None)
        self.assertEqual(out["method"], "steam")
        self.page.eval.assert_any_call('SteamClient.Apps.TerminateApp("620", false)')
        escalate.assert_not_called()

    def test_signals_when_steam_leaves_it_running(self):
        now = [0.0]
        with mock.patch.object(frame_running, "snapshot", return_value=frame()), \
             mock.patch.object(frame_running, "escalate", return_value="kill") as escalate:
            out = frame_running.quit_game(620, sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])
        escalate.assert_called_once_with(620)
        self.assertGreaterEqual(now[0], frame_running.STEAM_WAIT)
        self.assertEqual(out["message"], "Force quit Portal 2 (it had to be killed)")

    def test_without_steam_goes_straight_to_signals(self):
        frame_running.Page.side_effect = frame_running.Fail("no SharedJSContext page")
        with mock.patch.object(frame_running, "snapshot", return_value=frame()), \
             mock.patch.object(frame_running, "escalate", return_value="term") as escalate:
            out = frame_running.quit_game(620, sleep=self.fail)
        escalate.assert_called_once_with(620)
        self.assertEqual(out["method"], "term")

    def test_not_running(self):
        frame_running.running.return_value = []
        with mock.patch.object(frame_running, "escalate") as escalate:
            self.assertEqual(frame_running.quit_game(620)["method"], "gone")
        escalate.assert_not_called()
        self.page.eval.assert_not_called()


class Script(unittest.TestCase):
    def test_server_sends_it_with_frame_steam_inside(self):
        import server
        with mock.patch.object(server, "ssh", return_value='{"running": []}') as ssh:
            self.assertEqual(server.running_games(), {"running": [], "message": "Nothing is running on the Frame"})
        source = ssh.call_args.kwargs["stdin"]
        self.assertEqual(ssh.call_args.args[0], "python3 - list")
        # The same script runs as `python3 -`: frame_steam resolves, and bad usage is one JSON error.
        r = subprocess.run([sys.executable, "-I", "-", "bogus"], input=source, capture_output=True, text=True,
                           cwd=tempfile.gettempdir(), timeout=30)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"error": "usage: list | quit APPID"})


class Server(unittest.TestCase):
    def setUp(self):
        import server
        self.server = server

    def quit(self, listed, quit_result=None, stop_error=None):
        calls = []

        def frame(*args, timeout=40):
            calls.append(args)
            return {"running": listed} if args == ("list",) else quit_result
        with mock.patch.object(self.server, "running_frame", side_effect=frame), \
             mock.patch.object(self.server, "ensure_master"), \
             mock.patch.object(self.server.frame_android, "stop", side_effect=stop_error) as stop:
            out = self.server.force_quit({"action": "quit", "appid": "3346865537"})
        return out, calls, stop

    def test_android_app_stops_its_container_first(self):
        app = {"appid": 3346865537, "kind": "android", "package": "org.example.game", "name": "Example"}
        out, calls, stop = self.quit([app], {"name": "Example", "method": "gone", "message": "That game isn't running"})
        stop.assert_called_once_with("org.example.game")
        self.assertEqual(calls, [("list",), ("quit", "3346865537")])
        self.assertEqual(out["message"], "Stopped Example")

    def test_android_stop_failure_falls_back_to_processes(self):
        app = {"appid": 3346865537, "kind": "android", "package": "org.example.game", "name": "Example"}
        err = self.server.frame_android.FrameError("podman failed")
        out, calls, _ = self.quit([app], {"name": "Example", "method": "term", "message": "Force quit Example"}, err)
        self.assertEqual(calls[-1], ("quit", "3346865537"))
        self.assertEqual(out["message"], "Force quit Example")

    def test_other_games_skip_the_android_path(self):
        app = {"appid": 3346865537, "kind": "devkit", "title": "Cool_Game", "name": "Cool_Game"}
        out, _, stop = self.quit([app], {"name": "Cool_Game", "method": "steam", "message": "Quit Cool_Game"})
        stop.assert_not_called()
        self.assertEqual(out["message"], "Quit Cool_Game")

    def test_not_running_is_a_conflict(self):
        with self.assertRaises(self.server.Failure) as cm:
            self.quit([])
        self.assertEqual(cm.exception.status, 409)


class Routes(test_server.ServerGuards):
    """Validation runs before any SSH."""

    def test_input_validation(self):
        for body in ({"action": "quit", "appid": "620; reboot"}, {"action": "quit", "appid": ""},
                     {"action": "kill", "appid": "620"}, {"appid": "620"}, {"action": "quit", "appid": "12345678901"}):
            status, payload = self.post("/api/running", body)
            self.assertEqual(status, 400, f"{body} -> {payload}")

    def test_routes_need_custom_header(self):
        self.assertEqual(self.request("GET", "/api/running")[0], 403)
        self.assertEqual(self.request("POST", "/api/running", {"action": "quit", "appid": "620"})[0], 403)


if __name__ == "__main__":
    unittest.main()
