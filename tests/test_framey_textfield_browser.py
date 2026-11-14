"""Real React/DOM text-field contracts with private, network-blocked pages."""
import sandbox  # noqa: F401
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from framey_official import PLUGINS, WEB_BROWSER_143, archive

ROOT = Path(__file__).resolve().parents[1]
BROWSER = next(filter(None, map(shutil.which, ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'))), None)


def wait_browser_group(group, timeout=5):
    # Waiting for the direct child does not wait for SIGKILL delivery to every
    # grandchild. Ignore zombies (which hold no files), but do not return while
    # a live member of this invocation's private session can hold the profile.
    deadline = time.monotonic()+timeout
    while True:
        live = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            if fields[2:4] == [str(group), str(group)] and fields[0] not in ('Z', 'X'):
                live.append(entry.name)
        if not live:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Owned browser group did not stop: '+', '.join(live))
        time.sleep(.01)


def run_browser(command, timeout=30):
    # Chrome can leave children holding the profile and captured output after
    # its parent exits or times out. Own the whole session before starting it,
    # and stop only that group before TemporaryDirectory removes the profile.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
            wait_browser_group(process.pid)
        finally:
            process.stdout.close()
            process.stderr.close()


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux process-group fixture')
class BrowserCleanup(unittest.TestCase):
    def test_success_keeps_browser_output(self):
        result = run_browser([sys.executable, '-c', 'print("fixture complete")'])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'fixture complete\n')

    def test_timeout_stops_child_holding_output_and_profile(self):
        with tempfile.TemporaryDirectory(prefix='framey-clear-cleanup-') as folder:
            ready = Path(folder)/'child.pid'
            child = ('import os,time; from pathlib import Path; '
                     'profile=Path('+repr(folder)+')/"profile"; profile.mkdir(); '
                     '(profile/"owned").write_text("fixture"); '
                     'Path('+repr(str(ready))+').write_text(str(os.getpid())); time.sleep(60)')
            parent = ('import subprocess,sys; child=subprocess.Popen([sys.executable,"-c",'
                      + repr(child) + ']); child.wait()')
            with self.assertRaises(subprocess.TimeoutExpired):
                run_browser([sys.executable, '-c', parent], timeout=2)
            self.assertTrue(ready.is_file(), 'child must have started before the timeout')
            status = Path('/proc')/ready.read_text()/'stat'
            if status.exists():
                # A grandchild can briefly await init reaping; it must no
                # longer execute or hold the profile/output descriptors.
                self.assertIn(status.read_text().rsplit(')', 1)[1].split()[0], ('Z', 'X'))


@unittest.skipUnless(sys.platform.startswith('linux') and BROWSER, 'Linux Chrome/Chromium is needed for the real DOM check')
class TextfieldBrowser(unittest.TestCase):
    def test_documented_tooltip_remains_visible_without_hover(self):
        # The declared @decky/ui 4.16.0 TextField.tooltip string prop, with
        # synthetic local content; no published plugin or headset claim.
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_textfield_help.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start)]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-textfield-help-') as folder:
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
        print('Framey TextField help browser proof: '+json.dumps(report, sort_keys=True))

    def test_tabmaster_search_ref_can_focus_its_native_input(self):
        plugin = next(p for p in PLUGINS if p['id'] == 61)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        control = re.search(r'window\.SP_REACT\.createElement\(DFL\.TextField, \{ value: query,'
                            r'[\s\S]*?ref: searchRef \}\)', frontend)
        action = re.search(r'const actionButtonProps = \{\s*onButtonDown: \(evt\) => \{'
                           r'[\s\S]*?\[DFL.GamepadButton.SELECT\]: \'Search\' \},\s*\};', frontend)
        self.assertIsNotNone(control)
        self.assertIsNotNone(action)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_textfield_ref.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_CONTROL__', control.group()),
                              ('__OFFICIAL_ACTION__', action.group())]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-textfield-ref-') as folder:
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
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey TextField ref browser proof: '+json.dumps(report, sort_keys=True))

    def test_native_text_constraints_preserve_browser_validation_and_events(self):
        # Exercise declared Decky numeric bounds and Framey's explicit native
        # text constraints with synthetic drafts, not a published plugin's
        # settings, Steam's TextField implementation or the VR keyboard.
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_textfield_constraints.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start)]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-text-constraints-') as folder:
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
        print('Framey text constraint browser proof: '+json.dumps(report, sort_keys=True))

    def test_fileserver_published_port_control_preserves_validation_style(self):
        plugin = next(p for p in PLUGINS if p['id'] == 60)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        control = re.search(r'window\.SP_REACT\.createElement\(DFL\.TextField, '
                            r'\{ description: "Must be between 1024 and 65535"[\s\S]*?'
                            r'onChange: handleValueChange\("port"\) \}\)', frontend)
        self.assertIsNotNone(control)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_textfield_style.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_CONTROL__', control.group())]:
            self.assertEqual(page.count(token), 1)
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-textfield-style-') as folder:
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
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey textfield style browser proof: '+json.dumps(report, sort_keys=True))

    def test_web_browser_published_inline_folder_action_retains_its_draft(self):
        plugin = WEB_BROWSER_143
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder']+'/dist/index.js').decode()
        component = re.search(r'const NewFavoriteFolderModal = .*?\n    \};', frontend, re.S)
        self.assertIsNotNone(component)
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_textfield_inline.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_COMPONENT__', component.group())]:
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-inline-controls-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                               '--no-default-browser-check', '--disable-background-networking',
                               '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                               '--virtual-time-budget=2000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey inline controls browser proof: '+json.dumps(report, sort_keys=True))

    def test_radiyo_text_dialog_preserves_initial_input_focus(self):
        plugin = next(p for p in PLUGINS if p['id'] == 24)
        data = archive(plugin)
        self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            frontend = bundle.read(plugin['folder'] + '/dist/index.js').decode()
        component = re.search(r'const TextFieldModal = \(\{ closeModal, onClosed, label, placeholder \}\) => \{'
                              r'[\s\S]*?\n  \};', frontend)
        self.assertIsNotNone(component)
        self.assertIn('focusOnMount: true', component.group())
        host = (ROOT/'ui/framey-host.js').read_text()
        without_start = re.sub(r'\n  start\(\);\n\}\)\(\);\s*$', '\n})();', host)
        self.assertNotEqual(without_start, host)
        page = (ROOT/'tests/page/framey_textfield_focus.html').read_text()
        for token, source in [('__REACT__', (ROOT/'ui/vendor/react-18.3.1.min.js').read_text()),
                              ('__REACT_DOM__', (ROOT/'ui/vendor/react-dom-18.3.1.min.js').read_text()),
                              ('__HOST__', without_start), ('__OFFICIAL_COMPONENT__', component.group())]:
            page = page.replace(token, source.replace('</script', r'<\/script'))
        with tempfile.TemporaryDirectory(prefix='framey-focus-browser-') as folder:
            document = Path(folder)/'fixture.html'
            document.write_text(page)
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                                  '--no-default-browser-check', '--disable-background-networking',
                                  '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                                  '--virtual-time-budget=2000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey initial focus browser proof: '+json.dumps(report, sort_keys=True))

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
            run = run_browser([BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                                  '--no-default-browser-check', '--disable-background-networking',
                                  '--user-data-dir='+str(Path(folder)/'profile'), '--dump-dom',
                                  '--virtual-time-budget=1000', document.as_uri()])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = re.search(r'<pre id="result">([^<]*)</pre>', run.stdout)
        self.assertIsNotNone(result, run.stderr[-2000:])
        report = json.loads(html.unescape(result.group(1)))
        self.assertIs(report.get('passed'), True, report)
        report.update(archiveSha256=plugin['sha256'], hostSha256=hashlib.sha256(host.encode()).hexdigest())
        print('Framey clear browser proof: '+json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
