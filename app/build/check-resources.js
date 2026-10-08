// Checks that the app's resources hold what Frame Control can't work without.
// The OpenXR compatibility layer is why this exists: VR APK installs need its
// arm64-v8a library (ui/frame_android.py XR_COMPAT_FILES).
//
// As electron-builder's afterPack hook it checks the unpacked app. From the
// command line it checks an installed copy, which is what caught the Windows
// installer silently dropping the library (see .github/workflows/release.yml):
//   node build/check-resources.js INSTALLED_RESOURCES [REFERENCE_RESOURCES]
// With a reference (the unpacked build's resources), every file in it must also
// be in the installed copy, at the same size.
const fs = require("fs");
const path = require("path");

const REQUIRED = [
  "ui/server.py",
  "ui/frame_android.py",
  "frame/android/lepton-app.sh",
  "frame/openxr-compat/XrApiLayer_FRAME_compat.json",
  "frame/openxr-compat/prebuilt/arm64-v8a/libXrApiLayer_FRAME_compat.so.gz",
];

function resourcesDir(context) {
  if (context.electronPlatformName === "darwin" || context.electronPlatformName === "mas") {
    const app = `${context.packager.appInfo.productFilename}.app`;
    return path.join(context.appOutDir, app, "Contents", "Resources");
  }
  return path.join(context.appOutDir, "resources");
}

function size(file) {
  try {
    return fs.statSync(file).size;
  } catch {
    return -1;
  }
}

// Required files that are missing or empty.
function missing(dir) {
  return REQUIRED.filter((rel) => size(path.join(dir, rel)) <= 0);
}

// Files under reference that aren't in dir at the same size.
function differences(dir, reference) {
  const out = [];
  (function walk(rel) {
    for (const e of fs.readdirSync(path.join(reference, rel), { withFileTypes: true })) {
      const r = path.join(rel, e.name);
      if (e.isDirectory()) walk(r);
      else if (e.isFile() && size(path.join(dir, r)) !== size(path.join(reference, r))) out.push(r.split(path.sep).join("/"));
    }
  })("");
  return out;
}

exports.default = async function afterPack(context) {
  const dir = resourcesDir(context);
  const gone = missing(dir);
  if (gone.length) {
    throw new Error(`packaged app is missing required resources in ${dir}: ${gone.join(", ")}`);
  }
};
exports.missing = missing;
exports.differences = differences;
exports.REQUIRED = REQUIRED;

if (require.main === module) {
  const [dir, reference] = process.argv.slice(2);
  if (!dir) {
    console.error("usage: node build/check-resources.js INSTALLED_RESOURCES [REFERENCE_RESOURCES]");
    process.exit(2);
  }
  const problems = [...missing(dir), ...(reference ? differences(dir, reference) : [])];
  if (problems.length) {
    console.error(`${dir} is missing or has the wrong size for:\n  ${[...new Set(problems)].join("\n  ")}`);
    process.exit(1);
  }
  console.log(`${dir}: all required resources present${reference ? ", and every file of " + reference : ""}`);
}
