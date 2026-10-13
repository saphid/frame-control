// The store's "Add a source" login handling and GitHub token field, run in node against
// the real functions from ui/index.html. A login typed into the address must leave the
// address field (into the login fields) before anything is sent, and stay out of it.
import { readFileSync } from "fs";
const src = readFileSync(new URL("../../ui/index.html", import.meta.url), "utf8");
const lines = src.split("\n");
const fail = msg => { console.log("FAIL " + msg); process.exit(1); };

function grab(name) {
  const start = lines.findIndex(l => new RegExp(`^(?:(?:async )?function ${name}\\(|const ${name} = )`).test(l));
  if (start < 0) fail(`no top-level ${name} in index.html`);
  let depth = 0;
  for (let i = start; i < lines.length; i++) {
    for (const c of lines[i]) depth += c === "{" ? 1 : c === "}" ? -1 : 0;
    if (depth <= 0) return lines.slice(start, i + 1).join("\n") + "\n";
  }
  fail(`unbalanced ${name}`);
}
const { moveLogin, sourceToken } = new Function(
  "const esc = s => String(s).replace(/[&<>\"']/g, c => `&#${c.charCodeAt(0)};`); const storeName = s => s;\n" +
  grab("moveLogin") + grab("sourceToken") + "return { moveLogin, sourceToken };")();

function form(url, username = "", password = "") {
  const details = { open: false };
  const field = value => ({ value, closest: () => details });
  return { details, elements: { url: field(url), username: field(username), password: field(password) } };
}

let f = form("https://alice:s3cr%40t@repo.example/fdroid/repo");
moveLogin(f);
if (f.elements.url.value !== "https://repo.example/fdroid/repo") fail("address still holds the login: " + f.elements.url.value);
if (f.elements.username.value !== "alice" || f.elements.password.value !== "s3cr@t") fail("login not moved into its fields");
if (!f.details.open) fail("login fields not shown");

f = form("https://alice:fromurl@repo.example/repo", "typed", "typedpw");
moveLogin(f);
if (f.elements.url.value.includes("fromurl") || f.elements.username.value !== "typed" || f.elements.password.value !== "typedpw")
  fail("typed login replaced, or address kept the login");

// Undecodable logins and addresses the URL parser rejects still lose their login, decoded where possible.
for (const [url, address, user, pass] of [
  ["https://alice:100%done@repo.example/private/repo", "https://repo.example/private/repo", "alice", "100%done"],
  ["https:\t//alice:s3cret@repo.example/repo", "https://repo.example/repo", "alice", "s3cret"],
  ["ht\ntps://alice:s3cret@repo.example/repo", "https://repo.example/repo", "alice", "s3cret"],
  ["https:\\\\alice:s3cret@repo.example/repo", "https://repo.example/repo", "alice", "s3cret"],
  ["https:alice:s3cret@repo.example/repo", "https://repo.example/repo", "alice", "s3cret"],
  ["\u0000https://alice:s3cret@repo.example/repo", "https://repo.example/repo", "alice", "s3cret"],
  ["fdroidrepos://alice:p\\w@repo.example/repo", "fdroidrepos://repo.example/repo", "alice", "p\\w"],
  ["https://alice:%FF@repo.example/private/repo", "https://repo.example/private/repo", "alice", "%FF"],
  ["https://al%20ice:p%40ss:word@repo.example/r", "https://repo.example/r", "al ice", "p@ss:word"],
  ["https://alice:s3cret@repo example/repo", "https://repo example/repo", "alice", "s3cret"],
  ["fdroidrepos://alice:pw@repo.example/repo?fingerprint=AB", "fdroidrepos://repo.example/repo?fingerprint=AB", "alice", "pw"],
  ["https://alice@repo.example/repo", "https://repo.example/repo", "alice", ""],
]) {
  f = form(url);
  moveLogin(f);
  if (f.elements.url.value !== address) fail(`address kept the login: ${url} -> ${f.elements.url.value}`);
  if (f.elements.username.value !== user || f.elements.password.value !== pass)
    fail(`login for ${url}: ${f.elements.username.value} / ${f.elements.password.value}`);
}

for (const url of ["https://repo.example/repo", "not a url", "https://repo.example/a@b", "fdroidrepos:///a@b", "fdroidrepos:/a@b", "https://repo.example/r?x=a@b#c@d"]) {
  f = form(url);
  moveLogin(f);
  if (f.elements.url.value !== url || f.elements.username.value) fail("changed an address without a login: " + url);
}

const html = sourceToken({ id: "github", name: "GitHub releases", token: { set: true, from: "saved", rejected: true } });
if (!html.includes("rejected") || !html.includes('data-clear-token="github"')) fail("token row: " + html);
if (sourceToken({ id: "fdroid", name: "F-Droid" }) !== "") fail("token field on a source without one");
console.log("ok");
