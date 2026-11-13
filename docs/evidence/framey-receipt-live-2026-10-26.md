# Framey receipt guard, unworn Frame exercise (26 October 2026)

The bounded `scripts/framey-vr-check.py --exercise` runner acquired `/tmp/frame-test.lock` with its own random owner before reading the real Frame. Its 05:26 UTC run used source commit `c2f94c242dac670e18259193311a7375f5a87942`. Preflight found SteamVR activity 3 (standby), proximity 6.25 and battery 99%. No wearer was confirmed.

The temporary Frame Control dashboard overlay became visible to OpenVR. The stereo compositor image changed, and the `/dev/video99` mirror produced a frame. The sample settings panel displayed its stored off value, accepted a trusted synthetic OpenVR pointer event, saved on through the real Decky Python backend, read the setting from disk, and showed on after a fresh iframe reopen. The quick action read on. A native slider reached 50. Text entry used CDP after OpenVR focus. The runner exited 0 with `input.passed=true` and `compositorChanged=true`.

The private capture files remain outside the repository at `/tmp/frame-pr301-unworn-vr-fixed/`. The before/after stereo SHA-256 values were `1683bf1dab70c1a0a1e8f313c8317dc04f992070b5b0de232de9008700130711` and `684a27eecf7bcbbc5308092ddbb1517c4596fb283e061e73dd6bb7f025954e8b`; the mirror frame SHA-256 was `5939149ea9c85fd2d86d3f8879c348f006c421a386bd66a93fe`. Room pixels are not committed.

An earlier locked run at 05:24 UTC exposed a missing SHA-256 in the runner's temporary sample receipt: the new guard correctly asked to reopen the panel. Commit `c2f94c2` gives that sample a content digest; the second run passed. Both runs reported no cleanup errors, restored `power.pauseCompositorOnStandby=false` and `power.turnOffScreensTimeout=5`, removed their power recovery timers, and released only their own locks. Battery remained 99%.

This is an **unworn sample-plugin result**. It does not prove wearer-visible pixels, physical controller input, native scrolling (the attempted scroll offset stayed 0), VR keyboard behavior, comfort, or any official Decky plugin's VR panel or backend. The hourly worn check remains enabled.
