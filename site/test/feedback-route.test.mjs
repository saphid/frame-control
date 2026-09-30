import assert from "node:assert/strict";
import { test } from "node:test";
import { onRequestPost } from "../functions/api/feedback.js";

const env = { GITHUB_TOKEN: "local-test-placeholder", GITHUB_REPO: "example/local-test" };
const input = { kind: "bug", title: "Local test report", message: "No external requests are made by these tests.", elapsed: 4000 };
const request = (origin, body = input) => new Request("https://framecontrol.fun/api/feedback", {
  method: "POST",
  headers: { "content-type": "application/json", ...(origin === undefined ? {} : { origin }) },
  body: JSON.stringify(body),
});

test("malformed and opaque Origins are rejected without throwing or contacting GitHub", async (testContext) => {
  const upstream = testContext.mock.method(globalThis, "fetch", async () => { throw new Error("Unexpected external request"); });
  for (const origin of ["not-a-url", "null", "https://other.example", "http://framecontrol.fun"]) {
    const response = await onRequestPost({ request: request(origin), env });
    assert.equal(response.status, 403, origin);
  }
  assert.equal(upstream.mock.callCount(), 0);
});

test("same-origin invalid JSON content is rejected before contacting GitHub", async (testContext) => {
  const upstream = testContext.mock.method(globalThis, "fetch", async () => { throw new Error("Unexpected external request"); });
  const response = await onRequestPost({ request: request("https://framecontrol.fun", null), env });
  assert.equal(response.status, 400);
  assert.equal(upstream.mock.callCount(), 0);
});

test("missing integration settings fail without contacting GitHub", async (testContext) => {
  const upstream = testContext.mock.method(globalThis, "fetch", async () => { throw new Error("Unexpected external request"); });
  const response = await onRequestPost({ request: request("https://framecontrol.fun"), env: {} });
  assert.equal(response.status, 503);
  assert.equal((await response.json()).retrySafe, true);
  assert.equal(upstream.mock.callCount(), 0);
});

test("GitHub network failure produces an uncertainty-aware response instead of throwing", async (testContext) => {
  testContext.mock.method(globalThis, "fetch", async () => { throw new Error("Local simulated outage"); });
  const response = await onRequestPost({ request: request("https://framecontrol.fun"), env });
  assert.equal(response.status, 502);
  assert.equal((await response.json()).retrySafe, false);
});

test("an unreadable successful GitHub response does not encourage duplicate submission", async (testContext) => {
  testContext.mock.method(globalThis, "fetch", async () => new Response("not JSON", { status: 201 }));
  const response = await onRequestPost({ request: request("https://framecontrol.fun"), env });
  assert.equal(response.status, 502);
  assert.equal((await response.json()).retrySafe, false);
});

test("successful feedback returns the created issue", async (testContext) => {
  testContext.mock.method(globalThis, "fetch", async () => Response.json({ number: 7, html_url: "https://github.com/example/local-test/issues/7" }, { status: 201 }));
  const response = await onRequestPost({ request: request("https://framecontrol.fun"), env });
  assert.equal(response.status, 201);
  assert.deepEqual(await response.json(), { ok: true, number: 7, url: "https://github.com/example/local-test/issues/7" });
});
