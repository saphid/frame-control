# TabMaster refresh against main dd41aed

PR #525 normally merges main `dd41aede875d7a6b7abac68520784824b96103e9`
at tested source `770edead5cb834a6fc886b2e0a7c3ce34599740f`. The two conflicts
were the runtime source inventory and installer payload dispatch. Both TabMaster
and main's Free Loader helper registrations are retained. The shared IPC adapter
is unchanged; no history was rewritten.

Fresh networkless AMD64 containers run the digest-pinned published Decky 3.3.0.
TabMaster's repaired/original/previous-managed controls make 47/48/47 literal
RPCs. The repaired case preserves private per-user settings, false values,
shared-tab filtering, backup/restore and malformed/non-object refusals, and
completes both controlled-disconnect and restarted ordinary stops in about
0.214 seconds with the original unload hook. The original backend still refuses
a valid backup restore; it receives no extra closed peer and stops normally.
The previous managed backend preserves the JSON restore repair but reproduces
a 5.224-second forced plugin kill without its unload hook, followed by a clean
ordinary stop. This is an expected negative, not a compatibility pass.

Main's repaired/original Free Loader controls make 11/7 RPCs and retain their
clean-positive/forced-negative outcomes. Independent settings/cache hashes and
parsed contents verify stop/restart preservation and the hidden-state change.
Both plugins retain consoles, recorded process identities, zero adopted-child
exit statuses, disappearance of recorded descendants and an unrelated surviving
sibling. Native container/image cleanup remains bound to the frozen runner.
The original TabMaster strict red test and all its original source hashes remain
in the evidence; it is historical, not a new red run at this integration source.

The [structured audit](framey-tabmaster-main-dd41aed-refresh-2026-10-31.json)
and [raw reports, logs, snapshots and auditors](framey-tabmaster-main-dd41aed-refresh-2026-10-31-raw.json.gz)
record the full server pass: 1,946 tests with 16 optional/platform skips, plus
18 website tests without skips. One production
HTTP/SSH installer method covers 37 pinned fixtures, exact receipts/backend
bytes and removal. Owned installer containers, volumes, networks and image tags
are independently absent afterward. It does not run official backends or replace
full e2e. All 17 native input hashes match this tested source. AST/catalog checks
preserve main's other 36 runtime bodies, other installer branches and payload
dispatches, the other 115 catalog rows and all 116 install/status policies.
The full matrix expects 44 probes/34 positive pins/17 inputs; only TabMaster and
Free Loader ran locally.

Separately, prior head `5817bc9573845627bbfbdba2af033b2deecabcab` hosted
AMD64 and ARM64 artifacts from run `41203828163` match GitHub ZIP digests,
successful exact-head checkout logs, 43 probes, 34 archive pins and 16 source
hashes per architecture. Both repaired TabMaster cases complete two clean stops
with unload hooks; both previous-managed negatives force-kill once. Literal
47/48/47 RPC sequences and original restore refusal match the fresh controls.
Those old-head results do not qualify this integration.

The old ARM64 artifact also retains positive forced stops for Deck Settings,
Battery Tracker and Simple Timer, already owned by #524/#519/#521, plus a new
Deck Shelves 2.0.0/store 135 failure. Deck Shelves' first stop force-kills before
its unload hook, while the restarted ordinary stop unloads normally. The exact
peer history/cause is unknown. Search found no open Deck Shelves repair; a
separate strict reproduction and scoped fix are queued after this integration.
The published archive digest is
`b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91`.
The raw artifact and audit preserve the failure. Unattributed JSON diagnostics
remain, so neither artifact success nor this scoped result proves a globally
clean runtime.

Fresh exact final-head CI/full e2e/native AMD64+ARM64/ownership/PC/all triggered
package modes and completed current-main CI remain mandatory. Compatibility
stays **partial**; Steam library-tab editing still has no library/MobX target.
No browser/backend integration, actual Steam CEF, real Frame, worn UI,
physical-controller or release proof was obtained. No headset, hourly schedule
or existing user data was accessed.
