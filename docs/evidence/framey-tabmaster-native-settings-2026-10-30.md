# TabMaster private native settings fixture

TabMaster 2.15.1 had an earlier isolated AMD64 browser/read check, but no reproducible native CI case for its settings or restart behavior. This adds its exact published archive and an unmodified-backend case to the existing AMD64/ARM64 Decky 3.3.0 workflow. It changes no production adapter, install policy or plugin source. TabMaster remains **partial**.

The archive's SHA-256 is `e08333859a32b0c177b8e9a7959c5eeeafe38f946578f7f1d161c721f0e05da5` (5,712,641 bytes). The pinned CDN bytes match the catalog. The live store API returned HTTP 403 during this work, so this is not a fresh full-store metadata audit.

A local **AMD64-only** published Decky replay at source `86fb3b8c1185315f970b13d1e45c4457961ee7d9` passed 40 actual API1 RPCs. It checks the actual fixture user's Desktop path, empty defaults, false values, separate users' tabs/profiles/friends/game lists, global tags, shared-tab visibility filtering, private JSON disk readback and persistence across a loader restart. Both owned loader exits returned zero in about 0.214 seconds; the fixture checks captured PID/start-time identities are gone. All seven source fingerprints, pinned loader, exact archive/backend bytes and returned RPC records were independently audited in the adjacent [JSON evidence](framey-tabmaster-native-settings-2026-10-30.json). Disk and process-absence assertions remain source-bound observations, without a retained container image or complete process snapshot.

The complete private loader console is retained. It has one `Expecting value: line 1 column 1 (char 0)` diagnostic during shutdown; its cause is **not proven** and an error-free console is **not claimed**. Both startup/shutdown sequences, exit codes and identity checks pass. There is no shutdown-error/cancellation traceback or bad-file-descriptor message in the successful replay. This is not a real systemd service or release smoke test.

The first local replay failed at the first stop: the fixture sent SIGTERM to the whole owned process group, producing a nonzero parent exit and signal-wakeup errors. The revised fixture signals only the loader parent, matching the managed service's `KillMode=mixed` signal policy, and verifies descendant identity reaping. A second replay passed that exit/reaping check but failed a broad JSON-diagnostic assertion. The final fixture retains that diagnostic and full console instead of claiming all logs are clean. The adjacent audit preserves both failed log hashes and their distinct limits.

ARM64 and fresh exact-PR CI still need to pass. This case does not connect the earlier browser to this backend or verify Steam library-tab editing, library/MobX patches, backups/restores, real Steam CEF, a managed Frame installation, wearer-visible UI or physical controllers. No headset was contacted and no user's data was read or changed.


## Current main refresh, 2026-10-31

Main `51841728090a45f9f452b4cd4ccf93f4caf8df14` was merged normally. Frozen source
`a6a32451af03d9f0079251aebbcd9fdf82e0d716` retains all 31 main probe bodies and
the original TabMaster probe, main's exact store/keyboard/IPC/ownership sources,
all 116 catalog policies and the other 115 complete records. Additive inventory
conflicts retain TabMaster, Ludusavi and Deck Progress. An initial local merge
preparation failure was corrected before testing or pushing; it is recorded in
[the refresh audit](framey-tabmaster-main5184172-refresh-2026-10-31.json).

The refreshed source passed 105 focused host tests and local native AMD64's
40 literal TabMaster RPCs, private settings and two parent-only zero-exit stops.
All twelve source fingerprints, original backend/archive bytes, full console
hashes and exact process-reaping assertions were independently checked. The
one shutdown JSON diagnostic remains unattributed. Owned native containers and
image tags were removed. Subsequent commits add evidence only.

The full refreshed native matrix is 40 probes / 34 archive pins / 12 source
fingerprints; this targeted run does not qualify that full matrix. Final-head
hosted CI/e2e/native AMD64/ARM64 and every package gate remain required. No real
Frame, browser/backend integration, backup/restore or Steam editing proof is
added by this settings-only PR; the separate stacked #501 owns the restore fix.
