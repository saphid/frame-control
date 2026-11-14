# Terminal output event syntax

The exact published Terminal 0.5.3/store 65 frontend subscribes to `terminal_output#${id}`, and its backend emits `terminal_output#` plus that ID. Framey's iframe, production parent and Python dispatcher rejected `#`, so an initialized route could not receive terminal output. Accept this character at all three event-name boundaries while retaining the existing length/count limits, receipt-owned plugin selection, session/origin checks and event queue filtering.

The added routing regressions fail at all three boundaries before the fix (31 tests, two failures and one error), then pass after it (31 tests, zero failures). They verify actual shipped iframe callbacks/unsubscribe, parent request/reply routing, Python receipt-bound payload generation, and event filtering across plugin and terminal IDs. The [input hashes and results](framey-terminal-output-events-2026-10-30.json) bind the source observation to the exact published archive. No shell executes in these tests.

This verifies event routing only. It does not establish a working Terminal native dependency, complete browser/backend integration, managed installation, real Frame visuals or physical-controller usability. The original native import blocker is tracked in #487; private dependency and cleanup development remains separate. Compatibility status and installation policy are unchanged. No release or headset contact.

The full local server regression completed with 1,857 tests, zero failures and 16 skips (226.157 seconds). The paired JSON binds the retained log.
