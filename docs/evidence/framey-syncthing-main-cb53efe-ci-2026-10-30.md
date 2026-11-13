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

ARM64 artifact `12978736814` then passed the same independent exact-source,
signature, actual process, sync, service, ownership and migration audit. Its
SHA-256 is `88561ae98f92269c67048e4bfd203b2346e560b3d76afa57ee8749db31eab534`;
final instance cleanup took 1.017 seconds. All 11 exact-main checks were green
before #477 merged. This supersedes the earlier pending ARM64 checkpoint,
while retaining its original scope. No release was attempted.
