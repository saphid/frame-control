# Steam Status private settings persistence, 30 October 2026

The exact official Steam Status 1.2.3 archive (store ID 123, SHA-256
`9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e`)
was installed with the digest-scoped TLS adaptation in published Decky 3.3.0.
The x86_64 loader SHA-256 is
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`;
the ARM64 loader SHA-256 is
`8ef5dcf36cbbbb6e97201a6baed5d79c4cc44ec27789fc9af1c5b6ae8f0b25b6`.
The backend ran in unprivileged, networkless disposable x86_64 and ARM64
containers, each with a private Decky base. The exact-head ARM64 CI job
[passed case 123](https://github.com/saphid/frame-control/actions/runs/40982405516/job/123825349970)
on commit `3c57ece579236a58d7a47846f39f8a04169fe994`.

The `get_settings` RPC returned the default `refresh_interval_seconds` value
of 120. The `set_setting` RPC changed it to 180; `get_setting` returned 180,
and an independent read of the private `settings.json` file found the same
value. After Decky stopped and restarted, plugin discovery and `get_setting`
again returned 180. The runtime report is local at
`/tmp/framey-steam-status-runtime-20261030.json`. The owned container and
image were removed.

The probe also checked that both managed public diagnostic TLS contexts retain
certificate verification. It did not execute the public CM-list or speed-test
downloads. Real Frame use of the adapted backend, live public diagnostics,
worn VR and controller input remain unverified.
Steam Status stays **partial**.
