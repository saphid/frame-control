# Frame Control iOS 0.4.59 TestFlight upload, 5 November 2026

The iOS source was the exact pushed commit
`8cd2a5e822611471e044b5008d6b64a8c7dd535f`. Xcode 27.2 generated the
project and built an unsigned device archive. Its app had bundle ID
`com.saphid.framecontrol`, version `0.4.59`, and build `202611050600`.

Xcode exported the archive for App Store Connect with automatic managed
signing. The exported IPA passed `codesign --verify --deep --strict`, had an
Apple Distribution signature for team `NJZUMEA4BN`, and contained a
non-debuggable Store provisioning profile for the same bundle ID. Its
SHA-256 was
`a4ebca385508401d12834f760bab22feb32bfd84d6a800cfed24643050f2707d`.
The App Store Connect API key stayed on the Mac and was not copied into the
checkout or release artifacts.

The Xcode App Store Connect upload returned success. A subsequent read-only
App Store Connect API query found build
`04c02405-604f-42a0-8c1b-3a3b822ceacf` under app `6822547223`, with
marketing version `0.4.59`, build `202611050600`, platform iOS, and
processing state **VALID**. The build initially had missing export compliance
and was not in the public beta group. The earlier HTTP 403 came from a
relationship endpoint that does not support GET; the beta-group resource is
readable.

On 5 November, the build's exempt-encryption answer was set to match the
previous approved Frame Control build. The build then became eligible for
external beta review, and App Store Connect accepted the submission. Its
review state is **WAITING_FOR_REVIEW**. The public beta group still lists only
builds `202610160824` and `202610140516`; build `202611050600` is not yet
available through the public TestFlight link.

The earlier direct signed-archive attempt over SSH failed because the local
Apple Development key was unavailable to the noninteractive signing process
(`errSecInternalComponent`). The successful path signed at export time; the
repeatable script now follows that path.
