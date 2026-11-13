# SteamOS 0.5.6 compatibility check, 25 October 2026

The real Frame was accessed **after** the 00:00 AEDT hold, under a separately
acquired `/tmp/frame-test.lock`. The coordinator had finished its v0.4.19 smoke
test and released its lock first. This check took place approximately 00:04–
00:08 AEDT (13:04–13:08 UTC). A device clock reading in the first snapshot was
**00:04:58 AEDT**. The one temporary capture was removed and our lock was
released. Steam and SteamVR were left running.

| Check | Observation |
|---|---|
| OS | `VERSION_ID=0.5.6`, `VARIANT_ID=vr`, `BUILD_ID=20261022.6153909` |
| Update channel | `atomupd-manager tracked-branch` returned `beta`; tracked variant `vr`; update status `idle`. `atomupd-manager status` and `check` returned D-Bus `AccessDenied` to the normal user. No root, update, or channel change was attempted. |
| Discovery | `frame.local` and a sample `frame-0000.local` name were unresolved from the Linux host. Avahi was active on the Frame, but `/etc/avahi/avahi-daemon.conf` has `publish-addresses=no`. The configured `ssh frame` alias worked. The host reached the Frame over Tailscale, so a local-subnet scan and same-LAN cached-IP reconnection were not exercised. |
| Script fallback | `steamos-session-select` was present and `holo-session-select` absent. The installed devkit utilities contained `steamos-prepare-upload` and `steamos-delete`; their `holo-*` replacements were absent. No session switch, install, or delete command was run. |
| Battery and memory | Frame Control's `ui/frame_status.py` returned a system battery at 98%, Charging, with its source under `/sys/class/power_supply/max1720x_bat_7-36`; memory was 16,422,952,960 bytes total and 11,256,848,384 bytes available. The battery was 97% at the initial raw sysfs check and 98% at the final check while charging. |
| Recording source | The user `steamvr-v4l2cam.service` and `/dev/video99` were present. A single frame from that device was black while the unworn headset was in standby. Frame Control's MP4 path reads that same SteamVR `system.HeadsetView` mirror and never opens a passthrough camera. Active passthrough inclusion in the mirror remains unverified. The sample image was not retained or published. |
| Dominant eye | Neither standard `steamvr.vrsettings` path checked had a readable dominant-eye setting. No source or effect on the mirror was verified; Frame Control does not attach dominant-eye metadata. |

This was a bounded compatibility check, not a rerun of the coordinator's
13-step smoke test. The coordinator reported that smoke passed on this same
build, with battery 95% to 96% while charging and cleanup complete.
