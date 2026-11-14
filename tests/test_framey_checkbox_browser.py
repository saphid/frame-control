"""Published checkbox pointer routing through real React/native controls."""
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


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER, 'Linux Chrome/Chromium is needed for the real DOM check')
class CheckboxBrowser(unittest.TestCase):
    def test_published_multiselect_keeps_checkbox_pointer_routing(self):
        plugin = next(p for p in PLUGINS if p['id'] == 36)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        start = frontend.index('const DropdownMultiselectItem =')
        end = frontend.index('const DropdownMultiselect =', start)
        component = frontend[start:end]
        css = re.search(r'\.decky_DropdownMultiselectItem_DialogCheckbox \{[\s\S]*?\}', frontend)
        self.assertIsNotNone(css)
        self.assertIn('pointer-events: none', css.group())
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_checkbox.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_COMPONENT__', component),
                              ('__OFFICIAL_CSS__', css.group())]:
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-checkbox-browser-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=1000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        match = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(match, run.stderr[-2000:])
        report = json.loads(html.unescape(match.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey checkbox browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
