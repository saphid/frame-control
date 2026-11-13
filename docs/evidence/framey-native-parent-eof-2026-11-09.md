# Published Decky parent EOF investigation

The unmodified published AMD64 Decky 3.3.0 loader stopped responding after
its synthetic plugin child was terminated. A normal shutdown control passed.
This extends the source-level parent-listener probe in #604 to the actual
published executable. It does **not** establish the cause of the historical
ARM64 migration timeout, reproduce that VM, or clear a release gate.

The [local receipt](framey-native-parent-eof-2026-11-09.json) records source
digests for the initial tested worktree. The [hosted receipt](framey-native-parent-eof-hosted-2026-11-09.json) records the same experiment on both native architectures at exact head `46d7c97cba305911bb4475e3aaf508164fb03afc`.

| Observation | Normal control | Abrupt child exit |
| --- | --- | --- |
| Published loader and synthetic plugin discovery/RPC | Passed | Passed before exit |
| Plugin child EOF repair | Installed | Installed |
| Parent implementation | Unmodified | Unmodified |
| Loader shutdown after parent SIGTERM | Exit 0 in 0.314 s | Still running after 8 s |
| HTTP request after child exit | Not requested | Timed out |
| Parent CPU while HTTP was stalled | Not applicable | 124 user CPU ticks |
| Forced cleanup | None | Exact recorded descendants only |
| Owned processes left after cleanup | None | None |

The fixture learns the plugin's PID through its own RPC, verifies that PID is
an exact descendant of its loader, and records `/proc` start ticks before
sending SIGKILL to that child. This models abrupt child exit; it does not
demonstrate which event occurred in the historical VM. The parent is then
given eight seconds to respond to SIGTERM. A separately bounded Python
process makes the HTTP/RPC check so a stalled loader event loop cannot stall
the diagnostic itself. Both the request's own timeout and the outer process
deadline are recorded separately.

All execution uses a disposable native container with no network, host
devices, audio, session bus or home directory. The repository and pinned
loader are read-only mounts. Cleanup signals only recorded PIDs whose start
ticks still match. The launcher removes only its unique container and its
own image; `--image` reuses and preserves an explicitly supplied local image.

Run on native Linux AMD64 or ARM64 with Docker:

```sh
python3 scripts/framey-probe-decky-native-parent-eof.py --output /tmp/native-parent-eof
```

Use `--loader /path/to/PluginLoader` for an offline cached copy. Both published
loader SHA-256 and ELF architecture are checked before execution. The native
CI matrix retains the complete report, console, exact-head receipt and source
digests. The diagnostic passes only when the normal control succeeds, the
published parent hang is observed, and owned processes are reaped. A passing
diagnostic reports a reproduced bug; it does not report repaired shutdown.

Hosted native execution reproduced the published parent hang on both architectures:

| Architecture | Normal SIGTERM exit | SIGTERM after abrupt child exit | HTTP after exit | Cleanup |
| --- | --- | --- | --- | --- |
| AMD64 | Exit 0 in 0.326 s | Still running after 8.000 s | Timed out | All owned processes reaped |
| ARM64 | Exit 0 in 0.214 s | Still running after 8.001 s | Timed out | All owned processes reaped |

The native diagnostic artifacts are `13646318727` (AMD64) and `13647022740`
(ARM64). The committed hosted receipt retains their verified archive digests,
producer job IDs, exact-head receipts, complete reports and loader consoles.
Both native runtime suites also passed 40 primary cases and 32 negative
controls; 53 hosted e2e tests passed without skips at that head.

The next investigation is retained loader logs and user-space stacks from an
actual migration-timeout reproduction. No production shutdown timeout or transport was changed. No
headset was contacted by this experiment. Exact-release locked Frame smoke,
worn visibility, controller input, scrolling and the VR keyboard remain
unverified.
