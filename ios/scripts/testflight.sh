#!/usr/bin/env bash
# Archive, inspect, and optionally upload the iOS app to TestFlight.
# The API key file and signing certificate remain outside this checkout.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ios/scripts/testflight.sh archive|export|upload

Required for all modes:
  FRAME_IOS_TEAM_ID       Apple Developer team ID
  FRAME_ASC_KEY_ID        App Store Connect API key ID
  FRAME_ASC_ISSUER_ID     App Store Connect API issuer UUID
  FRAME_ASC_KEY_PATH      Absolute path to the private AuthKey_*.p8 file
  FRAME_IOS_OUTPUT        Absolute output directory for this build

Required for archive:
  FRAME_IOS_VERSION       App Store version, for example 0.4.59
  FRAME_IOS_BUILD         New, unused integer build number

archive creates a signed .xcarchive and checks its bundle ID, version, build,
and code signature. export produces an IPA for inspection. upload exports the
same archive directly to App Store Connect for TestFlight processing.
EOF
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
mode=${1:-}
if [[ $# != 1 || ! $mode =~ ^(archive|export|upload)$ ]]; then usage >&2; exit 2; fi
if [[ $(uname -s) != Darwin ]]; then echo 'TestFlight builds require macOS with Xcode.' >&2; exit 2; fi
for command in xcodebuild /usr/libexec/PlistBuddy codesign; do
  if ! command -v "$command" >/dev/null; then echo "Missing $command" >&2; exit 2; fi
done

for key in FRAME_IOS_TEAM_ID FRAME_ASC_KEY_ID FRAME_ASC_ISSUER_ID FRAME_ASC_KEY_PATH FRAME_IOS_OUTPUT; do
  if [[ -z ${!key:-} ]]; then echo "Missing $key" >&2; exit 2; fi
done
if [[ ! $FRAME_IOS_TEAM_ID =~ ^[A-Z0-9]{10}$ || ! $FRAME_ASC_KEY_ID =~ ^[A-Z0-9]{10}$ ||
      ! $FRAME_ASC_ISSUER_ID =~ ^[0-9A-Fa-f-]{36}$ ]]; then
  echo 'Invalid Apple team, API key, or issuer identifier.' >&2; exit 2
fi
if [[ $FRAME_ASC_KEY_PATH != /* || ! -f $FRAME_ASC_KEY_PATH || $FRAME_IOS_OUTPUT != /* ]]; then
  echo 'FRAME_ASC_KEY_PATH must name a file and both paths must be absolute.' >&2; exit 2
fi

ios_root=$(cd "$(dirname "$0")/.." && pwd -P)
archive="$FRAME_IOS_OUTPUT/FrameControl.xcarchive"
app="$archive/Products/Applications/Frame Control.app"
bundle_id=com.saphid.framecontrol
auth=(-authenticationKeyPath "$FRAME_ASC_KEY_PATH"
      -authenticationKeyID "$FRAME_ASC_KEY_ID"
      -authenticationKeyIssuerID "$FRAME_ASC_ISSUER_ID")

if [[ $mode == archive ]]; then
  if [[ ! ${FRAME_IOS_VERSION:-} =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ||
        ! ${FRAME_IOS_BUILD:-} =~ ^[1-9][0-9]*$ ]]; then
    echo 'Set FRAME_IOS_VERSION and a new positive integer FRAME_IOS_BUILD.' >&2; exit 2
  fi
  if [[ -e $archive ]]; then echo "Archive already exists: $archive" >&2; exit 2; fi
  mkdir -p "$FRAME_IOS_OUTPUT"
  xcodebuild -project "$ios_root/FrameControl.xcodeproj" -scheme FrameControl \
    -configuration Release -destination 'generic/platform=iOS' \
    -archivePath "$archive" -allowProvisioningUpdates "${auth[@]}" \
    DEVELOPMENT_TEAM="$FRAME_IOS_TEAM_ID" CODE_SIGN_STYLE=Automatic \
    MARKETING_VERSION="$FRAME_IOS_VERSION" CURRENT_PROJECT_VERSION="$FRAME_IOS_BUILD" \
    archive
  for entry in "CFBundleIdentifier:$bundle_id" \
               "CFBundleShortVersionString:$FRAME_IOS_VERSION" \
               "CFBundleVersion:$FRAME_IOS_BUILD"; do
    key=${entry%%:*}; expected=${entry#*:}
    actual=$(/usr/libexec/PlistBuddy -c "Print :$key" "$app/Info.plist")
    if [[ $actual != "$expected" ]]; then
      echo "$key mismatch: expected $expected, got $actual" >&2; exit 1
    fi
  done
  codesign --verify --deep --strict "$app"
  echo "Signed archive ready: $archive"
  exit 0
fi

if [[ ! -d $app ]]; then echo "Archive missing: $archive" >&2; exit 2; fi
actual=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app/Info.plist")
if [[ $actual != "$bundle_id" ]]; then echo "Unexpected bundle ID: $actual" >&2; exit 1; fi
codesign --verify --deep --strict "$app"

options=$(mktemp "${TMPDIR:-/tmp}/frame-testflight-export.XXXXXX")
trap 'rm -f "$options"' EXIT
destination=export
export_path="$FRAME_IOS_OUTPUT/export"
if [[ $mode == upload ]]; then
  destination=upload
  export_path="$FRAME_IOS_OUTPUT/upload"
fi
cat > "$options" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key><string>app-store-connect</string>
  <key>destination</key><string>$destination</string>
  <key>signingStyle</key><string>automatic</string>
  <key>teamID</key><string>$FRAME_IOS_TEAM_ID</string>
  <key>manageAppVersionAndBuildNumber</key><false/>
</dict></plist>
EOF
if [[ -e $export_path ]]; then
  echo "Export path already exists: $export_path" >&2; exit 2
fi
xcodebuild -exportArchive -archivePath "$archive" \
  -exportPath "$export_path" -exportOptionsPlist "$options" \
  -allowProvisioningUpdates "${auth[@]}"
if [[ $mode == export ]]; then
  echo "IPA ready for inspection: $export_path"
else
  echo 'Upload submitted to App Store Connect; check TestFlight processing and tester availability.'
fi
