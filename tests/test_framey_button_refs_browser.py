"""Published SteamGridDB toolbar focus through native dialog button refs."""
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
class ButtonRefsBrowser(unittest.TestCase):
    def test_published_toolbar_focus_and_native_button_ref_lifetimes(self):
        plugin = next(p for p in PLUGINS if p['id'] == 36)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        ref = re.search(r'const toolbarFocusRef = SP_REACT\.useRef\(null\);', frontend)
        focus = re.search(r'SP_REACT\.useImperativeHandle\(ref, \(\) => \(\{\s*focus: \(\) => \{\s*'
                          r'toolbarFocusRef\.current\?\.focus\(\);\s*\},\s*assetSizeStyleAttr,\s*'
                          r'\}\), \[assetSizeStyleAttr\]\);', frontend)
        control = re.search(r'window\.SP_REACT\.createElement\(DFL\.DialogButton, '
                            r'\{ ref: toolbarFocusRef,[^\n]+?onClick: onFilterClick \}, '
                            r'trans_string\(\x27ACTION_OPEN_FILTER\x27, \x27Filter\x27\)\)', frontend)
        self.assertIsNotNone(ref)
        self.assertIsNotNone(focus)
        self.assertIsNotNone(control)
        legacy = next(p for p in PLUGINS if p['id'] == 14)
        legacy_data = archive(legacy)
        self.assertEqual(hashlib.sha256(legacy_data).hexdigest(), legacy['sha256'])
        with zipfile.ZipFile(io.BytesIO(legacy_data)) as bundle:
            legacy_frontend = bundle.read(legacy['folder']+'/dist/index.js').decode()
        legacy_button = re.search(r'const Button = DFL\.DialogButton\.render\(\{\}\)\.type;', legacy_frontend)
        self.assertIsNotNone(legacy_button)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_button_refs.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_REF__', ref.group()),
                              ('__OFFICIAL_FOCUS__', focus.group()), ('__OFFICIAL_BUTTON__', control.group()),
                              ('__OFFICIAL_LEGACY_BUTTON__', legacy_button.group())]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-button-refs-') as folder:
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
        report.update(archiveSha256=plugin['sha256'], legacyArchiveSha256=legacy['sha256'],
                      hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey dialog button refs browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
