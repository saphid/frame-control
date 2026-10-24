# Battery and health monitoring

Open **Control Center → Battery & thermal health**, or expand **System
information**, to read the Frame's charge, charging state, signed battery
power, battery temperature and driver-reported health. Optional readings show
charge cycles, full charge capacity, design capacity and full / design capacity.
The existing battery chip also shows charging state and temperature.

These are read-only readings from the Linux host's `/sys/class/power_supply`,
not Android's container battery view. The probe prefers the documented Frame
fuel gauge, `max1720x_bat_7-36`, over other battery nodes, excludes peripheral
(`scope=Device`) and absent batteries, and otherwise uses a deterministic
battery fallback. The UI shows the selected source path.

| Reading | Linux attribute | Interpretation |
|---|---|---|
| Charge | `capacity` | Integer 0–100 percent; zero is a real reading |
| Charging state | `status` | Charging, Full, Discharging or Not charging; missing/unknown states stay unavailable |
| Battery power | `voltage_now × current_now` | Microvolts and microamps converted to signed watts; positive means charging on the Frame |
| Temperature | `temp` | Tenths of a degree Celsius, including valid negative readings |
| Battery health | `health` | Driver status such as Good or Overheat; not a wear percentage |
| Charge cycles | `cycle_count` | Driver-reported count, including zero |
| Full/design capacity | `charge_full`, `charge_full_design` | Microamp-hours converted to mAh |
| Full / design capacity | Ratio of those two capacities | Fuel-gauge estimate; not a diagnosis or a guaranteed runtime |
| Time estimate | `time_to_full_now`, `time_to_empty_now` | Seconds; displayed only for the corresponding charging/discharging state |

Unavailable means the field is absent, unreadable or invalid. One missing
sensor does not hide the others. Zero design capacity cannot produce a ratio. Time estimates outside 1 second
to 7 days and battery temperatures outside −273.15 to 200 °C are rejected
as invalid readings; these bounds are not thermal warning thresholds.
The ratio may exceed 100% because full capacity is a gauge estimate, so the app
does not clamp it or invent a wear warning. The app does not estimate health
from charge percentage or assign temperature thresholds. Existing thermal
alerts use the kernel's own hot/critical trip points.

A connected charger does not necessarily mean charging: the Frame can still
drain under load or sit idle near full charge. A 100% capacity reading alone
does not prove the driver reports Full. Missing status is explicitly unknown;
near-zero measured battery power with a charger is shown as not charging.
Failed, stale or disconnected status samples clear Control Center readings.

**No charge controls are provided.** Frame's SteamOS charge-limit backend is
unsupported; see [charge-limit research](charge-limit.md). Monitoring never
writes to power supplies, pauses charging, changes current or sets a limit.

## Verification

`tests/test_battery.py` uses temporary sysfs-like files for conversion,
malformed/missing values, permission failures, source selection and partial
sensor support. `tests/control_center.cjs` exercises charging states, optional
metrics and failed/stale/disconnected sample handling. These tests do not
connect to a headset. On 2026-10-24, the PR's uninstalled parser was also
piped over SSH to a real Frame running SteamOS 0.5.6 (build
`20261015.6141207`). Its read-only sysfs result selected
`max1720x_bat_7-36` and reported 99% charge, Not charging, 24.9 °C,
Good driver health, 14 cycles, 2,920 mAh full and 2,700 mAh design capacity
(108.1% fuel-gauge estimate). The Control Center UI was not run against this
headset; Windows and macOS were not tested. Optional fields are not claimed to
be available on every firmware build.
