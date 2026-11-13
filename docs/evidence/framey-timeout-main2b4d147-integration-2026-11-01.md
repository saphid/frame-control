# Package timeout diagnostics integrated with Steamback main

Normally merge current main `2b4d1474ec71573ab91845b46e21f773284bebad` into PR #535 head `95f72f7618012f685b3bed2d3af242c7ef9837b4`,
producing tested source `0415fb98f6ce67c587af19942b4c452e254b4115` without conflicts. The integration preserves
every main file except the intended timeout helper and its regression test,
plus the six existing evidence files. Both timeout files are byte-identical to
the previous publication. All 25 native inputs and all 116 catalog rows match
main byte for byte, including Steamback's helper, runner and installer controls.

Local Linux verification at this integration source:

- Full server suite: **1970 tests**, 15 platform/optional skips,
  253.630 seconds. All three real-child timeout, success and
  nonzero tests execute and pass. Timeout output remains bounded to 10,000
  characters per stream, includes the Unicode sentinel, reaps the child, and
  raises the timeout. Nonzero exit 23 remains a failure. Resource warnings remain
  in the retained logs.
- Website: **18 tests, zero skips**.

Separately, exact main `2b4d1474ec71573ab91845b46e21f773284bebad` has hosted Decky 3.3.0 AMD64/ARM64 evidence:
51 producer cases, 25 source inputs and 667 RPCs per architecture, with eight
independent behavior/installation audits. Its Fake Frame suite passed 53 tests
with zero skips and all 116 pins/outcomes verified. Both ownership architectures
and two signed-package modes were qualified at collection. The complete main
packet is retained here. These are main executions with byte-identical native
and e2e inputs, **not new executions of this integration**. No simulator, native
runtime or package rerun at this integration is claimed.

At prior publication `95f72f7618012f685b3bed2d3af242c7ef9837b4`, three AMD64 signed-package modes were
independently qualified; ARM64 remained live/unqualified at the observation.
Those results remain historical and do not qualify this integration. The
published branch was not updated and no live job was cancelled. Before a normal
push, require the prior jobs terminal, unchanged remote/current-main guards and
no current-main failure. Every triggered fresh exact-publication CI/e2e/native
AMD64+ARM64 and package gate remains required, followed by exact green main,
required checks, feedback/review and mergeability gates. The ownership workflow
may not trigger for this guest-only source change; no absent execution is claimed.

This closes a diagnostic gap; it does **not** fix or establish the cause of #529's
ARM64 migration/shutdown hang. Timeout budgets, strict nonzero/report checks,
cleanup and blocked installer policy remain unchanged. Store 130 stays 1.0.1;
separate GitHub 1.0.2 lookup remains unverified. Actual Steam CEF, official UI,
managed Frame, worn visual/controller behavior and release smoke remain
unverified. No real Frame, schedule, PR #113, pre-existing data or security
settings were changed. No release.

Raw SHA-256: `186bc6eb106df90c682fbfcf378f78128a920925e2f8bf269c43f079ef2ceac2`. Logs, reports, source bindings and programs are retained.
