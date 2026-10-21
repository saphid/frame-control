# Installing APKs (Lepton)

The confidence labels are the same as in [ssh.md](ssh.md). Android apps run
in **Lepton**, Valve's Waydroid-based container. Lepton is built for games,
not general Android use
([GamingOnLinux](https://www.gamingonlinux.com/2026/09/lepton-from-valve-to-run-android-games-on-linux-is-now-open-source/)).

**VR streaming clients:** WiVRn 26.9 and ALVR 20.14.1 install, but both fail
OpenXR instance creation on the checked Frame because its Android runtime lacks
`XR_KHR_convert_timespec_time` (**verified** 2026-09-28, SteamOS 0.4.1,
BUILD_ID 20260925.6191901). They are not Frame Control dependencies. See
[the feasibility results and options](linux-vr-streaming.md).

## Install from the Mac: one app, one Lepton instance (verified 2026-09-25)

Use Frame Control's **Android apps** section (search, Install, Test, Report), drop
an `.apk` on **Send to Frame**, or:

```sh
./scripts/install-apk.sh some-app.apk            # own instance, Steam shortcut
python3 ui/frame_android.py list|launch|stop|remove|probe <package>
```

Each APK becomes its own app, the way T3 Code is set up (see the instance
section below), instead of going into Lepton Development:

1. `ui/frame_apk.py` reads the package, label, version, ABIs and icon
   (a stdlib parser of the binary manifest and resource table, so no Android SDK). APKs that need
   API > 30 or have no `arm64-v8a` build are refused.
2. The APK, `frame/android/lepton-app.sh` (as `launch.sh`), `instance.id`,
   `meta.json`, the icon and the `lepton-show-flatscreen` marker go to
   `~/Applications/Android/<package>/` on the Frame.
3. A non-Steam shortcut is added through Steam's CEF debug port
   (`frame/android/steam_shortcuts.py`), with no Steam restart.
4. Launching the shortcut runs Lepton directly with `SteamAppId` set to the
   instance id (`2800000000 + crc32(package) % 70000000`). That's a
   "steamlaunch" context, so app data in `compatdata/<id>/internal` survives
   restarts and updates, and each app gets its own SteamVR panel. Several can
   run at once alongside Lepton Development, each in its own container
   (`lepton-steamlaunch-<id>`, ADB on 5556, 5557, …).

Split APKs (a base plus `split_*.apk` files) install as one app:
`python3 ui/frame_android.py install base.apk split1.apk …`. Lepton runs one
APK, so splits that add native libraries or assets are merged into the base
and re-signed; density and language splits are refused. See
[quest-import.md](quest-import.md#split-apks). A generated native app plus asset
split was installed and relaunched on a real Frame on 2026-10-18; this does not
verify arbitrary games or unsupported split types.

Verified with AntennaPod and Tabletop Tools: installed in about 7 s, launched
from the shortcut, stopped, and relaunched with their data intact. ADB and
Lepton Development aren't involved.

`--dev` keeps the old path: ADB into Lepton Development over an SSH tunnel
(first free Mac port from 15555), which starts Lepton Development if needed.
Apps installed that way are deleted when it exits (see below). No pairing or
"Allow debugging?" prompt is needed for either path.

Lepton Development must be installed once. Over SSH,
`ssh frame 'steam steam://install/3056000'` queues it, but the install still
needs to be confirmed or started in the headset.

## Games with extra data or split APKs

**Send to Frame accepts Android package sets, not just single APKs.** Select
matching files together or drop a ZIP-based Android bundle. Files are grouped
by their actual manifest package; the base is identified from its manifest,
not its filename or selection order. Imports wait in the existing install
queue and stay tied to the selected headset.

| Input | What happens |
|---|---|
| One `.apk` | Checks API/ABI/VR compatibility and installs as its own app, retaining its filename and install reporting. Replacing an installed app with an older standalone APK remains possible. A split without its base, or a base marked as requiring missing splits, is refused. |
| Base plus split `.apk` files selected together | Merges supported native-library and asset splits into one APK for Lepton. All must match the package and version. |
| `.xapk`, `.apks`, `.apkm` | Unpacks and checks one app's APK set, standard OBB files and `Android/data` files, then uses the same install/data paths. |
| Android `.zip` | Detected by its APK/OBB/data contents. PC-game ZIPs keep the title-import route. A ZIP containing PC executables takes that route even if it includes an Android build. |
| `.obb` with its APK, or after installing the APK | Associates standard main/patch filenames with their package and copies into that app's running Android instance, not `~/Downloads`. |
| `.aab` | A publishing bundle, not an installable app. Export a device APK/APKS set using the developer's build tools first. |

This grouped local-file importer is the source change for issue
[#102](https://github.com/saphid/frame-control/issues/102).

**Verified with generated fixtures, 2026-10-18:** a real arm64 app and asset
split installed on a Steam Frame. A second import copied matching OBB and
`Android/data` bytes, closed the app, and relaunch confirmed all three payloads
were readable inside it. RE4 gameplay and updates remain unverified.

### Games with companion data take two imports

An APK can install successfully but quit, hang or request a download when its
assets are missing. For a local bundle or APK/OBB selection:

1. Drop the files together. Frame Control checks the entire selection before
   changing any app, installs the APK and says if game data still needs copying.
2. Start that game's Steam shortcut and leave it open. Drop the **same files**
   again (or just the matching OBB). Frame Control checks the installed package
   and exact APK version, copies the data and closes the game.
3. Relaunch from Steam. A successful copy verifies transfer integrity, not
   whether those assets are the right ones for that game build.

Standard archive layouts are `base.apk` (or another base filename), split APKs,
`Android/obb/<package>/main|patch.<version>.<package>.obb` (or a standard OBB at
archive root or in `<package>/`), and `Android/data/<package>/...`. One shared
enclosing folder is accepted. OBB filenames must belong to
the app; use its matching assets, rather than renaming unrelated files. To
import an external data folder, ZIP its `Android/data/<package>/...` tree;
a loose folder drop still uses the PC-game workflow.

**Limits:** only native-library and asset splits can be merged. Resource,
density, language, code and feature splits fail with a specific reason; they
are never silently omitted. A universal APK or a compatible device-specific
set from the developer is needed instead. Bundles with multiple base APKs
(e.g. several device variants) are refused rather than choosing arbitrarily.
Repacking re-signs the APK, as the existing launcher fix does. See
[split limits](quest-import.md#split-apks).

Archives reject unsafe/duplicate paths, encrypted entries, links, special
files and unrecognised payload files. Recognised metadata (manifest/info JSON,
SAI v1/v2 JSON, icon, APKS table and APK incremental-signature files), Finder
`__MACOSX` sidecars, `.DS_Store` files and files named `._*` (AppleDouble) are
not installed, including inside `Android/data`. Metadata still
counts against archive limits and must pass the path/link/encryption checks.
Loose filenames follow the same portable path rules: rename files with colons,
trailing dots/spaces or Windows device names before importing them. Empty
companion files reject the selection before upload; they are never omitted
silently. Sets with splits or companion data cannot replace a newer or unknown
installed version. Close a running app before replacing it.
The import limit is 4,096 archive entries/files and 16 GiB in total; each
uploaded file is also subject to the server's 8 GiB upload limit. Staging must
have sufficient free disk space. Abandoned uploads expire after an hour;
finished, failed or removed queued imports clean up their uploaded files.

Data copying still needs the game's own Lepton instance to stay running.
**A game that exits immediately without its assets cannot use this data path
yet.** Frame Control does not start games implicitly or guess a host-side
`/sdcard` location. The generated fixture verified app-side readability after
relaunch; persistence through app or SteamOS updates and individual games'
storage requirements remain unverified.

If the game is already on your Quest, [Import from my Quest](quest-import.md)
uses the same two-step data workflow and can bring supported splits and
optional external app data. Quest import is on main/draft 0.4.7, absent from
public 0.4.6. The [local OBB CLI helper](sidequest.md#obb-files) remains available:

```sh
python3 ui/frame_android.py info /path/to/game.apk
python3 ui/frame_android.py install-obb org.example.game /path/to/main.42.org.example.game.obb
python3 ui/frame_android.py stop org.example.game
```

For that CLI path, install the APK and start its Steam shortcut first, wait
for a successful copy, then stop and relaunch. Retry the complete data set
after a partial failure before playing.

**Installation is not a compatibility verdict.** OBB files cannot fix an
unsupported ABI, a newer Android requirement, missing VrApi/OpenXR features,
or Meta services/licence checks. See [Quest compatibility limits](quest-import.md#what-wont-run-and-why).

## Diagnosing an APK game report (including RE4, issue [#102](https://github.com/saphid/frame-control/issues/102))

The RE4 screenshot says the APK "didn't work" and suggests missing OBBs. It
doesn't identify the game edition/build or show an error, so missing OBBs
remain a hypothesis. There is no verified RE4 compatibility result here.

1. Record the computer OS, Frame Control version, SteamOS/Lepton build and
   exact game edition/platform. List filenames and sizes (APK, base/splits,
   OBB, `Android/data`) without sharing game assets. From a source checkout,
   `python3 ui/frame_android.py info /path/to/game.apk` reads local package,
   version, minimum API, ABI and VR warnings without connecting to a headset.
2. Identify the first failure: upload/installation error, no Steam shortcut,
   Lepton not starting, or the game opening then quitting/hanging/asking for
   data. Save the exact Activity error and **Frame → Show Server Log** excerpt.
   Remove credentials, account details and private paths before sharing.
3. If installation succeeded, establish whether that exact build needs
   companion data. Use the matching data workflow above, then relaunch. A
   successful transfer only proves the bytes reached Android. Don't uninstall
   as a first diagnostic step: it deletes saved data.
4. If it still fails, **Test** in Android apps (or
   `python3 ui/frame_android.py probe org.example.game`) launches the game and
   reports instance-start failure, a running process or a crash summary.
   "Runs" means the process survived a short check, not that gameplay works.
   A missing-assets error supports the OBB hypothesis; a VrApi, entitlement,
   missing-library or Android-service error points elsewhere. Review relevant
   crash-log excerpts if the summary is empty; an empty crash buffer does not
   establish compatibility.

## When an app needs a newer Android

Lepton is Android 11 (API 30), with arm64-v8a only. If Frame Control refuses
an APK, it shows compatible versions from F-Droid's main and archive repos and
IzzyOnDroid. It shows at most eight version names, newest first, preferring an
arm64-only build, and says how many compatible builds it found in total.
Each index is reduced to its compatible builds once a day and cached (about
16 MB). The first lookup takes about 30 s and 100 MB of memory; later ones are
instant.
Choose **Install** to download a listed version, verify its SHA-256 against
the index, and install it as its own app.

You can also inspect a file or look up a package from the command line:

```sh
python3 ui/frame_android.py info some-app.apk
python3 ui/frame_android.py versions some-app.apk
python3 ui/frame_android.py versions org.example.app
```

The search links open APKMirror, APKPure, Uptodown, F-Droid and GitHub. Pick a
version whose minimum is Android 11 or lower and that has an arm64-v8a build
(or no native code). Frame Control does not fetch APKs from those search sites.
Older versions may lack fixes, and being installable does not guarantee an
app will run: see the missing services below. Android may refuse a downgrade
or an update signed by a different publisher; removing the app deletes its data.

## Installed apps disappear when Lepton Development closes (verified 2026-09-25)

Lepton Development runs in a throwaway "dev" context. When it exits for any
reason (you close it, or it crashes), the launcher script
`~/.local/share/Steam/steamapps/common/Lepton/lepton` calls
`clear_baked_app_data "non steamlaunch container"` and **deletes every app
installed over ADB**. The journal shows `Clearing baked app data due to non
steamlaunch container`, and `pm list packages -3` is empty afterwards.

The script skips the wipe when `LEPTON_NO_CLEANUP` is set
(`liblepton/liblepton.sh`, `clear_baked_app_data`). To keep your apps, set
Lepton Development's Steam launch options to:

```
LEPTON_NO_CLEANUP=1 %command%
```

(Steam → Library → Lepton Development → Properties → Launch Options.) Inferred
from the script, not yet tested across a restart.

## Which APKs work (verified 2026-09-25, SteamOS build 20260922.6101926)

Lepton is LineageOS 18.1 (`lepton_arm64_only`): Android 11, API 30,
`abilist=arm64-v8a` only, Mesa (Turnip, Adreno 750) with GLES 3.2 and
Vulkan 1.4. About 30 F-Droid apps were installed and opened on the Frame to
check each rule. The results are in the compatibility database (see compat-db/README.md).

**Won't install** (the installer refuses):

| Rule | Seen on device |
|---|---|
| `minSdkVersion` > 30 | `INSTALL_FAILED_OLDER_SDK: Requires newer sdk version #33 (current version is #30)` |
| Native code without `arm64-v8a` (32-bit ARM or x86 only) | `INSTALL_FAILED_NO_MATCHING_ABIS` |

**Crash on launch.** Lepton has no `clipboard` system service, so
`getSystemService(CLIPBOARD_SERVICE)` returns null:

| What | Result |
|---|---|
| **Jetpack Compose UI < 1.11** | Crashes as soon as a Compose screen appears: `null cannot be cast to non-null type android.content.ClipboardManager` in `AndroidComposeView`. Seen with 1.5, 1.6, 1.7, 1.8 and 1.10 apps. |
| Jetpack Compose UI 1.11, 1.12, 1.13 | **Works.** Six apps opened fine, including Aurora Store and NewPipe. |
| Old Compose, but the first screen uses classic Views | Opens (FoCal, Compose 1.3), and crashes only on Compose screens |
| SDL2 apps, including Kivy | Crash: SDL calls `ClipboardManager.addPrimaryClipChangedListener` at start-up |
| Godot 4.3 | Crashes (clipboard cast). Godot 4.6.1 works. |

**Works:** classic Android Views apps, Flutter (2 of 2), libGDX (2 of 2),
Compose 1.11+, Firebase-using apps. React Native: 2 of 3 opened; one
(controlloid) died with SIGSEGV on the Hermes JS thread. A Qt 6 app
(AusweisApp) failed on a missing libc++ symbol.

**Missing pieces:** an app may open but fail when you use one of these:

- No Google Play Services.
- No activity for `VIEW` of web links, `OPEN_DOCUMENT`/`GET_CONTENT` (no file
  picker), `IMAGE_CAPTURE`, or text-to-speech. WebView (Chromium 152) is there.
- No Downloads or Contacts providers.
- Missing system services also include `accessibility`, `vibrator`, `phone`,
  `print`, `usb`, `nfc` and `autofill`. The declared features lack
  `touchscreen.multitouch`, `bluetooth_le` and `telephony`.
- No on-screen keyboard (IME) is installed. How text entry reaches Android
  apps in the headset hasn't been checked.

**Lepton itself can crash.** Three times during testing, the graphics HAL
(`android.hardware.graphics.composer@2.1-service`) aborted right after an app
crashed. SurfaceFlinger died, the whole `lepton-dev` container exited, and the
installed apps were wiped (see above). A retry of the same app worked, so it's
intermittent rather than app-specific.

**How good are the predictions?** In a random sample of 12 apps rated "Should
work", all 12 installed, opened and were still running 12 s later (two needed
a retry because Lepton crashed mid-install). "Opened" isn't the same as fully
working: see the missing pieces above.

## Catalogue and compatibility reports

Frame Control's **Android apps** section lists every F-Droid app with a
verdict: Works on Frame, Should work, Might work, Probably crashes, or Won't
work, with the reasons. As of 2026-09-25 that's 30 working, 3,323 should work,
223 might work, 723 probably crash (mostly Compose < 1.11) and 156 won't
install. Each app is rated on its newest version that Lepton can install,
because F-Droid often publishes separate per-ABI builds and the newest is
frequently x86_64. **Install** downloads the APK (SHA-256 checked against the
F-Droid index) and sets it up as its own instance.

No ProtonDB-style database for sideloaded Android apps on the Frame existed
as of 2026-09-25. [Steam Frame Hub](https://verified.steamframehub.com/)
collects community reports for Steam games only and has no public API, and
Valve's "Great on Frame" badges and each Steam app's `recommended_runtime`
(for example `lepton-stable`) also cover Steam games only
([VR.org](https://vr.org/articles/steam-frame-lepton-android-runtime-52-of-130-certified-2026)).
So Frame Control keeps its own. Your reports are saved on your Mac; the
maintainer's copy also syncs them to a private Lakebed database.
**Test** records whether the app stays up in its own instance, and **Report**
(for any APK, F-Droid or not) records whether it worked, how it was run, where it came from, and notes, each with the SteamOS and Lepton build ids.
See
[compat-db/README.md](../compat-db/README.md) and
[apk-catalog/README.md](../apk-catalog/README.md).

## In-headset app store: F-Droid 1.17 (verified 2026-09-25)

F-Droid 1.23 uses an old Compose and crashes on launch. **F-Droid 1.17.2**, the
newest archived build without Compose, runs, loads the full catalogue (the
first repo update takes about 90s), and can install apps. F-Droid 2.0 uses
Compose 1.12, so it should work, but it hasn't been tried. The catalogue's
Install button for F-Droid installs 1.17.2. To let F-Droid install apps without
a settings prompt, with the tunnel open:

```sh
adb -s $S shell appops set org.fdroid.fdroid REQUEST_INSTALL_PACKAGES allow
```

## Handy commands

Open a tunnel by hand (use any free local port):

```sh
ssh -f -N -M -S /tmp/frame-adb.sock -L 127.0.0.1:15555:127.0.0.1:5555 frame
adb connect 127.0.0.1:15555
S=127.0.0.1:15555
# when done: adb disconnect $S; ssh -S /tmp/frame-adb.sock -O exit frame
```

Then:

```sh
adb -s $S shell pm list packages -3              # installed third-party apps
adb -s $S shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1
# If monkey exits with -5 (it did for T3 Code), start the activity directly:
adb -s $S shell am start -W -n "$(adb -s $S shell cmd package resolve-activity --brief -c android.intent.category.LAUNCHER <pkg> | tail -n 1)"
adb -s $S logcat -d -b crash                      # why an app died
adb -s $S uninstall <pkg>
adb -s $S exec-out screencap -p > shot.png        # the Lepton window
```

## Reaching a Mac service from Lepton (T3 Code v2, verified 2026-09-25)

Lepton runs in podman with `pasta` networking. It has **its own loopback**, so
a port on the Frame's `127.0.0.1` isn't visible as `127.0.0.1` inside Android.
But pasta runs with `--map-gw`, so the **gateway address inside Lepton
(`192.168.1.1` on the home network) maps to the Frame host's loopback**.

T3 Code v2 on the Mac listens only on `127.0.0.1:3873`. To reach it:

1. Keep `ssh -N -R 127.0.0.1:3873:127.0.0.1:3873 frame` running on the Mac,
   for example from a LaunchAgent with `KeepAlive`, so launchd restarts it if
   it drops.
2. In the app on the Frame, the environment host is `192.168.1.1:3873`.

The app on the Frame was built from the T3 Code v2 nightly source with `expo prebuild` and `gradlew assembleRelease
-PreactNativeArchitectures=arm64-v8a`, using Homebrew `openjdk@17` and the
`android-commandlinetools` SDK. It's signed with the debug key.

To pair again, issue a one-time code on the Mac and type it into
**Add environment**:

```sh
A="/Applications/T3 Code (V2 Preview).app"
ELECTRON_RUN_AS_NODE=1 "$A/Contents/MacOS/T3 Code (Alpha)" \
  "$A/Contents/Resources/app.asar/apps/server/dist/bin.mjs" \
  auth pairing create --base-dir "$HOME/.t3-v2" --ttl 15m --label "Steam Frame"
```

The app is deleted whenever Lepton Development closes (see above), so reinstall
it afterwards or set `LEPTON_NO_CLEANUP=1`. The gateway address comes from the Frame's network when Lepton starts. On a
different network, check it with `adb shell ip route` and edit the host.

## Lepton Development forgets apps; give an app its own instance (verified 2026-09-25)

**Lepton Development wipes every installed app when it exits.** Its launcher
logs `Clearing baked app data due to non steamlaunch container`, unless
`LEPTON_NO_CLEANUP` is set. A Steam-style launch (with `SteamAppId` set) is a
"steamlaunch" context and keeps its data:

- App data lives in `STEAM_COMPAT_DATA_PATH/internal/<package>` (symlinked to
  `/data/data/<package>`) and survives everything, including APK updates.
- `STEAM_COMPAT_DATA_PATH/baked` is Lepton's Android snapshot. It's rebuilt when
  the APK changes, or when the app exits within 30 seconds of starting.
- `STEAM_COMPAT_DATA_PATH` must be under `~/.local/share/Steam` (use
  `steamapps/compatdata/<id>`). Only that tree is mounted in the container. Put
  it anywhere else and the symlinks dangle, so the app crashes with
  `ENOENT` on its first file write.
- Lepton runs apps headless unless an empty `lepton-show-flatscreen` file sits
  next to the APK (`STEAM_COMPAT_INSTALL_PATH`).
- Several instances can run at once. Each gets ADB on `5555 + offset`
  (`podman ps --format "{{.Names}} {{.Labels.adb_port}}"`).
- Outside Steam, Lepton's `setpgid --foreground` re-exec fails with no
  terminal. Set `IS_PARENT=true` and start it with `setsid --wait`.

[`frame/t3code/launch.sh`](../frame/t3code/launch.sh) does all this for T3
Code (context `steamlaunch-2873873873`; ADB is the first free `5555 + n`, e.g. 5557). It needs the Steam client
running (it mounts `~/.steam/steam.pipe`).

**T3 Code in the Steam library (verified 2026-09-25).** The wrapper lives on
the Frame at `~/Applications/T3Code/launch.sh`, with `t3code.apk` and the
flatscreen marker next to it. It's a non-Steam shortcut called "T3 Code"
(shortcut app id `3130509679`). Launching it from Steam gets its own SteamVR
panel, `valve.steam.desktopgame.3130509679`, and opens already paired.

- The shortcut was added without restarting Steam, through Steam's CEF debug
  port (`127.0.0.1:8080` on the Frame, target `SharedJSContext`):
  `SteamClient.Apps.AddShortcut(name, exe, "", "")`, then `SetShortcutName`
  and `SetShortcutStartDir`. `steam steam://addnonsteamgame/<path>` only logged
  the URL and added nothing.
- To launch it over SSH: `steam steam://rungameid/13445436691150012416`, which
  is `(3130509679 << 32) | 0x02000000`.
- Steam sets `STEAM_FOSSILIZE_DUMP_PATH` for shortcut launches but not
  `STEAM_COMPAT_SHADER_PATH`. Lepton then dies with "unbound variable", so the
  wrapper sets both.
- To update T3, replace `t3code.apk`. Lepton rebuilds its snapshot on the next
  launch, and the pairing survives.

## Crashing apps can take down the headset session (verified 2026-09-25)

Some apps crash Android's graphics composer HAL, which kills the Lepton
container. On 2026-09-25 a batch crash-test also coincided with `steamvr.service`
restarting "on client request", which stops and SIGKILLs `gamescope-session`.
After one of those kills, gamescope crash-looped about once a second on
`rendervulkan.cpp:2181 ... Assertion '!modifiers.empty()'` because it kept
attaching to the SteamVR processes orphaned from the dead session. The fix
without sudo was to `for p in vrdashboard vrcompositor vrserver; do pkill -TERM -x $p; done` (pkill takes one pattern). The
next session then started SteamVR fresh and recovered within a minute.

## Android display: resolution, UI scale, text size (verified 2026-09-25, SteamOS 0.3.0, build 20260922.6101926)

Each running Lepton instance has its own ADB port on the Frame, assigned at
launch: 5555 is Lepton Development, and own-instance apps take the next free
port (T3 Code was on 5557). Find them with `ss -ltn` (5555–5599) and identify
each with `pm list packages -3`. Both instances reported `Physical size:
1920x1080`. Their densities were 180 dpi (Lepton Development) and 213 dpi
(T3 Code), and `settings get system font_scale` returned `null` (1.0).

These all apply immediately and read back as set. Tested on Lepton Development
only:

```sh
adb -s $S shell wm size 2560x1440         # or: wm size reset
adb -s $S shell wm density 240            # or: wm density reset
adb -s $S shell settings put system font_scale 1.15
adb -s $S shell settings delete system font_scale
```

After a `wm` reset, Android writes `font_scale=1.0` back asynchronously, so a
single delete that follows one reads back `1.0`. A second delete a second later
leaves it `null`. Frame Control's **Android display** card does this for you
(`/api/android/display`).

**Inferred, not yet checked in the headset:** a bigger Android resolution with
density scaled to match (2560×1440 at 4/3 of the density) gives sharper text,
because gamescope scales Lepton's surface to fit the same panel. Also unverified:
whether the settings survive the app or its Lepton instance relaunching.
Lepton Development rebuilds its Android data on exit, so there they probably
don't.

## Expansion files and save backups

SideQuest-inspired CLI helpers install local OBB files into an already-running
app instance and back up/restore a stopped instance's private app data. See
[SideQuest features and limits](sidequest.md) for commands, archive scope and
verification status. These paths have offline coverage; real Frame storage and
permissions remain unverified. They do not change APK install or launch behavior.
