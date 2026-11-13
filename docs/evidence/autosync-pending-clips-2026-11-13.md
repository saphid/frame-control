# Manual copy waits for saved Steam clips

With both automatic switches off, **Copy everything now** cleared its pending request when a saved clip was still being written. No later check ran, so that clip was never copied. The request now stays pending while clips are unsettled; copies already saved locally are skipped, and the request finishes after the remaining clips settle.

A deterministic fake-source regression checks both an unknown idle age and an age of 29 seconds, repeated waiting passes, a clip settling at the 30-second threshold, unchanged automatic switches, and no further listing after completion. Screenshots and an already settled clip are copied once. The regression fails in both cases with unchanged main source and passes with the fix. All 34 autosync tests pass without skips. The JSON record binds the source and before/after test logs by SHA-256.

No real Frame was contacted and no real capture files were transferred. Real headset export, mobile background copying, and exact-release smoke remain unverified.
