# Read-only Framey activity gate, 26 October 2026

At 11:12 UTC, a read-only probe acquired `/tmp/frame-test.lock` by atomic
`mkdir` with a random owner token before reading the Frame. SteamVR
returned two `vrcmd --stats` rows: performance metrics first and the status
row second. The status row reported activity level **1**. The original
`framey-worn-check.py` looked only at row zero and reported unknown activity;
`framey-vr-check.py` used the same row-zero assumption for its wake gate. The
fixed gates select the unique status row and fail closed if it is missing,
duplicated or malformed.

The first locked read found 90% battery, proximity raw 222.25, no active
managed headset panel service and no managed Decky plugin. A subsequent locked
read found activity 1 and proximity raw 223.625. No reliable wearer
confirmation was available. No wake, service install, settings write or input
was attempted.

While activity was 1, a separate owned-lock read captured four seconds from
`/dev/video99` into a private 640×360 H.264 MP4. It decoded successfully and
contained active video imagery. The inspected sample did **not** establish
room passthrough, Frame Control panel visibility, ProtonDB Badges UI or
controller interaction. The private recording and decoded frame were removed
after inspection; no room or media images are committed. Each read released
only its owner-token lock. The hourly worn-check schedule remains enabled.

The local focused safety suite covers a metrics row before the status row,
awake activity, ambiguous/missing status and foreign-lock refusal. A genuine
worn visual and physical-controller check remains outstanding.
