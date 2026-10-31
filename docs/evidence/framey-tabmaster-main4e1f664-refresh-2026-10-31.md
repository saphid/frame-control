# TabMaster unload repair after the Simple Timer merge

PR #525 normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into prior head
`8c084284e56aeb1dccc04dedc6fa24d68ec0317e` at tested source `15a21b92c10e4923b67de67fa9ec930f03877afc`.
The exact store 61 TabMaster 2.15.1 archive remains pinned to
`e08333859a32b0c177b8e9a7959c5eeeafe38f946578f7f1d161c721f0e05da5`. Compatibility stays **partial**;
existing copies need Update/reinstall.

## Fresh local evidence

Published Decky 3.3.0 on native AMD64 executes repaired/original/previous-managed
TabMaster cases with **47/48/47 RPCs**. The repaired backend preserves private
user isolation, shared-tab filtering, false settings, backup/restore, malformed
and non-object refusals, and restart state. Its controlled peer EOF and restarted
stops take **0.214/0.214 seconds**, with the original unload hook completed,
no forced kill, owned identities reaped, zero adopted exits, and unrelated
sibling preserved. The original published backend retains its valid-restore
refusal. The previous managed backend restores correctly but reproduces a
**5.223-second forced unload**;
its restarted instance stops normally. Neither negative is a compatibility pass.

Simple Timer's newly merged probe runs **31/10/18 RPCs**, preserving event
sequences, settings snapshots and restart state. Its four repaired stops take
**0.246/0.214/0.214/0.214 seconds** with original unload
hooks, no forced kill, and no recorded identities left behind. Original timer
state failures and the previous managed forced stop remain expected negatives.
All **20 native source fingerprints** match both runs and the tested source.

Full server suite: **1,949 tests**, **16 platform/optional skips**,
no failures, in **252.601 seconds**. Website: **18 tests**, no skips. One isolated
HTTP/SSH installer method verifies all **37 pinned fixtures**, including exact
TabMaster receipt, backend/helper bytes and removal. Owned containers, volumes,
network and image tags were removed and absence independently checked. This is
an installer transaction test, not execution of all official backends or the
full e2e suite.

The source/AST audit preserves main's other 36 runtime bodies, other 33 native
cases, other 115 complete catalog rows, all 116 status/install policies,
non-TabMaster installer/e2e branches, shared IPC, and the current Timer helpers.
The prior TabMaster probe and strengthened delivered-helper hash assertion
survive unchanged. Independent installation reconstructs exactly the preceding
JSON-repaired backend beneath the child EOF prefix; every other archive member
is unchanged.

## Limits and remaining gates

The strict-red and main-equivalent forced-stop controls in preceding evidence
remain historical; they were not rerun in this refresh. The current previous-
managed negative is fresh. Free Loader and Deck Settings native controls from
the preceding refresh are historical; their current sources are byte-preserved.
Unattributed JSON diagnostics remain in TabMaster consoles. Generic console
cleanup is not a globally clean-plugin or error-free runtime claim.

Exact final pushed-head hosted CI, full e2e, native AMD64/ARM64, applicable PC,
owned-watchdog and every triggered package mode, exact current-main checks,
feedback and mergeability remain merge gates. The full native matrix and full
e2e were not run locally. Release requires all exact release-commit gates and
a locked real Frame smoke. No library-tab editing, browser/backend integration,
actual Steam CEF, real Frame, wearer/controller, tagged installer or release
proof is claimed. Headset, schedules and pre-existing user data were untouched.

[Structured audit](framey-tabmaster-main4e1f664-refresh-2026-10-31.json) and [raw reports, logs and verifiers](framey-tabmaster-main4e1f664-refresh-2026-10-31-raw.json.gz).
