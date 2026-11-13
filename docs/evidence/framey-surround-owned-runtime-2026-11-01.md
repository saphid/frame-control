# Virtual Surround Sound owned runtime — 2026-11-01

Implementation `f97033529497f527b757920f3e30c0996e85f530`; base main `9b2f3c2634a61767ebc52099f595229b2515d96f`.
Only store **100 / 0.0.5**, ZIP
`b6c514d147cc46bad5331ca9da36628eb9c330976e13735687499a4a9f17f6d4`.
Original backend SHA-256 `ed93c09f3aa2f37b917a0ed6539173096175fd277e69c47fc13127e22be35569`;
service source `8709a0fa2106bce08d5fb9e9913ef3184850354098b5ce645dde411a14748cda`.

The published backend overwrites `~/.config/pipewire/hrir.wav` when selecting a
preset and removes it on uninstall, irrespective of ownership. Its service
hardcodes `/home/deck` in every convolver, writes/enables a shared user unit,
changes shared directory permissions and has process-name/PID-file cleanup.
The installed-archive test reproduces shared-file deletion only in a disposable
path, then proves the managed backend retains the same bytes/inode/mtime.
No actual user audio, unit or HRIR file was changed.

The exact managed archive gets two plugin-local helpers and a bounded prefix
and suffix around all original backend bytes. Every other published member,
including filter graphs, frontend and license, is retained. The helper uses
bundled presets only, content-addressed private copies under Decky's plugin
runtime directory, JSON-quoted paths for the actual service user, non-lingering
filter nodes and an owned `pw-cli` process. Seven-channel HRIRs use the existing
5.1 graph; fourteen-channel HRIRs use the existing 7.1 graph. It never executes
the service script, writes a user unit, changes shared permissions, launches
D-Bus, migrates unrelated template files or signals processes by name/PID file.
An existing surround sink is refused and left untouched. Older unmanaged
services are not stopped or migrated automatically; resolve that conflict
before the managed filter can start. Existing copies need Update/reinstall.

Selection is validated before replacing the owned filter; invalid selections
leave it running. Successfully selected presets and per-app choices persist.
The original periodic check recovers an exited owned filter. Sound testing
runs one bounded command per channel in an owned task, with unload cancellation
and child reaping. Private HRIR copies/settings/logs are intentionally retained
on uninstall. No attempt is made to recover shared HRIRs already overwritten or
deleted by an older copy. Runtime needs `pw-cli`, `pactl` and working user
PipeWire/Pulse; sound test also needs `speaker-test` and its ALSA Pulse plugin.
Those dependencies and the actual Frame audio server have not been checked.

## Final-source verification

- **1984 full unit tests**, 15 platform/optional skips,
  256.043 seconds; **nine focused installed-archive/ownership tests**, three
  runtime inventory tests, 25 compatibility tests and 18 site tests pass.
  Compilation, generated-doc and diff checks pass.
- Published Decky **3.3.0 native AMD64**, device-free and networkless, runs
  **21 actual plugin RPCs** with private PipeWire, WirePlumber and Pulse.
  A real Pulse stream routes into surround and back to a private neutral sink.
  OpenAL and Steam Audio preset switches expose six/eight-channel sinks.
  Terminating only the exact owned filter is followed by actual-backend
  recovery. The native test observes speaker-test channels 1 and 2 before
  cancellation; a complete all-channel sequence is **not** verified.
- Two strict parent-only loader stops exit zero without a forced plugin kill;
  exact descendants are reaped, including an active sound-test child. Settings
  survive restart; shared HRIR/unit marker bytes, inode, mode and mtime survive,
  as does an unrelated sibling process. Installed backend/helper hashes and
  all **29 native runtime input hashes** independently match this commit.
  The generic recorder's clean-shutdown flag is false by design; the two
  explicit scoped stops are independently checked.
- Source audit preserves main's whole installer/APPLY AST outside this exact
  repair and checker outside its two added fixture branches. All 34 prior
  native cases remain; **1,717 other existing main files** are byte-identical.
  All 116 archive pins, flags, classifications and install policies remain;
  other 115 complete catalog rows match. Compatibility stays **partial**.

The full disposable fake-Frame suite passed **53 tests / zero skips** in
**403.487 seconds**, including all 116 exact archives, 69 install/remove and
47 expected refusals. This was a working tree based on `9b2f3c2`, **before** the
final helper child-reaping/sound-test revision; its runner's sourceRevision
field records the base, not a tested final commit. The installer/pin logic is
unchanged by that final revision, and this suite stubs official backend
execution. It supplies broad transport evidence, not final runtime proof.
Owned containers, volumes, network and temporary files were removed; original
image tags were restored and shared simulator identity/start/health retained.
Socket ResourceWarnings remain. Fresh exact-publication hosted e2e is required.

The first native attempt failed because a sibling-preservation assertion
compared transient scheduler state (R versus S). It was corrected to process
start/parent identity and liveness; failed output is retained. No producer
failure is treated as a pass. Later final-source evidence above is separate.

Full hosted CI/native ARM64, rendered official controls, audible quality,
physical audio, actual user audio routing, actual Frame backend and
worn/controller behavior remain **unverified**. The avatar proxy is still
unavailable. No headset, schedules, security settings or PR #113 were touched.
No merge or release is qualified by these local results.

The JSON summary and compressed packet retain raw RPCs, consoles, file and
process observations, source fingerprints, prior failure and audit programs.
