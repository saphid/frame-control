#!/bin/zsh
# Archive Frame Control and upload it to TestFlight.
#
# Needs a paid Apple Developer Program team and an App Store Connect API key
# (Users and Access → Integrations → App Store Connect API, role App Manager):
#
#   ASC_KEY_ID=ABC123 ASC_ISSUER_ID=uuid ASC_KEY_PATH=~/.appstoreconnect/AuthKey_ABC123.p8 \
#     ios/scripts/testflight.sh
#
# TEAM_ID defaults to the team in this Mac's signing certificate. The build
# number is the current UTC time, so every upload is higher than the last.
set -euo pipefail

: "${ASC_KEY_ID:?set ASC_KEY_ID}" "${ASC_ISSUER_ID:?set ASC_ISSUER_ID}" "${ASC_KEY_PATH:?set ASC_KEY_PATH}"
TEAM_ID="${TEAM_ID:-NJZUMEA4BN}"
BUILD_NUMBER="${BUILD_NUMBER:-$(date -u +%Y%m%d%H%M)}"
# Resolve the key before changing directory; expand a quoted leading ~/.
key_path="${ASC_KEY_PATH/#\~\//$HOME/}"
key_path="${key_path:A}"
[[ -f "$key_path" ]] || { echo "no API key at $key_path" >&2; exit 1; }

cd "${0:A:h}/.."
out="build/testflight/$BUILD_NUMBER"
mkdir -p "$out"

auth=(-allowProvisioningUpdates
      -authenticationKeyPath "$key_path"
      -authenticationKeyID "$ASC_KEY_ID"
      -authenticationKeyIssuerID "$ASC_ISSUER_ID")

xcodegen generate
xcodebuild archive -project FrameControl.xcodeproj -scheme FrameControl \
  -configuration Release -destination generic/platform=iOS \
  -archivePath "$out/FrameControl.xcarchive" \
  DEVELOPMENT_TEAM="$TEAM_ID" CODE_SIGN_STYLE=Automatic \
  CURRENT_PROJECT_VERSION="$BUILD_NUMBER" "${auth[@]}"

# Check the archived build number, not just the argument passed.
archived=$(plutil -extract CFBundleVersion raw \
  "$out/FrameControl.xcarchive/Products/Applications/Frame Control.app/Info.plist")
[[ "$archived" == "$BUILD_NUMBER" ]] || { echo "archived build $archived, expected $BUILD_NUMBER" >&2; exit 1; }

cat > "$out/ExportOptions.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key><string>app-store-connect</string>
  <key>destination</key><string>upload</string>
  <key>teamID</key><string>$TEAM_ID</string>
  <key>signingStyle</key><string>automatic</string>
  <key>manageAppVersionAndBuildNumber</key><false/>
</dict></plist>
EOF

xcodebuild -exportArchive -archivePath "$out/FrameControl.xcarchive" \
  -exportOptionsPlist "$out/ExportOptions.plist" -exportPath "$out/export" "${auth[@]}"

echo "Uploaded build $BUILD_NUMBER. It shows in TestFlight once App Store Connect finishes processing."
