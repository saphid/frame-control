# RadiYo main refresh and blocking TabMaster shutdown, 31 October 2026

This refresh remains blocked by an unexpected forced plugin kill in the
positive TabMaster control. Successful restore/RPC assertions do not qualify
its shutdown. No merge or release is qualified by this evidence.

Source `62a99ba8b7c395ffc4000c0195b1917f12ba95e4` normally merges main
`1ac29413186fb29d5844ee9ad1c5c6fd36eeac27` into PR #520. The other 36 runtime
dispatch bodies, including TabMaster's restore repair, match current main;
RadiYo's dispatch body matches its previous head. Shared IPC/console helpers,
the archive inventory, other 33 native cases, all 116 catalog status/install
policies and the other 115 complete catalog rows are preserved. No history
was rewritten. RadiYo compatibility remains **partial**.

Isolated published Decky 3.3.0 AMD64 verified RadiYo's pinned managed archive.
The repaired case made nine RPCs, rejected self-signed HTTPS through both
`fetch` and `getRedirectUrl`, preserved loopback HTTP/redirect responses,
restarted and completed two parent-only stops in 0.214 and 0.225 seconds.
Recorded descendants disappeared, adopted children exited zero, and an
unrelated sibling survived. The previous-managed negative retained the TLS
repair, made seven RPCs and reproduced a forced plugin kill after 5.225
seconds. Installed source/helper hashes and unchanged archive members were
independently checked; the previous TLS source was reconstructed from the ZIP.

TabMaster's repaired and original-source cases made 47 and 48 RPCs. Valid
backup restore versus original-source refusal, malformed/non-object refusals,
private user values, sharing filters and restart persistence still passed.
However, the positive case's first stop took 5.224617586 seconds and logged
one forced plugin kill, with no completed original unload hook for that stop.
The second positive stop and both original-source stops completed in about
0.214 seconds. All loader parents exited zero and recorded owned identities
were reaped; those facts do not establish clean plugin shutdown. The positive
case logged no malformed-JSON diagnostic during its killed first stop; the
original-source control retained one.

The strict independent auditor rejected the positive stop's `<5`-second gate.
Its original source and failure are retained in the raw evidence. The final
collector asserts the observed failure and records `blockedByTabmasterRuntime`
and `mergeQualified: false`; it does not waive the failure or change production
gates. The cause of this intermittent shutdown failure remains unproven.
TabMaster's shutdown test/fix belongs in a separate scoped PR.

The full server suite passed 1,943 tests in 249.829 seconds with 16 skips; the
website suite passed 18 tests with no skips. These results do not waive the
TabMaster shutdown failure.

[Structured audit](framey-radiyo-main-refresh-2026-10-31.json) records those
results, 16 native source fingerprints and a passing production
HTTP/SSH installer method across 37 pinned fixtures. That method verifies
RadiYo and TabMaster receipts, installed bytes and removal. It does not execute
official backends or replace full e2e coverage. All owned installer containers,
volumes, networks and image tags were removed and their absence checked.
Native container/image cleanup is bound to the frozen runner; reported native
process cleanup is audited separately.

[Raw evidence](framey-radiyo-main-refresh-2026-10-31-raw.json.gz) retains the
native consoles/reports, strict-audit failure, verifiers, test logs and installer
cleanup records. The full native matrix was not repeated locally. Fresh
exact-head hosted CI/e2e, native AMD64/ARM64, ownership, PC, every triggered
package mode and exact-main gates remain required, alongside resolving the
blocking TabMaster shutdown failure. No new browser, external station,
trusted HTTPS, playback, Steam CEF, real Frame, wearer/controller or release
proof was obtained. No headset or hourly schedule was touched.
