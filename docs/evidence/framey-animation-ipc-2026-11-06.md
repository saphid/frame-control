# Animation Changer child IPC EOF repair — 2026-11-06

## Observed failure

Exact #562 head `80650f7e2035b02ad81f46239fe9e600c2f17228` failed [native AMD64 job 127766096798](https://github.com/saphid/frame-control/actions/runs/42179500365/job/127766096798). Animation Changer store 23/1.3.2 completed private apply/reset RPCs, but Decky sent SIGKILL after its five-second child shutdown deadline. The parent exited zero; that is not clean plugin shutdown. The primary gate rejected it without retrying.

Artifact `13486236635` archive SHA-256 is `01d39e34f9e3c8e0b944dd05b143d9df7e13be867f052906dcb460c81b8020cd`. Its exact checkout, loader, all 49 runtime source fingerprints and console digest were independently verified. Failed evidence is retained separately; the companion JSON contains the failure observation and local follow-up.

## Exact scope

Only archive SHA-256 `f2c62b90ca60d8a80b6d0f75d8027552b1509c7a05842c6f4a24a9072846d133` receives the existing child-local `framey_decky_ipc.py` adapter. The loader parent transport stays original. The adapter ends only the connection loop when Decky's reader returns an empty string at EOF, so a later connection can still receive RPC replies.

The published backend and prior override-preservation suffix remain intact. Previous managed backend SHA-256 is `1f09235c0acac021186e8b95e88cbca2fe6c4c6d0a3c94d06c9af8a33837a44c`; repaired SHA-256 is `41e8b19b457fa19f7eb080736a84dac5ce05a787ff4a0279b15df0666502d068`. Both retain preservation helper SHA-256 `1be712568c6675dd77cff64eb0b06a97569d80daa81d269533c2ea8d3be20188`. The repaired IPC adapter SHA-256 is `43ad5a8e19270347e6efaeb59ea94f06f149b525ac928e27298325c0b30500e8`. Existing receipts require Update/reinstall. Unknown digests receive no adapter; missing helper input rejects an update while preserving installed bytes.

## Local verification

Published Decky **3.3.0 AMD64**, pinned loader SHA-256 `e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`, ran in networkless/device-free disposable containers as UID 1100. No real home, Steam session, headset, media or repository was used.

- Primary: private default/apply/repeat/switch/reset RPCs preserve all three original movies and their inodes. Explicit Unix peer EOF is followed by a successful getState RPC. Two parent-only stops finish cleanly in **0.215/0.225 seconds**, including the published unload hook, no forced kill, no shutdown errors and no remaining recorded descendants. Restart discovers the plugin and retains private settings/movie bytes. An unrelated sibling survives both stops.
- Negative: remove only the new prefix/helper, assert the exact previous managed body, repeat the same file-preservation RPCs, then close the peer. Decky's parent exits zero but requires one forced child kill in **5.224 seconds**. The control remains explicitly unsuccessful compatibility evidence; private bytes and the unrelated sibling are preserved.
- All **49 probe source fingerprints** match unchanged local source bytes on the final run. The earlier development run is not used to bind final source evidence.
- **139 focused local tests pass with zero skips**: override safety, exact installation/receipt, failed-update preservation, compatibility status and primary shutdown gate/store transactions. Compilation, generated documentation and whitespace checks pass.
- Hosted fake-Frame e2e now asserts the installed backend and both helper hashes. Its fresh hosted result is pending.

Reproduce locally with `python3 scripts/framey-test-decky-runtime.py --case 23 --loader /path/to/digest-verified/PluginLoader --output /tmp/private-result.json`. This runs the primary and explicit previous-managed negative. No stop timeout or forced-kill gate was relaxed.

## Limits

Fresh exact-head hosted AMD64/ARM64, full e2e and package qualification are pending. These checks do not establish real Steam video playback, downloads, legacy migration, real Frame behavior, worn visibility or physical-controller usability. Compatibility stays partial.

The separate historical ARM64 Syncthing migration stop timeout remains unexplained. This Animation Changer child repair is not evidence of its cause or a fix. Release remains held on every release gate, including the uniquely locked real Frame smoke.
