"""Native browser storage recovery with real parent-page controls, offline."""
import sandbox  # noqa: F401
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

from test_framey_textfield_browser import BROWSER, run_browser

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER, 'Linux Chrome/Chromium is needed for native browser storage')
class CacheBrowser(unittest.TestCase):
    def test_retry_saves_latest_panel_cache_across_real_page_reload(self):
        source = (ROOT/'ui/headset.html').read_text()
        # Keep the actual parent DOM, handlers and persistence code. Stop only
        # automatic remote startup; CSP blocks every network/frame connection.
        marker = 'refresh();refreshGames();'
        self.assertEqual(source.count(marker), 1)
        page = source.split(marker)[0]+'</script>'
        page = page.replace('<head>', '<head><meta http-equiv="Content-Security-Policy" '
                            'content="default-src \'none\'; script-src \'unsafe-inline\'; '
                            'style-src \'unsafe-inline\'">', 1)
        page += (ROOT/'tests/page/framey_cache_retry.html').read_text()+'</body></html>'
        with tempfile.TemporaryDirectory(prefix='framey-cache-browser-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=3000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        self.assertIs(report.get('realPageReloadReadback'), True, report)
        report['headsetSourceSha256'] = hashlib.sha256(source.encode()).hexdigest()
        print('Framey cache retry browser proof: '+json.dumps(report, sort_keys=True))
