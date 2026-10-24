// Production standalone scripts with deterministic DOM/network boundaries. No browser/headset.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = process.env.STANDALONE_SOURCE_ROOT || path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, 'ui', name), 'utf8');
const script = html => html.match(/<script>([\s\S]*?)<\/script>/)[1];
const tick = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };

function fixture(html) {
  const elements = new Map(), events = new Map(), requests = [];
  const document = {
    activeElement: null,
    getElementById: id => element(id),
    querySelector: selector => selector === 'main' ? element('main') : document.querySelectorAll(selector)[0],
    querySelectorAll: selector => [...elements.values()].flatMap(el => el.children).filter(el => el.matches(selector)),
    addEventListener: (name, fn) => { if (!events.has(name)) events.set(name, []); events.get(name).push(fn); },
  };
  class Element {
    constructor(id, attrs = '', text = '') {
      this.id = id; this.dataset = {}; this.children = []; this.hidden = false; this.open = false;
      this.isConnected = true; this.value = ''; this.checked = false; this.disabled = /\bdisabled\b/.test(attrs);
      this.textContent = text; this.attrs = {}; this.listeners = new Map();
      for (const [, key, value] of attrs.matchAll(/([\w-]+)="([^"]*)"/g)) {
        this.attrs[key] = value;
        if (key.startsWith('data-')) this.dataset[key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
      }
      for (const [, key] of attrs.matchAll(/\bdata-([\w-]+)(?=\s|$)/g)) if (!Object.hasOwn(this.dataset, key)) this.dataset[key] = '';
    }
    matches(s) {
      if (s === 'button:not(:disabled)') return this.tag === 'button' && !this.disabled;
      if (s.startsWith('#')) return this.id === s.slice(1);
      const data = s.match(/\[data-([\w-]+)(?:="([^"]*)")?\]/);
      if (data) return Object.hasOwn(this.dataset, data[1]) && (data[2] === undefined || this.dataset[data[1]] === data[2]);
      return false;
    }
    set innerHTML(value) {
      this.html = value;
      for (const child of this.children) { child.isConnected = false; if (document.activeElement === child) document.activeElement = null; }
      this.children = [...value.matchAll(/<(button|h2)\b([^>]*)>([\s\S]*?)<\/\1>/g)].map(([, tag, attrs, text]) => {
        const child = new Element((attrs.match(/\bid="([^"]+)"/) || [])[1], attrs, text);
        child.tag = tag; child.parent = this; return child;
      });
    }
    get innerHTML() { return this.html || ''; }
    querySelectorAll(s) { return this.children.filter(el => el.matches(s)); }
    querySelector(s) { return this.querySelectorAll(s)[0] || null; }
    contains(el) { return el === this || this.children.includes(el); }
    closest(s) { return this.matches(s) ? this : this.parent?.closest(s) || null; }
    setAttribute(k, v) { this.attrs[k] = v; }
    append(el) { el.parent = this; }
    focus() { if (!this.disabled && this.isConnected) document.activeElement = this; }
    showModal() { this.open = true; this.modalOpened = true; }
    close() { this.open = false; this.onclose?.(); }
    addEventListener(name, fn) { this.listeners.set(name, fn); }
    reset() {}
  }
  function element(id) {
    const dynamic = [...elements.values()].flatMap(el => el.children).find(el => el.id === id);
    if (dynamic) return dynamic;
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  }
  element('detail').hidden = element('kbd').hidden = true;
  document.body = element('body');
  // The sheet is stable; its contents are replaced by the production redraw.
  element('detail').contains = el => el === element('detail') || element('sheet').contains(el);
  const context = {document, location: {search: '', hash: ''}, URLSearchParams,
    window: {addEventListener: (name, fn) => events.set(name, [fn])},
    setTimeout: () => 1, clearTimeout() {}, Event: class {},
    fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})),
  };
  vm.createContext(context);
  vm.runInContext(script(html).replace('__FRAME_KEY__', JSON.stringify('ios +&?key/#')), context);
  const run = code => vm.runInContext(code, context);
  const answer = async (index, data, ok = true) => { (typeof index === 'number' ? requests[index] : index).resolve({ok, json: async () => data}); await tick(); };
  return {element, document, context, requests, run, answer, events};
}

test('Assistant Back encodes the injected key for the same-origin workspace only', () => {
  const html = read('assistant.html'), f = fixture(html);
  const back = f.element('back');
  const fallback = html.match(/<a[^>]*href="([^"]*)"[^>]*>Back to Frame Control/)[1];
  const destination = new URL(back.href || fallback, 'http://127.0.0.1:8123/assistant#confirm=private');
  assert.equal(destination.origin, 'http://127.0.0.1:8123');
  assert.equal(destination.pathname, '/');
  assert.equal(destination.hash, '');
  assert.equal(destination.searchParams.get('key'), 'ios +&?key/#');
  const index = fs.readFileSync(path.join(__dirname, '../ui/index.html'), 'utf8');
  const expression = index.match(/const UI_KEY = ([^;]+);/)[1];
  assert.equal(vm.runInNewContext(expression, {URLSearchParams, location: {search: destination.search}}), 'ios +&?key/#');
  for (const [, href] of html.matchAll(/href="(https?:[^\"]+)"/g)) assert.ok(!href.includes('key='));
  assert.match(html, /referrerpolicy="no-referrer"/);
});

test('catalogue browsing starts while installed-app discovery is still pending', async () => {
  const f = fixture(read('store.html'));
  assert.deepEqual(f.requests.map(r => r.url.split('?')[0]), ['/api/android', '/api/search']);
  await f.answer(1, {apps: [{name: 'Example Game', category: 'games', package: 'example.game',
    offers: [{source: 'test', id: 'example'}]}], sources: []});
  assert.equal(f.run('st.installedState'), 'loading');
  assert.match(f.element('content').innerHTML, /Example Game/);
  await f.answer(0, {apps: [{package: 'example.game', label: 'Example Game'}]});
  assert.match(f.element('content').innerHTML, /Installed/);
});

test('installed read failure is persistent, retry recovers, and cached entries are marked stale', async () => {
  const f = fixture(read('store.html'));
  await f.answer(1, {apps: [], sources: []});
  f.run('st.view = "installed"; render()');
  assert.doesNotMatch(f.element('content').innerHTML, /Nothing installed yet/);
  f.requests[0].reject(Error('offline')); await tick();
  assert.equal(f.run('st.installedState'), 'error');
  assert.match(f.element('content').innerHTML, /data-retry-installed/);
  assert.doesNotMatch(f.element('content').innerHTML, /Nothing installed yet/);
  const retry = f.element('content').querySelector('[data-retry-installed]');
  for (const listener of f.events.get('click')) listener({target: retry});
  assert.equal(f.requests[2].url, '/api/android');
  await f.answer(2, {apps: [{package: 'cached.app', label: 'Cached app'}]});
  assert.equal(f.run('st.installedState'), 'ready');
  const failed = f.run('loadInstalled()');
  assert.match(f.element('content').innerHTML, /last (?:known|read)|stale/i);
  f.requests[3].reject(Error('refresh failed')); await failed;
  assert.match(f.element('content').innerHTML, /Cached app/);
  assert.match(f.element('content').innerHTML, /last (?:known|read)|stale/i);
  assert.match(f.element('content').innerHTML, /data-retry-installed/);
  const empty = f.run('loadInstalled()'); await f.answer(4, {apps: []}); await empty;
  assert.match(f.element('content').innerHTML, /Nothing installed yet/);
  assert.doesNotMatch(f.element('content').innerHTML, /data-retry-installed/);
});

test('newest installed read wins over older success and failure without pruning cached data', async () => {
  const f = fixture(read('store.html'));
  f.run('st.needsData.add("new.app"); st.jobs.set("data:new.app", {done: false})');
  const newer = f.run('loadInstalled()'); await f.answer(2, {apps: [{package: 'new.app', label: 'New app'}]}); await newer;
  await f.answer(0, {apps: []});
  assert.equal(f.run('st.installed.has("new.app")'), true);
  assert.equal(f.run('st.needsData.has("new.app")'), true);
  const old = f.run('loadInstalled()'), newest = f.run('loadInstalled()');
  await f.answer(4, {apps: []}); await newest; // request 1 is the independent bootstrap catalogue search
  f.requests[3].reject(Error('late failure')); await old;
  assert.equal(f.run('st.installedState'), 'ready');
  assert.equal(f.run('st.installedError'), '');
  assert.equal(f.run('st.installed.size'), 0);
});

test('an old success cannot mask the newest failure, and malformed data is not successful empty', async () => {
  const f = fixture(read('store.html'));
  f.run('st.view = "installed"');
  const newest = f.run('loadInstalled()'); f.requests[2].reject(Error('latest offline')); await newest;
  await f.answer(0, {apps: []});
  assert.equal(f.run('st.installedState'), 'error');
  assert.equal(f.run('st.installedError'), 'latest offline');
  assert.doesNotMatch(f.element('content').innerHTML, /Nothing installed yet/);
  const malformed = f.run('loadInstalled()'); await f.answer(3, {}); await malformed;
  assert.equal(f.run('st.installedState'), 'error');
  assert.match(f.element('content').innerHTML, /data-retry-installed/);
});

test('catalogue details distinguish unknown and stale installed state', async () => {
  const f = fixture(read('store.html'));
  f.context.app = {name: 'Example', package: 'example.app', detailed: true, offers: [{source: 'test', id: 'example'}]};
  f.run('openDetail(app)');
  assert.doesNotMatch(f.element('sheet').innerHTML, /data-act="install"/);
  f.requests[0].reject(Error('offline')); await tick();
  assert.doesNotMatch(f.element('sheet').innerHTML, /data-act="install"/);
  const loaded = f.run('loadInstalled()'); await f.answer(f.requests.at(-1), {apps: []}); await loaded;
  assert.match(f.element('sheet').innerHTML, /data-act="install"/);
});

test('named native Store dialog enters, contains and restores focus across async redraws', async () => {
  const html = read('store.html');
  assert.match(html.match(/<[^>]*id="detail"[^>]*>/)[0], /<dialog\b[^>]*aria-labelledby="detailTitle"/);
  const f = fixture(html);
  await f.answer(0, {apps: []});
  f.context.app = {name: 'Example', offers: [{source: 'test', id: 'example'}]};
  f.run('st.view = "games"; st.apps = [app]; st.loading = false; render()');
  const opener = f.element('content').querySelector('[data-i="0"]'); opener.focus();
  f.run('openDetail(app)');
  assert.equal(f.element('detail').modalOpened, true);
  assert.equal(f.element('toast').parent, f.element('detail'));
  assert.equal(f.document.activeElement.id, 'detailTitle');
  const install = f.element('sheet').querySelector('[data-act="install"]'); install.focus();
  await f.answer(2, {description: 'Details arrived'}); // request 1 is bootstrap search
  assert.equal(f.document.activeElement.dataset.act, 'install');
  assert.notEqual(f.document.activeElement, install);
  const close = f.element('sheet').querySelector('[data-act="close"]'); close.focus();
  f.run('st.jobs.set("test:example", {done: false, stage: "Downloading", percent: 20}); drawDetail(); render()');
  assert.equal(f.document.activeElement.dataset.act, 'close');
  const keydown = f.element('detail').onkeydown || f.element('detail').listeners.get('keydown');
  const event = {key: 'Tab', shiftKey: false, preventDefault() {this.prevented = true;}};
  keydown(event);
  assert.equal(event.prevented, true);
  assert.equal(f.document.activeElement.dataset.act, 'close'); // only remaining action
  f.run('st.jobs.delete("test:example"); drawDetail()');
  const first = f.element('sheet').querySelector('[data-act="install"]'); first.focus();
  const reverse = {key: 'Tab', shiftKey: true, preventDefault() {this.prevented = true;}}; keydown(reverse);
  assert.equal(reverse.prevented, true); assert.equal(f.document.activeElement.dataset.act, 'close');
  first.focus(); f.run('st.jobs.set("test:example", {done: false}); drawDetail()');
  assert.equal(f.document.activeElement.dataset.act, 'close'); // focused action disappeared
  f.run('closeDetail()');
  assert.equal(f.element('detail').open, false);
  assert.equal(f.element('toast').parent, f.document.body);
  assert.equal(f.document.activeElement.dataset.i, '0');
  assert.notEqual(f.document.activeElement, opener); // render replaced the background card
});

test('dialog Retry recovers installed knowledge without losing focus, and cancel restores its opener', async () => {
  const f = fixture(read('store.html'));
  await f.answer(1, {apps: [], sources: []});
  f.context.app = {name: 'Example', detailed: true, offers: [{source: 'test', id: 'example'}]};
  f.run('st.view = "games"; st.apps = [app]; render()');
  const opener = f.element('content').querySelector('[data-i="0"]'); opener.focus();
  f.run('openDetail(app)');
  f.requests[0].reject(Error('offline')); await tick();
  const retry = f.element('sheet').querySelector('[data-retry-installed]'); retry.focus();
  for (const listener of f.events.get('click')) listener({target: retry});
  assert.equal(f.document.activeElement.dataset.act, 'close');
  await f.answer(f.requests.at(-1), {apps: []});
  assert.equal(f.document.activeElement.dataset.act, 'close');
  assert.match(f.element('sheet').innerHTML, /data-act="install"/);
  const cancel = {preventDefault() {this.prevented = true;}};
  f.element('detail').oncancel(cancel);
  assert.equal(cancel.prevented, true); assert.equal(f.element('detail').open, false);
  assert.equal(f.document.activeElement.dataset.i, '0');
  // Removing the app while details are open falls back to Search on close.
  f.run('openDetail(app); st.apps = []; render(); closeDetail()');
  assert.equal(f.document.activeElement, f.element('q'));
});
