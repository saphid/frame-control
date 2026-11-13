# Fake Frame package download retry, 26 October 2026

The ARM64 fake Frame container sometimes fails before project tests start.
Valve's `holo-packages.steamos.cloud` returned package responses with **164
bytes missing** during the `pacman -Syu` layer in
`tests/fakeframe/Containerfile`:

| Run | Package and outcome |
| --- | --- |
| [v0.4.44 candidate checks](https://github.com/saphid/frame-control/actions/runs/40296431563) | `iptables` download truncated; a failed-only rerun passed on the unchanged PR head. |
| [PR #316 checks](https://github.com/saphid/frame-control/actions/runs/40298316496) | `c-ares` download truncated before e2e tests. |
| [PR #318 checks](https://github.com/saphid/frame-control/actions/runs/40301478955) | First attempt truncated `iptables`; failed-only rerun on the unchanged documentation head truncated `rsync`. The six other jobs passed. |

The fake Frame image now retries that package transaction at most five times,
with a two-second delay after each failed attempt except the last. A fifth
failure still fails the build. The end-to-end tests and their assertions are
unchanged. This retry affects only the fake Frame test image; it does not
change a real headset or the released application.

Exact-head hosted CI must pass before this change is merged. A successful
container build would show that at least one package attempt completed; it
would not establish that Valve's package service is permanently healthy.
