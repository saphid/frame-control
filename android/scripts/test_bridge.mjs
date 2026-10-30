import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import vm from 'node:vm';

const source = await readFile(new URL('../app/src/main/res/raw/android_bridge.js', import.meta.url), 'utf8');
async function scenario(failAt = Infinity) {
  const listeners = {};
  let active = null, started = 0, complete = 0, fetched = 0, aborted = 0, maximumChunk = 0;
  const bytes = Buffer.alloc(192 * 1024 + 13, 42);
  const blob = new Blob([bytes], {type: 'image/png'});
  const context = vm.createContext({Blob, Uint8Array, URL, atob,
    location: {href: 'http://127.0.0.1:4567/', origin: 'http://127.0.0.1:4567'},
    document: {addEventListener: (type, f) => { listeners[type] = f; }},
    FileReader: class {
      readAsDataURL(b) { b.arrayBuffer().then(data => { this.result = `data:;base64,${Buffer.from(data).toString('base64')}`; this.onload(); }); }
    },
    act: async (_label, action) => action(),
    shotBlob: async () => { assert.equal(active, null, 'previous screenshot finished before fetching the next'); fetched++; return blob; },
    api: async () => ({}),
    alert: () => assert.fail('unexpected alert'),
    fetch: async () => ({blob: async () => blob}),
  });
  context.window = context;
  context.frameAppNative = {
    postMessage: raw => {
      const m = JSON.parse(raw);
      let value = null, error;
      try {
        if (m.name === 'startSave') {
          assert.equal(active, null);
          active = {id: String(++started), data: [], offset: 0, expected: m.arg.size};
          value = active.id;
        } else if (m.name === 'saveChunk') {
          assert.equal(m.arg.token, active.id);
          if (started === failAt) throw new Error('disk full');
          assert.equal(m.arg.offset, active.offset);
          const chunk = Buffer.from(m.arg.data, 'base64');
          maximumChunk = Math.max(maximumChunk, chunk.length);
          assert.ok(chunk.length <= 192 * 1024);
          active.data.push(chunk); active.offset += chunk.length;
        } else if (m.name === 'finishSave') {
          assert.equal(active.offset, active.expected);
          assert.deepEqual(Buffer.concat(active.data), bytes);
          active = null; complete++;
        } else if (m.name === 'abortSave') {
          assert.equal(m.arg.token, active.id); active = null; aborted++;
        } else assert.fail(m.name);
      } catch (e) { error = e.message; }
      setImmediate(() => context.frameAppNative.onmessage({data: JSON.stringify({id: m.id, value, error})}));
    },
  };
  vm.runInContext(source, context);
  listeners.DOMContentLoaded();
  const list = Array.from({length: 51}, (_, id) => ({id, file: `${id}.png`}));
  if (failAt === Infinity) {
    const result = await context.saveShots(list, null);
    assert.match(result.message, /Saved 51 images/);
    assert.equal(complete, 51); assert.equal(fetched, 51); assert.equal(maximumChunk, 192 * 1024);
    // The blob download path uses the same bounded writer, but chooses a document.
    await context.frameAndroidDownloadBlob('blob:http://127.0.0.1:4567/example');
    assert.equal(complete, 52);
    assert.equal(aborted, 0);
  } else {
    await assert.rejects(context.saveShots(list, null), /Saved 21 of 51 images. disk full/);
    assert.equal(complete, 21); assert.equal(fetched, 22); assert.equal(aborted, 1); assert.equal(active, null);
  }
}
await scenario();
await scenario(22);
console.log('PASS: 51-image sequential save, 192-KiB chunk integrity, interrupted batch, blob download');
