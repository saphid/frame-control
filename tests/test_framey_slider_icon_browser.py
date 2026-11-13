"""Published volume slider with its real SVG, but no player or backend."""
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
class SliderIconBrowser(unittest.TestCase):
    def test_published_volume_slider_keeps_its_speaker_icon(self):
        plugin = next(p for p in PLUGINS if p['id'] == 24)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        control = re.search(r'window\.SP_REACT\.createElement\(deckyFrontendLib\.SliderField, '
                            r'\{ value: volume, min: 0, max: 100, step: 1, icon: '
                            r'window\.SP_REACT\.createElement\(MdVolumeUp, null\), '
                            r'onChange: changeVolume, bottomSeparator: "none" \}\)', frontend)
        self.assertIsNotNone(control)
        # Preserve the published react-icons runtime and icon function verbatim.
        runtime_start = frontend.index('var DefaultContext =')
        runtime_end = frontend.index('  // THIS FILE IS AUTO GENERATED', runtime_start)
        icon = re.search(r'function MdVolumeUp \(props\) \{[\s\S]*?\n  \}', frontend)
        self.assertIsNotNone(icon)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_slider_icon.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_CONTROL__', control.group()),
                              ('__OFFICIAL_ICON__', frontend[runtime_start:runtime_end]+icon.group())]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-slider-icon-') as folder:
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
        print('Framey slider icon browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
