# Framey detached Steam library context — 2026-10-26

Framey now reads a bounded library snapshot before importing official frontends
that reference `appStore`, `collectionStore` or `m_CurrentUser`. It supplies app
IDs/names/types/game IDs, sorting/playtime scalars, the actual all-games
collection and the current public Steam ID. It does not copy credentials,
balances, account names, filesystem paths or executable Steam objects.

The projection is a fixed, parameterless `GetLibrarySnapshot` read through the
existing installed-store-plugin boundary. The parent checks the iframe source,
session, method and empty argument list. The host validates rows before exposing
detached Maps and lookup methods. Plugin patches remain local to that iframe.
Missing or invalid data leaves the globals unavailable and logs a clear warning;
there is no invented account or empty-library fallback. Reopening the panel
refreshes the snapshot. Live MobX observations, account-switch notifications and
running-game events are outside this change.

Library-sized backend arguments now have a 256 KiB UTF-8 JSON budget. The old
8 KiB ceiling rejected normal app-name maps. Payloads travel as quoted literals
on SSH stdin, avoiding operating-system limits on a single command argument.
Store receipt ownership, method validation and legacy keyword envelopes still
apply. The library read has a separate 2 MiB / 10,000-app limit; other Steam
reads retain their 256 KiB response limit.

## Observations

| Plugin | Verified behavior | Remaining limit |
| --- | --- | --- |
| Steamback 1.0.0-1 | Panel opens; account setup and empty save-list reads succeed through actual Decky 3.3.0 amd64 | Private container had no Steam saves. ARM64 backend, backup/restore and automatic hooks unverified. Partial. |
| PlayTime 3.2.5 | Actual backend selects the user, returns empty statistics; statistics panel and routed settings/tabs render | No sessions were created. ARM64 backend, existing databases, live observations and automatic recording unverified. Partial. |
| Deck Settings 1.2.6 | Installed game picker renders the real Frame folder/name snapshot; search modal opens | Remote reports/proxy fetch, settings changes and ARM64 backend unverified. Partial. |
| Shotty 0.1.0 | Library-based initializer now completes | Exact backend fails importing `click.get_app_dir`: `ModuleNotFoundError: No module named 'click'`. Archive does not bundle it. Broken. |
| Discord Status 1.5.0 | Detached overview lookups available | Live running-app observations and artwork helpers remain absent; Discord activity unverified. Broken. |

Exact plugin versions/digests, runtime digest, scoped calls and counts are in the
[redacted observations](framey-library-context-2026-10-26.json). The canonical
table/store labels use the same digest-scoped JSON. None of these plugins is
promoted to **works** by this pass.

## Verification boundaries

- **Real Frame SSH:** atomic `/tmp/frame-test.lock` acquisition for every probe,
  matching-owner release in `finally`. Frame OS 0.5.6 ARM64 Steam CEF returned
  1,106 apps and 895 game IDs; no missing collection members or invalid rows.
  The compact library-only response was 88,451 bytes. Current-user field shape
  was separately inspected. Values remain private; only aggregate counts are
  published. No wake, power/service changes or device artifacts were needed.
- **Local Chromium:** production `headset.html`, current host, opaque iframe and
  unmodified digest-checked official frontends. Library/user and install-folder
  data were detached snapshots read from the Frame, replayed locally. This is
  not a deployed headset HTTP or worn-VR test.
- **Actual local backends:** published Decky 3.3.0 amd64 executable, private
  unprivileged container, network disabled, capabilities dropped, no devices,
  host home, saves or Steam files mounted. Only account setup within private
  plugin data and read methods were allowed. Backup, restore, aggregation,
  screenshot rescue and game actions were denied. Shotty's import failure was
  observed from the runtime log before invoking screenshot methods.
- **Catalog regression:** 116 exact frontends attempted, 101 initializer-ready
  and 15 failed, compared with 98 ready before this theme. Steamback, Shotty and
  PlayTime gained initializer readiness; no previous ready state regressed.
  Backend/network calls stayed denied in this sweep. Readiness alone does not
  establish useful operation.
- **Fake Frame:** 116 archive/transport cases; 60 install/remove cycles and 56
  expected blockers. Official backend execution was stubbed. Its private
  Compose containers, network and volumes were removed.

The browser audit accepts `--library-snapshot /private/library.json` to reproduce
the detached replay. This flag does not convert the audit into live Steam or
backend evidence. Never commit personal library snapshots or account values.

No worn-VR, physical controller, keyboard, automatic recording or backup claim
is made. Further device backend checks still require the shared hardware lock.
