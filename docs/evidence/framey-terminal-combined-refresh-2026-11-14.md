# Terminal combined refresh, 14 November 2026

Source `5762647522ec2a41135e2248b72263d0192a8cc8` normally includes the receipt-bounds fix #706 and sample child EOF repair #707. The merge preserved Terminal's UI, production HTTP client and VM probe inputs byte for byte. Receipt and sample source inputs match their prior local qualifications.

The combined source passes 162 focused/sample/packaging tests including both actual Chromium startup tests, plus all 122 store tests: 284 passed, no skips. The companion JSON binds the source and compressed full logs. No new full local Terminal HTTP VM replay is claimed; fresh exact-head hosted checks and artifacts remain required. The original ARM64 shutdown trigger remains unproven, official Terminal installation remains disabled, and real Frame/worn/controller/scrolling/VR keyboard behavior remains unverified.
