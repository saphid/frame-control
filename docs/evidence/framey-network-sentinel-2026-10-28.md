# Network Sentinel 1.0.4 managed user-service check

Official store ID 114, ZIP SHA-256 `d3e07f40a0c800e72d15594e03c8c61e9bf3092524a578a0260520e735b971a5`.
The exact archive's `main.py` SHA-256 is `2baa390cb66dc267e8f04e61ba1edc43af75115ad5e453d308f6bf26ed70b6b9`.
Its backend imports `psutil`, but the ZIP contains no wheel. The manifest requests `_root` although the inspected backend uses user-readable interface counters, subprocess ping and DNS, settings, and optional `nmcli` reads. Loading the backend does not start monitoring.

The managed install checks the complete archive digest, manifest and Python source before removing `_root`. It adds the existing pinned BSD psutil 7.2.2 wheel for the native architecture to this plugin's `py_modules`, uses Decky's plugin-scoped settings directory, leaves legacy path migration inactive in the user service, and initializes ping jitter for failed/offline calls. Other root-requesting archives still fail the root gate. The receipt records `network-sentinel-user-psutil`; existing copies need update or reinstall.

Local transaction tests installed and removed the exact archive, checked the native wheel and unmodified license, and rejected an altered archive. In network/device-isolated, unprivileged **actual Decky 3.3.0 amd64**, the managed plugin was discovered, imported native psutil, returned default and updated settings, reported empty history and bandwidth, started its monitoring loop, produced a history sample with quality and bandwidth fields, then stopped. The full native regression runner also passed its other cases, including FileServer and negative controls. The first run's existing large FileServer install timed out at 15 seconds under host load; its bounded timeout is now 30 seconds and the complete rerun passed. No external network call succeeded in the isolated container. Native ARM64 and fake Frame install/remove are CI gates for this change; neither is claimed by this local evidence.

The preexisting local Chromium audit initialized the exact frontend with backend calls denied. It did not prove a functioning panel. External latency/DNS, Wi-Fi scans, actual Frame ARM64 runtime, frontend controls, and worn VR remain unverified. This is a **partial** compatibility result, not a full monitoring or headset-usability claim. No real Frame, normal service, power value, or physical network setting was touched in this check.

## Hosted ARM64 follow-up

The [main native Decky run](https://github.com/saphid/frame-control/actions/runs/40776292569)
on `dad5f78a02dd477a689689865cd4ef4205b87e22` passed the exact Network
Sentinel case on native amd64 **and ARM64** runners. Both logs report `PASS 114`
for discovery, native psutil import, private settings and one isolated
monitoring-loop sample through actual Decky 3.3.0 RPC. The containers had no
external network or Frame device access. Real Frame monitoring, external
latency/DNS, panel controls and worn VR remain unverified.
