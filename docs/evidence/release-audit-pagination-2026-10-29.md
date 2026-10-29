# Release audit pagination check, 29 October 2026

The independent installer audit previously returned on the first GitHub
release-list page containing a matching tag or draft title. A second matching
draft on a later page was never inspected. The audit could therefore report
one release while the complete list was ambiguous.

Local tests mocked two GitHub pages with the same version draft. The old code
accepted the first draft; the corrected lookup rejects the duplicate after
reading both pages. A second test finds a release on page two, and a full
20-page response fails closed because uniqueness cannot be established. All
13 focused `test_audit_release_assets.py` tests passed locally.

These are mocked API responses. No release asset was downloaded, no release
was changed, and this result is not a release verification or real Frame smoke.
