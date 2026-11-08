import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const page = readFileSync(join(root, 'ui', 'mac-view.html'), 'utf8');
const match = page.match(/function wholeWheel\(carry, dx, dy\) \{[\s\S]*?\n\}/);
assert.ok(match, 'wholeWheel is present in the viewer');
assert.match(page, /const delta = wholeWheel\(wheelCarry, e\.deltaX \* unit, e\.deltaY \* unit\)/);
assert.match(page, /if \(delta\.dx \|\| delta\.dy\)\s+send\(stamp\(\{ t: "wheel", \.\.\.delta,/,
  'only a non-zero accumulated delta is sent to the Mac');
assert.match(page, /ws\.onclose = \(\) => \{\s+dropWheelCarry\(\);/, 'a dropped connection forgets the leftover fraction');
assert.match(page, /addEventListener\("blur", \(\) => \{ dropWheelCarry\(\);/, 'losing focus forgets the leftover fraction');
const context = vm.createContext({ Math });
vm.runInContext(`${match[0]}\nglobalThis.wholeWheel = wholeWheel;`, context);
const wholeWheel = context.wholeWheel;
const plain = value => JSON.parse(JSON.stringify(value));

const down = { x: 0, y: 0 };
assert.deepEqual(plain(wholeWheel(down, 0, 0.24)), { dx: 0, dy: 0 });
assert.deepEqual(plain(wholeWheel(down, 0, 0.24)), { dx: 0, dy: 0 });
assert.deepEqual(plain(wholeWheel(down, 0, 0.24)), { dx: 0, dy: 0 });
assert.deepEqual(plain(wholeWheel(down, 0, 0.28)), { dx: 0, dy: 1 },
  'small thumbstick deltas eventually produce a non-zero wheel message');

const up = { x: 0, y: 0 };
assert.deepEqual(plain(wholeWheel(up, 0, -0.4)), { dx: 0, dy: 0 });
assert.deepEqual(plain(wholeWheel(up, 0, -0.7)), { dx: 0, dy: -1 });
assert.ok(up.y < 0 && up.y > -1, 'the unused fraction is retained');

const both = { x: 0, y: 0 };
assert.deepEqual(plain(wholeWheel(both, 1.75, -2.25)), { dx: 1, dy: -2 });
assert.deepEqual(plain(wholeWheel(both, -0.5, 0.5)), { dx: 0, dy: 0 });
assert.deepEqual(plain(wholeWheel(both, -0.5, 0.75)), { dx: 0, dy: 1 },
  'horizontal and vertical fractions accumulate independently');

// Execute the whole production viewer with an inert socket/canvas. Exercise
// registered event handlers, including unit conversion and connection reset.
const handlers = new Map(), messages = [], sockets = [];
const canvas = { width: 16, height: 9, getContext: () => ({}),
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 160, height: 90 }) };
const elements = new Map([['c', canvas]]);
const element = id => {
  if (!elements.has(id)) elements.set(id, { hidden: false, addEventListener() {} });
  return elements.get(id);
};
class Socket {
  constructor() { this.readyState = 1; sockets.push(this); }
  send(value) { messages.push(JSON.parse(value)); }
}
const viewer = vm.createContext({
  URLSearchParams, location: { search: '?codec=jpeg', host: 'fixture.invalid' },
  document: { getElementById: element, createElement: () => ({ getContext: () => null }) },
  window: {}, WebSocket: Socket, innerHeight: 900,
  performance: { now: () => 10 }, requestAnimationFrame() {},
  setTimeout() {}, clearTimeout() {}, setInterval() {}, clearInterval() {},
  addEventListener: (name, callback) => handlers.set(name, callback),
});
vm.runInContext(page.match(/<script>([\s\S]*?)<\/script>/)[1], viewer);
await Promise.resolve();
assert.equal(sockets.length, 1, 'production connect created the inert socket');
const wheel = (dx, dy, mode = 0, target = canvas) => {
  let prevented = false;
  handlers.get('wheel')({ deltaX: dx, deltaY: dy, deltaMode: mode, target,
    clientX: 80, clientY: 45, timeStamp: 2, preventDefault() { prevented = true; } });
  return prevented;
};
const wheels = () => messages.filter(m => m.t === 'wheel');
for (let n = 0; n < 4; n++) assert.equal(wheel(0, 0.25), true);
assert.equal(wheels().length, 1);
assert.deepEqual({ dx: wheels()[0].dx, dy: wheels()[0].dy }, { dx: 0, dy: 1 });
assert.equal(wheels()[0].x, 0.5); assert.equal(wheels()[0].y, 0.5);
assert.equal(wheels()[0].i, 1, 'zero-pixel events do not consume input ids');
wheel(1, -1, 1);
assert.deepEqual({ dx: wheels().at(-1).dx, dy: wheels().at(-1).dy }, { dx: 16, dy: -16 });
wheel(0, 1, 2);
assert.equal(wheels().at(-1).dy, 900, 'page units use the viewport height');
const count = wheels().length;
assert.equal(wheel(0, 10, 0, element('switchWindow')), false);
assert.equal(wheels().length, count, 'the window switch button does not scroll the host');
wheel(0, 0.75); handlers.get('blur')(); wheel(0, 0.25);
assert.equal(wheels().length, count, 'blur discards the old fraction');
assert.equal(messages.at(-1).t, 'release', 'blur still releases held input');
wheel(0, 0.5); sockets[0].onclose();
vm.runInContext('connect()', viewer); await Promise.resolve();
assert.equal(sockets.length, 2);
wheel(0, 0.25);
assert.equal(wheels().length, count, 'reconnect discards the old fraction');
wheel(0, 0.75);
assert.equal(wheels().at(-1).dy, 1);
