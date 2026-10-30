# Exact-main signed Syncthing CI, 30 October 2026

Main `cb53efed70db011bf7ad8ae906e4a88d2dcb72ff` has a passing AMD64
signed-package job in run `41055227647`. Artifact `12977452522` was downloaded
and its GitHub SHA-256 matched
`9a4e36dca0426165bd747e9c2efc2dbfd914aa8d3142529740746c2bba2411f3`.
Independent audit verified every recorded source fingerprint against this
commit, signed app/runtime identities, actual Decky 3.3.0 RPC, two-way sync,
nine setup results, 17 service lifecycle results, 18 ownership refusals,
12 migration results, and data-preserving uninstall. Final Flatpak instance
cleanup took 0.154 seconds and left no owned instances.

ARM64 was still running at this audit, so main was not yet declared fully
green and no further merge was authorized from this result alone. This is
not release verification or a real Frame test. Syncthing installation remains
blocked. See the companion JSON for exact identities and results.
