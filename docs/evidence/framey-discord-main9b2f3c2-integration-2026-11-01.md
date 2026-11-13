# Discord lifecycle integration with Deck Shelves main

Combined implementation `c25c23b787ddb9ddf6c005fb0444208248fc552a` normally merges prior #536 head
`0dd017cc4d84f630faea3a8b9f70dc0dd07231c2` and main `9b2f3c2634a61767ebc52099f595229b2515d96f`.
Two adjacent installer conflict hunks were resolved by retaining both exact
archive-specific deliveries/repairs. Independent whole-module AST comparison
preserves main's installer and its embedded apply program outside the Discord
branch; it also preserves the complete main checker outside the scoped private
fixture/probe, plus runner, pins, inventory and generated-doc logic outside exact
Discord additions. All 34 main native cases, 116 archive pins/install/status/flags
and other 115 complete catalog rows remain intact. Prior Discord helper, private
probe, unit tests and archive are unchanged; only its compatibility note/shim
requirements differ. All **1717 other main file Git objects** are unchanged.

Fresh combined-source verification:

- **110 focused tests, zero skips**; generated-doc verification passes.
- Published Decky 3.3.0 native **AMD64**, networkless/device-free disposable
  runtime: **14 Discord RPCs**, **six** private Unix connections and **18** raw
  wire frames. Independent decoding checks original handshake/activity fields,
  clear, rejected-handshake retry, replacement, client close and EOF. Two strict
  parent-only stops and restart preserve the unrelated sibling, finish shutdown
  and reap owned identities with no forced plugin kills. Generic
  recorder shutdown flag remains false; scoped strict stops are separately
  audited. No real Discord server/account/socket was contacted.
- Deck Shelves: four managed RPCs, two strict clean parent-only stops and
  restart, settings/backup bytes and metadata preserved. The three-RPC original
  backend negative reproduces one forced plugin stop, as expected; it does not
  qualify compatibility. Both reports bind the same **29** runtime inputs.

Before integration, exact old head `0dd017cc4d84f630faea3a8b9f70dc0dd07231c2` finished all **19 checks/six
workflows** successfully. Its final native ARM64 signed-package artifact
**13072013168** completed normally; no live job was interrupted. All nine hosted
artifacts were authenticated against ZIP/member digests, successful exact-head
job steps and checkout logs. The completed old-head four-package audit verifies
**157 unique source paths / 1,389 hash bindings**, both native architectures,
signed app/runtime bundles, two-way sync, strict service stops, restart
persistence and preserving uninstall. Browser mode verifies 14 requests;
production-parent mode verifies 65 parent + 16 child requests (maximum 6.221s),
unchanged iframe/sandbox and no parent errors. These are prior-head candidate
package proofs, not a new release/tagged-installer or real Steam CEF proof.
Syncthing installation remains disabled.

The [original evidence](framey-discord-ipc-lifecycle-2026-11-01.md) and prior
hosted native/catalog/e2e evidence apply to earlier sources. Exact final-head
hosted full CI, both native architectures, catalog e2e and every triggered
package/ownership/installer gate, then exact green main, feedback and
mergeability remain required. This local packet does not qualify a merge or
release. An evidence-only final commit leaves all 29 tested runtime inputs intact.

Compatibility remains partial. Original blocking receive/framing and Flatpak
socket-path assumptions are not repaired. Real Discord account/activity,
Steam callbacks, shortcut/artwork UI, managed Frame and wearer/controller
usability remain unverified. No real hardware, schedules, PR #113, security
settings or pre-existing user data were changed. Store ID130 stays 1.0.1;
separate GitHub v1.0.2 is not a live-store claim.

[Summary](framey-discord-main9b2f3c2-integration-2026-11-01.json) and
[raw reports, wire snapshots, package provenance, logs and verifiers](framey-discord-main9b2f3c2-integration-2026-11-01-raw.json.gz).
