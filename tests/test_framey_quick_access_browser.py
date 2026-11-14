"""Published Decky-tab callbacks mapped only to this plugin's local page."""
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
class QuickAccessBrowser(unittest.TestCase):
    def test_published_decky_tab_callbacks_return_to_the_local_plugin(self):
        sources = {}
        digests = {}
        for plugin_id in (24, 63):
            plugin = next(p for p in PLUGINS if p['id'] == plugin_id)
            data = archive(plugin)
            self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
            with zipfile.ZipFile(io.BytesIO(data)) as bundle:
                sources[plugin_id] = bundle.read(plugin['folder']+'/dist/index.js').decode()
            digests[str(plugin_id)] = plugin['sha256']
        callback = re.search(r'const onSearchModalClosed = async \(query\) => \{[\s\S]*?\n      \};', sources[24])
        self.assertIsNotNone(callback)
        start = sources[63].index('class PyCaller {')
        end = sources[63].index('    static async getSettings()', start)
        published_toast = sources[63][start:end]+'}'
        self.assertIn('OpenQuickAccessMenu(DFL.QuickAccessTab.Decky)', published_toast)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$',
                               '\n  window.__FixtureSurface = PluginSurface;\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_quick_access.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_SEARCH_CALLBACK__', callback.group()),
                              ('__OFFICIAL_TOAST__', published_toast)]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-quick-access-') as folder:
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
        report.update(archiveSha256s=digests, hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey local Decky return browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
