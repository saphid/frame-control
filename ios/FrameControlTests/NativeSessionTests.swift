import Foundation
import XCTest
#if !NATIVE_CONTRACT_STANDALONE
@testable import Frame_Control
#endif

final class NativeSessionTests: XCTestCase {
    func testSavedAddressesRoundTripWithoutLosingPortOrIPv6() throws {
        for host in ["frame.local", "100.100.100.2", "2001:db8::42", "fe80::1%en0"] {
            for port in [22, 2222, 65535] {
                let target = FrameSettings(host: host, port: port, user: "alex")
                let saved = try JSONDecoder().decode(FrameSettings.self, from: JSONEncoder().encode(target))
                XCTAssertEqual(FrameSettings.parse(host: saved.address, user: saved.user), target)
            }
        }
        XCTAssertEqual(FrameSettings.parse(host: "  [2001:db8::42]:2222\n", user: " steamos "),
                       FrameSettings(host: "2001:db8::42", port: 2222))
        for host in ["", "frame.local:0", "frame.local:65536", "frame.local:no", "[::1]:no", "[::1]junk", "[::1"] {
            XCTAssertNil(FrameSettings.parse(host: host, user: "steamos"), host)
        }
    }

    func testManualTargetWinsAndSearchCallbacksExpire() {
        XCTAssertEqual(FrameSearchState.address(manual: " 100.100.100.2:2222 ", discovered: "192.168.1.237"), "100.100.100.2:2222")
        XCTAssertEqual(FrameSearchState.address(manual: " \n", discovered: "192.168.1.237"), "192.168.1.237")
        XCTAssertEqual(FrameSearchState.address(manual: "", discovered: nil), "frame.local")
        var search = FrameSearchState()
        let bonjour = search.start(manualAddress: nil)
        XCTAssertTrue(search.discovers)
        let manual = search.start(manualAddress: "100.100.100.2:2222")
        XCTAssertFalse(search.discovers)
        XCTAssertFalse(search.accepts(bonjour))
        XCTAssertTrue(search.accepts(manual))
        search.stop()
        XCTAssertFalse(search.accepts(manual))
        _ = search.start(manualAddress: "")
        XCTAssertTrue(search.discovers)
    }

    func testRecoveryIsBoundedUntilAnExplicitRetry() {
        var page = WebDocumentState()
        XCTAssertTrue(page.shouldReloadAfterFailure())
        page.beginDocument()
        page.ready("reloaded", generation: page.generation)
        XCTAssertFalse(page.shouldReloadAfterFailure())
        XCTAssertFalse(page.shouldReloadAfterFailure())
        page.resetSession()
        XCTAssertTrue(page.shouldReloadAfterFailure())
    }

    func testReplacementDocumentsCannotConsumeQueuedLinks() throws {
        var page = WebDocumentState()
        var queue = ["first", "second"]
        XCTAssertNil(page.beginDelivery())
        let oldGeneration = page.generation
        page.ready("first document", generation: oldGeneration)
        let oldDelivery = try XCTUnwrap(page.beginDelivery())
        XCTAssertNil(page.beginDelivery(), "Serialize delivery while an acknowledgement is pending")
        XCTAssertTrue(page.shouldReloadAfterFailure())
        page.ready("stale readiness", generation: oldGeneration)
        XCTAssertNil(page.beginDelivery())
        if page.finishDelivery(oldDelivery, acknowledged: true) { queue.removeFirst() }
        XCTAssertEqual(queue, ["first", "second"])
        page.ready("replacement", generation: page.generation)
        let failedDelivery = try XCTUnwrap(page.beginDelivery())
        if page.finishDelivery(failedDelivery, acknowledged: false) { queue.removeFirst() }
        XCTAssertEqual(queue, ["first", "second"])
        XCTAssertNil(page.beginDelivery(), "An evaluation error needs fresh readiness")
        page.ready("replacement", generation: page.generation)
        let liveDelivery = try XCTUnwrap(page.beginDelivery())
        if page.finishDelivery(liveDelivery, acknowledged: true) { queue.removeFirst() }
        XCTAssertEqual(queue, ["second"])
        XCTAssertNotNil(page.beginDelivery())
        page.beginDocument()
        XCTAssertNil(page.beginDelivery(), "Even healthy main-document navigation resets readiness")
    }

    func testPreferencesPersistAcrossSessionsAndRejectOtherKeysAndValues() throws {
        let suite = "frame-control-contract-\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let first = FramePreferences(defaults: defaults)
        XCTAssertEqual(first.read(), [:])
        XCTAssertTrue(first.write(key: "mvSeparate", value: "0"))
        XCTAssertTrue(first.write(key: "padUsed", value: "1"))
        let second = FramePreferences(defaults: try XCTUnwrap(UserDefaults(suiteName: suite)))
        XCTAssertEqual(second.read(), ["mvSeparate": "0", "padUsed": "1"])
        for (key, value) in [("other", "1"), ("mvSeparate", "false"), ("padUsed", ""), ("padUsed", "2")] {
            XCTAssertFalse(second.write(key: key, value: value))
        }
        XCTAssertEqual(first.read(), ["mvSeparate": "0", "padUsed": "1"])
        XCTAssertNil(defaults.object(forKey: "frame.control.preference.other"))
        defaults.set("bad", forKey: "frame.control.preference.mvSeparate")
        defaults.set("1", forKey: "frame.control.preference.unknown")
        XCTAssertEqual(second.read(), ["padUsed": "1"])
        defaults.set(true, forKey: "frame.control.preference.padUsed")
        XCTAssertEqual(second.read(), [:], "Only stored strings are supported")
    }

}
