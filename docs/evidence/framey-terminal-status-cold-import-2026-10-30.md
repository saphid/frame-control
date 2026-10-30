# Bounded Decky status cold-start candidate

PR #492 source `c3c239121232aacfb8eee188fdff7a616d9b8060` failed its actual ARM64 production-browser job `124309833146`: installed-plugins status returned HTTP 503 after the unchanged 15-second SSH deadline (15.204 seconds observed). No Terminal frontend interaction passed. The retained artifact and failure capture remain authoritative.

The failure-only, instrumented subsequent status request completed in 11.951 seconds, with 7.326 seconds cumulative in `urllib.request` and 4.789 seconds in `http.client`. This was a warmer, modified diagnostic; it neither proves one cause nor overrides the production failure.

The candidate replaces the remote probe's URL/proxy/TLS imports with a standard-library HTTP connection to its fixed loopback CEF endpoint, and uses `os.uname().machine` rather than importing `platform`. The outer application download path continues to use urllib. The CEF socket timeout remains two seconds and status SSH remains 15 seconds. Service operations, authentication, executable trust, discovery, receipts and installer behavior are unchanged. Non-200, malformed JSON and transport/protocol failures leave CEF unavailable.

Local HTTP regression coverage executes the real remote script in subprocesses against an owned ephemeral server. Valid targets, no targets, HTTP 503 and malformed JSON preserve managed version, active-service status, inventory and canary file bytes. The original probe fails the four cold-import cases before HTTP; the candidate passes. All 65 focused Decky tests pass. A first broad discovery pattern also imported non-test `deckyparty_contract.py` without its standalone fixture; the corrected `test*decky*.py` pattern passes.

This local change is retained without pushing while earlier CI is live. Fresh production runtime, ARM64 and complete exact-head CI are still required. No deadline increase, gate waiver, hardware contact or physical-usability claim.
