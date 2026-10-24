import Foundation
import CryptoKit
import XCTest
@testable import Frame_Control

@MainActor
final class ScreenshotSyncTests: XCTestCase {
    private let old = HeadsetScreenshot(id: "1/10/20261024010000_1.jpg", size: 3, time: 1)
    private let new = HeadsetScreenshot(id: "1/10/20261024010001_1.jpg", size: 3, time: 2)

    private func temporary() throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: root) }
        return root
    }

    func testBaselineStabilityAtomicOriginalAndRestartDedup() async throws {
        let root = try temporary()
        let engine = try ScreenshotSyncEngine(root: root, photos: true)
        var downloads = 0, exports = 0
        let fetch: (HeadsetScreenshot) async throws -> Data = { _ in downloads += 1; return Data([1, 2, 3]) }
        let save: (URL, () -> Bool) async throws -> Void = { file, allowed in
            XCTAssertTrue(allowed())
            XCTAssertEqual(try Data(contentsOf: file), Data([1, 2, 3]))
            exports += 1
        }
        try await engine.reconcile([old], download: fetch, validate: { _ in true }, export: save)
        try await engine.reconcile([old, new], download: fetch, validate: { _ in true }, export: save)
        XCTAssertEqual(downloads, 0, "Do not import history or read a file still being written")
        try await engine.reconcile([old, new, new], download: fetch, validate: { _ in true }, export: save)
        XCTAssertEqual(downloads, 1)
        XCTAssertEqual(exports, 1)
        let restarted = try ScreenshotSyncEngine(root: root, photos: true)
        try await restarted.reconcile([old, new], download: fetch, validate: { _ in true }, export: save)
        XCTAssertEqual(downloads, 1)
        XCTAssertEqual(exports, 1)
        XCTAssertEqual(restarted.journal.receipts[new.id]?.destination, .saved)
    }

    func testInterruptedDownloadRetriesAndAppOnlyNeverExportsLater() async throws {
        let root = try temporary()
        let engine = try ScreenshotSyncEngine(root: root, photos: false)
        let fetch: (HeadsetScreenshot) async throws -> Data = { _ in Data([1, 2, 3]) }
        let noExport: (URL, () -> Bool) async throws -> Void = { _, _ in XCTFail("App-only item exported") }
        try await engine.reconcile([], download: fetch, validate: { _ in true }, export: noExport)
        try await engine.reconcile([new], download: fetch, validate: { _ in true }, export: noExport)
        do {
            try await engine.reconcile([new], download: { _ in Data([1]) }, validate: { _ in true }, export: noExport)
            XCTFail("Truncated original accepted")
        } catch {}
        XCTAssertFalse(FileManager.default.fileExists(atPath: engine.file(for: new.id).path))
        let restarted = try ScreenshotSyncEngine(root: root, photos: true)
        try await restarted.reconcile([new], download: fetch, validate: { _ in true }, export: noExport)
        try await restarted.reconcile([new], download: fetch, validate: { _ in true }, export: noExport)
        XCTAssertEqual(restarted.journal.receipts[new.id]?.destination, .appOnly)
        XCTAssertTrue(restarted.journal.receipts[new.id]!.downloaded)
    }

    func testDestinationChangeDuringDownloadAndPermissionPrompt() async throws {
        let engine = try ScreenshotSyncEngine(root: temporary(), photos: true)
        let noExport: (URL, () -> Bool) async throws -> Void = { _, _ in XCTFail("Destination changed while downloading") }
        try await engine.reconcile([], download: { _ in Data() }, validate: { _ in true }, export: noExport)
        try await engine.reconcile([new], download: { _ in Data() }, validate: { _ in true }, export: noExport)
        try await engine.reconcile([new], download: { _ in
            try engine.setPhotos(false)
            try engine.setPhotos(true)
            return Data([1, 2, 3])
        }, validate: { _ in true }, export: noExport)
        XCTAssertEqual(engine.journal.receipts[new.id]?.destination, .appOnly)

        let other = HeadsetScreenshot(id: "2/10/20261024010001_1.jpg", size: 3, time: 2)
        try await engine.reconcile([new, other], download: { _ in Data() }, validate: { _ in true }, export: noExport)
        do {
            try await engine.reconcile([new, other], download: { _ in Data([1, 2, 3]) }, validate: { _ in true }, export: { _, allowed in
                try engine.setPhotos(false)
                try engine.setPhotos(true)
                XCTAssertFalse(allowed(), "Re-enabling must not revive an export cancelled during consent")
                throw CancellationError()
            })
        } catch {}
        XCTAssertEqual(engine.journal.receipts[other.id]?.destination, .appOnly)
    }

    func testCancellationRejectsLateOriginalAndIdentityIncludesAccountAndApp() async throws {
        let engine = try ScreenshotSyncEngine(root: temporary(), photos: false)
        let variants = [new, HeadsetScreenshot(id: "2/10/20261024010001_1.jpg", size: 3, time: 2),
                        HeadsetScreenshot(id: "1/20/20261024010001_1.jpg", size: 3, time: 2)]
        let save: (URL, () -> Bool) async throws -> Void = { _, _ in XCTFail("Unexpected export") }
        try await engine.reconcile([], download: { _ in Data() }, validate: { _ in true }, export: save)
        try await engine.reconcile(variants, download: { _ in Data() }, validate: { _ in true }, export: save)
        try await engine.reconcile(variants, download: { _ in engine.stop(); return Data([1, 2, 3]) }, validate: { _ in true }, export: save)
        XCTAssertEqual(engine.journal.receipts.count, 3)
        XCTAssertTrue(engine.journal.receipts.values.allSatisfy { !$0.downloaded })
        XCTAssertNotEqual(engine.file(for: variants[0].id), engine.file(for: variants[1].id))
        XCTAssertNotEqual(engine.file(for: variants[0].id), engine.file(for: variants[2].id))
    }

    func testUncertainPhotosCommitIsNotDuplicatedAndCorruptLedgerFailsClosed() async throws {
        let root = try temporary()
        var journal = ScreenshotJournal()
        journal.observe([], photos: true)
        journal.observe([new], photos: true)
        journal.receipts[new.id]?.downloaded = true
        journal.receipts[new.id]?.destination = .committing
        try JSONEncoder().encode(journal).write(to: root.appendingPathComponent("receipts.json"))
        let engine = try ScreenshotSyncEngine(root: root, photos: true)
        try await engine.reconcile([new], download: { _ in XCTFail(); return Data() }, validate: { _ in true }, export: { _, _ in XCTFail("Possible duplicate Photos asset") })
        XCTAssertEqual(engine.journal.receipts[new.id]?.destination, .committing)
        try Data("broken".utf8).write(to: root.appendingPathComponent("receipts.json"))
        XCTAssertThrowsError(try ScreenshotSyncEngine(root: root, photos: true))
        XCTAssertFalse(HeadsetScreenshot(id: "../../private.jpg", size: 3, time: 2).valid)
    }

    func testPhotosFailureRetainsOriginalAndRetriesOnlyExport() async throws {
        let root = try temporary()
        let engine = try ScreenshotSyncEngine(root: root, photos: true)
        var downloads = 0, exports = 0
        let fetch: (HeadsetScreenshot) async throws -> Data = { _ in downloads += 1; return Data([1, 2, 3]) }
        let denied: (URL, () -> Bool) async throws -> Void = { _, _ in throw CocoaError(.fileWriteNoPermission) }
        try await engine.reconcile([], download: fetch, validate: { _ in true }, export: denied)
        try await engine.reconcile([new], download: fetch, validate: { _ in true }, export: denied)
        do {
            try await engine.reconcile([new], download: fetch, validate: { _ in true }, export: denied)
            XCTFail("Denied export reported success")
        } catch {}
        XCTAssertEqual(downloads, 1)
        XCTAssertEqual(engine.journal.receipts[new.id]?.destination, .pending)
        XCTAssertEqual(try Data(contentsOf: engine.file(for: new.id)), Data([1, 2, 3]))
        let restarted = try ScreenshotSyncEngine(root: root, photos: true)
        try await restarted.reconcile([], download: fetch, validate: { _ in true }, export: { _, allowed in
            XCTAssertTrue(allowed()); exports += 1
        })
        XCTAssertEqual(downloads, 1)
        XCTAssertEqual(exports, 1)
        XCTAssertEqual(restarted.journal.receipts[new.id]?.destination, .saved)
    }

    func testLateExportSuccessAndFailureCannotOverwriteReplacementJournal() async throws {
        for succeeds in [true, false] {
            let root = try temporary()
            let oldEngine = try ScreenshotSyncEngine(root: root, photos: true)
            let fetch: (HeadsetScreenshot) async throws -> Data = { _ in Data([1, 2, 3]) }
            let noop: (URL, () -> Bool) async throws -> Void = { _, _ in }
            try await oldEngine.reconcile([], download: fetch, validate: { _ in true }, export: noop)
            try await oldEngine.reconcile([new], download: fetch, validate: { _ in true }, export: noop)
            var suspended: CheckedContinuation<Void, Never>?
            let task = Task {
                try await oldEngine.reconcile([new], download: fetch, validate: { _ in true }, export: { _, allowed in
                    await withCheckedContinuation { suspended = $0 }
                    XCTAssertFalse(allowed(), "Stopped export must lose eligibility")
                    if !succeeds { throw CocoaError(.fileWriteNoPermission) }
                })
            }
            while suspended == nil { await Task.yield() }
            oldEngine.stop()
            let replacement = try ScreenshotSyncEngine(root: root, photos: false)
            let other = HeadsetScreenshot(id: "2/10/20261024010001_1.jpg", size: 3, time: 3)
            try await replacement.reconcile([new, other], download: fetch, validate: { _ in true }, export: noop)
            try await replacement.reconcile([new, other], download: fetch, validate: { _ in true }, export: noop)
            suspended!.resume()
            try await task.value
            let reloaded = try ScreenshotSyncEngine(root: root, photos: true)
            XCTAssertEqual(reloaded.journal.receipts.count, 2)
            XCTAssertEqual(reloaded.journal.receipts[other.id]?.destination, .appOnly)
            XCTAssertTrue(reloaded.journal.receipts[other.id]!.downloaded)
            XCTAssertEqual(reloaded.journal.receipts[new.id]?.destination, .appOnly)
        }
    }

    func testDefaultPreferenceAndOfflineAppOnlyLibraryAfterRelaunch() throws {
        let root = try temporary()
        let suite = "frame-screenshot-test-\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let downloads = ScreenshotDownloads(defaults: defaults, storageRoot: root)
        XCTAssertTrue(downloads.saveToPhotos)
        downloads.setPhotos(false)
        let identity = "test-headset-pinned-key"
        let digest = SHA256.hash(data: Data(identity.utf8)).map { String(format: "%02x", $0) }.joined()
        let folder = root.appendingPathComponent("Screenshots/\(digest)")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        var ledger = ScreenshotJournal()
        ledger.observe([], photos: false)
        ledger.observe([new], photos: false)
        ledger.receipts[new.id]?.downloaded = true
        try JSONEncoder().encode(ledger).write(to: folder.appendingPathComponent("receipts.json"))
        let file = folder.appendingPathComponent(new.id)
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data([1, 2, 3]).write(to: file)
        let restarted = ScreenshotDownloads(defaults: defaults, storageRoot: root)
        XCTAssertFalse(restarted.saveToPhotos)
        restarted.load(identity: identity) // No URL, connection or network task.
        XCTAssertEqual(restarted.items.count, 1)
        XCTAssertEqual(restarted.items[0].status, "In Frame Control")
        XCTAssertEqual(try Data(contentsOf: restarted.items[0].file), Data([1, 2, 3]))
    }
}
