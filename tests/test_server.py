"""Frame Control server checks that need no headset.

Starts ui/server.py against an SSH alias that can't resolve, then exercises the
request guards and input validation, which all run before any SSH call.

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import http.client
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.ssh_dir = tempfile.mkdtemp(prefix="frame-control-ssh-")  # an empty ~/.ssh: no headsets set up
        env = {**os.environ, "FRAME_ALIAS": "frame-control-test.invalid", "PYTHONDONTWRITEBYTECODE": "1",
               "FRAME_CONTROL_SSH_DIR": cls.ssh_dir}
        cls.log = tempfile.TemporaryFile()
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / "ui" / "server.py"), "--port", str(cls.port)],
                                    env=env, stdout=cls.log, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                if cls.request("GET", "/")[0] == 200:
                    return
            except Exception:
                pass
            time.sleep(0.05)
        cls.proc.kill()
        cls.log.seek(0)
        raise RuntimeError("server didn't start:\n" + cls.log.read().decode(errors="replace"))

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        cls.log.close()

    @classmethod
    def request(cls, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        data = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=data, headers=headers or {})
        r = conn.getresponse()
        payload = r.read()
        conn.close()
        return r.status, dict(r.getheaders()), payload

    def post(self, path, body):
        status, _, payload = self.request("POST", path, body, {"X-Frame-UI": "1", "Content-Type": "application/json"})
        return status, json.loads(payload)

    def test_page_served_with_identifying_and_anti_framing_headers(self):
        status, headers, payload = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Server"].startswith("FrameControl"))
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn(b"<html", payload.lower())

    def test_control_center_assets_served_with_correct_types(self):
        for path, mime, marker in (('/control-center.js', 'text/javascript', b'createController'),
                                   ('/control-center.css', 'text/css', b'.cc-workspace')):
            with self.subTest(path=path):
                status, headers, payload = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertIn(mime, headers['Content-Type'])
                self.assertIn(marker, payload)

    def test_store_page_served_with_anti_framing_headers(self):
        status, headers, payload = self.request("GET", "/store")
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn(b"<title>APK Store</title>", payload)

    def test_local_extension_is_listed_and_sandboxed(self):
        folder = Path(os.environ["FRAME_CONTROL_DATA_DIR"]) / "extensions" / "test-glance"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "manifest.json").write_text(json.dumps({"id": "test-glance", "name": "Test Glance",
            "version": "1.0", "description": "Test status", "entry": "index.html"}))
        (folder / "index.html").write_text('<script src="main.js"></script>')
        (folder / "main.js").write_text('parent.postMessage({type:"frame-control:request",id:1,action:"status"},"*");')
        try:
            code, _, body = self.request("GET", "/api/extensions", headers={"X-Frame-UI": "1"})
            self.assertEqual(code, 200)
            self.assertIn("test-glance", [x["id"] for x in json.loads(body)["extensions"]])
            code, headers, body = self.request("GET", "/extension/test-glance/index.html")
            self.assertEqual(code, 200)
            self.assertIn(b"main.js", body)
            self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])
            self.assertNotIn("X-Frame-Options", headers)
            self.assertEqual(self.request("GET", "/extension/test-glance/manifest.json")[0], 404)
            self.assertEqual(self.request("GET", "/extension/test-glance/../index.html")[0], 404)
            try:
                (folder / "escape.js").symlink_to(Path(__file__))
            except OSError:  # Windows may not allow an unprivileged test to create a symlink.
                pass
            else:
                self.assertEqual(self.request("GET", "/extension/test-glance/escape.js")[0], 404)
        finally:
            shutil.rmtree(folder)

    def test_decky_write_requires_experimental_acknowledgement(self):
        code, body = self.post('/api/decky', {'action': 'install'})
        self.assertEqual(code, 400)
        self.assertIn('experimental', body['error'])

    def test_incompatible_extension_is_reported_and_assets_are_unavailable(self):
        folder = Path(os.environ['FRAME_CONTROL_DATA_DIR']) / 'extensions' / 'future-panel'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'manifest.json').write_text(json.dumps({'id': 'future-panel', 'name': 'Future',
            'version': '1.0', 'description': 'Requires a newer API', 'apiVersion': 2}))
        (folder / 'index.html').write_text('<p>Incompatible panel</p>')
        try:
            self.assertEqual(self.request('GET', '/api/extensions')[0], 403)
            code, _, body = self.request('GET', '/api/extensions', headers={'X-Frame-UI': '1'})
            self.assertEqual(code, 200)
            data = json.loads(body)
            self.assertNotIn('future-panel', [x['id'] for x in data['extensions']])
            self.assertTrue(any(x['folder'] == 'future-panel' and 'apiVersion' in x['error']
                                for x in data['errors']))
            self.assertEqual(self.request('GET', '/extension/future-panel/index.html')[0], 404)
        finally:
            shutil.rmtree(folder)

    def test_headset_page_and_install_acknowledgement(self):
        code, _, body = self.request('GET', '/headset')
        self.assertEqual(code, 200)
        self.assertIn(b'Frame Control VR [fc-headset]', body)
        code, body = self.post('/api/headset', {'action': 'install'})
        self.assertEqual(code, 400)
        self.assertIn('opt-in', body['error'])

    def test_foreign_host_rejected(self):
        # DNS rebinding: a hostile name pointed at 127.0.0.1.
        for path in ("/", "/api/status"):
            status, _, _ = self.request("GET", path, headers={"Host": f"evil.example:{self.port}", "X-Frame-UI": "1"})
            self.assertEqual(status, 403, path)

    def test_api_needs_custom_header(self):
        # <img src> and plain form posts from other sites can't set it.
        self.assertEqual(self.request("POST", "/api/comfort", {"action": "start"})[0], 403)
        self.assertEqual(self.request("GET", "/api/status")[0], 403)
        self.assertEqual(self.request("GET", "/api/screenshot?view=headset")[0], 403)
        self.assertEqual(self.request("GET", "/api/shots")[0], 403)
        self.assertEqual(self.request("GET", "/api/stream")[0], 403)
        self.assertEqual(self.request("GET", "/api/shots/image?id=1/250820/20260925225208_1.jpg")[0], 403)
        self.assertEqual(self.request("POST", "/api/launch", {"appid": "620"})[0], 403)
        self.assertEqual(self.request("GET", "/api/record")[0], 403)
        self.assertEqual(self.request("GET", "/api/clips")[0], 403)
        self.assertEqual(self.request("POST", "/api/record", {"action": "start"})[0], 403)
        self.assertEqual(self.request("POST", "/api/clips/export", {"id": "1/video/bg_620_20261020_201950"})[0], 403)

    def test_captures_are_not_cacheable(self):
        # Headset captures show everything on screen; nothing may cache them.
        _, headers, _ = self.request("GET", "/api/screenshot", headers={"X-Frame-UI": "1"})
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy", ""))

    def test_input_validation(self):
        cases = [
            ("/api/comfort", {"action": "poweroff"}),
            ("/api/comfort", {"action": "start", "minutes": 0}),
            ("/api/launch", {"appid": "620; rm -rf ~"}),
            ("/api/launch", {"appid": ""}),
            ("/api/flatpak", {"id": "org.example.App;id", "action": "install"}),
            ("/api/flatpak", {"id": "org.example.App", "action": "explode"}),
            ("/api/volume", {"level": 1.5}),
            ("/api/clipboard", {"text": ""}),
            ("/api/open", {"what": "anything-else"}),
            ("/api/open", {"what": "shot", "id": "1/250820/../../.ssh/id_ed25519"}),
            ("/api/open", {"what": "shot"}),
            ("/api/shots/save", {"ids": []}),
            ("/api/shots/save", {"ids": "1/250820/20260925225208_1.jpg"}),
            ("/api/shots/save", {"ids": [1]}),
            ("/api/shots/save", {"ids": ["1/250820/../../.ssh/id_ed25519"]}),
            ("/api/shots/save", {"ids": ["1/250820/20260925225208_1.jpg; rm -rf ~"]}),
            ("/api/record", {}),
            ("/api/record", {"action": "explode"}),
            ("/api/clips/export", {}),
            ("/api/clips/export", {"id": 5}),
            ("/api/clips/export", {"id": "1/video/../../../../.ssh"}),
            ("/api/clips/export", {"id": "1/video/bg;rm -rf ~"}),
            ("/api/clips/export", {"id": "../1/video/bg"}),
        ]
        for path, body in cases:
            status, payload = self.post(path, body)
            self.assertEqual(status, 400, f"{path} {body} -> {payload}")

    def test_recorder_idle_until_started(self):
        status, _, payload = self.request("GET", "/api/record", headers={"X-Frame-UI": "1"})
        self.assertEqual((status, json.loads(payload)), (200, {"state": "idle"}))
        status, payload = self.post("/api/record", {"action": "stop"})
        self.assertEqual(status, 409, payload)

    def test_showing_a_shot_needs_it_saved_here(self):
        status, payload = self.post("/api/open", {"what": "shot", "id": "1/250820/19990101000000_1.jpg"})
        self.assertEqual(status, 404, payload)

    def test_screenshot_ids_checked_before_ssh(self):
        for shot in ("../../etc/passwd", "1/250820/x.jpg", "1/2/20260925225208_1.jpg;id", "1/250820/20260925225208_1.gif"):
            status, _, _ = self.request("GET", f"/api/shots/image?id={quote(shot)}", headers={"X-Frame-UI": "1"})
            self.assertEqual(status, 400, shot)

    def test_stream_settings_checked_before_ssh(self):
        for query in ("h=480", "fps=24", "h=abc", "h=1080&fps=120"):
            status, _, _ = self.request("GET", f"/api/stream?{query}", headers={"X-Frame-UI": "1"})
            self.assertEqual(status, 400, query)

    def test_bad_bodies(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/launch", body=b"{not json", headers={"X-Frame-UI": "1"})
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()
        status, _ = self.post("/api/launch", ["not", "an", "object"])
        self.assertEqual(status, 400)

    def test_title_upload_is_inspected_then_discarded(self):
        # A zip holding a Windows x86-64 program: inspected locally, no SSH until install.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("Tiny Game/Tiny Game.exe",
                       b"MZ" + b"\0" * 0x3A + struct.pack("<I", 0x40) + b"PE\0\0" + struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 0xF0, 0x22))
        status, _, payload = self.request("POST", "/api/upload", buf.getvalue(),
                                          {"X-Frame-UI": "1", "X-Mode": "title", "X-Filename": quote("Tiny Game-win64.zip")})
        r = json.loads(payload)
        self.assertEqual(status, 200, r)
        self.assertEqual((r["plan"]["id"], r["plan"]["target"], r["plan"]["runtime"]),
                         ("Tiny_Game", "Tiny Game.exe", "proton-experimental"))
        self.assertNotIn("root", r["plan"])
        self.assertEqual(self.post("/api/titles", {"action": "discard", "token": r["token"]})[0], 200)
        self.assertEqual(self.post("/api/titles", {"action": "install", "token": r["token"]})[0], 400)

    def test_title_input_validation(self):
        status, _, _ = self.request("POST", "/api/upload", b"not a zip",
                                    {"X-Frame-UI": "1", "X-Mode": "title", "X-Filename": "x.zip"})
        self.assertEqual(status, 400)
        for body in ({"action": "inspect", "path": "relative/game.zip"},
                     {"action": "inspect", "path": "/nonexistent/frame-control/game.zip"},
                     {"action": "install", "token": "nope"},
                     {"action": "launch", "id": "x; rm -rf ~"},
                     {"action": "remove", "id": "../etc"},
                     {"action": "explode"}):
            status, payload = self.post("/api/titles", body)
            self.assertEqual(status, 400, f"{body} -> {payload}")
        self.assertEqual(self.request("GET", "/api/titles/job?token=nope", headers={"X-Frame-UI": "1"})[0], 404)
        self.assertEqual(self.request("POST", "/api/titles", {"action": "list"})[0], 403)

    def test_direct_local_transfer_is_desktop_only(self):
        status, payload = self.post("/api/transfer", {"action": "copy-local", "path": "/tmp/a.bin"})
        self.assertEqual(status, 403, payload)

    def test_oversized_browser_upload_rejected_without_reading_body(self):
        status, _, payload = self.request("POST", "/api/upload", b"",
                                          {"X-Frame-UI": "1", "X-Filename": "large.bin",
                                           "Content-Length": str(27 * 1024 ** 3)})
        self.assertEqual(status, 413, payload)
        self.assertIn(b"limited to 8 GiB", payload)

    def test_web_install_needs_the_app_page(self):
        # A website can only open frame-control:// links; it can't call these itself.
        link = {"url": "https://cdn.example.com/game.apk"}
        self.assertEqual(self.request("POST", "/api/webinstall/check", link)[0], 403)
        self.assertEqual(self.request("POST", "/api/webinstall/start", {"id": "x"})[0], 403)
        status, _, _ = self.request("POST", "/api/webinstall/check", link,
                                    {"X-Frame-UI": "1", "Host": f"evil.example:{self.port}"})
        self.assertEqual(status, 403)

    def test_web_install_validation(self):
        for body in ({}, {"url": 5}, {"url": "http://cdn.example.com/game.apk"}, {"url": "https://10.0.0.2/game.apk"},
                     {"url": "https://u:p@example.com/game.apk"}, {"url": "https://example.com/"},
                     {"url": "https://1.1.1.1/game.sh"}, {"manifest": "file:///etc/passwd"},
                     {"manifest": "https://example.com/m.json", "url": "https://example.com/g.apk"}):
            status, payload = self.post("/api/webinstall/check", body)
            self.assertEqual(status, 400, f"{body} -> {payload}")
        # Only an id from /check starts an install, and only once.
        self.assertEqual(self.post("/api/webinstall/start", {"id": "made-up"})[0], 400)
        self.assertEqual(self.request("GET", "/api/webinstall/job?id=x", headers={"X-Frame-UI": "1"})[0], 404)
        self.assertEqual(self.post("/api/webinstall/cancel", {"job": "x"})[0], 404)

    def test_unreachable_frame_is_one_clear_offline_error(self):
        status, _, payload = self.request("GET", "/api/status", headers={"X-Frame-UI": "1"})
        body = json.loads(payload)
        self.assertEqual(status, 503, body)
        self.assertTrue(body["offline"])
        self.assertIn("Can't find the Frame", body["error"])
        self.assertIn("frame-control-test.invalid", body["detail"])  # ssh's own words stay available

    def test_flatpak_install_runs_as_a_job(self):
        status, started = self.post("/api/flatpak", {"id": "org.example.App", "action": "install"})
        self.assertEqual(status, 200, started)
        for _ in range(200):
            status, _, payload = self.request("GET", f"/api/job?id={started['job']}", headers={"X-Frame-UI": "1"})
            job = json.loads(payload)
            if job["done"]:
                break
            time.sleep(0.05)
        self.assertEqual(status, 200)
        self.assertTrue(job["done"])
        self.assertIn("Can't find the Frame", job["error"])
        self.assertEqual(self.request("GET", "/api/job?id=nope", headers={"X-Frame-UI": "1"})[0], 404)

    def test_android_install_checks_the_package_before_starting(self):
        status, body = self.post("/api/android", {"action": "install", "package": "org.example.not.in.catalogue"})
        self.assertNotEqual(status, 200, body)
        self.assertNotIn("job", body)

    def test_android_install_of_another_version_runs_as_a_job(self):
        pkg = "org.example.frame_control.not_in_any_repo"
        sys.path.insert(0, str(ROOT / "ui"))
        import frame_apk_versions
        # The job must fail on the cached lookup, before any download: nothing is cached for this package.
        self.assertEqual(frame_apk_versions._versions(pkg, cached_only=True)[0], [])
        status, started = self.post("/api/android", {"action": "install", "package": pkg,
                                                     "url": f"https://f-droid.org/repo/{pkg}_1.apk"})
        self.assertEqual(status, 200, started)
        for _ in range(200):
            job = json.loads(self.request("GET", f"/api/job?id={started['job']}", headers={"X-Frame-UI": "1"})[2])
            if job["done"]:
                break
            time.sleep(0.05)
        self.assertTrue(job["done"])
        self.assertIn("no longer available", job["error"])

    def test_unknown_routes(self):
        self.assertEqual(self.request("GET", "/nope")[0], 404)
        self.assertEqual(self.post("/api/nope", {})[0], 404)


class OneServer(unittest.TestCase):
    """Two servers for one user would each connect and edit headsets on their own."""

    def start(self, env):
        proc = subprocess.Popen([sys.executable, str(ROOT / "ui" / "server.py"), "--port", "0"], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(lambda: (proc.terminate(), proc.wait(10), proc.stdout.close()))
        return proc

    def test_a_second_server_is_refused_until_the_first_exits(self):
        data = tempfile.mkdtemp(prefix="frame-one-server-")
        env = {**os.environ, "FRAME_CONTROL_DATA_DIR": data, "FRAME_ALIAS": "frame-control-test.invalid",
               "FRAME_CONTROL_SERVER_WAIT": "1"}
        first = self.start(env)
        self.assertIn("Frame Control on", first.stdout.readline())
        second = subprocess.run([sys.executable, str(ROOT / "ui" / "server.py"), "--port", "0"], env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(second.returncode, 1, second.stderr)
        self.assertIn("already running", second.stderr)
        first.terminate()
        first.wait(10)
        self.assertIn("Frame Control on", self.start(env).stdout.readline())

    def test_a_private_server_runs_alongside_but_cant_change_headsets(self):
        """The MCP adapter starts its own server (FRAME_PRIVATE_SSH=1) while the app runs."""
        data = tempfile.mkdtemp(prefix="frame-one-server-")
        env = {**os.environ, "FRAME_CONTROL_DATA_DIR": data, "FRAME_ALIAS": "frame-control-test.invalid",
               "FRAME_CONTROL_SERVER_WAIT": "1"}
        self.assertIn("Frame Control on", self.start(env).stdout.readline())
        private = self.start({**env, "FRAME_PRIVATE_SSH": "1"})
        line = private.stdout.readline()
        self.assertIn("Frame Control on", line)
        port = int(line.split("http://127.0.0.1:")[1].split()[0])
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", "/api/devices", body=json.dumps({"action": "use", "id": "x"}),
                     headers={"Content-Type": "application/json", "X-Frame-UI": "1", "Host": f"127.0.0.1:{port}"})
        r = conn.getresponse()
        self.assertEqual(r.status, 403, r.read())

    @unittest.skipIf(os.name == "nt", "no SIGTERM on Windows")
    def test_sigterm_while_the_app_holds_stdin_exits_cleanly(self):
        """The app keeps stdin open; a stop signal used to abort Python (SIGABRT) at exit,
        and later, now and then, crash it (SIGSEGV) while background threads were still
        loading TLS certificates. Run a few times: that crash came about 1 run in 100."""
        for attempt in range(5):
            with self.subTest(attempt=attempt):
                env = {**os.environ, "FRAME_CONTROL_DATA_DIR": tempfile.mkdtemp(prefix="frame-one-server-"),
                       "FRAME_ALIAS": "frame-control-test.invalid", "PYTHONFAULTHANDLER": "1"}
                proc = subprocess.Popen([sys.executable, str(ROOT / "ui" / "server.py"), "--port", "0", "--exit-on-eof"],
                                        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                try:
                    self.assertIn("Frame Control on", proc.stdout.readline())
                    proc.terminate()
                    self.assertEqual(proc.wait(30), 0, proc.stdout.read())
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
                    proc.stdin.close()
                    proc.stdout.close()
                    shutil.rmtree(env["FRAME_CONTROL_DATA_DIR"], ignore_errors=True)

    def test_staging_folders_cleared_when_stopped_mid_transfer(self):
        """The server leaves without interpreter teardown, so TemporaryDirectory cleanup
        doesn't run for work still in progress: its own staging folders go on the way out,
        and a dead server's at the next start."""
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        home = tempfile.mkdtemp(prefix="frame-stop-home-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        env = {**os.environ, "FRAME_CONTROL_DATA_DIR": os.path.join(home, "data"),
               "FRAME_ALIAS": "frame-control-test.invalid", "HOME": home, "XDG_CACHE_HOME": os.path.join(home, ".cache"),
               "LOCALAPPDATA": home, "APPDATA": home}
        index_dir = Path(subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import frame_host; "
                                   "print(frame_host.cache_dir('apk-sources'))", str(ROOT / "ui")],
            env=env, capture_output=True, text=True, check=True).stdout.strip())
        index_dir.mkdir(parents=True)
        tmp = Path(tempfile.gettempdir())

        def staged(folder, prefix, pid):
            d = Path(tempfile.mkdtemp(prefix=f"{prefix}{pid}-", dir=folder))
            self.addCleanup(shutil.rmtree, d, ignore_errors=True)
            (d / "app.apk").write_bytes(b"\0" * 4096)
            return d

        # Stopped as the app stops it: by closing stdin (the only way on Windows,
        # where terminate() is a hard kill) and, elsewhere, by SIGTERM too.
        for stop in ["stdin"] + (["sigterm", "stdin+late-sigterm"] if os.name != "nt" else []):
            with self.subTest(stop=stop):
                left_by_dead = [staged(tmp, "frame-vr-", dead.pid), staged(index_dir, ".download-", dead.pid)]
                command = [sys.executable, str(ROOT / "ui" / "server.py"), "--port", "0", "--exit-on-eof"]
                if stop == "stdin+late-sigterm":
                    # Deliver the app's second stop mechanism exactly as cleanup
                    # replaces the signal handler: the race observed on a real Mac.
                    wrapper = (
                        "import os, runpy, signal, sys; from pathlib import Path\n"
                        "original = signal.signal\n"
                        "def install(sig, handler):\n"
                        "    if sig == signal.SIGTERM and handler == signal.SIG_IGN:\n"
                        "        os.kill(os.getpid(), signal.SIGTERM)\n"
                        "    return original(sig, handler)\n"
                        "signal.signal = install\n"
                        "sys.argv = sys.argv[1:]\n"
                        "sys.path.insert(0, str(Path(sys.argv[0]).parent))\n"
                        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
                    )
                    command = [sys.executable, "-c", wrapper, *command[1:]]
                proc = subprocess.Popen(command,
                                        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                try:
                    self.assertIn("Frame Control on", proc.stdout.readline())
                    self.assertEqual([d for d in left_by_dead if d.exists()], [])
                    in_flight = [staged(tmp, "frame-vr-", proc.pid), staged(tmp, "frame-agent-", proc.pid),
                                 staged(index_dir, ".download-", proc.pid)]
                    if stop.startswith("stdin"):
                        proc.stdin.close()
                    else:
                        proc.terminate()
                    self.assertEqual(proc.wait(30), 0, proc.stdout.read())
                    self.assertEqual([d for d in in_flight if d.exists()], [])
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
                    proc.stdin.close()
                    proc.stdout.close()


class ArtworkSettings(unittest.TestCase):
    """The settings panel's endpoints, with and without the page's X-Frame-UI key."""

    def test_settings_need_and_accept_the_ui_key(self):
        with tempfile.TemporaryDirectory() as home:
            port = free_port()
            env = {**os.environ, "FRAME_ALIAS": "frame-control-test.invalid", "PYTHONDONTWRITEBYTECODE": "1",
                   "HOME": home, "APPDATA": home, "XDG_DATA_HOME": home}
            for name in ("STEAMGRIDDB_API_KEY", "FRAME_STEAMGRIDDB_API_KEY", "FRAME_UI_KEY"):
                env.pop(name, None)
            proc = subprocess.Popen([sys.executable, str(ROOT / "ui" / "server.py"), "--port", str(port)],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                def request(method, path, body=None, headers=None):
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    conn.request(method, path, body=json.dumps(body).encode() if body is not None else None,
                                 headers=headers or {})
                    r = conn.getresponse()
                    payload = r.read()
                    conn.close()
                    return r.status, payload
                for _ in range(100):
                    try:
                        if request("GET", "/")[0] == 200:
                            break
                    except OSError:
                        time.sleep(0.05)
                key = {"X-Frame-UI": "1", "Content-Type": "application/json"}
                self.assertEqual(request("GET", "/api/settings/artwork")[0], 403)
                # The missing-key guard runs before reading a body. Leaving an
                # unread body on Windows can reset this test connection before
                # http.client receives the 403 response.
                self.assertEqual(request("POST", "/api/settings/artwork")[0], 403)
                status, payload = request("GET", "/api/settings/artwork", headers=key)
                self.assertEqual((status, json.loads(payload)["steamgriddb_configured"]), (200, False))
                status, payload = request("POST", "/api/settings/artwork", {"steamgriddb_api_key": "abc_1"}, key)
                self.assertEqual((status, json.loads(payload)["steamgriddb_configured"]), (200, True))
                self.assertNotIn(b"abc_1", payload)
                status, payload = request("GET", "/api/settings/artwork", headers=key)
                self.assertTrue(json.loads(payload)["steamgriddb_configured"])
                self.assertEqual(request("POST", "/api/settings/artwork", {"steamgriddb_api_key": "a b"}, key)[0], 400)
            finally:
                proc.terminate()
                proc.wait(timeout=10)

    def test_panel_script_uses_the_keyed_api_helper(self):
        script = (ROOT / "ui" / "artwork-settings.js").read_text(encoding="utf-8")
        self.assertNotIn("fetch(", script)
        self.assertIn("api('/api/settings/artwork'", script)
        page = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertLess(page.index("async function api("), page.index('<script src="/artwork-settings.js">'))


@unittest.skipUnless(shutil.which("node"), "needs node")
class PageScripts(unittest.TestCase):
    """A page's scripts share one global scope, where a later function declaration
    silently replaces an earlier one of the same name. Issue #68: the Devices page's
    renderDetail replaced the Android store's, so every app opened as an empty
    dialog (a bare horizontal line). Compiled together as one module, any top-level
    name declared twice is a SyntaxError; node's parser handles nested scopes,
    comments and strings."""

    PAGES = ("index.html", "assistant.html", "mac-view.html")

    @staticmethod
    def page_scripts(html):
        """A page's inline scripts, then its /*.js scripts, in one source."""
        import re
        parts = re.findall(r"<script>([\s\S]*?)</script>", html)
        parts += [(ROOT / "ui" / src).read_text(encoding="utf-8") for src in re.findall(r'<script src="/([\w.-]+\.js)">', html)]
        return "\n;\n".join(parts)

    @staticmethod
    def module_check(source):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.mjs"
            path.write_text(source, encoding="utf-8")
            r = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        return r.returncode, r.stderr

    def test_the_check_catches_top_level_duplicates_only(self):
        dup = "<script>function a() {}\nfunction a() {}</script>"
        across = "<script>function a() {}</script><p>x</p><script>  async function a() {}</script>"
        same_line = "<script>function a() {} function a() {}</script>"
        const_and_function = "<script>const a = 1, b = 2;\nfunction b() {}</script>"
        for html in (dup, across, same_line, const_and_function):
            rc, err = self.module_check(self.page_scripts(html))
            self.assertNotEqual(rc, 0, html)
            self.assertIn("has already been declared", err, html)
        nested = ("<script>function a() {}\nfunction f() { function a() {} if (1) { const a = 2; } }\n"
                  "// function a() {}\nconst s = `function a() {}`;</script>")
        self.assertEqual(self.module_check(self.page_scripts(nested)), (0, ""))

    def test_no_top_level_name_is_declared_twice(self):
        for name in self.PAGES:
            source = self.page_scripts((ROOT / "ui" / name).read_text(encoding="utf-8"))
            self.assertIn("function", source, name)
            rc, err = self.module_check(source)
            self.assertEqual(rc, 0, f"{name}: {err}")

    def test_store_app_page_renders(self):
        """tests/page/store_detail.mjs runs the real store functions from index.html."""
        r = subprocess.run(["node", str(ROOT / "tests" / "page" / "store_detail.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_meta_library_rows_render(self):
        """tests/page/meta_rows.mjs runs the real Meta library row rendering from index.html."""
        r = subprocess.run(["node", str(ROOT / "tests" / "page" / "meta_rows.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_large_local_file_uses_direct_copy(self):
        r = subprocess.run(["node", str(ROOT / "tests" / "page" / "large_transfer.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


@unittest.skipIf(os.name == "nt", "runs on the Frame (Linux); local-bin/ssh is a POSIX shell script")
class LocalMode(unittest.TestCase):
    """FRAME_LOCAL=1, as the iPhone app starts the server on the Frame: its own key
    guards /api/, and ssh goes to ui/local-bin/ssh, which runs commands here."""

    KEY = "0123456789abcdef0123456789abcdef"

    @classmethod
    def setUpClass(cls):
        env = {**os.environ, "FRAME_LOCAL": "1", "FRAME_UI_KEY": cls.KEY, "FRAME_DEVICE": "iPhone",
               "PYTHONDONTWRITEBYTECODE": "1"}
        cls.log = tempfile.TemporaryFile()
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / "ui" / "server.py"), "--port", "0", "--exit-on-eof"],
                                    env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=cls.log, text=True)
        line = cls.proc.stdout.readline()
        cls.port = int(line.split("127.0.0.1:")[1].split()[0])  # --port 0: the server prints the port it took

    @classmethod
    def tearDownClass(cls):
        cls.proc.stdin.close()  # --exit-on-eof: the phone disconnecting
        cls.proc.wait(timeout=15)
        cls.proc.stdout.close()
        cls.log.close()

    def request(self, method, path, body=None, key=KEY):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.request(method, path, body=json.dumps(body).encode() if body is not None else None,
                     headers={"X-Frame-UI": key, "Content-Type": "application/json"})
        r = conn.getresponse()
        data = json.loads(r.read() or b"{}")
        conn.close()
        return r.status, data

    def test_needs_the_session_key(self):
        self.assertEqual(self.request("GET", "/api/host", key="1")[0], 403)
        self.assertEqual(self.request("GET", "/api/host", key="")[0], 403)
        status, host = self.request("GET", "/api/host")
        self.assertEqual(status, 200)
        self.assertEqual(host, {"os": "SteamOS", "fileManager": None, "computer": "iPhone", "mobile": True})

    def test_commands_run_locally(self):
        # frame_titles lists ~/devkit-game here; with nothing there, the list is empty rather than an ssh error.
        status, body = self.request("GET", "/api/titles")
        self.assertEqual(status, 200, body)
        self.assertIsInstance(body["titles"], list)

    def test_recordings_are_for_a_computer(self):
        for method, path, body in (("GET", "/api/record", None), ("GET", "/api/clips", None),
                                   ("POST", "/api/record", {"action": "start"}),
                                   ("POST", "/api/clips/export", {"id": "1/video/bg_620_20261020_201950"})):
            status, payload = self.request(method, path, body)
            self.assertEqual(status, 400, (path, payload))
            self.assertIn("computer", payload["error"])

    def test_open_is_for_the_app_and_power_needs_a_password(self):
        self.assertEqual(self.request("POST", "/api/open", {"what": "terminal"})[0], 400)
        status, body = self.request("POST", "/api/open", {"what": "reboot"})
        self.assertEqual(status, 400)
        self.assertIn("password", body["error"])
        self.assertEqual(self.request("POST", "/api/open", {"what": "reboot", "password": "a\nb"})[0], 400)


class UnreachableMessages(unittest.TestCase):
    """Only ssh's own connection failures are reworded; other errors keep their text."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "ui"))
        import server
        cls.server = server

    def test_ssh_connection_failures(self):
        cases = {
            "ssh: Could not resolve hostname frame: nodename nor servname provided": "Can't find",
            "ssh: connect to host frame.local port 22: Operation timed out": "isn't answering",
            "ssh: connect to host 192.168.1.9 port 22: Host is down": "isn't answering",
            "ssh: connect to host 192.168.1.9 port 22: No route to host": "isn't answering",
            "ssh: connect to host 192.168.1.9 port 22: Connection refused": "refused",
            "steamos@192.168.1.9: Permission denied (publickey,password).": "SSH key",
            "Host key verification failed.": "identity has changed",
            "@@@@\n@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @\nHost key verification failed.":
                "Check the new key on the Devices tab",
            "No ED25519 host key is known for frame-control-f7b4e9ac and you have requested strict checking.\n"
            "Host key verification failed.": "isn't saved yet",
            "kex_exchange_identification: read: Connection reset by peer": "dropped",
            "Timed out talking to frame": "too long",
        }
        for raw, words in cases.items():
            body, status = self.server.error_body(raw)
            self.assertEqual(status, 503, raw)
            self.assertIn(words, body["error"], raw)
            self.assertTrue(body["offline"])

    def test_other_errors_pass_through(self):
        for raw in ("bad Flatpak app ID", "error: No remote refs found for 'org.example.App'",
                    "cp: cannot open 'x': Permission denied", "timed out waiting for Steam"):
            self.assertEqual(self.server.error_body(raw), ({"error": raw}, None), raw)


class ClipboardDesktopClosed(unittest.TestCase):
    """The headset's desktop being closed is the person's to fix: a 409, not a 5xx fault for telemetry."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "ui"))
        import server
        cls.server = server

    def paste_failing_with(self, message):
        s = self.server
        saved = s.ssh

        def fake_ssh(remote, **kw):
            raise s.Failure(message)
        s.ssh = fake_ssh
        try:
            s.clipboard({"text": "hello"})
        finally:
            s.ssh = saved

    def test_desktop_closed_is_a_409(self):
        with self.assertRaises(self.server.Failure) as cm:
            self.paste_failing_with("The headset's desktop isn't open (plasmashell is not running). "
                                    "Open the desktop in the headset, then try again.")
        self.assertEqual(cm.exception.status, 409)
        self.assertIn("Open the desktop", str(cm.exception))
        # Older wording (scripts/paste-to-frame.sh) is recognised too.
        with self.assertRaises(self.server.Failure) as cm:
            self.paste_failing_with("plasmashell is not running: open the desktop in the headset first.")
        self.assertEqual(cm.exception.status, 409)

    def test_other_failures_stay_faults(self):
        with self.assertRaises(self.server.Failure) as cm:
            self.paste_failing_with("Klipper call failed (bus: none)")
        self.assertEqual(cm.exception.status, 502)

    def test_paste_script_says_it(self):
        self.assertIn(self.server.DESKTOP_CLOSED, self.server.PASTE)


class StatusProbe(unittest.TestCase):
    # frame_status.py only ever runs on the Frame (Linux); it needs os.statvfs.
    @unittest.skipIf(os.name == "nt", "Frame-side script; POSIX only")
    def test_runs_off_device_and_prints_one_json_object(self):
        # The probe runs on the Frame; elsewhere every field must degrade to null/empty.
        out = subprocess.run([sys.executable, str(ROOT / "ui" / "frame_status.py")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        for key in ("hostname", "battery", "disk", "services", "games", "flatpaks"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
