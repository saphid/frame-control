# Require exact-release ownership/watchdog CI — 2026-11-01

Base main `a963dc2920231448353e7cc0fb03ae9c519c0aaf` required the main,
native Decky, signed-package and tagged installer workflows before publishing,
but did not query `syncthing-candidate.yml`. Both actual ownership/watchdog
jobs could be missing or failed while the publisher still accepted the draft.

The publisher now requires both AMD64 and ARM64 ownership jobs at the exact
release commit on main, from a push or manual dispatch. Existing all-run and
all-attempt verification rejects prior failures, cancellations, skips and
unfinished work. The release guide includes manual dispatch for version-only
commits, where path filters can omit the workflow.

The offline publisher regression produced **16 assertion failures before the
fix**: missing run, wrong SHA/branch/event, unfinished/failed run, either missing
architecture, failed/cancelled/skipped jobs on both architectures, a failed
prior run and a cancelled earlier attempt were all accepted. After the fix,
all those scenarios refuse publication before any mutation. Push and manual
success cases pass in dry-run mode, with no upload or release PATCH.

The complete publisher suite passes **25 tests**, and release-workflow
coverage passes **12 tests**, both with zero skips. The stand-in GitHub CLI
records every command; these tests never contact GitHub or publish a real
release. Existing checksums, installer audit, manifest readback and exact
locked Frame-smoke gates remain in place. No real headset or physical
installer test was performed. Fresh exact-head hosted CI remains required.

Source SHA-256 after testing:

- `docs/releasing.md`: `4599297f1b543cadb7fd1eb55470be0a2bf2366dbb0f35f56fdc1d1f78fd4b33`
- `scripts/verify-release-gates.py`: `c89571f48779d4ee6e22762cf0b1f513834f5924f0eecc968b4eddd1fb6d04b8`
- `tests/fakegh/gh`: `99cb455e57d722673799c21819b1d6d11b79d04dd489d7cd174c642c5436919b`
- `tests/test_publish_release.py`: `f3afda553da4a18e5ea04221686944ff4b67b4afdbfc21d1cef740ad58b352f5`
