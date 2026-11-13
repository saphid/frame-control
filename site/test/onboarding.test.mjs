import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../public/js/site.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');

function visit(navigator, hash = '') {
  const label = { textContent: 'Choose your computer’s download' };
  const hero = { href: '#download', querySelector: () => label };
  const cards = Object.fromEntries(['mac', 'windows', 'linux'].map(os => [os, {
    classes: [], classList: { add(name) { cards[os].classes.push(name); } },
    tag: { hidden: true }, querySelector() { return this.tag; },
  }]));
  const details = { tagName: 'DETAILS', open: false };
  const listeners = {};
  const context = {
    navigator, location: { hash }, window: { addEventListener: (name, fn) => { listeners[name] = fn; } },
    document: {
      querySelectorAll: () => [],
      getElementById: id => id === 'hero-download' ? hero : id === 'mac-opening' ? details : null,
      querySelector: selector => cards[selector.match(/data-os="([^"]+)"/)[1]],
    },
  };
  runInNewContext(script, context);
  return { hero, cards, details, listeners, context };
}

for (const [name, navigator, expected] of [
  ['Intel Mac', { platform: 'MacIntel', userAgent: 'Macintosh' }, 'mac'],
  ['Apple Silicon browser with Intel hint', { platform: 'MacIntel', userAgent: 'Macintosh', userAgentData: { platform: 'macOS' } }, 'mac'],
  ['Windows', { platform: 'Win32', userAgent: 'Windows NT 10.0' }, 'windows'],
  ['Linux x64', { platform: 'Linux x86_64', userAgent: 'Linux x86_64' }, 'linux'],
  ['Linux ARM', { platform: 'Linux aarch64', userAgent: 'Linux aarch64' }, 'linux'],
  ['iPhone', { platform: 'iPhone', userAgent: 'iPhone' }, null],
  ['iPad desktop mode', { platform: 'MacIntel', userAgent: 'Macintosh', maxTouchPoints: 5 }, null],
  ['Android', { platform: 'Linux armv8l', userAgent: 'Linux Android' }, null],
  ['unknown', { userAgent: '' }, null],
]) {
  test(`${name} opens choices instead of guessing an installer architecture`, () => {
    const { hero, cards } = visit(navigator);
    assert.equal(hero.href, expected ? `#download-${expected}` : '#download');
    assert.ok(html.includes(`id="${hero.href.slice(1)}"`));
    assert.deepEqual(Object.keys(cards).filter(os => !cards[os].tag.hidden), expected ? [expected] : []);
  });
}

test('opening help expands for direct and in-page links; unknown fragments are safe', () => {
  const result = visit({ userAgent: '' }, '#mac-opening');
  assert.equal(result.details.open, true);
  result.details.open = false;
  result.context.location.hash = '#unknown';
  result.listeners.hashchange();
  assert.equal(result.details.open, false);
  result.context.location.hash = '#mac-opening';
  result.listeners.hashchange();
  assert.equal(result.details.open, true);
});
