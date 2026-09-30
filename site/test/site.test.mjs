import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import vm from "node:vm";

const script = await readFile(new URL("../public/js/site.js", import.meta.url), "utf8");
const html = await readFile(new URL("../public/index.html", import.meta.url), "utf8");

function visit(platform, userAgent = "", maxTouchPoints = 0, hash = "") {
  const label = { textContent: "Get started — download the app" };
  const hero = { href: "#download", querySelector: () => label };
  const answer = { open: false };
  const listeners = {};
  const context = {
    navigator: { platform, userAgent, maxTouchPoints },
    location: { hash },
    window: { addEventListener: (event, handler) => { listeners[event] = handler; } },
    document: {
      addEventListener: (event, handler) => { listeners[`document-${event}`] = handler; },
      querySelectorAll: () => [],
      querySelector: () => null,
      getElementById: (id) => id === "hero-download" ? hero : id === "mac-first-launch" ? { closest: () => answer } : null,
    },
  };
  vm.runInNewContext(script, context);
  return { hero, label, answer, listeners, context };
}

test("desktop hero leads to opening instructions rather than a bare package", () => {
  for (const [platform, name] of [["MacIntel", "macOS (Apple Silicon)"], ["Win32", "Windows"], ["Linux x86_64", "Linux"], ["Linux aarch64", "Linux (arm64)"]]) {
    const page = visit(platform);
    assert.equal(page.hero.href, "#download");
    assert.equal(page.label.textContent, `Get started on ${name}`);
  }
});

test("phones and touch-enabled iPads are not offered a desktop package", () => {
  for (const [platform, userAgent, touches] of [["iPhone", "iPhone", 1], ["MacIntel", "Macintosh", 5], ["Linux armv8l", "Android", 1]]) {
    const page = visit(platform, userAgent, touches);
    assert.equal(page.hero.href, "#download");
    assert.equal(page.label.textContent, "Get started — download the app");
  }
});

test("first-launch links open the answer on arrival and hash navigation", () => {
  assert.equal(visit("", "", 0, "#mac-first-launch").answer.open, true);
  const page = visit("");
  page.context.location.hash = "#mac-first-launch";
  page.listeners.hashchange();
  assert.equal(page.answer.open, true);
  assert.doesNotThrow(() => visit("", "", 0, "#missing"));
});

test("clicking the same first-launch link reopens a manually closed answer", () => {
  const page = visit("", "", 0, "#mac-first-launch");
  page.answer.open = false;
  page.listeners["document-click"]({ target: { closest: () => ({ getAttribute: () => "#mac-first-launch" }) } });
  assert.equal(page.answer.open, true);
  assert.doesNotThrow(() => page.listeners["document-click"]({ target: {} }));
});

test("landing page keeps unique anchors and opening instructions for every desktop", () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const match of html.matchAll(/href="#([^"]+)"/g)) assert.ok(ids.includes(match[1]), match[1]);
  assert.match(html, /Install Frame Control on your computer, not your headset/);
  assert.match(html, /drag Frame Control to Applications/);
  assert.match(html, /launch Frame Control from Start/);
  assert.match(html, /Properties → Permissions/);
  assert.match(html, /Frame-Control-linux-arm64\.deb/);
  assert.match(html, /Not an App Store download/);
});

test("sharing metadata points to the custom domain", () => {
  assert.match(html, /rel="canonical" href="https:\/\/framecontrol\.fun\/"/);
  assert.match(html, /property="og:url" content="https:\/\/framecontrol\.fun\/"/);
  assert.match(html, /property="og:image" content="https:\/\/framecontrol\.fun\/img\/og\.jpg"/);
});

test("Linux arm64 download explains the system adb prerequisite", () => {
  assert.match(html, /On arm64 Linux, install <code>adb<\/code>/);
});

test("privacy describes released telemetry and distinguishes private app reports from public feedback", async () => {
  const privacy = await readFile(new URL("../public/privacy/index.html", import.meta.url), "utf8");
  assert.doesNotMatch(privacy, /app collects nothing|has no analytics/);
  for (const text of ["on by default", "PostHog", "random persistent installation ID", "Privacy &amp; updates", "off by default", "public GitHub issue", "v0.4.0/docs/privacy.md"]) {
    assert.ok(privacy.includes(text), text);
  }
});

test("compact headers retain navigation and high-contrast support text", async () => {
  const css = await readFile(new URL("../public/css/site.css", import.meta.url), "utf8");
  assert.doesNotMatch(css, /\.top nav\s*\{\s*display:\s*none/);
  assert.match(css, /\.top nav \{ order: 3; width: 100%/);
  assert.match(css, /@media \(max-width: 880px\) \{\s*\.top \{ position: static; \}/);
  assert.match(css, /\.btn\.coffee \{[^}]*color: #0e141b/);
});

test("primary button gradients keep white text above 4.5:1 contrast", async () => {
  const css = await readFile(new URL("../public/css/site.css", import.meta.url), "utf8");
  const luminance = (channels) => channels.map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
  }).reduce((total, channel, index) => total + channel * [0.2126, 0.7152, 0.0722][index], 0);
  for (const variable of ["action", "action-hi"]) {
    const value = css.match(new RegExp(`--${variable}: ([^;]+);`))[1];
    const colors = [...value.matchAll(/#([0-9a-f]{6})/g)].map((match) => [0, 2, 4].map((offset) => parseInt(match[1].slice(offset, offset + 2), 16)));
    assert.equal(colors.length, 2);
    for (let step = 0; step <= 100; step++) {
      const channels = colors[0].map((channel, index) => channel + (colors[1][index] - channel) * step / 100);
      assert.ok(1.05 / (luminance(channels) + 0.05) >= 4.5, `${variable} at ${step}%`);
    }
  }
});

test("every page versions shared assets to avoid stale onboarding behavior", async () => {
  for (const file of ["index.html", "feedback/index.html", "privacy/index.html", "404.html"]) {
    const page = await readFile(new URL(`../public/${file}`, import.meta.url), "utf8");
    assert.match(page, /href="\/css\/site\.css\?v=/, file);
    assert.match(page, /src="\/js\/site\.js\?v=/, file);
  }
});
