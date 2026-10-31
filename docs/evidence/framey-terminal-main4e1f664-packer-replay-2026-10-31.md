# Terminal current-main replay with timestamp-preserving VM packing

Tested source `c5fccb3088d2e87b1549490f742813e716a6faf0` follows normal merge `24f51f50e6f2c01171b8816b8a5619c7745e6f47`
of #530 runtime head `d4c4fa94775d3e5a188ba1bf5a334713517842e2` into #492's prior head `abbc6bb3bfb7fd1a6b78dc97e4dac87a6300f4b2`, then corrects
the private fixture call to the required shared-Client transcript. It includes current main `4e1f664be47b99fcf88c84d1280126c39d6753b4` and remains
stacked on #490. #530's complete hosted qualification remains an explicit
dependency; this test integration does not merge that PR into main.

## Fresh AMD64 replay

The existing production-HTTP replay passes in an owned, networkless QEMU/TCG
Debian VM with the cached browser rootfs and digest-pinned published Decky 3.3.0
AMD64 loader. All **168 guest source hashes**, reconstructed archive, generated
panel/bootstrap, official archive/frontend and guest result packet independently
verify. Eight guest inputs changed for current main, the packer and private Client call; the other
160 remain byte-identical to the prior Terminal head. Production Terminal
parent/panel/method/event/SSH/browser/candidate paths remain unchanged. The private lifecycle fixture now passes and retains the required shared-Client transcript. Inherited
status/UI changes from the Terminal stack remain unchanged as well.

Textarea, shell output and removal stages complete without page errors. There
are **20 successful HTTP requests**:
**14 methods**, **6 event polls**, and
**4 delivered events**. Maximum HTTP duration is
**5.396 seconds**. The original synthetic CEF trace succeeds;
the private output marker and marker-file hash match. No failure-only diagnostic,
deadline change or failed-mutation retry is used. All three captures were visually
inspected; horizontal overflow remains and this is not a broad UI-usability pass.

The iframe retains its sandbox; renderer Seccomp/no-new-privileges observations
verify. HTTP handlers drain to zero. Owned browser target, shell, event listener,
HTTP server and Decky service stop; the observer/private bundle are removed and
the original unit restored. The service reports inactive/success/PID zero.
Its mixed stop takes **3.263 seconds**.
This does not prove clean shutdown for every plugin. The owned user manager
stops, QEMU is reaped, and only generated boot artifacts are removed. The cached
rootfs, host user data and other sessions remain untouched.

## Initial integration failure and correction

The first combined-source VM run failed before browser work because the private
Terminal lifecycle called `Client(name)` after main made its transcript argument
required. That failed result, old packet and owned cleanup remain retained; no
pass is credited to it. The fixture now supplies and retains its transcript in
success and failure evidence. A source AST audit proves that the transcript is
its only behavior change; the successful corrected native replay executes the
real shared client and independently verifies its successful RPC/event transcript.
The initial owned local unit run was stopped for this correction and is not
credited; the full suite below ran afresh on the frozen corrected source.

## Integration and regression evidence

Full server suite: **1,975 tests**, successful with **16
platform/optional skips**, **259.951 seconds**. Website: **18 tests**, no skips.
Main's complete catalog, all 116 install/status policies, installer, 34 positive
native cases, shared adapter/console, Timer helpers and e2e assertions match.
Removing only prior Terminal additions reconstructs main's complete checker and
runner. Packer and regression tests exactly match #530; no new production
deadline, input, compatibility or release change is introduced by this merge.

The full-range whitespace check excludes only one unchanged historical raw
carriage-return console transcript. Its exact prior bytes and hash are preserved
and independently checked; new changes pass whitespace checks. Generated docs pass.

## ARM64 and release limits

Prior #492 ARM64 job 124590135092/artifact 13049393574 remains a failed
observation: production get_terminal returns HTTP 503 after 30.095 seconds.
Its original CEF trace has nine successful calls, including a 139-ms native
get_terminal, but no subscription or output. The independently audited old
failure/packet is retained in raw evidence. A new exact-source ARM64 browser
replay is required; this AMD64 pass neither proves the cause nor resolves it.

Fresh exact final-head CI/e2e/native AMD64+ARM64, both browser replays, ownership,
applicable PC, every triggered package mode, completed current-main CI, #490
stacked-parent/#530 dependency qualification, feedback and mergeability remain
required. Full e2e/native matrix did not run locally. Official managed Terminal
stays partial; this is a private candidate with synthetic CEF, receipt and input.
No real Steam CEF, Frame, wearer-visible display, controller, tagged installer or
release proof follows. Headset and schedules untouched. Release remains held
until every exact release-commit gate and locked real Frame smoke passes.

[Audit](framey-terminal-main4e1f664-packer-replay-2026-10-31.json) and [raw replay, historical failure, logs, packets and verifiers](framey-terminal-main4e1f664-packer-replay-2026-10-31-raw.json.gz).
