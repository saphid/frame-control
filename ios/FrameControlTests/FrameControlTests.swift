import CryptoKit
import Foundation
import XCTest
@testable import Frame_Control

final class InstallLinkTests: XCTestCase {
    func testAcceptsManifestAndURLLinks() {
        XCTAssertEqual(InstallLink("frame-control://install?manifest=https://example.com/app.json"),
                       InstallLink("frame-control://install/?manifest=https://example.com/app.json"))
        XCTAssertEqual(InstallLink("frame-control://install?url=https://example.com/a.apk")?.kind, .url)
        XCTAssertEqual(InstallLink("FRAME-CONTROL://install?manifest=https://example.com/m.json")?.target, "https://example.com/m.json")
    }

    func testRejectsAnythingElse() {
        for raw in ["frame-control://other?url=https://example.com/a.apk",
                    "frame-control://user@install?url=https://example.com/a.apk",
                    "frame-control://user:pw@install?url=https://example.com/a.apk",
                    "frame-control://install:8080?url=https://example.com/a.apk",
                    "frame-control://install?url=ftp://example.com/a.apk",
                    "frame-control://install?url=https://user:pw@example.com/a.apk",
                    "frame-control://install?url=https://example.com/a%0Ab.apk",
                    "frame-control://install?url=https://example.com/a\nb.apk",
                    "frame-control://install?url=https://example.com/a&manifest=https://example.com/b",
                    "frame-control://install?url=https://a.example/x&url=https://b.example/y",
                    "frame-control://install?url=",
                    "frame-control://install/deeper?url=https://example.com/a.apk",
                    "https://example.com/?url=https://example.com/a.apk",
                    "frame-control://install?url=https://example.com/" + String(repeating: "a", count: 2100)] {
            XCTAssertNil(InstallLink(raw), raw)
        }
    }
}

final class FrameLinkTests: XCTestCase {
    func testParseCommandOutputFailsClosedWithoutSentinel() {
        let ok = FrameLink.parseCommandOutput("hello\n@@rc=0\n")
        XCTAssertEqual(ok.output, "hello")
        XCTAssertEqual(ok.status, 0)

        let failed = FrameLink.parseCommandOutput("boom\n@@rc=17\n")
        XCTAssertEqual(failed.output, "boom")
        XCTAssertEqual(failed.status, 17)

        let truncated = FrameLink.parseCommandOutput("partial output without marker\n")
        XCTAssertEqual(truncated.output, "partial output without marker")
        XCTAssertEqual(truncated.status, -1)

        let malformed = FrameLink.parseCommandOutput("bad\n@@rc=oops\n")
        XCTAssertEqual(malformed.output, "bad")
        XCTAssertEqual(malformed.status, -1)
    }
}

final class WebShellPolicyTests: XCTestCase {
    func testBridgeOriginRequiresMainFrameAndExactTunnelOrigin() throws {
        let loaded = try XCTUnwrap(URL(string: "http://127.0.0.1:41234/?key=abc"))
        XCTAssertTrue(WebShell.Coordinator.allowsBridgeOrigin(
            isMainFrame: true, scheme: "http", host: "127.0.0.1", port: 41234, loaded: loaded))
        XCTAssertFalse(WebShell.Coordinator.allowsBridgeOrigin(
            isMainFrame: false, scheme: "http", host: "127.0.0.1", port: 41234, loaded: loaded))
        XCTAssertFalse(WebShell.Coordinator.allowsBridgeOrigin(
            isMainFrame: true, scheme: "http", host: "127.0.0.1", port: 41235, loaded: loaded))
        XCTAssertFalse(WebShell.Coordinator.allowsBridgeOrigin(
            isMainFrame: true, scheme: "https", host: "127.0.0.1", port: 41234, loaded: loaded))
        XCTAssertFalse(WebShell.Coordinator.allowsBridgeOrigin(
            isMainFrame: true, scheme: "http", host: "example.com", port: 41234, loaded: loaded))
        XCTAssertFalse(WebShell.Coordinator.allowsBridgeOrigin(
            isMainFrame: true, scheme: "http", host: "127.0.0.1", port: 41234, loaded: nil))
    }

    func testNavigationAndExternalBrowserPolicies() throws {
        let loaded = try XCTUnwrap(URL(string: "http://127.0.0.1:41234/?key=abc"))
        for allowed in ["http://127.0.0.1:41234/", "http://127.0.0.1:41234/api/ping", "about:blank", "about:srcdoc", "blob:http://127.0.0.1:41234/id", "data:text/plain,hi"] {
            let url = try XCTUnwrap(URL(string: allowed))
            XCTAssertTrue(WebShell.Coordinator.allowsWebNavigation(url, loaded: loaded), allowed)
        }
        for blocked in ["http://127.0.0.1:9999/", "https://127.0.0.1:41234/", "https://example.com/", "file:///etc/passwd", "tel:1234567890", "shortcuts://run-shortcut?name=x"] {
            let url = try XCTUnwrap(URL(string: blocked))
            XCTAssertFalse(WebShell.Coordinator.allowsWebNavigation(url, loaded: loaded), blocked)
        }
        XCTAssertFalse(WebShell.Coordinator.allowsWebNavigation(try XCTUnwrap(URL(string: "http://127.0.0.1:41234/")), loaded: nil))

        for ext in ["https://github.com/saphid/frame-control", "http://example.com/docs"] {
            let url = try XCTUnwrap(URL(string: ext))
            XCTAssertEqual(WebShell.Coordinator.externalBrowserURL(url), url, ext)
        }
        for rejected in ["tel:1234567890", "sms:1234", "shortcuts://run-shortcut?name=x", "file:///etc/passwd", "javascript:alert(1)", "http://127.0.0.1:9999/", "http://localhost:8080/", "http://[::1]:8080/", "https:///path"] {
            let url = try XCTUnwrap(URL(string: rejected))
            XCTAssertNil(WebShell.Coordinator.externalBrowserURL(url), rejected)
        }
    }
}

final class HeadsetServerTests: XCTestCase {
    func testReadsThePortTheServerPrints() {
        XCTAssertEqual(HeadsetServer.port(in: "Frame Control on http://127.0.0.1:41234  (alias: frame; Ctrl-C to stop)\n"), 41234)
        XCTAssertNil(HeadsetServer.port(in: "Traceback (most recent call last):"))
        XCTAssertNil(HeadsetServer.port(in: "Frame Control on http://127.0.0.1:4"))  // more digits may follow
        XCTAssertNil(HeadsetServer.port(in: "Frame Control on http://127.0.0.1:99999 "))
    }

    func testBundleIsInTheApp() throws {
        let bundle = try HeadsetServer.Bundle.fromApp()
        XCTAssertGreaterThan(bundle.data.count, 100_000)
        XCTAssertEqual(bundle.version.count, 16)
    }
}

final class KeyTests: XCTestCase {
    func testAuthorizedKeysLine() {
        let line = DeviceKey.authorizedKeysLine(Curve25519.Signing.PrivateKey(), comment: "frame-control@iPhone")
        let parts = line.split(separator: " ")
        XCTAssertEqual(parts.count, 3)
        XCTAssertEqual(parts[0], "ssh-ed25519")
        XCTAssertEqual(Data(base64Encoded: String(parts[1]))?.count, 51)  // string "ssh-ed25519" + 32-byte key
        XCTAssertEqual(parts[2], "frame-control@iPhone")
    }

    func testShellQuote() {
        XCTAssertEqual(shellQuote("it's"), "'it'\\''s'")
    }
}
