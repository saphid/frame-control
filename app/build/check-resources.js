// electron-builder afterPack hook: fail the build if a resource the app can't
// work without is missing or empty in the packaged app. The OpenXR
// compatibility layer is the reason this exists: VR APK installs need its
// arm64-v8a library (ui/frame_android.py XR_COMPAT_FILES).
const fs = require("fs");
const path = require("path");

const REQUIRED = [
  "ui/server.py",
  "ui/frame_android.py",
  "frame/android/lepton-app.sh",
  "frame/openxr-compat/XrApiLayer_FRAME_compat.json",
  "frame/openxr-compat/prebuilt/arm64-v8a/libXrApiLayer_FRAME_compat.so",
];

function resourcesDir(context) {
  if (context.electronPlatformName === "darwin" || context.electronPlatformName === "mas") {
    const app = `${context.packager.appInfo.productFilename}.app`;
    return path.join(context.appOutDir, app, "Contents", "Resources");
  }
  return path.join(context.appOutDir, "resources");
}

function missing(dir) {
  return REQUIRED.filter((rel) => {
    try {
      return fs.statSync(path.join(dir, rel)).size === 0;
    } catch {
      return true;
    }
  });
}

exports.default = async function afterPack(context) {
  const dir = resourcesDir(context);
  const gone = missing(dir);
  if (gone.length) {
    throw new Error(`packaged app is missing required resources in ${dir}: ${gone.join(", ")}`);
  }
};
exports.missing = missing;
exports.REQUIRED = REQUIRED;
