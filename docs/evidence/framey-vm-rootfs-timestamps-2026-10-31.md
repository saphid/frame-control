# Preserve Python caches in the isolated service VM

Base: `4e1f664be47b99fcf88c84d1280126c39d6753b4`.

The shared service/Flatpak/browser VM packer wrote zero into every newc member's
mtime field. Timestamp-based Python bytecode in the Debian rootfs still contained
the original source timestamp. Those caches therefore became invalid in the
guest. This is a fixture fidelity defect; it does not establish the cause of
Terminal #492's ARM64 HTTP timeout.

The packer now retains each tar member's whole-second timestamp. Generated
overlays and the gzip header retain their existing zero timestamp. Values outside
newc's unsigned 32-bit field fail explicitly. File contents, modes, ownership,
symlink targets and device numbers retain their previous handling. Every
module-level definition outside `pack()` is unchanged, checked independently by
AST comparison with the base.

## Deterministic regression

`tests/test_syncthing_rootfs_pack.py` creates timestamp-based bytecode, sends both
source and cache through the actual packer, reads newc independently, and restores
only its two known temporary files. Importing the restored module must succeed
while `SourceFileLoader.source_to_code` is set to fail. The old packer fails this
check; the corrected packer executes the cached module. This does not depend on a
timing threshold or writable Python caches.

The three tests also check fractional timestamp conversion, metadata, regular
files, symlinks, hardlinks, directories, character devices, generated overlays,
and rejection of negative/overflow timestamps. Against the base they produce
eight assertion failures; against the fix all three pass.

## Actual Debian VM controls

Two separate owned, networkless AMD64 QEMU/TCG VMs boot the same cached Debian
rootfs with the original and corrected packers. Both use the production
`normal_root=True` init path, including tar copy and `switch_root`. A child drops
to UID/GID 1000 and requests compiled code for `http.client` and `email.parser`
using guest Python 3.13.5, with source compilation forbidden.

Both Debian bytecode headers contain source timestamp `1786363619`; the source
sizes are 58,613 and 4,975 bytes. With the original packer, both sources have
mtime zero and both lookups fail because recompilation would be required. With
the fix, both retain `1786363619` and both code lookups succeed without compiling
source. This verifies cache lookup in the actual guest; it does not execute the
HTTP/parser modules or run Terminal's browser replay.

Both QEMU processes exit zero and are reaped. Their owned temporary boot files
are removed. No host devices, user homes, session buses, network interfaces or
existing user data enter either guest. An initial standalone helper omitted an
explicit `importlib.util` import and produced no cache verdict; its failed log is
retained, and both controls were rerun after the helper-only correction.

## Validation and limits

- Full server suite: 1,952 tests in 249.378 seconds; successful with 16 existing
  platform/optional skips.
- Website: all 18 tests pass, with no skips.
- Exact source hashes, rootfs hash, per-module results, cleanup observations and
  console hashes are in the [audit record](framey-vm-rootfs-timestamps-2026-10-31.json).
  [Raw logs and the standalone VM helper](framey-vm-rootfs-timestamps-2026-10-31-raw.json.gz)
  retain the original negative and fixed positive.

No ARM64, full package, browser, real Steam CEF, wearer/controller or headset
usability pass follows from these controls. Terminal #492 still needs its own
exact-source ARM64 replay. No production RPC deadlines, input behavior, package
receipts, security settings, compatibility claims or release versions changed.
The real Frame and hourly schedules were untouched; this does not publish a release.
