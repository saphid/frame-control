// Opt-in OS login item. Linux owns only its marked autostart file; an existing
// custom entry is never overwritten or removed.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const MARKER = "# Managed by Frame Control; use Frame > Open at Login to remove.\n";
const FILE = "com.saphid.frame-control.desktop";

function quoteExec(value) {
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\$/g, "\\$").replace(/`/g, "\\`").replace(/%/g, "%%")}"`;
}

function createLoginItem({ platform = process.platform, electronApp, env = process.env,
                           executable = process.execPath, filesystem = fs,
                           home = os.homedir() }) {
  const config = env.XDG_CONFIG_HOME && path.isAbsolute(env.XDG_CONFIG_HOME)
    ? env.XDG_CONFIG_HOME : path.join(home, ".config");
  const file = path.join(config, "autostart", FILE);
  const command = platform === "linux" && env.APPIMAGE && path.isAbsolute(env.APPIMAGE)
    ? env.APPIMAGE : executable;
  function owned() {
    try { return filesystem.readFileSync(file, "utf8").startsWith(MARKER); }
    catch (err) { if (err.code === "ENOENT") return false; throw err; }
  }
  function enabled() {
    if (platform === "linux") return owned();
    return !!electronApp.getLoginItemSettings().openAtLogin;
  }
  function set(enabledNow) {
    if (platform !== "linux") {
      electronApp.setLoginItemSettings({ openAtLogin: !!enabledNow, openAsHidden: !!enabledNow,
                                        args: enabledNow ? ["--hidden"] : [] });
      if (enabled() !== !!enabledNow) throw new Error("The operating system did not save the login item.");
      return enabled();
    }
    if (enabledNow) {
      if (filesystem.existsSync(file) && !owned()) throw new Error(`A different autostart entry already exists: ${file}`);
      filesystem.mkdirSync(path.dirname(file), { recursive: true });
      const body = MARKER + "[Desktop Entry]\nType=Application\nName=Frame Control\n" +
        `Exec=${quoteExec(command)} --hidden\nTerminal=false\nX-GNOME-Autostart-enabled=true\n`;
      const tmp = file + `.tmp-${process.pid}`;
      try { filesystem.writeFileSync(tmp, body, { mode: 0o600 }); filesystem.renameSync(tmp, file); }
      finally { try { filesystem.unlinkSync(tmp); } catch (err) { if (err.code !== "ENOENT") throw err; } }
    } else if (owned()) {
      filesystem.unlinkSync(file);
    }
    return enabled();
  }
  return { enabled, set, file };
}

module.exports = { createLoginItem, quoteExec };
