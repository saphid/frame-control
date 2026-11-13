"""Desktop plugin-job guards with real DOM controls and production runJob."""
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


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER,
                     'Linux Chrome/Chromium is needed for the real DOM check')
class DesktopStoreBrowser(unittest.TestCase):
    def test_plugin_changes_stay_locked_through_job_and_status_refresh(self):
        source = (ROOT/'ui/index.html').read_text()
        start = source.index('function deckyCompatibilityText(')
        store = source[start:source.index("$('deckyRefresh').onclick", start)]
        start = source.index('async function runJob(')
        job = source[start:source.index('// The install queue as the server has it:', start)]
        page = (ROOT/'tests/page/framey_desktop_store_jobs.html').read_text()
        for token, script in [('__STORE__', store), ('__RUN_JOB__', job)]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, script.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-desktop-store-jobs-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=4000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        match = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(match, run.stderr[-2000:])
        report = json.loads(html.unescape(match.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(desktopSha256=hashlib.sha256(source.encode()).hexdigest(),
                      storeSliceSha256=hashlib.sha256(store.encode()).hexdigest(),
                      runJobSliceSha256=hashlib.sha256(job.encode()).hexdigest())
        print('Framey desktop store job browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
