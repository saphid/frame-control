const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require.resolve('../ui/index.html'), 'utf8');

async function session(native, initial = {}, duringRead) {
  const saved = { ...initial }, element = { checked: true, disabled: false };
  const storage = { getItem: key => saved[key] ?? null, setItem: (key, value) => { saved[key] = String(value); } };
  for (const key of ['mvSeparate', 'padUsed']) Object.defineProperty(storage, key, {
    get: () => saved[key], set: value => { saved[key] = String(value); },
  });
  const calls = [];
  const context = vm.createContext({ window: { frameApp: native ? { preferences: native } : undefined }, localStorage: storage,
    $: () => element, log: (...args) => calls.push(args),
    api: async () => ({ state: 'off' }), padStart: () => calls.push('start'), padShow: s => calls.push(s.state) });
  const marker = html.indexOf('// ---- client preferences');
  const start = marker >= 0 ? marker : html.indexOf('$("mvSeparate").checked =');
  vm.runInContext(html.slice(start, html.indexOf('$("macview").onclick', start)), context);
  if (duringRead) duringRead(context, element);
  await vm.runInContext('typeof clientPreferences === "undefined" ? Promise.resolve() : clientPreferences.ready', context);
  return { element, saved, calls, context, async change(value) {
    element.checked = value; element.onchange({ target: element });
    await new Promise(resolve => setImmediate(resolve));
  } };
}

test('a layout choice survives moving from one native local origin to another', async () => {
  const values = {};
  const native = { read: async () => ({ ...values }), write: async (key, value) => { values[key] = value; } };
  const first = await session(native);
  await first.change(false);
  assert.equal(first.element.checked, false);
  const second = await session(native); // fresh origin storage
  assert.equal(second.element.checked, false);
});

test('native values win over stale origin values and missing values migrate', async () => {
  const values = { mvSeparate: '0' };
  const native = { read: async () => ({ ...values }), write: async (key, value) => { values[key] = value; } };
  const page = await session(native, { mvSeparate: '1', padUsed: '1' });
  assert.equal(page.element.checked, false);
  assert.equal(values.padUsed, '1');
});

test('ordinary browser storage and a failed native read retain usable choices', async () => {
  assert.equal((await session(null, { mvSeparate: '0' })).element.checked, false);
  const native = { read: async () => { throw Error('Unavailable'); }, write: async () => true };
  const page = await session(native, { mvSeparate: '0' });
  assert.equal(page.element.checked, false);
  assert.equal(page.element.disabled, false);
});

test('starting input during a native read wins over its stale remembered value', async () => {
  let resolveRead;
  const writes = [];
  const native = { read: () => new Promise(resolve => { resolveRead = resolve; }), write: async (key,value) => writes.push({key,value}) };
  const page = await session(native, {}, context => {
    vm.runInContext("clientPreferences.set('padUsed','1')",context);
    resolveRead({padUsed:'0'});
  });
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(vm.runInContext("clientPreferences.get('padUsed')",page.context),'1');
  assert.deepEqual(writes,[{key:'padUsed',value:'1'}]);
});

test('one failed migration does not hide another native preference', async () => {
  const native = {read:async()=>({padUsed:'1'}),write:async()=>{throw Error('disk unavailable');}};
  const page=await session(native,{mvSeparate:'0'});
  assert.equal(page.element.checked,false);
  assert.equal(vm.runInContext("clientPreferences.get('padUsed')",page.context),'1');
});
