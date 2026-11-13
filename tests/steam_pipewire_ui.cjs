const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../ui/index.html'), 'utf8');
const code = html.split('// Local Steam helper: never start')[1].split('// ---- shared destinations')[0];

function fixture() {
  const elements = new Map(), requests = [];
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {disabled:true, textContent:''});
    return elements.get(id);
  };
  const ctx = {$, api:(url, body) => new Promise((resolve, reject) => requests.push({url, body, resolve, reject}))};
  vm.createContext(ctx);
  vm.runInContext('// never start' + code, ctx);
  return {ctx, $, requests};
}

test('navigation reads status; only clicks request launch or permission UI', async () => {
  const {ctx, $, requests} = fixture();
  assert.equal(requests.length, 0);
  const load = ctx.loadSteamPipewire();
  assert.equal(requests[0].url, '/api/steam-pipewire');
  assert.equal(requests[0].body, undefined);
  requests[0].resolve({available:true, guidance:'Verify the Steam session'});
  await load;
  assert.equal($('steamPipewireLaunch').disabled, false);
  assert.equal($('steamPipewireGuidance').textContent, 'Verify the Steam session');
  const launch = $('steamPipewireLaunch').onclick();
  assert.deepEqual(JSON.parse(JSON.stringify(requests[1].body)), {action:'launch', confirmed:true});
  assert.equal($('steamPipewireReset').disabled, true);
  await $('steamPipewireReset').onclick(); // repeated action suppressed
  assert.equal(requests.length, 2);
  requests[1].reject(new Error('Exit Steam first'));
  await launch;
  assert.equal($('steamPipewireStatus').textContent, 'Exit Steam first');
  const reset = $('steamPipewireReset').onclick();
  assert.deepEqual(JSON.parse(JSON.stringify(requests[2].body)), {action:'permissions', confirmed:true});
  requests[2].resolve({reset:false, opened:true, message:'No permission was changed'});
  await reset;
  assert.equal($('steamPipewireStatus').textContent, 'No permission was changed');
});

test('unsupported status and read failure keep actions disabled', async () => {
  const {ctx, $, requests} = fixture();
  const load = ctx.loadSteamPipewire();
  requests[0].resolve({available:false, reason:'Local Wayland required'});
  await load;
  assert.equal($('steamPipewireLaunch').disabled, true);
  assert.equal($('steamPipewireReset').disabled, true);
  assert.equal($('steamPipewireStatus').textContent, 'Local Wayland required');
  const retry = ctx.loadSteamPipewire();
  requests[1].reject(new Error('Unavailable'));
  await retry;
  assert.equal($('steamPipewireLaunch').disabled, true);
});

test('stale status cannot overwrite an action result', async () => {
  const {ctx, $, requests} = fixture();
  const load = ctx.loadSteamPipewire();
  const reset = ctx.steamPipewireAction('permissions');
  requests[1].resolve({message:'No permission was changed'});
  await reset;
  requests[0].resolve({available:true});
  await load;
  assert.equal($('steamPipewireStatus').textContent, 'No permission was changed');
});


test('Tools navigation opens the separate Steam panel without starting PC capture', () => {
  const {workspaceFixture} = require('./workspace_fixture.cjs');
  const f = workspaceFixture();
  f.navigate('#steamPipewire');
  assert.equal(f.activePage, 'tools');
  assert.equal(f.el('steamPipewire').hidden, false);
  assert.equal(f.el('macview').hidden, true);
  assert.ok(f.calls.some(call => call[0] === 'steam-pipewire'));
  assert.ok(!f.calls.some(call => call[0] === 'macview'));
  assert.match(html, /\$\("steamPipewireLink"\)\.hidden = h.mobile \|\| h.os !== "Linux"/);
});
