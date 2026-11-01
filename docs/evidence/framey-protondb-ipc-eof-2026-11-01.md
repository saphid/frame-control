# ProtonDB Badges child IPC EOF — 2026-11-01

Implementation `d4852de1ccd1f81a6eddaa9a236a2a27381d3a06`; base main `a963dc2920231448353e7cc0fb03ae9c519c0aaf`.
Only store **14 / 1.3.4**, exact ZIP SHA-256
`90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358`.
Published backend SHA-256 `07ae28331b7d1ab55a6303636026dadd7e5523fde84d95c62899fed6e1c133ba`.

A review of #542's exact AMD64 native artifact 13100869862 found a hidden
ProtonDB forced kill despite a green producer. A deterministic private fixture
closes a real plugin IPC peer before signaling only the parent loader. On the
unmodified archive, the new assertion fails after **5.224 seconds**:
Decky forces the child down while its parent returns zero. The red fixture is
committed as `381a548fff8c2bd1f536872016f9fb90ea6268e5`; its console and fingerprints are retained.

The exact managed archive receives the existing child-only EOF adapter and a
three-line prefix before every original backend byte. All other published
members, including frontend, settings implementation, API2 manifest and flags,
remain byte-identical. The installed-archive test checks every member and the
helper; other archive digests/store IDs do not receive this adaptation. Existing
copies need Update/reinstall. It does not change Decky's parent or other plugins.

Published Decky **3.3.0 native AMD64**, network/device/session isolated, passes
**nine actual RPCs**, including empty-config defaults, private settings writes,
false values, loader-restart persistence and container OS metadata. Both strict
parent-only stops complete in **0.214 / 0.224 seconds**,
with the original unload hook observed, zero forced kills/shutdown errors,
zero remaining exact descendants and zero-status adopted exits. The first
stop follows a real child peer EOF; the second follows restart/readback.
Settings bytes survive. The generic console recorder still says
`cleanShutdownVerified=false`; these are explicit scoped stop assertions,
not a complete filesystem cleanup claim.

Independent auditing matches all **33 native source fingerprints** to this
implementation and confirms the entire installer/APPLY AST outside this exact
repair, all 37 native cases, all 116 pins/policies/ratings and the other 115
catalog rows remain unchanged. Compatibility stays **partial**. The original
read-only Frame evidence predates this repair and is not proof of this backend.

Validation: **2007 unit tests**, 15 platform/optional skips, 260.061 seconds;
**83 focused tests / zero skips** (74 store, 2 installed archive, 4 IPC and
3 runtime inventory). Full disposable fake-Frame: **53 tests / zero skips**,
**409.672 seconds**, all 116 exact archives, 69 install/remove and
47 expected refusals. Owned Compose resources were removed, prior image tags
restored, and shared simulator identity/start/restart count/health retained.
The log retains 2 HTTP fixture socket ResourceWarnings; #544 repairs those
separately. No real Frame was contacted by these tests.

Fresh publication-head hosted CI/e2e/native AMD64 and ARM64 and package gates
remain required. Repaired Frame runtime, badge rendering, Steam game-page
patches, browser/backend integration and worn/controller use are unverified.
No headset, schedule, security setting or PR #113 was changed; no release is
qualified. Other hidden forced-kill cases found in #542 remain separate work.

The JSON summary and compressed raw packet retain reports, red/green consoles,
fingerprints, full unit/focused logs, simulator cleanup and the independent
source audit program.
