# GitHub Prefix Manager 1.0.2: refresh against Free Loader main

PR #526's previous head `72a4115eb13742f7c006beb5042c768f9f6044de` had
successful checks but conflicted with main. A normal merge includes exact main
`dd41aede875d7a6b7abac68520784824b96103e9`, preserving its Free Loader repair.
Tested merge source: `643c60807caaed3e0d8e37c8f92e7c18fda30c81`.
Subsequent evidence-only commits preserve all 17 native source inputs. No
history is rewritten.

## Published versions remain distinct

The public [Decky catalog](https://plugins.deckbrew.xyz/plugins) read at
2026-10-31 15:04:19 UTC lists store 130 as Games Prefix Manager **1.0.1**, SHA-256
`ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473`.
The separate [GitHub v1.0.2 release](https://github.com/Saad-Alareqi/GamesPrefixManager/releases/tag/v1.0.2)
has asset 411464964, `games-prefix-manager.zip`, 58,717 bytes, with GitHub's
published SHA-256
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`.
That digest and size match the tested fixture exactly. The source readbacks are
retained in the audit.

The 116-row compatibility catalog and generated table are byte-identical to
main. Store 130 stays at 1.0.1, with partial compatibility. GitHub 1.0.2 stays
`unverified` in catalog lookup and is not offered as a store version by this
work. Independent installation comparisons prove every installed 1.0.1 file
and receipt remains identical to main, with no new IPC adapter.

The 1.0.2 repair prepends the unchanged shared EOF adapter only after matching
the exact GitHub archive and prior managed backend digest. The prior managed
backend below that prefix is byte-identical, retaining the actual-user paths,
unnecessary root-request removal, multi-library handling and bounded
backup/delete safeguards. The only changed existing installed files are
`main.py` and its managed receipt; the helper is the only added file.

## Fresh isolated native results

The focused matrix uses the published Decky 3.3.0 AMD64 loader, SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`,
in network-isolated disposable containers. All 17 source fingerprints match
the tested merge.

| Case | RPCs | Stop seconds | Forced kills | Qualification |
| --- | ---: | --- | ---: | --- |
| Store 1.0.1 | 39 | No dedicated lifecycle probe | — | Existing private safety controls |
| Repaired GitHub 1.0.2 | 42 | 0.214 / 0.214 | 0 | EOF readback, restart, two clean stops |
| Prior managed GitHub 1.0.2 | 40 | 5.223 | 1 | Expected failure control |
| Main's repaired Free Loader | 11 | 0.214 / 0.214 | 0 | Settings/deals, restart, two clean stops |
| Published Free Loader | 7 | 5.234 | 1 | Expected failure control |

Each Prefix Manager case verifies private backup contents, an older backup,
outside-marker preservation, scoped prefix removal, a second user's prefix,
malformed/unreadable shortcuts, ambiguous library IDs, and symlink/traversal
refusals. Bulk cleanup remains refused. No real prefixes or saves are used.

Repaired 1.0.2 answers `get_games` after the owned Unix peer closes and after
restart. Its strict stops signal only the owned loader, require exit 0, reap
the recorded PID/start identities and adopted children, retain both backup ZIP
hashes and the outside marker, and preserve an unrelated sibling. The plugin
has **no custom `_unload` hook**. The test checks normal framework completion
and the missing-hook diagnostic, not a nonexistent hook. The previous managed
backend still requires a forced kill and is explicitly not a compatibility
pass.

Free Loader's private settings and deal database are independently decoded,
hashed and compared across its repaired stops/restart. Its original-backend
negative remains intact. Generic runtime-console clean-shutdown qualification
remains false by design; plugin-specific lifecycle checks establish the
repaired results. There is no global clean/error-free runtime claim.

## Regression checks and source preservation

The full server suite completes 1,946 tests with 16 platform/optional skips.
All 18 website tests pass without skips. The production HTTP/SSH installer
method passes all 37 pinned store/legacy transactions and removes its owned
containers, volumes, networks and image tags; absence is checked independently.
That installer method covers store 1.0.1, not GitHub 1.0.2 or official-backend
execution. Separate baseline/candidate install comparisons and the native
matrix above cover 1.0.2. This is not the full e2e suite.

Independent source comparisons preserve main's other 36 runtime bodies, 33
native cases, every other installer branch and payload dispatch, the complete
e2e file, all 116 catalog rows/policies, and generated compatibility table.
The prior Prefix Manager runtime branch/helper remain unchanged. The runner
gains only its helper fingerprint and versioned negative control relative to
main. Free Loader and the shared IPC adapter match main. Generated-doc and
whitespace checks pass.

[Structured audit](framey-prefix-manager-102-main-dd41aed-refresh-2026-10-31.json)
and [compressed raw reports/verifiers](framey-prefix-manager-102-main-dd41aed-refresh-2026-10-31-raw.json.gz)
retain source fingerprints, installed-file comparisons, native reports,
available console text, public-source readbacks, test logs and installer
execution/cleanup. The JSON records compressed and decoded raw hashes.

Fresh final-head hosted CI/e2e/native AMD64+ARM64, ownership, PC, every triggered
package mode, exact-current-main checks, feedback and mergeability remain
gates. The full native matrix expects 44 probes, 34 archive pins and 17 source
fingerprints. Earlier exact-head results do not qualify this integration.

No refreshed browser, ARM64, real Frame, wearer-visible UI, physical-controller
or release proof is claimed. The exact socket history of the earlier
intermittent failure remains unknown. Headset and hourly schedules are
untouched; this local refresh qualifies neither a merge nor a release.
