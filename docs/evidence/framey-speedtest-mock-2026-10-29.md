# Speed Test 1.0.2 local frontend replay, 2026-10-29

The official Decky Speed Test ID 118 archive is pinned at SHA-256
`8b1ee429aece9330b83ea3fc2e7e27d007ac61a737169f20bda3f1a19ab95508`.
It has an API 1 frontend and no executable Python backend. The fake Frame
catalog flow had already installed and removed it successfully. This probe
checks what its panel does after initialization, using the Framey host in
local Chromium.

## Reproduce

1. Copy `tests/fixtures/framey-official/118.zip` to a temporary cache named
   `<sha256>.zip`, then run
   `python3 scripts/framey-audit-browser.py --cache <cache> --speed-test-mock`.
2. Open the printed loopback URL in local Chromium. Run
   `runAudit([118], 10000)` in the console. The result's `rootText` should
   show the completed panel and Retest control.
3. Open `/panel/118` on the same loopback origin. After completion, inspect
   `window.__speedTestMock`, click Retest, and inspect it again. The download
   and upload counts should increase. Do not use the displayed Mbps numbers
   as a speed measurement.

The mode is opt-in and limits the audit catalog to ID 118. It accepts only
Cloudflare's trace, download and POST upload paths, generates bounded response
bytes, and keeps the page's `connect-src 'none'` policy. It does not install a
plugin or call a Decky backend. The default catalog audit still rejects fetch.

## Observation

The exact archived bundle reported `ready: true`, `error: null`, no backend
methods and no console errors. The panel showed Sydney, AU from the fixture
trace, download/latency/upload/jitter fields, Retest and a measured timestamp.
The first run recorded mock counts `trace=1, down=64, up=12, other=0`; after
clicking Retest, `down=128, up=24, other=0`. Browser network entries for this
run were loopback runtime and panel assets plus the bundle's blob URL; no
Cloudflare request was sent.

**Limit:** The responses are made in memory, so the Mbps values are synthetic.
No actual internet bandwidth, real Frame session, worn display, controller
interaction or optical readability was checked. Speed Test remains **partial**
in the compatibility catalog.
