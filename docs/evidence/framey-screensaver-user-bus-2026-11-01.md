# ScreenSaver configured user bus — 2026-11-01

Implementation `9132a56393bac21cc1df274dc02b40d01d2f6711`; base main `89757d33f61124486404bc16e84b7d3697cf2c9f`.
Exact store **87 / ScreenSaver 1.1.2**, archive
`5e61f20d53e244c55a0375d6299b16cdb9701c222519c7fecd726f1926091822`;
original backend `21969c9cf387012c980a0330051dfa5fd961037b160d0a3bac6498138f20c29d`.
The archive comes from the earlier digest-verified catalog cache; this does
not claim a freshly queried live store version.

The published import sets HOME=/home/deck and runtime/session bus UID 1000.
A private environment-dictionary fixture reproduces all three overwrites. The
managed import preserves the entire configured environment instead; only that
exact backend environment block is removed, plus scoped helper/IPC hooks.
Every other archive member remains byte-identical, including vendored dbus-next.
The backend uses the configured session bus only, acquires all three names
with DO_NOT_QUEUE and no replacement flag, refuses an existing desktop owner,
and closes a partially acquired connection. Start/stop is serialized. Stop,
unload and restart clear this connection's stale inhibitor map/events and
release its names; future starts after unload are refused. Settings behavior
and all four exported object paths remain compatible.

## Verification

- **Eight focused tests**, three native inventory tests, 25 compatibility tests
  and 18 site tests pass. **1983 full unit tests / 15 platform or
  optional skips**, 259.892 seconds. The managed-import test compares the
  entire environment. The earlier site glob selected zero tests; that result
  is retained and not counted. The actual 18-test invocation passed.
- Published Decky **3.3.0 native AMD64**, no network/devices/host session bus:
  **31 actual legacy RPCs** and **14 independent D-Bus client calls**. The
  plugin uses its unchanged vendored dbus-next; the oracle uses system
  dbus-python against a disposable user bus. ScreenSaver, PowerManagement and
  Gnome Inhibit/UnInhibit APIs, the /ScreenSaver alias, ignored Steam application labels,
  positive unique cookies and last-inhibitor events pass. These are client
  invocation/reply records, not captured raw D-Bus packets or real app playback.
- An existing private desktop service remains its owner, with no queued plugin
  takeover; releasing that owner does not cause delayed plugin ownership.
  Explicit retry then acquires all names. Closing a real inhibitor client
  releases its request. Explicit stop clears stale cookies and events.
- Two independently checked parent-only loader stops exit zero under five
  seconds, including controlled Unix EOF, with no forced plugin kills. Exact
  descendants disappear and adopted exits succeed. Names are released after
  each stop; a separate bus name, sibling process and unrelated marker
  bytes/inode/mode/mtime survive. Both settings values, including false,
  persist through a fresh loader, with settings file hash/inode/mode/mtime
  unchanged. The generic recorder does not certify plugin clean shutdown;
  those two scoped stop observations do.
- All **29 runtime input hashes** and installed backend/helper/IPC hashes match
  this implementation. The full installer/APPLY AST outside exact store 87 and
  native checker outside its two fixture branches match main. All 34 previous
  native cases and **1,721 other existing main files** remain.
  Other 115 complete catalog rows match; all 116 archive pins, flags,
  classifications and install policies are unchanged. Compatibility stays
  **partial**; existing managed copies need Update/reinstall.
- Isolated fake-Frame e2e: **53 tests / zero skips**, 402.503 seconds,
  all 116 pinned archives, 69 install/removes and 47 expected refusals. This
  suite stubs official backend execution. Owned Compose/temp resources are
  gone, prior image tags restored and shared simulator identity/start/health
  retained. Socket ResourceWarnings remain.

Two earlier native fixture attempts failed: an assumed dbus-python convenience
method was replaced by the real ListQueuedOwners method, then an assumed
settings display-name folder was replaced by discovery of the one settings
file in the disposable user home. The actual folder is DeckyInhibitScreenSaver.
The failed raw logs and results are retained separately; neither is counted
as a product pass. The production helper did not change between these trials.

## Limits

The actual Frame user bus and its existing owners, actual Steam suspend bridge,
rendered official controls, real app playback, client introspection, native
ARM64, Steam CEF and wearer/controller behavior are **unverified**. The bus
connection and event path do not prove physical suspend inhibition or a visible
VR overlay. An occupied desktop service is deliberately left alone, so startup
returns false in that case. No headset, schedule, security setting, existing
user data or PR #113 was touched. Fresh exact-publication hosted CI, native
ARM64, e2e and applicable ownership/package gates remain required. No merge or
release is qualified by this local proof.

The JSON and compressed companion retain raw RPC/client calls, owner/event
observations, consoles, process/file identities, source hashes, prior failures,
unit/e2e logs and the independent verifier.
