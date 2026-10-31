# Native AMD64 passive panel profiling replay

The networkless disposable-VM replay at source `4a5e9674943da4dfc627f86863cf05c2802bc21f` passes the unchanged production Terminal HTTP/event flow. Independent verification covers all 166 input hashes, the full checksummed result packet, native lifecycle, returned output and owned cleanup. Fourteen production method requests and six event polls return successfully. All three retained PNGs were inspected: rendered terminal, `18 125` / `framey-browser-output` / prompt, and empty list after removal.

The actual owned Decky service stops with KillMode=mixed, inactive/success, MainPID 338 → 0, zero exit status in 2.681 seconds. The user manager is stopped and owned QEMU is reaped. Complete loader consoles are not retained, so this does not claim error-free complete logs.

The replay exposes a diagnostic labeling bug: the old METHOD_SCRIPT prefix also matches EVENT_SCRIPT. Twenty panel-method profile records therefore cover 14 method executions and six event polls. They establish passive panel profiling, not method-specific attribution. The evidence JSON marks this limit explicitly and retains the original source fingerprints and trace/profile records.

The follow-up matches both prefix and suffix of each shipped template's payload slot, labels methods and event polls separately, and samples both without recording their payloads. A regression uses the real production templates to reproduce their shared preamble and verify distinct labels, while success/error passthrough tests cover all three profiled kinds. Thirty-three gateway and three failure-diagnostic tests pass. Production commands, deadlines and receipt checks are unchanged. The corrected labeling still needs its own native replay; this historical source result does not qualify changed inputs.

These tests use synthetic CEF, receipt and browser input. The ARM64 Terminal RPC timeout remains failed with unproven cause. This adds no production installation/adaptation, real Steam CEF, real Frame pixels, wearer visibility or physical-controller claim. No headset or schedule was accessed.

The later [corrected-source guest-only audit](framey-terminal-method-profile-corrected-2026-10-30.md) verifies distinct method/event classifications and retained captures. Its original host runner was interrupted; it does not qualify as a complete host replay or override the ARM64 failure.
