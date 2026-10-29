# Publisher checkout gate, 29 October 2026

The release publisher previously printed a note when its local
`app/package.json` version differed from the requested tag, then continued.
That left a path to run the publisher's verifier and release-note code from a
checkout other than the exact release commit. The remote CI, tagged installers,
checksums, independent asset audit and Frame smoke gates still applied, but a
different local checkout could carry older gate logic or notes.

Both dry run and publication now require the local checkout's `HEAD` to equal
the exact remote tag commit returned by `verify-release-gates.py`. They fail
closed if the checkout cannot be inspected, has tracked or untracked changes,
or the commit's `app/package.json` version differs from the requested tag.
These checks run before reading or mutating a release draft. No bypass flag was
added.

The stand-in GitHub publisher suite passed 19 tests. New cases verified that a
wrong commit, dirty checkout, failed status inspection and wrong package
version all stop before an upload or release PATCH. Existing successful dry-run
and publication cases still pass with an exact fake commit and version. This
evidence uses local fixtures only; it is not a tagged installer build, real
Frame smoke or release publication.
