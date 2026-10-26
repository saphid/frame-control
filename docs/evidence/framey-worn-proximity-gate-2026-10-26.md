# Interactive Framey worn-check proximity gate, 26 October 2026

The interactive `scripts/framey-worn-check.py` already required an explicit
operator wear confirmation and a unique `/tmp/frame-test.lock` owner before
reading SteamVR activity. It did not read proximity. This change makes its
locked preflight read the raw proximity sensor and stop before its interaction
window when the reading is missing or invalid. It checks activity, proximity
and battery again before input. The same owned-lock cleanup applies on failure.

The focused local gate suite passes 9/9 tests, including missing and nonfinite
proximity, proximity disappearing between reads, metrics preceding the SteamVR status row,
standby, low battery, no operator confirmation and a foreign lock. No headset
input was sent for this change. A separate owner-locked read-only Frame check
found SteamVR activity 3 (standby), proximity raw 3.0625 and battery 93%; it
released its lock without a worn test.

The raw proximity value is not calibrated as proof of wear. The operator's
in-person confirmation remains required; awake activity, proximity and trusted
synthetic input alone do not prove wearer-visible pixels or physical controller
usability. The hourly worn-check schedule remains enabled.
