const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { preferenceStore } = require("../preferences");

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "frame-preferences-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return path.join(dir, "client-preferences.json");
}

test("desktop packaging includes every local application module dependency", () => {
  const root = path.resolve(__dirname, "..");
  const packaged = new Set(require("../package.json").build.files);
  for (const file of ["main.js", "preload.js"]) {
    const source = fs.readFileSync(path.join(root, file), "utf8");
    for (const match of source.matchAll(/require\(["'](\.\/[^"']+)["']\)/g)) {
      const target = match[1].slice(2) + ".js";
      assert.ok(packaged.has(target), `${file} needs packaged ${target}`);
    }
  }
});

test("client choices survive a new native session and local server origin", t => {
  const file = fixture(t);
  const first = preferenceStore(file);
  assert.deepEqual(first.read(), {});
  first.write("mvSeparate", "0");
  first.write("padUsed", "1");
  // A new process/session reads the same client store, regardless of its URL.
  const second = preferenceStore(file);
  assert.deepEqual(second.read(), { mvSeparate: "0", padUsed: "1" });
  second.write("mvSeparate", "1");
  assert.deepEqual(first.read(), { mvSeparate: "1", padUsed: "1" });
});

test("only the non-sensitive binary choices can enter the native store", t => {
  const file = fixture(t), store = preferenceStore(file);
  for (const [key, value] of [["token", "secret"], ["__proto__", "1"], ["padUsed", true], ["mvSeparate", "yes"]]) {
    assert.throws(() => store.write(key, value), /Invalid preference/);
  }
  assert.equal(fs.existsSync(file), false);
  fs.writeFileSync(file, JSON.stringify({ token: "discard", mvSeparate: "0", padUsed: 1 }));
  assert.deepEqual(store.read(), { mvSeparate: "0" });
  store.write("padUsed", "1");
  assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf8")), { mvSeparate: "0", padUsed: "1" });
});

test("a missing or damaged preference file retains usable defaults", t => {
  const file = fixture(t), store = preferenceStore(file);
  assert.deepEqual(store.read(), {});
  for (const bad of ["{broken", "null", "[]", '"text"']) {
    fs.writeFileSync(file, bad);
    assert.deepEqual(store.read(), {});
  }
  store.write("padUsed", "1");
  assert.deepEqual(store.read(), { padUsed: "1" });
});

test("the PC in the headset opt-in is remembered and off unless saved", t => {
  const file = fixture(t), store = preferenceStore(file);
  assert.equal(store.read().pcView, undefined);
  store.write("pcView", "1");
  assert.deepEqual(preferenceStore(file).read(), { pcView: "1" });
  assert.throws(() => store.write("pcView", "on"), /Invalid preference/);
});
