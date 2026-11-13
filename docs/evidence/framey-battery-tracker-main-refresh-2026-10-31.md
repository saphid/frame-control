# Battery Tracker after the TabMaster main update, 31 October 2026

Source `aa65c50cbd25ef191d167c36a4bc404fc4963453` normally merges main
`1ac29413186fb29d5844ee9ad1c5c6fd36eeac27` into PR #519, preserving its
Battery Tracker 0.2.0 pending-sample shutdown repair. No history was rewritten.
Historical green checks belong to the previous head and do not qualify this
refresh. Compatibility remains **partial**.

The other 36 runtime dispatch bodies, including main's TabMaster backup
restore, match current main. Battery Tracker's dispatch body matches its
previous head. The shared IPC adapter, console helper, archive inventory and
other 33 native cases are unchanged. All 116 catalog status/install policies
and the other 115 complete catalog rows are preserved.

Under isolated published Decky 3.3.0 AMD64, the repaired Battery Tracker made
39 RPCs and completed two parent-only loader stops in 0.215 seconds each.
Before the first stop the database was empty, with samples pending in memory;
afterward it held two rows. Restart read the saved samples, and the second
stop increased the database to three rows. Recorded descendants disappeared,
adopted children exited zero, and an unrelated sibling survived. The exact
previous managed source made 36 RPCs, required a forced plugin stop after
5.225 seconds and left the database empty. These are observed polling counts,
not fixed API-call requirements. The final SQLite snapshot from each case was
independently decoded, opened read-only, integrity-checked and compared with
the reported rows. Installed backend/adapter hashes and unchanged archive
members were checked against the digest-pinned archive.

TabMaster's repair and original-source control made 47 and 48 RPCs. The repair
restored a valid private backup; the published source refused it. Both refused
malformed/non-object backups, preserved private user values and sharing
filters, and retained restart persistence. Both completed two parent-only
loader stops with exact owned-process cleanup. The expected malformed-JSON
diagnostic remains in both logs; this is not an error-free console claim.

[Structured audit](framey-battery-tracker-main-refresh-2026-10-31.json) records
the full server suite (1,943 tests in 243.645 seconds, 16 skips), all 18
website tests (no skips), 16 native source fingerprints and the
37-fixture HTTP/SSH installer method. The installer verifies receipts,
installed bytes and removal for Battery Tracker and TabMaster; it does not
execute official backends or constitute the full e2e suite. Owned installer
containers, volumes, networks and image tags are removed and their absence
checked. Native container/image cleanup is bound to the frozen runner;
reported native process cleanup is audited separately.

[Raw evidence](framey-battery-tracker-main-refresh-2026-10-31-raw.json.gz)
retains the verifier, native reports/consoles, SQLite payloads, test logs and
installer cleanup records. The full native matrix was not repeated locally.
Fresh exact-head hosted CI/e2e, native AMD64/ARM64, ownership, PC, every
triggered package mode and exact-current-main gates remain required. No new
browser, real battery, long-term recording, Steam CEF, managed Frame,
wearer/controller or release proof was obtained. No headset or hourly
schedule was touched. Global clean plugin shutdown remains unverified.
