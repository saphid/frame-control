# TabMaster private native settings fixture

TabMaster 2.15.1 had an earlier isolated AMD64 browser/read check, but no reproducible native CI case for its settings or restart behavior. This adds its exact published archive and an unmodified-backend case to the existing AMD64/ARM64 Decky 3.3.0 workflow. It changes no production adapter, install policy or plugin source. TabMaster remains **partial**.

The archive's SHA-256 is `e08333859a32b0c177b8e9a7959c5eeeafe38f946578f7f1d161c721f0e05da5` (5,712,641 bytes). The pinned CDN bytes match the catalog. The live store API returned HTTP 403 during this work, so this is not a fresh full-store metadata audit.

A local **AMD64-only** published Decky replay at source `86fb3b8c1185315f970b13d1e45c4457961ee7d9` passed 40 actual API1 RPCs. It checks the actual fixture user's Desktop path, empty defaults, false values, separate users' tabs/profiles/friends/game lists, global tags, shared-tab visibility filtering, private JSON disk readback and persistence across a loader restart. Both owned loader exits returned zero in about 0.214 seconds; the fixture checks captured PID/start-time identities are gone. All seven source fingerprints, pinned loader, exact archive/backend bytes and returned RPC records were independently audited in the adjacent [JSON evidence](framey-tabmaster-native-settings-2026-10-30.json). Disk and process-absence assertions remain source-bound observations, without a retained container image or complete process snapshot.

The complete private loader console is retained. It has one `Expecting value: line 1 column 1 (char 0)` diagnostic; that original capture did not prove its phase or cause, and an error-free console is **not claimed**. Both startup/shutdown sequences, exit codes and identity checks pass. There is no shutdown-error/cancellation traceback or bad-file-descriptor message in the successful replay. This is not a real systemd service or release smoke test. A [later instrumented AMD64 observation](framey-tabmaster-json-startup-2026-10-31.md) traces an empty settings-file read before initialization or shutdown; it does not establish the cause of every occurrence or an ARM64 diagnosis.

The first local replay failed at the first stop: the fixture sent SIGTERM to the whole owned process group, producing a nonzero parent exit and signal-wakeup errors. The revised fixture signals only the loader parent, matching the managed service's `KillMode=mixed` signal policy, and verifies descendant identity reaping. A second replay passed that exit/reaping check but failed a broad JSON-diagnostic assertion. The final fixture retains that diagnostic and full console instead of claiming all logs are clean. The adjacent audit preserves both failed log hashes and their distinct limits.

ARM64 and fresh exact-PR CI still need to pass. This case does not connect the earlier browser to this backend or verify Steam library-tab editing, library/MobX patches, backups/restores, real Steam CEF, a managed Frame installation, wearer-visible UI or physical controllers. No headset was contacted and no user's data was read or changed.


## Current main refresh, 2026-10-31

Main `51841728090a45f9f452b4cd4ccf93f4caf8df14` was merged normally. Frozen source
`a6a32451af03d9f0079251aebbcd9fdf82e0d716` retains all 31 main probe bodies and
the original TabMaster probe, main's exact store/keyboard/IPC/ownership sources,
all 116 catalog policies and the other 115 complete records. Additive inventory
conflicts retain TabMaster, Ludusavi and Deck Progress. An initial local merge
preparation failure was corrected before testing or pushing; it is recorded in
[the refresh audit](framey-tabmaster-main5184172-refresh-2026-10-31.json).

The refreshed source passed 105 focused host tests and local native AMD64's
40 literal TabMaster RPCs, private settings and two parent-only zero-exit stops.
All twelve source fingerprints, original backend/archive bytes, full console
hashes and exact process-reaping assertions were independently checked. The
one JSON diagnostic remains unlocalized in that replay. Owned native containers and
image tags were removed. Subsequent commits add evidence only.

The full refreshed native matrix is 40 probes / 34 archive pins / 12 source
fingerprints; this targeted run does not qualify that full matrix. Final-head
hosted CI/e2e/native AMD64/ARM64 and every package gate remain required. No real
Frame, browser/backend integration, backup/restore or Steam editing proof is
added by this settings-only PR; the separate stacked #501 owns the restore fix.

## Qualified-main refresh, 2026-10-31

Main `012f874906bd122c29e75a0c9d572980b41a1085` was merged normally at tested
source `b141914f880536dcf917ab2755d8fb08f9cd4c66`, retaining the held diagnostic
evidence commit `ef1f16f213bdd8f397e7e13e060300662628328b`. All 31 main probe
bodies, the TabMaster probe, all catalog policies and the other 115 complete
records remain unchanged. Production store/input/IPC sources match that main.

The refreshed source passed 92 focused host tests and a new published Decky
3.3.0 AMD64 replay: 40 literal settings RPCs, original backend/archive bytes,
14 exact source fingerprints, private settings persistence, and two parent-only
zero-exit loader stops with source-bound PID/start-time reaping checks. Its full
available console is hash-bound and retains one JSON diagnostic. This replay is
unmodified-backend evidence; the earlier instrumented diagnosis remains a
separate observation. No new owned containers or image tags remain.

The [refresh audit](framey-tabmaster-main012f874-refresh-2026-10-31.json) and
[raw reports and unit log](framey-tabmaster-main012f874-refresh-2026-10-31-raw.json.gz)
bind this result to the tested source. The full new native matrix is 41 probes,
34 archive pins and 14 source fingerprints per architecture; this single-case
AMD64 replay does not qualify that matrix. Exact final-head CI/e2e/native and
all triggered package gates remain required. Compatibility stays partial; no
Steam library editing, browser/backend integration, backup/restore, managed
Frame, wearer/controller or release proof is added.

## Catalog diagnostic wording correction

The compatibility row previously called the unattributed JSON diagnostic a
shutdown diagnostic. Remove that phase attribution: the retained settings replays
do not localize it. The separate instrumented AMD64 observation in
[the startup diagnostic record](framey-tabmaster-json-startup-2026-10-31.md)
traces one empty settings read before initialization/shutdown; it does not
establish the cause or phase of every occurrence or ARM64 behavior. Historical
raw reports are retained without rewriting their bytes.

This correction changes the TabMaster reason and its generated documentation
only; no compatibility status, install policy, runtime source, archive or
observed result is promoted. Current hosted results remain bound to their
exact tested head. The correction is carried by the normal main refresh below;
final exact-head gates remain required before merge.

## Refresh onto main d3ae60e

Normally merged main `d3ae60ebed19829e3a3ae43ed1ea3766e0cee45f` into
the correction at source `d340158d1e12dba40f9690c53985f8d86e200925`.
That main's hosted jobs were still pending at the time of this local replay;
integration does not qualify main or authorize a merge. No history was rewritten.

All 31 main probe bodies and the complete prior TabMaster probe remain unchanged.
All 116 catalog install/status policies, the other 115 complete catalog records
and production store/input/IPC sources match main. The TabMaster reason drops
the unsupported shutdown-phase attribution. All 92 focused host tests passed;
the generated compatibility document and diff checks passed.

A fresh isolated AMD64 replay with digest-pinned published Decky 3.3.0 passes
the 40 settings RPCs, private settings/restart assertions, original archive and
backend pins, and all 15 current native-source fingerprints. Both parent-only
loader stops return zero. The integrated generic cleanup records both loaders
as already exited; it does not claim another signal or clean plugin shutdown.
The complete available console and its hash are retained, including one JSON
diagnostic whose phase/cause this replay does not establish. No full process
snapshot was retained; PID/start-time reaping remains a source-bound assertion.

The [refresh audit](framey-tabmaster-maind3ae60e-refresh-2026-10-31.json)
and [raw native report](framey-tabmaster-maind3ae60e-refresh-2026-10-31-raw.json.gz)
record the exact source and limits. Hosted checks/e2e, native AMD64/ARM64 and all
triggered package modes must be requalified at the final head. Earlier artifacts
remain historical. Compatibility stays partial; no headset or release proof
is added.
