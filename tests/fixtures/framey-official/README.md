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
| `26.zip` | HLTB for Deck | 2.0.12 | `bd54a23b0b8ec0798aa590e5be236522a593529d7680e77fb888e2971bf3d558` |

The matching source projects are
[ProtonDB Badges](https://github.com/bschelst/protondb-decky),
[Steam Status](https://github.com/bschelst/steamstatus-decky), and
[Storage Cleaner](https://github.com/mcarlucci/decky-storage-cleaner), and
[HLTB for Deck](https://github.com/morwy/hltb-for-deck).
The test verifies the ZIP digest, archive policy, API v1/v2 manifest, installed
frontend bytes, managed store receipt, and removal. A separate local host
test starts HLTB's bundled frontend and builds its settings view with a stub
Steam module lookup. It does **not** run plugin Python backends, HLTB searches,
or prove JavaScript panels render in the VR shell.
