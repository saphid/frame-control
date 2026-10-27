# MusicControl / Music Control runtime checks, 26 October 2026

Both official entries remain **partial**. Their pure-Python backends need a
user-session MPRIS player and `dbus-send`, rather than Deck-specific hardware or
an x86 binary. [Results](framey-mpris-runtime-2026-10-26.json) pin both archives
and the actual Decky 3.3.0 executables used.

Two runtime failures were reproduced and repaired:

- The #335 `music-control-bound-methods` transformation was incorrect. Neither
  manifest declares `api_version`, so Decky uses `module.Plugin` and explicitly
  supplies the class as `self`. The earlier test used `module.Plugin()` and
  therefore diagnosed a fixture error as an upstream bug. In actual Decky,
  the transformation breaks discovery with `_get_dbus_env() missing ... self`
  and transport with `_sp_player_dbus() missing ... parameters`. Managed installs
  now retain the original class calls. This supersedes the earlier
  [bound-method evidence](framey-music-control-bound-methods-2026-10-26.md).
- On Frame OS 0.5.6, MusicControl 1.1.6's `/bin/sh` subprocess inherits Decky's
  PyInstaller library path. Its bundled `libtinfo.so.6` needs `GLIBC_2.42`, which
  the Frame's libc lacks. A private diagnostic backend confirmed the same
  read-only D-Bus command fails with a shell and succeeds without one. Both
  exact-archive backends now restore `LD_LIBRARY_PATH_ORIG` (or an empty path)
  only in their copied D-Bus subprocess environment. The Decky process keeps
  its original environment. The receipt records `music-control-system-dbus-env`.

The patch is gated by store ID, SHA-256 and folder, and checks the expected
source before editing. Existing installed copies need **remove/reinstall** or
an explicit managed update; a desktop update alone does not rewrite them.
The store still shows partial, with the same reason as the docs table.

Actual Decky 3.3.0 amd64 ran each repaired production-managed install separately
in a container with no network, host audio, host D-Bus, home or device access.
A private `dbus-daemon` hosted a silent synthetic MPRIS service. Discovery,
selection, identity, metadata, status, progress, volume/CanSeek reads,
play/pause, next/previous, seek, track position and volume writes passed through
the real legacy websocket RPC envelope. The service's own state independently
confirmed each write. The shared plugin folder prevents co-installation; each
entry was tested in a fresh container.

Local headless Chromium loaded the shipped `headset.html` and exact official
frontends inside their ordinary opaque `allow-scripts` iframe. The relay used
actual Decky backends and allowed only the private fixture. Track/artist
rendering, previous/next, play/pause, seek to 90 seconds, volume to 60%, Info
navigation and close/reopen passed for both entries. Chromium retained its
normal process isolation and sandboxed-origin restrictions. No external media
or artwork request was permitted.

Under the shared `/tmp/frame-test.lock`, a removable private Decky 3.3.0 ARM64
user service loaded each corrected managed install on the real Frame.
Read-only `sp_list_media_players` returned an empty string successfully for
both, and `sp_get_media_player` returned their default Spotify bus name.
These final checks used Decky's direct loopback websocket through SSH; they
do not claim the deployed Framey HTTP/CEF route. Earlier CEF attempts encountered
transient reinjection failures. No player controls ran on the real Frame.
The private units, runtimes and owned Steam image-cache link were removed;
independent follow-up reads confirmed cleanup and lock release. Battery was
100 → 100. Existing managed Decky remained failed and the headset panel inactive,
as found. Power settings were not changed.

Remaining gaps: actual media-app playback/volume on ARM64, local-file album-art
routing, physical controls and worn VR. Both backends truncate multiword player
names to their last word. Music Control 1.1.7 automatically probes volume by
writing 0.01 and restoring it; this was exercised only on the silent fixture.

Validation: full Python suite **1,639 tests, 16 skipped**; focused managed-store
suite **23/23**; shared frontend action checks; all **116** store digests unchanged.
The complete fake-Frame audit passed: **61 installed/removed, 55 rejected**
for documented safeguards; official backends are stubbed in that harness. The
regression test uses Decky's actual legacy class convention for both entries,
checks original/absent library-path restoration without changing the parent
environment, and rejects transferring the patch to a different archive digest.

The pinned HTTP/SSH flow also passed `scripts/e2e.sh test_framey`: **2/2**
tests in 32.590 seconds. Its receipt assertion covers the replacement shim for
both Music Control entries; the old assertion caused the first hosted e2e
failure and left a plugin installed, cascading into the following test.
