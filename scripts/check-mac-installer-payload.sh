#!/usr/bin/env bash
# Inspect the actual DMG and ZIP before either Mac installer is uploaded.
set -euo pipefail
shopt -s nullglob

cd "$(dirname "$0")/.."
references=(app/dist/*/'Frame Control.app')
if [[ ${#references[@]} -ne 1 ]]; then
  echo "expected one unpacked Mac app; found ${#references[@]}" >&2
  exit 1
fi
reference=${references[0]}
version=$(node -p "require('./app/package.json').version")

for extension in dmg zip; do
  packages=(app/dist/*."$extension")
  if [[ ${#packages[@]} -ne 1 ]]; then
    echo "expected one Mac $extension; found ${#packages[@]}" >&2
    exit 1
  fi
  scratch=$(mktemp -d)
  mounted=0
  cleanup() {
    if [[ $mounted -eq 1 ]]; then
      hdiutil detach -quiet "$scratch" || return 1
    fi
    rm -rf -- "$scratch"
  }
  trap cleanup EXIT
  if [[ $extension == dmg ]]; then
    hdiutil attach -quiet -readonly -nobrowse -mountpoint "$scratch" "${packages[0]}"
    mounted=1
  else
    ditto -x -k "${packages[0]}" "$scratch"
  fi

  packaged="$scratch/Frame Control.app"
  if [[ ! -d $packaged ]]; then
    echo "Mac $extension does not contain Frame Control.app" >&2
    exit 1
  fi
  actual=$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$packaged/Contents/Info.plist")
  if [[ $actual != "$version" ]]; then
    echo "Mac $extension app version $actual differs from $version" >&2
    exit 1
  fi
  lipo "$packaged/Contents/MacOS/Frame Control" -verify_arch "$(uname -m)"
  node app/build/check-resources.js "$packaged/Contents/Resources" "$reference/Contents/Resources"
  echo "verified Mac $extension package payload for $version on $(uname -m)"
  cleanup
  trap - EXIT
done
