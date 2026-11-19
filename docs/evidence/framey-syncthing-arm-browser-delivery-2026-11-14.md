# ARM64 signed-package browser delivery, 14 November 2026

The exact #483 head `a27a15caf43e3d47ab3438a4edb35b8409f9c774` failed
native ARM64 browser HTTP at run 43560299960/job 132342255670. The retained
artifact ZIP digest and all 137 input hashes match that head. Package install,
sync and migration cleanup passed before browser startup. The parent receiver
was installed, its iframe URL assigned and document state interactive, but
iframe-load/cache-request/seed/ready counters all remained zero. No browser
stage or RPC passed. Chromium stayed alive; browser, bridge and VM cleanup
were retained. This does not establish why the child failed to start.

A normal merge now includes main `37fec5637edd83111ecbb444e98e6caeaab93876`.
The test serves its existing child HTML as a separate loopback HTTP document,
as the production parent does, rather than embedding the whole child in a
base64 data URL. Measured on the same current candidate panel, parent delivery
falls from 778,745 bytes to 2,094 bytes; child delivery is 582,476 bytes. The
child sandbox is still exactly `allow-scripts`, with no same-origin grant;
its existing CSP still refuses network connections. The parent receiver is
installed before assigning `/panel#fixture`. The actual Decky bridge and DOM
probe are byte-identical to the failed head; every shipped UI file matches main.
The 60-second startup deadline and all package/ownership/control gates stay.

All 85 focused readiness, browser lifecycle, HTTP gateway, signed-package and
timeout tests passed without skips. Isolated real Chromium on local x86_64
passed normal startup, a seven-second parent-stream pause and a 2 MiB child.
Each case verified the cache handshake, an opaque `null` child origin, refusal
to read the parent's DOM, CSP denial before a child network request reached
the server, and CDP target metadata below 65,537 bytes with bounded URLs.
These are fixture checks, not signed-package/backend or ARM64 runtime passes.
The native report now retains hashes and bounded request sizes for both HTML
resources, so a future failure can distinguish assignment from HTTP delivery.

The adjacent compressed file preserves the earlier failed result and browser
progress plus original artifact metadata; the JSON binds its digest and current
source inputs. Fresh exact-head CI, including native ARM64 browser HTTP, must
pass. The historical ARM64 shutdown/migration cause remains unresolved.
Syncthing managed installation stays disabled. Real Steam CEF, Frame rendering,
worn visibility, controllers, scrolling and VR keyboard remain unverified.
