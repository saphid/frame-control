# PlayTime with ScreenSaver main — 2026-11-01

Implementation `964e85b83c5d56ce761cd0ecb045d1d4d6535917` normally merges prior #511 head `81b046d8425f0b867b944ba7e2f9a3d05872a048` and main
`ad070b731386dfbc2c8ed24b901b0b5edaeacbf2`. Three shared-file conflicts retain both exact native cases and pins.
Whole checker/runner/pin/inventory/doc-generator AST audits outside the PlayTime
additions match main. All **36 prior native cases**, **116 install/status policies**
and **115 other complete catalog rows** remain. **1,743 other main files**,
including current main evidence and mandatory CI/ownership/package sources,
are byte-identical. Production code except the one PlayTime catalog note is
unchanged. PlayTime's archive, all 40 original Python sources and native helper
are unchanged from the prior PR head; ZIP SHA-256 is
`10fc3beea48991c77cb02867e919b618d4cd6d5e9c6a6d0ccd5266c13214039f`.

## Fresh combined-source verification

- **119 focused tests, zero skips**, covering transactions, compatibility,
  native inventory, exact ScreenSaver environment/ownership, shared IPC and
  official panel packing. Generated compatibility docs pass their check.
- Published Decky **3.3.0 native AMD64**, in networkless/device-free disposable
  containers: **22 PlayTime RPCs**, 40 unchanged Python source hashes, six SQL
  readbacks and two independently decoded read-only SQLite snapshots with
  integrity checks. Private manual writes, paused-session refusal, two-user
  isolation and restart persistence pass. Two owned parent-only stops exit
  zero in about 0.215 seconds and their owned identities are reaped. Full
  process snapshots and global clean-plugin shutdown remain unverified; the
  generic shutdown recorder stays false.
- Same-source ScreenSaver regression: **31 RPCs / 14 independent D-Bus calls**,
  busy-owner refusal without delayed queueing, three inhibit APIs, actual peer
  disconnect release, settings restart and two strict parent-only clean stops
  including real IPC EOF. Independent dbus-python calls verify the backend's
  unchanged vendored dbus-next behavior. Existing bus owner, unrelated sibling,
  marker and settings metadata are preserved. Actual suspend/UI/Frame use is
  unverified.
- Both native reports bind the same **32 runtime source hashes**, matched to
  this implementation. The evidence-only publication changes none of them.
- Full fake-Frame e2e: **53 tests / zero skips**, 408.273 seconds; **116 exact
  archive pins**, **69 install/removes** and **47 expected refusals** pass.
  PlayTime's managed HTTP/SSH install, receipt, frontend transport and removal
  pass. Official backend execution is stubbed here; native behavior is covered
  separately above. Owned Compose containers and volumes are gone. Socket
  ResourceWarnings remain.

## Gates and limits

Prior head `81b046d8425f0b867b944ba7e2f9a3d05872a048` completed all 16 hosted checks. Its four signed-package
modes are independently qualified with **154 distinct sources / 1,351 hash
bindings**. That packet and its hosted AMD64/ARM64 native records apply to the
prior head; they do not qualify this integrated implementation. Exact final-head
hosted full CI, native AMD64/ARM64, e2e and every triggered package/ownership gate
remain required, along with exact current-main green, reviews and mergeability.
No merge or release is qualified by this local packet.

PlayTime stays partial. Private MobX running-app observation is unsupported;
automatic recording, actual Steam library callbacks, existing-user database
migration, browser/Steam CEF, managed Frame and wearer/controller behavior remain
unverified. ScreenSaver's private bus fixture is not proof of actual suspend
inhibition. No real headset, schedule, security setting or pre-existing user
data was touched. Store130 remains 1.0.1; GitHub1.0.2 is a separate exact asset.
Syncthing installation remains disabled.

[Summary](framey-playtime-mainad070-integration-2026-11-01.json) · [Raw reports, snapshots, logs and verifiers](framey-playtime-mainad070-integration-2026-11-01-raw.json.gz).
