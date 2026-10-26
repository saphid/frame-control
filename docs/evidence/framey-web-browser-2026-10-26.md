# Official Web Browser 1.4.3 frontend follow-up

The exact official Decky store archive for ID 59 is 91,859 bytes and matched
SHA-256 `1192864fddc5d72550346b8dff02c21d71f0c40a06ac41c4e67bb6220d267f9d`.
Its legacy bundle calls `deckyFrontendLib.getReactRoot` when attempting to patch
Steam's main menu and search bar. The prior full-catalog audit recorded
`getReactRoot is not a function` and initializer failure.

Framey's isolated iframe has no Steam React root. The host now exposes
`getReactRoot()` with a **null** result, consistent with its existing inert
`findInReactTree()` lookup. It never returns a fabricated Steam tree or permits
patching the user's Steam UI. The focused Node host test checks this contract.

A focused local Chromium run used the verified archive through
`scripts/framey-audit-browser.py`, with every backend method, fetch and
WebSocket denied. The exact frontend reported `ready=true` with no initializer
error after 2.5 seconds, and again during a longer ten-second observation.
It attempted `set_main_tab` and `load`; the audit denied both. Console output
reported that no Steam window or main-menu root was available. The panel did
not show a usable browser view in the audited state.

Static inspection of this archive's published Python backend shows
`set_main_tab()` requesting a Steam GamepadUI CDP tab, then returning a key and
port for its own WebSocket server. That Steam tab and browser injection path
are outside Framey's isolated panel. No real plugin backend was executed, no
browser tab or navigation was verified, and no real Frame or worn-VR check was
performed for this change. The catalog retains **broken** for this digest; its
reason and focused observation now distinguish successful initialization from
the unresolved core browser dependency. The full 116-plugin browser baseline
still refers to its earlier host commit; this is a one-plugin follow-up.
