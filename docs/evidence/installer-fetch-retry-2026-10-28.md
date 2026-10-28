# Installer dependency fetch retry, 28 October 2026

The desktop installer build fetches pinned Python, platform-tools, CA and KDE
Connect packages through `app/build/fetch-deps.js`. Before this change, one
temporary connection drop or HTTP 503 ended the build. The iOS bundle's
separate Python fetch hit a real remote disconnect in main CI run
[40698195628](https://github.com/saphid/frame-control/actions/runs/40698195628);
that path was repaired separately in PR #372.

The desktop fetch now retries transient transport errors and HTTP 408, 429 or
5xx responses at most twice, with one- and two-second waits. HTTP 4xx errors
other than 408/429 fail immediately. The existing pinned SHA-256 comparison
still happens after download and before writing package bytes, so altered
content fails without retry or installation.

Local Node 24 checks passed: retry recovery, exhausted retries, permanent HTTP
error, HTTP 503 and a response aborted after partial bytes; all six app test
files, script syntax and
`git diff --check`. Hosted exact-head CI and installer preview remain required
before merge/release. No installer was published, and this test makes no
claim about a physical Mac or Windows install.
