# Shotty bounded screenshot copies, 30 October 2026

The exact official Shotty **0.1.0**, store ID **53**, remains pinned to SHA-256
`ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe`.
The original main.py SHA-256 is
`7c58aa5e273dca65ccfb59746f24b4d20edfd478b280fc8e08ff92dbe7d0d1be`.
A fresh official store read on 2026-10-30 confirmed that version/digest.
Its existing click shim repairs import, but its copy methods still use hard
links and put Steam-provided app names directly into destination paths.

## Reproduced failures

An isolated, temporary-home test installed the exact archive with the old
managed import shim and exercised its real Python methods. Four contracts
failed: `../../escaped` wrote outside Pictures/Screenshots, a repeated selected
copy returned false, a source symlink was accepted, and ambiguous account
matches wrote a destination before returning failure. All test files were
inside the owned temporary home. No real screenshot or headset was accessed.

## Managed change

Only that exact archive receives `shotty-bounded-copies`, in addition to the
existing `shotty-click-app-dir` receipt shim. The managed installer verifies
the original main.py, stages Frame Control's small Python copy module, and
changes the screenshot-copy methods. The upstream frontend, app-ID map and
LICENSE remain unchanged. Other archive digests receive neither adaptation.

- App names become bounded directory labels; separators and control characters
  cannot turn them into paths. Output remains under the actual user's
  Pictures/Screenshots. Parent directories and files are opened with held
  directory descriptors and no symlink following.
- Selected sources must be a unique account match for a numeric app ID and
  literal filename in Steam userdata. Sources must be owned regular files,
  at most 64 MiB, stable during reading; special files and symlinks are refused.
  A scan is capped at 10,000 matching screenshot candidates.
- Copies use independent bytes, supporting different source/output filesystems.
  An identical existing output is a successful repeat; different existing
  image bytes are preserved and the operation reports failure. Destination
  symlinks are preserved/refused. The fixed most_recent.jpg output can be
  atomically updated with the same captured bytes as the named image.
- The copy helper cleans only its own temporary output files after publication/failure.
  Historical aggregation no longer deletes pre-existing broken symlinks.
  The continuous rescuer uses the confined destination/copy code, and unload
  cancels and awaits its own task. Its global gamescope-file cleanup behavior
  is otherwise unchanged and is not verified here.

## Verification

The focused contract suite passes selected-repeat behavior, independent
source/destination bytes, preserved output conflicts, selected PNG copies, app-name confinement,
invalid IDs, source/file-parent symlink refusal, ambiguous accounts, oversized
and special sources, and cancellation of only the owned rescuer task. The
managed install test also checks the original LICENSE bytes and digest scope.

[Published Decky 3.3.0 x86_64 evidence](framey-shotty-bounded-native-2026-10-30.json)
uses a disposable unprivileged container without network, host devices, user
session or writable host mount. A separate Pictures tmpfs makes the test
assert that source and output have different device IDs. Actual legacy RPCs
pass selected/repeated copy, independent byte readback after source changes,
conflict preservation, unsafe title confinement, symlink and invalid-ID
refusal, and historical aggregation. Empty aggregation and rescue status
remain covered. The runner cleans its owned containers and image.

The same cross-filesystem fixture is in the native AMD64/ARM64 CI case. This
local result proves x86_64 only; the new ARM64 case must pass before merge.
The earlier [copy RPC evidence](framey-shotty-rpc-2026-10-28.md) used two files
on one filesystem; it did not cover these failures.

## Limits

Shotty stays **partial**. Existing managed installs need Update/reinstall to
receive this fix. Real Frame managed backend, live screenshot notifications,
continuous gamescope rescue, real user screenshots, wearer-visible rendering
and physical controller use remain unverified. The continuous watcher was not
started by the direct contracts; actual Decky starts it only inside the isolated
container. No release follows from these fixtures. All release gates and the
separate locked real-Frame smoke/worn schedule remain in force.
