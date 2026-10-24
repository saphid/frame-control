# Wired connection doctor

If you use a USB-C cable because the Wireless Adapter is unreliable, open
**Devices & connection → Wired connection doctor** in the desktop app. Enter
the headset's configured SSH alias and click **Check cable connection**. From
a source checkout, run `python3 scripts/frame-wired-doctor.py --alias frame`.

The on-demand check reads the computer's selected route to the Frame USB
address, checks whether port 22 answers, then runs remote `true` over SSH with
the existing pinned host key. It does not change network settings or the
headset, accept a new key, or attempt a password. A failure is shown as unknown
or warning; the doctor never claims a cable works from an IP address alone.

The known address is `10.86.200.233` on the Frame's `10.86.200.232/29` USB
network. A Mac with the Frame attached used `10.86.200.234/29` and completed a
strict SSH login on 2026-09-28; see [the observed link](how-the-frame-works.md).
If the route check says unknown, first confirm a data-capable USB-C cable, a
visible PC network interface and a current Frame OS build. Other OS builds may
use another subnet. If the port answers but SSH identity fails, connect using
the normal pinned headset alias and resolve the pairing or key warning there;
do not disable host-key checking.

This checks **Frame Control's SSH route**, not whether SteamVR's game stream
uses the cable. The Wireless Adapter and Steam streaming can follow a different
path. No cable is attached to the Linux test host, so this exact UI has only
synthetic route/SSH tests. Windows and Linux physical USB-C behavior, and a
fresh wired readback on the current Frame OS, remain unverified.
