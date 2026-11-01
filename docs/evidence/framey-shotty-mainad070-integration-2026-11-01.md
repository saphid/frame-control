# Shotty evidence with ScreenSaver main — 2026-11-01

Implementation `4ab5232d8483be4584e3aa28bc7d8e8f4a5c7717` normally merges prior #498 head `b919306b786d738f60fec6fbb26400f20aee199b` and main
`ad070b731386dfbc2c8ed24b901b0b5edaeacbf2`. The merge had no conflicts. This PR records historical native
AMD64/ARM64 private copy evidence and updates only Shotty's reason, verification
and runtime-evidence fields. **All 116 versions/digests/ratings/install policies
and required shims**, and the other **115 complete catalog rows**, are retained.
An unrelated Prefix Manager wording change from the prior PR head was removed.
**1,749 other main files**, including production runtime, current CI, package
and ownership tests, remain byte-identical. All **31 native runtime inputs**
match main. Five historical Shotty evidence files retain their prior bytes.
The Shotty child IPC EOF update requirement and fresh ARM64 unload limitation
remain unchanged. Shotty stays partial.

## Fresh local verification

**111 focused tests / zero skips** passed, covering managed installation,
Shotty copy contracts, catalog compatibility, native inventory, child IPC and
official archives. Generated documentation and diff checks against exact main
pass. No runtime source changed, and this documentation refresh did not rerun
the full local fake-Frame e2e suite. Hosted exact-head e2e remains required.

Published **Decky 3.3.0 native AMD64** ran current case 53 in disposable,
networkless containers with no headset or host user data. The exact official
Shotty 0.1.0 ZIP is
`ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe`.
The positive case makes **17 legacy RPCs**: private cross-filesystem copies,
repeat copies, destination independence, conflict preservation, title confinement,
symlink and invalid-ID refusals, historical aggregation and discovery after
restart. Direct fixture byte/filesystem checks are bound to the committed
checker; no disk image is retained.

The independent audit reconstructs the exact production install block, verifies
the managed backend and IPC hashes, and preserves every other original archive
member. Two parent-only stops exit zero in **[0.214, 0.214] seconds**;
owned child identities are absent afterward, full stop consoles contain the
plugin-stopped and loader-finished messages, and no forced kill or listed
shutdown diagnostic appears. An unrelated sibling survives. Restoring the prior
managed source makes the same first **16 RPCs** pass but reproduces **one forced
plugin kill after five seconds**. This expected negative is explicitly
unqualified. Owned containers and the temporary image tag are removed.

Full native consoles, exact owned process identities, input hashes, test logs
and audit scripts are retained in the raw packet. The generic recorder's global
clean-shutdown flag remains false; only the separately audited Shotty lifecycle
has the scoped two-stop pass. No broader error-free/global shutdown claim is made.

## Historical attribution and remaining gates

The original [AMD64/ARM64 report](framey-shotty-native-architectures-2026-10-30.md)
remains tied to source `e26ae7fea77c7c8702fdcfc694f4f0186f80cf43` and its original
workflow/jobs. Its 16-RPC results lack raw consoles and do not prove fresh ARM64
unload. This fresh local AMD64 record does not extend those historical scopes.

Current final-head hosted CI, e2e, native AMD64/ARM64 and every triggered package
and ownership gate remain mandatory, along with exact current-main green,
mergeability and unresolved-feedback review. Neither a merge nor a release is
qualified by this packet. Managed real Frame installation, live Steam screenshot
notifications, continuous rescue, browser/backend integration, Steam CEF,
wearer-visible UI and physical-controller use remain unverified. No real Frame,
schedule, security setting, tag or pre-existing user data was touched.

[Summary](framey-shotty-mainad070-integration-2026-11-01.json) · [Raw observations and verifiers](framey-shotty-mainad070-integration-2026-11-01-raw.json.gz).
