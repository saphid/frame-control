# Host shutdown gate: completed prior-head CI evidence

All four signed-package jobs passed at exact pre-refresh head `0fafc02c59059b3270df5d40be459538d685f805` in run `41114645218`. These audits independently checked source fingerprints, GitHub artifact digests, actual signed app/runtime packages, two-way sync, migration, lifecycle, ownership refusals and data preservation. Both candidate and migration Decky services reported checked complete logs and actual clean PID-to-zero, inactive/success/exit-0/mixed stops, accepted by the stricter host gate. Plain console reports match their complete saved guest results.

| Mode | Job | ZIP SHA-256 | Service/migration stop seconds | Evidence |
| --- | --- | --- | --- | --- |
| amd | `124265566346` | `657e78e9b39e6f6914607d9557c1a9711b5d4898b09c9560804fe80ae76cb397` | 1.992/2.175 | [amd](framey-syncthing-host-shutdown-ci-amd-2026-10-30.json) |
| arm | `124265565797` | `5c359f15cd6214f8eb924e0d61f6ccc0693d858ec1c0369c3cdccfff5cadd629` | 14.508/9.548 | [arm](framey-syncthing-host-shutdown-ci-arm-2026-10-30.json) |
| http | `124265566452` | `a4da8a0321d31ef3ae4f3e528f2e0d19bc8bb5a1526f3e21650340e7d8a3587c` | 6.223/6.279 | [http](framey-syncthing-host-shutdown-ci-http-2026-10-30.json) |
| parent | `124265566271` | `3ee24d8c2e6a5330436fed277fea7166ba5aed16e5e76e1773937dae8318df61` | 1.853/1.873 | [parent](framey-syncthing-host-shutdown-ci-parent-2026-10-30.json) |

Browser HTTP and production-parent reports validate all retained capture payloads. Both distinct browser images and all four distinct parent/bridge images were inspected. The browser uses private synthetic CEF, receipt and input; actual Steam CEF, managed installation, physical Frame and controller usability remain unverified. No real Frame was contacted.

The branch subsequently absorbed main `bc3e592` through a normal merge. These artifacts are historical evidence for the pre-refresh head, not final-head CI approval. Fresh exact-head applicable CI, native, e2e, ownership and all four package results, plus current-main green, remain required before merge. No timeout, production adaptation, security setting, installer policy or compatibility status was changed.
