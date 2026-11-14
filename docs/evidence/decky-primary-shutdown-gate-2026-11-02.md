# Native Decky primary shutdown gate

The native runtime CLI previously accepted a zero Docker/loader exit even when
Decky forcibly killed a plugin during shutdown. Its console diagnostics exposed
the failure, but did not fail the producer job. Independent release and merge
audits must still inspect all required artifacts.

The CLI now checks complete, SHA-256-bound runtime console captures for each
primary case and rejects `Sending SIGKILL!` or `Error during shutdown:`. It
retains the failing observation in the output report and runs the existing
owned container/image cleanup. Expected RPC errors remain allowed. Only the
runner's explicitly enumerated original-source negative controls bypass this
primary policy; their existing probe assertions still apply.

## Evidence

- The committed fixture is an actual ARM64 Game Sync case 104 console from
  main `39ed2b0b139c2f486daeb3f3cb8a27067d9bc858`, artifact
  [13103701800](https://api.github.com/repos/saphid/frame-control/actions/artifacts/13103701800).
  The loader parent returned zero after `Sending SIGKILL!`.
- The fixture file SHA-256 is
  `1250e3217cc7d84d6bb7e22e550cdaa100ce2257135b6d12dab7caa72b695353`.
  These are private disposable container paths, without a real user session.
- Before the fix, two of four mocked CLI regression tests failed because the
  CLI accepted forced kill/shutdown error diagnostics. After the fix, all five
  regression tests pass, including complete/digest checks, retained failure
  reports, expected RPC errors, and the explicit negative-control distinction.
  The existing three runtime coverage tests also pass. Docker is mocked in
  these CLI tests; they do not establish new-head native execution.
- Artifact replay applies the new validator to all 38 primary observations
  from each of the audited #536 AMD64/ARM64 reports (artifacts 13105743739 and
  13105139948). All 76 pass. The 20 explicit controls per architecture are
  excluded from primary validation. The historical ARM64 fixture is rejected.

Fresh exact-head hosted CI/native runs remain required. This gate does not
repair additional plugins, establish filesystem ownership by itself, verify
physical audio or controllers, or prove real Frame/wearer-visible behavior.
No real Frame was contacted for this change.
