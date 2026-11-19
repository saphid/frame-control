# Native sample settings merge, 14 November 2026

PR #698 merged as `7777eedf` after all 27 hosted checks passed. The actual-main
integration tree was identical to the checked head and passed 14 sample tests;
the GitHub merge tree and both parents match the independently verified result.
Both native architectures' full runtime and Terminal-candidate artifacts pass
independent size/digest, pinned-loader, input-source and console audits.

Both sample-specific artifacts independently match all 19 inputs and the
deterministic sample ZIP. Each records 18 real API2 calls with 12 expected
refusals, two full loader restarts, three saved-state hashes and 0600 modes, and
three clean parent-only stops with no recorded descendants or forced fixture
cleanup. Raw reports and all four console hashes verify. Earlier failed-run
evidence remains in the original sample integration record.

These are isolated backend checks. Browser, Frame HTTP/SSH, live headset,
physical controller, scrolling, VR keyboard and worn visibility are not proved.
