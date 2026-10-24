#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ndk=${ANDROID_NDK_HOME:-"$HOME/Library/Android/ndk/30.0.16248370"}
cmake -S "$here" -B "$here/build-android" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 \
  -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release
cmake --build "$here/build-android"
mkdir -p "$here/prebuilt/arm64-v8a"
# Committed and shipped gzipped: electron-builder's 7-Zip applies its ARM64
# branch filter to a bare arm64 ELF, which the Windows installer's extractor
# can't decode, so the installed app silently lacked the library.
shasum -a 256 "$here/build-android/libXrApiLayer_FRAME_compat.so"
gzip -9 -n -c "$here/build-android/libXrApiLayer_FRAME_compat.so" > "$here/prebuilt/arm64-v8a/libXrApiLayer_FRAME_compat.so.gz"
