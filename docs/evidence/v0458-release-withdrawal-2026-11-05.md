# v0.4.58 draft withdrawal, 5 November 2026

The new candidate at `1c850ef7ff44cf0e059b4b40df1819e8222e9ae1` passed a
fresh real Frame smoke with 13 passes, no skips or failures, and verified
cleanup. All six tagged release jobs passed. An independent audit downloaded
all ten installers, checked their SHA-256 digests, package formats and
versions, matched `SHA256SUMS`, and launched the x86_64 AppImage on Xvfb.

The exact-commit [Windows server-test job](https://github.com/saphid/frame-control/actions/runs/41960920213/job/127026826522)
failed in `test_tag_allowlists_match_ui_and_live_steam_evidence`. The test
read `ui/index.html` without specifying an encoding; Windows tried cp1252 and
raised `UnicodeDecodeError` on its UTF-8 content. This is a test bug, not a
packaged app failure. The next candidate explicitly reads both test fixture
files as UTF-8. The targeted Steam test suite passed locally after the fix.

Because the exact-commit release gate rejects any failed job, `v0.4.58` must
remain an unpublished, withdrawn draft. The next candidate needs a new tag,
fresh real Frame smoke, all exact-commit CI gates, and a new asset audit.
