"""My itch.io purchases: the account key, owned games and their Android downloads.

Offline: a fake HTTPS layer under urllib's real opener (so redirects and header
handling are the real ones) serves the recorded JSON in fixtures/itch_account.
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import contextlib, email.message, http.client, io, json, os, sys, tempfile, threading, unittest
import urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
from apk_sources import SourceError, SourceLimited, _itch_account as account, _web, itch, search
import server

FIX = Path(__file__).parent / 'fixtures' / 'itch_account'
KEY = 'TESTKEYabcdefghijklmnopqrstuvwxyz0123456789'
OTHER = 'OTHERKEY0123456789abcdefghijklmnopqrstuv'


def apk_bytes():
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr('AndroidManifest.xml', b'\x03\x00\x08\x00')
        z.writestr('classes.dex', b'dex\n035\x00')
    return out.getvalue()


class Reply(io.BytesIO):
    """Just enough of http.client.HTTPResponse for urllib's handlers."""

    def __init__(self, url, code=200, body=b'', headers=None):
        super().__init__(body if isinstance(body, bytes) else json.dumps(body).encode())
        self.url, self.code, self.status, self.msg, self.reason = url, code, code, 'fake', 'fake'
        self.headers = email.message.Message()
        for k, v in (headers or {}).items():
            self.headers[k] = v

    def info(self):
        return self.headers

    def geturl(self):
        return self.url

    def getcode(self):
        return self.code


class FakeItch:
    """Routes https requests by host and path; records every request with its headers."""

    def __init__(self):
        self.calls, self.routes = [], {}

    def route(self, host_path, reply):
        self.routes[host_path] = reply

    def __call__(self, handler, req):
        url = urllib.parse.urlsplit(req.full_url)
        headers = {k.lower(): v for k, v in req.header_items()}
        self.calls.append((req.full_url, headers))
        reply = self.routes.get(url.hostname + url.path)
        if reply is None:
            return Reply(req.full_url, 404, {'errors': ['not found']})
        if callable(reply):
            reply = reply(req, urllib.parse.parse_qs(url.query))
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, Reply):
            return reply
        return Reply(req.full_url, 200, reply)

    def urls(self, host_path):
        return [u for u, _ in self.calls if urllib.parse.urlsplit(u).hostname + urllib.parse.urlsplit(u).path == host_path]


def owned_pages(req, query):
    page = query['page'][0]
    return {'1': json.loads((FIX / 'owned-keys-1.json').read_text()),
            '2': json.loads((FIX / 'owned-keys-2.json').read_text())}.get(page, {'page': int(page), 'owned_keys': []})


class ItchPurchases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for target, value in [(account.frame_host, 'data_dir'), (search.frame_host, 'data_dir')]:
            p = patch.object(target, value, lambda *parts: root.joinpath('data', *parts))
            p.start()
            self.addCleanup(p.stop)
        (root / 'cache').mkdir()
        for p in (patch.object(_web, 'cache', return_value=str(root / 'cache')),
                  patch.object(_web.frame_host, 'cache_dir', lambda *parts: root.joinpath('cache', *parts))):
            p.start()
            self.addCleanup(p.stop)
        self.web = FakeItch()
        self.web.route('api.itch.io/profile', {'user': {'username': 'player', 'id': 1}})
        self.web.route('api.itch.io/profile/owned-keys', owned_pages)
        self.web.route('api.itch.io/games/341190/uploads', json.loads((FIX / 'uploads.json').read_text()))
        p = patch('urllib.request.HTTPSHandler.https_open', autospec=True, side_effect=self.web)
        p.start()
        self.addCleanup(p.stop)
        p = patch('urllib.request.HTTPHandler.http_open', side_effect=AssertionError('plain HTTP in test'))
        p.start()
        self.addCleanup(p.stop)
        account._forget()
        self.addCleanup(account._forget)
        _web._limited.clear()
        self.addCleanup(_web._limited.clear)
        search._status.clear()

    def owned_source(self):
        return next(s for s in itch.sources() if s['id'] == itch.OWNED)

    def connect(self):
        self.assertTrue(account.connect(KEY)['itch']['connected'])

    # -- the key ---------------------------------------------------------------

    def test_connect_checks_the_key_then_saves_it_0600(self):
        result = account.connect('  ' + KEY + '\n')
        self.assertEqual(result['message'], 'Connected to itch.io as player')
        self.assertEqual(result['itch'], {'connected': True, 'username': 'player'})
        self.assertNotIn(KEY, json.dumps(result))
        url, headers = self.web.calls[0]
        self.assertEqual(url, 'https://api.itch.io/profile')
        self.assertEqual(headers['authorization'], 'Bearer ' + KEY)
        self.assertEqual(json.loads(account.path().read_text())['key'], KEY)
        if os.name == 'posix':
            self.assertEqual(os.stat(account.path()).st_mode & 0o777, 0o600)
        self.assertEqual([p.name for p in account.path().parent.iterdir()], ['itch-account.json'])  # no .tmp left
        self.assertNotIn(KEY, json.dumps(account.status()))

    def test_reconnecting_rewrites_the_file_0600_even_if_it_was_wider(self):
        self.connect()
        os.chmod(account.path(), 0o644)
        account.connect(OTHER)
        self.assertEqual(json.loads(account.path().read_text())['key'], OTHER)
        if os.name == 'posix':
            self.assertEqual(os.stat(account.path()).st_mode & 0o777, 0o600)

    def test_bad_or_revoked_key_stays_disconnected(self):
        for reply in (Reply('https://api.itch.io/profile', 401, {'errors': ['invalid key']}),
                      Reply('https://api.itch.io/profile', 403, b'Forbidden'),
                      {'errors': ['invalid key']}):
            self.web.route('api.itch.io/profile', reply)
            with self.assertRaisesRegex(account.BadKey, 'did not accept the API key') as caught:
                account.connect(KEY)
            self.assertNotIn(KEY, str(caught.exception))
            self.assertFalse(account.path().exists())
            self.assertEqual(account.status(), {'connected': False, 'username': None})
            self.assertEqual([s['id'] for s in itch.sources()], ['itch', 'itch-quest'])
        with self.assertRaisesRegex(account.BadKey, 'does not look like'):
            account.connect('short')
        with self.assertRaisesRegex(account.BadKey, 'does not look like'):
            account.connect(KEY + '\r\nX-Injected: 1')
        self.assertEqual(len(self.web.calls), 3)  # malformed keys never reach itch.io

    def test_a_key_revoked_later_is_removed_with_a_clear_message(self):
        self.connect()
        self.web.route('api.itch.io/profile/owned-keys', Reply('https://api.itch.io/profile/owned-keys', 401, b''))
        with self.assertRaisesRegex(account.BadKey, 'no longer accepts the saved API key'):
            itch.search(self.owned_source(), '')
        self.assertFalse(account.path().exists())
        self.assertNotIn(itch.OWNED, [s['id'] for s in itch.sources()])

    def test_disconnect_deletes_the_key_file(self):
        self.connect()
        self.assertIn(itch.OWNED, [s['id'] for s in itch.sources()])
        result = account.disconnect()
        self.assertFalse(account.path().exists())
        self.assertEqual(result['itch'], {'connected': False, 'username': None})
        self.assertNotIn(itch.OWNED, [s['id'] for s in itch.sources()])
        with self.assertRaisesRegex(SourceError, 'Connect your itch.io account first'):
            account.owned_keys()
        account.disconnect()  # already gone: fine

    # -- owned games -------------------------------------------------------------

    def test_owned_keys_follow_pages_until_an_empty_one(self):
        self.connect()
        keys = account.owned_keys()
        self.assertEqual([k['id'] for k in keys], [9001, 9002, 8001, 8002])
        pages = self.web.urls('api.itch.io/profile/owned-keys')
        self.assertEqual([urllib.parse.parse_qs(urllib.parse.urlsplit(u).query) for u in pages],
                         [{'page': [str(n)], 'per_page': ['500']} for n in (1, 2, 3)])
        self.assertTrue(all('Bearer ' + KEY == h['authorization'] for _, h in self.web.calls))
        self.assertTrue(all(KEY not in u for u, _ in self.web.calls))
        account.owned_keys()  # cached in memory, not on disk
        self.assertEqual(len(self.web.urls('api.itch.io/profile/owned-keys')), 3)
        self.assertFalse(any(KEY in p.read_text(errors='ignore') or b'Orbit' in p.read_bytes()
                             for p in Path(_web.cache()).iterdir()))

    def test_page_cap_stops_a_server_that_never_ends(self):
        self.connect()
        self.web.route('api.itch.io/profile/owned-keys', lambda req, q: {'owned_keys': [{'id': int(q['page'][0])}]})
        with patch.object(account, 'PAGES', 3):
            self.assertEqual(len(account.owned_keys()), 3)

    def test_search_lists_owned_android_games_labelled(self):
        self.connect()
        entries = itch.search(self.owned_source(), '')
        self.assertEqual([(e['id'], e['name']) for e in entries], [('341190', 'Orbit Garden VR'), ('77', 'Free Quest Toy')])
        orbit, toy = entries
        self.assertEqual(orbit['download_key_id'], 9001)  # the newest key for a game owned twice
        self.assertTrue(orbit['owned'])
        self.assertEqual(orbit['owned_label'], 'Owned on itch.io')
        self.assertFalse(orbit['free'])
        self.assertTrue(toy['free'])
        self.assertIsNone(toy['icon'])  # not an itch.io image host
        self.assertEqual(orbit['page'], 'https://maker.itch.io/orbit-garden')
        self.assertEqual(itch.search(self.owned_source(), 'zero gravity')[0]['id'], '341190')
        # Through the store's search, owned (paid) games pass the free-only filter.
        result = search.search('orbit', source=itch.OWNED)
        self.assertEqual(result['sources'][0]['status'], 'ok')
        offer = result['apps'][0]['offers'][0]
        self.assertEqual((offer['source'], offer['source_name'], offer['owned_label']),
                         (itch.OWNED, 'itch.io (my purchases)', 'Owned on itch.io'))
        self.assertNotIn(KEY, json.dumps(result))

    def test_only_the_account_source_may_mark_paid_games_owned(self):
        entry = {'free': False, 'owned': True}
        self.assertFalse(search.obtainable({'id': 'fdroid'}, entry))
        self.assertTrue(search.obtainable({'id': itch.OWNED, 'owned': True}, entry))
        self.assertTrue(search.obtainable({'id': 'fdroid'}, {'free': True}))

    def test_android_upload_selection(self):
        uploads = json.loads((FIX / 'uploads.json').read_text())['uploads']
        # .apk files before other Android files, full games before demos, newest first; never
        # soundtracks, externally hosted files or other platforms.
        self.assertEqual([u['id'] for u in account.android_uploads(uploads)], [503, 502, 504, 505])
        self.assertTrue(account.is_android({'filename': 'Game.APK'}))
        self.assertTrue(account.is_android({'filename': 'game.zip', 'p_android': True}))
        self.assertTrue(account.is_android({'filename': 'game.zip', 'platforms': {'android': 'all'}}))
        self.assertFalse(account.is_android({'filename': 'game.zip', 'traits': ['p_windows']}))
        self.assertEqual(account.android_uploads({'not': 'a list'}), [])

    def test_details_offer_the_android_uploads(self):
        self.connect()
        entry = itch.details(self.owned_source(), '341190')
        self.assertTrue(entry['downloadable'])
        self.assertEqual([v['upload_id'] for v in entry['versions']], [503, 502, 504, 505])
        self.assertEqual((entry['version'], entry['size'], entry['updated']), ('Quest 1.2', 115343360, '2026-04-03'))
        self.assertTrue(entry['versions'][2]['demo'])
        url = self.web.urls('api.itch.io/games/341190/uploads')[0]
        self.assertEqual(url, 'https://api.itch.io/games/341190/uploads?download_key_id=9001')
        with self.assertRaisesRegex(SourceError, 'not among'):
            itch.details(self.owned_source(), '3')  # owned, but not for Android
        self.web.route('api.itch.io/games/77/uploads', {'uploads': []})
        self.assertFalse(itch.details(self.owned_source(), '77')['downloadable'])
        with self.assertRaisesRegex(SourceError, 'no Android download'):
            itch.download(self.owned_source(), '77')

    def test_download_url_building(self):
        self.assertEqual(account.download_url(503, 9001),
                         'https://api.itch.io/uploads/503/download?download_key_id=9001')
        for bad in [(0, 1), (1, None), ('5', 1), (True, 1), (-2, 1)]:
            with self.assertRaises(SourceError):
                account.download_url(*bad)

    # -- downloads -----------------------------------------------------------------

    def storage(self, location='https://storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk?sig=abc'):
        self.web.route('api.itch.io/uploads/503/download',
                       Reply('https://api.itch.io/uploads/503/download', 302, b'', {'Location': location}))
        self.web.route('storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk', Reply(location, 200, apk_bytes()))

    def test_download_sends_the_key_to_itch_only_and_strips_it_on_redirect(self):
        self.connect()
        self.storage()
        result = itch.download(self.owned_source(), '341190')
        self.assertTrue(os.path.isfile(result['apk']))
        self.assertFalse(result['verified'])
        api, cdn = self.web.calls[-2:]
        self.assertEqual(api[0], 'https://api.itch.io/uploads/503/download?download_key_id=9001')
        self.assertEqual(api[1]['authorization'], 'Bearer ' + KEY)
        self.assertTrue(cdn[0].startswith('https://storage.itch-cdn.example/'))
        self.assertNotIn('authorization', cdn[1])
        self.assertTrue(all(KEY not in u for u, _ in self.web.calls))
        with self.assertRaisesRegex(SourceError, 'version codes'):
            itch.download(self.owned_source(), '341190', version_code=3)

    def test_redirects_to_plain_http_or_addresses_are_refused(self):
        self.connect()
        for location in ('http://storage.itch-cdn.example/a.apk', 'https://127.0.0.1/a.apk',
                         'https://[::1]/a.apk', 'https://localhost/a.apk', 'https://user:pw@cdn.example/a.apk',
                         'https://cdn.example:8443/a.apk'):
            self.storage(location)
            with self.assertRaisesRegex(SourceError, 'unexpected download URL'):
                itch.download(self.owned_source(), '341190')
        self.assertEqual({urllib.parse.urlsplit(u).hostname for u, _ in self.web.calls}, {'api.itch.io'})

    def test_existing_hosts_still_strip_authorization_on_redirect(self):
        req = urllib.request.Request('https://api.github.com/a', headers={'Authorization': 'Bearer x'})
        nxt = _web.Redirect(('api.github.com',)).redirect_request(req, None, 302, 'Found', {}, 'https://api.github.com/b')
        self.assertFalse(nxt.has_header('Authorization'))
        with self.assertRaises(SourceError):
            _web.Redirect(('api.github.com',)).redirect_request(req, None, 302, 'Found', {}, 'https://evil.example/b')

    def test_install_uses_the_normal_apk_install_path(self):
        import frame_android
        self.connect()
        self.storage()
        calls = []

        def install(apk_path, flatscreen=None, name=None, source=None, icon_png=None, xr_compat=None, artwork=None):
            with zipfile.ZipFile(apk_path) as z:
                self.assertIn('AndroidManifest.xml', z.namelist())
            calls.append((name, source))
            return {'package': 'com.maker.orbit', 'message': 'Installed'}
        with patch.object(frame_android, 'install', install):
            result = search.install(itch.OWNED, '341190')
        self.assertEqual(calls, [('Orbit Garden VR', 'itch.io (my purchases)')])
        self.assertEqual(result['package'], 'com.maker.orbit')

    # -- errors never carry the key ------------------------------------------------

    def test_errors_are_readable_and_never_contain_the_key(self):
        self.connect()
        cases = [
            (Reply('https://api.itch.io/profile/owned-keys', 429, b'', {'Retry-After': '120'}),
             SourceLimited, '^itch.io is limiting requests; try again in 2 minutes$'),
            (Reply('https://api.itch.io/profile/owned-keys', 503, b''), SourceError, 'HTTP error 503; try again later'),
            (urllib.error.URLError('connect to api.itch.io with ' + KEY + ' failed'), SourceError,
             r'^Could not reach itch.io: connect to api.itch.io with \[API key\] failed$'),
            (OSError('timed out'), SourceError, '^Could not reach itch.io: timed out$'),
            (Reply('https://api.itch.io/profile/owned-keys', 200, b'<html>'), SourceError, 'invalid response'),
            ({'errors': ['echo ' + KEY]}, SourceError, r'^itch.io: echo \[API key\]$'),
        ]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            for reply, kind, message in cases:
                account._forget()
                _web._limited.clear()
                self.web.route('api.itch.io/profile/owned-keys', reply)
                with self.assertRaisesRegex(kind, message) as caught:
                    account.owned_keys()
                self.assertNotIn(KEY, str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)
                self.assertTrue(account.connected())  # not the key's fault: stays connected
            # The store's search reports the failure as a non-fatal source status.
            account._forget()
            result = search.search('', source=itch.OWNED)
        self.assertEqual(result['sources'][0]['status'], 'error')
        self.assertNotIn(KEY, json.dumps(result) + stderr.getvalue())

    def test_server_api_connects_and_never_echoes_the_key(self):
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        def request(method, path, body=None):
            c = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
            c.request(method, path, json.dumps(body) if body is not None else None,
                      {'X-Frame-UI': '1', 'Content-Type': 'application/json'})
            r = c.getresponse()
            out = r.status, r.read().decode()
            c.close()
            return out
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.web.route('api.itch.io/profile', Reply('https://api.itch.io/profile', 401, b''))
            bad = request('POST', '/api/sources', {'action': 'itch-connect', 'key': KEY})
            self.web.route('api.itch.io/profile', {'user': {'username': 'player'}})
            good = request('POST', '/api/sources', {'action': 'itch-connect', 'key': KEY})
            listed = request('GET', '/api/sources')
            empty = request('POST', '/api/sources', {'action': 'itch-connect', 'key': ' '})
            gone = request('POST', '/api/sources', {'action': 'itch-disconnect'})
        self.assertEqual(bad[0], 400)
        self.assertIn('did not accept the API key', json.loads(bad[1])['error'])
        self.assertEqual(good[0], 200)
        self.assertEqual(json.loads(good[1])['itch'], {'connected': True, 'username': 'player'})
        self.assertEqual(json.loads(listed[1])['itch'], {'connected': True, 'username': 'player'})
        self.assertIn(itch.OWNED, [s['id'] for s in json.loads(listed[1])['sources']])
        self.assertEqual(empty[0], 400)
        self.assertEqual(json.loads(gone[1])['itch'], {'connected': False, 'username': None})
        self.assertFalse(account.path().exists())
        for text in (bad[1], good[1], listed[1], empty[1], gone[1], stderr.getvalue()):
            self.assertNotIn(KEY, text)


if __name__ == '__main__':
    unittest.main()
