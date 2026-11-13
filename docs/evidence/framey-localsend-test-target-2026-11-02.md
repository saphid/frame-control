# LocalSend missing-adapter test target — 2026-11-02

PR #552 macOS job **125121054266** failed on head `7270d396eeaf3876c2a4321d4a0736e3a2efb940`. Its actual checkout was merge `2b74e8ac51bc2f6aab7110ecdc127d37d2454f14`, whose tree `7a84b753ae53b3cb3abe119656c7683d6cece673` independently equals that exact head; both parent SHAs are verified. The `macos-26-arm64` runner reports its CPU as `arm64`. The Linux installer intentionally supports `x86_64` and `aarch64`, so the new missing-adapter transaction test hit **Unsupported LocalSend helper architecture** before reaching the intended **Missing LocalSend child IPC EOF repair** guard. Full CI result: **2035 tests, one failure, 70 platform/optional skips**. Log SHA-256: `fa3524a7512d1ddd7a00610cc6d7aeb0825e783b497ab4c81b110625e669bbb5`. The failed run is retained and not rerun to replace this evidence.

Implementation `f03d19d1ae16596ee78cd4bc2ccd846fda82a55f` changes only `test_localsend_missing_ipc_payload_cannot_publish_install`. The test explicitly models each supported Linux target (`x86_64`, `aarch64`) in its disposable installer subprocess, matching the existing ARM64 helper-write fixture. It still requires the missing-adapter error and no published plugin folder for both targets. No production architecture mapping/validation, native runtime, e2e source, helper payload, archive, catalog or workflow changes; no new skip. Independent AST comparison preserves the rest of the test file, and all **42 native source fingerprints** remain unchanged.

## Verification

- Original committed test reproduces the CI error under simulated subprocess host-machine alias `arm64`; original `x86_64` alias passes. This is Linux-based host-alias simulation, not actual macOS execution.
- Corrected test passes under both simulated host aliases, each exercising both supported target architectures: **four target/host combinations**, zero skips. Only helper files are written; their binaries are not executed.
- Complete store test module: **77 tests / zero skips**, **17.777s**. Corrected file SHA-256 `94155f9205131e1e4d1e1e66de2af39bcb27642a73554ef9870e0bc62be52703` binds the pre-commit test runs to the committed implementation.
- Previous native AMD64 and full fake-Frame e2e observations remain historical evidence with unchanged inputs. Fresh full CI, including actual macOS and both native architectures, plus every artifact/merge/release gate remains required for the new publication. Local modelled targets do not prove native ARM64 or macOS runtime behavior.

No merge, release or headset interaction. #551 remains held until this child and the later combined parent head qualify. Existing compatibility limits remain.

[Bound summary](framey-localsend-test-target-2026-11-02.json) · [Retained failure, RED/GREEN logs and runner](framey-localsend-test-target-2026-11-02-raw.json.gz).
