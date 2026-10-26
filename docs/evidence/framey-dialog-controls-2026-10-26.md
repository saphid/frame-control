# Framey activation and dialog follow-up — 2026-10-26

AlarMe 1.6.3 now has usable timer, preset and stopwatch controls in the local
Framey host with its official backend running on the ARM64 Frame. It remains
**partial**. This check does not establish audio, alarm/reminder, sleep-control,
background-notification or worn-VR compatibility.

The exact archive is store ID 124, SHA-256
`17d4166a9e98979df5fdb07c7eae42317acd54a453d3b82757508f971193c0fe`.
See the [structured results](framey-dialog-controls-2026-10-26.json).

## Reproduced blockers and repairs

AlarMe uses DFL `Focusable.onActivate` for timer pause, save-as-preset, cancel,
preset deletion, tabs and stopwatch controls. Framey's previous `div`
passthrough ignored that callback: clicks on the save/pause controls did not
dispatch backend calls. Focusable now maps pointer activation and Enter/Space
to plugin callbacks, exposes a keyboard focus target and respects disabled
controls. A click does not invoke both `onClick` and `onActivate` when a plugin
supplies both; nested activation stops bubbling to the parent action.

The previous ConfirmModal omitted `strDescription`, Cancel, middle actions and
disabled flags. showModal did not inject a `closeModal` callback into custom
dialog components, and every Close handle cleared the same root. A confirmation
opened by another dialog could therefore disappear when the earlier action
closed. Dialogs also appeared below the panel's long page content.

Dialogs now occupy a scrollable overlay inside the opaque iframe. They preserve
the underlying dialog's mounted state, receive scoped close callbacks, support
Close/ClosedPromise/Update, show confirmation descriptions and cancel/middle
actions, and respect disabled flags. The underlying plugin surface becomes
inert while a dialog is open; Tab stays in the top dialog, Escape cancels it and
closing restores focus. Steam popouts and controller navigation are not emulated.

43 official archives import ConfirmModal and 65 import Focusable in this
snapshot. These are shared API surfaces, **not** verification or status
promotions for every importing plugin.

## Real backend and local browser verification

Held the normal atomic shared headset lock. Installed the exact official archive
through the production archive validation/extraction path into a random private
directory. Used published Decky 3.3.0 ARM64, an unprivileged user service that was
never enabled, with a 900-second runtime bound and five-second stop timeout.
RPCs and events used Framey's production receipt-bound bridge through real Steam
CEF. The Chromium host served repository headset.html, React and framey-host.js;
its status endpoints were fixture-shaped, while AlarMe RPCs/events were live.

The initial private settings seed used the plugin display name instead of the
archive folder. A safety assertion failed on readback of the defaults before any
timer action. That service/data was removed and the lock released. The corrected
run read back subtle mode, zero volume, no auto-suspend, no sleep inhibition and
no overlay before exposing actions. Its relay allowed only the documented safe
methods; sound, suspend, sleep-inhibitor and arbitrary plugin actions were denied.

Verified with actual browser clicks and real backend readback:

1. Add Label opened a custom timer dialog. Created a silent five-minute timer
   named `Framey silent private timer`; live backend ticks changed its display.
2. Pause and save-as-preset activated after the Focusable repair. Backend
   readback reported a paused timer and its saved preset.
3. Delete Preset showed the preset's name in its confirmation description.
   Cancel closed the dialog without dispatching `remove_preset`; readback kept
   the preset. Reopening and choosing Delete dispatched it once and removed it.
4. Cancel removed the private timer. Watch opened the stopwatch; Start, Lap and
   Pause produced real backend state and events.
5. Closing and reopening the panel retained the paused stopwatch at 34.339
   seconds and one lap. Reset cleared it. Final readback showed no active timers,
   no laps and no active sleep inhibitor.

A separate local Chromium DOM fixture passed 14 checks for nested-dialog state,
scoped handles, descriptions, disabled buttons, Cancel, Escape, Tab wrapping,
Close/ClosedPromise/Update and pointer/Enter/Space activation. These programmatic
DOM checks do not verify physical input devices.

## Cleanup and remaining limits

Removed both private service units, bases and uploaded archives; reloaded the
user service manager and released the matching shared lock. A fresh locked audit
confirmed both units were not found, inactive and PID zero, with all test paths
absent. Managed Decky remained failed and the headset panel inactive, matching
the initial state. Battery was 97% before and 96% after. No power settings changed.

AlarMe stays partial. Audio, sound imports, alarms/reminders, auto-suspend and
`/dev/uinput` sleep inhibition were not exercised. Steam's global/in-game overlay
has no injection target inside Framey's isolated panel. Notifications require
the plugin panel to remain open. The deployed headset HTTP host, worn VR and
physical controller/keyboard input were not tested in this pass.

The store and documentation use the same exact-digest catalog reason. Aggregate
counts remain **4 works / 49 partial / 52 broken / 11 N/A**.

Validation: all 116 official IDs/versions/digests unchanged on store refresh;
fake-Frame 60 installed/removed and 56 blocked; full Python suite 1,628 tests,
16 skipped; Framey action/running Node contracts and both site test files pass.
The no-Steam-context Chromium pass attempted all 116 frontends (101 initialized,
15 failed); backend and network access were denied throughout that pass.
The repeat with synthetic library/running context initialized 104 of 116, with no
initialization regressions against the prior context-replay pass. Neither
initialization pass is a useful-functionality check.
