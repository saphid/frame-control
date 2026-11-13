"""Repositories and sources behind a login: F-Droid basic auth and GitHub tokens.

A fake HTTPS layer stands in for the network (urllib's real redirect, error and
request processing still run), so these tests see every request and its headers.
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import base64
import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import urllib.request
import urllib.response

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
from apk_sources import SourceAuthError, SourceError, SourceLimited, _credentials, _images, _web, fdroid, github, search
import server

FIXTURES = Path(__file__).parent / 'fixtures' / 'fdroid'
PIN = (FIXTURES / 'fingerprint.txt').read_text().strip()
REPO = 'https://repo.example/fdroid/repo/'
USER, PASSWORD = 'alice', 's3cr@t-pässword'
TOKEN = 'ghp_frameControlTestToken0123456789'
SECRETS = (PASSWORD, TOKEN, base64.b64encode((USER + ':' + PASSWORD).encode()).decode())
REAL_BUILD_OPENER = urllib.request.build_opener


def basic(user, password):
    return 'Basic ' + base64.b64encode((user + ':' + password).encode()).decode()


class FakeHTTPS(urllib.request.HTTPSHandler):
    """Answers https requests from route(url, authorization) -> (status, headers, body)."""

    def __init__(self, route):
        super().__init__()
        self.route, self.seen = route, []

    def https_open(self, req):
        auth = req.get_header('Authorization')
        self.seen.append((req.full_url, auth))
        status, headers, body = self.route(req.full_url, auth)
        message = http.client.HTTPMessage()
        for key, value in headers.items():
            message[key] = value
        response = urllib.response.addinfourl(io.BytesIO(body), message, req.full_url, status)
        response.msg = 'fake'
        return response


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for name, value in [('data_dir', lambda *p: self.root.joinpath('data', *p)),
                            ('cache_dir', lambda *p: self.root.joinpath('cache', *p))]:
            mock = patch.object(fdroid.frame_host, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.web = FakeHTTPS(self.route)
        mock = patch('urllib.request.build_opener', lambda *handlers: REAL_BUILD_OPENER(*handlers, self.web))
        mock.start()
        self.addCleanup(mock.stop)
        mock = patch.dict(os.environ, {github.ENV: ''})
        mock.start()
        self.addCleanup(mock.stop)
        for state in (_web._limited, fdroid._stale, fdroid._retry_at, fdroid._refreshing, github._rejected):
            state.clear()
            self.addCleanup(state.clear)
        self.stderr = io.StringIO()
        mock = patch('sys.stderr', self.stderr)
        mock.start()
        self.addCleanup(mock.stop)

    def route(self, url, auth):
        raise AssertionError('unexpected request ' + url)

    def assertNoSecrets(self, *texts):
        for text in texts:
            for secret in SECRETS + (USER + ':',):
                self.assertNotIn(secret, text)

    def disk(self):
        """Everything saved under the data and cache folders except the credentials file."""
        out = []
        for path in self.root.rglob('*'):
            if path.is_file() and path.name != 'source-credentials.json':
                out.append(path.read_bytes().decode('utf-8', 'replace'))
        return '\n'.join(out)

    def credentials_file(self):
        return self.root / 'data' / 'source-credentials.json'


class Repository(Base):
    """A repository at REPO that wants USER and PASSWORD."""
    def setUp(self):
        super().setUp()
        self.login = basic(USER, PASSWORD)
        self.redirect = None  # file name -> absolute URL it redirects to
        self.forbidden = 401

    def serve(self, name):
        return (FIXTURES / ('example.apk' if name.endswith('.apk') else name)).read_bytes()

    def route(self, url, auth):
        for mirror in ('https://mirror.example/fdroid/repo/', 'https://repo.example/elsewhere/'):
            if url.startswith(mirror):  # serves anyone; a login must never get here unless same-origin
                return 200, {}, self.serve(url[len(mirror):])
        self.assertTrue(url.startswith(REPO), url)
        if auth != self.login:
            return self.forbidden, {'WWW-Authenticate': 'Basic realm="repo"'}, b'no'
        name = url[len(REPO):]
        if self.redirect and name in self.redirect:
            return 302, {'Location': self.redirect[name]}, b''
        return 200, {}, self.serve(name)

    def add(self, **kw):
        return fdroid.add_repo('https://alice:s3cr%40t-p%C3%A4ssword@repo.example/fdroid/repo', PIN, **kw)


class RepositoryLogin(Repository):
    def test_add_search_download_with_login_in_the_url(self):
        source = self.add()
        self.assertEqual(source['url'], REPO)
        self.assertEqual(source['fingerprint'], PIN)
        saved = fdroid.user_repos()[0]
        self.assertEqual(saved['url'], REPO)
        self.assertNotIn('login', saved)
        self.assertEqual(len(fdroid.search(source, 'example offline')), 1)
        downloaded = fdroid.download(source, 'org.example.app', 1)
        self.assertTrue(downloaded['verified'])
        self.assertTrue(self.web.seen)
        self.assertTrue(all(auth == self.login for url, auth in self.web.seen))
        self.assertTrue(all('@' not in url for url, auth in self.web.seen))  # never in the URL
        self.assertTrue(next(s for s in fdroid.sources() if s['id'] == source['id'])['login'])
        self.assertNoSecrets(json.dumps(source), json.dumps(fdroid.sources()), self.disk(), self.stderr.getvalue())
        # The settings file holds no part of the login; the credentials file holds it, privately.
        settings = (self.root / 'data' / 'apk-repos.json').read_text()
        self.assertNotIn(USER, settings)
        self.assertTrue(self.credentials_file().is_file())
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(self.credentials_file().stat().st_mode), 0o600)

    def test_login_given_apart_and_saved_login_reused_on_refresh(self):
        source = fdroid.add_repo(REPO, PIN, username=USER, password=PASSWORD)
        self.assertEqual(source['url'], REPO)
        self.web.seen.clear()
        fdroid._load(fdroid.user_repos()[0], force=True)  # as a background refresh would
        self.assertTrue(self.web.seen)
        self.assertTrue(all(auth == self.login for url, auth in self.web.seen))
        fdroid.add_repo(REPO)  # re-adding without a login keeps the saved one
        self.assertTrue(_credentials.has(source['id']))

    def test_wrong_or_missing_login_saves_nothing(self):
        for kw, message in [({'username': USER, 'password': 'wrong'}, 'check the username and password'),
                            ({}, 'needs a username and password')]:
            with self.subTest(kw=kw):
                with self.assertRaisesRegex(SourceAuthError, message) as caught:
                    fdroid.add_repo(REPO, PIN, **kw)
                self.assertNoSecrets(str(caught.exception), repr(caught.exception))
                self.assertNotIn('wrong', str(caught.exception))
                self.assertEqual(fdroid.user_repos(), [])
                self.assertFalse(self.credentials_file().exists())
                self.assertFalse((self.root / 'data' / 'apk-repo-state.json').exists())
                self.assertEqual(_web._limited, {})  # an auth failure isn't a rate limit

    def test_403_with_a_login_is_a_login_error_not_a_rate_limit(self):
        self.forbidden = 403
        with self.assertRaisesRegex(SourceAuthError, 'check the username and password'):
            fdroid.add_repo(REPO, PIN, username=USER, password='wrong')
        self.assertEqual(_web._limited, {})
        self.assertEqual(fdroid.user_repos(), [])

    def test_signature_checks_still_apply(self):
        with self.assertRaisesRegex(SourceError, 'fingerprint mismatch'):
            fdroid.add_repo(REPO, '0' * 64, username=USER, password=PASSWORD)
        self.assertEqual(fdroid.user_repos(), [])
        self.assertFalse(self.credentials_file().exists())

    def test_cross_origin_redirect_never_gets_the_login(self):
        self.redirect = {'entry.jar': 'https://mirror.example/fdroid/repo/entry.jar',
                         'index-v2.json': 'https://repo.example/elsewhere/index-v2.json'}
        source = self.add()
        self.assertEqual(source['fingerprint'], PIN)  # the mirror's copy still had to verify
        mirror = [auth for url, auth in self.web.seen if url.startswith('https://mirror.example/')]
        same_origin = [auth for url, auth in self.web.seen if url.startswith('https://repo.example/elsewhere/')]
        self.assertEqual(mirror, [None])
        self.assertEqual(same_origin, [None])  # same origin but outside the repository: no login either

    def test_traversal_names_are_refused_and_never_get_the_login(self):
        for name in ('%252e%252e/%252e%252e/evil/collect.apk', '..;/..;/evil/collect.apk', 'a%2f..%2f..%2fevil.apk',
                     'a%5c..%5cevil.apk', '%2e%2e/evil.apk', 'x;y.apk', '100%25.apk'):
            with self.subTest(name=name), self.assertRaisesRegex(SourceError, 'unsafe|outside'):
                fdroid._child(REPO, name)
        self.assertEqual(fdroid._child(REPO, '/app/en-US/phoneScreenshots/#0 a.png'),
                         REPO + 'app/en-US/phoneScreenshots/%230%20a.png')
        # Even if such a URL reached the downloader directly, the login stays home.
        login = _credentials.basic(REPO, USER, PASSWORD)
        for url in (REPO + '%252e%252e/%252e%252e/evil/collect.apk', REPO + '..;/..;/evil/collect.apk'):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as tmp:
                self.web.seen.clear()
                with contextlib.suppress(SourceError):  # the repository answers 401 without the login
                    fdroid._fetch(url, Path(tmp) / 'out', 1 << 20, auth=login)
                self.assertEqual(self.web.seen, [(url, None)])

    def test_same_origin_redirect_outside_the_repository_gets_no_login(self):
        self.redirect = {'example1.apk': 'https://repo.example/elsewhere/example1.apk'}
        source = self.add()
        self.web.seen.clear()
        self.assertTrue(fdroid.download(source, 'org.example.app', 1)['verified'])
        self.assertEqual(self.web.seen, [(REPO + 'example1.apk', self.login),
                                         ('https://repo.example/elsewhere/example1.apk', None)])

    def test_other_ports_and_http_never_get_the_login(self):
        login = _credentials.basic(REPO, USER, PASSWORD)
        for url in ('https://repo.example:8443/fdroid/repo/x', 'http://repo.example/fdroid/repo/x',
                    'https://other.example/fdroid/repo/x', 'https://repo.example.evil/x'):
            self.assertFalse(login.matches(url), url)
        self.assertTrue(login.matches('https://REPO.example:443/anything'))
        self.assertNoSecrets(repr(login))
        handler = _credentials.Handler(login)
        req = urllib.request.Request('https://other.example/x', headers={'Authorization': 'Basic stale'})
        self.assertIsNone(handler.https_request(req).get_header('Authorization'))

    def test_http_and_bad_logins_are_refused_before_any_request(self):
        for url, kw in [('http://alice:pw@repo.example/fdroid/repo', {}),
                        ('http://repo.example/fdroid/repo', {'username': USER, 'password': PASSWORD}),
                        (REPO, {'username': 'a:b', 'password': PASSWORD}),
                        (REPO, {'username': USER, 'password': 'x\r\nX-Evil: 1'}),
                        (REPO, {'password': PASSWORD}),
                        ('https://alice:pw@repo.example/fdroid/repo', {'username': 'bob'})]:
            with self.subTest(url=url, kw=kw), self.assertRaises(SourceError) as caught:
                fdroid.add_repo(url, PIN, **kw)
            self.assertNotIn('pw', str(caught.exception).replace('password', ''))
            self.assertNoSecrets(str(caught.exception))
        self.assertEqual(self.web.seen, [])

    def test_remove_deletes_the_login(self):
        source = self.add()
        other = _credentials.bearer('https://api.github.com/', TOKEN)
        _credentials.put('github', other)
        fdroid.remove_repo(source['id'])
        self.assertFalse(_credentials.has(source['id']))
        self.assertNotIn(PASSWORD, self.credentials_file().read_text())
        _credentials.remove('github')
        self.assertFalse(self.credentials_file().exists())  # nothing left: the file goes

    def test_cli_reads_the_password_from_stdin(self):
        out = io.StringIO()
        argv = ['fdroid.py', 'add', REPO, '--fingerprint', PIN, '--username', USER, '--password-stdin']
        with patch.object(sys, 'argv', argv), patch.object(sys, 'stdin', io.StringIO(PASSWORD + '\n')), \
                contextlib.redirect_stdout(out):
            fdroid.main()
        self.assertEqual(json.loads(out.getvalue())['url'], REPO)
        self.assertNoSecrets(out.getvalue())
        self.assertTrue(_credentials.has(fdroid.user_repos()[0]['id']))

    def test_artwork_from_the_repository_gets_the_login_and_only_there(self):
        source = self.add()
        self.assertEqual(_credentials.for_url(REPO + 'icons/a.png').header(), self.login)
        self.assertTrue(_credentials.has(source['id']))
        self.assertIsNone(_credentials.for_url('https://repo.example/other/a.png'))  # outside the repository
        self.assertIsNone(_credentials.for_url('https://cdn.example/fdroid/repo/a.png'))


class GitHubToken(Base):
    def setUp(self):
        super().setUp()
        self.accept = {TOKEN}
        self.releases = json.dumps([]).encode()
        self.anonymous_limited = False

    def route(self, url, auth):
        if url.startswith('https://api.github.com/'):
            if auth is not None and auth not in {'Bearer ' + t for t in self.accept}:
                return 401, {}, b'{"message": "Bad credentials"}'
            if auth is None and self.anonymous_limited:
                return 403, {'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': str(int(time.time()) + 1800)}, b'{}'
            if url.endswith('/redirected'):
                return 302, {'Location': 'https://github.com/landed'}, b''
            return 200, {}, self.releases
        if url == 'https://github.com/landed':
            return 200, {}, b'{"ok": true}'
        raise AssertionError('unexpected request ' + url)

    def test_saved_token_goes_only_to_the_api(self):
        github.set_token(TOKEN)
        self.assertEqual(github._api('/repos/a/b/releases'), [])
        self.assertEqual(self.web.seen, [('https://api.github.com/repos/a/b/releases', 'Bearer ' + TOKEN)])
        auth = github._credential(github._token()[0])
        self.assertEqual(_web.read('https://api.github.com/redirected', ('api.github.com', 'github.com'), auth=auth),
                         b'{"ok": true}')
        self.assertEqual(self.web.seen[-2:], [('https://api.github.com/redirected', 'Bearer ' + TOKEN),
                                              ('https://github.com/landed', None)])  # redirect: no token
        status = github.sources()[0]['token']
        self.assertEqual(status, {'set': True, 'from': 'saved', 'rejected': False})
        self.assertNoSecrets(json.dumps(github.sources()), self.disk(), self.stderr.getvalue())
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(self.credentials_file().stat().st_mode), 0o600)

    def test_rejected_token_retries_once_without_it(self):
        github.set_token(TOKEN)
        self.accept = set()
        self.assertEqual(github._api('/repos/a/b/releases'), [])
        self.assertEqual([auth for _, auth in self.web.seen], ['Bearer ' + TOKEN, None])
        self.assertTrue(github.token_status()['rejected'])
        self.assertIn('rejected', self.stderr.getvalue())
        self.assertNoSecrets(self.stderr.getvalue())
        self.web.seen.clear()
        github._api('/repos/a/b/other')
        self.assertEqual([auth for _, auth in self.web.seen], [None])  # not tried again this run
        github.set_token(TOKEN)  # saving it again gives it a fresh chance
        self.assertFalse(github.token_status()['rejected'])

    def test_environment_variable_wins(self):
        github.set_token(TOKEN)
        env = 'ghp_fromTheEnvironment'
        self.accept = {env}
        with patch.dict(os.environ, {github.ENV: env}):
            github._api('/repos/a/b/releases')
            self.assertEqual(self.web.seen[-1][1], 'Bearer ' + env)
            self.assertEqual(github.token_status(), {'set': True, 'from': 'env', 'rejected': False})
        self.assertEqual(github.token_status()['from'], 'saved')

    def test_clear_removes_it_from_disk(self):
        github.set_token(TOKEN)
        github.clear_token()
        self.assertFalse(self.credentials_file().exists())
        self.assertEqual(github.token_status(), {'set': False, 'from': None, 'rejected': False})
        github._api('/repos/a/b/releases')
        self.assertEqual(self.web.seen[-1][1], None)

    def test_saving_a_token_escapes_the_anonymous_rate_limit(self):
        self.anonymous_limited = True
        with self.assertRaisesRegex(SourceLimited, 'GitHub is limiting requests'):
            github._api('/repos/a/b/releases')
        self.assertEqual(self.web.seen[-1][1], None)
        github.set_token(TOKEN)
        self.assertEqual(github._api('/repos/a/b/other'), [])  # tried, with the token's own quota
        self.assertEqual(self.web.seen[-1], ('https://api.github.com/repos/a/b/other', 'Bearer ' + TOKEN))
        github.clear_token()
        count = len(self.web.seen)
        with self.assertRaisesRegex(SourceLimited, 'GitHub is limiting requests'):
            github._api('/repos/a/b/third')
        self.assertEqual(len(self.web.seen), count)  # anonymous is still backing off: no request

    def test_bad_tokens_are_refused(self):
        for token in ('', '   ', 'two words', 'x\nAuthorization: y'):
            with self.subTest(token=token), self.assertRaises(SourceError):
                github.set_token(token)
        self.assertFalse(self.credentials_file().exists())


PNG = b'\x89PNG\r\n\x1a\nfixture'
PRIVATE = 'https://repo.example/private/repo/'
TRAVERSALS = [PRIVATE + '%2e%2e/%2e%2e/evil/collect.png', PRIVATE + '%2E%2E/x.png', PRIVATE + '../../evil/x.png',
              PRIVATE + './icons/a.png', PRIVATE + '..%2f..%2fevil/x.png', PRIVATE + 'a%5c..%5c..%5cevil.png',
              PRIVATE + 'a;b/../../evil.png', PRIVATE + '%252e%252e/%252e%252e/evil.png',
              'https://repo.example/private/repository/x.png', 'https://repo.example/private/repo%2fx.png']


class ArtworkScope(Base):
    """The artwork proxy: actual outgoing headers, through _images.get's own HTTP code."""

    def setUp(self):
        super().setUp()
        self.sent, self.redirects = [], {}
        _credentials.put('fdroid-user-private', _credentials.basic(PRIVATE, USER, PASSWORD))
        test = self

        class Response:
            def __init__(self, status, location=''):
                self.status, self.location, self.body = status, location, PNG if status == 200 else b''

            def getheader(self, name, default=''):
                return self.location if name == 'Location' else default

            def read1(self, n):
                chunk, self.body = self.body[:n], self.body[n:]
                return chunk

        class Connection:
            def __init__(self, host, port, timeout=None):
                self.host, self.port = host, port

            def request(self, method, path, headers):
                url = 'https://%s%s' % (self.host, path)
                test.sent.append((url, headers.get('Authorization')))
                self.url = url

            def getresponse(self):
                if self.url in test.redirects:
                    return Response(302, test.redirects[self.url])
                return Response(200)

            def close(self):
                pass

        # A public address, no real socket or TLS, and Connection in place of http.client's.
        for target, name, value in [(_images, '_resolve', lambda host, port, timeout: [(2, 1, 6, '', ('93.184.216.34', port))]),
                                    (_images.socket, 'create_connection', lambda *a, **k: Mock()),
                                    (_images.ssl, 'create_default_context', lambda: Mock()),
                                    (_images.http.client, 'HTTPConnection', Connection)]:
            mock = patch.object(target, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_artwork_in_the_repository_gets_the_login(self):
        self.assertEqual(_images.get(PRIVATE + 'icons/a%20b.png'), PNG)
        self.assertEqual(self.sent, [(PRIVATE + 'icons/a%20b.png', basic(USER, PASSWORD))])

    def test_paths_a_server_could_normalise_outside_the_repository_get_nothing(self):
        for url in TRAVERSALS:
            with self.subTest(url=url):
                self.sent.clear()
                self.assertEqual(_images.get(url), PNG)
                self.assertEqual(self.sent, [(url, None)])
                self.assertIsNone(_credentials.for_url(url))

    def test_redirect_to_a_traversal_gets_nothing(self):
        start = PRIVATE + 'icons/a.png'
        self.redirects[start] = PRIVATE + '%2e%2e/%2e%2e/evil/collect.png'
        self.assertEqual(_images.get(start), PNG)
        self.assertEqual(self.sent, [(start, basic(USER, PASSWORD)), (self.redirects[start], None)])


class ScopedHandler(Base):
    """Handler(scoped=True), for callers (artwork-like) that must stay inside a scope, redirects included."""

    def route(self, url, auth):
        if url == PRIVATE + 'icons/a.png':
            return 302, {'Location': PRIVATE + '%2e%2e/%2e%2e/evil/collect.png'}, b''
        return 200, {}, PNG

    def test_redirect_into_a_traversal_is_stripped(self):
        login = _credentials.basic(PRIVATE, USER, PASSWORD)
        opener = urllib.request.build_opener(_credentials.Handler(login, scoped=True))
        with opener.open(PRIVATE + 'icons/a.png') as r:
            self.assertEqual(r.read(), PNG)
        self.assertEqual(self.web.seen, [(PRIVATE + 'icons/a.png', basic(USER, PASSWORD)),
                                         (PRIVATE + '%2e%2e/%2e%2e/evil/collect.png', None)])
        for url in TRAVERSALS:
            self.assertFalse(_credentials.in_scope(login, url), url)
        self.assertTrue(_credentials.in_scope(login, PRIVATE + 'a/b%20c.png?x=1'))
        self.assertTrue(_credentials.in_scope(login, PRIVATE.rstrip('/')))


CHURN = '''
import sys
sys.path.insert(0, sys.argv[1])
from apk_sources import _credentials
for i in range(int(sys.argv[3])):
    key = sys.argv[2] + str(i)
    _credentials.put(key, _credentials.basic('https://h.example/', 'u', 'p'))
    if i % 2:
        _credentials.remove(key)
'''


class TwoProcesses(Base):
    def test_interleaved_saves_and_removals_are_not_lost(self):
        ui = str(Path(__file__).resolve().parents[1] / 'ui')
        env = dict(os.environ, FRAME_CONTROL_DATA_DIR=str(self.root / 'data'))
        count = 60
        procs = [subprocess.Popen([sys.executable, '-c', CHURN, ui, prefix, str(count)], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for prefix in ('a', 'b')]
        for p in procs:
            out, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, err.decode())
        saved = set(json.loads(self.credentials_file().read_text()))
        self.assertEqual(saved, {p + str(i) for p in 'ab' for i in range(0, count, 2)})
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(self.credentials_file().stat().st_mode), 0o600)


@unittest.skipUnless(shutil.which('node'), 'needs node')
class PageLogin(unittest.TestCase):
    def test_login_leaves_the_address_field_before_sending(self):
        """tests/page/source_login.mjs runs the real page functions from index.html."""
        r = subprocess.run(['node', str(Path(__file__).parent / 'page' / 'source_login.mjs')],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('ok', r.stdout)


class Endpoints(Repository):
    """The server API: logins in, never out, in responses or the server log."""

    def setUp(self):
        super().setUp()
        mock = patch.object(search, 'modules', return_value=([fdroid, github], []))
        mock.start()
        self.addCleanup(mock.stop)
        self.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, method, path, body=None):
        c = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port)
        c.request(method, path, json.dumps(body) if body is not None else None,
                  {'X-Frame-UI': '1', 'Content-Type': 'application/json'})
        r = c.getresponse()
        raw = r.read().decode()
        c.close()
        self.replies.append(raw)
        return r.status, json.loads(raw)

    def job(self, reply):
        for _ in range(500):
            job = self.request('GET', '/api/job?id=' + reply['job'])[1]
            if job['done']:
                return job
            time.sleep(.01)
        self.fail('job did not finish')

    def test_add_with_login_and_token_settings(self):
        self.replies = []
        bad = self.job(self.request('POST', '/api/sources', {'action': 'add', 'url': REPO, 'fingerprint': PIN,
                                                             'username': USER, 'password': 'wrong'})[1])
        self.assertIn('check the username and password', bad['error'])
        self.assertEqual(fdroid.user_repos(), [])
        code, reply = self.request('POST', '/api/sources', {'action': 'add', 'url': REPO, 'fingerprint': PIN,
                                                            'username': USER, 'password': PASSWORD})
        self.assertEqual(code, 200)
        job = self.job(reply)
        self.assertIsNone(job['error'])
        listed = self.request('GET', '/api/sources')[1]['sources']
        repo = next(s for s in listed if s['id'] == job['result']['source']['id'])
        self.assertEqual((repo['url'], repo['login']), (REPO, True))
        self.assertEqual(self.request('POST', '/api/sources', {'action': 'set-token', 'source': 'github',
                                                               'token': TOKEN})[0], 200)
        github_row = next(s for s in self.request('GET', '/api/sources')[1]['sources'] if s['id'] == 'github')
        self.assertEqual(github_row['token'], {'set': True, 'from': 'saved', 'rejected': False})
        self.assertEqual(self.request('POST', '/api/sources', {'action': 'set-token', 'source': 'fdroid',
                                                               'token': TOKEN})[0], 400)
        self.assertEqual(self.request('POST', '/api/sources', {'action': 'clear-token', 'source': 'github'})[0], 200)
        self.assertFalse(_credentials.has('github'))
        self.assertEqual(self.request('POST', '/api/sources', {'action': 'remove', 'source': repo['id']})[0], 200)
        self.assertFalse(self.credentials_file().exists())
        self.assertNoSecrets(*self.replies, self.stderr.getvalue(), self.disk())

    def test_login_in_the_url_is_accepted(self):
        self.replies = []
        url = 'https://alice:s3cr%40t-p%C3%A4ssword@repo.example/fdroid/repo'
        job = self.job(self.request('POST', '/api/sources', {'action': 'add', 'url': url, 'fingerprint': PIN})[1])
        self.assertIsNone(job['error'])
        self.assertEqual(fdroid.user_repos()[0]['url'], REPO)
        self.assertNoSecrets(*self.replies, self.stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
