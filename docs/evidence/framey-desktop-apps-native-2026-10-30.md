# Desktop Apps native backend probe, 30 October 2026

The exact store-143 Desktop Apps 0.1.0 archive has SHA-256
`33fb674993c9b2bd119f0c6118c465e379f166ec1539c8183fcf7580f1d89577`.
The unchanged backend now has a case in the published Decky 3.3.0 runtime gate.
Its [local AMD64 report and source hashes](framey-desktop-apps-native-2026-10-30.json)
bind the executed fixture to `0c2a7b53757b91e4578872d3a95a6515e0260493`.

`python3 scripts/framey-test-decky-runtime.py --case 143 --output /tmp/desktop-apps.json`
passed in a disposable native AMD64 container. External network, host devices,
user home and session bus were unavailable. The managed installer accepted the
pinned archive without adaptation, and actual Decky discovered its API-v1
backend. RPCs scanned private desktop entries and verified XDG directory
precedence, nested entry IDs, Flatpak metadata, `%c`/`%k` expansion and removal
of unused field codes. Seven hidden, terminal, non-application, incomplete or
malformed entries were omitted. A launch canary was never executed.

Private favorite/hidden/last-opened settings agreed with the on-disk JSON and
survived a full loader restart. Temporary-shortcut bookkeeping deduplicated a
private numeric ID, retained it through restart, and removed it idempotently.
These are backend settings; no Steam shortcut was created, changed or removed.
The runner reaped its owned processes and removed its disposable container/image.

The first development run passed discovery and settings RPCs but failed an
incorrect fixture assumption that Decky's settings file wrapped its keys in
`state`. The pinned upstream SettingsManager writes keys directly. That
assertion was corrected; the failed log digest is retained in the JSON. No
production source or plugin archive was changed.

ARM64 CI, browser controls, discovery of actual installed Flatpaks, Steam
shortcut operations, application launch, the real Frame and worn/controller
usability remain unverified. Desktop Apps stays partial; this test does not
change the compatibility table or grant a release approval.
