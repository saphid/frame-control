const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createLoginItem } = require("../login-item");

test("Linux login toggle creates and removes only its own desktop entry", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "frame-login-test-"));
  try {
    const login = createLoginItem({ platform: "linux", env: { XDG_CONFIG_HOME: root },
                                    executable: "/opt/Frame Control/frame-control" });
    assert.equal(login.enabled(), false);
    assert.equal(login.set(true), true);
    const body = fs.readFileSync(login.file, "utf8");
    assert.match(body, /^# Managed by Frame Control;/);
    assert.match(body, /Exec="\/opt\/Frame Control\/frame-control" --hidden/);
    assert.equal(fs.statSync(login.file).mode & 0o777, 0o600);
    assert.equal(login.set(false), false);
    assert.equal(fs.existsSync(login.file), false);
    fs.mkdirSync(path.dirname(login.file), { recursive: true });
    fs.writeFileSync(login.file, "[Desktop Entry]\nName=My custom launcher\n");
    assert.throws(() => login.set(true), /different autostart entry/);
    assert.equal(login.set(false), false);
    assert.match(fs.readFileSync(login.file, "utf8"), /My custom launcher/);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test("AppImage autostart launches the AppImage, with safe desktop escaping", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "frame-appimage-test-"));
  try {
    const login = createLoginItem({ platform: "linux", env: { XDG_CONFIG_HOME: root,
                                    APPIMAGE: '/home/user/Frame Control 100%.AppImage' },
                                    executable: "/tmp/.mount_extracted/AppRun" });
    login.set(true);
    assert.match(fs.readFileSync(login.file, "utf8"), /Exec="\/home\/user\/Frame Control 100%%\.AppImage" --hidden/);
    login.set(false);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

for (const platform of ["win32", "darwin"]) {
  test(`${platform} login toggle uses the OS API and starts hidden`, () => {
    let openAtLogin = false;
    const calls = [];
    const electronApp = {
      getLoginItemSettings: () => ({ openAtLogin }),
      setLoginItemSettings: opts => { calls.push(opts); openAtLogin = opts.openAtLogin; },
    };
    const login = createLoginItem({ platform, electronApp });
    assert.equal(login.enabled(), false);
    assert.equal(login.set(true), true);
    assert.deepEqual(calls.at(-1).args, ["--hidden"]);
    assert.equal(calls.at(-1).openAsHidden, true);
    assert.equal(login.set(false), false);
    assert.deepEqual(calls.at(-1).args, []);
  });
}
