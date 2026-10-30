# Signed native gates for the #479 merge, 30 October 2026

Exact main `28181ac0065389a70444b799c25be255fbc7dbaa` passed all 14 checks;
exact #479 head `5a6629155b4b9b9822f6d2c216b47a377b59f2e0` passed all 18.
Immediately before merge, both heads, mergeability and empty review/comment/
unresolved-thread lists were rechecked. #479 merged as
`24c6acd778fe3aba4936c532793523fa4780716b`.

The four [independent native audits](framey-syncthing-native-merge-479-2026-10-30.json)
retain run/artifact IDs and SHA-256 digests for AMD64 and ARM64 signed-package
results on both heads. Every source fingerprint, pinned Flathub signature and
content check passed. Actual signed Syncthing 1.27.3 identities, namespaces,
ancestry, Decky 3.3.0 RPC, two-way sync, nine setup results, 17 lifecycle results,
18 ownership refusals and 12 migration results passed. Uninstall preserved data;
owned units/processes and Flatpak instances were removed. These are native
runtime results, distinct from the ownership fixture using a launcher shim.

The [separate combined AMD64 browser audit](framey-syncthing-browser-5a66291-ci-2026-10-30.md)
retains the inspected Running/Stopped/Running/Stopped captures. It uses a private
test bridge and synthetic DOM input. The production-parent HTTP development
replay is separate and pending after retained failures. Production Steam CEF,
ARM64 browser, managed install/update/remove, real Frame visuals and physical
controllers remain unverified. Installation stays blocked. No release or real
Frame contact occurred. Postmerge main CI must pass before another merge.
