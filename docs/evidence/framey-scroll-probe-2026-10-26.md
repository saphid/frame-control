# Unworn Framey scroll transport probe, 26 October 2026

The previous `scripts/framey-vr-check.py --exercise` runs reported `scrollY=0` before and after one injected smooth-scroll event. That was inconclusive because the repository sample may fit inside the iframe. This probe changed only the **test script**: it created a temporary 160-pixel-high scroll region with 716 pixels of content, moved the native OpenVR pointer over it, and measured its own `scrollTop` and captured wheel events. No production Framey panel code changed.

Two local diagnostic versions ran on the real Frame from base main `784118b` after PR #292. The final version in this PR tried OpenVR `VREvent_ScrollSmooth` (309) and `VREvent_ScrollDiscrete` (305), using Valve's documented `VREvent_Scroll_t` ABI. The overlay listing showed the temporary Frame Control dashboard visible with `+smoothscroll`; a trusted native pointer move reached the iframe. Neither scroll event reached Chromium's capture listener and the region stayed at `scrollTop=0`. This establishes only that `IVROverlayView_003.PostOverlayEvent` did not deliver these synthetic scroll events in this run. A physical controller may follow a different path.

| Check | First probe | Final probe |
| --- | --- | --- |
| Unique shared lock and standby gate | Acquired; activity 3, battery 99% | Acquired; activity 3, battery 100% |
| Scroll region | 160 px viewport, 716 px content | 160 px viewport, 716 px content |
| Native pointer | Moved over region | Trusted pointer move reached iframe |
| Injected scroll | Smooth 309 | Smooth 309, then discrete 305 |
| Wheel events / offset | 0 / 0 → 0 | 0 / 0 → 0 |
| Other sample checks | Passed | Passed |
| Cleanup | Power restored to `false/5`, recovery timer removed, owned lock released; battery 99% | Same cleanup; battery 99% |

Both runs captured changed stereo compositor frames and a `/dev/video99` mirror frame, saved only in private folders `/tmp/framey-native-scroll-probe/` and `/tmp/framey-native-scroll-events/`. No room pixels are committed. The final run's `result.json` reported `passed=true`, `cleanupErrors=[]`, `powerRecoveryRemoved=true` and `lockReleased=true`. Here `passed` covers the sample setting, quick action, slider, text and cleanup checks; **native scroll did not pass**. The final immediate SteamVR activity was 0 after the temporary wake; original power settings were restored and read back. No person wore the headset, and physical controller scrolling, rays, haptics, keyboard, optical readability and comfort remain unverified. The hourly worn-check schedule remains enabled.

## Post-#294 exact-main sample check

After PR #294 merged, the **unmodified** `scripts/framey-vr-check.py --exercise` from exact main `c38e7e8da459e44a9a717d15e6a07ab8a8e8ef8d` exited 0 on the real Frame. Locked preflight found activity 3 standby, proximity 6.3125 and battery 99%. The sample saved `{"enabled": true}` through trusted synthetic OpenVR input and the live Decky backend, read the file independently, then reopened a fresh iframe with the value retained. Quick action, slider value 50 and text entry completed; compositor frames changed and the mirror capture returned a frame. The old scroll diagnostic still reported no offset movement.

The run removed its temporary services and recovery timer, restored/read back power `false/5`, reported no cleanup errors, and released only its owned lock. Its immediate activity was 0 after the temporary wake. Private captures/result are under `/tmp/framey-post294/` outside Git. This was one setting activation, so it does not prove the new rapid-double-input guard on physical controllers. No person wore the headset.
