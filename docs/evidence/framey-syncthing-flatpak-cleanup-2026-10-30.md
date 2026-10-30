# Signed Flatpak instance cleanup, 30 October 2026

Main `af0433b` passed signed package launch, actual two-way sync, restart and
owned process cleanup, then failed the immediate `flatpak ps` assertion in its
AMD64 native job. The original failure archive and digest are retained in the
[source-bound record](framey-syncthing-flatpak-cleanup-2026-10-30.json).

[PR #478](https://github.com/saphid/frame-control/pull/478) at `dbbee87` waits
within the existing bounded readiness window for the instance registry to
clear. It retains the last list and elapsed time. It does not kill processes;
forced termination, failed queries and persistent instances remain failures.
All 26 focused tests pass, including transient registry lag, persistent entries
and query failures.

A fresh local AMD64 replay passed at that exact head. Its independent audit
matched all 13 runtime source hashes, pinned signed commits, ten signed process
identity checks, nine setup results, 17 lifecycle results, 18 ownership
refusals, 12 migration results, actual sync, preserving uninstall and QEMU
cleanup. The final recorded instance-list query completed in 0.273 seconds.

The exact-head AMD64 CI artifact also passed independent audit of source,
signatures, actual signed identities, migration and cleanup. Its final list was
empty after 0.112 seconds. These passing runs do not reproduce registry lag;
the behavioral regression test supplies the transient/persistent cases.

Main's unchanged ARM64 signed-package job passed and its artifact was
independently audited. Its backend setup needed one null scan before finding
8384; that does not prove a UI retry. Main's failed AMD64 job has been requested
once more now that its containing workflow finished. The first failure remains
retained, and no release is attempted from this commit.

#478's ARM64 CI and the retry remain pending. No whole-main green or merge pass
is credited. Syncthing installation stays blocked. No real Frame, SteamVR
visuals or physical controller use were tested; the hourly worn schedule is
unchanged.
