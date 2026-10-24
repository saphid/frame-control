# Keyboard and trackpad through gamescope, 2026-10-24

PR: [#66](https://github.com/saphid/frame-control/pull/66), `pad-gamescope`.
Parent/main: v0.4.18 commit `0da1fe5`. Merge commit: `1737366`, with parents
`cba23fb` (the existing PR) and `0da1fe5` (main). No history was rewritten.

## Merge and implementation

Both `/api/input` (keyboard/trackpad) and `/api/touch` (live-view Control)
start and poll the gamescope helper. KDE Connect starts only when Unicode
typing needs it. The existing ordered, bounded queue and switch cancellation
remain in place; cross-service typing order is an estimate, not an application
acknowledgement.

The merge keeps main's intended-device validation and work reservation before
a GET starts an input helper, immutable SSH routes, launch generations and
serialized writes. Switching headsets also stops the power report and resets
both input agents and queued typing before publishing the new route. The page
keeps main's Tools sections, clipboard controls and single instances of the
keyboard/trackpad and VR tools, with the PR's gamescope help text.

The start/status regression tests now exercise the gamescope helper for both
endpoints. An explicit `/api/input` test checks that start and poll use that
helper without starting KDE Connect. Existing stale/missing-headset and
route-reservation tests remain active.

## Real Frame: read-only preflight; input not tested

Host: lxso2, `ssh frame`. SteamOS **0.5.6**, BUILD_ID **20261015.6141207**,
SteamVR **2.18.2**. At **11:05 UTC**, Game Mode was active, full Plasma was
inactive, Steam and SteamVR were running, battery was **99%**, and gamescope's
focusable/focused window lists were empty. The shared test lock was absent.
Existing X11 tools and libX11 were available; Tk could not load its library.

A disposable X11 event-recorder probe was prepared outside the repository. It
would acquire `/tmp/frame-test.lock` atomically, create only its own window,
check that gamescope focused it and that activity remained standby, then use
the production server's input functions and SSH helper. Cleanup was designed
to close the helper by EOF, destroy the owned window and remove only its own
owner-marked lock. It did **not** run those active steps.

At **11:09:23 UTC**, its read-only preflight saw no focused window but activity
level **0** (idle), rather than the required **3** (standby), and aborted before
lock acquisition, window creation or input. A later read at **11:09:57 UTC**
found another task's shared lock and a focused window. That lock and panel were
left alone. No test helper was launched on the headset, no input was injected,
and this task had no owned headset lock to release. No dashboard/session switch,
application install, security setting change, reset or reboot was performed.

This run does **not** prove a real focused-panel click or key on current
SteamOS. The PR's earlier report that the helper accepted move/click/text/Enter/
scroll events and started KDE Connect for an accent remains historical evidence
only; it did not prove delivery to a focused panel either. Older focused-input
observations documented in `streaming.md` concern other test sessions.

## Offline checks and remaining limits

- `python3 -m unittest discover -s tests -p test_input.py -v`: **58 passed**.
- `python3 -m unittest discover -s tests -p test_touch.py -v`: **43 passed**.
- `python3 -m unittest discover -s tests -p test_service_regressions.py -v`:
  **34 passed**.
- `python3 -m unittest discover -s tests -v`: **1,403 ran, OK, 15 skipped**
  (Linux x86_64, Python 3.12; 150.825 seconds).
- Node page suites: `ctrl_gestures.mjs`, `pad_queue.mjs`, `desk_panels.mjs`
  passed, using the production page functions.
- `node --test app/test/*.test.js`: **3 test files passed**.
- `node --test site/test/*.test.mjs`: **2 test files passed**.
- Python compilation, desktop/site JavaScript syntax and `git diff --check`
  passed. Fake-Frame e2e and exact-head CI results are recorded in the PR after completion.

The first full regression run executed 1,401 tests and found two tests still
expecting `/api/input` to start the old KDE Connect helper. They were updated
to the intended gamescope route. The final full run includes the lazy-KDE
regression above and the lock-order regression below. The initial restricted-sandbox input run could not open
loopback sockets; the focused rerun with managed network access passed.

Review of the merged code then found a lock inversion: the Unicode worker
held the pad-send lock while `InputAgent.start()` acquired the route lock,
whereas a headset switch held the route lock before resetting the pad. A
bounded subprocess regression reproduced the deadlock with the real
`InputAgent.send/start` methods and an offline launch stub. Unicode delivery
and resets now take the route lock before the pad lock; the route lock is
reentrant so an agent can capture its route inside that reservation. The new
regression passed after the fix, as did all **58 focused input tests** and
the **1,403-test full suite** (15 skipped). The local fake-Frame suite also
passed 47 tests before this fix; its final rerun and exact-head CI results are
recorded in the PR.

Remaining device work requires an idle, available Frame and the shared lock:
record actual button and key events in an owned focused panel, verify Unicode
in a real text field and evaluate ordering under real typing load. A worn
headset, packaged Electron pointer-lock path and Windows execution are separate
checks; no result here substitutes for those interactions.
