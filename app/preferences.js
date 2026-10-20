// Client choices live outside the local server's changing URL/origin.
const fs = require("node:fs");
const path = require("node:path");
const KEYS = ["mvSeparate", "padUsed"];
const valid = value => value === "0" || value === "1";

function preferenceStore(file) {
  function read() {
    try {
      const saved = JSON.parse(fs.readFileSync(file, "utf8"));
      if (!saved || typeof saved !== "object" || Array.isArray(saved)) return {};
      return Object.fromEntries(KEYS.filter(key => valid(saved[key])).map(key => [key, saved[key]]));
    } catch { return {}; }
  }
  function write(key, value) {
    if (!KEYS.includes(key) || !valid(value)) throw new Error("Invalid preference");
    const saved = { ...read(), [key]: value };
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const tmp = file + ".tmp";
    fs.writeFileSync(tmp, JSON.stringify(saved), { mode: 0o600 });
    fs.renameSync(tmp, file);
    return true;
  }
  return { read, write };
}

module.exports = { preferenceStore };
