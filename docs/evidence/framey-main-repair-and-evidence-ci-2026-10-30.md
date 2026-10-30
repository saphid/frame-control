# Completed package and main-repair evidence

The four signed-package jobs below independently passed at pre-refresh PR #494 head `7c73d883e7f2553db4abe0430a9288b456f09422`, run `41115486303`. All verify source fingerprints, actual signed packages, two-way sync, lifecycle and migration, ownership refusals, preserved data, and checked clean owned Decky shutdowns. Plain complete guest reports match console results. Both distinct browser HTTP images and all four distinct production-parent/bridge images were inspected; all retained payloads match PNG hashes.

| Variant | Job | ZIP SHA-256 | Service/migration stop seconds | Audit |
| --- | --- | --- | --- | --- |
| amd | `124268495613` | `df250888fc0830e7cce1d897e8ba6843a59016ef506269761fd8f08468327f4c` | 7.016/2.098 | [amd](framey-native-evidence-signed-package-ci-amd-2026-10-30.json) |
| arm | `124268495177` | `c6cf95fa924a8847608f98072c983356e25bedc65ef40a2b0465e5207a3aced8` | 8.846/9.465 | [arm](framey-native-evidence-signed-package-ci-arm-2026-10-30.json) |
| http | `124268495800` | `0a5a8472a75258b91406e7d7dcedf59e47942215ed4b349459cc12e200b39602` | 7.167/2.07 | [http](framey-native-evidence-signed-package-ci-http-2026-10-30.json) |
| parent | `124268495708` | `89303829ee849a633af61378968cfa4bd209253c3515de1646acc2ca2689ff1e` | 1.26/1.308 | [parent](framey-native-evidence-signed-package-ci-parent-2026-10-30.json) |

These are prior-head results. The branch subsequently absorbed main `bc3e592` by a normal merge. Fresh exact-head applicable checks, native, e2e and package results remain required before merge.

Also retain independent exact-main `bc3e592` native AMD64/ARM64 (33 probes/30 published archives each), actual e2e (233 seconds, 306 with builds), and ownership AMD64/ARM64 audits (14 source fingerprints each, actual two-way sync, 17 lifecycle assertions and 18 ownership refusals). Exact workflow event, actual logged checkout, GitHub artifact digest and successful completed job/steps were checked. These five audits cover completed jobs; main's four signed-package jobs were still pending when this record was written. They do not establish that full main or any release gate passed.

- [framey-main-bc3e592-native-amd-ci-2026-10-30.json](framey-main-bc3e592-native-amd-ci-2026-10-30.json)
- [framey-main-bc3e592-native-arm-ci-2026-10-30.json](framey-main-bc3e592-native-arm-ci-2026-10-30.json)
- [framey-main-bc3e592-ownership-amd-ci-2026-10-30.json](framey-main-bc3e592-ownership-amd-ci-2026-10-30.json)
- [framey-main-bc3e592-ownership-arm-ci-2026-10-30.json](framey-main-bc3e592-ownership-arm-ci-2026-10-30.json)
- [framey-main-bc3e592-e2e-ci-2026-10-30.json](framey-main-bc3e592-e2e-ci-2026-10-30.json)

All browser CEF, receipts and inputs are private synthetic fixtures. Actual Steam CEF, managed installation, the real Frame and physical/worn controller usability remain unverified. No real Frame was contacted, no publication authorized, no compatibility status promoted, and no installer policy changed.

A [later current-source audit](framey-host-and-main-current-ci-2026-10-30.md) records all nine completed host-gate jobs at PR #493 head `f114892` and completed native/e2e jobs at main `d89291e`. It preserves the pending main package and physical-testing gates and does not replace the historical identities above.
