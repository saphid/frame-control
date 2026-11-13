# Animation Changer integration with TabMaster recovery

Implementation merge `1f59125443e99513ae0f230b56a5fee8510a5de7` brings #537 onto main
`89757d33f61124486404bc16e84b7d3697cf2c9f` without rewriting history. The reviewed prospective
merge tree equals the committed tree. All Animation Changer production inputs,
fixture, native probe and classifications are byte-identical to prior head
`72d63f7284e128213465c80f9a3eacec222451de`. Only main's TabMaster negative recovery
patch and its three evidence files were added; the exact patch reverse-checks
against the merged checker. Both existing Animation probe branches remain.

Sixteen focused Animation tests and three native inventory tests pass. Logs
and SHA-256 values are retained in the JSON companion. The initial source
verifier expected an `elif` where existing source uses two `if` branches; its
corrected assertion requires those two branches. No production change or
producer failure was relabeled a pass.

The preceding 18 green hosted checks, both native architectures, e2e and four
package modes describe the **old head**, not this merge. Fresh exact-publication
CI, native/e2e and applicable package/ownership checks remain required. Existing
playback, download, user-migration, official-rendering and real Frame limits
remain. No hardware or schedule was touched and no release is qualified.
