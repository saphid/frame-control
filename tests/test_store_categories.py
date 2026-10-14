"""The store's Frame categories (ui/apk_sources/_categories.py): which apps go where, which are
phone-only and hidden, and how the browse, search and library artwork use them. Offline."""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
from apk_sources import SourceError, _categories, _images, fdroid, search  # noqa: E402
import test_fdroid_sources as fixtures  # noqa: E402  (a module, so its tests don't run twice)
FIXTURES, PIN, URL = fixtures.FIXTURES, fixtures.PIN, fixtures.URL


def kind(**entry):
    return _categories.classify(dict({'name': 'App', 'summary': ''}, **entry))


class Classify(unittest.TestCase):
    def test_vr_first_whatever_else_it_is(self):
        self.assertEqual(kind(vr=True, categories=['Phone & SMS']), {'category': 'vr', 'phone_only': False})

    def test_fine_categories_decide(self):
        self.assertEqual(kind(categories=['Games', 'Puzzle Game'])['category'], 'games')
        self.assertEqual(kind(categories=['Games', 'Emulator'])['category'], 'emulators')
        # A chat app is in Multimedia too; the finer Social Network wins.
        self.assertEqual(kind(categories=['Multimedia', 'Internet', 'Social Network'])['category'], 'web')
        self.assertEqual(kind(categories=['Reading', 'Ebook Reader'])['category'], 'read')
        self.assertEqual(kind(categories=['Multimedia', 'Podcast'])['category'], 'watch')

    def test_broad_categories_alone(self):
        self.assertEqual(kind(categories=['Multimedia']), {'category': 'watch', 'phone_only': False})
        self.assertEqual(kind(categories=['Writing']), {'category': 'work', 'phone_only': False})

    def test_phone_only(self):
        for categories in (['System', 'Launcher'], ['Internet', 'VPN & Proxy'], ['Theming', 'Wallpaper'],
                           ['Sports & Health'], ['Connectivity'], ['Time', 'Alarm Clock'], ['Habit Tracker']):
            with self.subTest(categories=categories):
                self.assertTrue(kind(categories=categories)['phone_only'])
        self.assertTrue(kind(name='[ROOT] Night Light', categories=['Development'])['phone_only'])
        self.assertTrue(kind(name='5G Proxy Client', summary='Routes traffic')['phone_only'])

    def test_games_and_media_keep_phone_words(self):
        # 'Battery' in a game's name or a widget in a music player doesn't hide a game or a player.
        self.assertFalse(kind(name='Widget Wars', categories=['Strategy Game'])['phone_only'])
        self.assertFalse(kind(name='Music', summary='with a home screen widget', categories=['Local Media Player'])['phone_only'])

    def test_emulators_by_name_without_categories(self):
        self.assertEqual(kind(name='RetroArch', summary='Frontend for emulators')['category'], 'emulators')

    def test_unknown_is_neither_hidden_nor_guessed(self):
        self.assertEqual(kind(name='Thing'), {'category': None, 'phone_only': False})
        self.assertEqual(kind(categories=['Something New']), {'category': None, 'phone_only': False})

    def test_matches(self):
        phone = {'category': 'tools', 'phone_only': True}
        self.assertFalse(_categories.matches(phone))
        self.assertTrue(_categories.matches(phone, phone=True))
        self.assertTrue(_categories.matches({'category': 'games', 'phone_only': False}, 'games'))
        self.assertFalse(_categories.matches({'category': 'watch', 'phone_only': False}, 'games'))

    def test_every_store_category_has_a_label(self):
        self.assertEqual({c for c, _ in _categories.CATEGORIES}, _categories.IDS)
        targets = set(_categories.FINE) | {c for c in _categories.BROAD.values() if c}
        self.assertLessEqual(targets, _categories.IDS)
        self.assertLessEqual(set(_categories.PRIORITY), _categories.IDS)


class FDroidCategories(unittest.TestCase):
    setUp, fetch, add = fixtures.Repositories.setUp, fixtures.Repositories.fetch, fixtures.Repositories.add

    def index(self, version, categories):
        raw = json.loads((FIXTURES / ('artwork-' + version + '.json')).read_text())
        if version == 'v2':
            raw['packages']['org.example.app']['metadata']['categories'] = categories
        else:
            raw['apps'][0]['categories'] = categories
        path = self.root / ('index-' + version + '.json')
        path.write_text(json.dumps(raw))
        if version == 'v1':
            fdroid._v1(path.read_bytes(), path)
        return path

    def test_categories_survive_v1_and_v2(self):
        source = self.add()
        for version in ('v1', 'v2'):
            with self.subTest(version=version):
                apps = fdroid._reduce(self.index(version, ['Games', 'Puzzle Game', 7]), source)
                self.assertEqual(apps['org.example.app']['categories'], ['Games', 'Puzzle Game'])

    def save(self, source, apps):
        fdroid._write(fdroid.frame_host.cache_dir('apk-sources', source['id'] + '.json'),
                      {'version': fdroid.CACHE_VERSION, 'url': URL, 'fingerprint': PIN, 'apps': apps})

    def app(self, pkg, name, updated, categories=(), banner=None):
        return {'source': 'x', 'id': pkg, 'package': pkg, 'name': name, 'summary': '', 'updated': updated,
                'categories': list(categories), 'images': {'icon': None, 'banner': banner, 'screenshots': []}}

    def test_browse_shows_artwork_then_newest_and_filters_before_the_limit(self):
        source = self.add()
        self.save(source, {a['id']: a for a in (
            self.app('a.old', 'Aaa', '2020-01-01', ['Puzzle Game']),
            self.app('b.new', 'Bbb', '2026-01-01', ['Puzzle Game']),
            self.app('c.art', 'Ccc', '2019-01-01', ['Puzzle Game'], banner=URL + 'b.png'),
            self.app('d.sms', 'Ddd', '2026-02-01', ['Phone & SMS']))})
        self.assertEqual([a['id'] for a in fdroid.search(source, '', limit=10)], ['c.art', 'd.sms', 'b.new', 'a.old'])
        keep = lambda e: _categories.matches(dict(e, **_categories.classify(e)))
        self.assertEqual([a['id'] for a in fdroid.search(source, '', limit=1, keep=keep)], ['c.art'])
        self.assertEqual([a['id'] for a in fdroid.search(source, 'a', limit=10)], ['a.old', 'c.art'])  # a query sorts by name

    def test_lookup_reads_the_saved_index_only(self):
        source = self.add()
        self.assertEqual(fdroid.lookup(dict(source, id='never-loaded'), ['org.example.app']), {})
        self.save(source, {'a.b': self.app('a.b', 'A', None)})
        before = self.fetch_mock.call_count
        self.assertEqual(list(fdroid.lookup(source, ['a.b', 'missing'])), ['a.b'])
        self.assertEqual(self.fetch_mock.call_count, before)
        self.assertEqual(fdroid.lookup(dict(source, enabled=False), ['a.b']), {})


def fake_source(entries, kind_='fake', lookup=None):
    mod = types.SimpleNamespace(KIND=kind_)
    mod.sources = lambda: [{'id': kind_, 'kind': kind_, 'name': kind_.title(), 'url': 'https://example.org/',
                            'builtin': True, 'enabled': True, 'trust': 'community'}]
    mod.search = lambda source, query, limit=50: [dict(e) for e in entries][:limit]
    mod.details = lambda source, entry_id: next(dict(e) for e in entries if e['id'] == entry_id)
    if lookup is not None:
        mod.lookup = lookup
    return mod


ENTRY = {'source': 'fake', 'package': None, 'summary': '', 'free': True, 'downloadable': True,
         'min_sdk': 24, 'abis': ['arm64-v8a'], 'vr': None}


class Search(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = patch.object(search, 'settings_path', return_value=Path(tmp.name) / 'sources.json')
        p.start()
        self.addCleanup(p.stop)
        for state in (search._running, search._pending, search._status):
            state.clear()
            self.addCleanup(state.clear)

    def run_search(self, entries, **kwargs):
        with patch.object(search, 'modules', return_value=([fake_source(entries)], [])):
            return search.search(**kwargs)

    def test_category_and_phone_filters(self):
        entries = [dict(ENTRY, id='g', name='Game', categories=['Puzzle Game']),
                   dict(ENTRY, id='s', name='Texts', categories=['Phone & SMS']),
                   dict(ENTRY, id='v', name='Video', categories=['Local Media Player'])]
        result = self.run_search(entries)
        self.assertEqual(sorted(a['name'] for a in result['apps']), ['Game', 'Video'])
        self.assertEqual({a['name']: a['category'] for a in result['apps']}, {'Game': 'games', 'Video': 'watch'})
        self.assertIn({'id': 'emulators', 'label': 'Emulators'}, result['categories'])
        self.assertEqual([a['name'] for a in self.run_search(entries, category='games')['apps']], ['Game'])
        self.assertEqual(len(self.run_search(entries, phone=True)['apps']), 3)
        with self.assertRaisesRegex(SourceError, 'Unknown category'):
            self.run_search(entries, category='phones')

    def test_listing_offers_three_screenshots_details_all(self):
        shots = ['https://example.org/%d.png' % i for i in range(8)]
        entry = dict(ENTRY, id='g', name='Game', images={'icon': None, 'banner': None, 'screenshots': shots})
        listed = self.run_search([entry])['apps'][0]['offers'][0]
        self.assertEqual(len(listed['artwork']['screenshots']), 3)
        self.assertEqual(len(search.decorate(entry)['artwork']['screenshots']), 8)

    def test_browse_asks_sources_for_more_than_a_search(self):
        seen = []
        mod = fake_source([])
        mod.search = lambda source, query, limit=50: seen.append((query, limit)) or []
        with patch.object(search, 'modules', return_value=([mod], [])):
            search.search('')
            search.search('chess')
        self.assertEqual(seen, [('', search.BROWSE_LIMIT), ('chess', 50)])


class LibraryArtwork(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = patch.object(search, 'settings_path', return_value=Path(tmp.name) / 'sources.json')
        p.start()
        self.addCleanup(p.stop)

    def test_by_package_from_saved_indexes_then_by_name_for_curated_apps(self):
        icon = {'images': {'icon': 'https://example.org/icon.png', 'banner': None, 'screenshots': []}}
        repo = fake_source([], 'fdroid', lookup=lambda source, packages: {
            p: dict(icon, name='x') for p in packages if p == 'org.antennapod'})
        github = fake_source([dict(icon, id='icosa/open-brush', name='Open Brush')], 'github')
        bare = fake_source([dict(icon, id='x', name='Elsewhere', package='org.elsewhere')], 'itch')
        apps = [{'package': 'org.antennapod', 'label': 'AntennaPod'}, {'package': 'com.Icosa.OpenBrush', 'label': 'Open Brush'},
                {'package': 'org.elsewhere', 'label': 'Elsewhere'}, {'package': 'org.none', 'label': 'None'}]
        with patch.object(search, 'modules', return_value=([repo, github, bare], [])):
            found = search.artwork_for(apps)
        self.assertEqual(sorted(found), ['com.Icosa.OpenBrush', 'org.antennapod'])
        self.assertTrue(found['org.antennapod']['icon'].startswith('/source-image/'))

    def test_a_failing_source_is_skipped(self):
        def broken(source, packages):
            raise SourceError('no')
        with patch.object(search, 'modules', return_value=([fake_source([], 'fdroid', lookup=broken)], [])):
            self.assertEqual(search.artwork_for([{'package': 'a.b', 'label': 'A'}]), {})


class ImageHandles(unittest.TestCase):
    def test_same_url_same_handle_without_scanning(self):
        with _images._lock:
            _images._urls.clear()
            _images._tokens.clear()
        a = _images.register('https://example.org/a.png')
        self.assertEqual(_images.register('https://example.org/a.png'), a)
        self.assertNotEqual(_images.register('https://example.org/b.png'), a)



class Route(unittest.TestCase):
    def test_search_filters_are_checked(self):
        import server
        with patch.object(server.apk_search, 'search', return_value={'apps': []}) as run:
            server.source_search('q=&category=games&phone=1')
            self.assertEqual(run.call_args.kwargs['category'], 'games')
            self.assertIs(run.call_args.kwargs['phone'], True)
            server.source_search('q=chess')
            self.assertEqual((run.call_args.kwargs['category'], run.call_args.kwargs['phone']), (None, False))
            for bad in ('phone=maybe', 'category=' + 'x' * 41):
                with self.subTest(bad=bad), self.assertRaises(server.Failure):
                    server.source_search(bad)



class ReviewCases(unittest.TestCase):
    """Real index entries (October 2026) that the first rules got wrong."""
    def test_useful_apps_with_a_phone_side_stay(self):
        for categories, category in ((['Connectivity', 'Email', 'Internet', 'Writing'], 'web'),  # Thunderbird
                                     (['Connectivity', 'Internet', 'Multimedia', 'Podcast'], 'watch'),  # FocusPodcast
                                     (['Contact', 'Email'], 'web'),
                                     (['Cloud Storage & File Sync', 'File Manager', 'System'], 'tools')):
            with self.subTest(categories=categories):
                self.assertEqual(kind(categories=categories), {'category': category, 'phone_only': False})

    def test_phone_side_alone_or_with_a_broad_category_is_hidden(self):
        for categories in (['Internet', 'VPN & Proxy'], ['App Manager', 'Development', 'System'], ['Navigation']):
            with self.subTest(categories=categories):
                self.assertTrue(kind(categories=categories)['phone_only'])
        self.assertTrue(kind(categories=['Launcher', 'Games'])['phone_only'])  # system ones always

    def test_no_root_needed_is_not_a_root_tool(self):
        for summary in ('Linux on Android, no root required', 'Linux Without Root Access', 'SSH server without root',
                        'Works on non-rooted phones', 'Rootless and simple'):
            with self.subTest(summary=summary):
                self.assertFalse(kind(summary=summary, categories=['Development'])['phone_only'])
        self.assertTrue(kind(summary='Needs root to tune the kernel', categories=['Development'])['phone_only'])

    def test_izzyondroid_names(self):
        self.assertEqual(kind(categories=['Office'])['category'], 'work')
        self.assertTrue(kind(categories=['Xposed'])['phone_only'])



class ReviewCasesTwo(unittest.TestCase):
    """Round two of real entries (October 2026)."""
    def test_messengers_with_phone_or_push_stay(self):
        for categories in (['Internet', 'Messaging', 'Phone & SMS'], ['Internet', 'Messaging', 'Push'],
                           ['Connectivity', 'Messaging', 'Phone & SMS', 'Voice & Video Chat']):
            with self.subTest(categories=categories):
                self.assertEqual(kind(categories=categories), {'category': 'web', 'phone_only': False})

    def test_broad_only_sources_can_escape_a_phone_side(self):
        self.assertEqual(kind(categories=['System', 'Development']), {'category': 'tools', 'phone_only': False})
        self.assertEqual(kind(categories=['Connectivity', 'Internet']), {'category': 'web', 'phone_only': False})
        self.assertTrue(kind(categories=['VPN & Proxy', 'Internet'])['phone_only'])  # it has finer ones, none useful

    def test_summary_features_dont_make_a_phone_app(self):
        self.assertFalse(kind(name='OSS Weather', summary='Forecasts with home screen widgets', categories=['Weather'])['phone_only'])
        self.assertFalse(kind(name='Digital Calculator', summary='Hardware keyboard support', categories=['Calculator', 'System'])['phone_only'])
        self.assertTrue(kind(name='Clock Widget', categories=['Clock'])['phone_only'])  # but the name says what it is

    def test_saying_root_isnt_needed(self):
        for summary in ('VNC server app that does not require root privileges', "Backups that don't need root access",
                        "It doesn't need root", 'Linux without root', 'Works on non-rooted phones', 'Rootless'):
            with self.subTest(summary=summary):
                self.assertFalse(kind(summary=summary, categories=['Remote Access'])['phone_only'])
        for summary in ('Requires root', 'Needs root access to change the kernel', 'For rooted devices'):
            with self.subTest(summary=summary):
                self.assertTrue(kind(summary=summary, categories=['Remote Access'])['phone_only'])

    def test_hardware_the_frame_lacks(self):
        self.assertTrue(kind(name='IR Blaster Remote', categories=['Multimedia', 'Remote Controller', 'System'])['phone_only'])
        self.assertTrue(kind(name='Wear Sync for Breezy', summary='Weather on your Wear OS watch', categories=['Connectivity', 'Weather'])['phone_only'])


class SearchFindsPhoneApps(unittest.TestCase):
    setUp, run_search = Search.setUp, Search.run_search

    def test_a_search_finds_what_browsing_hides(self):
        entries = [dict(ENTRY, id='s', name='Texts', categories=['Phone & SMS'])]
        self.assertEqual(self.run_search(entries)['apps'], [])
        found = self.run_search(entries, query='texts')['apps']
        self.assertEqual([(a['name'], a['offers'][0]['phone_only']) for a in found], [('Texts', True)])


if __name__ == '__main__':
    unittest.main()
