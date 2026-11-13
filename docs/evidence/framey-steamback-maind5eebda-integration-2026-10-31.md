# Steamback current-main integration verification

Tested source: `42affd87661c6cc3d22acf82a6c93d67f52b7c98`. Current main `d5eebdac850bdedaf0472dc1bbc93afede17c710` is its normal merge parent.
The one conflict in the native fingerprint list retains Steamback, DeckyParty and
TabMaster helpers. Independent whole-checker and installer AST comparisons preserve
main outside the Steamback repair; all 116 compatibility ratings/install policies,
other 33 native cases, and mandatory full-catalog CI remain preserved.

Local server suite: 1963 tests, 15 platform/optional skips.
Website: 18 tests, no skips. Published Decky 3.3.0 on AMD64 executes ten
fixture cases: Steamback repaired/original, three TabMaster, three Simple Timer and
two DeckyParty controls. All 22 exact source hashes match the tested source.
Independent audits verify Steamback's 11/9 RPCs, published archive/member hashes,
managed installation/receipt, original unload hook, clean repaired parent-only stops,
private save/backup/undo snapshot bytes and restart. The original forced-kill control
remains a deliberate failure. TabMaster 47/48/47, Timer 31/10/18 and DeckyParty 15/8
RPC transcripts are independently audited. Generic clean-runtime flags remain false.

An isolated Fake Frame transport run passes 53 tests with zero skips in
405.600 seconds. All 116 exact catalog archives are mounted read-only;
69 installs/removals and 47 refusals match the previous main integration individually.
Catalog transport does not execute every official plugin backend.
Owned containers, networks, volumes, images and temporary configuration are removed.
Independent cleanup readbacks preserve the pre-existing simulator and image tags.

This packet records local execution at the tested source. Publishing it changes
only evidence files; it is not execution of its eventual publication commit.
Fresh exact-head hosted CI/native ARM64/packages and fresh merge gates remain required.
Compatibility stays partial. Automatic backup triggers, real Steam saves, managed
Frame backend, official UI, wearer-visible/controller behavior and release smoke
remain unverified. No real Frame or schedule was touched.

The gzip retains reports, private fixture snapshots, logs, source audits and verifiers.
