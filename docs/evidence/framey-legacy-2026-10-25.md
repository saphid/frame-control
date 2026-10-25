# Legacy Decky frontend bridge

The exact official MusicControl 1.1.6 archive (`12.zip` in the test fixtures)
has no `api_version` field and returns its initializer from a Decky IIFE.
Framey now wraps that expression in an ES module inside the existing
opaque-origin iframe. It passes a legacy `serverAPI` to the initializer.

Local Chromium ran the unchanged official frontend, including React effects,
with all backend calls rejected and network access blocked. It emitted
`framey:ready` without a JavaScript startup error during the observation window.
This proves initialization, not playback, MPRIS access, or a useful populated UI.

The fake Frame installed, packed, checked the frontend bytes and removed this
exact archive. Its synthetic Sample Panel also read a legacy keyword argument,
wrote a setting, and read that setting through the modern API. This exercised
the real HTTP → SSH → CDP path with a fake Decky backend. The RPC contract was
checked against Decky's `handle_plugin_method_call_legacy`: it calls with a
keyword object and returns `{success, result}`. Invalid argument shapes and
unmanaged plugin IDs are rejected.

Verification: `python3 -m unittest discover -s tests -p 'test_framey*.py'`
(21 passed), `node tests/page/framey_actions.mjs`, and
`scripts/e2e.sh test_framey` (2 passed). No official Python backend code or
headset state was changed by these checks. Real Frame backend behavior,+controller input, playback and worn VR use remain unverified.
