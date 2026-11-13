# Type from your computer into the Frame

Open **Keyboard and trackpad**, turn it on, then focus the app or panel you want
to control in the headset. Click the trackpad area to capture your computer's
keyboard and mouse. Press **Esc** to stop capture.

| Keys | Forwarding |
|---|---|
| Ctrl, Alt, Shift, Super/Windows/Meta | Left and right keys send separate press and release events during capture. Mac Command sends Linux Super. |
| Tab, arrows, F1–F12 | Send physical key events during capture. |
| Esc | Physical Esc exits capture. Use the **Esc** button to send Escape to the headset. In the text field, Escape also sends a tap. |
| Ctrl+C, Ctrl+V, Ctrl+Z | Forward to the focused headset app; also available in **Send shortcut**. Ctrl+V uses the headset's clipboard. |
| Alt+Tab, Ctrl+Alt+T | Forward when the browser receives them; **Send shortcut** sends a complete chord without relying on host interception. |
| Super and F1–F12 fallback | Choose the key in **Send shortcut**, then click **Send shortcut**. |

Capture sends the modifier down before the chord key, and releases the chord
key before the modifier. Leaving capture, switching windows, hiding the page
or losing focus queues releases for all held keys and mouse buttons. Releases
are retained across a connection error for retry. A disconnected or closed
browser cannot guarantee immediate delivery; reconnect and use **Try again**
if the tool reports an error.

The text field keeps ordinary typing, pasted Unicode and input-method text on
the existing text route. It also forwards received Ctrl/Alt/Meta chords as
complete taps, including Shift when held. Use capture for standalone modifier
holds. AltGr and composing text remain text input in the field. Capture uses
physical key positions and the headset's layout; use the text field for accents,
emoji and other layout-dependent text.

Your computer or browser can keep Alt+Tab, Command/Super combinations, function
keys and other system shortcuts. Frame Control cannot forward an event it never
receives. The shortcut menu and Esc/Tab/arrow buttons provide explicit remote
input without changing your computer's system shortcuts. The menu and entry
into capture wait for queued input to finish so a modifier cannot be held over
pending Unicode text.

Sending the right events does not mean every headset app implements the action:
Ctrl+Alt+T needs a desktop terminal shortcut, for example. Browser/OS interception,
focus and app bindings still apply. The separate Capture viewer retains its
existing Command-to-Ctrl mapping; this page describes **Keyboard and trackpad**.

Automated coverage executes the production browser handlers, server validation,
translation and gamescope input dispatch through the libei key-call boundary.
HTTP/SSH transport and the final device are test doubles. These tests establish event sequences and
focus-loss cleanup, not real-headset or wearer-visible usability. See the
[keyboard verification record](evidence/keyboard-chords-2026-10-31.md).
