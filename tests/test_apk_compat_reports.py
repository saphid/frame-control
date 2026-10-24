"""Search report snapshots: synthetic evidence only, no credentials or services."""
import sandbox  # noqa: F401
import sys
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_catalog
import frame_compat_db as db
from apk_sources import search
from test_apk_search import SettingsTest, fake, ENTRIES


class ReportTests(SettingsTest):
    def hook(self, rows):
        by = frame_catalog.reports.by_package(rows)
        snapshot = {pkg: v for pkg, rs in by.items() if (v := frame_catalog.reports.verdict(rs))}
        p = patch.object(search, 'compat_reports', lambda: snapshot)
        p.start()
        self.addCleanup(p.stop)

    def test_search_and_details_share_catalogue_rules(self):
        pkg = ENTRIES[0]['package']
        self.hook([dict(package=pkg, date='2026-10-01', result='runs'),
                   dict(package=pkg, date='2026-10-02', rating='broken', notes='Crashes <here>'),
                   dict(package=pkg, date='2026-10-03', result='runs')])
        mod = fake()
        with patch.object(search, 'modules', return_value=([mod], [])):
            offer = search.search(timeout=.01)['apps'][0]['offers'][0]
            detail = search.details('one', ENTRIES[0]['id'])
        self.assertEqual(detail['compat_report']['verdict'], 'no')
        self.assertEqual(offer['compat_report'], detail['compat_report'])
        self.assertEqual(detail['verdict']['tone'], 'warning')
        self.assertIn('Reported not working', detail['verdict']['label'])

    def test_warnings_never_change_installability_or_hard_blockers(self):
        entry = dict(ENTRIES[0], min_sdk=23, abis=['arm64-v8a'])
        for kind, tone in [('works', 'works'), ('issues', 'issues'), ('broken', 'warning')]:
            self.hook([dict(package=entry['package'], date='2026-10-01', rating=kind)])
            decorated = search.decorate(entry)
            self.assertEqual(decorated['verdict']['tone'], tone)
            self.assertTrue(decorated['fit']['installable'])
            for blocker in [dict(min_sdk=31), dict(abis=['x86_64']),
                            dict(requires_meta_services=True), dict(engine='VrApi')]:
                blocked = search.decorate(dict(entry, **blocker))
                self.assertEqual(blocked['verdict']['tone'], 'blocked')
                self.assertIsNotNone(blocked['compat_report'])

    def test_wrong_file_failures_do_not_warn_but_real_failures_do(self):
        entry = dict(ENTRIES[0], min_sdk=23, abis=[])
        for notes in ['no arm64-v8a build', 'needs Android API 32']:
            self.hook([dict(package=entry['package'], date='2026-10-01', result='install_failed', notes=notes)])
            self.assertIsNone(search.decorate(entry)['compat_report'])
        self.hook([dict(package=entry['package'], date='2026-10-01', result='crashes')])
        self.assertEqual(search.decorate(entry)['verdict']['tone'], 'warning')
        self.hook([dict(package=entry['package'], date='2026-10-01', result='install_failed', notes='installer crashed')])
        self.assertEqual(search.decorate(entry)['verdict']['tone'], 'warning')

    def test_report_warning_does_not_prevent_install(self):
        self.hook([dict(package=ENTRIES[0]['package'], date='2026-10-01', rating='broken')])
        mod = fake()
        with patch.object(search, 'modules', return_value=([mod], [])), \
             patch.object(frame_catalog.frame_android, 'install', return_value={'package': ENTRIES[0]['package']}) as install:
            result = search.install('one', ENTRIES[0]['id'])
        self.assertEqual(result['package'], ENTRIES[0]['package'])
        install.assert_called_once()

    def test_stalled_loader_does_not_block_search_or_details(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        main = threading.get_ident()

        def loader():
            self.assertNotEqual(threading.get_ident(), main)
            entered.set()
            try:
                if not release.wait(2):
                    raise TimeoutError('test stalled')
                return []
            finally:
                finished.set()

        cache = search.ReportCache(loader, frame_catalog.reports.verdict)
        from apk_sources import _web
        with patch.object(search, 'compat_reports', cache.read), \
             patch.object(search, 'modules', return_value=([fake()], [])), \
             patch.object(_web, 'prune'), \
             patch.object(db, 'key', side_effect=AssertionError('credentials on request')), \
             patch.object(db._opener, 'open', side_effect=AssertionError('network on request')), \
             patch.object(db.subprocess, 'run', side_effect=AssertionError('subprocess on request')):
            try:
                search.warm()  # production server startup, before the first request
                self.assertTrue(entered.wait(1))
                start = time.monotonic()
                result = search.search(timeout=.01)
                detail = search.details('one', ENTRIES[0]['id'])
                self.assertLess(time.monotonic() - start, .2)
                self.assertTrue(result['apps'])
                self.assertIsNone(detail['compat_report'])
            finally:
                release.set()
                self.assertTrue(finished.wait(1))


class CacheTests(unittest.TestCase):
    def wait_idle(self, cache):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with cache._lock:
                if not cache._running:
                    return
            time.sleep(.001)
        self.fail('report worker did not finish')

    def test_public_copy_reads_its_local_mirror_and_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror, outbox = Path(tmp) / 'mirror.json', Path(tmp) / 'outbox.jsonl'
            mirror.write_text(json.dumps({'reports': [dict(package='org.example.app', id='old',
                              date='2026-10-01', result='runs')]}))
            outbox.write_text(json.dumps(dict(package='org.example.app', id='new',
                              date='2026-10-02', rating='broken')) + '\n')
            with patch.object(db, 'MIRROR', str(mirror)), patch.object(db, 'OUTBOX', str(outbox)), \
                 patch.object(db, '_mem', dict(at=0, reports=None, source=None)), \
                 patch.object(db, 'shared', return_value=False), \
                 patch.object(db, 'fetch_all', side_effect=AssertionError('private database read')):
                cache = search.ReportCache(db.load, frame_catalog.reports.verdict)
                cache.read()
                self.wait_idle(cache)
                self.assertEqual(cache.read()['org.example.app'][0], 'no')

    def test_ttl_refresh_is_single_flight_and_keeps_last_good_snapshot(self):
        loader = Mock(return_value=[dict(package='org.example.app', date='2026-10-01', rating='issues')])
        cache = search.ReportCache(loader, frame_catalog.reports.verdict, ttl=60)
        cache.read()
        self.wait_idle(cache)
        first = cache.read()
        self.assertEqual(first['org.example.app'][0], 'maybe')
        self.assertEqual(loader.call_count, 1)
        entered, release = threading.Event(), threading.Event()

        def stalled():
            entered.set()
            release.wait(2)
            raise OSError('offline')

        loader.side_effect = stalled
        cache._at -= 61
        try:
            self.assertIs(cache.read(), first)
            self.assertTrue(entered.wait(1))
            for _ in range(10):
                self.assertIs(cache.read(), first)
            self.assertEqual(loader.call_count, 2)
        finally:
            release.set()
            self.wait_idle(cache)
        self.assertIs(cache.read(), first)
        self.assertEqual(loader.call_count, 2)  # failure also has a retry TTL
        loader.side_effect = None
        loader.return_value = [dict(package='org.example.app', date='2026-10-02', rating='works')]
        cache._at -= 61
        cache.read()
        self.wait_idle(cache)
        self.assertEqual(cache.read()['org.example.app'][0], 'works')
        self.assertEqual(first['org.example.app'][0], 'maybe')  # published snapshots never mutated
