# Intel Mac acceptance test: official v0.4.39, 26 October 2026

Tested on the physical **MacBookAir9,1, Intel Core i3-1000NG4 1.10 GHz,
8 GB RAM, macOS 15.7.7 (24G720), x86_64**. Job `1vbt29ptkw` repeated the
[earlier release test](mac-v0439-2026-10-26.md) and added ZIP verification,
native menu actions and Open at Login persistence. The app under test was
the official [v0.4.39 release](https://github.com/saphid/frame-control/releases/tag/v0.4.39),
tag commit `fd0b0a946f11d92fd1cc480cd9d1a83be795bf71`.
It was not rebuilt or patched. Current source validation is reported separately.

## Download and clean DMG installation

Downloaded both Intel assets and `SHA256SUMS` from that exact tag with
`gh release download`. Independently calculated SHA-256 values matched the
same-release manifest:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `Frame-Control-mac-x64.dmg` | 169,230,398 | `f47b5a188b5090f97a72467394d4fa65ccc73fe3169a6276e2a32cab5c8019d8` |
| `Frame-Control-mac-x64.zip` | 169,141,014 | `bafc1aec0c11c1fae097dbe1e4b585ebc13a0f8eaf1b249717c14d78811e08d7` |

Mounted the DMG read-only with `hdiutil attach -readonly -nobrowse` and
unpacked the ZIP separately. For each app, `file` reported
`Mach-O 64-bit executable x86_64` and `lipo -info` reported:

```text
Non-fat file: …/Contents/MacOS/Frame Control is architecture: x86_64
```

The DMG's bundled Python and `frame-mac-view` are also x86_64; `adb` is
universal with x86_64 and arm64 slices. Both fresh bundles passed
`codesign --verify --deep --strict --verbose=2`. Signing is ad hoc, with no
TeamIdentifier. This verifies the resource seal, not Apple notarization.

Preserved the existing `/Applications/Frame Control.app` in the task's
temporary directory. An initial `ditto` overlay retained that installation's
extra Python bytecode caches and failed signature verification. Moved that
copy aside and copied the DMG app into an empty destination. The clean copy
passed `codesign --verify --strict`; the release bundles themselves passed.
The final installed app is the clean DMG copy.

## Gatekeeper: tested fallback, incomplete first-open coverage

The CLI downloads had **no `com.apple.quarantine` attribute**. This Air had
already launched the same app in the earlier job, so it is not a pristine
first-install trust environment. A controlled probe added only this app's
quarantine attribute (`0083;<timestamp>;FrameControlIntelReleaseTest;`).
That is synthetic metadata, not a Safari or Chrome download.

The overlaid copy's first `open` returned 0 and later produced a translocated
app process. After making the clean copy, a quarantined `open` returned:

```text
The application cannot be opened, error=Error Domain=NSPOSIXErrorDomain Code=16 "Resource busy"
```

Assessment of the clean copy with `spctl --assess --type execute -vv` did
not finish within 15 seconds. No readable Gatekeeper warning was captured;
the controlled probe is **inconclusive**. Do not interpret `open` returning
0 as proof of passing Gatekeeper. Native screen capture was unavailable.

The exact app-specific fallback used for the verified clean copy was:

```sh
xattr -dr com.apple.quarantine "/Applications/Frame Control.app"
```

The installed app then launched successfully. No global Gatekeeper setting
was changed. For a normal user, verify the Intel download, mount the DMG,
drag the app to Applications and open it. If macOS blocks it, Apple's
documented route is **System Settings → Privacy & Security → Open Anyway →
Open**, after the initial attempt. **Right-click Open and Open Anyway were
not exercised in this run**; neither is certified here. The Terminal command
above is the fallback actually exercised, limited to this trusted app.

## Official native app checks

Controlled runs disabled telemetry and used a task-local server data
directory. A temporary loopback CDP port inspected the actual Electron
renderer and its real `window.frameApp` bridge. This was not a web-only
substitute. Native menu actions used Apple's Accessibility API through an
existing authorized SSH session; no Accessibility grant was added. Direct
System Events/AppleScript calls timed out. The API route is why this run can
verify native menu actions that the earlier evidence left untested.

| Check | Result |
|---|---|
| Launch | **Pass.** Native window, real IPC bridge and bundled Python server loaded. Version remained 0.4.39 |
| Offline UI | **Pass.** Apps, Games, Tools, Settings, Privacy & updates, Capture & Live and Decky rendered their expected headings |
| Decky store | **Pass.** Official store returned 116 plugins, with 40 initial rows. Search displayed ProtonDB Badges 1.3.4 and its compatibility text. Install stayed disabled; no loader or plugin was installed |
| Settings save | **Pass.** Native preferences initially `{}`; `mvSeparate="0"` saved, read back and survived a real app restart. Restored the original absence of the preferences file afterward |
| Update check | **Pass.** Native IPC returned `available`, current 0.4.39, latest 0.4.40, `error=null`, `canInstall=true`. The actual Check for Updates menu action also succeeded. No update installed |
| OBS Start/Stop | **Partial.** Native status supported/idle → Start on port 15139 returned starting → Stop returned stopping → idle. This checks local helper lifecycle; no OBS receiver or headset stream was exercised |
| Open at Login | **Pass for toggle and persistence.** Native menu began unchecked. AXPress returned success, then the checkmark appeared. Native Quit/relaunch preserved it. Toggled off and independently read the unchecked menu back. Actual logout/login execution remains untested |
| Show Server Log | **Partial.** Native menu AXPress succeeded and launched Console. The log contains startup with the installed bundled Python/server paths. The viewer's displayed document was not independently read back |
| Intel Mac helper | **Pass for read-only commands.** `permissions`, `displays` and `windows` returned JSON. One 1440×900 built-in display was listed; screen/accessibility permissions were false. No capture or permission request was initiated by these commands |

[Native searched Decky store screenshot](intel-mac-v0.4.39-2026-10-26.png).
[Structured observations](intel-mac-v0.4.39-2026-10-26.json).

## Headset: read-only checks and one temporary transfer

`frame.local` resolved, but its LAN port 22 returned **No route to host**.
The Tailscale endpoint answered TCP 22, but direct SSH and the app refused
the Air's stale/missing host trust. No pin was replaced to bypass that
failure. Used the already-pinned `saphid@lxso2` coordinator relay and its
trusted `frame` SSH connection instead.

Atomically acquired `/tmp/frame-test.lock` on the coordinator and headset
with owner `intel-v0439-1vbt29ptkw-20261026`. Under those locks:

- Read SteamOS **0.5.6**, variant `vr`, build **20261022.6153909**.
- Read battery **99%, Not charging**.
- Read home storage: **996,984,774,656 bytes total**, **769,012,412,416 free**.
- Listed **7** JPEGs matching Steam's
  `userdata/*/760/remote/*/screenshots/*.jpg`; no screenshots were copied.
- Sent a **54-byte** payload originating on this Mac through the relay into
  an exclusively created `/tmp/intel-v0439-1vbt29ptkw-20261026-…/` folder.
  Its readback SHA-256 matched
  `82029b7e8b519bac65e43a6e90386a06da9988b23330aa7c48fea0abdfac0a8b`.
  Deleted the exact file and its temporary folder.
- Released only matching owned locks. Separate readback confirmed the
  headset lock was absent immediately after release. A later independent check
  found the transfer folder absent and coordinator lock absent, while the
  headset lock had been acquired by another job (`frame-smoke-92bb2294f1d9cd4b7084`);
  that different owner was left untouched.

This verifies a relay transfer, **not the native app's direct file-transfer
path**. No existing headset content, installs, services, settings, power
state or SteamVR state was changed. No wipe or reboot was attempted.

## Bugs, validation and remaining limits

No new Intel-specific product bug was isolated in these runtime checks.
The earlier v0.4.39 shutdown race already has a merged fix in
[PR #284](https://github.com/saphid/frame-control/pull/284), shipped in
v0.4.40. This run did not install or validate the v0.4.40 Intel app.

The initial full source suite on system Python 3.9 ran **1,621 tests in
818.353 seconds**, with **six failed assertions and 20 skips**. These were
source-test issues, separate from the released native checks:

- The recording fixture's time limit ended with `q`, because macOS Bash 3.2
  reports read timeout as status 1, the same as EOF. Frame Bash 5 reports a
  value above 128. Local recording-shell tests now explicitly require Bash 4+.
- The Foundation XCTest test found `swiftc` but failed `import XCTest`:
  the active Command Line Tools installation has no XCTest framework.
  It now checks for the actual framework and skips when unavailable.
- Two OBS tests (three assertions, including subtests) started 0.15/0.3-second
  watchdog clocks before the fixture's Python interpreter and signal handler
  were ready. Fixture startup is now synchronized or separately budgeted;
  the short stream-stall checks remain. Production watchdog limits did not change.
- The panel timeout fixture's 4.6-second sleeps were too close to each tool's
  five-second timeout once process startup was included, causing the wrong
  failure path. Three-second sleeps still exhaust the 12-second overall
  deadline before a panel is complete, with margin for process startup.

All four affected modules then passed on this physical Air with the official
app's bundled Python 3.12: **87 tests, two explicit prerequisite skips,
37.605 seconds**. Focused native app tests passed **14/14** and website tests
**18/18**. An isolated Linux checkout of base `741735a` plus the exact four
test-file changes passed the **full 1,621-test suite, 16 skips, 170.313 seconds**,
including recording-shell fixtures under modern Bash. No full Mac suite pass
after these corrections is claimed.

Final native cleanup confirmed the app processes and loopback debug port were
closed, original preferences restored, Open at Login off, the DMG ejected and
its installed signature still valid. External test subprocesses had generated
36 Python bytecode files inside the bundle; removed only those absent from
the verified clean release before the final signature check. The native app
uses `-B` itself. The installed desk cleanup tool reported
only **Finder, Messages and cmux** in front, **zero notifications**, no items
needing attention and the **display asleep**. The official app remains installed;
previous copies and raw test logs are retained in `/tmp/frame-control-v0439-intel`.
The desk hold is released at the end of the task.

Actual login startup, ordinary browser quarantine/first-open override,
direct app/headset transfer, real OBS audio/video, Mac screen capture,
headset VR interaction, wearer comfort and controller input remain untested.
No social post was made. PR #113 was left untouched; merging and releasing
remain with the lxso2 coordinator.
