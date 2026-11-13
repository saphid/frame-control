# Isolate reserved connection-test names from system DNS

Tested source: `35369a6ff1431b04e2761b801fc7df9a67f773de`, based on exact main `61efc562a65b552b1c00b75e8559c1c78764f57e`.
[PR527 macOS job 124723415873](https://github.com/saphid/frame-control/actions/runs/41264183889/job/124723415873)
failed three assertions at `0316a4299bd41f091ad39477c50a8d20c12ac337`. Its connection-test file is byte-identical
to main. The failures report `resolving` instead of `unresolved`, a timeout
message instead of an unknown-name message, and `frame_unreachable` instead of
`frame_not_set_up` after switching headsets.

A controlled resolver keeps reserved `.invalid` lookups pending until the harness
releases them. Temporary 0.05-second probe/grace values make the deadline path
repeatable without an actual slow resolver. The same three existing tests fail
with exactly the observed assertion types before the fixture change. After the
change all three pass, no reserved name reaches the controlled system resolver,
and all recorded resolver threads are released and joined. These shortened
values exist only in the standalone evidence harness.

The fixture now returns `socket.gaierror(EAI_NONAME)` immediately for reserved
`.invalid` names in Probe and Connecting. Numeric addresses, localhost resolution,
real loopback TCP sockets and fake SSH still exercise the original connection
path. All 84 tests in `test_link.py` pass with no skips, including the existing
slow-lookup deadline test. Production UI, connection code, timeout constants,
workflows, e2e and native fixture sources are unchanged.

Local execution is Linux/Python3.12. It reproduces the shared dependency, not a
fresh run on the failing macOS runner. Full server matrix, e2e and native hosted
checks on the publication head remain required. No real Frame or schedule was
touched. This is not a release qualification or a claim of headset usability.
The hash-bound raw packet contains the controlled harness, before/after results,
all connection-module output and the original job failure excerpt.
