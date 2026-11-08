"""Synthetic Decky slider validation through real React/native input events."""
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


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER, 'Linux Chrome/Chromium is needed for the real DOM check')
class SliderBrowser(unittest.TestCase):
    def test_predicate_blocks_invalid_settings_from_all_slider_actions(self):
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_slider_validation.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start)]:
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-slider-browser-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=1000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report['hostSha256'] = hashlib.sha256(host.encode()).hexdigest()
        print('Framey slider predicate browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
