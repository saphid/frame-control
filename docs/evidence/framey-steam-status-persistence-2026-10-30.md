# Steam Status private settings persistence, 30 October 2026

The exact official Steam Status 1.2.3 archive (store ID 123, SHA-256
`9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e`)
was installed with the digest-scoped TLS adaptation in published Decky 3.3.0
x86_64 (loader SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`).
The backend ran in an unprivileged, networkless disposable container with a
private Decky base.

The `get_settings` RPC returned the default `refresh_interval_seconds` value
of 120. The `set_setting` RPC changed it to 180; `get_setting` returned 180,
and an independent read of the private `settings.json` file found the same
value. After Decky stopped and restarted, plugin discovery and `get_setting`
again returned 180. The runtime report is local at
`/tmp/framey-steam-status-runtime-20261030.json`. The owned container and
image were removed.

The probe also checked that both managed public diagnostic TLS contexts retain
certificate verification. It did not execute the public CM-list or speed-test
downloads. ARM64 setting persistence, real Frame use of the adapted backend,
live public diagnostics, worn VR and controller input remain unverified.
Steam Status stays **partial**.
