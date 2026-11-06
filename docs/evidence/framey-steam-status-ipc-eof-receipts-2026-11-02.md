# Steam Status receipt fixture correction — 2026-11-02

Implementation `d11ba8293d9cd01301fc0a9e3333fd31d1eafc09` changes only the compatibility test fixture from the
initial publication `cb1519a8f478b07702f561e7bb0ec2a141d68441`. Existing copies with only the verified-TLS shim
still lack the new child IPC EOF adapter, so their Update/reinstall notice must
remain. The fixture now checks original, TLS-only and fully repaired receipts.
Both older copies require Update, all remain partial, and only both shims clear
the generic missing-fix notice. No production behavior or security setting changes.

The initial publication's Windows job 125175388115, Linux job 125175387970 and
checks job 125175387962 failed this outdated expectation; exact metadata and
complete logs are retained. All **25 compatibility tests / zero skips** pass after
the correction. All **43 native source fingerprints** match the previously
verified repair; no fresh native execution is claimed for this test-only edit.
Fresh full exact-publication CI remains required. No main merge or release is
qualified. [Summary](framey-steam-status-ipc-eof-receipts-2026-11-02.json) · [Raw logs](framey-steam-status-ipc-eof-receipts-2026-11-02-raw.json.gz).
