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

## Earlier blocked real Frame attempt

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

## Follow-up real Frame smoke at the exact PR head

**Passed, 2026-10-24 10:35:02–10:35:23 UTC**, with byte-identical media modules
from **`5d551a81658d9ff14f49285c28609d506cbc20aa`**. This later run resolves
the earlier lack of fresh playback evidence. No production code changed.
The headset was unworn. SteamOS **0.5.6**, BUILD_ID **20261015.6141207**,
SteamVR **2.18.2**; battery **100%, Full** before and after.

Read-only preflight found Game Mode (`XDG_CURRENT_DESKTOP=gamescope`,
`start-gamescope` running, no `plasmashell`), Steam/SteamVR running, no media
overlays, and the installed media service inactive/not loaded. The test then
acquired `/tmp/frame-test.lock` with atomic `mkdir`; it did not take over a
foreign lock. Under the lock, those safety conditions were checked again.

Only generated media and the PR's four unchanged modules were uploaded, under
the test-owned, uid-1000 directory
`/tmp/pr51-5d551a8-4c0976a52564-utfbk_m0/`. The clip was a **12 s, 30 fps,
960×540 half-SBS H.264** MP4 with solid red/cyan eye images and **silent AAC**.
It was generated with FFmpeg's `color`, `hstack` and `anullsrc` sources; no
personal or external media was used.

The exact `frame_media_remote.run()` Play/status/Stop path was exercised by
importing its unmodified module and changing only its in-memory `ROOT`,
`RUNTIME`, `STATUS` and `UNIT` constants to the isolated test locations and
`frame-control-media-pr51-5d551a8-4c0976a52564.service`. The real
`frame_media_player.py` ran unchanged with `--layout auto --theatre`, using
`h264_v4l2m2m` and Pulse output. This checks the player and its systemd lifecycle;
it does **not** reverify the HTTP/UI upload or runtime installer, nor the
literal production unit name. The installed media runtime, log, status and
library were preserved.

- First Play: `starting` → `playing` → **`ended`**, **360 frames**, **160 dropped**,
  **12.0397 s**, `running=false`. The drops were the normal unworn/standby
  `SetOverlayRaw` retry path; no fault was forced. At 60 frames, dropped was 0.
  `vrcmd --overlays` listed `framecontrol.media.surround` as **1×1 visible**
  and `framecontrol.media.screen` as **visible**. These are SteamVR metadata,
  not a wearer or eye-capture verification.
- After EOF: unit **inactive/dead, not-found, MainPID 0**, no test player or
  decoder, and neither owned overlay remained. Stop after EOF succeeded and
  retained `ended`.
- Second Play reached `playing`, 60 frames, 0 dropped. Explicit Stop returned
  **`stopped`, 72 frames, 0 dropped, `running=false`**. Again the unit was
  inactive/dead/not-found with MainPID 0, no player/decoder and no owned overlays.
- The test unit's `ExecStart` and cgroup identified the unique temporary
  runtime. First-run player/decoder PIDs were **309650/309655**; second-run
  PIDs were **309805/309810**. Stop controlled only this dedicated test unit.
  Its player log was empty; no surround refusal or teardown error was logged.

### Uploaded SHA-256 values

```text
generated_SBS.mp4      1b39cac1d3b092b89657250c817019b68e87a474976ccd44aeb38e8eee44ffca
frame_media.py         001e3158f4c3931794846b21f1e4cb553349d9326b4db1454a01976d446ad97a
frame_media_player.py  86b0a140ebff857c2819c74d3ac45d1897735c585d44c7360ad6f18c2ecf2645
frame_media_remote.py  b60386eb192d32594358246a4e665474c543600f2c564c2efd554ef38d7a631d
frame_splat.py         f35750926f1149c41b95617a302012406d355c0dfdd4530438b0c42ee6d55daa
```

### Cleanup and limits

The temporary directory, including its fixture, code, bytecode, status and log,
was removed only after verifying that its player and decoder had exited. The
transient unit was collected. The test released only its own lock after cleanup.
All installed media runtime file hashes, including `player.log` and
`status.json`, were unchanged. The installed `frame-control-media.service`
remained inactive/not loaded. Steam **297826**, vrserver **297506**,
vrcompositor **297620**, vrdashboard **297721**, and start-gamescope **296997**
kept the same PIDs. The pre-existing overlay key/dimension/visibility/type
inventory matched the final inventory, and all dashboard main panels remained
`not_visible`. No dashboard command, wake request, global setting, reboot or
Steam/SteamVR stop was issued.

Cosmetic surround refusal and exceptional teardown remain **fake-tested**;
no real refusal or teardown fault was induced. This short unworn-headset
smoke does not verify appearance, eye isolation, comfort, audible sound/lip
sync (the AAC was silent), sustained display performance, or the issue #28
report of laggy 1080p video. It does not cover new H.265, photo or splat cases.
Historical checks remain in the earlier PR #51 description and
[media playback notes](../vr-video.md). The PR remains draft and unmerged
for parent review and CI.
