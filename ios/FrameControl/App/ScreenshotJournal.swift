import Foundation

struct HeadsetScreenshot: Codable, Equatable {
    let id: String
    let size: Int
    let time: Double

    var valid: Bool {
        id.range(of: #"^[0-9]{1,12}/[0-9]{1,20}/[0-9]{14}_[0-9]{1,4}\.(jpg|png)$"#, options: .regularExpression) != nil
            && size > 0 && size <= 30 * 1024 * 1024 && time.isFinite
    }
}

/// All receipt state lives beside the originals, outside purgeable caches.
/// An interrupted Photos transaction is deliberately not retried automatically:
/// add-only access cannot check whether its asset was committed before a crash.
struct ScreenshotJournal: Codable {
    enum Export: String, Codable { case pending, appOnly, committing, saved }
    struct Receipt: Codable {
        var shot: HeadsetScreenshot
        var downloaded = false
        var destination: Export
    }
    var baseline: Set<String>?
    var receipts: [String: Receipt] = [:]

    mutating func observe(_ shots: [HeadsetScreenshot], photos: Bool) {
        let shots = shots.filter(\.valid)
        guard let baseline else {
            self.baseline = Set(shots.map(\.id))
            return
        }
        for shot in shots where !baseline.contains(shot.id) {
            if var receipt = receipts[shot.id] {
                if !receipt.downloaded { receipt.shot = shot; receipts[shot.id] = receipt }
            } else {
                receipts[shot.id] = Receipt(shot: shot, destination: photos ? .pending : .appOnly)
            }
        }
    }

    mutating func keepPendingInApp() {
        for id in receipts.keys where receipts[id]?.destination == .pending || receipts[id]?.destination == .committing {
            receipts[id]?.destination = .appOnly
        }
    }
}

/// Serialized reconciler shared by foreground polling and future event delivery.
/// Network and Photos operations are injected so failures and late callbacks can
/// be exercised against the actual persistence and state transitions.
@MainActor
final class ScreenshotSyncEngine {
    let root: URL
    private(set) var journal: ScreenshotJournal
    private var previous: [String: HeadsetScreenshot] = [:]
    private var generation = UUID()
    private var running = false
    private(set) var saveToPhotos: Bool

    init(root: URL, photos: Bool) throws {
        self.root = root
        saveToPhotos = photos
        let ledger = root.appendingPathComponent("receipts.json")
        if FileManager.default.fileExists(atPath: ledger.path) {
            // Corrupt state must never silently become a fresh receipt ledger.
            journal = try JSONDecoder().decode(ScreenshotJournal.self, from: Data(contentsOf: ledger))
        } else { journal = ScreenshotJournal() }
        if !photos { journal.keepPendingInApp() }
        try persist()
    }

    func stop() { generation = UUID() }

    func setPhotos(_ enabled: Bool) throws {
        let oldJournal = journal
        let oldSetting = saveToPhotos
        saveToPhotos = enabled
        if !enabled { journal.keepPendingInApp() }
        do { try persist() }
        catch { journal = oldJournal; saveToPhotos = oldSetting; throw error }
    }

    func file(for id: String) -> URL { root.appendingPathComponent(id) }

    private func persist() throws {
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        try JSONEncoder().encode(journal).write(to: root.appendingPathComponent("receipts.json"), options: .atomic)
    }

    func reconcile(_ shots: [HeadsetScreenshot],
                   download: (HeadsetScreenshot) async throws -> Data,
                   validate: (Data) -> Bool,
                   export: (URL, () -> Bool) async throws -> Void) async throws {
        guard !running else { return }
        running = true
        defer { running = false }
        let mine = generation
        func current() -> Bool { mine == generation && !Task.isCancelled }
        guard current() else { return }
        let valid = shots.filter(\.valid)
        let observed = Dictionary(valid.map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
        let stable = previous
        previous = observed
        journal.observe(valid, photos: saveToPhotos)
        try persist() // Queue before touching an original or the photo library.
        var firstError: Error?
        for id in journal.receipts.keys.sorted() {
            guard current(), var receipt = journal.receipts[id], receipt.shot.valid else { continue }
            do {
                let file = file(for: id)
                if !receipt.downloaded {
                    // Steam may still be writing. Require two equal observations.
                    guard observed[id] == receipt.shot, stable[id] == receipt.shot else { continue }
                    let data = try await download(receipt.shot)
                    guard current() else { return }
                    guard data.count == receipt.shot.size, validate(data) else {
                        throw CocoaError(.fileReadCorruptFile)
                    }
                    try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
                    try data.write(to: file, options: .atomic)
                    // Re-read destination: the user can change it during download.
                    receipt = journal.receipts[id]!
                    receipt.downloaded = true
                    journal.receipts[id] = receipt
                    try persist()
                }
                if receipt.destination == .pending, saveToPhotos {
                    journal.receipts[id]?.destination = .committing
                    try persist()
                    do {
                        try await export(file, { current() && self.saveToPhotos && self.journal.receipts[id]?.destination == .committing })
                    } catch {
                        guard current() else { return }
                        // A reported transaction failure is safe to retry. A crash
                        // leaves committing, which needs explicit user recovery.
                        if journal.receipts[id]?.destination == .committing {
                            journal.receipts[id]?.destination = saveToPhotos ? .pending : .appOnly
                        }
                        try persist()
                        throw error
                    }
                    guard current() else { return }
                    journal.receipts[id]?.destination = .saved
                    try persist()
                }
            } catch { if firstError == nil { firstError = error } }
        }
        if let firstError { throw firstError }
    }
}
