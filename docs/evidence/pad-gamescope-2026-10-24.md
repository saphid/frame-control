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

## Real Frame: focused click and ASCII keys received

Host: lxso2, `ssh frame`. SteamOS **0.5.6**, BUILD_ID **20261015.6141207**,
SteamVR **2.18.2**. At **11:05 UTC**, Game Mode was active, full Plasma was
inactive, Steam and SteamVR were running, battery was **99%**, and gamescope's
focusable/focused window lists were empty. The shared test lock was absent.
Existing X11 tools and libX11 were available; Tk could not load its library.

At **11:09:23 UTC**, an initial read-only preflight saw no focused window
but activity level **0** (idle), rather than the required **3** (standby), and
aborted before lock acquisition or input. At **11:09:57 UTC**, another task
held the shared lock with a focused panel; that lock and panel were left alone.

At **11:20:22 UTC**, read-only checks found the lock absent, no focused or
focusable windows, activity **3** and battery **98%**. The bounded probe ran at
**11:20:37 UTC** against implementation commit `5641d3c`:

1. Rechecked empty focus and standby, acquired `/tmp/frame-test.lock` with
   atomic `mkdir`, wrote a unique owner marker and rechecked both conditions.
2. Created only a disposable 640×400 X11 event-recorder window on `:0`, tagged
   with test app ID `2000999066`. It had a 45-second alarm and closed on stdin
   EOF. No existing application, full desktop or dashboard was started.
3. Waited for gamescope to report that exact window (`62914561`) focused.
   Started the production server's `TouchAgent` over SSH; it reported ready.
4. Called production `server.remote_touch` for positioning, then
   `server.remote_input` with a left click, `Frame66` and the Enter key button.
   Both responses reported `sent: true`. More importantly, the **window itself
   recorded ButtonPress/Release (button 1), the ASCII key events in order and
   Return**. `XLookupString` decoded exactly `Frame66\r`. The events were
   delivered through gamescope's EIS socket, not fabricated with XSendEvent.
5. Closed the helper by EOF and waited for exit, closed the recorder, checked
   empty focus and standby, then removed only the owner-matching test lock.

[State and received events](pad-gamescope-2026-10-24/readback.json) and the
[probe](pad-gamescope-2026-10-24/probe.py)/[X11 recorder](pad-gamescope-2026-10-24/recorder.py)
are retained. The archived scripts use checkout-relative source paths; the
recorded run used the same harness from `/tmp`. Motion records omit an unused
field that only has meaning for key/button events.

Delayed readback at **11:21:46 UTC** confirmed no test lock or recorder process,
empty focused/focusable lists, Game Mode active, full Plasma inactive, activity
3 and battery 98%. The original Steam and vrserver PIDs were unchanged. No
install, security/global setting change, dashboard/session switch, reset or
reboot was performed. No headset helper or owned lock remained.

This establishes **focused-panel click and ASCII key delivery on `:0`**.
It does not establish wearer-visible presentation, Unicode delivery or GUI
interaction. The absolute-position setup reached the recorder's edge
(639,399), rather than its centre; pixel-accurate absolute pointing is **not**
proved by this small-window probe. The trackpad click and typed keys still
arrived in the owned focused window. The original PR's earlier acceptance-only
observations remain historical; this observation adds actual window events.

## Offline checks and remaining limits

- `python3 -m unittest discover -s tests -p test_input.py -v`: **58 passed**.
- `python3 -m unittest discover -s tests -p test_touch.py -v`: **43 passed**.
- `python3 -m unittest discover -s tests -p test_service_regressions.py -v`:
  **34 passed**.
- `python3 -m unittest discover -s tests -v`: **1,403 ran, OK, 15 skipped**
  (Linux x86_64, Python 3.12; 150.825 seconds).
- Full fake-Frame e2e in task-specific Docker project `frame-control-pr66`:
  **47 passed** after the lock fix (192.270 seconds). Both task containers,
  their network and all three volumes were removed afterward. The run emitted
  an unclosed test-socket ResourceWarning; the suite returned OK.
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
passed **47 tests after this fix**. Exact-head CI results are recorded in the PR.

Remaining device work requires an idle, available Frame and the shared lock:
verify Unicode in a real text field, ordering under real typing load and
precise absolute pointing for small panels. Worn-headset presentation,
packaged Electron pointer lock and Windows GUI execution remain separate
checks. Automated Windows/macOS CI does not establish those interactions.
