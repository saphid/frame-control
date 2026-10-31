# Integrated private Terminal browser candidate, 2026-10-30

A local AMD64 VM replay at `41dcaba4121e965bfdaeeb80196d59478f8496db`
passed using the isolated native candidate from #490 and event-name handling
from #488. These source changes remain under separate CI review. This local
branch adds a repeatable browser fixture; it is not a production adapter.

The audit compared 155 committed source fingerprints, pinned loader, official
Terminal archive and frontend, private dependency hashes, and the complete
243,280-byte checksummed virtio result packet. The loader exercised private
PTY input/output, resize, explicit remove, real reload shell cleanup and config
persistence before the browser opened the exact published Terminal frontend.
The opaque child made 15 actual Decky RPC calls and received four native output
events through a private HTTP/event bridge. Synthetic paste contained only the
fixed private command in the fixture.

All three captures were inspected: [terminal](framey-terminal-integrated-terminal-2026-10-30.png),
[output](framey-terminal-integrated-output-2026-10-30.png),
[removed](framey-terminal-integrated-removed-2026-10-30.png).
The output shows `42 129`, `framey-browser-output`, and a shell prompt;
the removed view has an empty Active Terminals list. The private marker file
and exact output lines independently confirm execution, beyond command echo.
The audit confirmed renderer sandboxing and browser/bridge/event socket,
user-manager and QEMU cleanup with no bridge failures.

This verifies the local desktop fixture. Native ARM64, a production adapter,
production HTTP parent, actual Steam CEF, managed installation, Frame display
pixels and physical controller/wearer usability remain unverified. No host
home, host bus, network NIC, headset access or schedule changes were used.
