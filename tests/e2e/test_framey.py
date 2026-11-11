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

from harness import FrameTestCase, ROOT, Server, api, finished, ok, require, reset, ssh
import frame_decky_store
from framey_official import LEGACY_PLUGINS, MANAGED_FRONTENDS, PLUGINS as PANEL_PLUGINS, archive as official_archive

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
        cls.addClassCleanup(cls.fixture.server_close)
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

    def test_fake_frame_reset_clears_managed_decky_state(self):
        ssh('mkdir -p ~/.local/share/frame-control/decky/plugins/test-leftover ~/.config/systemd/user')
        ssh('touch ~/.config/systemd/user/frame-control-decky.service')
        reset()
        self.assertEqual(ssh('test -e ~/.local/share/frame-control/decky && echo yes || echo no').strip(), 'no')
        self.assertEqual(ssh('test -e ~/.config/systemd/user/frame-control-decky.service && echo yes || echo no').strip(), 'no')

    def test_store_install_update_remove_and_guards(self):
        self.backend()
        status, _, _ = api('GET', '/api/decky/store', headers={'X-Frame-UI':''})
        self.assertEqual(status, 403)
        catalogue = ok('GET', '/api/decky/store')['plugins']
        self.assertEqual((catalogue[0]['version'], catalogue[0]['sha256']), ('1.0.0', HASHES[0]))
        status, _, _ = api('POST', '/api/decky/plugin', {'action':'install','id':999})
        self.assertEqual(status, 400)  # Third-party code needs explicit acknowledgement.
        request = {'action':'install','id':999,'acknowledged':True,
                   'requestId':'0123456789abcdef' * 2}
        started = ok('POST', '/api/decky/plugin', request)
        self.assertEqual(ok('POST', '/api/decky/plugin', request)['job'], started['job'])
        status, conflict, _ = api('POST', '/api/decky/plugin', {**request, 'id':998})
        self.assertEqual(status, 409)
        self.assertIn('already used', conflict['error'])
        job = finished(started)
        self.assertFalse(job.get('error'), job)
        self.assertEqual(ok('POST', '/api/decky/plugin', request)['job'], started['job'])
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
                          {'action':'update','id':999,'installedSha256':HASHES[0],
                           'acknowledged':True}))
        self.assertFalse(job.get('error'), job)
        self.assertEqual(ok('GET', '/api/decky')['plugins'][0]['version'], '1.1.0')
        for action in ('update', 'remove'):
            stale_job = finished(ok('POST', '/api/decky/plugin',
                {'action':action,'id':999,'installedSha256':HASHES[0],
                 'acknowledged':True}))
            self.assertIn('Installed plugin changed', stale_job.get('error', ''))
            current = ok('GET', '/api/decky')['plugins'][0]
            self.assertEqual((current['version'], current['sha256']), ('1.1.0', HASHES[1]))
            self.assertIn('Sample 1.1.0', ssh('cat ~/.local/share/frame-control/decky/plugins/sample-panel/dist/index.js'))
        status, stale_reply, _ = api('POST', '/api/framey/method',
            {'id':999,'receipt':receipt,'method':'get_setting','args':['theme','dark']})
        self.assertEqual(status, 400)
        self.assertIn('changed', str(stale_reply))
        receipt = HASHES[1]
        self.assertEqual(framey_call(
                            {'id':999,'method':'get_setting','args':['theme','dark']})['result'], 'light')
        job = finished(ok('POST', '/api/decky/plugin',
                          {'action':'remove','id':999,'installedSha256':HASHES[1],
                           'acknowledged':True}))
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
                expected = MANAGED_FRONTENDS.get(plugin['id'], expected)
                self.assertEqual(ssh(f'sha256sum {installed}/dist/index.js').split()[0], expected)
                self.assertEqual(json.loads(ssh(f'cat {installed}/plugin.json')).get('api_version', 'legacy'), plugin['api_version'])
                if plugin['id'] == 123:
                    self.assertEqual(found[0]['compatShims'], ['steam-status-verified-tls', 'steam-status-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0], 'a16ab5869a93d64fb87f0cf836d98148ef83fb3000daafd32d37ee64dc1aba13')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                        hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 131:
                    self.assertEqual(found[0]['compatShims'], ['download-all-local-queue', 'download-all-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                        original = bundle.read(plugin['folder']+'/main.py')
                    prefix = b'from framey_decky_ipc import install as _framey_install_ipc_eof\n_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n'
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0], hashlib.sha256(prefix+original).hexdigest())
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                        hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 125:
                    self.assertEqual(found[0]['compatShims'], ['localsend-digest-native', 'localsend-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                        original = bundle.read(plugin['folder']+'/main.py')
                    prefix = b'from framey_decky_ipc import install as _framey_install_ipc_eof\n_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n'
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0], hashlib.sha256(prefix+original).hexdigest())
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                        hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 135:
                    self.assertEqual(found[0]['compatShims'], ['deck-shelves-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertNotIn('Update or reinstall', found[0]['compatibility']['reason'])
                    with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                        original = bundle.read(plugin['folder']+'/main.py')
                    prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                              b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     hashlib.sha256(prefix+original).hexdigest())
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 36:
                    self.assertEqual(found[0]['compatShims'], ['steamgriddb-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'broken')
                    self.assertNotIn('Update or reinstall', found[0]['compatibility']['reason'])
                    with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                        original = bundle.read(plugin['folder']+'/main.py')
                    prefix = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
                              b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     hashlib.sha256(prefix+original).hexdigest())
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 61:
                    self.assertEqual(found[0]['compatShims'], ['tabmaster-json-file-restore', 'tabmaster-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertNotIn('Update or reinstall', found[0]['compatibility']['reason'])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '68b2aa6701cc0868113f69f8cb26c0a16cd93e45876ab1deb79a5938548b439a')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 96:
                    self.assertEqual(found[0]['compatShims'], ['simple-timer-lifecycle', 'simple-timer-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '7c3b00e081dbfa602a7f811f25d3b19271b881a6fbb90d56c500ba8ea0d2598f')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 117:
                    self.assertEqual(found[0]['compatShims'], ['deckyparty-user-lifecycle', 'deckyparty-ipc-eof'])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     'ace5c277fc010ebc102ba731c479a478e11aa004f763755c8e5b298a4a2c0734')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                        helper_hash = hashlib.sha256(bundle.read('Decky-CP/bin/copyparty-sfx.py')).hexdigest()
                    self.assertEqual(ssh(f'sha256sum {installed}/bin/copyparty-sfx.py').split()[0], helper_hash)
                if plugin['id'] == 104:
                    self.assertEqual(found[0]['compatShims'], ['game-sync-bounded-selection', 'game-sync-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                    with zipfile.ZipFile(io.BytesIO(official_archive(plugin))) as bundle:
                        manager_hash = hashlib.sha256(bundle.read(plugin['folder']+'/py_modules/rclone_manager.py')).hexdigest()
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/rclone_manager.py').split()[0], manager_hash)
                if plugin['id'] == 130:
                    self.assertEqual(json.loads(ssh(f'cat {installed}/plugin.json'))['flags'], [])
                    self.assertEqual(found[0]['compatShims'], ['prefix-manager-user-paths'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
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
                    self.assertEqual(receipt['compatShims'],
                                     ['deckyfileserver-user-native', 'deckyfileserver-https-address',
                                      'deckyfileserver-directory-entry', 'deckyfileserver-ipc-eof'])
                    arch = ssh('uname -m').strip()
                    self.assertEqual(ssh(f'sha256sum {installed}/bin/backend').split()[0],
                                     frame_decky_store.FILESERVER_BINARIES[arch])
                if plugin['id'] == 68:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['wine-cellar-native-bridge', 'wine-cellar-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    arch = ssh('uname -m').strip()
                    self.assertEqual(ssh(f'sha256sum {installed}/bin/backend').split()[0],
                                     frame_decky_store.WINE_CELLAR_AARCH64 if arch == 'aarch64'
                                     else frame_decky_store.WINE_CELLAR_ORIGINAL)
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     frame_decky_store.WINE_CELLAR_MANAGED_MAIN)
                if plugin['id'] == 125:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['localsend-digest-native', 'localsend-ipc-eof'])
                    arch = ssh('uname -m').strip()
                    self.assertEqual(ssh(f'sha256sum {installed}/bin/localsend-core').split()[0],
                                     frame_decky_store.LOCALSEND_AARCH64 if arch == 'aarch64'
                                     else frame_decky_store.LOCALSEND_ORIGINAL)
                if plugin['id'] == 28:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['emuchievements-safe-arm64', 'emuchievements-ipc-eof'])
                    arch = ssh('uname -m').strip()
                    self.assertEqual(ssh(f'sha256sum {installed}/bin/hash').split()[0],
                                     frame_decky_store.EMU_BINARIES[arch])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     'c3314c4202a2523fe0d68b50683c3640ab7cd0da074364eb65a28b34c9af1d3c')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 53:
                    self.assertEqual(ssh(f'test -f {installed}/py_modules/click.py && echo yes').strip(), 'yes')
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['shotty-click-app-dir', 'shotty-bounded-copies', 'shotty-ipc-eof'])
                if plugin['id'] == 46:
                    expected_shims = ['steamback-ipc-eof']
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], expected_shims)
                    self.assertEqual(found[0]['compatShims'], expected_shims)
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '4aab5d758aceca5889427a74f4ac0edd535e018ce9a403a9abd23c2e3b8882a0')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 63:
                    expected_shims = ['free-loader-ipc-eof']
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], expected_shims)
                    self.assertEqual(found[0]['compatShims'], expected_shims)
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '1be5c28420161c97207cc52e2f32cd5a1c9a47758f9cf3963aaa36aa7e706d45')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 24:
                    expected_shims = ['radiyo-verified-tls', 'radiyo-ipc-eof']
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], expected_shims)
                    self.assertEqual(found[0]['compatShims'], expected_shims)
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '23cdff5bfa7f57e6c0341c825ab23cfb363e4408ae3c4f117fe3d1885f00a265')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 103:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['ludusavi-dependency-discovery', 'ludusavi-ipc-eof'])
                    self.assertEqual(found[0]['compatShims'], receipt['compatShims'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 143:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['desktop-apps-ipc-eof'])
                    self.assertEqual(found[0]['compatShims'], receipt['compatShims'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '6e9c31f6758299f31dbbf637d9a87c0ea94857cc1531cb9933221bc59d888aff')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 14:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['protondb-ipc-eof'])
                    self.assertEqual(found[0]['compatShims'], ['protondb-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 132:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['suggestme-verified-tls', 'suggestme-ipc-eof'])
                    self.assertEqual(found[0]['compatShims'], ['suggestme-verified-tls', 'suggestme-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0], 'e3cc595e706d79907d3c8f6203ee0b1762a015230b17b4c444974e479d5d2b95')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                        hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 79:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['notifications-private-logs'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                if plugin['id'] == 93:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['deck-settings-verified-tls', 'deck-settings-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '7fb87f779459bfe2792331c038dd026eff06122617c1b9528863d517af602ba3')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     '43ad5a8e19270347e6efaeb59ea94f06f149b525ac928e27298325c0b30500e8')
                if plugin['id'] == 52:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['game-theme-music-ipc-eof'])
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     'cfac245371ec85776983f7a5664304d84a8d406d4127cd790f154504f85b59e8')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                if plugin['id'] == 89:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['deckyspy-psutil-and-battery', 'deckyspy-ipc-eof'])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '6a6294821cf306d19191ac81edea0b5a95e87ce2065290bb851ee9e086060ac8')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                    self.assertEqual(ssh(f'test -f {installed}/py_modules/psutil/_psutil_linux.abi3.so && test -f {installed}/py_modules/framey_battery.py && echo yes').strip(), 'yes')
                if plugin['id'] == 67:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['battery-tracker-user-supply', 'battery-tracker-ipc-eof'])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     'ba50a1bc9b81547d718ff155cd6ca0bc37426ba0e9a76a68ccee437abf6a8549')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(json.loads(ssh(f'cat {installed}/plugin.json'))['flags'], [])
                if plugin['id'] == 114:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['network-sentinel-user-psutil', 'network-sentinel-ipc-eof'])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     'd4394570b110759247c731fdd55221db67875346e0e3fb23831948cad9a96891')
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                    self.assertEqual(json.loads(ssh(f'cat {installed}/plugin.json'))['flags'], ['debug'])
                    self.assertEqual(ssh(f'test -f {installed}/py_modules/psutil/_psutil_linux.abi3.so && echo yes').strip(), 'yes')
                if plugin['id'] == 23:
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['animation-preserve-overrides', 'animation-ipc-eof'])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0],
                                     '41e8b19b457fa19f7eb080736a84dac5ce05a787ff4a0279b15df0666502d068')
                    for helper in ('framey_decky_ipc.py', 'framey_animation_overrides.py'):
                        self.assertEqual(ssh(f'sha256sum {installed}/py_modules/{helper}').split()[0],
                                         hashlib.sha256((ROOT/'ui'/helper).read_bytes()).hexdigest())
                    self.assertEqual(found[0]['compatibility']['status'], 'partial')
                if plugin['id'] in (12, 111):
                    receipt = json.loads(ssh(f'cat {installed}/.frame-control-store.json'))
                    self.assertEqual(receipt['compatShims'], ['music-control-system-dbus-env', 'music-control-ipc-eof'])
                    self.assertEqual(ssh(f'sha256sum {installed}/main.py').split()[0], {
                        12: '1a1430918a2894deda35337219ad538a24b7f4278e655e3397322228679bb6a8',
                        111: '0170de1dc0da6f8520019d92858048c72827fd6755d471720884fdd346c3a791',
                    }[plugin['id']])
                    self.assertEqual(ssh(f'sha256sum {installed}/py_modules/framey_decky_ipc.py').split()[0],
                                     hashlib.sha256((ROOT/'ui/framey_decky_ipc.py').read_bytes()).hexdigest())
                job = finished(ok('POST', '/api/decky/plugin',
                                  {'action':'remove','id':plugin['id'],'acknowledged':True}))
                self.assertFalse(job.get('error'), job)
                self.assertFalse(any(item['storeId'] == plugin['id']
                                     for item in ok('GET', '/api/decky')['plugins']))
