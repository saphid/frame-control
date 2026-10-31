# PC keyboard modifiers and shortcuts — 2026-10-31

This fix follows [keyboard feedback](https://x.com/ViralCellPhone/status/2116329709629780464)
about the importance of Ctrl, Alt and Esc, replying to
[Alex’s post](https://x.com/alexpsouthwell/status/2116294155404230915).
The source links record the reported issue; no social account was accessed or posted to.
Base: `8b56eeaf9c9bfb0ca82fc1706145e8e2a95bb766`.

The typing tool previously turned physical keydowns into complete taps. It
ignored standalone modifiers and allowed text-field Ctrl/Alt shortcuts to stay
local. It now retains physical press/release state during capture and sends
received text-field chords as complete taps. Command maps to Linux Super here;
the separate Capture viewer keeps its existing Command-to-Ctrl behavior.

## Event-path proof

`tests/page/pad_keyboard.cjs` runs production page code with DOM and transport
boundaries replaced. Its 66 scenarios use independently specified Linux key
codes. `tests/test_keyboard_chords.py` sends the resulting events through real
`remote_input`, validation, pad translation, `frame_touch.apply` and
`Gamescope.key`. HTTP/SSH agent transport and the final libei device/frame calls
are replaced; no compositor socket is opened. Exact
press/release lists and an empty held-key set are asserted for every scenario.

| Cases | Verified at the stubbed device boundary |
|---|---|
| Ctrl, Alt, Shift, Super/Meta, both sides | Distinct Linux key codes and balanced press/release |
| Tab, all four arrows, F1–F12 | Correct physical key codes |
| Ctrl+C/V/Z, Alt+Tab, Ctrl+Alt+T | Modifier presses precede the chord key; releases unwind the chord |
| Shift+Left, Super+T | Modifier holds preserved |
| Esc button | Real delegated button handler translates to Linux Escape down/up |
| Shortcut menu | Ctrl+C/V/Z, Alt+Tab, Ctrl+Alt+T, Super and F1–F12 emit complete chords/taps |
| Blur, hidden page, pagehide, pointer-lock loss | Held chord keys release before modifiers, including the error state |
| All four modifiers during blur | No ordinary or modifier key stays held |
| Missed modifier down, repeated keydown, swallowed Command keyup | State reconciles without duplicate holds or retained letters |
| Text-field chords, Shift, Command | Complete taps with the intended modifier flags |

The page queue tests preserve raw releases after failures, unacknowledged
requests and queue saturation. The existing headset-switch test now also
asserts that old modifier state is discarded. A server regression keeps
Unicode marked pending until its existing delivery estimate settles, so the
page does not start physical modifier capture during that interval.

## Validation

Focused keyboard tests: five unittest methods, including the 66 event sequences
and five Node behavior tests, passed on the host and in a disposable Fake Frame
image. Queue tests, all 62 existing input tests and the updated headset-switch
behavior suite passed. App tests: 50 passed. Website tests: 18 passed. Python
compilation, inline JavaScript parsing and `git diff --check` passed.

Full host unit suite: 1,914 tests in 246.101 seconds, successful with 16
platform/optional skips. The final focused keyboard rerun also passed after a
test-docstring clarification; production sources remained unchanged.

Final isolated Fake Frame e2e suite: 53 tests in 266.225 seconds, successful
with one optional full-catalog audit skipped because its cache is not mounted.
The owned Compose containers, network and volumes were removed afterwards.

The first full unit run found one outdated test fixture without the new held-key
set. The fixture was corrected and now asserts modifier clearing on headset
switch; it was not treated as a passing run.

## Simulator and limits

The focused keyboard test also ran with no network and a read-only repository
mount in disposable `fakeframe-frame` image
`sha256:4d43e1f772f604770b6fe1d1d3e189abad5f5615f9fb53ae1320d63fadfa2eb7`.
It passed five tests and removed its container. This is a simulator-image event
fixture, using the same final-device stub, not compositor or visible UI proof.
The existing shared `frame-sim` session and its data were left alone.

The full Fake Frame e2e run uses its own Compose project and volumes, not the
shared simulator. Its optional full-catalog test is skipped when no audit cache
is mounted. Fake Frame has no real gamescope/libei keyboard socket. This run
checks broad server/install regressions, not headset application key delivery.

No real Frame was contacted, woken or sent input. Real compositor input,
wearer-visible behavior, controller interaction, browser rendering, platform
shortcut interception and app-specific bindings remain unverified. An OS may
withhold Alt+Tab, Super/Command or function shortcuts completely. The UI explains
this and offers explicit menu/button input; it does not claim to override the OS.
Physical Esc exits capture; the Esc button sends remote Escape. Browser closure
or disconnection cannot guarantee immediate release delivery.

[Supported keys and user-facing limits](../keyboard-input.md).
[Exact source fingerprints](keyboard-chords-2026-10-31.json).
