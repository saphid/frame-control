"""Send to Frame groups Android files and keeps normal file/title routing (#102)."""
import sandbox  # noqa: F401
from pathlib import Path
import shutil
import subprocess
import unittest

PAGE = (Path(__file__).resolve().parents[1] / 'ui/index.html').read_text(encoding='utf-8')


@unittest.skipUnless(shutil.which('node'), 'Node runs the page functions')
class SendFiles(unittest.TestCase):
    def run_page(self, checks):
        routing = PAGE[PAGE.index('const TITLE_EXT ='):PAGE.index('// ---- sideloaded titles')]
        action = PAGE[PAGE.index('async function act('):PAGE.index('function setConn(')]
        setup = r'''
const assert = require('node:assert/strict');
const calls = [], logs = [], toasts = [];
const window = {connDevice: 'frame-a'};
const elements = new Map();
const $ = id => {if (!elements.has(id)) elements.set(id, {value: id === 'apkDisplay' ? 'vr' : '', textContent: ''}); return elements.get(id);};
const log = (message, kind) => logs.push({message, kind});
const toast = (message, error) => toasts.push({message, error});
const refresh = () => calls.push(['refresh']);
let result = {message: 'Imported', apps: [{package: 'org.example.game'}], needs_game_data: false};
const api = async (path, body, dev) => {calls.push(['api', path, body, dev]); return result;};
let upload = async (file, mode, dev) => {
  calls.push(['upload', file.name, mode, dev]); return {token: 'token-' + file.name};
};
const runJob = async (label, key, start) => start();
const offerTest = async app => calls.push(['test', app.package]);
const sideload = async file => calls.push(['title', file.name]);
const file = name => ({name, size: 10});
'''
        script = setup + action + routing + '\n(async () => {\n' + checks + r'''
})().catch(e => {console.error(e); process.exitCode = 1;});
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_companion_files_and_splits_are_one_import_not_separate_installs(self):
        self.run_page(r'''
  await sendFiles(['main.42.org.example.game.obb', 'base.apk', 'split.apk'].map(file));
  assert.deepEqual(calls.filter(c => c[0] === 'upload').map(c => c.slice(1)), [
    ['main.42.org.example.game.obb', 'android', 'frame-a'],
    ['base.apk', 'android', 'frame-a'], ['split.apk', 'android', 'frame-a']]);
  const imports = calls.filter(c => c[0] === 'api' && c[2].action === 'import');
  assert.equal(imports.length, 1);
  assert.deepEqual(imports[0][2], {action: 'import', display: 'vr',
    tokens: ['token-main.42.org.example.game.obb', 'token-base.apk', 'token-split.apk']});
  assert.equal(imports[0][3], 'frame-a');
  assert.equal(calls.filter(c => c[0] === 'test').length, 1);
''')

    def test_bundle_formats_use_android_import_and_pending_data_does_not_offer_test(self):
        self.run_page(r'''
  result.needs_game_data = true; result.message = 'Start the game, then drop again';
  await sendFiles(['game.XAPK', 'game.APKS', 'game.apkm'].map(file));
  assert.equal(calls.filter(c => c[0] === 'upload' && c[2] === 'android').length, 3);
  assert.equal(calls.filter(c => c[0] === 'test').length, 0);
  assert.equal($('androidImportState').textContent, result.message);
''')

    def test_normal_file_and_pc_title_routes_survive(self):
        self.run_page(r'''
  await sendFiles(['game.apk', 'notes.txt', 'pc.zip'].map(file));
  assert.ok(calls.some(c => c[0] === 'upload' && c[1] === 'notes.txt' && c[2] === 'push'));
  assert.ok(calls.some(c => c[0] === 'title' && c[1] === 'pc.zip'));
  assert.equal($('fileInput').value, '');
''')

    def test_upload_failure_discards_previous_tokens_without_installing(self):
        self.run_page(r'''
  const originalUpload = upload;
  upload = async (file, mode, dev) => {if (file.name === 'base.apk') throw new Error('transfer failed'); return originalUpload(file, mode, dev);};
  await sendFiles(['main.42.org.example.game.obb', 'base.apk'].map(file));
  assert.equal(calls.filter(c => c[0] === 'api' && c[2].action === 'import').length, 0);
  assert.ok(calls.some(c => c[0] === 'api' && c[2].action === 'discard' && c[2].tokens.length === 1));
  assert.match(toasts.at(-1).message, /transfer failed/);
''')

    def test_empty_companion_is_rejected_before_any_upload_in_either_order(self):
        self.run_page(r'''
  for (const files of [[file('base.apk'), {name: 'main.7.org.example.game.obb', size: 0}],
                       [{name: 'main.7.org.example.game.obb', size: 0}, file('base.apk')]]) {
    calls.length = 0;
    await sendFiles(files);
    assert.equal(calls.filter(c => c[0] === 'upload' || c[0] === 'api').length, 0);
    assert.match(toasts.at(-1).message, /main\.7\.org\.example\.game\.obb.*empty/);
  }
''')

    def test_switch_during_upload_cannot_import_to_new_headset(self):
        self.run_page(r'''
  const originalUpload = upload;
  upload = async (...args) => {const r = await originalUpload(...args); window.connDevice = 'frame-b'; return r;};
  await sendFiles([file('game.xapk')]);
  assert.equal(calls.filter(c => c[0] === 'api' && c[2].action === 'import').length, 0);
  assert.match(toasts.at(-1).message, /Switched headsets/);
''')

    def test_aab_is_explained_as_a_publishing_format(self):
        self.run_page(r'''
  await sendFiles([file('game.aab')]);
  assert.deepEqual(calls, [['refresh']]);
  assert.match(toasts.at(-1).message, /publishing file/);
  assert.equal(toasts.at(-1).error, true);
''')
