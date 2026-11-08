"""Published progress descriptions in real React/DOM, with synthetic data."""
import sandbox  # noqa: F401
import hashlib
import html
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile

from framey_official import PLUGINS, archive
from test_framey_textfield_browser import BROWSER, run_browser

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER, 'Linux Chrome/Chromium is needed for real React/DOM')
class ProgressBrowser(unittest.TestCase):
    def test_emuchievements_progress_keeps_error_details_and_achievement_counts(self):
        plugin = next(p for p in PLUGINS if p['id'] == 28)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        info = re.search(r'window\.SP_REACT\.createElement\(deckyFrontendLib\.ProgressBarWithInfo, '
                         r'[\s\S]*?indeterminate: loadingData\.fetching \}\)', frontend)
        item = re.search(r'window\.SP_REACT\.createElement\(deckyFrontendLib\.ProgressBarItem, '
                         r'[^\n]*?bottomSeparator: "none" \}\)', frontend)
        self.assertIsNotNone(info)
        self.assertIsNotNone(item)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_progress.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_INFO__', info.group()),
                              ('__OFFICIAL_ITEM__', item.group())]:
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-progress-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=2000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey progress browser proof: '+json.dumps(report, sort_keys=True))
