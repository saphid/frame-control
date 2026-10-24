# Backup and recovery

**Tools → Backup & recovery** copies what a factory reset would lose from the
Steam Frame to your computer, puts it back afterwards, and gets the headset out
of Desktop Mode. It runs from Frame Control on a computer, not from the iPhone
app or the Frame itself.

**Not tested on a headset yet.** Everything here is covered by unit tests and
the fake Frame (see [Verification](#verification)); the save locations and the
Desktop Mode switch are taken from Valve's tools and from Proton's layout, not
from a backup and restore on a real Frame.

## Back up

Choose **Game saves**, **Steam and desktop settings** and **Android app data**
(all three by default), then **Back up now**. **See what's included** lists each
part and its size first. Backing up only reads the headset.

Each backup is a folder named after the time it started:

```
~/Documents/Frame Control Backups/2026-10-23-142530/
  manifest.json
  saves/saves-1234.tar.gz          one per game
  saves/saves-linux.tar.gz
  settings/settings-steam.tar.gz
  settings/settings-system.tar.gz
  android/org.example.game.tar.gz  one per Android app
```

`manifest.json` records the headset's name, SteamOS version and BUILD_ID, every
file with its size and SHA-256, and each archive's SHA-256. It also lists what
was skipped and why. A backup is written under a hidden `.…partial` name and
renamed when complete, so a cut-off backup never shows up as one.

### What's saved

| Part | From the headset (`~` is `/home/steamos`) | Restored? |
|---|---|---|
| Windows game saves | `~/.local/share/Steam/steamapps/compatdata/<appid>/pfx/drive_c/users/steamuser/` → `AppData/Roaming`, `AppData/Local`, `AppData/LocalLow`, `Documents`, `Saved Games`. Wine's own folders in them (`Temp`, `Microsoft`, `D3DSCache`, `CrashDumps`) are left out. Sideloaded Windows games (non-Steam shortcuts) have prefixes here too | Yes |
| Linux game saves | `~/.config/unity3d`, `~/.local/share/godot/app_userdata`: where Unity and Godot games save by default | Yes |
| Steam controller layouts | `userdata/<account>/241100/remote/controller_config`, `steamapps/common/Steam Controller Configs/<account>/config` | Yes |
| Steam library settings | `userdata/<account>/config/localconfig.vdf`, `shortcuts.vdf`, `grid/` (custom artwork) | Kept for reference |
| Desktop settings | `~/.config/kdeglobals`, `kwinrc`, `kxkbrc` (keyboard layout), `konsolerc`, `dolphinrc` | Yes |
| SteamVR settings | `~/.config/openvr/config/steamvr.vrsettings` | Kept for reference |
| Android app data | Each Frame Control Android app's private data, through the existing `backup-data` helper ([sidequest.md](sidequest.md#private-app-data-backups)) | Yes |

"Kept for reference" files are in the backup but not put back automatically:
Steam and SteamVR rewrite them while they run, and an old `shortcuts.vdf` would
point at apps that aren't installed after a reset. Open the backup folder to
copy one by hand if you need it.

### What's never copied

- **Steam sign-in:** `steam.token`, `config/config.vdf`, `loginusers.vdf`,
  `registry.vdf` and `ssfn*` files.
- **Keys and passwords:** `~/.ssh`, `~/.gnupg`, keyrings and KWallet, any
  `*.token`, `*.key` or `*.pem` file, Tailscale state and proxy settings
  (`secrets.env`). These are refused by name wherever they turn up, including
  inside a game's folder, and a restore refuses them too.
- Games, Proton and the Steam runtimes: reinstall them from Steam.
- Steam Cloud's own folders (`userdata/<account>/<appid>`), shader caches and
  screenshots (**Tools → Capture & Live** saves those to Pictures).
- Android apps themselves, their OBB files and shared storage (`/sdcard`).
- Symbolic links (never followed), and single files over 2 GiB.

Backups aren't encrypted. Game folders can still hold a launcher's login, and
Android app data can hold an app's, so keep backups private.

Android apps that are open are skipped (the helper needs the app closed); close
them and back up again.

## Restore after a factory reset

1. Set up the headset again: Developer Mode, **Set Up Connection**, sign in to
   Steam with the same account.
2. Reinstall your games, and **start each once** so Proton creates its folders.
3. Reinstall your Android apps from Frame Control.
4. **Tools → Backup & recovery → Restore…** on a backup. Frame Control checks
   each part against the headset and says what it would do: how many files it
   replaces and how many are new.
5. Tick the parts to restore and **Restore selected**. It asks before replacing
   anything.

Parts that can't go back yet are skipped, not failed, with the reason:

| Reason | What to do |
|---|---|
| Install the game first | Install it from Steam, then restore |
| Start the game once | Proton hasn't made its folders yet; start the game, quit, restore |
| Sign in to Steam first | Controller layouts go under your account's folder |
| Install the app first / close the app first | Android app data needs the app installed and closed |
| The backup file doesn't match its checksum | The archive changed since it was made |

A restore writes only the files in the parts you chose, and only inside that
part's folders: it never deletes a file, and a save archive can't write outside
its game. Before replacing a file it copies the current one to
`~/.local/share/frame-control/restore-previous/<time>/` on the headset. Files
already identical are left alone. Android app data goes through the existing
`restore-data` helper, which keeps the previous data folder beside it.

## Stuck in Desktop Mode

On the Frame, Game Mode is gamescope running Steam, and the Linux desktop
normally runs *inside* it as one panel (`steamos-nested-desktop`, see
[how-the-frame-works.md](how-the-frame-works.md#the-layer-cake)). If that panel
is what you see, you're already in Game Mode: close it from the Steam dashboard.

Full Desktop Mode is a different session. SteamOS picks the session through
SDDM's autologin file, `/etc/sddm.conf.d/zz-steamos-autologin.conf` (or the
default `/etc/sddm.conf.d/steamos.conf`), and switches with
`steamos-session-select` (`holo-session-select` on newer images). This is what
Valve's own devkit tools on the Frame read and run
([`steamos-get-status`](../frame/devkit-utils/steamos-get-status),
[`steamos-delete`](../frame/devkit-utils/steamos-delete)).

**Check** reads that file and whether gamescope and Plasma are running; it
changes nothing. On the Frame gamescope's process is `gamescope-wl`, started by
`start-gamescope-session`, and either counts as Game Mode. Only when Plasma is
running without gamescope (Desktop Mode) does **Return to Game Mode** run
exactly `steamos-session-select gamescope` (or `holo-session-select
gamescope`) over SSH, after asking. It closes the desktop and anything open in
it. Frame Control never edits the SDDM files itself, and runs nothing when the
headset is in Game Mode, when it can't tell which mode it's in, or when the
image has neither command.

**Uncertain:** whether the Frame offers a full Desktop Mode session at all
(only the nested desktop has been seen on BUILD_ID 20260922.6101926 and
20260925.6191901), and whether `steamos-session-select` there works without
the Developer Mode password. If the switch is refused, Frame Control says so and
leaves the headset as it was.

### Manual fallback

If the button can't help, or the headset isn't reachable:

1. **Restart it:** hold Power about 10 seconds until the light goes off, then
   power on. On the Steam Deck, **Switch to Desktop** starts a one-shot
   Desktop Mode session, so a restart brings Game Mode back. That the Frame
   behaves the same is **inferred**, not tested.
2. **Over SSH** (Developer Mode on), run Valve's switch yourself:
   `ssh frame steamos-session-select gamescope`.
3. **Boot menu:** hold Power 10 seconds, then power on while holding the AUX
   button on top of Power. Choose `Current`, or `Previous` to start the other
   SteamOS slot; both keep your data. Details and the further options
   (`Repair Steam Installation`, `Erase User Data`, a full re-image) are in
   [how-the-frame-works.md](how-the-frame-works.md#facts-worth-knowing) and
   [recovery-and-images.md](recovery-and-images.md). Back up first if you can:
   `Erase User Data` is a factory reset.

## Verification

`tests/test_backup.py` runs the headset-side script (`ui/frame_backup_remote.py`)
for real against a folder laid out like the Frame's home, with only SSH faked:
which paths are picked, that sign-in files and keys never are (also inside game
folders), links never followed, the manifest and its checksums, restore checks
after a reset (game not installed, no Proton folders yet, not signed in), that a
restore replaces only its own files and keeps the old ones, unsafe archives
(`..`, absolute paths, links, other games' folders) writing nothing, backup
names that try to leave the backups folder, and the exact Game Mode command.
`tests/e2e/test_recovery_kit.py` backs up a Proton save from the fake Frame through
the server, deletes it and restores it. Neither involves a real headset.
