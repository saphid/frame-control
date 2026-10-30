# Shotty native AMD64 and ARM64 copy evidence

The compatibility table still described Shotty's private copy proof as x86_64-only. Published Decky 3.3.0 CI on exact main `e26ae7fea77c7c8702fdcfc694f4f0186f80cf43` now verifies the same managed Shotty 0.1.0 case on both architectures. This updates the recorded backend scope; Shotty stays **partial**.

The exact official archive has SHA-256 `ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe`. Its managed copy receives the existing `shotty-click-app-dir` and `shotty-bounded-copies` repairs from the [copy-boundary follow-up](framey-shotty-bounded-2026-10-30.md). No shim, archive digest, install policy or runtime behavior changes here.

Completed workflow `41131194212`, attempt 1, produced these independently audited jobs:

| Architecture | Job | Artifact | Artifact ZIP SHA-256 |
| --- | --- | --- | --- |
| AMD64 / x86_64 | 124322238547 | 13013828653 | `ca44dfea636b5b851200259a6185559a85e097da2e462c22ffe5e6897df001a3` |
| ARM64 / aarch64 | 124322238238 | 13012959851 | `ede7526d8abf77c06b1e60bfbb87a97aacd357d80bd25031aba635f4a517dde9` |

For each job, the GitHub artifact digest, successful attempt and steps, actual logged checkout, pinned Decky loader, seven committed source fingerprints and official archive bytes were checked. The adjacent [JSON audit](framey-shotty-native-architectures-2026-10-30.json) retains both case records and job-log hashes. These are historical exact-main results; they do not stand in for this documentation PR's own CI or main's remaining package gates.

The published loader discovers the managed plugin. Sixteen legacy RPCs verify empty aggregation, selected screenshot copies across distinct filesystems, repeat copies, destination bytes independent of later source changes, preservation of conflicting output, title confinement, symlink and invalid app-ID refusals, and historical aggregation. The test reads the private output bytes and filesystem identities directly before setting its state flags; these checks are source-bound fixture evidence, not a retained disk image. No real screenshot or user data is used.

Raw loader consoles are absent from these artifacts. This report does not independently claim clean complete loader logs or a strict service shutdown result. The native proof is separate from browser/backend integration, Steam screenshot events, continuous rescue, a managed installation on the real Frame, real Steam CEF, wearer-visible UI and physical-controller use; all remain unverified. The earlier local Chromium and fake-Frame transport evidence keep their original scopes. Existing installed copies still need Update/reinstall to receive the original copy-boundary repair.
