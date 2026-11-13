# Full official catalog transport regression, 30 October 2026

A fresh official store read matched every ID/version/digest in the 116-plugin
registry. `scripts/framey-audit-store.py` downloaded and SHA-256 verified all
116 exact archives and statically inspected them with **zero audit errors**.
No plugin code was imported or executed.

`scripts/framey-audit-fake.py` then passed the optional full-catalog regression
against the actual HTTP/SSH managed installer in the uniquely owned project
`framey-catalog-7cd4659d51`. The audited host code was PR #461 head
`bdeb347e20c11fc22723f82337ce5fc0500e4acb`; its service/CEF backend was stubbed.
The later Python 3.9 annotation fix was not part of this transport snapshot.

[All 116 observations](framey-catalog-transport-2026-10-30.json) record:

- **69 installed and removed:** expected frontend bytes (including managed
  transforms), exact version/digest receipts, successful removal and absence
  from the managed inventory afterward.
- **47 blocked as expected:** root, hardware/compatibility, architecture or
  archive-policy refusal, with no managed plugin installed afterward.

The test completed in **124.719 seconds**, with no failure or skip. All 116
observation IDs/digests match the current registry exactly. DeckyParty's pinned
archive is included in the successful install/remove set. The owned project's
two containers, network and three named volumes were removed by the harness.
Downloaded archives and raw static output remain in the private audit cache;
no pre-existing cache or user data was deleted.

This closes the transport regression gap left by the focused fixture tests.
It does **not** prove any plugin's backend, frontend controls, external service,
real Frame behavior or wearer-visible/controller usability. Official Python
and native plugin code did not execute in this run. Compatibility ratings stay
unchanged; separately scoped native/backend evidence remains necessary.
