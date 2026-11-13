# Shared standalone Toggle contract — 2026-10-27

Framey previously exported `DFL.Toggle` as `ToggleField`. Official standalone
toggles pass `value`, while ToggleField takes `checked`. A saved true setting
therefore appeared unchecked, and clicking it could send true again instead of
turning it off. Toggle now renders a standalone controlled checkbox from
`value`; ToggleField retains its `checked` contract. Both emit booleans and keep
disabled controls inert. No official archive or manifest is rewritten.

Nine exact catalog archives use this standalone contract: CSS Loader (7),
Pause Games (13), AutoFlatpaks (32), DeckyFileServer (60), Syncthing (64),
Decky LSFG-VK (113), Muon (116), Launch Options (126), and ShadowDeck (129).
These are affected API consumers, **not nine verified working plugins**.
Their existing root, native, Steam UI and runtime blockers still apply.
The catalog records this repair without promoting any status.

## Verification

- The Node regression fails against the old alias: true renders false. It
  passes with the fix and checks true/false callbacks, disabled behavior and
  the unchanged ToggleField contract.
- The pinned, unmodified Pause Games 1.0.3 frontend component renders both
  persisted exclusion-list states and dispatches only its expected add/remove
  settings callbacks. This VM fixture does not run effects or process actions.
- Local Chromium, React 18.3.1 and the production host in an opaque sandboxed
  iframe pass eight DOM checks: saved true, standalone shape, false/true native
  clicks and rerenders, external false/true updates, disabled input, and
  ToggleField. This is a control fixture, not nine end-to-end plugin tests.
- Actual published Decky 3.3.0 on native amd64 discovers the exact Pause Games
  archive and uses public API1 instance RPC to save/read true/false settings,
  add/remove a synthetic exclusion and independently read its private settings
  file. This is a permanent runtime probe alongside existing backend shims;
  all eight probes, including historical negative cases, pass. Hosted CI also
  runs this gate on native ARM64; local ARM64 evidence below is from the Frame.
- Under the shared headset lock, a bounded, removable private Decky 3.3.0 ARM64
  user service repeats discovery and those safe settings operations through
  the normal Steam CEF DeckyBackend bridge. The private file readback matches.
  The harness never requests pause/resume/kill or suspend operations. Steam's
  Decky frontend also populated its normal default setting keys during this
  run; no running-game behavior is claimed.
- Fake-Frame audit: all 116 archives attempted, 61 installed/removed and 55
  blocked by existing policy. Full Python suite: 1,659 tests, 16 skipped, OK.

The exact Pause Games archive SHA-256 is
`4aefdfb0ef25dea9c6d9fd037731c8b99ee8a1be966c2f7d5b0602112ef29f62`.
The official store refresh still contains 116 entries; all pinned IDs, versions
and digests are unchanged.
[Structured results](framey-toggle-2026-10-27.json) include scoped readbacks and
the nine version/digest pairs.

## Probe retries and cleanup

The first hardware adapter connected directly to Decky's single WebSocket and
reused a request ID also used by Steam CEF; it received an unrelated cached
reply. A second adapter retained a CEF connection across Decky's startup reload
and disconnected. Neither is a successful plugin verification. Both private
services and files were removed. The successful adapter waits for startup and
reattaches CEF during discovery, then serializes settings calls through the
normal DeckyBackend bridge.

All private services, bases and uploaded archives were removed, and the shared
lock was released. An independent locked audit confirms no matching unit is
loaded and no private base, unit file or upload remains. Original managed Decky
and panel states were preserved. Battery stayed 100 → 100 during the successful
run; no power setting changed.

No plugin gains a works claim. Real process control, other importer backends,
physical input and worn VR remain unverified. The original independent branch
had **6 works / 50 partial / 49 broken / 11 N/A**. After merging main's landed
DeckyFileServer ARM64 support, current totals are **6 works / 51 partial /
48 broken / 11 N/A**. Its managed-native receipt guard and both runtime probes
are preserved; its former Toggle display limitation is removed from the current
catalog reason. The initial verification counts above describe the original
branch; combined validation is recorded below.

Combined merge validation against main `b963937`: full Python suite passes
1,663 tests with 16 skips; all ten actual published Decky 3.3.0 native amd64
probes pass, including Pause Games settings and DeckyFileServer positive/negative
cases. Generated documentation matches the merged catalog. No hardware rerun
was needed for these fixture/catalog conflicts.
