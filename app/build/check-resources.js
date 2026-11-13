// Checks that the app's resources hold what Frame Control can't work without.
// The OpenXR compatibility layer is why this exists: VR APK installs need its
// arm64-v8a library (ui/frame_android.py XR_COMPAT_FILES).
//
// As electron-builder's afterPack hook it checks the unpacked app. From the
// command line it checks an installed copy, which is what caught the Windows
// installer silently dropping the library (see .github/workflows/release.yml):
//   node build/check-resources.js INSTALLED_RESOURCES [REFERENCE_RESOURCES]
// With a reference (the unpacked build's resources), every regular file in it
// must also be in the installed copy with identical bytes.
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const REQUIRED = [
  "ui/server.py",
  "ui/vendor/hls-1.6.13.light.min.js",
  "ui/vendor/hls-LICENSE",
  "ui/vendor/react-18.3.1.min.js",
  "ui/vendor/REACT-LICENSE.txt",
  "ui/vendor/react-dom-18.3.1.min.js",
  "ui/vendor/REACT-DOM-LICENSE.txt",
  "ui/vendor/deckyfileserver-1.2.0/aarch64.gz",
  "ui/vendor/deckyfileserver-1.2.0/x86_64.gz",
  "ui/vendor/deckyfileserver-1.2.0/source.tar.gz",
  "ui/vendor/deckyfileserver-1.2.0/LICENSE.txt",
  "ui/vendor/deckyfileserver-1.2.0/GO-LICENSE.txt",
  "ui/vendor/deckyfileserver-1.2.0/README.md",
  "scripts/build-framey-fileserver.py",
  "ui/vendor/localsend-0.4.5/aarch64.gz",
  "ui/vendor/localsend-0.4.5/source.tar.gz",
  "ui/vendor/localsend-0.4.5/LICENSE.txt",
  "ui/vendor/localsend-0.4.5/GO-LICENSE.txt",
  "ui/vendor/localsend-0.4.5/README.md",
  "scripts/build-framey-localsend.py",
  "ui/vendor/psutil-7.2.2/aarch64.whl",
  "ui/vendor/psutil-7.2.2/x86_64.whl",
  "ui/vendor/psutil-7.2.2/LICENSE.txt",
  "ui/frame_power.py",
  "ui/frame_status.py",
  "scripts/frame_power_sample.py",
  "scripts/frame_power_report.py",
  "scripts/obs-headset-source.py",
  "ui/frame_android.py",
  "ui/frame_nxnative.py",
  "ui/nxnative.js",
  "frame/nxnative/stage.py",
  "frame/nxnative/build.py",
  "frame/nxnative/extract_romfs.py",
  "frame/nxnative/android-frame.patch",
  "frame/nxnative/README.md",
  "frame/nxnative/LICENSE.nxnative",
  "frame/nxnative/profiles/01002B30028F6000/game.tsv",
  "frame/nxnative/profiles/01002B30028F6000/dmsh_chain.h",
  "frame/nxnative/profiles/01002B30028F6000/pso_manifest.tsv",
  "frame/nxnative/profiles/01002B30028F6000/shader_facts.tsv",
  "frame/nxnative/profiles/01002B30028F6000/bf_want.tsv",
  "frame/nxnative/profiles/01002B30028F6000/cb_extent.tsv",
  "frame/nxnative/profiles/01002B30028F6000/c1_full.tsv",
  "frame/nxnative/profiles/01002B30028F6000/shader_map.tsv",
  "frame/nxnative/profiles/01002B30028F6000/shader_map.tsv.conflicts.tsv",
  "frame/nxnative/profiles/01002B30028F6000/shader_pairs.tsv",
  "frame/love/package.py",
  "frame/love/clipboard.py",
  "frame/love/SDLClipboardHandler.java",
  "frame/love/LICENSE.SDL.txt",
  "frame/love/README.md",
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

// Files under reference that are absent or differ in the installed copy.
function differences(dir, reference) {
  function digest(file) {
    const hash = crypto.createHash("sha256");
    const buffer = Buffer.allocUnsafe(1024 * 1024);
    const fd = fs.openSync(file, "r");
    try {
      let read;
      while ((read = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) {
        hash.update(buffer.subarray(0, read));
      }
    } finally {
      fs.closeSync(fd);
    }
    return hash.digest("hex");
  }
  const out = [];
  (function walk(rel) {
    for (const e of fs.readdirSync(path.join(reference, rel), { withFileTypes: true })) {
      const r = path.join(rel, e.name);
      if (e.isDirectory()) walk(r);
      else if (e.isFile()) {
        const installed = path.join(dir, r);
        const original = path.join(reference, r);
        if (size(installed) !== size(original) || digest(installed) !== digest(original)) {
          out.push(r.split(path.sep).join("/"));
        }
      }
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
    console.error(`${dir} is missing or differs from the unpacked build for:\n  ${[...new Set(problems)].join("\n  ")}`);
    process.exit(1);
  }
  console.log(`${dir}: all required resources present${reference ? ", and every file of " + reference : ""}`);
}
