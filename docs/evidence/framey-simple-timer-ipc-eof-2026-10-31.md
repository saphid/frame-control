# Simple Timer child IPC EOF repair, 31 October 2026

Then-current main `0082d79a3ff9a9338e49dd5c83bbe25aa9e784b4` passed timer RPC/event probes but its raw native consoles showed a forced Simple Timer unload on both architectures. The current-main positive observation is separate from the expected original-source timer regression. A new private native AMD64 regression against unchanged production reproduced one forced kill after 5.224 seconds when a private Unix peer closed with an active deadline.

The managed install for only Simple Timer 1.0.0 archive SHA-256 `973d927e9d9a1feec04679c564af7e389a729b6735d2a988ffc2cb46ce4eb312` now adds the existing child-local EOF adapter. It ends the closed connection loop so the existing `_unload` hook can cancel/join its timer task. The parent loader, shared adapter, timer calculations, completion notifications, settings and API1 dispatch convention are unchanged. The repaired backend is exactly a three-line import/install prefix followed by the complete previous managed backend. Published non-backend files, manifest and license are byte-identical. Existing copies need update/reinstall; the receipt requires both lifecycle and IPC shims.

## Local native evidence

Use the [independent audit](framey-simple-timer-ipc-eof-2026-10-31.json) and [retained native packets, console text, RPC/events, settings and unit output](framey-simple-timer-ipc-eof-2026-10-31-raw.json.gz). The repaired case retains 31 RPCs and 30 events, the original-source negative 10 RPCs, and the previous managed-source negative 18 RPCs. All 93 focused tests pass. These bind the exact loader and all 17 source fingerprints to the tested source revision, and retain the unchanged-production failure separately.

The private fixture uses published Decky 3.3.0 AMD64 in a disposable network/device/session-isolated container. It exercises API1 WebSocket dispatch, silent mode, fresh/idempotent cancel, replacement without a stale completion, normal and late completion, active deadline/recents persistence, canceled restart and expired restart. The repaired run passes four clean parent-only stops with no forced plugin kill, preserves complete settings bytes across each stop, records PID/start-time descendants and adopted exits, and keeps an unrelated sibling alive. The first stop explicitly closes one private owned Unix peer to stabilize the EOF regression. Neither plugin nor process group is signaled to manufacture a clean stop.

The prior managed source negative control removes only the IPC prefix/helper and checks its literal original source hash. It must still require a forced kill. A separate original published-source negative control retains the existing annotation-only state, uncanceled deadline and stale replacement-event failures. These are expected negatives, never compatibility passes.

The first repaired attempt passed its active stop, then exposed a fixture assertion copied from legacy plugins: Simple Timer publishes frontend load type **1**, not 0. The corrected test checks its exact published discovery record. That failed fixture console is retained rather than presented as a runtime success.

## HTTP/SSH receipt follow-up

Source `a10634f58ecd57bfb547c3050b170e134d34c768` corrects stale transport
expectations: both timer lifecycle/IPC shims must appear in the receipt, and the
compatibility status is partial. The test checks the installed managed backend
and IPC helper SHA-256 values. It preserves the tighter compatibility claim.

One real HTTP installer/fake Frame SSH method covering all 37 pinned plugin
fixtures passes with zero skips. All owned containers, volumes, network and
image tags are removed. Production/native-probe sources are unchanged, and all
17 retained native source fingerprints match. This establishes installation
bytes, receipt and removal; the fake Frame does not execute official backends.
Neither the full e2e suite nor real-headset behavior was tested here. Fresh
final-head hosted gates remain required.

[Receipt audit](framey-simple-timer-receipt-e2e-2026-10-31.json) and
[complete local log, test source and cleanup records](framey-simple-timer-receipt-e2e-2026-10-31-raw.json.gz)
retain the result.

## Scope and limits

The table changes Simple Timer from works to partial because the earlier usability evidence did not qualify this discovered shutdown defect. Previous Chromium plus actual ARM64 Decky evidence stays historical. No refreshed browser, managed Frame install, wearer-visible UI, physical controller, sound or suspend proof is claimed. Sound/suspend remain unsupported; alerts still require an open panel.

Raw native console text retains JSON parsing diagnostics from Decky's parent response listener. Scoped zero-exit owner/plugin stops do not establish an error-free global shutdown. The original-source negative also retains its expected task-state exceptions.

Fresh final-head hosted checks/e2e, both native architectures and every triggered package mode remain required before merge. Main's own checks/package gates must qualify first. No headset or hourly schedule was accessed, and no release is qualified by this evidence.

For the subsequent normal merge of main `1ac2941` into this repair and fresh
combined-source checks, see the [current-main integration evidence](framey-simple-timer-main1ac2941-integration-2026-10-31.md).
The original checks above remain bound to their historical source revisions.
