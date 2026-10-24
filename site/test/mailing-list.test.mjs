import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { onRequestPost, onRequest } from "../functions/api/mailing-list.js";

const choice = (over = {}) => ({ token: "a".repeat(64), rev: 1, email: "me@example.com", updates: true, ...over });
const request = (body, headers = {}) => new Request("https://framecontrol.fun/api/mailing-list", {
  method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(body),
});
const call = (body, env = {}, headers) => onRequestPost({ request: request(body, headers), env });

// Execute the actual D1 SQLite statements and migration, rather than mirroring
// their conflict handling in a mock. No Cloudflare account or network needed.
function database(t) {
  const dir = mkdtempSync(join(tmpdir(), "frame-mailing-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, "list.sqlite");
  const sql = (query, args = []) => {
    const result = spawnSync("python3", ["-c", `
import json, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
query, args = json.loads(sys.stdin.read())
rows = db.execute(query, args).fetchall()
db.commit()
print(json.dumps(rows))
`, file], { input: JSON.stringify([query, args]), encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    return JSON.parse(result.stdout);
  };
  sql(readFileSync(new URL("../migrations/mailing-list/0001_subscribers.sql", import.meta.url), "utf8"));
  return { sql, prepare: query => ({ bind: (...args) => ({ run: async () => sql(query, args) }) }) };
}

test("stores one current choice; retries and delayed joins cannot undo a withdrawal", async t => {
  const db = database(t), env = { MAILING_LIST: db };
  assert.equal((await call(choice(), env)).status, 200);
  assert.equal((await call(choice(), env)).status, 200);
  assert.deepEqual(db.sql("SELECT rev, email FROM mailing_list"), [[1, "me@example.com"]]);
  await call(choice({ rev: 3, email: "", updates: false }), env);
  await call(choice({ rev: 2, email: "old@example.com" }), env);
  assert.deepEqual(db.sql("SELECT rev, email FROM mailing_list"), [[3, null]]);
  await call(choice({ rev: 4, email: "new@example.com" }), env);
  assert.deepEqual(db.sql("SELECT rev, email FROM mailing_list"), [[4, "new@example.com"]]);
  assert.notEqual(db.sql("SELECT subscriber_id FROM mailing_list")[0][0], choice().token);
});

test("each app capability only changes its own row", async t => {
  const db = database(t), env = { MAILING_LIST: db };
  await call(choice(), env);
  await call(choice({ token: "b".repeat(64), email: "other@example.com" }), env);
  await call(choice({ rev: 2, email: "", updates: false }), env);
  assert.deepEqual(db.sql("SELECT email FROM mailing_list WHERE email IS NOT NULL"), [["other@example.com"]]);
});

test("requires a valid email and explicit boolean consent before storing anything", async () => {
  let writes = 0;
  const env = { MAILING_LIST: { prepare() { writes++; throw new Error(); } } };
  for (const invalid of [null, {}, choice({ updates: "true" }), choice({ updates: false }),
    choice({ email: "", updates: true }), choice({ email: "invalid" }),
    choice({ token: "guess" }), choice({ token: ["a".repeat(64)] }), choice({ rev: 0 }), choice({ rev: 1.5 }),
    choice({ email: "x".repeat(255) + "@example.com" })]) {
    assert.equal((await call(invalid, env)).status, 400);
  }
  assert.equal(writes, 0);
});

test("rejects browser origins, oversized bodies, malformed JSON and wrong methods", async () => {
  const env = { MAILING_LIST: {} };
  assert.equal((await call(choice(), env, { origin: "https://elsewhere.example" })).status, 403);
  assert.equal((await call(choice({ padding: "x".repeat(3000) }), env)).status, 413);
  assert.equal((await call(choice(), env, { "content-type": "text/plain" })).status, 415);
  const bad = new Request("https://framecontrol.fun/api/mailing-list", {
    method: "POST", body: "{bad", headers: { "content-type": "application/json" },
  });
  assert.equal((await onRequestPost({ request: bad, env })).status, 400);
  assert.equal(onRequest().status, 405);
});

test("unconfigured or unavailable storage fails safely without personal data in errors", async () => {
  assert.equal((await call(choice())).status, 503);
  const result = await call(choice(), { MAILING_LIST: { prepare() { throw new Error("private database details"); } } });
  assert.equal(result.status, 503);
  const body = await result.text();
  assert.doesNotMatch(body, /me@example|aaaa|private database/);
});

test("uses the existing salted rate-limit store and refuses bursts", async () => {
  const keys = [], writes = [];
  const env = {
    GITHUB_TOKEN: "test-salt",
    FEEDBACK_RL: { get: async key => { keys.push(key); return "30"; }, put: async () => {} },
    MAILING_LIST: { prepare: () => { writes.push(true); } },
  };
  assert.equal((await call(choice(), env, { "cf-connecting-ip": "192.0.2.8" })).status, 429);
  assert.equal(writes.length, 0);
  assert.equal(keys.length, 1);
  assert.doesNotMatch(keys[0], /192\.0\.2\.8|example|test-salt/);
});
