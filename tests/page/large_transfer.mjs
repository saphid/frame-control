// Exercise the real page functions for desktop direct copy and browser size guard.
import { readFileSync } from "fs";
import assert from "node:assert/strict";

const src = readFileSync(new URL("../../ui/index.html", import.meta.url), "utf8");
const lines = src.split("\n");
function grab(name) {
  const start = lines.findIndex(line => line.startsWith(`function ${name}(`));
  assert.notEqual(start, -1, `${name} exists`);
  let depth = 0;
  for (let i = start; i < lines.length; i++) {
    for (const c of lines[i]) depth += c === "{" ? 1 : c === "}" ? -1 : 0;
    if (depth === 0) return lines.slice(start, i + 1).join("\n");
  }
  throw new Error(`${name} is unbalanced`);
}

const calls = [];
const copy = new Function("api", "upload", grab("copyToDownloads") + "\nreturn copyToDownloads;")(
  async (...args) => { calls.push(["api", ...args]); return { message: "sent" }; },
  async (...args) => { calls.push(["upload", ...args]); return { message: "uploaded" }; });
const large = { name: "usb-file.bin", size: 27 * 1024 ** 3 };
assert.deepEqual(await copy(large, "/media/usb/usb-file.bin", "frame-a"), { message: "sent" });
assert.deepEqual(calls.pop(), ["api", "/api/transfer", { action: "copy-local", path: "/media/usb/usb-file.bin" }, "frame-a"]);
assert.deepEqual(await copy({ name: "small.bin", size: 100 }, "", "frame-a"), { message: "uploaded" });
assert.deepEqual(calls.pop(), ["upload", { name: "small.bin", size: 100 }, "push", "frame-a"]);

let opened = false;
const browserUpload = new Function("XMLHttpRequest", grab("upload") + "\nreturn upload;")(
  class { constructor() { opened = true; } });
await assert.rejects(browserUpload(large, "push", "frame-a"), /limited to 8 GiB/);
assert.equal(opened, false, "oversized browser file is refused before creating a request");
console.log("ok");
