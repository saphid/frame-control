# Surround host fixture repair and main integration

Implementation `99f87abefa46963ae2852ace1f680c26e00932f6` integrates main `89757d33f61124486404bc16e84b7d3697cf2c9f`
with a normal merge and fixes the two first-head CI fixture errors.

The Windows host attempted a POSIX installer transaction that creates an exact
remote `/tmp` receipt and uses ownership/symlinks. These nine tests now have the
same explicit Windows exclusion as the underlying store transaction. This is
not Windows backend runtime proof; the installed plugin runs in native Linux
Decky. Python 3.9 evaluated the published plugin's Python 3.10 union
annotations while importing the backend for a host-side fixture. The fixture
now compiles with postponed annotations. Installed archive bytes and native
execution remain unchanged. The failed job logs and hashes are retained in
the compressed companion; neither failed job is counted as a pass.

After main integration, all nine focused tests pass on both Python 3.9.25 and
3.12.3, and three native inventory tests pass. Compilation/diff checks pass.
The production helper, installer and private Surround native probe remain
byte-identical to prior publication `9917ac1359e626527e664b6366dc1845b9b551f4`. Of the
29 native input hashes, only the shared checker changed, by main's TabMaster
recovery patch; that exact patch reverse-checks cleanly. Prior full unit/native
proof remains attributed to its original source, not relabeled this head.
Fresh exact-head hosted Windows/Python 3.9, full CI, native AMD64/ARM64, e2e and
applicable package/ownership gates are still required before merge. Sound-test
completion, physical audio, actual Frame dependencies, rendered controls and
worn/controller behavior remain unverified. No headset or schedule was touched
and no release is qualified.
