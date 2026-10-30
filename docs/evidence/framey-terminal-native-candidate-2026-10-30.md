# Terminal native candidate: test scope, 2026-10-30

The published Terminal 0.5.3 (store 65) still fails to import `termios` in
published Decky 3.3.0. This change adds a separate, opt-in test of an adapted
copy, with native AMD64 and ARM64 CI jobs. It adds no managed adapter,
installation dependency, compatibility claim, or release.

The original archive remains pinned to SHA-256
`7bd8765ca57663a24178b05687acb52c3723518ac9eac1c14419a87904c0a872`.
The default runtime gate retains the unmodified negative import probe and
never calls Terminal RPC or opens a PTY in that probe. Candidate testing does
not add Terminal to `cases.json` or the supported-plugin inventory.

The disposable candidate receives pinned CPython 3.14.8 `pty`, `tty` and
architecture-specific `termios` files in its private package. It removes an
incorrect await of synchronous SIGWINCH delivery, keeps resize escape bytes
out of shell input, and unloads/reaps its owned shells with a bounded wait.
These are test-only changes to the extracted copy. Original bytes come from
the pinned archive; resulting candidate file hashes are in the runtime report.
Fixture provenance, licenses and extraction instructions accompany the inputs.

## Local verification

The accompanying JSON records two actual AMD64 Decky runs. Every report source
fingerprint was independently compared with the tested tree, as were both
fixture manifests, loader pin, plugin archive pin, actual loader Python ABI,
PTY output and process-cleanup observations.

- The candidate passed private shell input/output, including a marker file,
  separate output lines (not merely echoed command text), and `stty` size 31x97.
- Explicit removal reaped its first shell. Actual Decky reload removed the
  second shell, preserved an unrelated private sleep process, and retained
  private config. The loader imported the private CPython 3.14 extension.
- The unmodified archive separately reproduced the exact missing-`termios`
  import failure, without backend RPC, PTY commands, or input.
- The three managed-shim coverage tests, Python syntax and diff checks passed.

Both executions used nonroot, read-only, networkless disposable Docker
containers with private homes and no host home, session bus, or hardware.
The owned containers and images exited and were removed.

## Limits

Native ARM64 execution is pending CI. Extracting an ARM64 image and checking
ELF machine 183 proves provenance and architecture, not successful loading.
Browser/production HTTP parent/actual Steam CEF, managed installation, actual
Frame pixels, wearer visibility and physical controllers remain unverified by
this change. No headset or hourly worn schedule was touched. Earlier private
VM browser exploration is outside this PR's evidence and is not a production
compatibility claim.
