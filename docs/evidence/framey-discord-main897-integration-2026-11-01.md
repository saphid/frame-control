# Discord Status integration with TabMaster recovery

Implementation merge `b6a489b4c55f2d7d8660877ef14c78a138ce4547` integrates main
`89757d33f61124486404bc16e84b7d3697cf2c9f` without rewriting history. The exact prospective
merge tree matches. Only main's TabMaster negative-recovery checker patch and
its evidence files were added; that exact patch reverse-checks cleanly. All
Discord production inputs, archive pins, classifications and the private
native Discord probe remain byte-identical to preceding head
`bd2a51ebef0d2b76c653d896d1a53be988da737b`.

Eight focused tests and three native inventory tests pass. Published Decky
3.3.0 native AMD64 independently verifies 14 actual RPCs, six private Unix
connections and 18 decoded protocol frames. Replacement, clear, rejected
handshake/retry, two strict parent-only clean stops and restart pass. Owned
process identities disappear, adopted child exits succeed and an unrelated
sibling survives. All 29 runtime hashes match this merge. The generic console
recorder never certifies plugin shutdown; the two scoped stops are separately
verified. Raw wire, consoles, source hashes and verifier are retained in the
compressed companion.

The earlier 18/18 hosted checks, native AMD64/ARM64, e2e, ownership and four
signed-package modes apply to the old head, not this integration. Fresh exact
publication CI/native/e2e/ownership/package gates remain required. Real Discord
account/activity, live Steam callbacks, rendered controls, real Steam CEF and
Frame/worn/controller behavior remain unverified. No headset or schedule was
touched. Syncthing installation stays disabled; no release is qualified.
