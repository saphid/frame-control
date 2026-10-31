# Syncthing runtime failure evidence — 2026-10-31

The raw-peer runtime probe previously printed only the last 5,000 characters of
each log on failure. Its successful result omitted the loader console, and the
ownership workflow did not upload a separate runtime console. The retained
shutdown failure on PR #503 therefore cannot establish the helper's process
state at failure or the precise shutdown cause.

The host runner now saves captured stdout and stderr in
`syncthing-runtime.console.log` on success, failure, or timeout. The workflow
uploads it even when a probe fails. A successful result binds that file by
SHA-256 and retains the loader console and its separate hash. On an exception
inside the native probe, diagnostics include the exact owned helper's PID,
state and parent PID, whether its socket directory remains, and the full logs
available at that point. No environment variables or command lines are dumped.

The original three tests execute actual subprocesses: exit 23 retains more than 12,000 output
bytes without becoming success; a timeout retains emitted stdout/stderr and
still raises; success replaces a stale console file.

The initial native AMD64 positive control uses published Decky 3.3.0, the unchanged main
candidate helper and pinned Syncthing v2.1.7 peers. Two-way sync, restart, private
RPC reads, wrong-key 403 and normal helper/process shutdown pass at the initial probe source, before the strict gate below. All five
runtime input fingerprints and the loader/helper/console hashes were checked.

A separate owned source copy deliberately pauses only the plugin before
requesting loader shutdown. The loader reports shutdown without its forced-kill
fallback; the probe then fails its unchanged helper-shutdown assertion. The
14,980-byte retained console includes the full available logs and a sleeping
helper with its plugin parent and socket directory still present. No successful
result JSON is written. This validates the diagnostic failure path; it does not
reproduce or explain the historical CI failure. The injected source is not part
of the product or CI probe.


## Green job with an unclean loader shutdown

At head `4f27b3d9dcf297acbdc20666af32b843cf01e972`, the
[AMD64 ownership job](https://github.com/saphid/frame-control/actions/runs/41170465301/job/124447124841)
passed, but its [artifact 13030957526](https://github.com/saphid/frame-control/actions/runs/41170465301/artifacts/13030957526)
retains a 2,067-byte loader console containing `Error during shutdown:` and
`asyncio.exceptions.CancelledError` in Decky's `kill_if_still_running` sleep.
The helper was reaped and no plugin SIGKILL was logged; those facts do not
prove clean loader shutdown. The artifact ZIP digest, successful exact-head
checkout, 14 source fingerprints, inner loader hash and outer console hash
were independently checked. This observation does not establish the root
cause or the cause of PR #503's earlier failure.

The runtime probe now requires a zero loader exit, a shutdown completion and
Syncthing's plugin-stopped record. Shutdown exceptions, pending-task errors,
bad descriptors and forced plugin kills fail the probe before success JSON is
emitted. The exception path retains the console and owned helper snapshot.
The normal `Cancelling tasks...` banner remains allowed. Seven host tests pass,
including a real subprocess that rejects the exact retained hosted log and
preserves it in the sidecar. The new gate is a test change, not a candidate
shutdown fix. All 101 related host tests also pass. A first native trial using the old group signal returned loader exit 1 even
though its unload log appeared normal; the strict gate rejected it and retained
the failure console. Normal stop now signals only the owning loader, matching
`KillMode=mixed`, so plugin/helper termination must be performed by the loader
rather than the test. A fresh native AMD64 run with that final fixture passes
the strict zero-exit, plugin-stopped and clean-console assertions, helper/socket
cleanup, peer transfer/restart and RPC checks. Its five source fingerprints and
inner/outer console hashes were independently verified. Final-head hosted
AMD64/ARM64 and all other triggered jobs remain required.

The timeout path retains only output emitted before timeout. The existing
forced peer-cleanup path still prints the tail of that peer's log and was not
exercised here. ARM64 and final-head hosted CI remain required. Syncthing stays
blocked and unselected; its helper, production code and all catalog entries
match base main `8ebe9acda1cb1174120f07fb42b39afcc1ed8c9c`. No real Frame,
Steam CEF, worn view, physical controller or release is verified by this work.

[Results, source fingerprints, negative injection and limits](framey-syncthing-runtime-failure-evidence-2026-10-31.json).

## Current-main refresh

Frozen source `6c149a70cd23312adfda6ed2351a21fbe31f182d` normally merges
verified main `dd12031f55ccbcba01aa07296080495df1935af1`. The previously green
head `a39ca82529258b66c915f006197314afe96ad71f` did not contain current main:
its combined tree would add 31 files, including helper/runtime changes. Its
hosted evidence remains historical, rather than qualification of this refresh.
The test change still leaves production and catalog bytes identical to main.

All 26 selected host tests pass after correcting two nonexistent module names
in the initial local command. The corrected test log and the initial selection
error are retained locally; no repository test failed in that initial command.
A full local AMD64 raw-peer replay uses the pinned Decky 3.3.0 loader, Syncthing
v2.1.7 archive and current main's helper. All five input source hashes, the
three helper build source hashes and every executable/archive digest were
independently checked before accepting the reused helper build.

The replay verifies the literal transfer bytes and their hashes in both
directions, persistence after a peer restart, all nine proxy HTTP statuses and
wrong-key 403. The loader exits zero, stops Syncthing in 0.1 seconds and emits
one shutdown completion; its full console contains none of the five forbidden
shutdown diagnostics. Both inner and outer console hashes were verified.
Owned helper and peers were reaped; the container and private image tag were
removed. This raw-peer test has no service bus and adds no systemd, browser,
managed-install, real Frame or release proof. Final-head hosted AMD64/ARM64,
e2e and every other triggered check remain required before merge.

The machine record retains this replay under `currentMainRefresh`, separate
from all earlier successes and observed failures. Syncthing remains blocked
and unselected.

## Refresh onto Shotty/Wine main

Main `1c1e4f588735dc3119f67f90ca8c33d3a90563cd` was merged normally at frozen source `e565b133c05cbc3f4f785adc0097333f28bee64c`. The runtime-evidence correction diff is unchanged. All production/catalog bytes and current main’s native runner/probe sources remain identical to main. The refresh brings in the 27 main files added since this branch’s previous base, including the Wine and Shotty unload repairs. Syncthing remains blocked and unselected.

All 26 selected host tests pass, including actual subprocess failure/timeout retention and rejection of the exact historical unclean green-job console. A fresh local native AMD64 replay independently verifies the five runtime source hashes, current main’s unchanged three helper-build inputs, pinned Decky 3.3.0/Syncthing v2.1.7 executables and archive, literal two-way transfer and restart bytes, nine proxy HTTP 200 responses, and wrong-key 403. The loader exits zero, emits its plugin-stopped and single shutdown-complete records without any forbidden diagnostics, and reaps the owned helper. Full inner/outer console hashes match. No new owned container or image tag remains. The run took about 41 seconds.

[Source-bound audit](framey-syncthing-main1c1e4f5-refresh-2026-10-31-audit.json), [raw report, complete available consoles, selected-test log and resource-delta result](framey-syncthing-main1c1e4f5-refresh-2026-10-31-raw.json.gz). The cached helper build was reused only after verifying its binary digest and all three current-main build inputs. This is a new local AMD64 replay, not a fresh Rust build or hosted/full-matrix qualification. Raw-peer service-bus/systemd, managed installation, browser integration, ARM64, real Frame and wearer/controller behavior remain unverified. Exact current-main CI and all fresh applicable head workflows, e2e, native/ownership/package gates and final review remain required before merge. No release qualification follows from this replay.


## Refresh onto main d3ae60e

Main `d3ae60ebed19829e3a3ae43ed1ea3766e0cee45f` was merged normally at
`faddd91bb067c0bfa95b45b1f04e248132732db4`, without conflicts or rewriting
history. The runtime evidence-correction diff is unchanged. All product and
catalog bytes and main's native probe/console sources remain identical to main.
The signed-package gates for that main are still incomplete.

All 38 focused runtime-evidence, candidate-ownership, native-console and Wine
unload-evidence tests pass, including rejection and retention of the historical
unclean shutdown console and real subprocess timeout/failure output. A fresh
isolated AMD64 replay with pinned published Decky 3.3.0 and Syncthing v2.1.7
passes two-way private transfer, restart/preservation, all nine literal proxy
HTTP 200 responses, wrong-key 403 and the strict source-bound parent-only,
zero-exit, complete-plugin-unload assertion. The raw loader exit code is not
separately recorded in the report. Complete inner/outer console bytes and hashes
are retained and independently checked; no global plugin-shutdown claim follows.

The cached helper is reused only after its binary digest and all three current
build-input hashes match. No new Rust build is claimed. All five report source
fingerprints and additional launcher/Containerfile hashes match the tested
source. No new owned runtime container or image tag remains.

[Current refresh audit](framey-syncthing-maind3ae60e-refresh-2026-10-31-audit.json)
and [raw report, full available consoles and unit log](framey-syncthing-maind3ae60e-refresh-2026-10-31-raw.json.gz)
retain this result. Fresh final-head hosted checks/e2e, native AMD64/ARM64,
ownership and all triggered package modes remain required. Previous-head
hosted successes remain historical. The raw-peer fixture has no service bus;
no new systemd, browser, managed-install, Frame or wearer/controller proof is
claimed. Syncthing stays blocked and unselected, and no release is published.
