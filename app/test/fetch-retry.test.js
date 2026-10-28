const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const test = require('node:test');
const { get, fetchWithRetry } = require('../build/fetch-retry');

test('installer fetch recovers a dropped connection without hiding final failure', async () => {
  let calls = 0;
  const delays = [];
  const bytes = await fetchWithRetry(async () => {
    if (++calls < 3) throw new Error('socket closed');
    return Buffer.from('pinned bytes');
  }, 'https://example.invalid/package', async (ms) => delays.push(ms));
  assert.equal(bytes.toString(), 'pinned bytes');
  assert.equal(calls, 3);
  assert.deepEqual(delays, [1000, 2000]);

  calls = 0;
  await assert.rejects(fetchWithRetry(async () => {
    calls++;
    throw new Error('socket closed');
  }, 'https://example.invalid/package', async () => {}), /socket closed/);
  assert.equal(calls, 3);
});

test('installer fetch rejects permanent HTTP errors on the first attempt', async () => {
  let calls = 0;
  const missing = new Error('HTTP 404');
  missing.statusCode = 404;
  await assert.rejects(fetchWithRetry(async () => {
    calls++;
    throw missing;
  }, 'https://example.invalid/missing', async () => {}), /HTTP 404/);
  assert.equal(calls, 1);
});

test('installer fetch retries a transient HTTP response', async () => {
  let calls = 0;
  const busy = new Error('HTTP 503');
  busy.statusCode = 503;
  const bytes = await fetchWithRetry(async () => {
    if (++calls === 1) throw busy;
    return Buffer.from('pinned bytes');
  }, 'https://example.invalid/package', async () => {});
  assert.equal(bytes.toString(), 'pinned bytes');
  assert.equal(calls, 2);
});

test('installer fetch retries a response aborted after headers and partial bytes', async () => {
  let calls = 0;
  const transport = {
    get(_url, _options, callback) {
      const request = new EventEmitter();
      queueMicrotask(() => {
        const response = new EventEmitter();
        response.statusCode = 200;
        response.headers = {};
        callback(response);
        if (++calls === 1) {
          response.emit('data', Buffer.from('partial'));
          response.emit('aborted');
        } else {
          response.emit('data', Buffer.from('complete'));
          response.emit('end');
        }
      });
      return request;
    },
  };
  const bytes = await fetchWithRetry(
    (url) => get(url, 5, transport),
    'https://example.invalid/package',
    async () => {},
  );
  assert.equal(bytes.toString(), 'complete');
  assert.equal(calls, 2);
});
