# Windows Wireless Adapter doctor

Open **Tools → This PC → Wireless Adapter doctor**, then choose **Read PC
adapters**. It works without a headset connection. It only queries this Windows
PC, with no automatic polling, changes, elevation or UAC prompt. It never
contacts the Frame. A direct `#wireless` link on another platform explains that
Windows is required.

The snapshot shows:

- Exact network PnP instance IDs, including non-present devices, with separate
  presence, PnP status/problem code, operational state and media connection state.
- Microsoft Wi-Fi Direct Virtual Adapter candidates and their distinct instance
  count. `SWD\WIFIDIRECT\` is enumerator evidence; an English device-name match
  is explicitly labelled **Name only**. A repeated row for one ID is counted once.
- PC Wi-Fi interfaces, hardware-interface status and whether Windows has a
  default route configured on an interface. Neither a route nor **Up** proves
  that Steam uses that adapter. Multiple configured defaults are possible.
- Reported channel and band, when `netsh wlan show interfaces` supplies recognised
  English fields and an exact matching interface GUID. Missing, localised,
  disconnected or denied readings remain **Unknown**. There is no name-based
  channel association. A PC's router channel is not the Steam dongle's channel.
- Possible spectrum overlap when an interface reports **2.4 GHz**, without
  claiming interference. With no such reading, overlap stays **Unknown**:
  unreported virtual/proprietary radios and audio dongles may still use 2.4 GHz.
  Channel 1–14 alone does not identify a band: 6 GHz reuses low channel numbers.

## Why there is no disable button

[夕凪's report](https://x.com/Oo_yuunagi_oO/status/2113904070352343135)
(24 October 2026) says extra Microsoft Wi-Fi Direct Virtual Adapter instances
appear when their wireless adapter becomes unavailable, and disabling the newly
appeared one *seems* to stop recurrence. This is useful owner evidence, but does
not establish which instance would be safe to disable on another PC.

Windows can legitimately create several Wi-Fi Direct virtual interfaces.
A `#2` suffix is not a creation timestamp; non-present, down, or disconnected
status is not proof of an unused instance. The inventory does not reliably map
Steam's active radio/session to an expendable PnP instance. Disabling the wrong
one could interrupt streaming, PC Wi-Fi, Mobile Hotspot or wireless displays.
Frame Control therefore supplies evidence and guidance, with no disable,
re-enable, driver removal or other write endpoint. It never changes security or
location settings, requests administrator access, or bypasses execution policy.

Before any manual changes, retain the exact instance IDs and compare snapshots
before/after a drop with Steam Support. Do not disable a device based only on
this report. A future disable feature needs a verified Steam adapter/session
mapping, fresh protection for primary/active instances, explicit confirmation
for one exact instance, and a tested recovery path that re-enables that same ID.

## When a stream drops immediately or the adapter will not reconnect

Read PC adapters **before** starting a stream, then refresh immediately after a
drop. Compare the *exact* PnP instance IDs, presence and problem codes. Note
whether the PC's own Wi-Fi drops too. A new `#2` name is not proof that this
instance caused the failure. Keep the time of the drop and the two snapshots
for Steam Support; the doctor does not save or upload them.

The app shows **Changes since previous read** after the second click. It
compares exact PnP IDs, known status fields and reported channels/bands; an
unknown value is never treated as a state change. If the PnP source was
unavailable in either read, it declines to compare devices. Each successful
read becomes the baseline for the next one. **Forget previous read** clears the
baseline and comparison; closing the app clears them too. The before/after
comparison stays in local memory and is not uploaded or added to telemetry.
Reported changes can reflect sequential query timing or a service recovering,
not a fault or permission to disable any instance.

To narrow a drop at stream start, try one condition at a time: wired PC
networking instead of PC Wi-Fi, wired headphones instead of 2.4 GHz audio, and
spacing the USB radio dongles apart. Recheck the stream after each change. The
PC Wi-Fi channel in this report is not the Steam dongle's channel, so a matching
or different number does not establish interference.

If the adapter will not reconnect, stop the failed stream and close Steam's
streaming session before touching its USB connection. Refresh the inventory. If
the dongle is absent, reconnect it once at the PC, understanding that this
interrupts any connection using it, then refresh again. If the **same exact**
PnP instance now reports problem code 22 (disabled), review that instance in
Windows Device Manager and its normal enable action. Do not enable or disable a
different numbered instance by guesswork. For a missing device or another
problem code, record the before/after ID and code for Steam Support; do not
guess a driver or change security settings.

These are user-controlled checks, not an automatic repair. We have no physical
Steam Wireless Adapter dropout to reproduce and no verified mapping from a
Wi-Fi Direct virtual instance to Steam's active session. An in-app disable and
re-enable control remains deferred until that mapping and a recovery path are
tested on real hardware.

## Checking a 2.4 GHz audio conflict

[Deko's report](https://x.com/DekoDrak/status/2113412044644897023)
(22 October 2026) describes Razer wireless-headset interference and temporarily
disabling the Steam Frame dongle. It also mentions a PC/Wi-Fi shutdown during
Windows Update and asks whether the dongle caused it. The post does not prove
that connection or specify a measured audio radio channel. Treat the suggested
2.4 GHz conflict as a hypothesis, not a diagnosis of the shutdown.

Try wired audio briefly, separate radio dongles with a USB extension lead, or
compare PC Ethernet / an existing 5 or 6 GHz network. Change one thing at a time
and record whether symptoms recur. The doctor cannot measure RF congestion,
read an audio dongle's channel, identify a faulty driver, or prove a dropout fix.

## Sources, privacy and limits

The single local PowerShell process uses `Get-PnpDevice -Class Net`, its
`-PresentOnly` variant, `Get-NetAdapter -IncludeHidden`, `Get-NetRoute` for
IPv4/IPv6 defaults, and `netsh wlan show interfaces`. Each source reports
availability separately. Access denial, unavailable cmdlets/services and
unsupported features produce partial/unknown results; there is no permission
workaround. Queries run sequentially, so even one snapshot can span a state
change. One probe runs at a time, with a 20-second process timeout.

SSIDs, MAC addresses and raw command/error output are omitted from the API/UI.
PnP IDs and adapter/interface names can identify this PC; review before sharing.
The tool does not send or save reports, and does not add these readings to
telemetry or problem-report diagnostics. Copy relevant text manually if needed.

The shipped basic network-identity probe (`frame_network.py`) finds a gateway,
network name and Tailscale state. It does not inventory virtual adapters or
check channel overlap. The new doctor is a separate, explicit PC query.

## Verification

`tests/test_wireless.py` checks duplicate identity, presence/disabled/link
separation, ambiguous joins, partial sources, privacy filtering, 6 GHz/channel
ambiguity, localisation, missing band and denied output. HTTP tests require the
UI key, reject headset-local mode, and assert no SSH call. `tests/wireless.cjs`
executes the production UI with boundary fixtures: navigation starts no query,
clicks query once, unknown values and failure/retry remain visible, and PnP IDs
and names are escaped as text.

Windows CI also executes the real read-only PowerShell probe against the
runner's network devices. That proves Windows query execution, not a physical
Steam dongle, Wi-Fi Direct session or Razer headset. See the PR for exact CI
results. An existing local Windows 11 VM passed 15 targeted tests (one UI test skipped
because Node is absent), including the live query. PnP, presence, adapters and
routes were available; WLAN was unavailable in this VM. See
[VM evidence](evidence/windows-wireless-2026-10-24.md). No Frame was accessed; no physical
adapter/dropout fix or RF measurements are claimed.
