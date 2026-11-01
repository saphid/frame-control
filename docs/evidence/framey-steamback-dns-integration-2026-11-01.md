# Steamback integration with the DNS fixture repair

Normally merge current main `4558a36f58f84840d835f4fc281f12541f15ea94` into prior published PR #527 head
`0316a4299bd41f091ad39477c50a8d20c12ac337`, yielding tested source `a7b8f1232d9089fcb02488ff302ec605e1df7800`. All old jobs were terminal:
17 successful checks and the macOS connection-suite failure. Main's exact nine
triggered checks and two workflows were successful before integration.

The merge adds only `tests/test_link.py` and the three existing #534 evidence
files relative to the prior PR head. The test file is byte-identical to main.
The fixture resolves reserved `.invalid` names immediately without changing
production DNS behavior or deadlines.

On this Linux AMD64 host, all **84 connection tests pass, zero skips,
27.745 seconds**. This is not an actual macOS rerun.

The complete checker/installer/test AST preservation audit passes. All 25 native
source inputs are byte-identical to the prior publication. The original
Steamback controlled-EOF hook, restart/save probes and negative control are
preserved, alongside main's other plugin branches and all 116 status/install
policies. Native source preservation does not establish new native execution.
No local native or simulator e2e rerun was performed for this test-only merge;
fresh exact publication-head hosted CI/e2e/native, ownership and every triggered
package mode remain required before final current-main/review/mergeability gates.

Earlier native/e2e/full-suite packets remain historical evidence. Compatibility
stays partial. Store 130 stays 1.0.1; the separate GitHub 1.0.2 candidate retains
lookup status unverified. Real Steam saves, automatic backup triggers, official
UI, actual Steam CEF, Frame installation, worn visuals and controllers remain
unverified. No headset or schedule was touched, and this is not a release.

The raw packet retains the complete source audit and program, local connection
log and preintegration job/review/current-main snapshots.
Raw SHA-256: `e3f448382fa54736fe4af48c3dd6a17ae4e01f4d7d708680ddeee0ab334ceaa6`.
