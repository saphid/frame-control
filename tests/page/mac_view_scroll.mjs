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
