# Exact-head VM packer and catalog qualification

PR #530 merged as `fda7bcd86237033949d72a967c4e8fd41c9d46cc` after exact head
`d4c4fa94775d3e5a188ba1bf5a334713517842e2` passed all **19 hosted checks**, with current main
`4e1f664be47b99fcf88c84d1280126c39d6753b4` at **15/15**. Fresh feedback,
thread and mergeability checks passed immediately before the ordinary merge.
The merged tree exactly equals the tested head. Fresh merge-commit CI remains
a separate gate; this record does not qualify a release.

## Hosted artifact verification

Eight downloaded artifacts retain archive/member hashes. Independent checks
verify **1,361 source-hash bindings across 148 files**, both digest-pinned
published Decky 3.3.0 loaders, complete browser result packets, ownership/runtime
controls, and every triggered signed-package mode: AMD64, ARM64, browser HTTP,
and production-parent HTTP. Both package architectures install signed app/runtime
bundles, sync both ways, restart, preserve data on uninstall, and report owned
process/instance cleanup. This is private VM evidence; installer enablement stays
false and no real Frame is contacted.

Native AMD64/ARM64 reports retain **45 cases each**, **534/535 RPC calls**, and
**seven expected regression controls per architecture**. These cases do not
prove every official plugin shuts down cleanly or works fully. Historical
negative results remain in the raw reports. No catalog/status/policy change
follows from these fixture checks.

The browser HTTP report retains 13 requests. Production-parent HTTP retains
15 direct gateway requests plus **65 successful parent requests**, maximum
**7.590 seconds**, with the unchanged sandboxed iframe and no parent errors.
Complete result packets match their byte counts/checksums and decoded guest
reports. Inspected running/stopped screenshots show the private Syncthing panel;
the production parent still displays the official blocked compatibility status.
Synthetic input, CEF and store receipts remain explicit. Real Steam CEF, managed
installation, headset visibility and controller interaction remain unverified.

## Full-catalog supplement to the hosted skip

Hosted e2e runs 53 tests with one skip: its full-catalog archive cache is absent.
A fresh uniquely owned fake-Frame project at the exact tested head mounts the
existing cache read-only and independently checks every archive digest.
The actual full-catalog HTTP/SSH installer test passes **all 116 records without
skips** in **164.832 seconds**: **69 install/remove outcomes**
and **47 correct policy/archive rejections**. No official backend executes.
This fills that installer-audit gap; it does not establish runtime compatibility.

Owned containers, volumes, network and image tags are removed; absence is
independently checked after the test. Existing cache/data and shared image tags
are preserved. The hosted Linux server job runs 1,952 tests with 28 documented
platform/dependency skips; those are not converted to passes. The three new
packer regression tests pass in that exact hosted log. AST comparison confirms
all module-level code outside `pack()` is unchanged from premerge main.

## Limits

Terminal #492's separate ARM64 browser replay is not qualified by this record.
No compatibility upgrade, tagged installer, release smoke, Frame, wearer or
controller pass is claimed. The headset and hourly schedules were untouched.
Release remains held for exact release-commit gates and locked Frame smoke.

[Audit](framey-vm-packer-hosted-qualification-2026-10-31.json) and [raw artifact reports, catalog outcomes/logs and verifiers](framey-vm-packer-hosted-qualification-2026-10-31-raw.json.gz).
Workflow runs: [native](https://github.com/saphid/frame-control/actions/runs/41221273105),
[ownership/runtime](https://github.com/saphid/frame-control/actions/runs/41221273155),
[all package modes](https://github.com/saphid/frame-control/actions/runs/41221273097),
[CI/e2e](https://github.com/saphid/frame-control/actions/runs/41221273182).
