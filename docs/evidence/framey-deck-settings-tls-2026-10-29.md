# Deck Settings verified upload TLS, 29 October 2026

The exact official Deck Settings 1.2.6 archive (store ID 93, SHA-256
`23c2a933a6883e2622f0184c33a76ce4a4e88c0a7dcd730f9bab71b8c3702132`)
contains an image-upload helper that sends an `Authorization: Bearer` header
over HTTPS after setting `check_hostname = False` and `verify_mode = CERT_NONE`.
That would expose an upload token and image contents to a server with an
untrusted certificate. The managed installer now removes those two lines only
for this archive digest, folder and exact `main.py` hash. It retains Python's
default certificate and hostname verification. Older managed copies need an
explicit Update or reinstall to receive the repair.

The pinned official archive passed managed install/remove and receipt checks.
A focused host test loaded the installed helper and confirmed its SSL context
keeps hostname checks and `CERT_REQUIRED`. In a network-, device- and
session-isolated container, published Decky 3.3.0 x86_64 discovered the
managed plugin and returned read-only vendor and eMMC classification RPCs.
The installed upload helper rejected a private self-signed loopback HTTPS
endpoint before sending its fixture bearer header or body. No external
request, account token, user image or headset was involved. The test runner
removed its disposable container and plugin installation.

Deck Settings remains **partial**: its game picker and search modal have only
local Chromium coverage; remote reports, verified public uploads, settings
changes, actual ARM64 backend on Frame, worn VR and physical controllers
remain unverified. The hosted native ARM64 test is a separate gate and does
not prove the real Frame session.
