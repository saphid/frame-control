// Frame Control as a desktop app (macOS, Windows, Linux): starts ui/server.py on
// a free loopback port and shows it in a native window. The server does all the
// work over the `frame` SSH alias; this file only hosts it.
const { app, BrowserWindow, Menu, Notification, Tray, clipboard, dialog, ipcMain, nativeImage, session, shell } = require("electron");
const { execFile, spawn } = require("child_process");
const { promisify } = require("util");
const fs = require("fs");
const http = require("http");
const net = require("net");
const os = require("os");
const path = require("path");
const { SCHEME, parseInstallLink, linkFromArgv } = require("./install-link");
const updater = require("./updater");
const { preferenceStore } = require("./preferences");
const { createLoginItem } = require("./login-item");
const { createMetaSignIn } = require("./meta-signin");

const run = promisify(execFile);

const IS_MAC = process.platform === "darwin";
const IS_WIN = process.platform === "win32";

// Packaged: <resources>/{ui,scripts,python}. Dev: the repo checkout.
const ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, "..");
const TOOLS = path.join(ROOT, "tools");  // bundled adb and CA certificates
const SERVER = path.join(ROOT, "ui", "server.py");
const SCRIPTS = path.join(ROOT, "scripts");
const LOG_DIR = IS_MAC ? path.join(os.homedir(), "Library", "Logs", "Frame Control")
                       : path.join(app.getPath("userData"), "logs");
const LOG = path.join(LOG_DIR, "server.log");
const BG = "#0d1117";
const FRAME = process.env.FRAME_ALIAS || "frame";
const preferences = preferenceStore(path.join(app.getPath("userData"), "client-preferences.json"));
const loginItem = createLoginItem({ electronApp: app });

let server = null;
let url = null;
let win = null;
let tray = null;
let quitting = false;
let python = null;

// Apps launched from Finder get PATH=/usr/bin:/bin:/usr/sbin:/sbin, which misses
// Homebrew's python3, rsync and adb (desktop launchers on Linux can be as bare).
// Take PATH from the login shell instead. Windows has no login shell to ask.
// Runs asynchronously so a slow shell profile can't freeze the window.
let cachedPath = null;
async function loginPath() {
  if (IS_WIN) return process.env.PATH || "";
  if (cachedPath) return cachedPath;
  const shellPath = os.userInfo().shell || process.env.SHELL || (IS_MAC ? "/bin/zsh" : "/bin/sh");
  const extra = IS_MAC ? ["/opt/homebrew/bin", "/usr/local/bin", path.join(os.homedir(), ".homebrew", "bin")] : [];
  let fromShell = "";
  try {
    const { stdout } = await run(shellPath, ["-ilc", 'printf "\\n__PATH__%s__PATH__" "$PATH"'],
                                 { encoding: "utf8", timeout: 5000 });
    fromShell = (stdout.match(/__PATH__(.*)__PATH__/) || [])[1] || "";
  } catch {}
  const parts = [...fromShell.split(":"), ...(process.env.PATH || "").split(":"), ...extra];
  const joined = [...new Set(parts.filter(Boolean))].join(":");
  if (fromShell) cachedPath = joined;  // retry next time if the shell didn't answer
  return joined;
}

// The Windows build bundles Python; elsewhere use the system's python3 (3.8+).
// -I ignores PYTHON* variables and user site-packages, so a PYTHONHOME or
// PYTHONPATH set for another Python can't break the bundled one. That makes these
// flags stand in for PYTHONUNBUFFERED, PYTHONDONTWRITEBYTECODE (no __pycache__
// inside the signed app) and PYTHONUTF8.
const PY_FLAGS = ["-I", "-u", "-B", "-X", "utf8"];

async function findPython(env) {
  const names = IS_WIN ? ["python.exe", "python3.exe"] : ["python3"];
  // The packaged app bundles Python (app/build/fetch-deps.js); a checkout uses PATH.
  const candidates = [path.join(ROOT, "python", ...(IS_WIN ? ["python.exe"] : ["bin", "python3"]))];
  for (const dir of env.PATH.split(path.delimiter)) {
    // The WindowsApps "python.exe" is a stub that opens the Microsoft Store.
    if (!dir || (IS_WIN && /\\WindowsApps\\?$/i.test(dir))) continue;
    for (const name of names) candidates.push(path.join(dir, name));
  }
  for (const p of candidates) {
    try {
      fs.accessSync(p, fs.constants.X_OK);
      // /usr/bin/python3 on macOS is a stub until the Command Line Tools are installed.
      await run(p, [...PY_FLAGS, "-c", "import http.server, sys; assert sys.version_info >= (3, 8)"],
                { timeout: 10000, env, windowsHide: true });
      return p;
    } catch {}
  }
  return null;
}

async function hasSsh(env) {
  try { await run("ssh", ["-V"], { timeout: 5000, env, windowsHide: true }); return true; } catch { return false; }
}

const PYTHON_HELP = app.isPackaged ? "The bundled Python is missing; reinstall Frame Control."
  : "Install Python 3.8 or later, then reopen the app.";
const SSH_HELP = IS_WIN
  ? "Turn on Windows' OpenSSH client: Settings → System → Optional features → Add a feature → OpenSSH Client."
  : "Install the OpenSSH client (e.g. sudo apt install openssh-client).";

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once("error", reject);
    s.listen(0, "127.0.0.1", () => { const { port } = s.address(); s.close(() => resolve(port)); });
  });
}

// Ready once the port answers with our Server header.
function ping(target) {
  return new Promise((resolve) => {
    const req = http.get(target, { timeout: 1000 }, (res) => {
      res.resume();
      resolve(/^FrameControl/.test(res.headers.server || ""));
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function startServer() {
  // The version, the time zone and whether this is a built app go to ui/frame_telemetry.py,
  // which sends nothing from a source checkout.
  const env = { ...process.env, PATH: await loginPath(), FRAME_CONTROL_APP: "1",
                FRAME_CONTROL_VERSION: app.getVersion(), FRAME_CONTROL_LOG: LOG,
                FRAME_CONTROL_TIMEZONE: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
                ...(app.isPackaged ? { FRAME_CONTROL_PACKAGED: "1" } : {}),
                ...(fs.existsSync(TOOLS) ? { FRAME_CONTROL_TOOLS: TOOLS } : {}) };
  python = await findPython(env);
  if (!python) throw new Error(`Frame Control needs Python 3.8 or later. ${PYTHON_HELP}`);
  if (!await hasSsh(env)) throw new Error(`Frame Control needs the ssh command. ${SSH_HELP}`);
  const port = await freePort();
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const log = fs.openSync(LOG, "a");
  fs.writeSync(log, `\n--- ${new Date().toISOString()} ${python} ${SERVER} --port ${port}\n`);
  // stdin stays open while the app runs; the server exits cleanly when it closes.
  const child = spawn(python, [...PY_FLAGS, SERVER, "--port", String(port), "--exit-on-eof"],
                      { env, stdio: ["pipe", log, log], windowsHide: true });
  child.stdin.on("error", () => {});
  fs.closeSync(log);
  server = child;
  let exited = null;
  child.once("error", (err) => {
    exited = err.message;
    if (server === child) { server = null; if (!quitting && url) serverDied(err.message); }
  });
  child.once("exit", (code, signal) => {
    exited = signal || code;
    if (server !== child) return;  // replaced by Restart Server
    server = null;
    if (!quitting && url) serverDied(exited);
  });

  const target = `http://127.0.0.1:${port}/`;
  for (let i = 0; i < 100; i++) {
    if (exited !== null) throw new Error(`The server exited (${exited}). See ${LOG}.`);
    if (await ping(target)) { url = target; serverStarted = Date.now(); return; }
    await new Promise((r) => setTimeout(r, 100));
  }
  if (server === child) server = null;
  endServer(child);
  throw new Error(`The server didn't start within 10 seconds. See ${LOG}.`);
}

// Closing stdin lets server.py close its SSH connections and exit (the only clean
// way on Windows); SIGTERM does the same elsewhere.
// Resolves once it has exited (or after 20 s), so a replacement can take the server
// lock: server.py allows one per user.
function endServer(child) {
  const gone = child.exitCode !== null || child.signalCode !== null ? Promise.resolve()
    : new Promise((resolve) => child.once("exit", resolve));
  try { child.stdin.end(); } catch {}
  if (!IS_WIN) child.kill("SIGTERM");
  // server.py ignores a second SIGTERM while it shuts down, so the fallback is a hard kill.
  setTimeout(() => { if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL"); }, 12000).unref();
  return Promise.race([gone, new Promise((resolve) => setTimeout(resolve, 20000).unref())]);
}

function stopServer() {
  if (server) endServer(server);
}

function errorPage(message, title = "Frame Control couldn't start") {
  const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const html = `<!doctype html><meta charset="utf-8"><body style="margin:0;height:100vh;display:grid;
    place-items:center;background:${BG};color:#e6edf3;font:14px -apple-system,sans-serif">
    <div style="max-width:560px;padding:32px;line-height:1.5"><h2>${esc(title)}</h2>
    <p>${esc(message)}</p>
    <p><button onclick="this.disabled = true; frameApp.restartServer()" style="font:inherit;padding:6px 16px;
      border-radius:6px;border:1px solid #30363d;background:#21262d;color:inherit;cursor:pointer">Try Again</button></p>
    <p style="color:#8b98a8">Frame → Restart Server does the same.</p></div>`;
  return "data:text/html;charset=utf-8," + encodeURIComponent(html);
}

// A server that had been running starts again by itself (something stopped it: a
// signal, a crash). One that stops again within a minute shows the error instead,
// so a server that can't stay up doesn't restart forever.
let serverStarted = 0;
function serverDied(why) {
  url = null;
  if (!win) return;
  if (Date.now() - serverStarted > 60000) restartServer();
  else win.loadURL(errorPage(`Its server stopped unexpectedly (${why}). See ${LOG}.`, "Frame Control stopped"));
}

// Restarts that overlap share one: two could each start a server, and the one
// that lost the lock would leave the app pointing at nothing.
let restarting = null;
function restartServer() {
  if (!restarting) {
    restarting = (async () => {
      const old = server;
      server = null;
      url = null;
      if (old) await endServer(old);
      if (starting) await starting.catch(() => {});  // a start it cut short: then start afresh
      await load();
    })().finally(() => { restarting = null; });
  }
  return restarting;
}

// On macOS the page's sticky header becomes the title bar, clear of the traffic lights.
const CHROME_CSS = IS_MAC && `
  header { padding-left: 92px !important; -webkit-app-region: drag; user-select: none; }
  header a, header button, header input, header select, header .chip { -webkit-app-region: no-drag; }
`;

// Restart Server can start a new load while an older one is still waiting for
// its server; only the newest load may touch the window.
let loadGen = 0;
let starting = null;  // loads that overlap share one server start
async function load() {
  const gen = ++loadGen;
  try {
    if (!url) await (starting ||= startServer().finally(() => { starting = null; }));
    if (gen === loadGen && win) { await win.loadURL(url); firstRunCheck(); }
  } catch (e) {
    if (gen === loadGen && win) await win.loadURL(errorPage(e.message));
  }
}

// `ssh -G` prints the effective config. An alias nobody configured keeps its
// own name as HostName; connect.sh always writes a HostName.
async function aliasConfigured(env) {
  try {
    const { stdout } = await run("ssh", ["-G", FRAME], { encoding: "utf8", timeout: 5000, env });
    return (stdout.match(/^hostname (.*)$/m) || [])[1] !== FRAME;
  } catch {
    return true;  // can't tell; don't nag
  }
}

let setupOffered = false;
async function firstRunCheck() {
  if (setupOffered || !url) return;  // not on the error page, and once per launch
  if (await aliasConfigured({ ...process.env, PATH: await loginPath() })) return;
  if (!win || setupOffered) return;
  setupOffered = true;
  const { response } = await dialog.showMessageBox(win, {
    type: "info",
    message: "Connect to your Steam Frame",
    detail: `There's no "${FRAME}" SSH alias yet. On the Frame, turn on Steam Settings → System → `
          + "Enable Developer Mode, then Developer → Set User Password. Then run the setup: it finds the "
          + "headset, creates a key, and asks for that password once in a terminal window.",
    buttons: ["Set Up Connection…", "Later"],
    defaultId: 0, cancelId: 1,
  });
  if (response === 0) setUpConnection();
}

// IPC only from our own page in our own window.
function fromUi(e) {
  if (!win || e.sender !== win.webContents || !url || !e.senderFrame) return false;
  try {
    return new URL(e.senderFrame.url).origin === new URL(url).origin;
  } catch { return false; }
}

// The error page's Try Again button. The error page is the only data: page the window
// shows (`url` can still be set then: the server answered but the page failed to load).
ipcMain.handle("server:restart", (e) => {
  if (win && e.sender === win.webContents && e.senderFrame && e.senderFrame.url.startsWith("data:")) restartServer();
});
ipcMain.handle("clipboard:read", (e) => fromUi(e) ? clipboard.readText() : "");
// Text from the headset's clipboard onto this computer's.
ipcMain.handle("clipboard:write", (e, text) => {
  if (!fromUi(e) || typeof text !== "string") return false;
  clipboard.writeText(text);
  return true;
});
ipcMain.handle("preferences:read", (e) => fromUi(e) ? preferences.read() : {});
ipcMain.handle("preferences:write", (e, key, value) => fromUi(e) ? preferences.write(key, value) : false);
// A PNG or JPEG (a screenshot) onto the clipboard as an image.
ipcMain.handle("clipboard:writeImage", (e, bytes) => {
  if (!fromUi(e) || !(bytes instanceof Uint8Array)) return false;
  const img = nativeImage.createFromBuffer(Buffer.from(bytes));
  if (img.isEmpty()) throw new Error("not an image");
  clipboard.writeImage(img);
  return true;
});
ipcMain.handle("connection:setup", (e) => { if (fromUi(e)) setUpConnection(); });
ipcMain.on("keys:capture", (e, on) => { if (fromUi(e)) win.webContents.setIgnoreMenuShortcuts(on === true); });
ipcMain.handle("update:get", (e) => fromUi(e) ? publicUpdate() : null);
ipcMain.handle("update:check", (e) => fromUi(e) ? checkForUpdate({ manual: true }).then(publicUpdate) : null);
ipcMain.handle("update:install", (e) => { if (fromUi(e)) installUpdate(); });

// The OBS source is local to this computer. Closing the Python relay's control
// pipe lets it stop SSH on every platform, including Windows where SIGTERM
// terminates Python without running its cleanup block.
const OBS_SCRIPT = path.join(SCRIPTS, "obs-headset-source.py");
let obsChild = null;
let obsState = { state: "idle", alias: "", error: "" };
function publicObs() { return { ...obsState, supported: true }; }
function setObs(state, alias = "", error = "") {
  obsState = { state, alias, error };
  if (win && !win.isDestroyed()) win.webContents.send("obs:state", publicObs());
  return publicObs();
}
function stopObs() {
  if (!obsChild) return publicObs();
  setObs("stopping", obsState.alias);
  if (obsChild.stdin && !obsChild.stdin.writableEnded) obsChild.stdin.end();
  return publicObs();
}
ipcMain.handle("obs:status", (e) => fromUi(e) ? publicObs() : null);
ipcMain.handle("obs:start", async (e) => {
  if (!fromUi(e)) return null;
  if (obsChild) return publicObs();
  const alias = activeAlias();
  if (!ALIAS_RE.test(alias)) throw new Error("Select a valid headset first.");
  if (!fs.existsSync(OBS_SCRIPT)) throw new Error("The OBS helper is missing; reinstall Frame Control.");
  const env = { ...process.env, PATH: await loginPath() };
  const executable = python || await findPython(env);
  if (!executable) throw new Error(PYTHON_HELP);
  // A concurrent click or a headset switch may have happened while finding Python.
  if (obsChild) return publicObs();
  if (alias !== activeAlias()) throw new Error("The selected headset changed; try again.");
  const child = spawn(executable, [...PY_FLAGS, OBS_SCRIPT, "--frame", alias, "--control-stdin"],
                      { env, stdio: ["pipe", "ignore", "pipe"], windowsHide: true });
  obsChild = child;
  setObs("starting", alias);
  let output = "";
  child.stderr.on("data", (chunk) => {
    output = (output + chunk.toString("utf8")).slice(-2048);
    if (obsChild === child && output.includes("Frame Control OBS stream is ready")) setObs("running", alias);
  });
  child.once("error", (err) => {
    if (obsChild !== child) return;
    obsChild = null;
    setObs("failed", alias, `Could not start OBS source: ${err.message}`);
  });
  child.once("exit", (code, signal) => {
    if (obsChild !== child) return;
    const stopping = obsState.state === "stopping" || quitting;
    obsChild = null;
    setObs(stopping ? "idle" : "failed", alias,
           stopping ? "" : `OBS source stopped (${signal || code}). ${output.trim().split("\n").pop() || "Check SteamVR and SSH."}`);
  });
  return publicObs();
});
ipcMain.handle("obs:stop", (e) => fromUi(e) ? stopObs() : null);

// The page reports the headsets it knows (the server's Devices tab), so the Frame
// menu can switch between them. Only plain names and ids go into the menu.
const ALIAS_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
let devices = [];
ipcMain.on("devices:changed", (e, list) => {
  if (!fromUi(e) || !Array.isArray(list)) return;
  const next = list.slice(0, 20).filter(d => d && typeof d.id === "string" && ALIAS_RE.test(d.alias || ""))
    .map(d => ({ id: d.id.slice(0, 80), name: String(d.name || d.alias).slice(0, 60), alias: d.alias, active: !!d.active }));
  if (JSON.stringify(next) === JSON.stringify(devices)) return;
  devices = next;
  if (obsChild && obsState.alias !== activeAlias()) stopObs();
  buildMenu();
});
const activeAlias = () => (devices.find(d => d.active) || {}).alias || FRAME;

// SSH through the server, so it goes to the headset and address the app is using
// (with its own pinned identity), and refuses when there's none.
function openSsh() {
  if (!url) return dialog.showErrorBox("Couldn't open SSH", "Frame Control's server isn't running.");
  const body = JSON.stringify({ what: "terminal" });
  const req = http.request(new URL("/api/open", url), {
    method: "POST", timeout: 15000,
    headers: { "Content-Type": "application/json", "X-Frame-UI": "1", "Content-Length": Buffer.byteLength(body) },
  }, (res) => {
    let data = "";
    res.on("data", (c) => { data += c; });
    res.on("end", () => {
      if (res.statusCode === 200) return;
      let why = `HTTP ${res.statusCode}`;
      try { why = JSON.parse(data).error || why; } catch {}
      dialog.showErrorBox("Couldn't open SSH", why);
    });
  });
  req.on("error", (e) => dialog.showErrorBox("Couldn't open SSH", e.message));
  req.on("timeout", () => req.destroy(new Error("the server didn't answer")));
  req.end(body);
}
function showDevices() {
  if (win && url) win.webContents.executeJavaScript('location.hash = "devices"').catch(() => {});
}

ipcMain.handle("comfort:notify", (e, message) => {
  if (!fromUi(e) || typeof message !== "string" || message.length > 500) throw new Error("Invalid notification");
  if (!Notification.isSupported()) throw new Error("System notifications are unavailable");
  return new Promise((resolve, reject) => {
    const notification = new Notification({title: "Frame Control", body: message});
    const timer = setTimeout(() => reject(new Error("Notification delivery was not confirmed. Check system notification settings.")), 5000);
    notification.once("show", () => { clearTimeout(timer); resolve(true); });
    notification.once("failed", (_event, error) => {
      clearTimeout(timer);
      reject(new Error("Notification delivery failed. Check system notification settings: " + error));
    });
    notification.show();
  });
});

// ---- Sign in with Meta (app/meta-signin.js, docs/meta-library.md) ----
// The token goes from the sign-in window's own session straight to the server's
// connect path; the page asks for it and only hears the server's answer.
function postApi(apiPath, body) {
  return new Promise((resolve, reject) => {
    if (!url) return reject(new Error("Frame Control's server isn't running."));
    const data = JSON.stringify(body);
    const req = http.request(new URL(apiPath, url), {
      method: "POST", timeout: 60000,
      headers: { "Content-Type": "application/json", "X-Frame-UI": process.env.FRAME_UI_KEY || "1",
                 "Content-Length": Buffer.byteLength(data) },
    }, (res) => {
      let text = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { text += c; });
      res.on("end", () => {
        let parsed = {};
        try { parsed = JSON.parse(text); } catch {}
        resolve({ status: res.statusCode, data: parsed });
      });
    });
    req.on("error", reject);
    req.on("timeout", () => req.destroy(new Error("the server didn't answer")));
    req.end(data);
  });
}

let metaSignIn = null;
const meta = () => (metaSignIn ||= createMetaSignIn({
  BrowserWindow, session, shell, parent: () => win,
  // The page only offers sign-in after its "I understand" box is ticked (checked again below).
  connect: (token, attempt) => postApi("/api/meta", { action: "connect", token, acknowledged: true, attempt }),
  cancel: (attempt) => postApi("/api/meta", { action: "cancel-signin", attempt }),
}));
ipcMain.handle("meta:signin", (e, acknowledged) => {
  if (!fromUi(e)) return null;
  if (acknowledged !== true) return { ok: false, error: "My Meta library is experimental: tick that you understand the warning first." };
  return meta().signIn();
});
ipcMain.handle("meta:signout", (e) => fromUi(e) ? meta().signOut() : false);

// frame-control://install links from websites (docs/web-install.md). They can
// arrive before the window or server exists (macOS open-url on a cold launch),
// so they wait here until the page asks for them. The page checks the link with
// the server and installs nothing until the user confirms in its dialog.
const pendingLinks = [];
let linkPage = null;  // the webContents whose current page is listening

function openInstallLink(raw) {
  const req = parseInstallLink(raw);
  if (!req) {
    app.whenReady().then(() => dialog.showErrorBox("Frame Control can't use this link",
      "Install links look like frame-control://install?manifest=https://… or frame-control://install?url=https://…"));
    return;
  }
  pendingLinks.push(req);
  if (pendingLinks.length > 5) pendingLinks.shift();  // a page opening links in a loop
  deliverLinks();
  if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
}

function deliverLinks() {
  if (!win || !linkPage || linkPage !== win.webContents) return;
  while (pendingLinks.length) win.webContents.send("install-link", pendingLinks.shift());
}

ipcMain.on("install-link:ready", (e) => {
  if (!fromUi(e)) return;
  linkPage = e.sender;
  deliverLinks();
});

// ---- updates (app/updater.js, docs/releasing.md) ----
// Checked shortly after launch and every few hours; the page shows a banner and
// the Update button calls installUpdate.
const UPDATE_EVERY = 6 * 3600 * 1000;
const update = { status: "idle", current: app.getVersion(), latest: null, error: null, progress: 0, how: null };

function publicUpdate() {
  const r = update.latest;
  return { status: update.status, current: update.current, error: update.error, progress: update.progress,
           latest: r && { version: r.version, notes: r.notes, page: r.page },
           canInstall: !!update.how && update.how.method !== "manual", why: update.how && update.how.why };
}

function setUpdate(fields) {
  Object.assign(update, fields);
  if (win && linkPage === win.webContents) win.webContents.send("update:state", publicUpdate());
}

async function checkForUpdate({ manual = false } = {}) {
  if (["checking", "downloading", "ready"].includes(update.status)) return;
  setUpdate({ status: "checking", error: null });
  try {
    const latest = await updater.latestRelease();
    const how = updater.updateMethod({ platform: process.platform, isPackaged: app.isPackaged,
                                       execPath: process.execPath, env: process.env,
                                       exists: fs.existsSync, writable: updater.writable });
    if (updater.isNewer(latest.version, update.current)) {
      setUpdate({ status: "available", latest, how });
      if (manual) offerUpdateDialog();
    } else {
      setUpdate({ status: "none", latest, how });
      if (manual) dialog.showMessageBox(win, { type: "info", message: "Frame Control is up to date",
                                               detail: `You have ${update.current}, the newest version.` });
    }
  } catch (e) {
    // A failed check: nothing to install, and never an older release kept from before.
    setUpdate({ status: "check-failed", error: e.message, latest: null });
    if (manual) dialog.showMessageBox(win, { type: "warning", message: "Couldn't check for updates", detail: e.message });
  }
}

async function offerUpdateDialog() {
  const r = update.latest;
  const { response } = await dialog.showMessageBox(win, {
    type: "info", message: `Frame Control ${r.version} is available`,
    detail: `You have ${update.current}.` + (update.how.method === "manual" ? ` Download it from the release page (${update.how.why}).` : ""),
    buttons: [update.how.method === "manual" ? "Open Release Page" : "Update and Restart", "Later"], defaultId: 0, cancelId: 1,
  });
  if (response === 0) installUpdate();
}

async function installUpdate() {
  // "error" here only ever means an install failed, so trying again is safe.
  if (update.status !== "available" && update.status !== "error") return;
  if (!update.latest || !updater.isNewer(update.latest.version, update.current)) return;
  if (!update.how || update.how.method === "manual") { shell.openExternal(update.latest.page); return; }
  setUpdate({ status: "downloading", progress: 0, error: null });
  try {
    const start = await updater.prepare(update.latest, update.how,
      (done, total) => { if (total) setUpdate({ progress: done / total }); }, update.current);
    setUpdate({ status: "ready", progress: 1 });
    start();
    quitting = true;
    app.quit();
  } catch (e) {
    setUpdate({ status: "error", error: e.message });
  }
}

function scheduleUpdateChecks() {
  if (process.env.FRAME_CONTROL_NO_UPDATE_CHECK === "1") return;
  setTimeout(checkForUpdate, 8000);
  setInterval(checkForUpdate, UPDATE_EVERY).unref();
}

function registerScheme() {
  // A checkout runs as `electron .`, so the OS must be told the script too.
  // (macOS takes the scheme from Info.plist, which only the built app has.)
  if (process.defaultApp) {
    if (process.argv.length >= 2) app.setAsDefaultProtocolClient(SCHEME, process.execPath, [path.resolve(process.argv[1])]);
  } else {
    app.setAsDefaultProtocolClient(SCHEME);
  }
}

function showWindow() {
  if (!win) return createWindow(true);
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

function ensureTray() {
  if (tray) return true;
  try {
    const icon = nativeImage.createFromPath(path.join(__dirname, "build", "icon.png"));
    if (icon.isEmpty()) return false;
    tray = new Tray(icon);
    // Some Linux desktops accept the Tray object but expose no status icon.
    // Keep a visible login window rather than hiding the only way back in.
    if (process.platform === "linux") {
      const bounds = tray.getBounds();
      if (!bounds.width || !bounds.height) { tray.destroy(); tray = null; return false; }
    }
    tray.setToolTip("Frame Control");
    tray.on("click", showWindow);
    updateTrayMenu();
    return true;
  } catch {
    if (tray) { try { tray.destroy(); } catch {} tray = null; }
    return false;
  }
}

function updateTrayMenu() {
  if (!tray) return;
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Open Frame Control", click: showWindow },
    { label: "Open at Login", type: "checkbox", checked: loginItem.enabled(), click: toggleLoginItem },
    { type: "separator" },
    { label: "Quit Frame Control", click: () => app.quit() },
  ]));
}

function toggleLoginItem() {
  try {
    const on = loginItem.set(!loginItem.enabled());
    if (on) ensureTray();
    else if (tray) { tray.destroy(); tray = null; }
    buildMenu();
    updateTrayMenu();
  } catch (err) {
    dialog.showErrorBox("Open at Login", String(err.message || err));
    buildMenu();
    updateTrayMenu();
  }
}

function createWindow(showOnReady = !process.argv.includes("--hidden") || !tray) {
  win = new BrowserWindow({
    width: 1400, height: 950, minWidth: 760, minHeight: 560,
    title: "Frame Control", backgroundColor: BG, show: false,
    ...(IS_MAC ? { titleBarStyle: "hiddenInset", trafficLightPosition: { x: 18, y: 26 } }
               : { icon: path.join(__dirname, "build", "icon.png") }),
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, backgroundThrottling: false,
                      preload: path.join(__dirname, "preload.js") },
  });
  win.once("ready-to-show", () => { if (showOnReady) win.show(); });
  win.on("close", (event) => {
    if (!quitting && tray && loginItem.enabled()) { event.preventDefault(); win.hide(); }
  });
  if (CHROME_CSS) win.webContents.on("did-finish-load", () => win.webContents.insertCSS(CHROME_CSS));
  // External links open in the default browser; the app never navigates away.
  win.webContents.setWindowOpenHandler(({ url: target }) => {
    if (/^https?:\/\//.test(target)) shell.openExternal(target);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, target) => {
    if (!url || new URL(target).origin !== new URL(url).origin) e.preventDefault();
  });
  // A reload or a new page must ask for links again before it gets any.
  win.webContents.on("did-start-loading", () => { linkPage = null; });
  win.on("closed", () => { win = null; linkPage = null; });
  load();
}

// Opens a terminal window (Terminal, a Linux terminal emulator or a console) via
// ui/frame_host.py, which the server uses too: setup and power actions ask for the
// Developer Mode password there.
async function runInTerminal(argv) {
  try {
    const env = { ...process.env, PATH: await loginPath() };
    const py = python || await findPython(env);
    if (!py) throw new Error(`Python 3.8 or later is needed. ${PYTHON_HELP}`);
    await run(py, [...PY_FLAGS, path.join(ROOT, "ui", "frame_host.py"), "terminal", "--", ...argv],
              { env, timeout: 15000, windowsHide: true });
  } catch (err) {
    dialog.showErrorBox("Couldn't open a terminal", String((err.stderr || err.message || err)).trim());
  }
}

// Set Up Connection for the headset in use (or another alias, from the Devices tab).
async function setUpConnection(name = activeAlias()) {
  if (!ALIAS_RE.test(name)) return;
  const alias = `FRAME_ALIAS=${name}`;
  if (IS_MAC) return runInTerminal(["env", alias, "zsh", path.join(SCRIPTS, "connect.sh")]);
  const py = python || await findPython({ ...process.env, PATH: await loginPath() });
  // --alias, since a new console on Windows (and some Linux terminals) doesn't get our environment.
  runInTerminal([py || "python3", ...PY_FLAGS, path.join(ROOT, "ui", "frame_connect.py"), "--alias", name]);
}

function buildMenu() {
  const template = [
    ...(IS_MAC ? [{ label: app.name, submenu: [
      { role: "about" }, { label: "Check for Updates…", click: () => checkForUpdate({ manual: true }) },
      { type: "separator" }, { role: "services" }, { type: "separator" },
      { role: "hide" }, { role: "hideOthers" }, { role: "unhide" }, { type: "separator" }, { role: "quit" },
    ] }] : []),
    { role: "fileMenu" },
    { role: "editMenu" },
    {
      label: "Frame",
      submenu: [
        { label: "Set Up Connection…", click: () => setUpConnection() },
        { label: "Open at Login", type: "checkbox", checked: loginItem.enabled(),
          enabled: app.isPackaged, click: toggleLoginItem },
        { label: IS_MAC ? "Open SSH in Terminal" : "Open SSH in a Terminal", click: openSsh },
        { type: "separator" },
        ...(devices.length > 1 ? [{
          label: "Headset",
          submenu: devices.map(d => ({ label: d.name, type: "radio", checked: d.active,
                                       click: () => { if (win) win.webContents.send("use-device", d.id); } })),
        }] : []),
        { label: "Devices…", accelerator: "CmdOrCtrl+5", click: showDevices },
        { type: "separator" },
        { label: "Open in Browser", click: () => url && shell.openExternal(url) },
        { label: "Restart Server", click: () => win ? restartServer() : createWindow() },
        { label: "Show Server Log", click: () => shell.openPath(fs.existsSync(LOG) ? LOG : LOG_DIR) },
        ...(IS_WIN ? [] : [{ label: "Reveal Helper Scripts", click: () => shell.openPath(SCRIPTS) }]),
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" }, { role: "forceReload" }, { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
        { type: "separator" }, { role: "togglefullscreen" },
      ],
    },
    ...(IS_MAC ? [{ role: "windowMenu" }] : []),
    {
      role: "help",
      submenu: [
        ...(IS_MAC ? [] : [{ label: "Check for Updates…", click: () => checkForUpdate({ manual: true }) }]),
        { label: "Report a Problem…", click: () => {
          if (win && url && linkPage === win.webContents) win.webContents.send("report:open");
          else shell.openExternal("https://frame-control.pages.dev/feedback/");  // the page isn't up
        } },
        { label: "Release Notes", click: () => shell.openExternal(updater.RELEASES) },
        { label: "Project on GitHub", click: () => shell.openExternal("https://github.com/saphid/steam-frame") },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  // macOS delivers install links here, even before the app is ready.
  app.on("open-url", (e, link) => { e.preventDefault(); openInstallLink(link); });
  // Windows and Linux start a second instance with the link as an argument.
  app.on("second-instance", (_e, argv) => {
    if (!argv.includes("--hidden")) showWindow();
    const link = linkFromArgv(argv);
    if (link) openInstallLink(link);
  });
  const firstLink = IS_MAC ? null : linkFromArgv(process.argv);
  if (firstLink) openInstallLink(firstLink);
  app.whenReady().then(() => {
    registerScheme();
    if (loginItem.enabled()) ensureTray();
    buildMenu();
    createWindow();
    scheduleUpdateChecks();
  });
  app.on("activate", showWindow);
  app.on("window-all-closed", () => app.quit());
  let obsQuitWaiting = false;
  let obsQuitReady = false;
  app.on("before-quit", (event) => {
    quitting = true;
    stopServer();
    if (!obsChild || obsQuitReady) return;
    event.preventDefault();
    if (obsQuitWaiting) return;
    obsQuitWaiting = true;
    const child = obsChild;
    let timer;
    child.once("close", () => {
      clearTimeout(timer);
      obsQuitReady = true;
      app.quit();
    });
    stopObs();
    timer = setTimeout(() => {
      if (child.exitCode === null) {
        if (IS_WIN) {
          // Only the helper and its SSH child: never enumerate unrelated SSH jobs.
          spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"],
                { stdio: "ignore", windowsHide: true, detached: true }).unref();
        } else child.kill("SIGKILL");
      }
      obsQuitReady = true;
      app.quit();
    }, 8000);
  });
  process.on("exit", () => { stopObs(); stopServer(); });
}
