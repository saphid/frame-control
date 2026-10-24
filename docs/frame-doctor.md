# Frame doctor

Run `scripts/frame-doctor.sh` from a checkout on macOS or Linux to diagnose
first-time setup, pairing and common Frame failures without applying repairs.
It needs Bash, Python 3 and OpenSSH on the computer, and Python 3 on the Frame.
Windows users can run `python scripts/frame_doctor.py` with Python and OpenSSH
installed; the desktop app does not bundle this command.

```sh
scripts/frame-doctor.sh
scripts/frame-doctor.sh --alias bedroom --lan frame.local
scripts/frame-doctor.sh --alias frame --lan 192.168.1.40
```

Use only addresses belonging to your intended headset. The command tries the
existing `frame` SSH alias first (Tailscale if setup configured it that way),
then `frame.local`, then USB-C at `10.86.200.233`. `--alias`, `--lan` and `--usb`
override those defaults. It reports the successful path without printing its
address. It neither discovers other devices nor enables Tailscale.

The existing alias supplies the user, port, keys and known-hosts file. LAN and
USB overrides preserve its `HostKeyAlias`, or its configured hostname if no
alias was set. A first connection therefore needs trusted setup first. The
doctor never accepts a new host key, deletes a saved key, generates keys or
sends a pairing request. It uses your trusted OpenSSH configuration; OpenSSH
can evaluate `Match exec` conditions in that configuration. Proxy commands,
jumps, local commands, forwarding and connection sharing are disabled for
these direct diagnostic connections.

## Reading the result

Each of the eleven runbook sections has one line: `OK`, `WARN`, `BROKEN` or
`UNKNOWN`. `OK` means only that the stated check passed, not that the whole
feature works. Optional features that are off may produce a warning.

| Section | Read-only evidence and limits |
|---|---|
| 1. Boot and crash history | Previous-boot kernel-oops signatures; one day of coredump history. An oops alone does not prove an unclean reset. |
| 2. Wi-Fi | NetworkManager's wlan0 state, without SSIDs or connection profiles. |
| 3. Displays and SteamVR | DSI timeout signatures in the recent kernel journal; no display, compositor or game is launched. |
| 4. Steam and storage | Free space in home and `devkit-game`, including separate mounts; missing Steam install marker. No CRC scan or restart. |
| 5. Idle sleep and keep-awake | Existing keep-awake unit state; never takes ownership or changes idle timers. |
| 6. Remote wake | WoWLAN state, without arming it or testing suspend. Wake with the power button. |
| 7. Lepton | Recent port-clash, binder and data-clearing signatures; no Android/container commands. |
| 8. Chromium XR | Crash history; no browser profile or environment inspection. |
| 9. KDE Connect | Process presence; absence is normal when sharing is off. |
| 10. Streaming and capture | ffmpeg crash history; no capture or encoder is started. |
| 11. Panels | Always `UNKNOWN`: placement requires the user's visual confirmation. |

Journal samples are capped at 2,000 entries; current-boot samples cover the
last ten minutes. This can miss older or high-volume failures. Empty,
inaccessible or permission-limited journals are `UNKNOWN`, never zero errors.
Commands time out individually, and each SSH probe is bounded to 90 seconds.

Exit codes: **0** if all reported checks are OK; **1** for warnings, broken or
unknown checks after connecting; **2** if no authenticated SSH path exists or
local SSH setup is unavailable. Panel verification currently means a connected
run normally exits 1. Automation should read the labelled checks rather than
treating a warning as proof the headset is unusable.

## First-time setup and pairing

- **No SSH response:** wake the headset with its power button. Check the cable
  or Steam Settings → Internet, then enable Developer Mode. Sleep and network
  failure can look alike; a timeout cannot distinguish them.
- **Key rejected:** open **Set Up Connection** in Frame Control. In the headset,
  open Steam Settings → Developer → **Pair new host**, then approve setup's
  request. The doctor only checks whether devkit port 32000 responds; that
  does not prove pairing mode is open or the service is healthy.
- **Unknown or changed identity:** verify the intended headset through setup
  or Devices → **Check its key**. Do not delete `known_hosts` to bypass this.
- **No devkit response:** check Developer Mode and the address. See
  [SSH setup](ssh.md) for the manual fallback. The doctor cannot turn SSH on.

No password is requested. Enter any password required by the separate setup
flow only in its local terminal; never paste it into an issue or report.

## Restart safety and recovery

Before deeper checks, and again afterwards, the doctor samples Steam and
SteamVR `NRestarts` and health-check tracker sizes two seconds apart. Rising
counters stop diagnostics immediately. Nonempty health-check trackers also stop
deeper checks even when stable, since a short sample could miss a slower loop.
Missing counters or counters that reset stop deeper checks as `UNKNOWN`. Stable
counters with empty trackers still cannot rule out a slower restart loop.

The [historical runbook from PR #33](https://github.com/saphid/frame-control/blob/cce3d940302054ab5246c92d740afaefc4e58d38/docs/frame-doctor.md)
is the source for these section numbers and observed signatures (September
2026 builds). Its section 4 describes freezing and verifying health-check
trackers before prolonged recovery during a live loop. That changes headset
state, so this read-only implementation stops and directs you there instead.
It does not implement issue #34's automatic fixes, before/after repair runs,
or full recovery automation. Review build-specific recovery instructions with
the person using the headset; a repair can remove data.

Never reload `ath12k`, suspend remotely, kill gamescope to diagnose a loop,
reset or force power off during extraction/repair, or write passwords to disk.
The doctor never restarts services, signals processes, repairs Steam, changes
WoWLAN/standby settings, takes keep-awake ownership, installs anything or writes
a report. Nothing needs restoring after its checks. Manual/device tests must
follow the [shared-device lock and battery procedure](testing.md#headset-smoke-test).

## Privacy and verification

Only fixed diagnostic summaries leave the remote probe. Raw journals, process
arguments, environment variables, SSH errors, account IDs, network addresses,
SSIDs, keys and tokens are not printed. No telemetry or HTTP request is sent;
the only pairing-service probe is a TCP connection. SSH produces normal access
logs. Review summaries before sharing them; feature availability can still be
personal information. Redirecting stdout saves a report only if you choose it.

Unit tests use mocked boundaries. `scripts/e2e.sh test_doctor` covers asleep,
disk-full, SSH/devkit-off and missing-key faults against the fake Frame. Its
stable restart counters are explicitly simulated, not proof about SteamOS.
No real-headset validation is claimed for this implementation.
