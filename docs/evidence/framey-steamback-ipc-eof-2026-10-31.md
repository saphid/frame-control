# Steamback IPC shutdown and private save preservation, 31 October 2026

Steamback 1.0.0-1 could pass backup/restore/undo RPCs while Decky force-killed
its plugin and skipped the original unload hook. The observed ARM64 case is
from prior head `cb9fb6e83785e68cfe8c83a85533021c1c6dde16`,
[job 124535833590](https://github.com/saphid/frame-control/actions/runs/41200729134/job/124535833590),
artifact 13042149685, ZIP SHA-256
`5d62c2d25af6ca11f61803145585f74134f7ea4b375ef026f33300a905f73240`.
Its eight RPCs complete, then the console records a forced stop without
`Steamback exiting!`. That job/artifact and all source/console hashes were
independently audited; the scoped original report is retained here too.
The exact peer history of that failure was not retained, so its sole cause
is not established by the later controlled reproduction.

The new strict test first ran at unchanged production source
`5603d99dedd9a67012491b8831fbfdbe14b90426`, based on main
`dd41aede875d7a6b7abac68520784824b96103e9`. Closing one owned Unix peer
reproduces the failure: loader exit zero after 5.255 seconds, one forced
plugin kill and no unload hook. All 17 source fingerprints verify. The red
run retains the stop observation and complete console; its private byte
assertions executed, but the failed run did not serialize the save snapshots.
The final repaired and original-source controls retain those snapshots.

Source `97f26ff232b4e667bd2776dc8c6924c30c37ed10` applies the existing
child-local EOF adapter only to published archive SHA-256
`ed5f2fbb47cdfc3aa9a4349a139ab20c29976117a3be0de7e8a588bb265ee7f3`.
The installed backend is the exact original backend with only the adapter
installation prefix. Save discovery, backup, restore, undo, calling convention
and other archive members remain unchanged, including identical duplicate
members. All published files, helper bytes, receipt and owned removal are
independently checked through a sandboxed production installer transaction.
Existing managed copies need Update/reinstall; compatibility remains partial.

Published Decky 3.3.0 AMD64 repaired/original controls verify all 17 frozen
inputs and 11/9 literal RPC sequences. Private save discovery, backup, restore
and undo have independent old/new byte checks. Before and after each stop,
all private runtime backup/undo metadata and save bytes are retained with
base64 payloads and verified hashes. The repaired original unload hook runs
once on the controlled-disconnect stop and once on an ordinary stop after
restart; stops take 0.225/0.215 seconds without forced kills. Restart discovery,
account selection and identical save-info readback pass. The original-source
negative reproduces the forced stop in 5.224 seconds and remains explicitly
unqualified. Recorded owned descendants disappear, adopted children exit zero,
and an unrelated sibling survives. Full consoles and identities are retained.

Independent AST/catalog checks preserve main's other 36 runtime bodies, every
other installer branch/payload dispatch, other 115 complete catalog rows and
all 116 status/install policies. The shared IPC adapter, console collector,
official archive inventory and Free Loader fixture are unchanged. The future
full native inventory is 44 probes, 34 pins and 17 fingerprints; only the
scoped AMD64 controls were run locally.

The full server suite passes 1,949 tests in 249.285 seconds with 16 optional/
platform skips; all 66 focused store tests and all 18 website tests pass without
skips. One production HTTP/SSH installer test passes across 37 pinned fixtures,
checking receipts, installed bytes and removal. Uniquely owned installer
containers, volumes, networks and image tags are removed and their absence
checked. This does not execute official backends or replace full e2e.
Native process cleanup is independently checked; container/image cleanup
remains bound to the frozen runner. Published Python syntax warnings remain;
no globally clean or warning-free runtime claim follows.

Fresh exact-head CI/full e2e/native AMD64+ARM64/ownership/PC/all triggered
package modes, current-main checks and feedback review remain required. No
automatic game triggers, real Steam saves, browser, Steam CEF, managed real
Frame, wearer-visible behavior, physical controller, tagged installer or
release proof was obtained. The headset and hourly schedule were untouched.

[Structured audit](framey-steamback-ipc-eof-2026-10-31.json) and
[raw reports, snapshots, logs and verifier](framey-steamback-ipc-eof-2026-10-31-raw.json.gz).
