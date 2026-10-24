"""iPhone packaging and Foundation contracts; no headset, downloads or Xcode build."""
import sandbox  # noqa: F401
import fnmatch
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BundleContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("ios_bundle_contract", ROOT / "ios/scripts/make_frame_bundle.py")
        cls.bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.bundle)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        with tarfile.open(fileobj=io.BytesIO(cls.bundle.build()), mode="r:gz") as archive:
            archive.extractall(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_required_resources_ship_to_both_clients(self):
        resources = ["frame/android/library_artwork.js", "frame/openxr-compat/XrApiLayer_FRAME_compat.json",
                     "frame/openxr-compat/prebuilt/arm64-v8a/libXrApiLayer_FRAME_compat.so.gz"]
        config = json.loads((ROOT / "app/package.json").read_text())
        for resource in resources:
            with self.subTest(resource=resource):
                self.assertTrue((self.root / resource).is_file(), resource)
                # Match the desktop's real resource filters as well as the phone archive.
                packaged = False
                for entry in config["build"]["extraResources"]:
                    source = entry["from"].removeprefix("../")
                    if Path(resource).is_relative_to(source):
                        relative = str(Path(resource).relative_to(source))
                        packaged |= any(fnmatch.fnmatch(relative, pattern) for pattern in entry.get("filter", ["**/*"]))
                self.assertTrue(packaged, "desktop resource contract: " + resource)

    def test_extracted_runtime_can_render_and_load_xr_layer(self):
        result = subprocess.run([sys.executable, "-I", "-B", "-c", """
import sys, zipfile
from unittest.mock import patch
sys.path.insert(0, 'ui')
import frame_android as android
with patch.object(android, 'ssh', return_value='rendered') as ssh:
    assert android.shortcut_tool('render', '/synthetic/app') == 'rendered'
    assert 'ART_RENDERER = ' in ssh.call_args.kwargs['input']
    assert len(ssh.call_args.kwargs['input']) > 1000
with zipfile.ZipFile('synthetic.apk', 'w') as apk:
    apk.writestr('lib/arm64-v8a/libopenxr_loader.so', b'synthetic loader')
files = android.xr_compat_files('synthetic.apk')
assert set(files) == set(android.XR_COMPAT_FILES)
assert files['lib/arm64-v8a/libXrApiLayer_FRAME_compat.so'].startswith(b'\\x7fELF')
"""], cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class NativeContracts(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "darwin" and shutil.which("swiftc"), "macOS Swift compiles actual Foundation production sources")
    def test_foundation_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "main.swift"
            main.write_text("import XCTest\nlet suite = XCTestSuite(forTestCaseClass: NativeSessionTests.self)\nsuite.run()\nexit(suite.testRun!.hasSucceeded ? 0 : 1)\n")
            executable = Path(tmp) / "native-contracts"
            developer = subprocess.check_output(["xcode-select", "-p"], text=True).strip()
            frameworks = str(Path(developer) / "Platforms/MacOSX.platform/Developer/Library/Frameworks")
            libraries = str(Path(developer) / "Platforms/MacOSX.platform/Developer/usr/lib")
            shared = str(Path(developer).parent / "SharedFrameworks")
            result = subprocess.run(["swiftc", "-I", libraries, "-L", libraries, "-F", frameworks, "-Xlinker", "-rpath", "-Xlinker", frameworks,
                                     "-Xlinker", "-rpath", "-Xlinker", libraries,
                                     "-Xlinker", "-rpath", "-Xlinker", shared,
                                     "-D", "NATIVE_CONTRACT_STANDALONE",
                                     str(ROOT / "ios/FrameControl/App/NativeSessionState.swift"),
                                     str(ROOT / "ios/FrameControlTests/NativeSessionTests.swift"),
                                     str(main), "-o", str(executable)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Executed 5 tests", result.stdout + result.stderr)

    @unittest.skipUnless(sys.platform == "darwin" and shutil.which("swiftc"), "macOS exercises the production finder with controlled probes")
    def test_finder_ignores_late_probes_after_edit_and_stop(self):
        harness = r'''import Foundation
actor Probes {
    var pending: [String: CheckedContinuation<Bool, Never>] = [:]
    func probe(_ host: String) async -> Bool {
        await withCheckedContinuation { pending[host] = $0 }
    }
    func has(_ host: String) -> Bool { pending[host] != nil }
    func answer(_ host: String) { pending.removeValue(forKey: host)!.resume(returning: true) }
}
@main struct FinderContracts {
    @MainActor static func wait(_ condition: () async -> Bool) async {
        for _ in 0..<100 {
            if await condition() { return }
            try! await Task.sleep(nanoseconds: 5_000_000)
        }
        fatalError("controlled callback did not run")
    }
    @MainActor static func main() async {
        let probes = Probes()
        let finder = FrameFinder(probe: { await probes.probe($0) }, discoveryEnabled: false)
        finder.start(fallback: "old.local")
        await wait { await probes.has("old.local") }
        finder.start(fallback: "100.100.100.2:2222", manual: true)
        await wait { await probes.has("100.100.100.2:2222") }
        await probes.answer("old.local")
        // Let the cancelled task return its deliberately late successful answer.
        try! await Task.sleep(nanoseconds: 20_000_000)
        precondition(finder.found == nil, "A stale probe replaced the edited target")
        await probes.answer("100.100.100.2:2222")
        await wait { finder.found != nil }
        precondition(finder.found?.host == "100.100.100.2:2222")
        finder.start(fallback: "stopped.local", manual: true)
        await wait { await probes.has("stopped.local") }
        finder.stop()
        await probes.answer("stopped.local")
        try! await Task.sleep(nanoseconds: 20_000_000)
        precondition(finder.found == nil, "A stopped search published a result")
        print("Production FrameFinder: stale and cancelled probes ignored; manual target retained")
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "FinderContracts.swift"
            main.write_text(harness)
            executable = Path(tmp) / "finder-contracts"
            result = subprocess.run(["swiftc", "-parse-as-library",
                                     str(ROOT / "ios/FrameControl/App/NativeSessionState.swift"),
                                     str(ROOT / "ios/FrameControl/SSH/FrameFinder.swift"),
                                     str(main), "-o", str(executable)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node executes the unmodified production bridge script")
    def test_bridge_preferences_and_document_acknowledgement(self):
        source = (ROOT / "ios/FrameControl/Web/WebShell.swift").read_text()
        bridge = source.split('static let bridge = """', 1)[1].split('"""', 1)[0]
        script = r'''const vm = require('node:vm');
const assert = require('node:assert/strict');
const calls = [];
const window = {webkit: {messageHandlers: {frameApp: {postMessage: body => {calls.push(body); return Promise.resolve(true)}}}}};
vm.runInNewContext(process.argv[1], {window, crypto: {randomUUID: () => 'document-42'}});
assert.equal(window.__frameInstallLink({}), false);
window.frameApp.preferences.read();
window.frameApp.preferences.write('mvSeparate', '0');
assert.equal(JSON.stringify(calls), JSON.stringify([
  {name: 'preferencesRead', arg: null}, {name: 'preferencesWrite', arg: {key: 'mvSeparate', value: '0'}}
]));
const received = [];
window.frameApp.onInstallLink(req => received.push(req));
assert.equal(calls.at(-1).name, 'installLinkReady');
assert.equal(calls.at(-1).arg, 'document-42');
assert.equal(window.__frameInstallLink({target: 'a'}), true);
assert.equal(received[0].target, 'a');
window.frameApp.onInstallLink(() => {throw new Error('callback failed')});
assert.throws(() => window.__frameInstallLink({}), /callback failed/);
'''
        result = subprocess.run(["node", "-e", script, bridge], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
