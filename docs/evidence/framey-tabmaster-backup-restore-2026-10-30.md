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
