"""Verified Decky-store-shaped install flow through the real HTTP server and fake Frame SSH."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import shlex
import subprocess
import threading
import zipfile

from harness import FrameTestCase, ROOT, Server, api, finished, ok, require, ssh
from framey_official import LEGACY_PLUGINS, PLUGINS as PANEL_PLUGINS, archive as official_archive

OFFICIAL_PLUGINS = PANEL_PLUGINS + LEGACY_PLUGINS

require()  # Skip the module outside the disposable fake Frame, like its peers.


def archive(version):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as bundle:
        bundle.writestr('sample-panel/plugin.json', json.dumps({'name':'Sample Panel','api_version':2,'flags':[]}))
        bundle.writestr('sample-panel/dist/index.js',
                        f"export default () => ({{content: SP_REACT.createElement('p', null, 'Sample {version}')}});")
        bundle.writestr('sample-panel/README.txt', ''.join(hashlib.sha256(f'{version}-{n}'.encode()).hexdigest() for n in range(35)))
    return raw.getvalue()


ARTIFACTS = {hashlib.sha256(a).hexdigest(): a for a in (archive('1.0.0'), archive('1.1.0'))}
HASHES = list(ARTIFACTS)
for plugin in OFFICIAL_PLUGINS:
    data = official_archive(plugin)
    assert hashlib.sha256(data).hexdigest() == plugin['sha256']
    ARTIFACTS[plugin['sha256']] = data


class StoreFixture(BaseHTTPRequestHandler):
    release = 0
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == '/plugins':
            records = [{'id':999,'name':'Sample Panel','author':'Fixture',
                                'description':'A harmless panel','tags':[],
                                'versions':[{'name':['1.0.0','1.1.0'][self.release],
                                             'hash':HASHES[self.release]}]}]
            records.extend({'id':plugin['id'], 'name':plugin['name'], 'author':'Official Decky store',
                            'description':'Pinned official archive', 'tags':[],
                            'versions':[{'name':plugin['version'], 'hash':plugin['sha256']}]}
                           for plugin in OFFICIAL_PLUGINS)
            body = json.dumps(records).encode()
            content_type = 'application/json'
        elif self.path.startswith('/versions/') and self.path.endswith('.zip'):
            body = ARTIFACTS.get(self.path.split('/')[-1][:-4])
            content_type = 'application/zip'
        else:
            body = None
        self.send_response(200 if body is not None else 404)
        self.send_header('Content-Type', content_type if body is not None else 'text/plain')
        self.end_headers()
        self.wfile.write(body or b'not found')


class FrameyFlow(FrameTestCase):
    @classmethod
    def setUpClass(cls):
        require()
        StoreFixture.release = 0
        cls.fixture = ThreadingHTTPServer(('127.0.0.1', 0), StoreFixture)
        cls.thread = threading.Thread(target=cls.fixture.serve_forever, daemon=True)
        cls.thread.start()
        port = cls.fixture.server_port
        cls.previous = {key:os.environ.get(key) for key in ('FRAMEY_STORE_URL','FRAMEY_CDN_URL')}
        os.environ['FRAMEY_STORE_URL'] = f'http://127.0.0.1:{port}/plugins'
        os.environ['FRAMEY_CDN_URL'] = f'http://127.0.0.1:{port}/versions/'
        Server.stop()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        Server.stop()
        cls.fixture.shutdown()
        for key, value in cls.previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value

    def backend(self):
        code = '''import json,pathlib
h=pathlib.Path.home(); b=h/'.local/share/frame-control/decky/.frame-control'; b.mkdir(parents=True,exist_ok=True)
(b/'receipt.json').write_text(json.dumps({'managedBy':'Frame Control','version':'v3.3.0'}))
(b.parent/'plugins').mkdir(exist_ok=True)
u=h/'.config/systemd/user/frame-control-decky.service'; u.parent.mkdir(parents=True,exist_ok=True); u.write_text('[Service]')'''
        ssh('python3 -c ' + shlex.quote(code))
        ssh('mkdir -p ~/.local/share/frame-control/headset/bundle/ui')
        source = (ROOT/'ui/frame_steam.py').read_bytes()
        copy = subprocess.run(['ssh','frame','cat > ~/.local/share/frame-control/headset/bundle/ui/frame_steam.py'],
                              input=source, capture_output=True, timeout=20)
        self.assertEqual(copy.returncode, 0, copy.stderr)

    def test_store_install_update_remove_and_guards(self):
        self.backend()
        status, _, _ = api('GET', '/api/decky/store', headers={'X-Frame-UI':''})
        self.assertEqual(status, 403)
        catalogue = ok('GET', '/api/decky/store')['plugins']
        self.assertEqual((catalogue[0]['version'], catalogue[0]['sha256']), ('1.0.0', HASHES[0]))
        status, _, _ = api('POST', '/api/decky/plugin', {'action':'install','id':999})
        self.assertEqual(status, 400)  # Third-party code needs explicit acknowledgement.
        job = finished(ok('POST', '/api/decky/plugin',
                          {'action':'install','id':999,'acknowledged':True}))
        self.assertFalse(job.get('error'), job)
        self.assertEqual(ok('GET', '/api/decky')['plugins'][0]['version'], '1.0.0')
        self.assertIn('Sample 1.0.0', ssh('cat ~/.local/share/frame-control/decky/plugins/sample-panel/dist/index.js'))
        receipt = HASHES[0]
        def framey_call(body):
            return ok('POST', '/api/framey/method', dict(body, receipt=receipt))
        status, _, _ = api('POST', '/api/framey/method', {'id':999,'method':'get_setting','args':[]},
                           headers={'X-Frame-UI':''})
        self.assertEqual(status, 403)
        status, _, _ = api('POST', '/api/framey/method', {'id':999,'method':'x;alert(1)','args':[]})
        self.assertEqual(status, 400)
        self.assertEqual(framey_call(
                            {'id':999,'method':'get_setting','args':['theme','dark']})['result'], 'dark')
        self.assertTrue(framey_call(
                           {'id':999,'method':'set_setting','args':['theme','light']})['result'])
        self.assertEqual(framey_call(
                            {'id':999,'method':'get_setting','args':['theme','dark']})['result'], 'light')

        self.assertEqual(framey_call(
                            {'id':999,'method':'get_setting','args':[{'key':'theme','default':'dark'}],
                             'legacy':True})['result'], {'success':True,'result':'light'})
        self.assertEqual(framey_call(
                            {'id':999,'method':'set_setting','args':[{'key':'legacy','value':'saved'}],
                             'legacy':True})['result'], {'success':True,'result':True})
        self.assertEqual(framey_call(
                            {'id':999,'method':'get_setting','args':['legacy','default']})['result'], 'saved')

        StoreFixture.release = 1
        job = finished(ok('POST', '/api/decky/plugin',
                          {'action':'update','id':999,'acknowledged':True}))
        self.assertFalse(job.get('error'), job)
        self.assertEqual(ok('GET', '/api/decky')['plugins'][0]['version'], '1.1.0')
        status, stale_reply, _ = api('POST', '/api/framey/method',
            {'id':999,'receipt':receipt,'method':'get_setting','args':['theme','dark']})
        self.assertEqual(status, 400)
        self.assertIn('changed', str(stale_reply))
        receipt = HASHES[1]
        self.assertEqual(framey_call(
                            {'id':999,'method':'get_setting','args':['theme','dark']})['result'], 'light')
        job = finished(ok('POST', '/api/decky/plugin',
                          {'action':'remove','id':999,'acknowledged':True}))
        self.assertFalse(job.get('error'), job)
        self.assertEqual(ok('GET', '/api/decky')['plugins'], [])
        self.assertEqual(ssh('test -e ~/.local/share/frame-control/decky/plugins/sample-panel && echo yes || echo no').strip(), 'no')
        status, _, _ = api('POST', '/api/framey/method',
                           {'id':999,'method':'get_setting','args':['theme','dark']})
        self.assertEqual(status, 400)  # No method calls while the plugin is removed.
        job = finished(ok('POST', '/api/decky/plugin',
                          {'action':'install','id':999,'acknowledged':True}))
        self.assertFalse(job.get('error'), job)
        self.assertEqual(framey_call(
                            {'id':999,'method':'get_setting','args':['theme','dark']})['result'], 'light')
        stale = finished(ok('POST', '/api/decky/plugin',
                            {'action':'update','id':999,'sha256':HASHES[0],
                             'acknowledged':True}))
        self.assertIn('version changed', stale.get('error', ''))
        self.assertEqual(ok('GET', '/api/decky')['plugins'][0]['version'], '1.1.0')

    def test_pinned_official_plugins_install_and_remove(self):
        self.backend()
        catalog = {plugin['id']:plugin for plugin in ok('GET', '/api/decky/store')['plugins']}
        for plugin in OFFICIAL_PLUGINS:
            with self.subTest(plugin=plugin['name']):
                self.assertEqual(catalog[plugin['id']]['sha256'], plugin['sha256'])
                job = finished(ok('POST', '/api/decky/plugin',
                                  {'action':'install','id':plugin['id'],'acknowledged':True}))
                self.assertFalse(job.get('error'), job)
                found = [item for item in ok('GET', '/api/decky')['plugins']
                         if item['storeId'] == plugin['id']]
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0]['version'], plugin['version'])
                installed = f"~/.local/share/frame-control/decky/plugins/{plugin['folder']}"
                with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                    expected = hashlib.sha256(bundle.read(plugin['folder']+'/dist/index.js')).hexdigest()
                self.assertEqual(ssh(f'sha256sum {installed}/dist/index.js').split()[0], expected)
                self.assertEqual(json.loads(ssh(f'cat {installed}/plugin.json')).get('api_version', 'legacy'), plugin['api_version'])
                if plugin['id'] == 96:
                    self.assertEqual(found[0]['compatShims'], ['simple-timer-lifecycle'])
                    self.assertEqual(found[0]['compatibility']['status'], 'works')
                if plugin['id'] == 135:
                    chunk = 'chunks/pluginApi-B8sV7970.js'
                    with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                        expected_chunk = bundle.read(plugin['folder']+'/dist/'+chunk)
                    self.assertEqual(
                        ssh(f'sha256sum {installed}/dist/{chunk}').split()[0],
                        hashlib.sha256(expected_chunk).hexdigest())
                if plugin['id'] == 60:
                    self.assertEqual(json.loads(ssh(f'cat {installed}/plugin.json'))['flags'], [])
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['deckyfileserver-user-native'])
                    import frame_decky_store
                    arch = ssh('uname -m').strip()
                    self.assertEqual(ssh(f'sha256sum {installed}/bin/backend').split()[0],
                                     frame_decky_store.FILESERVER_BINARIES[arch])
                if plugin['id'] == 53:
                    self.assertEqual(ssh(f'test -f {installed}/py_modules/click.py && echo yes').strip(), 'yes')
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['shotty-click-app-dir'])
                if plugin['id'] == 89:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['deckyspy-psutil-and-battery'])
                    self.assertEqual(ssh(f'test -f {installed}/py_modules/psutil/_psutil_linux.abi3.so && test -f {installed}/py_modules/framey_battery.py && echo yes').strip(), 'yes')
                if plugin['id'] in (12, 111):
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['music-control-system-dbus-env'])
                job = finished(ok('POST', '/api/decky/plugin',
                                  {'action':'remove','id':plugin['id'],'acknowledged':True}))
                self.assertFalse(job.get('error'), job)
                self.assertFalse(any(item['storeId'] == plugin['id']
                                     for item in ok('GET', '/api/decky')['plugins']))
