# Frame smoke sensor validation, 29 October 2026

The locked real Frame smoke reads SteamVR activity, IIO proximity and battery
before installing a test title. The proximity reader converts sensor text to a
Python float. Python accepts `NaN` and infinity as floats, while range
comparisons with `NaN` do not reject it. Before this change, a proximity array
containing `NaN` could pass the standby preflight and the saved-result release
verifier.

Focused local tests supplied `NaN`, positive and negative infinity to both
the live preflight parser and the release-result verifier. They also supplied
boolean, nonfinite, below-threshold and above-100 battery values. Every invalid
sample was rejected. Valid standby, finite proximity and 99–100% integer
battery samples continued to pass. The 25 smoke/cleanup tests, six result-gate
tests and 16 publisher tests passed locally.

This evidence uses simulated sensor responses. It does not record a real Frame
smoke, a worn-headset check, or controller input. Release publication still
requires a complete locked smoke from the exact clean release commit, including
the x86 launch that was skipped in the held v0.4.54 candidate.
