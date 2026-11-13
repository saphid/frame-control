import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const page = readFileSync(join(root, 'ui', 'mac-view.html'), 'utf8');
const match = page.match(/function windowSwitchEvents\(hostName\) \{[\s\S]*?\n\}/);
assert.ok(match, 'viewer exposes a bounded host-specific switch sequence');
const events = vm.runInNewContext(`(${match[0]})`);
for (const [host, modifier, mod] of [
  ['mac', 'MetaLeft', 'meta'], ['windows', 'AltLeft', 'alt'],
]) {
  const sequence = JSON.parse(JSON.stringify(events(host)));
  assert.deepEqual(sequence.map(x => [x.e, x.code]),
    [['down', modifier], ['down', 'Tab'], ['up', 'Tab'], ['up', modifier]]);
  assert.deepEqual(sequence[1].mods, [mod]);
  assert.deepEqual(sequence[2].mods, [mod]);
}
assert.deepEqual(JSON.parse(JSON.stringify(events('linux'))), []);
assert.match(page, /switchButton\.hidden = !src\.startsWith\("display:"\)/);
console.log('window switch sequences passed');
