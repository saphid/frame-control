# Published release manifest guard

The publisher previously accepted an already published release, deleted its existing `update.json`, then attempted to upload a replacement. If that upload failed, running copies would lose the live update manifest. The publisher now refuses a non-draft release before any asset deletion or upload.

The stand-in GitHub API regression provides a published release with an existing `update.json` and verifies that publication fails without any mutating API call. On 2026-10-28, `python3 -m unittest discover -s tests -p test_publish_release.py -q` passed all 12 tests; `git diff --check` passed. Hosted CI remains the merge gate. No GitHub release or update channel was changed by this test.
