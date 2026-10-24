// Run the actual wired-doctor page script without browser or device I/O.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor() { this.value = ''; this.disabled = false; this.textContent = ''; this.children = []; }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
}
const elements = Object.fromEntries(['back','alias','check','message','results'].map(id => [id, new Element()]));
elements.alias.value = 'frame';
const requests = [];
let respond;
const context = vm.createContext({
  document: {getElementById: id => elements[id], createElement: () => new Element()},
  URLSearchParams, location: {search: '?key=test-key'},
  fetch: (url, options) => { requests.push({url, options}); return new Promise(resolve => {respond = resolve;}); },
});
const source = readFileSync(new URL('../../ui/wired-doctor.html', import.meta.url), 'utf8');
vm.runInContext(source.match(/<script>([\s\S]*)<\/script>/)[1], context);
assert.equal(requests.length, 0, 'page load must not probe the PC or Frame');
assert.equal(elements.back.href, '/?key=test-key#devices');
let promise = elements.check.onclick();
assert.equal(elements.check.disabled, true);
assert.equal(requests[0].url, '/api/host/wired?alias=frame');
assert.equal(requests[0].options.headers['X-Frame-UI'], 'test-key');
respond({ok: true, json: async () => ({state: 'unknown', checks: [{title: '<script>bad</script>',status: 'unknown',detail: 'No known route'}]})});
await promise;
assert.equal(elements.results.children.length, 1);
assert.equal(elements.results.children[0].children[0].textContent, '<script>bad</script>', 'device text must stay plain text');
assert.equal(elements.check.disabled, false);
promise = elements.check.onclick();
assert.equal(elements.results.children.length, 0, 'stale result cleared before retry');
respond({ok: false, json: async () => ({error: 'PC route unavailable'})});
await promise;
assert.match(elements.message.textContent, /route unavailable/);
assert.equal(elements.results.children.length, 0);
assert.equal(elements.check.disabled, false);
console.log('wired doctor UI: on-demand, escaped data, stale-result clearing and retry passed');
