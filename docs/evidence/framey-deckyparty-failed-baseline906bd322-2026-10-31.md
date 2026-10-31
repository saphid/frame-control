# DeckyParty failed reload baseline retained

## Announcement

Retain the actual native AMD64 failure at documentation head `906bd32288cbdec7dbe1b7d6c158a4c7bf0b9bab`. [Job 124642498607](https://github.com/saphid/frame-control/actions/runs/41236913339/job/124642498607) forced a plugin kill after five seconds, missed the original unload hook and timed out. Its later clean replacement stop does not qualify the failed reload. This was not waived as infrastructure and was not blindly rerun.

Original artifact ZIP SHA-256 `2cd56fbd18c83ba35ade48767b1e8c4603bb7a7731d2dcc29a0a774cb5a88770` and its extracted native report verify. All 20 recorded inputs equal pre-repair main 7062ef4. The scoped repair in PR #518 subsequently passed exact-head native AMD64/ARM64, full catalog e2e, ownership and all four package modes, then merged normally at de5eb65. This documentation branch now normally integrates that source repair; its new exact-head CI is still mandatory. Older failed evidence remains a failure.

[Summary](framey-deckyparty-failed-baseline906bd322-2026-10-31.json), [raw failed report/run/job/log and repair merge](framey-deckyparty-failed-baseline906bd322-2026-10-31-raw.json.gz), SHA-256 `5f8133d31f4739f5f257352ae0d6a45568bcc444ed94b8b0fb50a7fb9f6e63e5`. No real Frame, global clean runtime, plugin UI, wearer/controller or release claim. No headset, schedules or pre-existing data touched.
