# Changelog

## Unreleased

- Use gamescope's input for the keyboard and trackpad, following the focused
  headset panel without installing an input service. Start KDE Connect only for
  accents and emoji, keeping queued text ordered and cancelling it on headset
  switches. Retain intended-headset checks before starting either control and
  prevent Unicode helper startup from deadlocking with a headset switch.
- Keep accepted keyboard text when the Unicode queue is full: reject new batches
  before sending their clicks or keys, and count in-flight text toward the limit.
  Retain unsent text after helper failures/timeouts, report the error and resume
  it with Try again. Clean up failed workers without touching a new headset's queue.
  [Current verification and device limits](docs/evidence/pad-gamescope-2026-10-24.md).

- Keep media playback running when SteamVR refuses the optional theatre dark
  surround, including a retry after standby. Log the refusal and play without
  the surround. Overlay teardown attempts every owned handle and always calls
  OpenVR shutdown even if a handle fails to close.

- Check the desktop server's single-instance lock before starting background
  downloads, so a second server exits cleanly with the existing "already
  running" message.

- Recheck saved spatial layouts on SteamOS 0.5.6 / SteamVR 2.18.2 (issue #31).
  Read-only probes expose some panel geometry, but safe restoration of
  Steam/gamescope docking and positions remains unverified. Record exact API
  results and a reproducible probe; saved layouts remain unavailable.

- Record packaged v0.4.17 Desktop Capture succeeding on a mapped nested KDE
  compositor on a real Frame with SteamOS 0.5.6. Headset overlay visibility was
  not established; this is evidence, not a new fix or resolution of issue #73.

- Correct the Return to Game Mode help text: Frame Control selects the switch
  supported by the headset's SteamOS build, including `steamosctl` on current
  Frames. The button's behavior is unchanged.

- Distinguish an unreadable gamescope panel list from a confirmed empty list in
  Desktop Capture and Control (issue #73). Failed discovery now asks users to
  check SteamVR and report the exact message and SteamOS version, rather than
  claiming no panel is open. This does not establish a new capture fix.

- Add an opt-in desktop low-battery alert without starting a family session.
  Existing status reads confirm low charge and drain; recovery hysteresis and a
  ten-minute cooldown limit repeat alerts. Off on page open/headset switch;
  pauses with hidden-page status refreshes. No extra polling or headset changes.

- Clarify first-time desktop downloads, installation and opening on the website
  and README, including CPU choices, unsigned-app warnings, pairing fallback
  and the source-only iOS build. Keep section navigation available on mobile.

- Treat headset aliases and other CSV metadata as plain text in power and heat
  exports, so spreadsheet formula prefixes cannot run when a report is opened.

- Add desktop Tools → Power & heat report: bounded read-only one/five-minute
  observations with progress, stop and HTML/JSON/CSV downloads. Received samples
  survive stop, disconnect and headset switch, labeled incomplete and tied to the
  original headset. Shared sampler/report modules ship with the app; no power or
  thermal controls are added. Download before replacing a report or quitting.

- Fix Return to Game Mode misidentifying full Plasma Desktop Mode when its VR
  overlay also runs gamescope (issue #142). Session targets now determine the
  mode; conflicting or incomplete evidence stays unknown. Use SteamOS's
  `steamosctl` switch when available, with older selector commands retained.

- Export read-only power and heat observations to an offline accessible HTML
  report with JSON/CSV downloads. `--html FILE` limits sessions to ten minutes;
  Ctrl+C saves received samples with an explicit incomplete state. Units,
  unknown counts and sources remain visible; no headset controls are added.

- Add a guarded `frame-doctor.sh --plan` with read-only, evidence-specific next
  steps and explicit local baseline reports for before/after diagnostics (issue
  #34). Restart risk blocks plans/comparisons; no automatic repairs, password
  changes or headset security changes are performed.

- Recover a tagged release upload when GitHub temporarily displays its draft
  as `untagged-…` after an edit, without creating a duplicate draft or
  silently retrying unrelated upload failures.

- Import standalone APK/OBB backups from XAPK/APKS/APKM archives through the
  existing preview and game-data setup flow. Unsafe archives, split sets and
  Android/data restores are refused with guidance. This does not establish RE4
  compatibility or diagnose its reported failure (issue #102).

- Add `scripts/frame-power-sample.sh`, a bounded read-only SSH sampler for
  battery, CPU, named temperatures, fan and available power rails (issue #52).
  JSON samples/summaries and CSV exports retain explicit unavailable states;
  active smoke-test locks stop measurement. No power settings are changed.

- Show saved Android compatibility reports on store search cards and app details.
  Reports refresh in the background, so a stalled database or credential lookup
  cannot delay search. Warnings allow installation; build compatibility blockers
  still apply. Public copies use this computer's reports, not private shared ratings.

- Fix two cases where optional diagnostic logs could retain part of a headset
  display name or an SSH host name, while preserving existing privacy redaction
  (issue #81).

- Keep the full host-key recovery explanation readable in Devices, including
  long addresses, and remove doubled punctuation from the connection tooltip
  (issue #87). Refresh stays within the header and switching headsets selects
  the new headset's details.

- Fix experimental PC screen capture on Windows builds whose streaming libraries
  lack Windows Graphics Capture. Whole screens use Desktop Duplication; individual
  windows are hidden with an explanation instead of failing when shown. A Windows
  VM streamed a real desktop to the Frame; physical input remains unverified.

- Add read-only battery health in Tools: charging state, temperature, cycle count,
  and available capacity with explicit unknown states. The parser was checked
  on a real Frame; the connected desktop UI was tested with synthetic readings.

- Add Tools → Game storage: read-only headset filesystem capacity and Steam
  library/game install-size breakdown, with unknown sizes, partial inventories
  and permission/missing-drive states. Includes instructions for Steam's own
  Move UI; Frame Control does not move or delete game files. The read-only
  parser was checked on a real Frame; the connected UI and game moves were not.

- Add `scripts/frame-doctor.sh` for read-only setup and pairing diagnostics,
  with verified SSH identity, private summaries and actionable next steps
  (issue #34). Connection steps links to the diagnostic guide. Repairs remain
  manual; restart-loop evidence stops deeper diagnostics. The real Frame
  verified the SSH connection and safety stop; deeper checks were skipped.
- Fixed headset smoke cleanup reporting success while a smoke-title process
  could remain running after its files were removed. Cleanup now stops and
  rechecks processes tied to exact reserved test-title paths, uses PID handles
  for safe TERM/KILL escalation, and records stopped PIDs. Unrelated titles and
  shared Wine services are left alone. Verified with local Linux process
  regressions and a 13/13 real Frame smoke run that stopped five test-owned
  Proton process PIDs before removing the Windows test title.
