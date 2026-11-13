# Completed host-gate and current-main runtime evidence

These records distinguish completed exact-source jobs from pending merge and release gates. They do not authorize a release or promote a compatibility status.

## PR #493 at exact head `f114892`

[The complete nine-job audit](framey-host-shutdown-current-ci-2026-10-30.json) covers exact head `f114892663dd546d73a28c55b96bacc880ab3418`. All five applicable workflows and 18 checks completed successfully. Each artifact matches GitHub's SHA-256; successful jobs/steps and actual logged checkout commits were checked. Native and e2e checkout `aa213458893ec7ac4293d5ec28c72a93cbaca41c` has the same complete tree as this exact head. Package and ownership jobs checked out the exact head directly. This document records #493's evidence; it does not ship that PR's stricter host verifier.

| Mode | Job | Artifact | ZIP SHA-256 |
| --- | --- | --- | --- |
| package-amd | `124283629453` | `13009952620` | `3f51a1eebedee0cf604c904c75d73b7412af53859dd3ac794860ce0d1b39a925` |
| package-arm | `124283629552` | `13012135163` | `59f3d5d5ea97b41a6b7aba6a05c3c46a94b5426a6432258ce7290801b70332de` |
| package-http | `124283629022` | `13009892726` | `d4097b95b3be5e16f5073a9a479d8f23f7a8698e9dbcf02b3b48c5fd8a59425f` |
| package-parent | `124283629334` | `13011311294` | `32dcab763c01b0ab3e475a6c89726e60fa7669c61195591e987e97897908980b` |
| native-amd | `124283628300` | `13007959945` | `173fe33b28afa935f94e564f7b11ff24141566a226482af79cf2ee64efc60dea` |
| native-arm | `124283627628` | `13009730140` | `db761bc2b8a9b89bd6ec909d2c5bd8faf687396adcd7df31560124bf05e0299d` |
| ownership-amd | `124283628016` | `13008197371` | `9f9622a9034ae9cad0cafd08dadc678364f67900581eb72a932cdfa1a80580ad` |
| ownership-arm | `124283628433` | `13008083193` | `4e53e9fddf24529eb93bc3c92d6de084a620d5014a7cdcbfd44228a31e784054` |

The four signed-package reports verify committed source hashes, published pinned app/runtime commits and signatures, actual two-way sync, 17 lifecycle results, 18 ownership refusals, 12 migration/preservation results, and both owned Decky shutdowns. Each shutdown reports checked complete logs, actual unit removal and PID-to-zero, inactive/success/exit-0/mixed stop. Package artifacts do not retain raw Decky consoles: the clean complete-log check is source-bound guest evidence, not an independent review of raw Decky logs.

The browser and production-parent jobs retain four and eight capture payloads. Each matches its PNG digest. All five distinct images across those jobs were visually inspected: the private panel shows Running with its private folder/peer, then Stopped with the contents removed. Their CEF facade, managed receipts, pointer input and browser bridge are synthetic. They do not establish actual Steam CEF, production managed installation, real Frame pixels, wearer visibility or physical controller usability.

Both native reports verify 33 probes and 30 published archive digests. Both ownership reports independently verify all 14 transported source hashes, actual runtime sync, lifecycle/refusal assertions, the strict stop gate and full retained service consoles without shutdown errors or cancellation. Actual e2e job `124283628515` in run `41119888746` passed in 234 seconds on the matching checkout tree. Source, packet, checksum and job-log identities are in the linked JSON. The source-bound migration namespace assertion is identified separately from serialized identity fields.

## Main at exact head `d89291e`

[The completed main jobs](framey-main-d89291e-completed-ci-2026-10-30.json) cover head `d89291ef3fcfbe94056ad4a1b659ee0d9e8b6b8c`. Native run `41125956882` passed on AMD64 and ARM64: each report verifies 34 probes, 30 published archive digests and all seven source fingerprints, including the unchanged published Terminal import failure. Actual e2e job `124304417284` in completed checks run `41125956886` passed in 236 seconds (310 including builds). Actual exact checkout, complete tree, artifact digest and successful steps were independently checked.

At this audit, main's four signed-package jobs in run `41125956883` remained running. The completed core/e2e/native jobs do not establish a full main or release pass. PR #494 subsequently absorbs this main through a normal merge; older PR artifact results remain historical and fresh final-head checks remain required.

No real Frame, wearer or controller test was performed. No headset session, security setting, installer policy, published asset, compatibility support status or pre-existing user data changed. Release remains held for all exact release-commit CI/e2e/native, release verification, tagged installers/checksums, publisher dry run and locked real Frame smoke requirements.
