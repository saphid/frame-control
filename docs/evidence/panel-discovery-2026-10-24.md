# Panel discovery investigation, 2026-10-24

Base: v0.4.16 (`040581a`). Scope: issue #73, Desktop Capture and Control.

## Evidence and change

Issue #73 reports SteamOS 0.4.5 with its desktop visibly running, without a
Frame Control version or steps. The maintainer's 2026-10-12 comment identifies
the duplicate `loadPanels` UI function fixed in 0.4.3 and requests the exact
remaining message and SteamOS build if it persists. There is no reporter
follow-up. At this base, the functions are distinct and the existing Node
regression checks their uniqueness and the Desktop GET request.

Read-only source inspection found a remaining diagnostic ambiguity:
`read_props()` returns `{}` for failed/timed-out X queries and missing root
properties. `panels()` treated that like a confirmed empty focusable-window
list. With no detected Plasma process it claimed no panel was open; with Plasma
it claimed SteamOS was not listing the desktop. Neither claim follows from an
unreadable list.

The change checks for the presence of `GAMESCOPE_FOCUSABLE_WINDOWS` before
those claims. An absent list now reports unknown panel state, suggests checking
SteamVR and retrying/Headset view, and asks for the exact message and SteamOS
version if persistent. Missing-tool and whole-run deadline explanations retain
precedence. No new probes, retries, timeouts, input or capture routes are added.

## Real-device boundary

A preliminary read-only SSH inspection returned SteamOS 0.5.6, BUILD_ID
`20261015.6141207`, battery 99%, discharging, and X0/X1 socket names. It made
no headset changes. The shared lock was absent at that moment.

The subsequent atomic `mkdir /tmp/frame-test.lock` failed with `File exists`.
The guarded command exited with status 3 before the session, X-property or
panel-helper probes ran. The other task's lock was left alone. No application
was installed, started, stopped or focused; no headset settings changed.

That implementation probe was blocked by the occupied shared device. The
coordinator later supplied a separate narrow read-only observation on SteamOS
0.5.6, BUILD_ID `20261015.6141207`, at battery 99%, with the shared lock absent
and both `xprop` and `xwininfo` installed:

- In **Game Mode**, `DISPLAY=:0 xprop -root GAMESCOPE_FOCUSABLE_WINDOWS
  GAMESCOPE_FOCUSED_WINDOW` returned both properties **present but empty**.
- On `DISPLAY=:1`, both properties were reported **not found**.

This observation distinguishes a confirmed empty list on `:0` from absent
properties on `:1`. It does **not** reproduce #73's Desktop Mode report on
SteamOS 0.4.5, and it does **not** test this PR's code on the headset. It is a
coordinator-supplied observation, separate from the blocked implementation probe
above; no new headset probe was run for this follow-up.

Remaining limit: there is no reproduction establishing a further
capture/discovery fix for the reported Desktop Mode/build combination. This PR
improves a demonstrated diagnostic error; it must not close #73 as a verified
new capture fix.

## Offline verification

Focused Python regressions distinguish absent, focus-only, failed/timed-out X
queries, confirmed empty and desktop-running lists. Existing tests cover
missing tools, alternate displays, successful discovery and the 12-second
deadline. The production page's Node behavior test verifies that both Capture
and Control preserve the unreadable-list advice. These use fake X/HTTP/DOM
boundaries and do not prove real SteamOS 0.4.5 capture or physical input.
