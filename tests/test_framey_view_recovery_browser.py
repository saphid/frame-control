"""A failing synthetic plugin view must leave local recovery controls usable."""
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
class ViewRecoveryBrowser(unittest.TestCase):
    def test_failed_routes_and_views_keep_local_recovery_controls(self):
        host = (ROOT/'ui/framey-host.js').read_text()
        instrumented = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$',
                              '\n  window.__FixtureSurface = PluginSurface;'
                              '\n  window.__FixtureBoundary = PanelBoundary;\n})();', host)
        self.assertNotEqual(instrumented, host)
        page = (ROOT/'tests/page/framey_view_recovery.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', instrumented)]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-view-recovery-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=1500', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        match = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(match, run.stderr[-2000:])
        report = json.loads(html.unescape(match.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report['hostSha256'] = hashlib.sha256(host.encode()).hexdigest()
        print('Framey view error recovery browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
