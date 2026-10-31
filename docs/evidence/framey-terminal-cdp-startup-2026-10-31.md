# Terminal CDP startup and VM archive repair — 2026-10-31

Frozen runtime source: `c5cf29954f14ede032fc50e281db15b94de40064`, incorporating
main `1ac29413186fb29d5844ee9ad1c5c6fd36eeac27` by a normal merge.
The existing ARM64 failure at `a66262225ac05e188ce185273c7c7da5bc6611b8`
remains failed: production `get_terminals` and `create_terminal` returned
HTTP 503 after approximately 25.11 seconds. Its later read-only diagnostic
succeeded under different conditions; that does not prove recovery or one cause.

CDP discovery now uses a direct standard-library HTTP connection instead of
the general URL opener. It preserves the query, five-second discovery timeout,
page selection and WebSocket evaluation, handles failed/truncated responses,
and closes the discovery connection. Production method, event and SSH deadlines
are unchanged. Five alternating local AMD64 cold-import pairs measured
136 modules before and 120 after, with medians of 0.031893 and 0.024178 seconds.
These are import measurements, not ARM64 or complete method-latency proof.

The frozen VM archive also includes `runtime_console.py`, now imported by the
main runtime probe. A regression checks entry-point local imports in both
architectures and both archive modes. The main refresh preserves 37 main
runtime dispatch bodies, the Terminal candidate dispatch and all 116 catalog
records; it does not promote Terminal compatibility.

## Verification

- 59 focused test methods pass, including real owned loopback HTTP/WebSocket
  discovery and archive-manifest checks. No Steam or Frame is contacted.
- The full unit suite passes 1,960 tests in 254.022 seconds with 16 optional or
  platform skips. It began at `b2f0916f`, before the manifest-only repair; the new
  manifest test passes separately at the final frozen source. Its mocked lock
  release failure deliberately prints an error; no real lock was involved.
- Full isolated Fake Frame e2e passes 53 tests in 269.758 seconds, with one
  optional catalog-cache skip. Owned containers, volumes, network and image
  tags are removed. Socket ResourceWarnings remain in the retained log.
- A networkless AMD64 QEMU replay verifies all 168 runtime fingerprints,
  published Decky 3.3.0, private PTY input/output/resize/remove/reload and config
  persistence. All 20 production HTTP requests pass: 14 method calls and six
  event polls, with four delivered backend events. The installed status route
  returns HTTP 200 in 3.867 seconds. No failure-only diagnostic runs.
- Sandboxing remains enabled; renderer seccomp and no-new-privileges are
  checked. The mixed Decky service stops with exit zero in 2.986 seconds,
  and the owned VM, browser, HTTP server, observer and private bundle are cleaned.
- The three captures were inspected: the initial pane is blank with a caret;
  the output capture shows `framey-browser-output`, dimensions and a returned
  prompt; removal leaves the empty Active Terminals scaffold. The parent
  partial-compatibility warning remains. Pane overflow is visible; no complete
  layout or clean-console claim follows.

## Retained failures and limits

The first local replay failed because its archive omitted `runtime_console`.
The second used the base rootfs, which lacks Chromium's sandbox helper; Chromium
exited before any HTTP request. Both failures and owned cleanup remain in the
raw evidence. The successful replay uses the existing browser rootfs with
SHA-256 `bd23ea5337a1a5fecd7be8624478d4c50b5258d2b8044fd2cfa900de2f117fc9`;
no sandbox or security setting was weakened.

Synthetic CEF, managed receipt and input do not verify real Steam CEF, an
official managed Terminal install, wearer-visible pixels or physical controllers.
Complete raw Decky console logs are absent. No real Frame or hourly schedule
was touched. Fresh exact-head hosted CI/e2e, AMD64/ARM64 runtime, ownership,
PC and all package modes remain required. This evidence qualifies no merge or
release and does not resolve the earlier ARM64 production timeout.

[Structured audit](framey-terminal-cdp-startup-2026-10-31.json) and
[raw logs, failures and verification source](framey-terminal-cdp-startup-2026-10-31-raw.json.gz).
Captures: [initial pane](framey-terminal-cdp-startup-2026-10-31-terminal.png),
[output](framey-terminal-cdp-startup-2026-10-31-output.png),
[removed](framey-terminal-cdp-startup-2026-10-31-removed.png).
