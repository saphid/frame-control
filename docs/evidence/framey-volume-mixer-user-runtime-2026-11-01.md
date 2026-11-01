# Volume Mixer configured user audio — 2026-11-01

Implementation `b42f1f9d1e062adb2fa806aca4dfc980166d25d5`; base main
`ad070b731386dfbc2c8ed24b901b0b5edaeacbf2`.
Exact catalog pin **38 / Volume Mixer 1.2.1-1**, ZIP SHA-256
`11b259ad234d0e97cfef4e6a2af3f1edfb0908d5482765af56b86b0a4601c5f3`;
original backend `4fbe68db632397bd78b0bd35a46426825351a74ed168a6bbbd6fb65378b3fce2`.
The archive is from the prior verified catalog cache, not a fresh live-store lookup.

The published import overwrites HOME with `/home/deck` and XDG_RUNTIME_DIR with
`/run/user/1000`. The original backend was discovered by published Decky 3.3.0
under UID 1100 but its first get_sink_inputs RPC failed with `Failed to connect
to pulseaudio server` while a real private Pulse server and two silent streams
were live under UID 1100. No PULSE_SERVER override hides the lookup regression.
The original source is restored in a required negative fixture, and that exact
failure is asserted while independent pactl still sees both streams.

Exact managed installs replace just those two environment assignments with a
no-op and add the existing shared child IPC EOF adapter. Manifest name, legacy
API, empty flags, folder, ZIP digest and backend digest are checked. Every
other published archive member remains byte-identical, including vendored
pulsectl and ravel/dbussy. No root request, system service change, host audio
socket or real device is used. Old managed receipts require Update/reinstall;
the historical works classification is retained with its original scope.

## Verification

- **117 focused tests, zero skips** pass: transaction rollback/refusal, exact
  member preservation, actual-user environment preservation, old receipts,
  shared IPC, native inventory, official panel packing and compatibility docs.
  Only the environment function is compiled in the regression unit test,
  keeping the Python 3.9 suite independent of the archive's Bluetooth match/case.
- Published Decky **3.3.0 native AMD64**, private D-Bus, PipeWire/Pulse, silent
  null sink and two actual stereo pacat streams: **12 actual legacy RPCs**.
  Stream discovery, selected volume **0 / 0.25 / 0.731 / 1**, both channel
  values independently read with system pactl, RPC readback, stopped-stream
  removal and a fresh loader restart pass. The plugin uses its unchanged
  vendored pulsectl, not the oracle's pactl interface.
- Both parent-only Decky stops exit zero in about **0.215 seconds**, with no
  SIGKILL or shutdown errors, no exact surviving descendants and zero adopted
  child exit statuses. The first includes an actual extra Unix IPC peer EOF.
  The plugin's unload callback is independently observed in its own log.
  The unrelated Pulse stream, sibling process and marker bytes/inode/mtime
  survive both stops. This is scoped evidence; the generic recorder's
  cleanShutdownVerified flag remains false and no global cleanup proof is claimed.
- **32 runtime source hashes** match this implementation, including installed
  backend and adapter hashes. The entire installer/APPLY AST outside the exact
  store-38 branches matches main. All **36 prior native cases**, all other
  **115 complete catalog rows**, and all **116 pins, flags, classifications
  and install policies** remain. The runtime runner adds only this source
  input and original-source negative to its prior behavior.
- Full fake-Frame e2e: **53 tests / zero skips**, 407.733 seconds; all
  **116 exact archive pins**, **69 install/removes** and **47 expected refusals**
  pass. Volume Mixer's managed HTTP/SSH install/receipt/frontend/removal passes.
  Official backend execution is stubbed, so this is separate from native proof.
  Owned Compose containers/volumes are gone. Socket ResourceWarnings remain.
  The first full attempt failed because I supplied the cache parent directory
  rather than its archives subdirectory. Its 116 missing-ZIP errors and failed
  outcome are retained locally and are not counted as a pass. All 116 ZIP
  hashes were checked before the corrected full run; no product gate was waived.

The first repaired native attempt passed discovery and volume checks, then
failed a fixture assertion that assumed the child's goodbye was on stdout.
This published plugin redirects root logging to `/tmp/VolumeMixer-decky.log`.
The oracle now reads the actual unload callback there while retaining the
strict parent/descendant exit, timeout and forced-kill checks. Production
repair bytes did not change to address that oracle error.

## Limits

The original archive's historical Frame ARM64/browser evidence remains linked
in the compatibility table. The adapted backend has **no current-head native
ARM64, browser-to-backend, real-Frame, Bluetooth playback, audible-output or
worn/controller proof** in this local record. CI must qualify its exact PR
head separately. No headset was contacted, woken or given input. This change
does not remove the published plugin's process-local fixed temporary log or
change its Bluetooth commands. It does not qualify a release.

[Independent audit](framey-volume-mixer-user-runtime-2026-11-01.json) ·
[Native, original-failure and unit records](framey-volume-mixer-user-runtime-2026-11-01-raw.json.gz).
