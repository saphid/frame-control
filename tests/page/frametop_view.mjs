// The Capture & Live page's third view: the Frametop desktop that runs on the Frame itself.
// Run in node against the real functions from ui/index.html with a fake Frame and a fake
// screen dropdown: screens listed by name fall back safely, an unreadable list keeps what it
// had, and Control only takes taps on the screen whose picture is showing.
import { readFileSync } from "fs";
const src = readFileSync(new URL("../../ui/index.html", import.meta.url), "utf8");
const grab = name => {
  const m = src.match(new RegExp(`(?:\\nconst ${name} = [^\\n]*\\n)|((?:async )?function ${name}\\([\\s\\S]*?\\n}\\n)`));
  if (!m) throw new Error("not found: " + name);
  return m[0];
};
// The page's scripts share one global scope, so a second copy would silently replace the
// real one: each function grabbed here must be the only definition in the page.
for (const name of ["ftScreen", "ftOff", "noFtWhy", "ftLabel", "renderFtPick", "loadFrametop", "syncFtUI", "ftEmpty", "watchFrametop", "ctrlFtTarget", "ctrlPoll"]) {
  const count = (src.match(new RegExp(`\\n(?:async )?function ${name}\\(`, "g")) || []).length;
  if (count !== 1) { console.log(`FAIL ${name} is defined ${count} times`); process.exit(1); }
}
if ((src.match(/\nconst ftUsable = /g) || []).length !== 1) { console.log("FAIL ftUsable is declared more than once"); process.exit(1); }
const fail = msg => { console.log("FAIL " + msg); process.exit(1); };
const eq = (actual, expected, msg) => { if (actual !== expected) fail(`${msg}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`); };
const ok = (cond, msg) => { if (!cond) fail(msg); };

const FT = over => Object.assign({ screens: [], pick: "", desktop: false, remote: false, why: "", loaded: false, error: "", timer: null, shown: null }, over);
const evalPage = (names, env, ret) => {
  const code = names.map(grab).join("\n");
  return new Function(...Object.keys(env), `${code}\nreturn { ${ret} };`)(...Object.values(env));
};
// Fake page DOM: the dropdown's innerHTML/value plus the controls syncFtUI touches.
function fakeDom() {
  const els = new Map();
  const $ = id => {
    if (!els.has(id)) els.set(id, { innerHTML: "", value: "", hidden: false, disabled: false, title: "", textContent: "", classList: { toggle() {} } });
    return els.get(id);
  };
  return { $, el: id => $(id) };
}
const options = html => [...html.matchAll(/<option value="([^"]*)">([^<]*)<\/option>/g)].map(m => [m[1], m[2]]);

// --- ftScreen / ftUsable ----------------------------------------------------
{
  const p = evalPage(["ftUsable", "ftScreen"], { ft: FT({ screens: [{ name: "WL-0" }, { name: "WL-1" }] }) }, "ft, ftUsable, ftScreen");
  eq(p.ftScreen().name, "WL-0", "an empty pick falls back to the first screen");
  p.ft.pick = "WL-1";
  eq(p.ftScreen().name, "WL-1", "the picked screen wins");
  p.ft.pick = "WL-9";
  eq(p.ftScreen().name, "WL-0", "a screen that went away falls back to the first");
  p.ft.screens = [];
  eq(p.ftScreen(), null, "no screens at all");
  p.ft.desktop = true; p.ft.remote = true;
  eq(p.ftUsable(), true, "a running desktop with remote access is usable");
  p.ft.remote = false;
  eq(p.ftUsable(), false, "remote access off is not usable");
  p.ft.desktop = false; p.ft.remote = true;
  eq(p.ftUsable(), false, "a desktop that isn't running is not usable");
}

// --- ftOff / noFtWhy --------------------------------------------------------
{
  const state = (over, view = "frametop") => evalPage(["ftUsable", "ftOff", "noFtWhy"], { ft: FT(over), view }, "ft, ftOff, noFtWhy");
  const cases = [
    ["not loaded yet", { loaded: false }, false, "Finding the Frame's Frametop screens…"],
    ["the first listing failed", { loaded: false, error: "Timed out talking to frame" }, true, "Couldn't read the Frame's Frametop screens: Timed out talking to frame"],
    ["desktop down", { loaded: true, desktop: false, remote: true }, true, "Frametop isn't running on the Frame."],
    ["remote access off", { loaded: true, desktop: true, remote: false }, true, "Remote access to Frametop is off."],
    ["no screens", { loaded: true, desktop: true, remote: true, screens: [] }, true, "Frametop isn't showing any screens."],
  ];
  for (const [label, over, off, why] of cases) {
    const p = state(over);
    eq(p.ftOff(), off, label + ": unusable?");
    eq(p.noFtWhy(), why, label + ": why");
  }
  const usable = state({ loaded: true, desktop: true, remote: true, screens: [{ name: "WL-0" }] });
  eq(usable.ftOff(), false, "a listed screen is usable");
  const told = state({ loaded: true, desktop: true, remote: true, why: "Frametop isn't ready yet." });
  eq(told.noFtWhy(), "Frametop isn't ready yet.", "the Frame's own reason wins");
  eq(state({ loaded: true, desktop: false }, "flat").ftOff(), false, "another view is never unusable");
}

// --- ftLabel ----------------------------------------------------------------
{
  const label = (screens, s, i) => evalPage(["ftLabel"], { ft: FT({ screens }) }, "ftLabel").ftLabel(s, i);
  eq(label([{ name: "left", width: 1920, height: 1080 }], { name: "left", width: 1920, height: 1080 }, 0),
    "Frametop screen 1 · 1920×1080", "one screen: the name adds nothing");
  eq(label([{ name: "WL-0" }, { name: "left" }], { name: "left", width: 2560, height: 1440 }, 1),
    "Frametop screen 2 · 2560×1440 (left)", "several screens: an opaque name is shown");
  eq(label([{ name: "WL-0" }, { name: "DP-1" }], { name: "DP-1", width: 2560, height: 1440 }, 1),
    "Frametop screen 2 · 2560×1440", "a connector name adds nothing");
  eq(label([{ name: "WL-0" }, { name: "WL-1" }], { name: "WL-1" }, 1),
    "Frametop screen 2", "no size when the server didn't give one");
  eq(label([{ name: "WL-0" }, { name: "right" }], { name: "right" }, 1),
    "Frametop screen 2 (right)", "a name with no size is still shown");
}

// --- renderFtPick -----------------------------------------------------------
{
  const dom = fakeDom();
  const p = evalPage(["ftLabel", "renderFtPick"], { ft: FT({ screens: [{ name: "WL-0", width: 1920, height: 1080 }, { name: "WL-1", width: 2560, height: 1440 }] }), $: dom.$, esc: s => String(s) }, "ft, renderFtPick");
  p.renderFtPick();
  eq(JSON.stringify(options(dom.el("ftPick").innerHTML)), JSON.stringify([["WL-0", "Frametop screen 1 · 1920×1080"], ["WL-1", "Frametop screen 2 · 2560×1440"]]), "options name the screens");
  eq(dom.el("ftPick").value, "WL-0", "the dropdown shows the first screen");
  eq(p.ft.pick, "WL-0", "and it becomes the pick");
  p.ft.pick = "WL-1";
  p.renderFtPick();
  eq(dom.el("ftPick").value, "WL-1", "the picked screen is kept");
  p.ft.screens = [{ name: "WL-1", width: 2560, height: 1440 }, { name: "WL-0", width: 1920, height: 1080 }];
  p.renderFtPick();
  eq(dom.el("ftPick").value, "WL-1", "a reload keeps the pick by name, not by position");
  eq(options(dom.el("ftPick").innerHTML)[0][1], "Frametop screen 1 · 2560×1440", "labels follow the new order");
  p.ft.screens = [{ name: "WL-0", width: 1920, height: 1080 }];
  p.renderFtPick();
  eq(p.ft.pick, "WL-0", "a pick that disappeared falls back to the first screen");
  eq(dom.el("ftPick").value, "WL-0", "and the dropdown follows it");
  p.ft.screens = [];
  p.renderFtPick();
  eq(dom.el("ftPick").innerHTML, "", "no screens leaves no stale options");
}

// --- syncFtUI: hidden/unusable states --------------------------------------
{
  const sync = (over, opts = {}) => {
    const dom = fakeDom(), calls = [];
    const env = {
      ft: FT(over), view: opts.view || "frametop", live: !!opts.live, $: dom.$,
      HINTS: { headset: "headset hint", flat: "desktop hint", frametop: "frametop hint" },
      rec: { state: "idle" }, ctrl: { on: !!opts.ctrlOn },
      ftEmpty: why => calls.push(["ftEmpty", why]),
      toggleLive: on => calls.push(["toggleLive", on]),
      ctrlToggle: on => calls.push(["ctrlToggle", on]),
    };
    return { ...evalPage(["ftUsable", "ftOff", "noFtWhy", "syncRecBtn", "syncFtUI"], env, "ft, syncFtUI"), el: dom.el, calls };
  };
  const down = sync({ loaded: true, desktop: false, remote: true }, { live: true, ctrlOn: true });
  down.syncFtUI();
  eq(down.el("ftPick").hidden, true, "unusable hides the screen dropdown");
  eq(down.el("shotBtn").disabled, true, "unusable disables Capture");
  eq(down.el("liveBtn").disabled, true, "unusable disables Live");
  eq(down.el("ctrlBtn").disabled, true, "unusable disables Control");
  eq(down.el("viewHint").textContent, "Frametop isn't running on the Frame.", "the why is in the hint");
  eq(JSON.stringify(down.calls[0]), JSON.stringify(["ftEmpty", "Frametop isn't running on the Frame."]), "the why fills the viewer's empty state");
  ok(down.calls.some(c => c[0] === "toggleLive" && c[1] === false), "live stops while the desktop is down");
  ok(down.calls.some(c => c[0] === "ctrlToggle" && c[1] === false), "Control stops while the desktop is down");
  eq(down.el("recBtn").title, "Record the Frametop screen, without sound, to ~/Videos/SteamFrame on this computer", "Record names the Frametop screen");

  const up = sync({ loaded: true, desktop: true, remote: true, screens: [{ name: "WL-0", width: 1920, height: 1080 }] });
  up.syncFtUI();
  eq(up.el("ftPick").hidden, false, "usable shows the screen dropdown");
  eq(up.el("shotBtn").disabled, false, "usable offers Capture");
  eq(up.el("liveBtn").disabled, false, "usable offers Live");
  eq(up.el("ctrlBtn").disabled, false, "usable offers Control");
  eq(up.el("viewHint").textContent, "frametop hint", "the usual Frametop hint when usable");

  const loading = sync({ loaded: false, screens: [] });
  loading.syncFtUI();
  eq(loading.el("ftPick").hidden, true, "no dropdown before the screens arrive");
  eq(loading.el("shotBtn").disabled, false, "Capture is offered while the first answer is on its way");

  const other = sync({ loaded: true, desktop: true, remote: true, screens: [{ name: "WL-0" }] }, { view: "flat" });
  other.syncFtUI();
  eq(other.el("ftPick").hidden, true, "the Desktop view hides the Frametop dropdown");
  eq(other.el("viewHint").textContent, "desktop hint", "the Desktop view keeps its own hint");
  eq(other.el("recBtn").title, "Record what the headset shows, with its sound, to ~/Videos/SteamFrame on this computer", "Record keeps the headset wording elsewhere");
}

// --- ftEmpty: the why where the picture would be ----------------------------
{
  const emptyHtml = "<div>Press <b>Capture</b> to see it.</div>";
  const dom = fakeDom();
  const fns = evalPage(["ftEmpty"], { $: dom.$, esc: s => String(s), FT_EMPTY_HTML: emptyHtml, ftEmptyWhy: "" }, "ftEmpty");
  fns.ftEmpty("Frametop isn't running on the Frame.");
  eq(dom.el("viewerEmpty").innerHTML, "<div>Frametop isn't running on the Frame.</div>", "the why replaces the viewer's empty state");
  dom.el("viewerEmpty").innerHTML = "painted meanwhile";
  fns.ftEmpty("Frametop isn't running on the Frame.");
  eq(dom.el("viewerEmpty").innerHTML, "painted meanwhile", "the same why isn't written again on every poll");
  fns.ftEmpty("");
  eq(dom.el("viewerEmpty").innerHTML, emptyHtml, "a usable answer restores the usual invitation");
}

// --- watchFrametop: polling only while the view is on screen ----------------
{
  const watch = (over) => {
    const dom = fakeDom();
    const cleared = [], timers = [];
    const env = {
      ft: FT(over.ft || {}), view: over.view || "frametop", document: { hidden: !!over.hidden },
      clearTimeout: id => cleared.push(id),
      setTimeout: (fn, ms) => { timers.push(ms); return 9; },
      loadFrametop: async () => {},
    };
    return { ...evalPage(["watchFrametop"], env, "ft, watchFrametop"), cleared, timers };
  };
  const flush = () => new Promise(resolve => setTimeout(resolve, 0));
  const p = watch({});
  p.ft.timer = null;
  p.watchFrametop();
  await flush();
  eq(p.timers.length, 1, "the watcher re-arms itself");
  eq(p.timers[0], 3000, "every 3 s while the page is visible");
  const hidden = watch({ hidden: true });
  hidden.watchFrametop();
  await flush();
  eq(hidden.timers[0], 10000, "every 10 s while the page is hidden");
  const other = watch({ view: "flat" });
  other.ft.timer = 9;
  other.watchFrametop();
  eq(other.timers.length, 0, "another view doesn't poll the Frametop screens");
  ok(other.cleared.includes(9), "and stops the timer it had");
}

// --- loadFrametop -----------------------------------------------------------
{
  const load = (api, over = {}, live = false) => {
    const dom = fakeDom(), logged = [], syncs = [];
    const env = {
      ft: FT(over), view: "frametop", live, $: dom.$, esc: s => String(s), api,
      log: (m, kind) => logged.push([m, kind]),
      syncFtUI: () => syncs.push("ui"), toggleLive: () => {}, ctrlShow: () => {},
    };
    return { ...evalPage(["ftUsable", "ftScreen", "ftOff", "ftLabel", "renderFtPick", "loadFrametop"], env, "ft, loadFrametop, ftOff, ftScreen"), el: dom.el, logged, syncs };
  };

  const calls = [];
  const answer = { desktop: true, remote: true, why: "", screens: [{ name: "WL-0", width: 1920, height: 1080 }, { name: "WL-1", width: 2560, height: 1440 }] };
  const p = load(async (path, body) => { calls.push([path, body]); return answer; });
  await p.loadFrametop();
  eq(calls.length, 1, "one listing request");
  eq(calls[0][0], "/api/frametop", "loadFrametop asks the Frame for its Frametop screens");
  eq(calls[0][1], undefined, "with a plain GET, no body");
  ok(p.ft.loaded, "an answer marks the screens loaded");
  eq(p.ft.error, "", "an answer clears the old error");
  eq(p.ft.screens.length, 2, "both screens are kept");
  eq(p.ft.pick, "WL-0", "the pick defaults to the first screen");
  eq(p.el("ftPick").value, "WL-0", "and the dropdown shows it");
  ok(p.syncs.length >= 1, "the UI follows the answer");

  const junk = load(async () => ({ desktop: true, remote: true, screens: [{ name: "WL-0" }, null, { width: 4 }] }));
  await junk.loadFrametop();
  eq(junk.ft.screens.length, 1, "screens without a name are dropped");
  const notList = load(async () => ({ desktop: true, remote: true, screens: "WL-0" }));
  await notList.loadFrametop();
  eq(notList.ft.screens.length, 0, "a screens list that isn't an array means no screens");

  const broken = load(async () => { throw new Error("Timed out talking to frame"); }, { screens: [{ name: "WL-0" }, { name: "WL-1" }], pick: "WL-1", loaded: true, desktop: true, remote: true });
  await broken.loadFrametop();
  eq(broken.ft.screens.length, 2, "a failed read keeps the screens it had");
  eq(broken.ft.pick, "WL-1", "and the picked screen");
  ok(broken.ft.loaded, "loaded stays true after a failed poll");
  eq(broken.ft.error, "Timed out talking to frame", "a failed read is remembered");
  eq(broken.logged.length, 1, "the first failure is logged once");
  eq(broken.logged[0][0], "Couldn't read the Frame's Frametop screens: Timed out talking to frame", "and says what failed");
  await broken.loadFrametop();
  eq(broken.logged.length, 1, "the same failure on the next poll isn't logged again");

  const stale = load(async () => { throw Object.assign(new Error("old headset"), { stale: true }); });
  await stale.loadFrametop();
  eq(stale.ft.error, "", "a stale answer says nothing about this Frame");
  eq(stale.logged.length, 0, "stale answers aren't logged");
  eq(stale.ft.loaded, false, "a stale answer doesn't mark loaded");

  const offline = load(async () => { throw Object.assign(new Error("Can't reach the Frame"), { offline: true }); });
  await offline.loadFrametop();
  eq(offline.ft.error, "Can't reach the Frame", "waiting for the Frame is shown");
  eq(offline.logged.length, 0, "waiting for the Frame isn't logged");

  const down = load(async () => ({ desktop: false, remote: false, why: "Frametop isn't running on the Frame", screens: [] }));
  await down.loadFrametop();
  eq(down.ftOff(), true, "the view is unusable once the Frame says the desktop is down");
  eq(down.ft.why, "Frametop isn't running on the Frame", "the Frame's reason is kept");
}

// --- ctrlFtTarget -----------------------------------------------------------
{
  const target = (over, live = false) => evalPage(["ftUsable", "ftScreen", "noFtWhy", "ctrlFtTarget"], { ft: FT(over), view: "frametop", live }, "ft, ctrlFtTarget");
  const usable = { loaded: true, desktop: true, remote: true, screens: [{ name: "WL-0", width: 1920, height: 1080 }] };
  eq(target({}).ctrlFtTarget().why, "Finding the Frame's Frametop screens…", "no answer yet");
  eq(target({ loaded: true, desktop: false }).ctrlFtTarget().why, "Frametop isn't running on the Frame.", "desktop down");
  eq(target(usable).ctrlFtTarget().why, "The Frametop screen has changed. Press Capture or Live to see it first.", "no picture yet");
  eq(target(usable, true).ctrlFtTarget().why, "Waiting for the picture of the Frametop screen…", "live is still connecting");
  const t = target(Object.assign({}, usable, { shown: "WL-0" })).ctrlFtTarget();
  ok(t.ok, "the screen whose picture is showing takes taps");
  eq(t.screen, "WL-0", "and the screen is named");
  const moved = target({ loaded: true, desktop: true, remote: true, screens: [{ name: "WL-0" }, { name: "WL-1" }], pick: "WL-1", shown: "WL-0" }).ctrlFtTarget();
  ok(!moved.ok, "a pick the picture doesn't match is refused until a fresh one is shown");
}

// --- ctrlPoll: the Frametop helper is started by query ----------------------
{
  const poll = (view = "frametop") => {
    const calls = [], flushed = [];
    const ctrl = { on: true, state: "", message: "" };
    const env = {
      ctrl, devGen: 1, view,
      api: async (path, body) => { calls.push([path, body]); return { state: "ready", message: "" }; },
      ctrlShow: () => {},
      ctrlFlush: async () => { flushed.push(ctrl.state); },
    };
    return { ...evalPage(["ctrlPoll"], env, "ctrl, ctrlPoll"), calls, flushed };
  };
  const p = poll();
  await p.ctrlPoll(0);
  eq(p.calls.length, 1, "one status request");
  eq(p.calls[0][0], "/api/touch?src=frametop&start=1", "Frametop Control starts its own helper by query");
  eq(p.calls[0][1], undefined, "with a plain GET");
  eq(p.flushed.length, 1, "a ready helper is flushed");
  await p.ctrlPoll(1);
  eq(p.calls[1][0], "/api/touch?src=frametop", "later polls ask about the Frametop helper");
  eq(p.ctrl.state, "ready", "the helper's state is kept");

  const desktop = poll("flat");
  await desktop.ctrlPoll(0);
  await desktop.ctrlPoll(1);
  eq(desktop.calls[0][0], "/api/touch?start=1", "the Desktop view still starts gamescope's helper");
  eq(desktop.calls[1][0], "/api/touch", "and polls it without the query");
}
