"""Read Linux batteries psutil misses because their names lack BAT/battery.

Copied only into exact managed DeckySpy installs. No sysfs writes or estimates.
"""
from pathlib import Path
from types import SimpleNamespace


def sensors_battery(power_supply=Path('/sys/class/power_supply')):
    import psutil
    battery = psutil.sensors_battery()
    if battery is not None:
        return battery
    try:
        supplies = sorted(power_supply.iterdir())
    except OSError:
        return None
    for supply in supplies:
        try:
            if (supply/'type').read_text().strip() != 'Battery':
                continue
            present = supply/'present'
            if present.exists() and present.read_text().strip() == '0':
                continue
            percent = float((supply/'capacity').read_text().strip())
            if not 0 <= percent <= 100:
                continue
            status = (supply/'status').read_text().strip().lower()
            plugged = True if status in ('charging', 'full') else False if status == 'discharging' else None
            secsleft = psutil.POWER_TIME_UNLIMITED if plugged else psutil.POWER_TIME_UNKNOWN
            if plugged is False:
                try:
                    # Linux power_supply time_to_empty_now is already seconds.
                    value = int((supply/'time_to_empty_now').read_text())
                    if value >= 0:
                        secsleft = value
                except (OSError, ValueError):
                    pass
            return SimpleNamespace(percent=percent, secsleft=secsleft, power_plugged=plugged)
        except (OSError, ValueError):
            continue
    return None
