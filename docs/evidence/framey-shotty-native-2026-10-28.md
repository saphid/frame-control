# Shotty native Decky backend check, 28 October 2026

The exact official Shotty 0.1.0 archive (store ID 53, SHA-256
`ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe`)
receives Frame Control's digest-scoped `shotty-click-app-dir` module during a
managed install. The [earlier isolated Python check](framey-shotty-python-2026-10-26.md)
copied one synthetic screenshot into a temporary `Pictures` folder.

The [main native Decky run](https://github.com/saphid/frame-control/actions/runs/40776292569)
on commit `dad5f78a02dd477a689689865cd4ef4205b87e22` passed Shotty's
`tests/decky-runtime/cases.json` case on both native amd64 and ARM64 runners.
The test used the digest-verified published Decky 3.3.0 loader and exact archive
in separate disposable, network and device isolated containers. It installed
the managed archive, checked the shim receipt and plugin discovery, then called
the legacy backend methods through Decky's real websocket RPC:

| Runner | Observed result |
| --- | --- |
| Ubuntu amd64 | `was_rescued` returned `false`; `aggregate_all(allapps=[])` returned `0` |
| Ubuntu ARM64 | `was_rescued` returned `false`; `aggregate_all(allapps=[])` returned `0` |

Both job logs report `PASS 53: discovery, backend import and empty screenshot
aggregation passed`. The containers were removed by the test runner. This
corrects the prior catalog statement that actual Decky ARM64 backend loading
was unverified. The empty RPCs do not exercise a real screenshot or the
continuous rescuer. The managed backend on a real Frame, live screenshot
notifications and copies, wearer-visible panel and physical controllers remain
unverified, so Shotty stays **partial**.
