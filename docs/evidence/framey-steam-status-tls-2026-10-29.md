# Steam Status managed TLS verification, 29 October 2026

The exact official Steam Status 1.2.3 archive (store ID 123, SHA-256
`9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e`)
disables both hostname and certificate checks for its public Steam CM-list and
speed-test HTTPS requests. Its `main.py` SHA-256 is
`3b0d2daa28f9f59b81bd0e7e11528e5b3522bd3287dc6bcd1ad8f7a92086858a`.
The managed install removes only those two pairs of assignments for this exact
archive, folder and source digest. Both calls retain Python's
`ssl.create_default_context()`.

The focused transaction test installed and removed the pinned archive, checked
the managed receipt and source, then executed both extracted diagnostic helper
functions with `urlopen` blocked before network access. Both contexts retained
`check_hostname=True` and `verify_mode=CERT_REQUIRED`. The old published
helpers would fail that assertion. A compatibility test confirms an older
managed receipt calls for Update or reinstall; the fixed receipt does not.

Published Decky 3.3.0 x86_64, digest
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`,
discovered the adapted plugin in an unprivileged, networkless disposable
container and returned its private default settings through the public
`get_settings` RPC. The runtime probe checked both installed contexts retain
verification. It did not call either public network diagnostic. The runtime
report was saved locally as `/tmp/framey-steam-status-runtime.json`; the test
container and owned image were removed.

The full local Python suite passed 1,739 tests with 16 existing skips. Focused
managed transaction, digest-scoped compatibility, runtime coverage and
generated-documentation checks passed. The earlier restricted-sandbox attempt
could not bind loopback server test ports; the full passing run used local
socket access.

This changes no current installed copy until the user updates it. Steam Status
remains **partial**: live public diagnostics, settings persistence, real Frame
use of this adapted backend, worn VR and controller input are unverified.
