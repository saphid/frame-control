# Decky Notifications private backend check, 29 October 2026

The exact official Decky Notifications 1.0.1 ZIP (store ID 79, SHA-256
`3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312`)
is pinned in `tests/fixtures/framey-official/79.zip`. Static inspection found
that its backend writes `/tmp/notifications.log` and, if `openssl` certificate
creation fails, logs every environment variable. The managed install for this
exact digest removes the shared log filename and environment enumeration.
The original `main.py` and `py_modules/connector/crypto.py` are independently
SHA-256 checked before alteration. Older managed copies need Update or
reinstall to receive the change.

`python3 scripts/framey-test-decky-runtime.py --case 79 --output
/tmp/framey-notifications-native-20261029.json` passed locally on native
x86_64 with the published Decky 3.3.0 loader. The disposable container used
`--network none`, no device mounts, dropped capabilities, a read-only root,
private tmpfs home/runtime directories and a test-only certificate. The plugin
was discovered; its public legacy RPCs returned a private certificate
fingerprint and an empty device list. A synthetic notification inserted into
the container's private SQLite database was returned by `notification_list`,
removed by `notifications_clear`, and remained absent after Decky restart.
The fingerprint persisted across the restart. The managed source contained
neither the shared log filename nor the environment dump; the shared log file
was absent. The test container and image were removed by the runner.

No phone or account was paired, no external packet was sent, and no actual
notification arrived. This does not verify LAN discovery, TLS pairing,
notification delivery, panel display, the real Frame ARM64 backend or worn VR.
The status remains **partial**.
