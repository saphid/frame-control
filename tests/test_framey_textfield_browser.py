"""Real React/DOM clear-action contract with a private, network-blocked page."""
import sandbox  # noqa: F401
import hashlib
import html
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from framey_official import PLUGINS, archive

ROOT = Path(__file__).resolve().parents[1]
BROWSER = next(filter(None, map(shutil.which, ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'))), None)


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER, 'Linux Chrome/Chromium is needed for the real DOM check')
class TextfieldBrowser(unittest.TestCase):
    def test_published_search_clear_uses_real_react_change_events(self):
        plugin = next(p for p in PLUGINS if p['id'] == 68)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        control = re.search(r'window\.SP_REACT\.createElement\(DFL\.TextField, '
                            r'\{ "aria-label": "Search installed Steam games[^\n]+? \}\)', frontend)
        self.assertIsNotNone(control)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_textfield_clear.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_CONTROL__', control.group())]:
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-clear-browser-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = subprocess.run([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                                  '--no-default-browser-check', '--disable-background-networking',
                                  '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                                  '--virtual-time-budget=1000', document.as_uri()],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey clear browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
