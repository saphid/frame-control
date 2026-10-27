# Frame Control standing goal and historical recovery handoff

Owner: Alex. This records the 27 October 2026 AEDT recovery handoff; status
checks below use UTC. Alex subsequently authorized the existing coordinator to
continue the roadmap and publish releases when every gate passes. This document
does not authorize a second coordinator to run concurrently.

## Alex's top priority

> Make Frame Control's released version always stable and running cleanly. Never release something that isn't working correctly. I don't want to break things for people.

Keep the released app stable and main green. Investigate failures before
shipping; a version number or an uploaded artifact is not proof of readiness.

## Standing roadmap

Continue official Decky compatibility, test gaps, fixes and useful features.
The existing owner is T3 job `mppkd9qczt` on lxso2. Preserve its work and avoid
competing coordinator or release jobs. Verify its current state before any
takeover; this historical handoff is not a takeover instruction.

## Mandatory release gates

- CI must be green on the **exact release commit**, not merely an earlier
  commit, another branch, or a previous successful workflow attempt.
- End-to-end tests and release verification must pass for that candidate.
- Every required installer build must succeed, including Linux, Windows,
  macOS Intel and macOS Apple Silicon.
- Never publish a release with failed or cancelled required builds. A retry
  must actually finish successfully; a cancelled build is not a pass.
- Keep main green. Resolve required failures before merging or releasing.
- Preserve evidence linking the release tag/commit, successful workflow run,
  installer assets/checksums, e2e results and real-device verification.
- Use `scripts/publish-release.sh --dry-run TAG` before publishing. Alex's
  standing full-auto instruction authorizes the existing coordinator to tag and
  publish after every gate passes. Stop for secrets, money, destructive Git
  actions or wiping the headset; never bypass a failed release gate.

## Current release state, checked 27 October 2026 at 05:15 UTC

- The latest public release is
  [v0.4.51](https://github.com/saphid/frame-control/releases/tag/v0.4.51),
  published at 05:10:05 UTC from main commit
  `4da7220660ba345bc46cdb525b6c512bc6a9d8bd`.
- [Exact-commit checks](https://github.com/saphid/frame-control/actions/runs/40451752952),
  [native Decky runtime](https://github.com/saphid/frame-control/actions/runs/40451752953),
  and the [tagged installer release](https://github.com/saphid/frame-control/actions/runs/40452627862)
  succeeded. The tag release built Linux, Windows, Intel Mac and Apple Silicon
  Mac installers and checksums. The published update manifest reports 0.4.51.
- The locked candidate smoke passed 12 checks, skipped one optional x86_64
  launch, and failed none. SteamVR was in standby; worn display and physical
  controller use remain unverified. The hourly shared-lock worn check remains
  enabled. See [candidate evidence](../evidence/v0451-candidate-2026-10-27.md)
  and [release evidence](../evidence/v0451-release-2026-10-27.md) for the exact
  asset audit and publication record.
- Main matched the release commit and its checks were green at this check.
  Revalidate before another merge or release. Disk capacity on lxso2 remains
  critical; do not delete pre-existing data to make space without Alex's OK.

## Incident snapshot supplied by Alex

At the time of the recovery request, latest published was **v0.4.47** with a
passed release run; **v0.4.48 RC was not published**, after a failed run with a
cancelled macOS build. PRs **#337 and #338 were open**. Preserve this as the
historical incident snapshot, not a claim that remote state stays unchanged.

## Verified update during recovery

Checked 26 October 2026 around 21:58 UTC:

- v0.4.47 was published at 15:07:28 UTC.
- A subsequent v0.4.48 release run
  [40406781383](https://github.com/saphid/frame-control/actions/runs/40406781383)
  completed successfully on commit
  `5438e1d9d05ca472f200dcde50799c8ae882fafb`. Its Linux, Windows, Intel macOS
  and Apple Silicon macOS installer jobs, draft and checksum jobs all succeeded.
- GitHub now reports **v0.4.48 published at 21:53:29 UTC**. This publication
  happened outside the recovery task. Recheck the exact-commit checks and
  release evidence before drawing conclusions about all release gates.
- [#337](https://github.com/saphid/frame-control/pull/337) is merged; lxso1's
  clean main was fast-forwarded to
  `1ddb6278b8ae0a98ecc79a181bba4d3cc67a52b6`.
- [#338](https://github.com/saphid/frame-control/pull/338) was open at that
  time; it has since merged.
- lxso2 T3 recovered at **21:42:54 UTC**; port 3773/local HTTP and existing
  HTTPS returned 200 by 21:43:58 UTC. Root disk capacity remains critical;
  recovery is not a capacity fix.
- Fleet guards, probe units, safety tests and incident evidence are proposed
  in [fleet #38](https://github.com/saphid/fleet/pull/38); units were installed
  under the owner's incident authorization. Disk critical alerts use the
  existing fleet Prometheus/watchdog pipeline.

## Historical lxso1 readiness

Main checkout: `/home/saphid/projects/steam-frame` (GitHub repository
`saphid/frame-control`). Shell default Node may be older; use
`~/.nvm/versions/node/v24.22.1/bin` first in PATH for Node 24 CI commands.
Python 3.9.25 and 3.13.14 were installed through uv for the CI matrix; system
Python 3.12.3 already existed. Workflows at that time required no Rust/Go
toolchain.

Readiness commands, per-gate logs and exact-commit JSON results live at
`/tmp/frame-control-readiness-20261027/` on lxso1. These are local readiness
checks, not a substitute for GitHub CI on a future release commit. The Linux
installer command uses `--publish never`; no release was published by these
checks. Native ARM64, Windows/macOS platform gates, Xcode/iOS and real-headset
checks still require their proper runners/hardware.

Completed on main commit `1ddb6278b8ae0a98ecc79a181bba4d3cc67a52b6`,
26 October 2026 at 22:00 UTC:

| Gate | Result on lxso1 |
| --- | --- |
| Shell syntax, Python compile | Passed |
| Python 3.9 / 3.12 / 3.13 server suites | 1,639 tests each; passed with platform/optional skips |
| Linux wireless doctor, app syntax/tests, website tests/syntax | Passed |
| `npm ci`, `npm run dist:linux` | Passed; AppImage and deb built without publishing |
| AppImage launch verification | Passed |
| `scripts/e2e.sh` on x86_64 Docker | Passed: 50 tests, one optional catalog audit skipped; not native ARM64 hardware proof |
| Publish dry runs for v0.4.47 and v0.4.48 | Passed, including all ten installer digests and SHA256SUMS; no mutation |
| Native PC host build and required-native tests | Blocked/failed: GStreamer/GLib development packages absent; required native adapter unavailable |

The workflows name system GStreamer packages but do not pin package versions.
They were left uninstalled under the owner's pinned-versions-only constraint.
Resolve that dependency policy before claiming full Linux native readiness.
Main was clean and matched origin/main on the final 21:59 UTC fetch.

## How a takeover should resume

1. Read this file, `docs/testing.md`, the current roadmap/evidence and the
   existing coordinator's recorded work through supported read-only tooling.
   Verify remote releases, PR states and workflow conclusions again.
2. Check lxso2 health and disk headroom. Disk-full recovery requires capacity
   decisions; do not delete protected data or alter T3 state databases.
3. Confirm that the existing coordinator is no longer active and that the
   takeover is authorized by the current instructions. Preserve uncommitted
   changes and active worktrees; do not run competing coordinator/release jobs.
4. Fetch origin and inspect local status before updating main. Resume the
   roadmap from recorded gaps and existing PRs, not from assumptions about
   what an interrupted worker completed.
5. Work on an isolated branch and use PRs. Validate the actual candidate
   commit with every release gate above; record hardware/platform blockers.
6. Publish only after all required gates pass under Alex's current full-auto
   instruction or a newer explicit instruction.

The lxso1 five-minute `fleet-t3-lxso2-health.timer` only checks and alerts; it
does not start takeover threads. Automatic stand-in launch is not configured
or proven by this recovery deployment. It would need supported gateway
capability and authorized credentials; do not copy or mint gateway secrets.

The original handoff copy was placed at
`/home/saphid/frame-control-handoff/STANDING_GOAL.md` on lxso1. This repository
document may be newer.
