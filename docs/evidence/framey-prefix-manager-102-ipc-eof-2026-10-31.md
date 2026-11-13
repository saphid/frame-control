# GitHub Games Prefix Manager 1.0.2: stop after child IPC EOF

This repair is limited to the separately published GitHub v1.0.2 archive,
SHA-256 `12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`.
The pinned live-store fixture for ID 130 remains **1.0.1**. Its installed files,
receipt, catalog classification and required shim are unchanged. GitHub 1.0.2
still has no catalog compatibility claim (`unverified`) or store selection.

The [preceding full native matrix](https://github.com/saphid/frame-control/blob/5817bc9573845627bbfbdba2af033b2deecabcab/docs/evidence/framey-tabmaster-full-native-main-controls-2026-10-31.md)
recorded one forced plugin kill after 40 successful v1.0.2 safety RPCs. This
fixture reproduces a matching failure by closing one owned Unix IPC peer.
Without the repair, a subsequent RPC times out and cleanup logs a forced kill.
The old managed-source negative skips that RPC and records the forced stop
explicitly. The original intermittent failure did not retain socket history;
its precise cause is not established by this reproduction.

## Repair and preserved behavior

Only this exact GitHub archive receives the existing shared child-process EOF
adapter. Its original Decky framing and dispatch remain in use; a closed peer
ends its connection loop instead of spinning on empty reads. The parent loader
and other plugins are not patched. The shared adapter itself is unchanged.

Before prefixing the adapter installation, the installer independently requires
the previous managed backend SHA-256
`96786bc3609b34d449a72b9159e01bd46b40d6c9b4e28ae384e64ffeab387478`.
Everything below the prefix is byte-identical to that backend. Existing root
request removal, actual-user paths, bounded prefix backups/deletes, preserved
backups, ambiguous-ID and symlink/traversal refusals, disabled orphan cleanup,
and refusal of `delete_game_folder=true` remain in place. Other managed files
are unchanged except the receipt's added `prefix-manager-102-ipc-eof` shim and
one added helper. No real user prefixes are used.

## Native verification

The focused run uses the published, digest-verified **Decky 3.3.0 AMD64** loader
in network/device/session-isolated containers. Sixteen source fingerprints bind
the final run to `a7a04498` (full revision in the JSON record).

- Store 1.0.1: 39 safety RPCs pass; this is not a new strict lifecycle claim for 1.0.1.
- Repaired GitHub 1.0.2: 42 RPCs, including readback after peer EOF and after
  restart, pass. Two parent-only loader stops finish below five seconds, with
  zero forced kills, selected shutdown errors, or surviving owned identities.
  Adopted child exit codes are zero. Both backup ZIP hashes and the outside
  marker survive, and an unrelated sibling remains alive.
- Previous managed GitHub 1.0.2: 40 safety RPCs pass, then the deliberate EOF
  regression requires one forced kill after five seconds. This is an expected
  negative, explicitly marked as an unsuccessful compatibility result.

The published plugin has **no custom `_unload` hook**. The strict repaired test
requires the child's missing-hook diagnostic, completed framework stop, zero
forced kills and owned process cleanup; it does not claim a custom hook ran.
The parent's generic “has been stopped” message alone is insufficient because
Decky emits it after a forced kill too.

An independent audit reconstructs baseline and candidate installations: all
installed store 1.0.1 bytes match; the GitHub 1.0.2 backend retains all previous
safeguards; the helper matches the unchanged shared source. All 116 catalog rows
and policies, the other 36 native dispatch bodies, and the other 33 case records
are preserved. Source hashes, process evidence, RPCs, full consoles and verifier
source are retained in the [JSON audit](framey-prefix-manager-102-ipc-eof-2026-10-31.json)
and [compressed raw record](framey-prefix-manager-102-ipc-eof-2026-10-31-raw.json.gz).

## Other checks and limits

The full server suite passed **1,942 tests**, with 16 platform/optional skips,
in 253.928 seconds. Website tests passed all 18 cases. Generated compatibility
documentation and diff checks passed. The full server suite ran at runtime
commit `50924649`; two later corrections changed only the native lifecycle
assertions, which the final focused native run exercises. The installer source
is identical across those commits. The isolated installer method passed with
no skips. Baseline/candidate production install comparisons also exercised
the GitHub 1.0.2 archive directly, independently of the store fixture.

The installer fixture executes production HTTP/SSH install, receipt and removal
transactions for **37 pinned store archives**, including 1.0.1. It does not
install GitHub 1.0.2 or execute official plugin backends. Owned Compose resources
and image tags are removed and their absence checked.

No full native matrix, ARM64, browser refresh, real Frame, Steam CEF,
wearer-visible behavior or controller proof was performed in this turn. Earlier
browser evidence remains historical. Generic runtime-console cleanup fields do
not qualify a plugin's shutdown; the repaired GitHub 1.0.2 case has its own
strict lifecycle assertions. Exact PR-head hosted CI/e2e/native/package and
current-main, feedback, mergeability and integration gates remain required.
No merge or release is authorized by this local evidence alone. The separate
hourly headset schedule is unchanged.
