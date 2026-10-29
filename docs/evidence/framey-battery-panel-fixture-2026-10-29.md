# Battery Tracker 0.2.0 local panel replay, 2026-10-29

The official Battery Tracker ID 67 archive is pinned at SHA-256
`91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94`.
The native Decky gate already covers adapted backend discovery and private
Frame-shaped battery history on amd64 and ARM64. The previous browser audit
proved frontend initialization while denying its backend calls. This probe
checks the panel with synthetic history; it does not run the plugin backend.

## Reproduce

Copy `tests/fixtures/framey-official/67.zip` to a temporary cache named
`91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94.zip`.
Run `python3 scripts/framey-audit-browser.py --cache <cache>
--battery-tracker-fixture` and open its loopback URL in local Chromium. Run
`runAudit([67], 4000)` in the console. The panel remains open in this mode;
inspect `window.batteryFixtureCalls`, then click the Lookback in days slider
and press ArrowRight. The fixture accepts only legacy `get_recent_data` for
integer lookback values 1–7 and `set_app`. Other methods get an error. The
ordinary 116-plugin audit keeps backend calls denied, and CSP retains
`connect-src 'none'`.

## Observation

The exact frontend reported `ready: true`, `error: null`, and called only
`set_app` and `get_recent_data`. With synthetic `cap=[0.89, 0.88]` and one
private power row, the opaque iframe showed Recent Battery Use, Lookback in
days, and `Framey private: 1.5W`. Its canvas render callback ran without a
frontend error. The browser's accessibility tree showed the slider at 1;
after a pointer click and ArrowRight it showed 5. The fixture call log
recorded `get_recent_data` with lookback 1, 4 and 5. The running-game bridge
was unavailable in this isolated audit and logged warnings. Browser network
entries were loopback assets and the bundle blob, with no external requests.

**Limit:** Battery readings, watts and app name were fixtures. The managed
backend did not record a real Frame battery sample here. Real long-term
history, foreground-app attribution, panel use on Frame, worn visibility and
physical-controller interaction remain unverified. Battery Tracker stays
**partial** in the compatibility catalog.
