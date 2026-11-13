# Isolate TabMaster's restore negative from its IPC defect

The ARM64 [runtime job on `dc74edb`](https://github.com/saphid/frame-control/actions/runs/42135327591/job/127621884356)
passed the managed TabMaster case, including both clean parent-only stops and
private settings persistence. Its later restore negative failed on the second
stop: Decky sent one forced plugin kill after 5.226 seconds and the original
unload hook did not complete. The loader exited zero; that was correctly
insufficient for the strict lifecycle gate.

The negative had replaced the entire managed backend with the upstream source
and deleted the independent child IPC EOF adapter. That reproduces the restore
bug but also reintroduces the known EOF starvation defect. Ordinary fixture
RPCs close their connections, so avoiding the explicit closed-peer probe does
not isolate the restore defect. This is not treated as runner infrastructure
failure and the failed check is not bypassed.

The restore negative now prefixes the digest-verified upstream backend with
the unchanged managed IPC adapter. All original backend bytes, including the
broken `json.loads(settings_file)` restore method, remain intact. It must still
refuse a valid backup without altering settings or the backup. Its report
explicitly records the retained IPC repair and does not claim an unmodified
published backend or a qualified compatibility pass. It also receives the
explicit peer EOF challenge before its first stop. Both stops retain every
strict lifecycle assertion. The separate unload negative still removes the
adapter and must reproduce a forced kill before recovery.

An offline replay used the actual fixture-setup statements and pinned ZIP,
then executed the resulting backend with private settings and a synthetic
Decky socket. The old setup retained restore refusal but starved on EOF; the
new setup retained the same refusal and private bytes while returning from EOF
without dispatch. Seven runtime-coverage/IPC tests and Python compilation
passed. Native AMD64/ARM64 qualification remains a hosted-CI requirement; this
offline replay is not native loader, real Frame, wearer, controller, scrolling
or VR keyboard proof. No hardware was contacted.
