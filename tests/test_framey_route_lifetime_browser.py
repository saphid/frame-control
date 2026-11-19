"""Local route registration ownership and active replacement in real React/DOM."""
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


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER, 'Linux Chrome/Chromium is needed for real React/DOM')
class RouteLifetimeBrowser(unittest.TestCase):
    def test_route_replacement_owns_cleanup_and_refreshes_the_active_view(self):
        host = (ROOT/'ui/framey-host.js').read_text()
        instrumented = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$',
                              '\n  window.__FixtureSurface = PluginSurface;\n})();', host)
        self.assertNotEqual(instrumented, host)
        page = (ROOT/'tests/page/framey_route_lifetime.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', instrumented)]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-route-lifetime-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=1500', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey route registration browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
