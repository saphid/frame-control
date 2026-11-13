"""Published sidebar page icons in real React, with synthetic child views."""
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


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER,
                     'Linux Chrome/Chromium is needed for the real DOM check')
class SidebarBrowser(unittest.TestCase):
    def test_suggestme_published_settings_keep_their_page_icons(self):
        plugin = next(p for p in PLUGINS if p['id'] == 132)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        settings = re.search(r'const SettingsPage = \(\) => \{[\s\S]*?\n\};', frontend)
        self.assertIsNotNone(settings)
        # Replay the exact published page list, icon runtime and seven icon
        # functions. Child views are synthetic and cannot read or save data.
        start = frontend.index('var DefaultContext =')
        end = frontend.index('// THIS FILE IS AUTO GENERATED', start)
        icons = frontend[start:end]
        expected = []
        for name in re.findall(r'icon: window\.SP_REACT\.createElement\((\w+),', settings.group()):
            function = re.search(r'function '+name+r' \(props\) \{\s*return GenIcon\((.+)\)\(props\);\s*\}', frontend)
            self.assertIsNotNone(function, name)
            icons += function.group()+'\n'
            expected.append(json.loads(function.group(1)))
        self.assertEqual(len(expected), 7)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_sidebar_icons.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_ICONS__', icons),
                              ('__OFFICIAL_SETTINGS__', settings.group()),
                              ('__EXPECTED_ICONS__', json.dumps(expected))]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-sidebar-icons-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=1200', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey sidebar icons browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
