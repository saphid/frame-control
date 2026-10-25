# Physical Mac desktop check, 26 October 2026

Host: **MacBook Air (MacBookAir9,1), Intel Core i3 1.1 GHz, macOS 15.7.7
(24G720), x86_64**. This is physical hardware. The console is an unattended
server with display/automation restrictions. No Apple Silicon runtime result
is inferred from this test.

## Released installers: verified, installed, cannot run on Intel

GitHub's latest release was v0.4.35 at the start; v0.4.36 became latest during
the check. Each DMG and its SHA256SUMS were downloaded from that exact release
with `gh release download`. Both passed `shasum -a 256 -c SHA256SUMS
--ignore-missing` (only the downloaded asset was checked):

| Release | Asset | SHA-256 |
|---|---|---|
| v0.4.35 | Frame-Control-mac-arm64.dmg | `eda670748679ca02fcf242870cd53954b22cf8b93af47a193c9903bd08a8334f` |
| v0.4.36 | Frame-Control-mac-arm64.dmg | `4d13068f0cfd3616823d63c82333afa7e368c1d57d375e9564f5f7ed4f0ebbd7` |

Each read-only DMG was mounted with `hdiutil attach -readonly -nobrowse`.
There was no existing `/Applications/Frame Control.app`; the app was copied
there with `ditto`, the command-line equivalent of the DMG's drag to
Applications. `open "/Applications/Frame Control.app"` returned exactly:

> The application cannot be opened because it has an incorrect executable format.

`file` identified the executable as `Mach-O 64-bit executable arm64`.
`codesign -dv` identified an ad hoc signature with no TeamIdentifier. The
v0.4.35 `spctl -a -vv` assessment returned `rejected`. The v0.4.36 assessment
stalled and is not counted as a completed assessment.

**No Gatekeeper warning dialog was observed.** LaunchServices rejected the
architecture first. The CLI download had no `com.apple.quarantine` attribute,
so this was not a browser-quarantine test. Neither right-click Open, Open
Anyway nor removing quarantine was tested. On this Intel Mac there is no
honest opening workaround for either released ARM64 app. Rosetta does not
run ARM64 apps on Intel. The README now separates that fact from Apple's
recommended Open Anyway flow for compatible Macs and labels the latter
unverified here. No global Gatekeeper setting was changed.

## Separate Intel candidate: partial native runtime pass

[PR #262](https://github.com/saphid/frame-control/pull/262), commit `6ea9eb2`,
adds native x64 DMG/ZIP builds, pinned x64 Python, an x86_64 Swift helper, and
CI architecture checks. Swift 6.2.4 rejected an ambiguous
`Data.withUnsafeMutableBytes` overload in the helper; an explicit
`UnsafeMutableRawBufferPointer` annotation compiled successfully on this Air.

`npm run dist:mac:x64` completed locally, producing an ad hoc signed app,
ZIP and DMG. The unpacked candidate was copied to
`/Applications/Frame Control Intel Test.app` and launched with telemetry off,
a task-local server data directory and a temporary loopback debug port.
This is **not** the published v0.4.36 binary.

The first launch stalled for several minutes before app code ran. A process
sample showed only `_dyld_start`, a 12 KiB footprint and no loaded image
list, while `syspolicyd` used about 89% CPU. It later proceeded without any
system-service restart; the app window and server loaded. The initial stall
is a host observation, not proof of a Frame Control bug. Restarting that
security daemon was rejected by automatic approval review, and was not done.

| Check | Observed result and limit |
|---|---|
| Native window and IPC bridge | The Electron renderer displayed Apps and the offline identity warning; `window.frameApp` was present. Native renderer inspected through its temporary loopback CDP port; this does not prove every macOS permission dialog or physical click |
| Settings | Native preference read returned `{}`. Writing `mvSeparate="0"` read back correctly. The original preference file was restored byte-for-byte (or removed when originally absent) in a finally block. Persistence across an app restart is not claimed |
| Open at Login | Source is opt-in and focused login-item tests passed. Native menu read via System Events timed out; an OS login session and actual checkbox state remain unverified. No login item was enabled |
| Logs | `~/Library/Logs/Frame Control/server.log` exists. Its startup line proves the candidate used `Contents/Resources/python/bin/python3` and its bundled `ui/server.py`; HTTP reads and offline failures were logged. Show Server Log menu interaction was not verified |
| Update check | Actual `frameApp.update.check()` completed with `status="none"`, `current="0.4.36"`, latest `0.4.36`, and `error=null`. No update was installed; native dialog dismissal was not verified |
| OBS setup and lifecycle | Native status reported supported/idle, Start on port 15123 reported starting, Stop reported stopping, then idle. The Frame's SSH identity rejection prevented a headset stream. This checks local lifecycle only: no OBS app, audio/video delivery or receiver tested |
| Decky store | The exact released UI/server resources, separately served by this Mac's existing Python 3.9.6, loaded 116 official entries in local Chromium. Forty rows rendered; searching ProtonDB found ProtonDB Badges 1.3.4; all Install buttons stayed disabled while offline. No loader or plugin was installed. [Browser screenshot](mac-decky-browser-2026-10-26.png) |
| Other UI | Released Apps, Settings, Privacy & updates, Tools, Capture & Live and Decky views rendered. The privacy page correctly reported telemetry blocked by `FRAME_CONTROL_TELEMETRY=0`; sharing/contact choices were left alone. The activity log displayed the offline failure. The browser path hides native OBS buttons as designed; it is not a substitute for the native lifecycle check above |
| Framey preview | No standalone local preview control was found in the desktop UI. The Framey panel belongs to the headset runtime; no VR or plugin-backend result is claimed |

The released server refused a stale SSH host identity rather than silently
trusting it. That safety check was preserved; no host pin was replaced just
to make the test pass. Capture, media, game launches, power controls, installs,
sign-ins and notifications were not triggered without a working connection.

## Headset: read-only relay checks, no changes

`frame.local` resolved on the Air, but direct TCP/SSH did not connect. The
coordinator host lxso2 could reach it. The app's read-only `frame_status.py`
was piped through lxso2 to the Frame and returned:

- SteamOS **0.5.6**, build **20261022.6153909**, variant `vr`.
- Battery **99%, Charging**.
- Home storage: 996,984,774,656 bytes total, 769,023,275,008 bytes free.
- A read-only search counted **14** Steam screenshot JPEGs; none was copied.

The shared `/tmp/frame-test.lock` was owned by another Framey test on each
check. This job did not acquire, remove or replace it. File upload/delete,
OBS on the device and every other headset mutation were skipped. These relay
reads do not prove the native Mac app's direct SSH or file-transfer path.
The headset was never wiped or rebooted.

## Validation and follow-up

A disposable Linux checkout of exact commit `6ea9eb2` on lxso2 passed:
**1,590 server tests (16 skipped)** and **46 app tests**. On the physical Air,
**14 focused login-item/preferences/OBS tests** and **18 website tests** passed.
Full Mac server/release suites were attempted but spawned helper programs
stalled and timed out during the policy-service problem; they are not a pass.
Node 22's complete app run cancelled sign-in tests around an unreferenced
timeout; the exact same app suite passed on lxso2. CI uses Node 24.

Required next steps: pass exact-head Mac packaging/architecture CI, publish
an Intel asset through coordinator job mppkd9qczt, then repeat a normal
browser-download/quarantine installation of that release on this Air. Verify
Open Anyway and Open at Login through an authorized interactive console.
Acquire the shared headset lock before a temporary transfer or real OBS test.
Preserve all unverified labels until those checks actually pass. PR #113 was
not changed. No social post was made.
