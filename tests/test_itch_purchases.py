"""My itch.io purchases: the account key, owned games and their Android downloads.

Offline: a fake HTTPS layer under urllib's real opener (so redirects and header
handling are the real ones) serves the recorded JSON in fixtures/itch_account.
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import contextlib, email.message, http.client, io, ipaddress, json, os, socket, sys, tempfile, threading, time
import unittest
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

    def getheader(self, name, default=None):
        return self.headers.get(name, default)


class FakeConnection:
    """_web._connect's http.client connection, answered from the same routes."""

    def __init__(self, web, host):
        self.web, self.host, self.reply = web, host, None

    def request(self, method, path, headers=None):
        req = urllib.request.Request('https://' + self.host + path, headers=headers or {})
        self.reply = self.web(None, req)

    def getresponse(self):
        return self.reply

    def close(self):
        pass


# What the fake resolver answers: the storage host is public; the rest are traps.
ADDRESSES = {'storage.itch-cdn.example': '151.101.1.1', 'other-cdn.example': '151.101.2.2',
             'localhost.': '127.0.0.1', 'frame.local': '192.168.1.20', '127.0.0x0.1': '127.0.0.1',
             'intranet.example': '10.0.0.5', 'mapped.example': '::ffff:127.0.0.1', 'cgnat.example': '100.64.0.1',
             'mixed.example': ('151.101.1.1', '10.0.0.5'), 'dual.example': ('2a04:4e42::81', '151.101.1.1'),
             'nat64.example': '64:ff9b:1::a00:1', 'sitelocal.example': 'fec0::1',
             'many.example': tuple('151.101.%d.1' % n for n in range(1, 9))}
REAL_CONNECT = _web._connect


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
        real_lookup = _web.socket.getaddrinfo

        def lookup(host, port, *args, **kwargs):
            if host not in ADDRESSES:
                try:
                    ipaddress.ip_address(host)  # IP literals (and the in-process test server) need no DNS
                    return real_lookup(host, port, *args, **kwargs)
                except ValueError:
                    pass
                if host == 'localhost':
                    return real_lookup(host, port, *args, **kwargs)
                raise _web.socket.gaierror('unknown test host ' + host)
            found = ADDRESSES[host]
            return [(10 if ':' in a else 2, 1, 6, '', (a, port)) for a in ([found] if isinstance(found, str) else found)]
        self.connected, self.unreachable = [], set()

        def connect(host, address, timeout, deadline):
            self.connected.append((host, address))
            if address[0] in self.unreachable:
                raise OSError('Network is unreachable')
            self.assertLessEqual(deadline - time.monotonic(), _web.CONNECT_BUDGET)
            return FakeConnection(self.web, host)
        for p in (patch.object(_web.socket, 'getaddrinfo', lookup), patch.object(_web, '_connect', connect)):
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

    def test_a_refused_request_with_a_working_key_keeps_the_key(self):
        self.connect()
        self.web.route('api.itch.io/games/341190/uploads', Reply('https://api.itch.io/games/341190/uploads', 403, b''))
        with self.assertRaisesRegex(SourceError, r'refused this request \(HTTP 403\)') as caught:
            itch.details(self.owned_source(), '341190')
        self.assertNotIsInstance(caught.exception, account.BadKey)
        self.assertTrue(account.connected())

    def test_a_key_revoked_later_is_removed_with_a_clear_message(self):
        self.connect()
        self.web.route('api.itch.io/profile/owned-keys', Reply('https://api.itch.io/profile/owned-keys', 401, b''))
        self.web.route('api.itch.io/profile', Reply('https://api.itch.io/profile', 401, b''))
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

    def test_owned_games_show_under_either_vr_choice(self):
        # itch.io doesn't say which purchases are VR, so neither filter hides them; other
        # games of unknown kind still count as flat.
        self.connect()
        both = ['Free Quest Toy', 'Orbit Garden VR']
        for vr in (True, False):
            names = sorted(a['name'] for a in search.search('', vr=vr, source=itch.OWNED)['apps'])
            self.assertEqual(names, both)
        flat = {'source': 'x', 'id': '1', 'name': 'Flat', 'summary': '', 'vr': None}
        self.assertEqual(search.group([flat], vr=True), [])
        self.assertEqual(len(search.group([flat], vr=False)), 1)
        self.assertEqual(search.group([dict(flat, owned=True, vr=False)], vr=True), [])

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
        # Connected to the address that was checked, not to a fresh lookup.
        self.assertEqual(self.connected, [('storage.itch-cdn.example', ('151.101.1.1', 443))])
        self.assertTrue(all(KEY not in u for u, _ in self.web.calls))
        with self.assertRaisesRegex(SourceError, 'version codes'):
            itch.download(self.owned_source(), '341190', version_code=3)

    def test_download_also_accepts_a_json_url_or_the_file_itself(self):
        self.connect()
        self.storage()
        location = 'https://storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk?sig=abc'
        self.web.route('api.itch.io/uploads/503/download',
                       Reply('https://api.itch.io/uploads/503/download', 200, {'url': location},
                             {'Content-Type': 'application/json'}))
        self.assertTrue(os.path.isfile(itch.download(self.owned_source(), '341190')['apk']))
        self.assertNotIn('authorization', self.web.calls[-1][1])
        self.web.route('api.itch.io/uploads/503/download',
                       Reply('https://api.itch.io/uploads/503/download', 200, apk_bytes(),
                             {'Content-Type': 'application/octet-stream'}))
        self.connected.clear()
        self.assertTrue(os.path.isfile(itch.download(self.owned_source(), '341190')['apk']))
        self.assertEqual(self.connected, [])  # api.itch.io served it; no storage host involved
        self.web.route('api.itch.io/uploads/503/download',
                       Reply('https://api.itch.io/uploads/503/download', 200, {'nothing': 1},
                             {'Content-Type': 'application/json'}))
        with self.assertRaisesRegex(SourceError, 'did not say where'):
            itch.download(self.owned_source(), '341190')

    def test_storage_redirects_are_checked_on_every_hop(self):
        self.connect()
        self.storage('https://other-cdn.example/hop')
        self.web.route('other-cdn.example/hop', Reply('https://other-cdn.example/hop', 302, b'',
                                                      {'Location': 'https://storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk'}))
        self.assertTrue(os.path.isfile(itch.download(self.owned_source(), '341190')['apk']))
        self.assertEqual([h for h, _ in self.connected], ['other-cdn.example', 'storage.itch-cdn.example'])
        self.web.route('other-cdn.example/hop', Reply('https://other-cdn.example/hop', 302, b'',
                                                      {'Location': 'https://intranet.example/a.apk'}))
        with self.assertRaisesRegex(SourceError, 'private network address'):
            itch.download(self.owned_source(), '341190')

    def test_redirects_to_plain_http_or_private_addresses_are_refused(self):
        self.connect()
        for location in ('http://storage.itch-cdn.example/a.apk', 'https://user:pw@cdn.example/a.apk',
                         'https://cdn.example:8443/a.apk'):
            self.storage(location)
            with self.assertRaisesRegex(SourceError, 'unexpected download URL'):
                itch.download(self.owned_source(), '341190')
        for location in ('https://localhost./a.apk', 'https://frame.local/a.apk', 'https://127.0.0x0.1/a.apk',
                         'https://intranet.example/a.apk', 'https://mapped.example/a.apk',
                         'https://cgnat.example/a.apk', 'https://mixed.example/a.apk',
                         'https://127.0.0.1/a.apk', 'https://[::1]/a.apk', 'https://169.254.169.254/a.apk',
                         'https://nat64.example/a.apk', 'https://[4000::1]/a.apk', 'https://[64:ff9b:1::a00:1]/a.apk',
                         'https://[fec0::1]/a.apk', 'https://sitelocal.example/a.apk'):
            self.storage(location)
            with self.assertRaisesRegex(SourceError, 'private network address'):
                itch.download(self.owned_source(), '341190')
        self.assertEqual(self.connected, [])
        self.assertEqual({urllib.parse.urlsplit(u).hostname for u, _ in self.web.calls}, {'api.itch.io'})

    def test_public_address_rules(self):
        for ip in ('151.101.1.1', '8.8.8.8', '2a04:4e42::81', '2001:4860:4860::8888'):
            self.assertTrue(_web.public_address(ip), ip)
        for ip in ('127.0.0.1', '10.1.2.3', '172.16.0.1', '192.168.0.1', '169.254.169.254', '100.64.0.1',
                   '0.0.0.0', '224.0.0.1', '255.255.255.255', '240.0.0.1', '::1', '::', 'fe80::1%en0', 'fc00::1',
                   'ff02::1', 'not an ip',
                   '192.0.0.8', '192.0.0.11', '192.0.0.255', '192.0.0.170', '192.0.0.9', '192.0.0.1',  # 3.9: global
                   '192.0.2.1', '192.88.99.1', '198.18.0.1', '198.19.255.255', '198.51.100.7', '203.0.113.9',
                   '0.1.2.3', '10.255.255.255', '172.31.0.1', '239.1.1.1', '254.0.0.1',
                   '4000::1', '100::1', 'f000::1',  # reserved: Python 3.9's is_global says True for 4000::1
                   '::ffff:10.0.0.1', '::ffff:127.0.0.1', '::ffff:8.8.8.8',  # IPv4-mapped
                   '::a00:1', '::8.8.8.8',  # IPv4-compatible
                   '64:ff9b::a00:1', '64:ff9b::808:808',  # NAT64 well-known prefix
                   '64:ff9b:1::a00:1', '64:ff9b:1::808:808',  # NAT64 local-use: 3.9's is_global says True
                   '2002:a00:1::1', '2002:808:808::1',  # 6to4
                   '2001:0:4136:e378:8000:63bf:3fff:fdd2',  # Teredo
                   'fec0::1', 'feff::1',  # site-local: Python 3.9's is_global says True
                   'fc00::1', 'fd12:3456::1', 'fe80::1', 'ff00::1', 'ff0e::1', '8000::1', 'c000::1',
                   '2001:db8::1', '3fff::1',  # documentation
                   '2001:10::1', '2001:20::1', '2001:2::1'):  # ORCHID, ORCHIDv2, benchmarking
            self.assertFalse(_web.public_address(ip), ip)
        self.assertEqual(_web.resolve_public('storage.itch-cdn.example'), [('151.101.1.1', 443)])
        self.assertEqual(_web.resolve_public('dual.example'), [('2a04:4e42::81', 443), ('151.101.1.1', 443)])

    def test_a_storage_url_carrying_the_key_is_refused(self):
        self.connect()
        for location in ('https://storage.itch-cdn.example/a.apk?api_key=' + KEY,
                         'https://storage.itch-cdn.example/a.apk?API_KEY=someone-elses',
                         'https://storage.itch-cdn.example/a.apk?apikey=x',
                         'https://storage.itch-cdn.example/' + KEY + '/a.apk',
                         'https://storage.itch-cdn.example/a.apk#' + KEY[:10],
                         'https://storage.itch-cdn.example/a.apk?x=' + urllib.parse.quote('%' + KEY),
                         'https://' + KEY.lower() + '.itch-cdn.example/a.apk'):
            self.storage(location)
            with self.assertRaisesRegex(SourceError, 'carrying your API key; refused') as caught:
                itch.download(self.owned_source(), '341190')
            self.assertNotIn(KEY.lower(), str(caught.exception).lower())
        self.web.route('api.itch.io/uploads/503/download',
                       Reply('https://api.itch.io/uploads/503/download', 200,
                             {'url': 'https://storage.itch-cdn.example/a.apk?api_key=' + KEY},
                             {'Content-Type': 'application/json'}))
        with self.assertRaisesRegex(SourceError, 'carrying your API key; refused'):
            itch.download(self.owned_source(), '341190')
        self.assertEqual(self.connected, [])
        # A storage URL's own signature or token parameters are fine.
        self.storage('https://storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk?token=abc&Signature=x')
        self.assertTrue(os.path.isfile(itch.download(self.owned_source(), '341190')['apk']))

    def test_a_later_redirect_carrying_the_key_is_refused_before_connecting(self):
        self.connect()
        bad = 'https://storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk?api_key=' + KEY
        for hops in (['https://other-cdn.example/hop1'],  # 2nd hop carries the key
                     ['https://other-cdn.example/hop1', 'https://other-cdn.example/hop2']):  # 3rd hop
            self.connected.clear()
            self.storage(hops[0])
            for here, there in zip(hops, hops[1:] + [bad]):
                path = urllib.parse.urlsplit(here).path
                self.web.route('other-cdn.example' + path, Reply(here, 302, b'', {'Location': there}))
            with self.assertRaisesRegex(SourceError, 'carrying your API key; refused') as caught:
                itch.download(self.owned_source(), '341190')
            self.assertNotIn(KEY, str(caught.exception))
            self.assertEqual([h for h, _ in self.connected], ['other-cdn.example'] * len(hops))
            self.assertFalse(any(KEY in u for u, _ in self.web.calls))
        # The check runs on every hop before the name is even looked up.
        seen = []
        with patch.object(_web, 'resolve_public', side_effect=AssertionError('looked up')):
            with self.assertRaisesRegex(SourceError, 'no thanks'):
                _web.public_apk('https://storage.itch-cdn.example/a.apk', 'itch.io',
                                check=lambda u: seen.append(u) or (_ for _ in ()).throw(SourceError('no thanks')))
        self.assertEqual(seen, ['https://storage.itch-cdn.example/a.apk'])

    def test_a_partial_match_before_the_key_cannot_hide_its_start(self):
        key = 'abcdefghABCDEFGHi1234567890'
        for text in (key[:8].upper() + key.upper(), key[:9] + key, 'xx' + key[:8] + key + 'yy'):
            out = account._clean(text, key)
            self.assertNotIn('1234567890', out, (text, out))
        import time
        t0 = time.monotonic(); account._clean(('abcdefgh' * 12500)[:100000], key)
        self.assertLess(time.monotonic() - t0, 2.0)

    def test_redaction_catches_every_spelling_of_the_key(self):
        hexed = ''.join('%%%02X' % ord(c) for c in KEY)
        for spelling in (KEY, KEY.lower(), KEY.upper(), hexed, hexed.lower(),
                         KEY[:5] + hexed[15:30] + KEY[10:],  # partly encoded
                         KEY[:9], hexed[:30].lower(),  # starts of it, 8+ characters
                         ''.join('%%%02x' % ord(c) for c in KEY.lower()),  # encoded after a case change
                         ''.join('%%%02X' % ord(c) for c in KEY.swapcase()),
                         '%%%02x' % ord(KEY[0].swapcase()) + KEY[1:]):  # one encoded, recased letter
            cleaned = account._clean('before ' + spelling + ' after', KEY)
            self.assertEqual(cleaned, 'before [API key] after', spelling)
        double = ''.join('%%25%02X' % ord(c) for c in KEY)  # percent-encoded twice
        for spelling in (double, double.lower(), double.upper(), double[:5 * 9],  # full, hex recased, 9-char start
                         ''.join('%%25%02x' % ord(c) for c in KEY.lower()),  # the key recased, then double-encoded
                         KEY[:4] + double[20:45] + hexed[27:33] + KEY[11:]):  # literal, double and single mixed
            self.assertEqual(account._clean('before ' + spelling + ' after', KEY), 'before [API key] after', spelling)
        self.assertEqual(account._clean(double[:5 * 7], KEY), double[:5 * 7])  # 7 characters: kept
        self.assertTrue(account._carries_key('https://cdn.example/a?x=' + double, KEY))
        self.assertTrue(account._carries_key('https://cdn.example/' + double[:5 * 8].lower() + '/a', KEY))
        self.assertEqual(account._clean('TESTKEY is short', KEY), 'TESTKEY is short')  # 7 characters: kept
        self.assertEqual(account._clean(KEY + KEY.lower(), KEY), '[API key][API key]')
        for url in ('https://cdn.example/a?x=' + hexed, 'https://cdn.example/a?x=' + hexed.lower(),
                    'https://cdn.example/' + KEY.upper() + '/a', 'https://cdn.example/a?x=' + urllib.parse.quote_plus(KEY)):
            self.assertTrue(account._carries_key(url, KEY), url)
        self.assertFalse(account._carries_key('https://cdn.example/a?token=abc&Signature=x', KEY))
        # Storage errors carrying an encoded or lowercased key lose it, keeping their kind.
        self.connect()
        self.storage()
        with patch.object(_web, 'public_apk', side_effect=SourceLimited('slow ' + hexed.lower(), 42)):
            with self.assertRaises(SourceLimited) as caught:
                itch.download(self.owned_source(), '341190')
        self.assertEqual((str(caught.exception), caught.exception.retry_after), ('slow [API key]', 42))
        with patch.object(_web, 'public_apk', side_effect=SourceError('host ' + KEY.lower() + '.cdn')):
            with self.assertRaisesRegex(SourceError, r'^host \[API key\]\.cdn$'):
                itch.download(self.owned_source(), '341190')

    def test_storage_errors_lose_the_key_but_keep_their_kind(self):
        self.connect()
        self.storage()
        with patch.object(_web, 'public_apk', side_effect=SourceLimited('slow down ' + KEY, 90)):
            with self.assertRaises(SourceLimited) as caught:
                itch.download(self.owned_source(), '341190')
        self.assertEqual((str(caught.exception), caught.exception.retry_after), ('slow down [API key]', 90))
        with patch.object(_web, 'public_apk', side_effect=SourceError('Could not find the download server ' + KEY)):
            with self.assertRaisesRegex(SourceError, r'^Could not find the download server \[API key\]$') as caught:
                itch.download(self.owned_source(), '341190')
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_broken_http_responses_are_readable_and_lose_the_key(self):
        self.connect()

        class Truncated(Reply):
            def read(self, *args):
                raise http.client.IncompleteRead(b'{"owned_keys": [' + KEY.encode(), 1000)
        cases = [http.client.BadStatusLine('HTTP/1.1 ' + KEY + ' oops'),
                 lambda req, q: Truncated(req.full_url, 200, b''),
                 http.client.RemoteDisconnected('closed after ' + KEY)]
        for case in cases:
            account._forget()
            self.web.route('api.itch.io/profile/owned-keys', case)
            with self.assertRaisesRegex(SourceError, '^Could not reach itch.io: ') as caught:
                account.owned_keys()
            self.assertNotIn(KEY, str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            self.assertTrue(caught.exception.__suppress_context__)
            self.assertTrue(account.connected())
        # The same on the download request, for each kind of answer it reads.
        for case in (http.client.BadStatusLine('HTTP/1.1 ' + KEY),
                     lambda req, q: Truncated(req.full_url, 200, b'', {'Content-Type': 'application/json'}),
                     lambda req, q: Truncated(req.full_url, 200, b'', {'Content-Type': 'application/octet-stream'})):
            self.web.route('api.itch.io/uploads/503/download', case)
            with self.assertRaises(SourceError) as caught:
                account.download(503, 9001)
            self.assertNotIn(KEY, str(caught.exception))
            self.assertRegex(str(caught.exception), '^Could not (reach itch.io|download APK): ')

    def test_connecting_shares_one_deadline_across_addresses(self):
        clock, deadlines = [1000.0], []

        def slow(host, address, timeout, deadline):
            deadlines.append(deadline)
            clock[0] += 7  # each address hangs for 7 s before failing
            raise socket.timeout('timed out')
        with patch.object(_web.time, 'monotonic', lambda: clock[0]), patch.object(_web, '_connect', slow):
            with self.assertRaises(OSError):
                _web._public_connection('many.example', 60)
        self.assertEqual(len(set(deadlines)), 1)  # one deadline for every attempt
        self.assertEqual(deadlines[0], 1000.0 + _web.CONNECT_BUDGET)
        self.assertEqual(len(deadlines), 3)  # 8 addresses, but only 21 s of trying, not 56
        self.assertLessEqual(clock[0] - 1000.0, _web.CONNECT_BUDGET + 7)
        deadlines.clear()
        clock[0] = 1000.0
        with patch.object(_web.time, 'monotonic', lambda: clock[0]), patch.object(_web, '_connect', slow):
            with self.assertRaises(OSError):
                _web._public_connection('many.example', 5)  # the caller's shorter timeout wins
        self.assertEqual(deadlines, [1005.0])

    def test_a_stalled_handshake_stops_at_the_deadline(self):
        # A local server that accepts and then says nothing: the TLS handshake never completes.
        server = socket.socket()
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        self.addCleanup(server.close)
        timeouts = []
        real_settimeout = socket.socket.settimeout

        def settimeout(sock, value):
            timeouts.append(value)
            return real_settimeout(sock, value)
        start = time.monotonic()
        # No thread is left behind to shut the connection later: the deadline is only socket timeouts.
        with patch.object(_web.threading, 'Timer', side_effect=AssertionError('watchdog thread')), \
                patch.object(socket.socket, 'settimeout', settimeout):
            with self.assertRaises(OSError):
                REAL_CONNECT('storage.itch-cdn.example', server.getsockname(), 60, start + 0.5)
        self.assertLess(time.monotonic() - start, 3)
        self.assertTrue(timeouts and all(0 < t <= 0.5 for t in timeouts), timeouts)  # what's left, each step
        with patch.object(_web.socket, 'create_connection', side_effect=AssertionError('connected')):
            with self.assertRaises(socket.timeout):  # a deadline already gone: no connection attempt at all
                REAL_CONNECT('storage.itch-cdn.example', server.getsockname(), 60, time.monotonic() - 1)

    def test_an_unreachable_address_falls_back_to_the_next_checked_one(self):
        self.connect()
        self.storage('https://dual.example/upload/503/OrbitGarden-Quest.apk')
        self.web.route('dual.example/upload/503/OrbitGarden-Quest.apk', Reply('https://dual.example/', 200, apk_bytes()))
        self.unreachable.add('2a04:4e42::81')
        self.assertTrue(os.path.isfile(itch.download(self.owned_source(), '341190')['apk']))
        self.assertEqual(self.connected, [('dual.example', ('2a04:4e42::81', 443)), ('dual.example', ('151.101.1.1', 443))])
        self.unreachable.add('151.101.1.1')
        with self.assertRaisesRegex(SourceError, '^Could not download APK: Network is unreachable$'):
            itch.download(self.owned_source(), '341190')

    def test_storage_refusals_are_download_errors_not_rate_limits(self):
        self.connect()
        self.storage()
        self.web.route('storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk',
                       Reply('https://storage.itch-cdn.example/x', 403, b'denied'))
        with self.assertRaisesRegex(SourceError, r"itch.io's download server refused the file \(HTTP 403\)") as caught:
            itch.download(self.owned_source(), '341190')
        self.assertNotIsInstance(caught.exception, SourceLimited)
        self.assertTrue(account.connected())
        self.assertEqual(_web.wait_time('https://api.itch.io/'), 0)
        self.web.route('storage.itch-cdn.example/upload/503/OrbitGarden-Quest.apk',
                       Reply('https://storage.itch-cdn.example/x', 429, b'', {'Retry-After': '60'}))
        with self.assertRaises(SourceLimited):
            itch.download(self.owned_source(), '341190')

    def test_a_key_revoked_after_details_were_cached_is_removed_at_download(self):
        self.connect()
        itch.details(self.owned_source(), '341190')  # uploads and owned keys now cached
        for code in (401, 403):
            self.connect()
            self.web.route('api.itch.io/uploads/503/download', Reply('https://api.itch.io/uploads/503/download', code, b''))
            self.web.route('api.itch.io/profile', Reply('https://api.itch.io/profile', code, b''))
            with self.assertRaisesRegex(account.BadKey, 'no longer accepts the saved API key'):
                account.download(503, 9001)
            self.assertFalse(account.path().exists())
            self.web.route('api.itch.io/profile', {'user': {'username': 'player'}})
        # The key still works, only this download is refused: keep the key, say so.
        self.connect()
        self.web.route('api.itch.io/uploads/503/download', Reply('https://api.itch.io/uploads/503/download', 403, b''))
        with self.assertRaisesRegex(SourceError, r'refused this request \(HTTP 403\)') as caught:
            account.download(503, 9001)
        self.assertNotIsInstance(caught.exception, (account.BadKey, SourceLimited))
        self.assertTrue(account.connected())

    def test_a_disconnect_during_the_key_check_wins(self):
        checking, release = threading.Event(), threading.Event()

        def slow_profile(req, query):
            checking.set()
            release.wait(5)
            return {'user': {'username': 'player'}}
        self.web.route('api.itch.io/profile', slow_profile)
        outcome = {}

        def run():
            try:
                outcome['result'] = account.connect(KEY)
            except SourceError as e:
                outcome['error'] = e
        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(checking.wait(5))
        account.disconnect()
        release.set()
        worker.join(5)
        self.assertRegex(str(outcome.get('error')), 'changed while the key was being checked; nothing was saved')
        self.assertFalse(account.path().exists())
        self.assertFalse(account.connected())

    def test_an_old_refusal_does_not_undo_a_reconnect_with_the_same_key(self):
        self.connect()
        listing, release, profile_ok = threading.Event(), threading.Event(), [True]

        def slow_owned(req, query):
            listing.set()
            release.wait(5)
            return Reply(req.full_url, 401, b'')
        self.web.route('api.itch.io/profile/owned-keys', slow_owned)
        self.web.route('api.itch.io/profile', lambda req, q: {'user': {'username': 'player'}} if profile_ok[0]
                       else Reply(req.full_url, 401, b''))
        outcome = {}

        def run():
            try:
                account.owned_keys()
            except SourceError as e:
                outcome['error'] = e
        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(listing.wait(5))
        account.disconnect()
        account.connect(KEY)  # same key, connected again while the old listing waits
        profile_ok[0] = False  # the old listing's confirmation now sees a refusal
        release.set()
        worker.join(5)
        self.assertIsInstance(outcome.get('error'), account.BadKey)
        self.assertTrue(account.path().exists())  # the fresh connection survives
        self.assertEqual(json.loads(account.path().read_text())['key'], KEY)

    def test_redacted_text_is_not_mistaken_for_a_key_error(self):
        self.connect()
        before = len(self.web.urls('api.itch.io/profile'))
        self.web.route('api.itch.io/profile/owned-keys', {'errors': ['Invalid request: ' + KEY]})
        with self.assertRaisesRegex(SourceError, r'^itch.io: Invalid request: \[API key\]$') as caught:
            account.owned_keys()
        self.assertNotIsInstance(caught.exception, account.BadKey)
        self.assertTrue(account.connected())
        self.assertEqual(len(self.web.urls('api.itch.io/profile')), before)  # not even a key check needed

    def test_an_invalid_key_error_elsewhere_is_confirmed_before_deleting(self):
        self.connect()
        self.web.route('api.itch.io/profile/owned-keys', {'errors': ['invalid key']})
        with self.assertRaisesRegex(SourceError, '^itch.io: invalid key$') as caught:
            account.owned_keys()  # /profile still accepts the key: keep it
        self.assertNotIsInstance(caught.exception, account.BadKey)
        self.assertTrue(account.connected())
        account._forget()
        self.web.route('api.itch.io/profile', {'errors': ['invalid key']})
        with self.assertRaisesRegex(account.BadKey, 'no longer accepts'):
            account.owned_keys()
        self.assertFalse(account.connected())

    def test_concurrent_connects_never_share_a_temporary_file(self):
        made = []
        real = account.tempfile.mkstemp

        def mkstemp(*args, **kwargs):
            fd, name = real(*args, **kwargs)
            made.append(name)
            if os.name == 'posix':
                self.assertEqual(os.stat(name).st_mode & 0o777, 0o600)
            return fd, name
        with patch.object(account.tempfile, 'mkstemp', mkstemp):
            workers = [threading.Thread(target=lambda k=k: self.swallow(account.connect, k)) for k in (KEY, OTHER) * 3]
            for w in workers:
                w.start()
            for w in workers:
                w.join(5)
        self.assertEqual(len(made), len(set(made)))
        self.assertIn(json.loads(account.path().read_text())['key'], (KEY, OTHER))
        self.assertEqual([p.name for p in account.path().parent.iterdir()], ['itch-account.json'])

    @staticmethod
    def swallow(fn, *args):
        try:
            fn(*args)
        except SourceError:
            pass  # a connect overtaken by another one refuses to save: fine here

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
            # The key straddles the 200-character cut: no piece of it may survive.
            ({'errors': ['x' * 180, KEY]}, SourceError, r'^itch.io: x{180}; \[API key\]$'),
            ({'errors': ['x' * 190 + KEY]}, SourceError, r'^itch.io: x{190}\[API key\]$'),
        ]
        self.assertEqual(account._clean('cut at ' + KEY[:9], KEY), 'cut at [API key]')  # a truncated key's start
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
