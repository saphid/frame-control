# TabMaster private backup and restore

TabMaster 2.15.1 passes an open file to `json.loads` in `restore_settings`. Its exception handler returns false even for a valid backup. The original failure was first reproduced through actual published Decky 3.3.0 API1, before applying the repair; the [original failure record](framey-tabmaster-original-restore-failure-2026-10-30.json) retains that failed replay and its limits.

The managed installer repairs only store 61, folder `TabMaster`, archive SHA-256 `e08333859a32b0c177b8e9a7959c5eeeafe38f946578f7f1d161c721f0e05da5`, and original backend SHA-256 `cd34adcd3ea0cef90ca96d8ceff15cbd86a5f3b6116da35eeb892e2fc4870347`. It changes the single incorrect call to `json.load` and refuses non-object JSON before replacing settings. API1, the frontend, license and every other archive member remain unchanged. A different archive receives no shim. Existing managed copies need update/reinstall to receive `tabmaster-json-file-restore`.

A local networkless disposable **AMD64** replay at source `226d1ee72b58a52cb2cc8c562491d242c9c8b581` passes both a repaired positive case (47 actual RPCs) and an unchanged-original negative case (48 RPCs). The positive case backs up private per-user state, mutates it, refuses malformed/list/null/string JSON without changing settings or the valid backup, restores exact original settings bytes, and verifies state after a loader restart. The negative case explicitly restores and verifies original backend bytes before RPC: its valid restore still returns false and preserves dirty state. It resets only private fixture tags through RPC before the restart checks. These checks make no general schema-validation or backup-path-confinement claim.

The [audit JSON](framey-tabmaster-backup-restore-2026-10-30.json) retains both full cases and consoles. All seven source fingerprints, loader/archive/backend hashes, discovery and RPC records were independently checked. Each case has two parent-only loader stops with zero exit and captured PID/start-time identity reaping checks. Disk readbacks and process-absence assertions remain source-bound observations; no complete process snapshot or container image is retained. The runner exited zero and performed its owned container/image cleanup.

Each case retains one `Expecting value: line 1 column 1 (char 0)` diagnostic. Those captures do not prove its phase or cause; an error-free console is not claimed. The earlier [unmodified settings fixture](framey-tabmaster-native-settings-2026-10-30.md) remains historical evidence for a separate source revision. A [separate instrumented AMD64 observation](framey-tabmaster-json-startup-2026-10-31.md) traces an empty settings read before initialization or shutdown; it does not establish the cause of every occurrence or an ARM64 diagnosis.

The focused fake-Frame official-plugin install/remove e2e passes, including the TabMaster shim receipt, installed backend digest, API1/frontend preservation and partial-status readback. It ran in a unique disposable Compose project because the standard shell runner requires unavailable `zsh`. Owned containers, volumes and image tags were cleaned; container/volume absence was independently checked. The audit JSON records the test, log hash and 126.743-second total runtime. This is installer evidence, not real Frame or browser/backend usability.

TabMaster remains **partial**. Fresh exact-head CI and ARM64 of this repair are pending. This replay does not connect a browser to the backend or verify Steam library-tab editing, library/MobX patches, real Steam CEF, a managed Frame installation, wearer-visible UI or physical controllers. No headset was contacted or user data accessed.


## Current main and fixture refresh, 2026-10-31

The refreshed #500 fixture base contains main
`51841728090a45f9f452b4cd4ccf93f4caf8df14`. It was merged normally into this
restore branch at frozen tested source
`8afd5b1711b969fb6c7c46f29eba7cd4bc40085a`. The later #500 evidence-only head
`0dc8da2114e145da8598d0b1763ba17154924715` is included without changing those
runtime inputs. All 31 main probe bodies and the complete prior TabMaster
restore probe survive. Keyboard, IPC and Syncthing ownership inputs match main;
all 116 catalog policies and the other 115 complete rows remain unchanged.

The [refresh audit](framey-tabmaster-restore-main5184172-refresh-2026-10-31.json)
records 107 passing focused host tests. Local published Decky 3.3.0 AMD64 checks
47 repaired and 48 unchanged-original literal RPCs, private backup bytes,
malformed/non-object refusals, restart persistence and four parent-only zero-exit
stops with exact process identities gone. Twelve fingerprints, exact archive and
managed backend hashes and complete consoles were independently checked. Each
case retains one JSON diagnostic, unlocalized in that replay; error-free output is
not claimed. The original valid-backup restore failure remains a negative.

The exact main ownership helper was matched to its build/source fingerprints
and replayed through the isolated native candidate: three normal reloads and
Decky's deliberately forced plugin kill followed by successful helper reload
pass, with an unrelated process preserved. This checks the merged lifetime
repair for the old #501 failure path. It does not prove why the original unload
stalled, nor qualify clean parent-only final candidate shutdown: this candidate
runner's final cleanup uses group signaling. Syncthing remains uninstalled.

Pinned official-plugin HTTP/fake-Frame SSH install/remove passes at the same
source. Its uniquely owned containers, volumes, network and image tags, and the
native runtime resources, were removed. Later changes add evidence only. The
full new native matrix is 41 probes / 34 archive pins / 12 source fingerprints;
local targeted runs do not replace fresh exact-head hosted gates on both PRs.
No real Frame, Steam editing, browser/backend integration or VR proof was added.

## Qualified-main and refreshed stack base, 2026-10-31

The refreshed #500 base `112fc4b62fdc409ca5b9db8042776e703231c124`, including
qualified main `012f874906bd122c29e75a0c9d572980b41a1085`, was merged normally
at tested source `39810272c7454ec024f9394cb023d2564c19dcd3`. The stack remains
#501 on #500. All 31 main probe bodies, the complete repaired/original TabMaster
probe, the restore repair, every catalog policy and the other 115 complete
records are unchanged. Main's unrelated input/IPC sources are preserved, as is
#500's separate diagnostic evidence.

All 94 focused host tests pass. A new digest-pinned published Decky 3.3.0 AMD64
replay independently verifies 47 repaired and 48 unchanged-original RPCs,
original/managed backend and archive bytes, 14 source fingerprints, exact
backup/restored bytes, malformed/non-object refusals and restart persistence.
Four parent-only loader stops return zero with source-bound PID/start-time
reaping checks. No new owned containers or image tags remain.

The [refresh audit](framey-tabmaster-restore-main012f874-refresh-2026-10-31.json)
and [raw reports and unit log](framey-tabmaster-restore-main012f874-refresh-2026-10-31-raw.json.gz)
retain complete available consoles, each with one JSON diagnostic. These runs
do not localize its phase or establish an error-free console. The instrumented
startup diagnosis in #500 remains a separate observation.

The full new native matrix is 42 probes, 34 archive pins and 14 source
fingerprints per architecture. This targeted local AMD64 run does not qualify
that matrix, refresh the earlier fake-Frame installer or ownership replay, or
replace exact final-head and #500-base checks/e2e/native/package gates. No new
backup-path confinement, general schema validation, browser/backend integration,
Steam editing, managed Frame, wearer/controller or release proof is claimed.

## Refresh onto main d3ae60e and base500 8fea583a

Normally merged #500 `8fea583a514be5ba8a0ce6b435b6359068c63af4`, including
main `d3ae60ebed19829e3a3ae43ed1ea3766e0cee45f`, at tested source
`ddabdc4982e4a45af67b3e26fef3c4b8b6f6614c`. The two catalog/generated-doc
conflicts were resolved by retaining the restore scope and dropping only the
unsupported shutdown-phase attribution for the JSON diagnostic. The stack is
still #501 on #500. Main and base500 hosted gates were pending during this
local run; this integration does not qualify either base or authorize a merge.

The restore repair diff and complete repaired/original probe remain unchanged.
All 31 main probe bodies, all 116 status/install policies, the other 115 complete
catalog records and unrelated production input/IPC sources are preserved.
All 94 focused host tests, generated compatibility documentation and diff checks
pass. The complete focused test output is retained with the new native report.

A fresh isolated AMD64 replay with digest-pinned published Decky 3.3.0 verifies
47 repaired and 48 unchanged-original settings RPCs, original/managed backend
bytes, the exact archive and all 15 native-source fingerprints. Private valid
backup restoration, malformed/non-object refusal and restored-state restart
persistence pass; the unchanged original still refuses a valid backup. Four
parent-only loader stops return zero. No newly owned fixture container or image
tag remains. PID/start-time reaping remains a source-bound assertion without a
complete retained process snapshot.

The integrated console capture retains the complete available post-cleanup
text and hashes for both cases, each with one JSON diagnostic. Generic cleanup
observes already-exited loaders without claiming another signal. Global clean
shutdown, an error-free console and the diagnostic's phase/cause remain
unverified. The [refresh audit](framey-tabmaster-restore-maind3ae60e-refresh-2026-10-31.json)
and [raw reports and unit log](framey-tabmaster-restore-maind3ae60e-refresh-2026-10-31-raw.json.gz)
record these observations and limits.

The final head needs fresh checks/e2e, native AMD64/ARM64, ownership and every
triggered package mode, plus exact-main and #500-base qualification. Prior-head
hosted evidence is historical. Compatibility stays partial; no new browser,
Steam, managed Frame, wearer/controller or release proof is claimed.


## Current-main integration and complete package audit, 31 October 2026

After every workflow on head `9cf28143f0b18216129579a737b503ed3a03f511` completed, current main `0082d79a3ff9a9338e49dd5c83bbe25aa9e784b4` was merged normally at `4f8bf676053b353399e58ebb03c33ec553f02a76`. The entire merge tree is identical to the old head: `968161584d0999dbea786f2a6eaf20cab06c11d5`. No production, test, catalog or workflow bytes change in this merge. Local tests are therefore not repeated. The following evidence commit adds only documentation; exact final-head hosted qualification is still required.

The [integration/package audit](framey-tabmaster-restore-main0082d79-refresh-2026-10-31.json) and [raw audit records and source inventories](framey-tabmaster-restore-main0082d79-refresh-2026-10-31-raw.json.gz) verify all 15 native, 14 ownership and all four complete package source inventories against the merged source. Historical native AMD64/ARM64, checks/e2e and ownership evidence remains bound to its original exact head; identical bytes do not turn those old run SHAs into new-head passes.

All four modes of package workflow `41188198598` are independently audited: AMD64, ARM64, standalone browser HTTP and production-parent HTTP. GitHub artifact ZIP digests, exact completed jobs/checkouts, every successful job step, signed app/runtime pins and full content, native package launch, actual private two-way sync, owned-service lifecycle, strict source-bound owner shutdown, migrations, preservation/refusals and cleanup pass. Plain native modes decode the retained console result; HTTP modes independently verify complete checksummed virtio guest packets. Package fixture raw Decky console is not separately retained, so an independent full-console/global clean plugin claim is unavailable.

All twelve retained capture payloads match their hashes and contain five unique images, each visually inspected. Standalone Running shows the private sync folder and both `framey-owned-vm`/`owned-peer` rows; Stopped is visible after shutdown. Production-parent Running shows the folder but clips device rows at the iframe bottom. Its published broken/non-ARM64 warning remains, and Stopped is visible. These are isolated Chromium/CEF/receipt/systemd fixtures, not real Steam or Frame usability evidence. Syncthing remains blocked/unselected.

No existing review, issue comment or review thread remains to address in the snapshot; main has no active ruleset or classic protection checks. User-required merge/release gates still apply. Main native and checks/e2e are independently audited; its package gate remains pending. The refreshed final head must pass checks/e2e, native AMD64/ARM64, ownership and every triggered package mode before final integration/merge review. No headset/hourly schedule was accessed, and no release is qualified.
