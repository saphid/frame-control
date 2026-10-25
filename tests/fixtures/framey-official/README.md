# Pinned Decky store test archives

These are unmodified ZIPs downloaded from the official Decky store CDN on
2026-10-25. Each ZIP includes its upstream `LICENSE`. They are test data, not
plugins shipped or installed by Frame Control. The fake Frame tests serve them
from a local fixture so CI does not depend on the store being online.

| File | Official plugin | Version | Store SHA-256 |
| --- | --- | --- | --- |
| `14.zip` | ProtonDB Badges | 1.3.4 | `90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358` |
| `123.zip` | Steam Status | 1.2.3 | `9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e` |
| `50.zip` | Storage Cleaner | 1.4.0 | `1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591` |
| `18.zip` | Bluetooth | 3.1.1 | `f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5` |
| `26.zip` | HLTB for Deck | 2.0.12 | `bd54a23b0b8ec0798aa590e5be236522a593529d7680e77fb888e2971bf3d558` |

The matching source projects are
[ProtonDB Badges](https://github.com/bschelst/protondb-decky),
[Steam Status](https://github.com/bschelst/steamstatus-decky),
[Storage Cleaner](https://github.com/mcarlucci/decky-storage-cleaner),
[Bluetooth](https://github.com/Outpox/Bluetooth), and
[HLTB for Deck](https://github.com/morwy/hltb-for-deck).
The test verifies the ZIP digest, archive policy, API v1/v2 manifest, installed
frontend bytes, managed store receipt, and removal. Separate local host tests
start Bluetooth's frontend and its initial panel without running effects or
actions, and start HLTB's frontend and shallow settings view with a stub Steam
module lookup. They do **not** run plugin Python backends, Bluetooth actions,
HLTB searches, or prove JavaScript panels render in the VR shell. The
Bluetooth result and limits are in
[the fixture evidence](../../../docs/evidence/framey-bluetooth-fixture-2026-10-25.md).
