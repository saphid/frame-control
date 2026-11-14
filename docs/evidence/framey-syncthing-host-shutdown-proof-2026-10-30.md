# Require loader shutdown proof at the host boundary

The guest fixtures added by #491 check both the manager stop result and the retained Decky log. The host verifier still accepted a report without that log check. The signed-package migration and managed-service verifiers also accepted missing unit-removal and successful-stop evidence.

Replaying the retained successful CI browser artifact from head `c013e99` (ZIP SHA-256 `7f3a119747b085fbd3b64f4e45e049007bdc1471832d9a0fff2e75be1df7c2a0`) reproduced this: its console contains `asyncio.exceptions.CancelledError`, but both old package verifiers accepted its unchecked reports. The new common host gate rejects both reports. It accepts the actual clean AMD64 ownership report from exact head `6e8f0f9` and rejects that same report with the log-check field removed.

The gate requires the actual owned Decky service, owned unit removal, the complete shutdown-log check, and an inactive/success mixed-policy stop with exit status zero and MainPID changing from a positive PID to zero. It is used by the ordinary service VM and both signed-package paths. New-head runtime CI remains required; passing these host refusal regressions is not a new package/runtime or physical Frame result.

The regression produced 28 failing subcases before the fix; all 46 package tests and 102 Syncthing tests pass after it. [Input digest and results](framey-syncthing-host-shutdown-proof-2026-10-30.json) retain the evidence. No guest source, production plugin behavior, timeout, installation policy, headset, user data or compatibility claim changed. The original #491 local replay continues from its own unchanged checkout.
