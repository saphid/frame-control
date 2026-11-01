# Exact integrated RadiYo head: hosted native AMD64 and ARM64

## Announcement

The exact integrated RadiYo head `2d530add215db0b308b674d0bb9f588272973326` passes published Decky 3.3.0 native qualification on AMD64 and ARM64. Each architecture discovers and probes 47 cases with 593 RPC calls, including nine expected regression controls. This closes the combined-source ARM64 native gap; full CI and all triggered package modes remain separate pending gates. No headset or release claim.

## Evidence

Both artifacts belong to [run 41235136552](https://github.com/saphid/frame-control/actions/runs/41235136552) at the exact head. Downloaded ZIP SHA-256 matches GitHub's published digest, and every one of the 21 report source fingerprints matches that head. Both published loader digests verify. Native artifacts: AMD64 `13055995178`, ARM64 `13055500820`.

- RadiYo repaired/prior-managed: 9/7 RPCs on each architecture. Both TLS methods reject self-signed HTTPS. Loopback station/redirect readbacks, restart/discovery, owned install/remove/receipt and two positive parent-only stops verify. Repaired stops: AMD64 0.174/0.174 seconds; ARM64 0.215/0.214 seconds. Prior forced-stop reproductions remain negative at 5.226/5.227 seconds.
- TabMaster repaired/original/prior-managed: 47/48/47 RPCs per architecture. Private settings/backup/restart readbacks, original restore refusal and previous forced-stop control remain intact; positive original unload hooks complete without forced kills.
- Simple Timer: 31/10/18 RPCs per architecture. Four repaired clean stops, hashed/decoded settings/deadline snapshots and original/prior-managed negatives verify. All source hashes match the same integrated source; production shared adapter and helper boundaries remain unchanged.

[Audit](framey-radiyo-main13360b-hosted-native-2026-10-31.json), [raw native reports, inventories, independent verifiers/readbacks](framey-radiyo-main13360b-hosted-native-2026-10-31-raw.json.gz), SHA-256 `976fabe340cc2ec371f13b6fafe78901f47faea2342a2bd3a96ef0a4e98b5b43`. Raw report/ZIP hashes are retained in the packet. Full downloaded artifacts remain in the linked run and local `build-watch/pr520-native-artifacts381`.

## Limits

These are native artifact results, not an all-green PR or release qualification. Full CI, ownership and all package modes still require final exact-head review. Nine intentional regression failures remain negative controls. Generic clean-runtime qualification remains false; socket/JSON diagnostics are not explained away. Real radio services/audio, managed Frame, actual Steam CEF and wearer/controller use are unverified. No headset, schedules or pre-existing data touched. Final current-main CI/feedback/mergeability and all release gates remain mandatory.
