# Sample browser persistence accepted merge, 14 November 2026

PR #705 merged as `5adf2271` after all 18 hosted checks passed. The exact
current-main integration passes 26 focused sample, packaging and bridge tests,
plus the actual browser-to-native-backend replay. GitHub's merge tree and both
parents exactly match the independently tested integration.

The downloaded browser artifact independently matches its size and ZIP digest,
all 27 source bindings and the deterministic sample ZIP. Seven UI states match
seven actual native API2 RPCs, three saved JSON hashes and 0600 modes, two full
Decky restarts and three clean parent-only stops with no recorded descendants.
The current-main replay passes the same independent audit. All seven captures
from each replay were inspected. Full native and Terminal-candidate artifacts
on both architectures pass input/loader/console audits; both native sample
artifacts separately pass 18 RPCs, 12 expected refusals, invalid/future schema
preservation, saved-state and shutdown audits.

The first local current-main replay failed before any browser/RPC stage:
the image's Debian package fetch reached the existing 300-second build limit.
The same unchanged Containerfile built through host networking; the unmodified
runner then used that exact cached image and passed. Plugin execution retained
`--network none`. The temporary base image was removed. The failed report and
build logs remain in the compressed evidence, along with an earlier focused
test-selection error corrected before all 26 tests ran.

The browser uses a synthetic private parent/receipt/input and a loopback
HTTP-to-stdin bridge. This is AMD64 browser coverage. Production Frame HTTP/SSH,
ARM64 browser, real Steam CEF, physical controllers, scrolling, VR keyboard
and worn visibility remain unverified. Invalid-schema preservation belongs to
the separate native sample tests and is not claimed by the browser replay.
