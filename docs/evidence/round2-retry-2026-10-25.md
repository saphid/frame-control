# Round 2 retry, 25 October 2026

The provider retry completed four further fixes, each in an isolated child
worktree with its own issue, branch, PR, tests, docs and Announcement draft.
The coordinator reviewed each patch, independently ran focused tests, verified
its exact head and complete CI, merged it, then read back GitHub's merged state.
PR #113 was untouched. No social announcements were posted.

## Merged fixes

| Change | PR | Merge commit | Coordinator focused tests | Final CI |
| --- | --- | --- | --- | --- |
| Skip linked backup ancestors and recheck before packing | [#215](https://github.com/saphid/frame-control/pull/215) | `da34d94` | 34 passed | 11 checks passed at `8cc03c8` |
| Clean orphan smoke metadata/shortcuts; POSIX runner without zsh | [#216](https://github.com/saphid/frame-control/pull/216) | `d5fa8fe` | 17 passed | 10 checks passed at `a5daa4a` |
| Separate Steam clips by headset/account/full session ID | [#217](https://github.com/saphid/frame-control/pull/217) | `1255ef2` | 62 passed | 10 checks passed at `7dfe777` |
| Retry failed automatic copies and bind listings to the captured headset | [#218](https://github.com/saphid/frame-control/pull/218) | `fdd60d3` | 33 passed | 10 checks passed at `af2bb17` |

Two initial CI fixture failures were fixed before merging: macOS temporary-path
aliases needed a resolved working directory in the wrapper test; Windows
needed explicit UTF-8 when reading the Settings test's HTML fixture.
Concurrent main changes #208/#209/#210 were preserved. Changelog conflicts
retained both entries. No history was rewritten.

## Integrated validation

At main `1255ef2`, after all four merges:

- `python3 -m unittest discover -s tests`: 1,559 tests, 16 skipped, passed in
  157.335 seconds. Loopback networking was enabled for local HTTP fixtures.
- `node --test app/test/*.test.js site/test/*.test.mjs`: 59 tests passed.
- Worker backup validation also passed both Docker recovery-kit E2E tests in
  an isolated Compose project, then removed its containers, volumes and network.
- Local proof logs: `/tmp/frame-round2-integrated-tests.log` and
  `/tmp/frame-round2-integrated-node.log`. Individual focused logs use
  `/tmp/frame-round2-{backup,smoke,clips,autosync}-review.log`.

## Real Frame smoke

The current host is lxso2; its existing direct `ssh frame` alias works.
Another OBS task initially held `/tmp/frame-test.lock`, so only read-only
checks were done until it released the lock. This coordinator then acquired it
atomically and labeled it `frame-round2-vdw4yh1xv8-20261025`.

The merged `scripts/frame-smoke.sh` ran directly without zsh at 06:38:37 UTC.
All 13 steps passed on SteamOS 0.5.6, BUILD_ID `20261022.6153909`. Native title
and Proton installs/launches/removals succeeded; the Windows title's remove
step stopped five test-owned PIDs. Both final process sweeps were empty.
Independent readback found no reserved title folders or metadata, SteamVR's
PID was unchanged, and the three observed gamescope focus properties matched
before/after. Battery went from 99% Charging to 100% Full. Only this task's
lock was removed, and its absence was verified.

[Sanitized structured proof](round2-smoke-2026-10-25.json). Raw local results:
`/tmp/frame-round2-smoke-results/2026-10-25T063837Z-20261022.6153909.json`;
console log `/tmp/frame-round2-headset-smoke.log`; state readbacks
`/tmp/frame-round2-smoke-before.txt` and `/tmp/frame-round2-smoke-after.txt`.

The headset was unworn. Visible rendering/controller input was not verified.
No pairing, password/security change, reboot or factory reset was performed.
The new backup/clip/auto-sync paths have local fixtures and cross-platform CI;
this smoke does not establish a new real-data backup/clip/UI test. Synthetic
orphan metadata was not seeded on the real device. Backup path checks retain
a documented race with concurrent filesystem changes.

## Prior round-two work reconciled

The failed coordinator checkout was still at v0.4.7. It was first updated to
main `d79efb4`, already v0.4.30. Earlier PRs had completed clipboard testing
(#124), original smoke process cleanup (#126), Windows VM capture (#129),
battery health (#125), setup doctor (#127), and read-only storage (#128).
Later evidence already covered real clip export (#147/#149/#154/#156) and
Return to Game Mode (#143/#157). These remain earlier evidence, not tests
performed by this retry. Physical Windows GPU/input and current physical
macOS checks remain incomplete; see the current support matrix.

Decision: fix reproduced data/cleanup/retry defects rather than automate game
moves without a verified transaction API or promise unverified phone-background
sync. Prepare v0.4.31; publication still requires its Linux AppImage install test.

## Delegation provenance

All implementations completed. Task IDs use prefix
`node:delegated-task:command%3Amcp%3Ad9bc35d8-0e9c-42c2-b798-25bd8af94d81%3Adelegate-task%3A`
followed by one of:

- `frame-r2-retry-smoke-orphans-20261025-r1`
- `frame-r2-backup-symlink-20261025-r1`
- `frame-r2-clip-collision-20261025-r1`
- `frame-r2-autosync-retry-20261025-r1`
