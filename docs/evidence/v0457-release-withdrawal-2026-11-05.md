# v0.4.57 draft withdrawal, 5 November 2026

The Steam discovery changes were committed as `a9f2004f68135fa65246dc385a5849be37b0aaaf`
and tagged `v0.4.57`. Local unit, end-to-end, Node, packaged-resource and
real Frame smoke checks passed. The real Frame smoke recorded 13 passes, no
skips or failures, and verified cleanup on SteamOS 0.5.6 build
`20261022.6153909`.

The exact-commit [ARM Decky runtime job](https://github.com/saphid/frame-control/actions/runs/41959848615/job/127023367649)
failed at official plugin case 52, Game Theme Music. The uploaded runtime
console shows Decky sent SIGKILL after the plugin failed to stop within five
seconds on its first stop. Its second stop completed in 0.1 seconds. The
same case's two stops completed in 0.1 seconds each in the prior ARM runtime
run at commit `1c2e48c89f031ae70136106c1de3ba556a4c6c74`. Case 52 uses
the pinned, unmodified official plugin; this release did not change it.

The release gate rejects a failed exact-commit job even if a later attempt
passes. Accordingly, `v0.4.57` must remain an unpublished, withdrawn draft.
The next candidate uses a new commit and tag and requires a new exact-commit
real Frame smoke and all release gates.
