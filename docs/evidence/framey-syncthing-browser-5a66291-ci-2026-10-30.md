# Combined browser CI at exact #479 head, 30 October 2026

The AMD64 combined browser/signed-package CI artifact at exact head
`5a6629155b4b9b9822f6d2c216b47a377b59f2e0` passes independent audit.
Run `41060673311`, artifact `12980797871`, archive SHA-256
`9d948fee3677f401aea3a93e5d2f1669b73e8b1ced156db6c87e14ddbf80a121`.
The [JSON](framey-syncthing-browser-5a66291-ci-2026-10-30.json) retains all 25
verified source fingerprints, signed/native results, selected RPC journal,
process observations, sandbox properties and capture hashes.

The actual generated panel, published frontend plus candidate patch, released
Decky 3.3.0 and signed Syncthing 1.27.3 operate together inside the networkless
VM. Synthetic DOM input completes fresh setup, Stop, Start and Stop. The browser
makes 68 actual RPC calls through the private test bridge. Four renderers have
verified browser ancestry, seccomp 2 and no-new-privileges 1. Actual signed
process PIDs differ after restart. Existing signature/process/namespace, two-way
sync, nine setup, 17 lifecycle, 18 ownership refusal, 12 migration and preserving
uninstall checks pass. Owned browser/bridge and QEMU cleanup passes.

All four captures were visually inspected:

- [Running](framey-syncthing-browser-5a66291-running1-2026-10-30.png): the private
  folder and both devices are populated.
- [Stopped](framey-syncthing-browser-5a66291-stopped2-2026-10-30.png): Stopped after
  the first actual stop.
- [Restarted](framey-syncthing-browser-5a66291-restarted3-2026-10-30.png): Running
  with the private folder and both devices restored.
- [Stopped again](framey-syncthing-browser-5a66291-stopped4-2026-10-30.png): Stopped
  after the second actual stop.

The restart DOM snapshot was emitted before the folder rows populated, while
its later screenshot visibly includes them. The initial independent audit's
assumption that both snapshots already contained the folder was corrected after
reading the retained snapshot and inspecting the actual image. No CI gate,
production behavior or fixture was relaxed. This run uses automatic port
discovery; manual fallback was not exercised.

This is a private-bridge desktop browser test. It does not verify the production
browser parent over HTTP, actual Steam CEF, managed installation, ARM64 browser,
real Frame or physical controllers. At the time of that audit the separate parent-browser trial was
failed/pending; installation stays blocked. The [completed native audits](framey-syncthing-native-merge-479-2026-10-30.md)
subsequently verified both signed ARM64 results before #479 merged. No release
is credited here.


## Later local parent result

The parent-failure statements above record the state at the audited merge.
Later strict local AMD64 replay12 passed at private source `a4f37b6`, with all
123 source fingerprints and eight captures independently checked. It used
synthetic CEF/receipt data and did not establish ARM64 parent, actual Steam CEF,
managed installation, real Frame or physical-controller behavior. The published
follow-up [#486](https://github.com/saphid/frame-control/pull/486) carries the
candidate, durable evidence and a separate exact-head production-parent CI gate.
Its published-head results must pass independently. Installation remains blocked.
