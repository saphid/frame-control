# DeckyParty after the TabMaster main update, 31 October 2026

Source `713e1692c48e6f89663c44786439e54141861af5` normally merges main
`1ac29413186fb29d5844ee9ad1c5c6fd36eeac27` into PR #518, preserving its
DeckyParty IPC shutdown repair. No history was rewritten. The earlier green
hosted checks belong to the previous head and do not qualify this refresh.

The source audit preserves main's other 36 runtime dispatch bodies, including
TabMaster's repaired backup restore, and the prior DeckyParty dispatch body.
The shared IPC adapter, console helper and published archive inventory remain
unchanged. All 116 catalog status/install policies and the other 115 complete
catalog rows match current main. DeckyParty remains **partial**.

Published Decky 3.3.0 AMD64 was exercised with isolated private files. The
repaired DeckyParty case made 15 RPCs, verified authenticated file operations
and authentication refusals, and completed three closed-peer reloads in
0.397, 0.367 and 0.367 seconds. Its unchanged original unload hook reaped the
owned server each time. The previous-managed negative made eight RPCs,
reproduced a forced reload after 5.273 seconds and retained the owned server
until fixture cleanup. Both final parent-only loader stops exited zero;
unrelated children survived. Installed backend/adapter hashes and every
unchanged archive member were independently checked against the pinned ZIP.

TabMaster's repaired and original-source control cases made 47 and 48 RPCs.
The repair restored a valid private backup; the original published source
refused it. Both refused malformed/non-object backups and preserved the
private backup, per-user values, sharing filters and restart persistence.
Both performed two parent-only stops with exact owned-process cleanup.

The 80 installer/compatibility tests and four IPC-adapter tests passed without
skips. The full server suite passed 1,943 tests in 245.300 seconds with 16
skips; all 18 website tests passed without skips. One production HTTP/SSH
installer method passed across 37 pinned
fixtures, including both DeckyParty and TabMaster receipts, installed bytes
and removal. All owned installer containers, volumes, networks and image tags
were removed and their absence checked. This installer method does not execute
the official backends or constitute the full e2e suite.

[Structured audit](framey-deckyparty-main-refresh-2026-10-31.json) records the
full server/website results and all 16 native source fingerprints.
[Raw evidence](framey-deckyparty-main-refresh-2026-10-31-raw.json.gz) retains
the verifier, native reports/consoles, test logs and installer cleanup records.
Native container/image cleanup is bound to the frozen runner; the reported
native process cleanup and separate installer absence checks are audited.

DeckyParty retains offline IP-discovery errors; TabMaster retains the expected
malformed-JSON diagnostic. There is no global clean or error-free runtime
claim. The full native matrix was not repeated locally. Fresh exact-head
hosted CI/e2e, native AMD64/ARM64, ownership, PC, every triggered package mode
and exact-current-main gates remain required. No LAN/HTTPS, browser/panel,
Steam CEF, real Frame, wearer/controller or release proof was obtained. No
headset or hourly schedule was touched.
