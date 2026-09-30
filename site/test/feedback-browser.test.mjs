import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import vm from "node:vm";

const script = await readFile(new URL("../public/js/feedback.js", import.meta.url), "utf8");

function load(fetchResponse) {
  const handlers = {};
  const links = [];
  const form = { elements: { os: { value: "" } }, addEventListener: (name, handler) => { handlers[name] = handler; } };
  const errorBox = { hidden: true, append: (link) => links.push(link), scrollIntoView: () => {} };
  const send = { disabled: false, textContent: "Send feedback" };
  let elapsed = 0;
  const context = {
    navigator: { userAgent: "Windows" },
    performance: { now: () => elapsed },
    URLSearchParams,
    fetch: fetchResponse,
    window: { scrollTo: () => {} },
    document: {
      getElementById: (id) => ({ feedback: form, error: errorBox, send })[id] || {},
      createElement: () => ({}),
    },
    FormData: class extends Map {
      constructor() { super(Object.entries({ kind: "question", title: "A local question", message: "This test never sends real feedback." })); }
    },
  };
  vm.runInNewContext(script, context);
  elapsed = 4000;
  return { context, handlers, links, send };
}

test("questions and general feedback are not mislabelled as bugs in GitHub fallback", () => {
  const page = load();
  for (const kind of ["question", "other"]) {
    const url = new URL(page.context.githubUrl({ kind, title: "A local question", message: "Please help" }));
    assert.equal(url.searchParams.has("template"), false);
    assert.equal(url.searchParams.get("body"), "Please help");
  }
  assert.equal(new URL(page.context.githubUrl({ kind: "bug", title: "A bug", message: "Details" })).searchParams.get("template"), "bug.yml");
  assert.equal(new URL(page.context.githubUrl({ kind: "idea", title: "An idea", message: "Details" })).searchParams.get("template"), "idea.yml");
});

test("an unconfirmed send points to recent issues rather than creating a duplicate", async () => {
  const page = load(async () => ({ ok: false, status: 502, json: async () => ({ error: "Could not confirm delivery", retrySafe: false }) }));
  await page.handlers.submit({ preventDefault: () => {} });
  assert.equal(page.links[0].href, "https://github.com/saphid/frame-control/issues");
  assert.equal(page.send.disabled, false);
});

test("a browser network failure also points to recent issues", async () => {
  const page = load(async () => { throw new Error("Local offline test"); });
  await page.handlers.submit({ preventDefault: () => {} });
  assert.equal(page.links[0].href, "https://github.com/saphid/frame-control/issues");
});

test("known-unsent integration errors retain the prefilled issue fallback", async () => {
  const page = load(async () => ({ ok: false, status: 503, json: async () => ({ error: "Not connected", retrySafe: true }) }));
  await page.handlers.submit({ preventDefault: () => {} });
  const url = new URL(page.links[0].href);
  assert.equal(url.pathname, "/saphid/frame-control/issues/new");
  assert.equal(url.searchParams.get("body"), "This test never sends real feedback.");
});
