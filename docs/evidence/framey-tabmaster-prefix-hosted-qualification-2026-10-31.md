# TabMaster and GitHub Prefix Manager exact-head qualification

Review heads: #525 `f445c71833b119aab35d0ac920859ca40c536ab1`; #526
`9aaaa004f7504725aff898ab198395d7389cf2f1`. Both finish **18/18 hosted checks** with no review
comments or unresolved threads at the recorded review. At this review, main was
`fda7bcd86237033949d72a967c4e8fd41c9d46cc`. **Merge remains held for completed exact-current-main CI
and a fresh final gate.** No source branch was pushed or rewritten for this review.

## Native shutdown and data controls

Both digest-pinned published Decky 3.3.0 architectures retain **46 cases** with
**eight expected regression controls** each. These are scoped controls, not a
global clean-runtime or compatibility pass. All **20 input hashes** per report
match the exact PR head. Each PR's eight native/watchdog/package artifacts pass
**1,363 source-hash bindings across 149 files**, including all four triggered
package modes. Complete browser result packets decode and match their checksums.
Package reports retain synthetic CEF/input/store-receipt limits and disabled
installer defaults.

TabMaster 2.15.1 repaired/original/prior-managed cases complete **47/48/47 RPCs**
on each architecture. Repaired peer-EOF and restarted stops take approximately
**0.214/0.214 seconds AMD64** and **0.164/0.164 seconds ARM64**: original unload
hook completed, zero forced kills, owned identities reaped, unrelated sibling
preserved. User isolation, shared filtering, false values and backup/restore
remain checked. Original published source refuses valid restore; the previous
managed negative force-stops at **5.230/5.227 seconds**. Those failures remain
retained. Generic console qualification stays false; JSON diagnostics remain.
Compatibility stays partial; library-tab editing and wearer-visible use are unverified.

Prefix Manager store/repaired-GitHub/prior-managed cases complete **39/42/40 RPCs**
on both architectures. Repaired stops take **0.164/0.164 seconds AMD64** and
**0.214/0.164 seconds ARM64**. The published plugin has no custom unload hook;
its normal framework unload completes without forced kills. Backup bytes and old
backups, outside marker, second-user prefixes, ambiguous-library prefixes, and
malformed/unreadable shortcuts survive. Symlink/traversal requests and bulk cleanup
are refused. The previous-managed forced-stop negative remains a failure.

A fresh production-User-Agent store read still lists **store 130 as 1.0.1**,
`ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473`.
GitHub v1.0.2 still publishes the separate **58,717-byte** ZIP, digest
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`.
Independent installation keeps every store file/receipt identical to main and
preserves the GitHub user-path/bounded-delete repairs beneath only the EOF prefix.
Its installed manifest does not request root. GitHub 1.0.2 stays **unverified** in
catalog lookup; it is not represented as the live store version.

## Prospective TabMaster merge with current main

Main's new VM-packer files and #525's changed paths do not overlap. Independent
comparison checks **all 1,430 tree entries**: the prospective merge
contains exactly main plus #525's paths, preserving main's packer fix and all
20 exact native inputs. Source/AST comparison preserves other runtime bodies,
installer/e2e branches, cases, catalog rows and policies.

Local candidate `5eb123694058df466a726c95ce61f09bce043393` (tree
`72db8606932901729acd0951cceb0a72ccdfde7e`) passes **1,952 server tests** with **16 stated
platform/optional skips**, **18 website tests** without skips, and the **full
53-test fake-Frame e2e suite without skips**. Mounting the exact cache fills the
hosted catalog skip: all **116 pinned archives** finish with 69
install/remove outcomes and 47 correct policy/archive refusals. Official
backends do not execute in this installer/e2e fixture. Native backend evidence
above comes from the separate published-Decky jobs.

Owned e2e containers, volumes, network and image tags are removed; absence is
independently checked. Initial website reporting used Node's spec format, which
our supplemental collector mistook for TAP; the original passing log remains,
and a short explicit-TAP rerun passes. No product source or server suite was
changed/repeated for that collector correction.

The candidate is local prospective-merge evidence, not a hosted PR head or
release-commit CI pass. Full package modes belong to the exact PR heads, not a
new hosted merge candidate. Existing negative histories, platform skips, and
headset/controller limits remain. Real Steam CEF, managed Frame installation,
real saves, wearer-visible interaction and release smoke are unverified.
The headset, schedules, #113 and pre-existing user data were untouched.

[Audit](framey-tabmaster-prefix-hosted-qualification-2026-10-31.json) and [native reports, artifact inventories, audit scripts,
readbacks and local logs](framey-tabmaster-prefix-hosted-qualification-2026-10-31-raw.json.gz). Full package reports/packets/images
remain in linked artifacts/local state, not embedded in this scoped native bundle.

#525: [native](https://github.com/saphid/frame-control/actions/runs/41223137911),
[ownership](https://github.com/saphid/frame-control/actions/runs/41223137807),
[all package modes](https://github.com/saphid/frame-control/actions/runs/41223137888),
[CI/e2e](https://github.com/saphid/frame-control/actions/runs/41223137795).
#526: [native](https://github.com/saphid/frame-control/actions/runs/41221501941),
[ownership](https://github.com/saphid/frame-control/actions/runs/41221501886),
[all package modes](https://github.com/saphid/frame-control/actions/runs/41221501895),
[CI/e2e](https://github.com/saphid/frame-control/actions/runs/41221501921).
