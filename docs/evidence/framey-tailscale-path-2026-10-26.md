# Tailscale Control read-only backend and Decky PATH, 26 October 2026

The audited archive was official Tailscale Control 0.1.3, store ID 43,
SHA-256 `06411711b27101d438339000da3d91202d682862710b02ef3ddf2462e642448a`.
Earlier local Chromium evidence showed its settings panel. This check focused
on the Frame's CLI lookup; it did not run a live Framey panel RPC.

Each real Frame check acquired `/tmp/frame-test.lock` atomically with its own
random owner, read SteamVR activity and proximity, and released only that
owner's lock. The headset was in standby. The installed Tailscale CLI wrapper
resides in `~/.local/bin`, which the systemd user manager did not put in the
Decky service's inherited `PATH`.

| Check | Result |
| --- | --- |
| Exact official backend with the current service PATH | Three read-only status methods returned `None`; `tailscale` was not found. |
| Same backend in a disposable process with `~/.local/bin` prepended | The read-only methods returned active state, two exit-node entries and 16 device entries. |
| Bounded transient systemd user unit with the proposed service PATH | Found `tailscale` and completed `tailscale status`. The unit ended inactive, PID 0, `LoadState=not-found`. |

The Frame Control managed Decky unit now sets `PATH` to `~/.local/bin` plus
standard system directories when installed or updated. The install transaction
rolls its prior unit back on failure. No Tailscale `up`, `down`, routing or
exit-node change was run. No persistent test service, headset wake, controller
input or settings write was used.

This supports CLI discovery and read-only backend data on the real Frame. It
does not prove the production Framey-to-Decky RPC, connection controls, QR
asset, worn panel visibility or physical controller usability. Tailscale
Control remains **partial** in the digest-scoped catalog.

A later independent hourly read-only check found SteamVR activity 3
(standby), proximity raw 3.0625 and battery 93%. It released its owned lock;
no worn test was possible and the hourly schedule remains enabled.
