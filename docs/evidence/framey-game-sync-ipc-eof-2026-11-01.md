# Game Sync child IPC EOF — 2026-11-01

Implementation `462752028acc9e5221a81902a1efd1ddefec76a7`; exact main `39ed2b0b139c2f486daeb3f3cb8a27067d9bc858`.
Only managed store **104 / 1.0.4**, ZIP SHA-256
`65e021ebb37d2ebfbfbe3dbc8af95aef9556cf484730362c6b26c4ecc3e62ccd`.
Published backend SHA-256
`96fa86a0f1f14531c701bc416a2ae244b521eb24abfa58ce3b76cb27bb8dcff0`.

While qualifying #536, exact current main passed all nine producer checks but
its ARM64 native artifact **13103701800** contained a managed Game Sync forced
kill after restart. #547's ARM64 artifact **13103371507** showed the same issue.
This is not a deliberately restored original-source negative. The #536 merge
guard stopped before mutation. A premature PR-body sentence calling main's
complete native audit passed was corrected before any merge. The source-bound
main failure and the local regression below are retained in the raw packet.

A deterministic regression `4e5cefbd56848e2b5c4e86650f24fe63dce06032` closes a real child
IPC peer before signaling only the loader parent. On the previous managed
source, it fails at **5.225s**, with one forced
plugin kill despite parent exit zero. Original unload callback completion is
not observed in that stop console. No retry or producer success waives it.
The strict shutdown observer module is byte-identical between the committed
red regression and fixed source; the fixed checker additionally records
installed-file hashes for independent reconstruction.

The repair delivers the existing child-only EOF helper and a three-line prefix
before every original backend byte, only after exact digest/folder/manifest/
flags/backend guards. The existing bounded selection repair in `utils.py` is
unchanged. Independent reconstruction checks all **15 original
members**, including the exact prefix and pre-existing utility adaptation,
and hashes the added helper. All other frontend, manifest, settings, rclone
manager and sync-target bytes remain unchanged. Existing copies need Update
or reinstall. Compatibility remains **partial**. All 116 pins/policies/ratings,
the other 115 complete rows and all 37 runtime cases are retained; installer
and checker AST outside the intended exact repair/probe are unchanged.

Published Decky **3.3.0 native AMD64**, isolated from network, host devices and
session, verifies **11 successful RPCs and seven expected selection refusals**.
Private file counts, inside-root links, outside paths/links, recursive-cycle
refusal and a preserved outside marker still pass. Private configuration
bytes, sync root and advanced-mode value survive restart. Two parent-only
unloads finish in **0.226 / 0.214s**; the first
follows real peer EOF. Both observe the original unload callback, zero forced
kills/errors, no remaining exact owned descendants and successful adopted
exits. These are scoped stop assertions; the generic recorder still does not
claim complete process/filesystem cleanup. All **33 native input hashes**
match the implementation commit.

Validation: **81 focused tests / zero skips**; full unit suite **2007 tests**
with **15 platform/optional skips**, 269.133s. Disposable simulator:
**53 tests / zero skips**, 408.257s, 116 exact archived plugins,
69 install/removes and 47 expected refusals; official plugin backends are
stubbed in this simulator, while the separate native Game Sync probe above
executes its published backend. The simulator log has
**0 unclosed HTTP socket ResourceWarnings**. Owned Compose resources
are removed, prior image tags restored, and the shared simulator identity,
start/restart count and health retained. No real Frame was contacted.

Fresh publication-head CI/e2e/native AMD64 and ARM64 and applicable ownership/
signed-package checks remain required. The failed main baseline must remain
visible; only exact-source fixed-head proof can justify a corrective merge,
followed by fresh main qualification. #536 and the rest of the queue remain
held until main is independently qualified. Actual rclone installation,
cloud authentication/sync, process-signaling methods, browser integration,
repaired ARM64/Frame runtime and worn/controller use are **unverified**.
This does not constrain rclone execution or its published `--copy-links`
behavior. No headset, schedule, security setting, social site or PR #113 was
changed. No release is qualified.

The JSON and compressed raw packet retain exact-main failure, red/green
reports and consoles, source fingerprints, complete test logs, simulator
cleanup and independent audit code.
