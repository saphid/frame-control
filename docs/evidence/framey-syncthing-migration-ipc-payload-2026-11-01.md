# Syncthing migration IPC adapter delivery

The ARM64 signed-package and production-parent HTTP jobs on `cea43ed35581893982b2a7045a1bfed1f473cf1c` failed because the migration fixture copied the candidate backend without its child IPC adapter. Both retained artifacts verify installed signed bundles and actual two-way sync before migration fails; neither is a package pass.

The repair creates `py_modules` and copies the already supplied adapter beside the backend, matching other service/runtime fixtures. The candidate backend and all 9 prior native input hashes are unchanged. No installer or compatibility claim changes.

Tested implementation: `17ee294ee59d88ade389974e7c928e8ed10b6ef6`. The isolated migration delivery regression fails before the repair with the same missing-module error and passes after it. The Linux focused suite passes **102 tests with zero skips**. It executes the real migration delivery statements and imports both real copied Python files under `python -I`, outside the checkout. Decky's provided API is a fixture and the private watchdog is never executed; this is dependency-delivery proof, not a native migration run.

[Structured evidence](framey-syncthing-migration-ipc-payload-2026-11-01.json) binds both failed artifact ZIP digests, exact heads, consoles and test/source hashes. The compressed raw packet retains the failed consoles/results and focused test logs.

New full package jobs, current-head hosted native/e2e, browser/Steam CEF and real Frame/wearer/controller behavior remain unverified. Syncthing stays disabled/unselected. No release is qualified.
