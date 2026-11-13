#!/usr/bin/env python3
"""Runs ON the Frame (piped over SSH, with frame_steam.py): what game is running,
and force quit it.

Steam starts every game, non-Steam shortcut and devkit title under its own
`reaper`, as `reaper SteamLaunch AppId=<id> -- <command>`, and the reaper stays
the parent of the game's processes. That's how Steam starts games on Linux
desktops and the Steam Deck; on the Frame it is **inferred, not yet seen**. So a
running game is a reaper with an AppId, and the game is that reaper's process
tree. Nothing is matched by name, so Steam, gamescope, SteamVR, sshd or the
session can't be picked by mistake, and the names in PROTECTED are skipped
even inside a game's tree.

Quitting asks Steam first (SteamClient.Apps.TerminateApp, what Steam's own Stop
uses for Android apps, docs/vr-apks.md). If the game's processes are still
there a few seconds later, they get SIGTERM, then SIGKILL.

Usage: python3 - list          # {"running": [{appid, gameid, name, kind, ...}]}
       python3 - quit APPID    # {"name", "method": "steam"|"term"|"kill"|"gone", "message"}
Prints one JSON object. Errors are {"error": "..."} with exit status 1.
"""
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time

from frame_steam import Fail, Page

# The Frame is Linux; "/" also keeps the unit tests' paths the same on Windows.
HOME = os.path.expanduser("~")
STEAM = HOME + "/.local/share/Steam"
DEVKIT = HOME + "/devkit-game"
ANDROID = HOME + "/Applications/Android"               # frame_android.APPS_DIR
SIGTERM, SIGKILL = signal.SIGTERM, getattr(signal, "SIGKILL", 9)  # Windows (unit tests) has no SIGKILL
SHORTCUT_BIT = 0x80000000                               # non-Steam shortcut ids have the top bit set
APPID_ARG = re.compile(r"AppId=(\d{1,10})")
# Never signalled, even when found under a game's reaper: Steam, the
# compositors, SteamVR, the session, audio, sshd and init.
PROTECTED = frozenset({
    "steam", "steamwebhelper", "gamescope", "gamescope-wl", "gamescopereaper", "gamescope-session",
    "sshd", "sshd-session", "ssh-agent", "systemd", "init", "dbus-daemon", "dbus-broker", "dbus-broker-lau",
    "pipewire", "pipewire-pulse", "wireplumber", "plasmashell", "kwin_wayland", "kwin_x11", "Xwayland",
    "sddm", "vrserver", "vrcompositor", "vrmonitor", "vrdashboard", "vrwebhelper", "vrstartup",
})
# Steam launches SteamVR under a reaper too, but on the Frame it's the headset's view,
# not a game: it's never listed or quit (SteamVR and SteamVR Beta).
NOT_GAMES = frozenset({250820, 1009850})
STEAM_WAIT = 5      # seconds for Steam's own terminate to end the game
TERM_WAIT = 3       # then SIGTERM, and this long before SIGKILL
KILL_WAIT = 2

RUNNING_JS = """((ids) => {
  const store = globalThis.SteamUIStore;
  const running = Array.isArray(store?.RunningApps) ? store.RunningApps.map(a => a.appid) : null;
  const names = {};
  for (const id of new Set([...ids, ...(running || [])])) {
    const a = appStore.GetAppOverviewByAppID(id);
    if (a) names[id] = a.display_name;
  }
  return {running, names};
})(%s)"""


def read(path, mode="r"):
    try:
        with open(path, mode) as f:
            return f.read()
    except OSError:
        return None


def snapshot(proc="/proc"):
    """pid -> {ppid, start, state, uid, comm, argv} for every process that can be read."""
    out = {}
    for d in os.listdir(proc):
        if not d.isdigit():
            continue
        stat = read(f"{proc}/{d}/stat")
        try:
            # comm is in parentheses and may hold spaces or ')': split at the last ')'.
            comm = stat[stat.index("(") + 1:stat.rindex(")")]
            fields = stat[stat.rindex(")") + 2:].split()
            uid = os.stat(f"{proc}/{d}").st_uid
        except (AttributeError, ValueError, OSError):
            continue
        argv = (read(f"{proc}/{d}/cmdline", "rb") or b"").split(b"\0")
        out[int(d)] = {"ppid": int(fields[1]), "state": fields[0], "start": int(fields[19]), "uid": uid,
                       "comm": comm, "argv": [a.decode(errors="replace") for a in argv if a]}
    return out


def launch_appid(argv):
    """The AppId of `reaper SteamLaunch AppId=<id> -- ...`, or None for any other process."""
    if not argv or os.path.basename(argv[0]) != "reaper" or "SteamLaunch" not in argv:
        return None
    for arg in argv[1:]:
        if arg == "--":
            break
        m = APPID_ARG.fullmatch(arg)
        if m:
            return int(m.group(1))
    return None


def reapers(procs, uid):
    """appid -> [reaper pid], for this user's game launches."""
    out = {}
    for pid, p in procs.items():
        appid = launch_appid(p["argv"])
        if appid and appid not in NOT_GAMES and p["uid"] == uid and p["state"] != "Z":
            out.setdefault(appid, []).append(pid)
    return out


def children(procs):
    kids = {}
    for pid, p in procs.items():
        kids.setdefault(p["ppid"], []).append(pid)
    return kids


def protected(procs, me, uid):
    """Pids never to signal: init, this helper and its parents (the SSH session),
    other users' processes and anything named in PROTECTED."""
    keep, pid = {0, 1}, me
    while pid > 1 and pid not in keep:
        keep.add(pid)
        pid = procs.get(pid, {}).get("ppid", 0)
    for pid, p in procs.items():
        argv0 = os.path.basename(p["argv"][0]) if p["argv"] else ""
        if p["uid"] != uid or p["comm"] in PROTECTED or argv0 in PROTECTED:
            keep.add(pid)
    return keep


def tree(procs, roots, keep):
    """The roots and their descendants, deepest first, leaving out kept processes
    and everything under them."""
    kids, out, level = children(procs), [], [r for r in roots if r not in keep]
    while level:
        out = level + out
        level = [c for pid in level for c in kids.get(pid, ()) if c not in keep and procs[c]["state"] != "Z"]
    return out


def alive(procs, pid, start):
    p = procs.get(pid)
    return bool(p) and p["start"] == start and p["state"] != "Z"


def escalate(appid, me=None, uid=None, scan=snapshot, kill=os.kill, sleep=time.sleep, clock=time.monotonic):
    """SIGTERM the game's processes, then SIGKILL what's left. The reaper itself
    is only killed last, so its orphans can't escape to init before they're
    signalled. Returns "term", "kill" or "gone"; raises Fail if any survive."""
    me = os.getpid() if me is None else me
    uid = os.getuid() if uid is None else uid
    seen = {}          # pid -> start time, so a reused pid is never signalled

    def targets(include_roots):
        procs = scan()
        keep = protected(procs, me, uid)
        roots = reapers(procs, uid).get(appid, [])
        for pid in tree(procs, roots, keep):
            seen.setdefault(pid, procs[pid]["start"])
        return procs, [pid for pid, start in seen.items() if alive(procs, pid, start) and pid not in keep
                       and (include_roots or pid not in roots)]

    def wait(seconds, include_roots):
        end = clock() + seconds
        while True:
            procs, left = targets(include_roots)
            if not left or clock() >= end:
                return left
            sleep(0.2)

    method = "gone"
    for sig, seconds, include_roots in ((SIGTERM, TERM_WAIT, False), (SIGKILL, KILL_WAIT, True)):
        _, left = targets(include_roots)
        if not left:
            # The reaper exits when its last child does; a lingering one is all that's left.
            _, left = targets(True)
            if not left:
                return method
        for pid in left:
            try:
                kill(pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                continue
        method = "term" if sig == SIGTERM else "kill"
        if not wait(seconds, True):
            return method
    raise Fail(f"{len(targets(True)[1])} of its processes are still running after SIGKILL")


def gameid(appid):
    """The game id Steam's Apps API takes: the appid, or (appid << 32) | 0x02000000
    for a non-Steam shortcut (docs/apks.md)."""
    return str((appid << 32) | 0x02000000 if appid >= SHORTCUT_BIT else appid)


def android_apps():
    """Shortcut or instance id -> Frame Control's Android app meta."""
    out = {}
    for path in glob.glob(os.path.join(ANDROID, "*/meta.json")):
        try:
            m = json.loads(read(path) or "null")
        except ValueError:
            continue
        if isinstance(m, dict) and m.get("package"):
            for key in ("shortcut", "instance"):
                if str(m.get(key) or "").isdigit():
                    out[int(m[key])] = m
    return out


def lepton_containers():
    try:
        r = subprocess.run(["podman", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return set(r.stdout.split())


def manifest_name(appid):
    m = re.search(r'"name"\s+"([^"]*)"', read(os.path.join(STEAM, f"steamapps/appmanifest_{appid}.acf")) or "")
    return m.group(1) if m else None


def devkit_title(procs, pids):
    """A devkit title's id from its processes' arguments (~/devkit-game/<id>/...)."""
    prefix = DEVKIT + "/"
    for pid in pids:
        for arg in procs[pid]["argv"]:
            arg = arg.strip('"')
            if arg.startswith(prefix) and "/" in arg[len(prefix):]:
                return arg[len(prefix):].split("/", 1)[0]
    return None


def steam_view(ids, page=None):
    """Steam's own running list and app names, or (None, {}) without Steam."""
    try:
        r = (page or Page()).eval(RUNNING_JS % json.dumps(sorted(ids)))
    except (Fail, OSError):
        return None, {}
    return r.get("running"), {int(k): v for k, v in (r.get("names") or {}).items()}


def running(procs=None, uid=None, steam=steam_view, android=android_apps, containers=lepton_containers):
    """Every game running now: reapers on this Frame, Steam's running list, and
    Android apps whose Lepton container is up."""
    procs = snapshot() if procs is None else procs
    uid = os.getuid() if uid is None else uid
    found = reapers(procs, uid)
    apps = android()
    up = containers() if apps else set()
    for m in apps.values():
        if f"lepton-steamlaunch-{m.get('instance')}" in up and str(m.get("shortcut") or "").isdigit():
            found.setdefault(int(m["shortcut"]), [])
    listed, names = steam(set(found))
    for appid in listed or ():
        if int(appid) not in NOT_GAMES:
            found.setdefault(int(appid), [])
    out = []
    for appid, roots in sorted(found.items()):
        pids = tree(procs, roots, set())
        app = {"appid": appid, "gameid": gameid(appid), "processes": len(pids)}
        meta = apps.get(appid)
        title = devkit_title(procs, pids)
        if meta:
            app.update(kind="android", package=meta["package"], name=names.get(appid) or meta.get("label") or meta["package"])
        elif title:
            app.update(kind="devkit", title=title, name=names.get(appid) or title)
        elif appid >= SHORTCUT_BIT:
            app.update(kind="shortcut", name=names.get(appid) or f"Shortcut {appid}")
        else:
            app.update(kind="steam", name=names.get(appid) or manifest_name(appid) or f"App {appid}")
        out.append(app)
    return out


def quit_game(appid, sleep=time.sleep, clock=time.monotonic):
    apps = {a["appid"]: a for a in running()}
    app = apps.get(appid)
    if not app:
        return {"name": None, "method": "gone", "message": "That game isn't running"}
    name = app["name"]
    try:
        page = Page()
        page.eval(f"SteamClient.Apps.TerminateApp({json.dumps(app['gameid'])}, false)")
    except (Fail, OSError):
        page = None     # Steam isn't answering: the processes are all that's left to stop
    end = clock() + (STEAM_WAIT if page else 0)
    while True:
        procs = snapshot()
        left = reapers(procs, os.getuid()).get(appid) or (page and appid in (steam_view({appid}, page)[0] or ()))
        if not left:
            return {"name": name, "method": "steam" if page else "gone", "message": f"Quit {name}"}
        if clock() >= end:
            break
        sleep(0.5)
    if not reapers(procs, os.getuid()).get(appid):
        # Steam still lists it, but there's no process of it to stop.
        raise Fail(f"Steam didn't quit {name}, and none of its processes were found on the Frame")
    method = escalate(appid)
    return {"name": name, "method": method,
            "message": f"Force quit {name}" + (" (it had to be killed)" if method == "kill" else "")}


def main():
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else ""
        if cmd == "list":
            out = {"running": running()}
        elif cmd == "quit" and len(sys.argv) == 3 and sys.argv[2].isdigit() and len(sys.argv[2]) <= 10:
            out = quit_game(int(sys.argv[2]))
        else:
            raise Fail("usage: list | quit APPID")
    except (Fail, OSError) as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    except Exception as e:  # keep the one-JSON-object contract for the server
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
