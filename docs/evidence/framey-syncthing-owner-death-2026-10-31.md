# Syncthing helper lifetime after forced plugin exit — 2026-10-31

The [AMD64 ownership job for #501](https://github.com/saphid/frame-control/actions/runs/41158034008/job/124409075172)
failed at exact head `fd3b66162fadb2e7a442fd0ee220de445a1f68c1`.
Decky reported that the plugin stayed alive for five seconds after its stop
request, sent SIGKILL, then the next helper could not acquire its ownership lock.
The reason the original plugin did not finish unload remains unproven.

Published Decky **v3.3.0** implements this five-second fallback in
[`plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/v3.3.0/backend/decky_loader/plugin/plugin.py).
The candidate's helper starts a separate session and previously depended on
Python `_unload` to stop it. Killing the plugin can bypass that callback and
leave the helper alive with the lock.

## Reproduction and repair

The unchanged candidate rebuilt with the exact CI Rust image and pinned sources
produced SHA-256
`bef65e425ff895dd40e932fdae424376988e6abed17a9527e4eda383002a578d`,
identical to the failed job's helper. In a disposable, networkless native AMD64
container, the published loader completed three normal reloads. The probe then
paused only the owning plugin, causing the loader's actual five-second SIGKILL
fallback. Reload failed with the same ownership error. This deliberately forces
the failure path; it does not reproduce the original reason unload stalled.

The helper now sets Linux `PR_SET_PDEATHSIG` so it dies if its spawning plugin
thread exits. Python supplies its PID before fork/exec; the helper checks that
its parent still matches before touching ownership, PID, settings or logs. An
invalid or changed parent is refused. A 500 ms lock retry budget permits the
kernel to finish a killed predecessor without bypassing a foreign lock. No
PID-file or executable-name signaling is introduced, and dependencies stay locked.

The corrected AMD64 helper SHA-256 is
`318c0c58bce164d5e23528ae0da40f7d142005984ff64801b74a36b790e456b0`.
Both actual-runtime reports independently match those helper bytes and every
listed production source fingerprint.

## Verification

- Published Decky 3.3.0: disabled defaults, private HTTP/error handling, foreign
  listener/unit/PID preservation, duplicate ownership refusal, owned restart,
  three normal reloads, and a forced plugin kill followed by successful reload.
  The final report retains and asserts the loader's SIGKILL console message.
- Actual pinned Syncthing **v2.1.7** peers: two-way private file sync, restart
  preserving files, completion=100, Decky RPC REST reads and a real 403 for the
  wrong fixture API key. Both peers stopped normally; all owned processes reaped.
- Full host unit suite: **1,912 tests**, successful with **16 platform/optional
  skips**, in 257.262 seconds. The focused ownership suite passed all **19** tests.
  Python compilation, fuzz-free patch application and `git diff --check` passed.

The probe uses Docker init to reap orphaned children. It explicitly removes the
private temporary socket directory of the deliberately killed Python owner after
proving the old helper exited. The kernel guard does **not** promise filesystem
cleanup after SIGKILL. Disposable containers and their data were removed, along
with the owned prepared test-image tag. Public build inputs and proof files were
retained locally for reproducibility.

## Limits

Base: `08bd8473b18c3d246a9c96d5e7a17ff4acaa3733`. This local proof is native AMD64.
Native ARM64, final hosted head CI, systemd VM lifecycle and signed Flatpak
package qualification remain required; they were not rerun locally for this
helper. The peer test uses private raw Syncthing processes, not a managed Flatpak
install. Browser rendering, the real Frame, worn VR and controller use are
unverified. No headset was contacted or sent input.

Syncthing remains blocked and unselected by the managed installer. All 116
catalog ratings, installer policy and compatibility-table claims match main.
No release is published by this fix.

[Full build/runtime records and source hashes](framey-syncthing-owner-death-2026-10-31.json).

## Hosted qualification and startup repair

At original PR head `8c271df55b9d8ec0a80ac82df4ec9a0875a9fab9`, the
[AMD64 ownership artifact](https://github.com/saphid/frame-control/actions/runs/41160719889/artifacts/13026764127)
and [ARM64 ownership artifact](https://github.com/saphid/frame-control/actions/runs/41160719889/artifacts/13026679896)
passed independent ZIP-digest, exact-checkout and 14-source-fingerprint checks.
Both retained Decky's real forced-kill/reload evidence, private raw-peer sync,
17 systemd service assertions and strict owned Decky shutdown. The built helper
and full native Decky console are not retained; those checks remain source-bound.

The [AMD64 signed-package job](https://github.com/saphid/frame-control/actions/runs/41160719979/job/124417438844)
failed before two-way sync. Its
[artifact](https://github.com/saphid/frame-control/actions/runs/41160719979/artifacts/13027501834)
matches SHA-256 `1a257b6a79091e254c83bda6563356c6be6d00541624e803c24afc3e8c3d5b49`,
the failed checkout, all 26 exact-head fingerprints and all 13 input fingerprints.
The VM console and retained guest result agree: signed bundles installed, but
peer 0 could not find `/run/user/1100/.flatpak/me.kozec.syncthingtk/tmp`.
The private service, processes and VM were cleaned. The precise path-removal
actor and timing remain unproven. This failed gate must not be dismissed by
rerunning the unchanged head.

The [browser HTTP](https://github.com/saphid/frame-control/actions/runs/41160719979/artifacts/13027741548)
and [production-parent HTTP](https://github.com/saphid/frame-control/actions/runs/41160719979/artifacts/13027317666)
modes passed independent artifact-digest, successful exact-checkout,
source-fingerprint, full guest-result, migration/preservation and strict
owned-shutdown checks. Parent running/restarted/final-stopped captures were
visually inspected: the running states show the private folder and Devices;
the final stopped state removes those sections. Inputs, CEF and store receipts
are synthetic. These two passing modes do not override the AMD64 failure.

PR #506 landed as main `6a5646e9da7f36ed45c840c3fe7190f2172e86ad` and
serializes private-peer startup. It is merged into this branch without rewriting
history. The inherited startup probe matches that main source exactly; the
owner-death helper, patch and native candidate probe remain byte-identical to
the original PR head. All 60 focused ownership, signed-package gate and fetch
tests passed locally after the merge. This local run does not establish package
runtime success. Fresh hosted qualification is required for the updated head.

At this record's preparation, the original ARM64 package job was still running;
its outcome and all updated-head gates remain unverified. No real Frame,
wearer/controller behavior or managed installation is proved by these results.
