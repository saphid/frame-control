const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { createObsSource } = require('../obs-source');

function fixture(prepare) {
  const states = [], children = [];
  const source = createObsSource({
    prepare: prepare || (async () => ({ executable: 'python', args: ['helper.py'], env: {} })),
    spawn(executable, args, options) {
      const child = new EventEmitter();
      child.stderr = new EventEmitter(); child.stdin = new EventEmitter();
      child.stdin.end = () => { child.stdin.writableEnded = true; };
      children.push({ child, executable, args, options }); return child;
    },
    onState: s => states.push(s),
  });
  return { source, states, children };
}

test('Stop during Python discovery cancels the pending start', async () => {
  let resolve;
  const f = fixture(() => new Promise(r => { resolve = r; }));
  const pending = f.source.start('frame', 15100);
  assert.equal(f.source.status().state, 'starting');
  f.source.stop();
  resolve({ executable: 'python', args: ['helper.py'], env: {} });
  await pending;
  assert.equal(f.children.length, 0);
  assert.equal(f.source.status().state, 'idle');
});

test('late stderr cannot undo Stop; closing allows a fresh start on another port', async () => {
  const f = fixture(); await f.source.start('frame', 15100);
  const { child, args } = f.children[0];
  assert.deepEqual(args.slice(-5), ['--frame', 'frame', '--port', '15100', '--control-stdin']);
  child.stderr.emit('data', Buffer.from('Frame Control OBS stream is '));
  child.stderr.emit('data', Buffer.from('ready\n'));
  assert.equal(f.source.status().state, 'running');
  f.source.stop();
  child.stderr.emit('data', Buffer.from('last ffmpeg warning\n'));
  assert.equal(f.source.status().state, 'stopping');
  child.emit('close', 0, null);
  assert.equal(f.source.status().state, 'idle');
  await f.source.start('other-frame', 15101);
  assert.equal(f.source.status().port, 15101);
  // An old child cannot overwrite the replacement's state.
  child.emit('close', 255, null);
  assert.equal(f.source.status().state, 'starting');
});

test('concurrent starts spawn once and preparation failures are retryable', async () => {
  let attempts = 0;
  const f = fixture(async () => {
    if (++attempts === 1) throw new Error('Python missing');
    return { executable: 'python', args: [], env: {} };
  });
  assert.equal((await f.source.start('frame')).state, 'failed');
  assert.match(f.source.status().error, /Python missing/);
  await Promise.all([f.source.start('frame'), f.source.start('frame')]);
  assert.equal(f.children.length, 1);
});

test('invalid ports and aliases cannot spawn; errors and closed pipes remain visible', async () => {
  const f = fixture();
  for (const port of [0, 1023, 65536, 15099.5, '15100']) {
    await assert.rejects(f.source.start('frame', port), /port/i);
  }
  await assert.rejects(f.source.start('-bad'), /headset/i);
  assert.equal(f.children.length, 0);
  await f.source.start('frame');
  const { child } = f.children[0];
  child.stdin.emit('error', Object.assign(new Error('closed pipe'), { code: 'EPIPE' }));
  child.stderr.emit('data', Buffer.from('network lost\n'));
  child.emit('close', 255, null);
  assert.equal(f.source.status().state, 'failed');
  assert.match(f.source.status().error, /network lost/);
});

test('an unverified host hides the controls and cannot spawn a relay', async () => {
  let spawned = false;
  const source = createObsSource({ supported: false, prepare: async () => ({}), spawn: () => { spawned = true; } });
  assert.equal(source.status().supported, false);
  await source.start('frame');
  assert.equal(spawned, false);
});
