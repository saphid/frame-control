# Simple Timer shutdown repair integrated with main 1ac2941

The Simple Timer IPC EOF repair in PR #521 now includes current main
`1ac29413186fb29d5844ee9ad1c5c6fd36eeac27` through a normal merge commit,
`552a3677f1a1d8dc82b29841261ac0574abcd7fd`. The merge has parents
`1890c7e26c17157fb9ce0817896ef912d6ab5606` and that exact main commit. No
history was rewritten. The previously green PR head's hosted checks and four
package audits are historical; they do not qualify this combined commit.

Main added TabMaster's scoped JSON-file restore repair, its valid-backup and
malformed/non-object controls, a separate original-source negative, HTTP/SSH
receipt/backend checks, and its partial compatibility row. The integration
preserves them and the timer's EOF repair. The original timer helper files and
shared EOF adapter are byte-identical to the previous PR head. Only Simple
Timer's catalog row differs from current main; the other 115 complete rows and
all 116 install policies are unchanged.

## Current-main motivation

Current main's independently audited published Decky ARM64 native artifact
recorded a forced Simple Timer kill despite successful CI job status. The
[earlier matrix audit](https://github.com/saphid/frame-control/blob/5817bc9573845627bbfbdba2af033b2deecabcab/docs/evidence/framey-tabmaster-full-native-main-controls-2026-10-31.md)
retains that observation and its exact job/artifact provenance. Green CI and
loader exit zero did not establish graceful plugin shutdown. This integration
is needed before the timer repair can be considered for merge against current
main; a new exact-head ARM64 result is still required.

## Combined-source validation

The full published Decky **3.3.0 AMD64** matrix completed all **43 probe
assertion sets**, with 34 independently verified archive pins, 17 source
fingerprints and all 43 available console hashes checked. This is not a global
clean-shutdown pass: **Battery Tracker 0.2.0 completed 36 RPCs but required one
forced kill**. The existing [separate repair PR #519](https://github.com/saphid/frame-control/pull/519)
owns that defect and is not included here. No additional PR was opened.

The repaired timer made **31 RPCs and 30 events**, with four parent-only clean
stops in **0.185–0.225 seconds**, zero forced kills, preserved complete settings
bytes, no surviving owned identities, zero exit codes for adopted children, and an
unrelated sibling still alive. The original-source negative made 10 RPCs and
14 events and retained the task-state/deadline failures. The previous managed
source made 18 RPCs and 24 events and reproduced one forced kill at 5.267
seconds. Those negatives do not qualify compatibility.

Main's TabMaster cases retain 47 repaired-source and 48 original-source RPCs,
including a successful private backup restore only on the repaired source,
four malformed/non-object backup refusals, preserved backup bytes and restored
state after restart. Its separate EOF repair remains in PR #525.

The full server suite passed **1,943 tests in 255.051 seconds**, with 16
platform/optional skips. Website tests passed all **18** cases. One fresh
owned HTTP/SSH installer method passed all **37 pinned store fixtures** with
zero skips. All owned containers, volumes, network and image tags were
removed and their absence checked. Generated compatibility docs and diff
checks passed.

The [independent audit](framey-simple-timer-main1ac2941-integration-2026-10-31.json)
and [compressed raw records](framey-simple-timer-main1ac2941-integration-2026-10-31-raw.json.gz)
retain the native inventory, all available consoles/hashes, literal timer
RPC/event expectations, PID/start-time descendants, settings readbacks, verifier
source, unit/website output and owned installer cleanup. All 17 source
fingerprints are bound to the merge commit above. Subsequent evidence-only
commits must preserve those inputs.

The production installer is independently reconstructed at main and at the
integration commit. The timer backend is exactly the EOF prefix plus the prior
managed lifecycle repair; the helper matches the unchanged shared adapter.
Both receipt shims are required. All eight other published members are
byte-identical to the archive. The other 36 native dispatch bodies and 33 case
records remain identical to current main.

## Limits

This turn's native run is local **AMD64**, not a new ARM64 or real-headset
qualification. Other probes do not uniformly require graceful plugin unload;
completing the full matrix does not establish a globally clean or error-free
console. The audit retains all forced-kill and selected diagnostic markers,
including expected negatives. No failure is promoted to a compatibility pass.

The HTTP/SSH method covers 37 pinned store install/receipt/removal transactions,
including both the integrated TabMaster and repaired timer assertions. It does
not execute official backends or the full e2e suite. Earlier browser evidence
remains historical. Sound and suspend are unsupported; alerts still need an
open panel. No managed Frame, wearer-visible, controller or release proof is
claimed. Headset and hourly schedules were untouched.

Fresh exact final-head checks, e2e, native AMD64/ARM64, PC/ownership checks, all
triggered package modes, reviews/feedback, current main and mergeability remain
gates. A release also needs every exact release-commit gate and locked real
Frame smoke. No merge or release is qualified by this local evidence alone.
