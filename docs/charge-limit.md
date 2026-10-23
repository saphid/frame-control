# Battery charge limit (80%): research

**Question:** can Frame Control set an 80% battery charge limit on the Frame
over SSH or adb, safely?

**Verdict: don't build it yet; it needs a headset check.** Valve's supported
mechanism (the one Steam's own charge-limit setting uses on the Deck) is not
configured for the Frame. The only control the Frame seems to have is a
vendor charger attribute that Valve's own charging daemon also manages.
Research as of 2026-10-23. **Not tested on a headset.**

## How Steam does it on other devices

- Steam's **Settings → Power → Battery Charge Limit** shipped to the Deck in
  SteamOS 3.7.8 (beta client 2025-05-08)
  ([GamingOnLinux](https://www.gamingonlinux.com/2025/05/steamos-3-7-7-beta-brings-a-battery-charge-limit-option-and-improved-lenovo-legion-go-s-support/)).
- Steam calls SteamOS Manager on the session bus:
  `com.steampowered.SteamOSManager1.BatteryChargeLimit1`, with properties
  `MaxChargeLevel` (`i`, read/write; `-1` resets to the default) and
  `SuggestedMinimumLimit` (`i`, read-only). The CLI is
  `steamosctl get-max-charge-level` / `set-max-charge-level` /
  `suggested-minimum-charge-limit`. Source: `data/interfaces/com.steampowered.SteamOSManager1.xml`
  and `steamos-manager/src/bin/steamosctl.rs` in
  [holo/steamos-manager](https://gitlab.steamos.cloud/holo/steamos-manager),
  read at commit `83981ab` (2026-10-21).
- The root daemon writes the value to sysfs only if the device's TOML in
  `data/devices/` has a `[battery_charge_limit]` section. Two methods exist
  (`steamos-manager/src/power.rs`, `BatteryChargeLimitMethod`):
  - `hwmon_attribute`: the Deck writes `max_battery_charge_level` on
    `steamdeck_hwmon` (`data/devices/steam-deck.toml`).
  - `acpi_sb`: ROG Ally, MSI Claw and others write the standard
    `charge_control_end_threshold` on the ACPI battery
    (`/sys/bus/{platform,acpi}/drivers/…battery…/PNP0C0A:00/…/power_supply/*/`).
    On ARM there's no ACPI, so this path can't match there either.
- With no `[battery_charge_limit]` section, the interface fails with
  `UnknownInterface` (Steam can still show its toggle on unsupported hardware:
  [steam-for-linux#12044](https://github.com/ValveSoftware/steam-for-linux/issues/12044)).

## What the Frame has

- **Upstream `data/devices/steam-frame.toml`** (matched by
  `dt.compatible = "qcom,sm8650"`, variant `Deckard`) configures GPU clocks
  and performance profiles only. It has **no `[battery_charge_limit]`**, so
  SteamOS Manager on the Frame has no charge-limit backend. Its git history
  (2026-09-10 to 2026-10-12) never added one.
- **Battery driver:** the Frame's battery is
  `/sys/class/power_supply/max1720x_bat_7-36`, and the charger is a
  `tcpm-source-psy-…` USB-PD supply ([how-the-frame-works.md](how-the-frame-works.md)).
  Both were verified 2026-09-25, and `ui/frame_status.py` `battery()` and
  `power_source()` read them. The Maxim MAX1720x is a **fuel gauge** and
  can't control charging. Mainline `drivers/power/supply/max1720x_battery.c`
  exposes only read-only properties (capacity, voltage, current, temp,
  charge_full…), with no `charge_control_end_threshold`. Valve's build is
  patched: it reports `time_to_full_now`, which mainline doesn't have. Even
  so, a charge stop would have to come from the separate charger IC, not this
  node.
- **Not the qcom_battmgr path.** Some other SM8650/SM8750 handhelds get
  `charge_control_end_threshold` from Qualcomm's `qcom_battmgr`
  (pmic_glink) driver, clamped at 55% or above. A third-party distro enabled
  Steam's limit on those by patching steamos-manager
  ([armada-os/armada#758](https://github.com/armada-os/armada/pull/758)). The
  Frame's battery isn't exposed by `qcom_battmgr`, so that doesn't carry over.
  (Unverified: whether a `qcom_battmgr` node also exists on the Frame. The
  read-only checks below answer this.)
- **What third parties found:**
  [y0usaf/frame-charge](https://github.com/y0usaf/frame-charge) reports that
  the Frame has no `charge_control_end_threshold` and falls back to a vendor
  `charging_pause` attribute. It also reports that `constant_charge_current`
  changes on its own, which it attributes to Valve's `deckard_charge_daemon`
  (`deckard-charger.service`). By its own README, that tool has only run its
  read-only `status` on a Frame and has **not** been tested against real
  charging. Two questions are still open: whether pausing stops the current,
  and whether Valve's daemon undoes it.

## Why not build it now

- **No supported endpoint.** The only Valve-supported interface,
  `BatteryChargeLimit1`, isn't backed on the Frame. Writing sysfs ourselves
  would bypass Steam and SteamOS Manager, and it needs root (`sudo -S` with
  the user's password).
- **A rival owner.** Valve's charge daemon already adjusts charging
  parameters. Toggling `charging_pause` underneath it could be undone without
  warning, fight it in a loop, or leave charging paused.
- **Stuck at a low charge.** If the app or the Frame dies while charging is
  paused, the Frame could sit at a low charge on the charger. Whether a
  reboot clears `charging_pause` is unknown.
- **The UI would mislead.** Steam's setting (if it shows at all) wouldn't
  reflect our limit.
- **adb doesn't help.** Wi-Fi adb (`frame:5555`) reaches the Lepton Android
  container only. USB-C adb reaches the Linux side as `steamos` (non-root, the
  same as SSH, [ssh.md](ssh.md)). Neither adds a charging-control route.
  Android's `dumpsys battery` in Lepton is a container view, not the hardware.

**Revisit when** a SteamOS update adds `[battery_charge_limit]` to
`steam-frame.toml` (or `steamosctl get-max-charge-level` stops returning
`UnknownInterface` on the Frame). Then the feature is just a SteamOS Manager
call:

- Read: `steamosctl get-max-charge-level`
- Set: `steamosctl set-max-charge-level 80`
- Undo: `steamosctl set-max-charge-level -- -1`

That runs as `steamos` with no sudo. It's the same value Steam's own
Settings → Power shows, so both stay in sync.

## Headset checks (read-only first)

Run these over SSH as `steamos`. Steps 1–4 only read.

```sh
# 1. Does SteamOS Manager offer the interface on this build?
steamosctl get-max-charge-level; steamosctl suggested-minimum-charge-limit
busctl --user introspect com.steampowered.SteamOSManager1 \
  /com/steampowered/SteamOSManager1 | grep -i -A3 ChargeLimit
grep -n battery_charge_limit /usr/share/steamos-manager/devices/*frame* 2>/dev/null

# 2. Which power supplies exist, and which drivers back them?
for d in /sys/class/power_supply/*; do
  echo "== $d ($(cat $d/type)) driver=$(basename "$(readlink -f $d/device/driver)" 2>/dev/null)"
  ls $d
done

# 3. Any charge-control attributes, with their values and permissions?
ls -l /sys/class/power_supply/*/{charge_control_*,charging_pause,charging_enable,constant_charge_current*,charge_behaviour} 2>/dev/null
grep -H . /sys/class/power_supply/*/{charge_control_*,charging_pause,charging_enable,constant_charge_current*,charge_behaviour} 2>/dev/null

# 4. What is Valve's charger daemon, and what does it touch?
systemctl status deckard-charger.service --no-pager
systemctl cat deckard-charger.service
journalctl -b -u deckard-charger.service --no-pager | tail -50
```

If step 1 succeeds on some build, test `steamosctl set-max-charge-level 80`
on a charger at a charge above 80%. Watch `current_now` on the
`max1720x_bat_*` node fall to about 0, then `steamosctl set-max-charge-level -- -1` and
confirm charging resumes. Do this on a supervised Frame only. If only step 3
finds a vendor attribute, **stop**: don't write it, and leave the question
with Valve.

## Sources

- steamos-manager source, commit `83981ab` (2026-10-21):
  `data/devices/steam-frame.toml`, `data/devices/steam-deck.toml`,
  `data/interfaces/com.steampowered.SteamOSManager1.xml`,
  `steamos-manager/src/power.rs`, `steamos-manager/src/manager/user.rs`.
  [gitlab.steamos.cloud/holo/steamos-manager](https://gitlab.steamos.cloud/holo/steamos-manager)
- Mainline [`max1720x_battery.c`](https://github.com/torvalds/linux/blob/master/drivers/power/supply/max1720x_battery.c)
- [ValveSoftware/steam-for-linux#12044](https://github.com/ValveSoftware/steam-for-linux/issues/12044):
  the Steam toggle shows on unsupported hardware
- [armada-os/armada#758](https://github.com/armada-os/armada/pull/758):
  `qcom_battmgr` threshold on other SM8650/SM8750 devices
- [y0usaf/frame-charge](https://github.com/y0usaf/frame-charge): third-party,
  untested on real charging
- [GamingOnLinux: SteamOS 3.7.7 beta charge limit](https://www.gamingonlinux.com/2025/05/steamos-3-7-7-beta-brings-a-battery-charge-limit-option-and-improved-lenovo-legion-go-s-support/)
- Repo: [how-the-frame-works.md](how-the-frame-works.md) (battery and
  charger nodes), [ssh.md](ssh.md) (adb scope), `ui/frame_status.py`
