# Backend merge qualification, 14 November 2026

PR #702 merged as `bbbf7260`, preserving the original #503 and #511 heads as
ancestors. All 25 hosted checks succeeded. The actual-main integration tree and
both GitHub merge parents match the independently tested result. The local
store/compatibility/runtime suites passed 153 tests and panel suite passed 38;
one browser-dependent panel check skipped locally, with hosted e2e green.

Both downloaded native architectures and their Terminal-candidate artifacts
passed independent size/digest, pinned-loader, source and console audits. Each
full run preserves 44 primary cases and 39 controls, with 60 input source hashes.
Bluetooth, Badges and PlayTime together record 12 parent-only stops. Four
retained SQLite databases were independently decoded, opened read-only, hashed
and checked for integrity, user isolation and exact expected session rows.

This is isolated runtime evidence. Radio pairing, visible Steam badges,
automatic play tracking, worn UI, physical controllers, scrolling and VR keyboard
remain unverified. Publication still requires the exact release's own gates.
