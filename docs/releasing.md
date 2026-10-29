# Releasing and updates

Frame Control checks for updates itself. The desktop app offers a new version
only once it's GitHub's **latest release**, and drafts and pre-releases never
count. So a build reaches people only when you publish it, after testing it.

## Steps

1. Bump `version` in `app/package.json`, commit, and push a tag:

   ```sh
   git tag v0.4.0 && git push origin v0.4.0
   ```

   `.github/workflows/release.yml` builds macOS, Windows and Linux, and
   attaches everything to a **draft** release for that tag. After all ten
   installers upload, the workflow also attaches `SHA256SUMS` built from
   GitHub's SHA-256 digests of those uploaded bytes. Nobody is
   offered a draft. Editing a draft while installers are uploading can make
   GitHub temporarily show its tag as `untagged-…`. The workflow finds that
   draft by its exact version title, restores the tag association and retries
   the affected upload; it refuses ambiguous matches.
   The Linux build runs `scripts/check-appimage-launch.py` before upload. It
   starts the built x86_64 AppImage on an isolated Xvfb display, checks that
   its bundled server answers, and checks that the server stops on exit. The
   check disables telemetry and update requests, and keeps extraction in its
   temporary profile. This CI test does not test a physical display, FUSE mount
   or a headset.

2. Independently download and inspect the draft's installers on an x86_64
   Linux host with `gh`, `dpkg-deb` and `xvfb-run` installed:

   ```sh
   scripts/audit-release-assets.py v0.4.0 \
     --report /tmp/frame-v0.4.0-assets.json --launch-x86-appimage
   ```

   The command downloads each of the ten installers by asset ID, verifies its
   size and SHA-256 against GitHub metadata, matches the downloaded
   `SHA256SUMS` byte for byte, checks package formats and versions, and starts
   the x86_64 AppImage with a temporary profile and isolated Xvfb display. It
   writes the report only after all checks pass. This does not prove that the
   Mac or Windows installers launch on physical machines. Test those packages
   separately when the required machines are available. An installed copy of
   the previous version won't offer the draft, so install it directly.

3. Write the release notes on the draft. The update banner links to them.

4. Publish:

   Confirm the exact tag commit's main CI and e2e, the locked real Frame smoke,
   release verification, independent package checks, and all four tagged
   installer builds have passed. Hold the release if any gate is failed,
   cancelled, skipped, still running, or unverified. The publisher also reads
   the exact commit's GitHub CI, native Decky runtime gate, and tagged build
   job records and refuses to
   publish unless every required job succeeded; it cannot prove physical
   headset or installer behavior on its own.

   Supply the saved smoke result to the publisher. Both its dry run and publish
   command reject a result from another or dirty commit, incomplete title or
   cleanup steps, a skip or failure, or an unconfirmed headset lock release:

   ```sh
   export FRAME_SMOKE_RESULT=/path/to/smoke-result.json
   python3 scripts/verify-frame-smoke-result.py "$FRAME_SMOKE_RESULT" \
     "$(git rev-parse 'v0.4.0^{commit}')"
   ```

   ```sh
   scripts/publish-release.sh --dry-run v0.4.0   # checks and shows update.json, changes nothing
   scripts/publish-release.sh v0.4.0
   ```

   The script checks that the tag is on GitHub, that exact-commit main CI
   (including e2e), native amd64/ARM64 Decky runtime checks, and the tagged
   release workflow are green with no failed, cancelled, skipped or running
   jobs in any exact-tag push run or attempt, and that all ten installers are
   attached, each with the SHA-256 digest GitHub records. It also checks
   that the draft does not begin with a `WITHDRAWN` notice, so the preserved
   v0.4.48 draft cannot accidentally be offered again. It checks
   that the uploaded `SHA256SUMS` digest matches a fresh list of those ten
   installer digests. It attaches
   `update.json` (the version, the notes, the release page and each
   installer's digest), verifies the uploaded asset's SHA-256 and downloads
   its bytes for an exact readback before publishing the release and marking
   it latest. It
   refuses an already published release before replacing its live update
   manifest; use a new tested release for changes after publication. It
   uses only the REST API: `gh release view` can't find a draft whose
   `tag_name` still reads `untagged-…`, and GraphQL is often rate-limited.
   Such a draft is found by its exact title (`Frame Control 0.4.0`, or that
   followed by `: subtitle`) and tied to the tag when it's published. The release page in `update.json` is always
   `releases/tag/<tag>`, because a draft's own address (`releases/tag/untagged-…`)
   stops working once it's published. From then on, running copies see the update. They check about 8
   seconds after starting, then every 6 hours, and anyone can use **Check for
   Updates…** (the app menu on macOS, the Help menu elsewhere).

   After publication, rerun `audit-release-assets.py` with a new report path.
   For a published release it also downloads `update.json`, verifies its
   GitHub SHA-256, and checks that the offered version, release page, notes,
   installer names, sizes, and digests match that release. This checks the
   updater channel's published bytes, which the draft audit cannot inspect.

To pull a bad release, mark the previous one as latest
(`gh release edit v0.3.9 --latest`) or turn the bad one back into a draft.
Copies that already updated stay on it. Nothing downgrades them.

## How a copy updates itself

`app/updater.js` reads `update.json` from
`github.com/saphid/frame-control/releases/latest/download/`. It falls back to the
REST API only when a release has no manifest, because the API allows just 60
unauthenticated requests an hour per IP address, shared by a whole household.
Then it downloads the installer for its platform and checks it
against the SHA-256 digest GitHub publishes for the asset. It refuses if the
digest is missing or doesn't match. Then:

| Installed from | Update |
|---|---|
| macOS `.dmg`, app in a writable folder such as Applications | The `.zip` is unpacked next to the app and its version checked. After the app quits, a small script swaps the new app in, putting the old one back if that fails, and reopens it. Updates don't get the download quarantine, so there's no `xattr` step. |
| Windows installer | The new `Setup` runs silently over the install (`/S --force-run`) and reopens the app. |
| Linux AppImage | The new AppImage replaces the old file and is started. |
| macOS app still on the disk image or translocated, Windows `.zip`, Linux `.deb` | The banner opens the release page instead. |

Version 0.3.1 and earlier have no updater, so people on them have to download
the new version once by hand.
