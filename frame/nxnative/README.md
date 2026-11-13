# NxNative on Steam Frame

Experimental game bring-up through the Android/Vulkan fork in a persistent
Lepton instance. This runs a flat game panel; it does not convert the game to VR.
Metroid Dread 2.1.0 has physical Frame installation and runtime evidence. The
bundled [Celeste 1.4.1.1 profile](profiles/01002B30028F6000/README.md) has visible
gameplay, remote movement/jump input, audio and a successful cold save reload.
Celeste also passed cold Continue, movement and output audio after the final
shared renderer APK update. Both games remain experimental; physical controller feel and worn-headset comfort
are untested.
See [research and device results](../../docs/nxnative-on-frame.md).

The fork is pinned to `32b0ef2c5408e1e32cb5c0bc49f84d1e63653dc3`.
`android-frame.patch` contains the API 30/tool-path fixes, English settings,
versioned data selection, opaque Vulkan presentation, keyboard input, Dread movie
thread handoffs, and an opt-in app-process execution/Vulkan probe.
Game data, APKs and signing keys are kept outside this repository.

## Build on a Mac

Install Android NDK, Android SDK/build-tools, JDK 21, .NET 10, Python with
fontTools, spirv-cross and Xcode's Metal tools. Put the .NET runtime and
spirv-cross on PATH and set DOTNET_ROOT and DEVELOPER_DIR as needed.

Use your existing decrypted/extracted Dread 2.1.0 inputs. The exact module build
IDs are listed in the research document. `--extracted` names the directory with
ExeFS, icon.jpg, control.nacp, and either RomFS or NxNative's DMROMFS1 RomFS.img.
The shader package/cache are translation inputs; Apple patched binaries and
Metal libraries cannot be reused as Android outputs.

The builder reads each game's module list and verifies its exact NSO build IDs
against the profile before rewriting. Bundled metadata under `profiles/` takes
precedence over the pinned fork's profiles. Other versions need their own verified
profile; a title ID alone does not establish compatibility. Profiles contain
identities and layout metadata, not game binaries or translated shader bytecode.

```sh
export ANDROID_SDK="$HOME/Library/Android/sdk"
export ANDROID_BUILD_TOOLS="$ANDROID_SDK/build-tools/36.0.0"
export ANDROID_JAR="$ANDROID_SDK/platforms/android-36/android.jar"
export JAVA_HOME="$(/usr/libexec/java_home)"
python3 frame/nxnative/build.py \
  --source /path/to/separate/android-fork \
  --build /path/to/dread-frame \
  --extracted /path/to/original/extract/v327680 \
  --shader-package /path/to/original/shader/pkg \
  --shader-cache /path/to/original/shader/cache \
  --ndk "$ANDROID_SDK/ndk/27.1.12297006"
```

Run this with the Python environment that has fontTools. The script clones the
pinned fork if needed, applies the patch, extracts into a separate build folder,
rewrites modules with DM_PATCH_TP=android, exports SPIR-V, builds libdmhost.so,
and signs `game.apk`. It records actual shader tool fingerprints using the
fork's `--update-lock` and saves `toolchain.patch` in the build folder.
Do not point `--source` at PA's existing Apple checkout.

The current exporter runs the fork's Metal build chain to recover SPIR-V. It
therefore still needs the Mac tools, although the finished app uses Vulkan.

For a different verified profile, set `--title`, `--label`, and the inputs for
that exact game version. Celeste uses title `01002B30028F6000`, version `1.4.1.1`,
and modules `main`/`sdk` without `subsdk0`. Its MGFX shader extraction also needs
the newer upstream shader reader described in the profile README; the pinned
Android fork cannot extract those shader packages by itself. The generic build
command does not automate that extra preparation.

Games whose extracted files contain LÖVE Lua sources have a separate
[native Android packaging route](../love/README.md). That route requires
`main.lua` and a compatible LÖVE runtime; it does not use NxNative bundles.

## Install through the app

The app’s **NxNative games** section accepts your own catalog or local/mounted
network folder. It includes no game repository or ROM links. Add the completed
build folder directly on your Mac, or append
`--bundle /path/to/my-game.nxnative.zip --version 2.1.0` to `build.py` to create a
portable installer for your own HTTP(S) catalog or share. The app verifies and
installs its APK and dataset together. [Source formats and preparation steps](../../docs/nxnative-sources.md).

## Install and stage data

From a Frame Control checkout on the build host (or copy the small APK to the
computer with Frame Control):

```sh
python3 ui/frame_android.py install /path/to/dread-frame/game.apk --flat
python3 ui/frame_android.py launch com.nxnative.t010093801237c000
python3 frame/nxnative/stage.py 010093801237C000 /path/to/dread-frame
```

The first launch opens settings because data is absent. Stage with this app's
container running and its game process stopped. If the configured Frame SSH
route is slow, `stage.py --address <LAN-IP>` uses the LAN address while checking
the configured host's existing SSH identity.

Staging hashes every file, sends an independent directory with four parallel
GNU-format archive streams, verifies checksums
inside Android, then atomically publishes `frame-data.current`. An interrupted
or damaged transfer leaves the old selection intact. Previous datasets remain
available; staging never touches saves. After staging, reopen the app. It starts
the game directly by default; hold − and + for two seconds to return to settings.
The missing Android document picker is not needed.

Data lives under `/sdcard/Android/data/com.nxnative.t010093801237c000/files/`:

- `frame-data/<manifest-sha256>/`: modules, SPIR-V/reflection, fonts and RomFS.
- `frame-data.current`: the selected immutable dataset's digest.
- `env.txt`: optional diagnostic KEY=VALUE settings.
- `log.txt` and `log.prev.txt`: current and previous native game logs.

Saves live separately in the app's private `files/save` directory and survive
APK updates, container stops and dataset changes. Frame Control's backup-data
command can back up stopped-instance private data.

Set `DM_FRAME_PROBE=1` in env.txt for thread-slot, executable-memory and Vulkan
checks in the game's own NativeActivity process. `DM_FRAME_PROBE_ONLY=1` returns
after that probe without loading game modules. Remove diagnostics when finished.
Logs say explicitly whether the probe passed. A probe pass is not gameplay proof.

## Local checks

```sh
python3 -m unittest discover -s tests -p test_nxnative_data.py
python3 -m py_compile frame/nxnative/*.py
```

Tests cover DMROMFS1 extraction, corrupt/unsafe inputs, checksum rejection,
interrupted uploads, dataset publication/reuse, and keeping saves intact.

## Input and scheduling checks

Keyboard fallback uses WASD for the left stick, Enter/Z for A, Space for B,
X for Y (shoot), C for X and Escape for +. Controller buttons keep the fork's
position-based mapping. Frame controller axes and worn-headset comfort need
separate validation.

For automated device checks, run the input helper **on Frame**:

```sh
ssh frame python3 - A 200 < frame/nxnative/input.py
ssh frame python3 - MoveRight 1000 < frame/nxnative/input.py
```

It targets this game's selected persistent Lepton instance. It writes actual
Linux input events into Lepton's Wayland keyboard FIFO; Android's shell
`input` and InputManager injection did not deliver events in the inspected image.

The patch backports upstream's wake handoff ordering for Dread and replaces the
old three-second movie-ring waits. A runnable dispatcher and its workers must
reach a blocking boundary before the lower-priority caller continues. Dread also keeps its profile’s broader
preemption check for already-runnable workers; queue notifications do not always
wake a waiter. Contended native codec locks and job conditions count as blocking boundaries.
Dread uses this ordering with core serialization off by default; other games keep
the fork's original scheduling policy. Do not use `DM_CORE_SERIAL=1` for this
Dread experiment.

The Mac scheduling regression suite has 28 cases covering real thread SVCs,
delayed dispatch (1 and 20 ms), transitive wakes, unrelated busy peers, native mutex contention,
excluded equal-priority/other-core/host-helper threads, and the already-runnable
worker required by Dread’s preemption profile:

```sh
make -C /path/to/android-fork/dm/host/tests GAME=010093801237C000 frame-handoff
```
