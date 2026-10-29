# RadiYo! 1.3 isolated backend check, 29 October 2026

The official Decky store archive for RadiYo! (ID 24) is 33,686 bytes with
SHA-256 `647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43`.
Its unmodified ZIP is pinned as `tests/fixtures/framey-official/24.zip` and
passes Frame Control's archive validation and fake Frame panel packaging.

`python3 scripts/framey-test-decky-runtime.py --case 24 --output /tmp/framey-radiyo-decky-runtime-20261029.json`
ran the published Decky 3.3.0 x86_64 loader, digest
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`,
in a disposable container with `--network none`, no host devices, dropped
capabilities and a private home. The real loader discovered the exact plugin
and dispatched its legacy `fetch` and `getRedirectUrl` RPCs. A server bound to
container loopback returned a fixed station marker: regular fetch returned it,
custom-station fetch omitted the body as upstream intends, and a redirect
resolved to the same fixture. The runner removed its container and image.

The previously recorded opaque-iframe browser audit showed frontend
initialization, but denied backend and network calls. This native probe adds
backend transport evidence only. No external radio station, HTTPS endpoint,
audio playback, real Frame service, VR visibility or controller was tested.
The published backend sets `check_hostname=False` and `CERT_NONE` for its
outbound HTTPS requests; the loopback HTTP test did not exercise that path.
RadiYo! remains **partial**. The compatibility count does not change.
