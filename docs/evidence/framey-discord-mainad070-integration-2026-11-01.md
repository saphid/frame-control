# Discord Status with ScreenSaver main — 2026-11-01

Implementation `b96c5a3ae3550b7470d4aad45bc79ccaf07089eb` normally merges prior #536 head `677f506838fea623d992526ba9f7e2aafff9b53e` and main
`ad070b731386dfbc2c8ed24b901b0b5edaeacbf2`. Five conflicted paths/seven hunks retain both exact archive repairs
and native cases. Whole installer/APPLY/checker AST outside Discord and
runner/pin/inventory/doc-generator AST outside its additions match main.
All **36 prior native cases**, **116 archive pins/classifications/policies**
and **115 other complete catalog rows** remain. **1,742 other main Git objects**
are unchanged, including main's current evidence and mandatory CI/package/
ownership sources. Discord helper/probe/tests/archive bytes are unchanged.
The exact Discord Status 1.5.0 ZIP remains
`00a45dd919abb6e050685e1e408ce8023b9c4a09d6e91ba528d50aed2a63bf45`.

## Fresh combined-source verification

- **127 focused tests / zero skips** across Discord lifecycle, installer
  transactions, compatibility, native inventory, ScreenSaver, shared IPC and
  official archives. Generated docs and diff checks against main pass.
- Published Decky **3.3.0 native AMD64**, isolated from network, devices, real
  accounts and user sessions: **14 Discord RPCs**, six private Unix connections
  and **18 independently decoded raw protocol frames**. Original handshake,
  activity, clear and failed-handshake retry payloads, replacement, protocol
  CLOSE before client EOF, two strict parent-only stops, actual IPC EOF,
  restart discovery and unrelated sibling preservation pass. Stop times are
  **[0.265, 0.225] seconds**. Installed backend/adapters, API 1 discovery,
  exact RPC sequence, full console hashes and owned process identities are
  independently checked. The added audit's initial discovery assertion used
  legacy load_type 0; the exact API 1 fixture uses 1. That oracle was corrected
  without a runtime change or test rerun.
- Same-source ScreenSaver: **31 RPCs / 14 independent dbus-python calls**
  against the plugin's unchanged vendored dbus-next. Existing service-name
  ownership is preserved without delayed queueing, all three inhibit APIs
  work privately, a disconnected client releases its inhibitor, settings
  survive restart, and two strict parent-only stops including real IPC EOF
  pass. Unrelated process, marker and bus owner remain intact. Actual suspend
  inhibition and official UI remain unverified.
- Both native reports bind the same **33 source hashes** to this implementation.
  Generic recorder clean-shutdown flags remain false; the separately audited
  Discord and ScreenSaver stop records supply scoped clean-stop evidence.
- Full fake-Frame e2e: **53 tests / zero skips**, **409.935 seconds**, all **116
  exact catalog archives**, **69 install/removes / 47 expected refusals**.
  Discord and ScreenSaver managed HTTP/SSH install, receipts, frontend transport
  and removal pass. Official backend execution is stubbed in this suite;
  real private backend behavior is covered by the native cases above. Owned
  Compose containers, volumes and networks are gone. Socket ResourceWarnings
  remain in the retained log.

## Prior evidence and remaining gates

Exact main `ad070b731386dfbc2c8ed24b901b0b5edaeacbf2` has separately audited hosted AMD64 and ARM64 ScreenSaver
evidence from [workflow 41289127932](https://github.com/saphid/frame-control/actions/runs/41289127932): 31 RPCs,
14 independent D-Bus calls and two strict stops per architecture. ZIP digests,
successful job steps, exact logged checkout and all 31 source hashes match.
The raw packet includes the targeted case records, attestations and audits;
not all 55 native producer cases are independently behavior-audited. These
results qualify only that main source, not the new Discord integration.

Prior `677f506838fea623d992526ba9f7e2aafff9b53e` has a separately audited hosted ARM64 Discord record with
14 RPCs, six connections and 18 raw frames (artifact 13075612841). Its evidence
is attributed to that source; fresh hosted ARM64 is required for this integrated
implementation. Not every producer case is independently behavior-audited.
At collection, **3 of four** prior-head signed-package modes
passed independent audits with **160 distinct sources /
1353 hash bindings**. Remaining modes:
`syncthing-flatpak-package-ubuntu-latest`. These package results do not
qualify this implementation. A live prior-head package job is preserved before
publishing a replacement head.

Exact final-head full CI/e2e/native AMD64 and ARM64/ownership/every triggered
package gate remain mandatory, along with exact current-main green, mergeability
and unresolved-feedback review. No merge or release is qualified by this packet.
Discord remains partial: original blocking receive/framing and Flatpak path
assumptions are unchanged. Actual Discord presence/account, Steam callbacks,
shortcut/artwork UI, browser/backend integration, Steam CEF, real Frame and
wearer/controller usability remain unverified. No headset, schedule, security
setting or pre-existing user data was touched. Syncthing installation stays
disabled. Store130 remains the separately documented 1.0.1 snapshot; GitHub
Prefix Manager1.0.2 remains a separate exact release asset.

[Summary](framey-discord-mainad070-integration-2026-11-01.json) · [Raw observations, logs and verifiers](framey-discord-mainad070-integration-2026-11-01-raw.json.gz).
