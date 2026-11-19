# AlarMe with ScreenSaver main; hidden ARM64 shutdown failure — 2026-11-01

Implementation `a2e1b3ea3ea94624b4c1d3060498cc1edec5fc01` normally merges exact main `ad070b731386dfbc2c8ed24b901b0b5edaeacbf2` into prior AlarMe head `b44f8642a243b2f6dd10f347da0e862f7b24a236`. Two inventory conflicts preserve all 36 main native cases, all 116 archive pins/policies/classifications and the other 115 complete rows. Whole installer/APPLY, checker, runner and e2e ASTs outside AlarMe match main. Another 1,742 main Git objects match. The original AlarMe helper and archive bytes are unchanged; generated docs pass.

## Local combined-source verification

**132 focused tests / zero skips** pass. Published Decky 3.3.0 native AMD64 executes **39 repaired / 38 original API1 RPCs**. The exact backends are independently reconstructed, every response is matched to the 77 retained calls, and silent completion events are checked. Repaired paused/elapsed deadlines survive restart and explicit resume; original source still ticks and deletes an expired paused timer. Preset/stopwatch persistence passes. Four source-bound parent-only loader exits return zero. Complete available consoles have two unattributed JSON diagnostics each; generic clean-shutdown flags stay false. No new native container/image tags remain. Complete independent preservation/process snapshots are not claimed.

Same-source ScreenSaver verifies **31 RPCs / 14 independent D-Bus calls**, busy-name ownership, disconnect release, settings persistence and two strict parent-only clean stops. Both reports bind all **32 runtime source hashes**.

Full fake-Frame simulator passes **53 tests / zero skips** in **416.347 seconds**, **116 pins**, **69 install/removes / 47 expected refusals**. Official backend execution is stubbed. Owned Compose resources are gone; prior image tags are restored and the shared simulator is unchanged and healthy. The log retains 2 listener warnings; #544 separately repairs those fixtures.

## Blocking prior-head ARM64 evidence

All 18 hosted checks reported success on `b44f8642a243b2f6dd10f347da0e862f7b24a236`, but artifact **13076642154** contradicts a clean-shutdown claim: the repaired AlarMe case logs **`still alive 5 seconds after stop request! Sending SIGKILL!`**. The parent returned zero after **5.176s**, so the producer's parent-exit check did not reject its child kill. The strict independent console audit rejects this ARM64 result. Its exact checkout, ZIP digest and 30 source fingerprints are verified and the complete targeted records are retained. The prior AMD64 case passes the stricter audit. Not all other native producer cases are independently behavior-audited.

All four prior-head signed-package modes pass their separate audits (159 distinct sources / 1393 hash bindings). They do not erase the native failure or qualify this new implementation.

**Hold merge and release** until AlarMe child shutdown is repaired, a strict native gate rejects the fallback, and fresh exact-head AMD64/ARM64/CI/e2e and triggered ownership/package gates pass. A separate AlarMe IPC/shutdown fix is required. Exact current-main green, feedback and mergeability are also mandatory. Actual sound, sleep inhibition, production browser/Steam CEF, real Frame and wearer/controller usability remain unverified. No headset, schedule, security setting or pre-existing user data was touched.

[Summary](framey-alarme-mainad070-integration-2026-11-01.json) · [Raw observations, failed ARM64 case, logs and verifiers](framey-alarme-mainad070-integration-2026-11-01-raw.json.gz).
