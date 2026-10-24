# Media surround hardening: 2026-10-24

PR [#51](https://github.com/saphid/frame-control/pull/51), branch
`theatre-media-surround-hardening`, merged main `2ded4c5` without rebasing.
Both fixes remain necessary on that main: an optional-surround error escapes
`play()`, and a non-`RuntimeError` during overlay teardown skips the remaining
handles and OpenVR shutdown.

## Offline checks

- Focused media suite: **23 tests passed** on Linux / Python 3.12.3.
- Final full suite: **1,381 tests, OK (15 skipped)** in 145.384 s with
  `PYTHONFAULTHANDLER=1 python3 -m unittest discover -s tests -v`.
  The service-regression module passed **33 tests**. Player/server compilation
  and `git diff --check` passed. Current macOS/Windows validation is left to CI.
- The startup/upload, creation/setup, deferred-surround refusal and teardown
  regression tests were also run with main's player implementation: they
  failed as expected (six errors across subtests). The screen-refusal test
  passed, confirming that actual screen failures still propagate.
- The historical macOS failure was job
  [109239733717](https://github.com/saphid/frame-control/actions/runs/36516462623/job/109239733717),
  on `dac9dbc`, Python 3.12: 619 tests, three failures in artwork resolver
  tests (`test_resolver_slot_released_when_thread_cannot_start`,
  `test_timed_out_lookups_are_capped`,
  `test_url_fetch_refuses_private_hosts_and_honours_deadline`). Media tests
  passed. Late DNS workers retained semaphore slots; the first failed
  assertion could also leak acquired slots into later tests.
- Main already contains `8051687`'s wait-for-idle and unconditional slot
  cleanup, preserved by `d546568`. The current artwork module passed all
  **40 tests** locally. No additional artwork changes were needed.
- The first full run completed **1,380 tests, 15 skipped**, with one failure:
  `test_a_second_server_is_refused_until_the_first_exits` observed SIGSEGV
  (`-11`) instead of exit 1. All 41 server tests passed on a focused rerun.
  Main started daemon index/TLS workers before refusing a second server;
  its existing shutdown notes document a race with OpenSSL interpreter exit.
  This crash mechanism is inferred; the first run did not retain a native
  fault trace. The subprocess assertion now retains stderr for diagnosis.
  A deterministic regression now checks that rejection starts no listener,
  cleanup sweep or background workers. It failed before moving the ownership
  check ahead of startup work and passed afterwards.

The surround retry now logs a refusal before discarding that cosmetic work.
Creation, setup and first-upload failures also allow the screen to play;
standby remains retryable, and screen errors remain fatal. Teardown tests
exercise OpenVR errors, unexpected exceptions and a late `InterruptedError`,
checking that all handles are attempted and shutdown runs.

## Real Frame preflight and limit

Read-only SSH preflight: SteamOS **0.5.6**, BUILD_ID **20261015.6141207**;
SteamVR server PID **297506**, compositor PID **297620**; existing media
service `inactive/dead`, MainPID 0; battery **99%**, fuel gauge `Not charging`,
charger `Full`. The shared lock was absent at preflight.

The subsequent atomic `mkdir /tmp/frame-test.lock` failed with
`FileExistsError(17, 'File exists')`: another session acquired it in between.
The probe stopped before uploading files, launching media, creating overlays,
or changing any state. The foreign lock was neither modified nor released.
All generated fixtures remained on the computer and were then removed; no
headset cleanup was necessary. Steam/SteamVR and the prior player state were
left alone.

There is **no new real-device playback evidence** for this revision. Historical
unworn-headset checks on SteamOS 0.4.1 / SteamVR 2.18.1 are in the earlier
PR #51 description and [media playback notes](../vr-video.md). Cosmetic
surround refusal and exceptional teardown remain fake-tested; no real
rejection was induced. Headset appearance, comfort, audible sound/lip sync,
and real display performance remain unverified. This change does not address
the later issue #28 report of laggy 1080p video.
