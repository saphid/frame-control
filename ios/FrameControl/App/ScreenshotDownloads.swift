import CryptoKit
import ImageIO
import Photos
import SwiftUI
import UIKit

@MainActor
final class ScreenshotDownloads: ObservableObject {
    struct Item: Identifiable {
        let id: String
        let file: URL
        let date: Date
        let status: String
    }
    @Published private(set) var items: [Item] = []
    @Published private(set) var message = "New screenshots download while Frame Control is open."
    @Published private(set) var saveToPhotos: Bool
    private let defaults: UserDefaults
    private let storageRoot: URL?
    private static let preference = "frame.screenshots.saveToPhotos"
    private var engine: ScreenshotSyncEngine?
    private var task: Task<Void, Never>?
    private var session: URL?
    private var identity: String?

    init(defaults: UserDefaults = .standard, storageRoot: URL? = nil) {
        self.defaults = defaults
        self.storageRoot = storageRoot
        saveToPhotos = defaults.object(forKey: Self.preference) == nil || defaults.bool(forKey: Self.preference)
    }

    func setPhotos(_ enabled: Bool) {
        do {
            try engine?.setPhotos(enabled)
            defaults.set(enabled, forKey: Self.preference)
            saveToPhotos = enabled
            refresh()
            if enabled { Task { _ = await Self.photoPermission() } }
        } catch { message = "Couldn't save the screenshot setting: \(error.localizedDescription)" }
    }

    /// Local files and settings remain available without a live SSH session.
    func load(identity: String) {
        guard self.identity != identity || engine == nil else { return }
        do {
            let digest = SHA256.hash(data: Data(identity.utf8)).map { String(format: "%02x", $0) }.joined()
            let base = try storageRoot ?? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                                                  appropriateFor: nil, create: true)
            self.engine = try ScreenshotSyncEngine(root: base.appendingPathComponent("Screenshots/\(digest)", isDirectory: true),
                                                   photos: saveToPhotos)
            self.identity = identity
            refresh()
        } catch {
            engine = nil
            self.identity = nil
            items = []
            message = "Screenshot downloads need attention: \(error.localizedDescription)"
        }
    }

    func start(url: URL, identity: String) {
        if session == url, task != nil { return }
        stop()
        load(identity: identity)
        if let engine {
            session = url
            task = Task { [weak self] in
                while !Task.isCancelled {
                    guard let self, self.session == url else { return }
                    if UIApplication.shared.applicationState == .active {
                        await self.poll(url: url, engine: engine)
                    }
                    do { try await Task.sleep(nanoseconds: 4_000_000_000) }
                    catch { return }
                }
            }
        }
    }

    func stop() {
        task?.cancel()
        task = nil
        engine?.stop()
        session = nil
    }

    private func poll(url: URL, engine: ScreenshotSyncEngine) async {
        do {
            let data = try await Self.get("/api/shots", from: url)
            struct Listing: Decodable { let shots: [HeadsetScreenshot] }
            let shots = try JSONDecoder().decode(Listing.self, from: data).shots
            guard !Task.isCancelled, session == url else { return }
            try await engine.reconcile(shots, download: { shot in
                try await Self.get("/api/shots/image", id: shot.id, from: url)
            }, validate: { data in
                guard let image = CGImageSourceCreateWithData(data as CFData, nil),
                      CGImageSourceGetStatus(image) == .statusComplete else { return false }
                return CGImageSourceCreateImageAtIndex(image, 0, nil) != nil
            }, export: { file, allowed in
                guard !Task.isCancelled, UIApplication.shared.applicationState == .active else { throw CancellationError() }
                guard await Self.photoPermission() else {
                    throw NSError(domain: "FrameScreenshots", code: 1,
                                  userInfo: [NSLocalizedDescriptionKey: "Originals are kept in Frame Control. Allow Photos access in iOS Settings to save them to Photos."])
                }
                // Cancellation or a toggle change while the permission prompt was
                // visible must not start a Photos transaction.
                guard !Task.isCancelled, allowed() else { throw CancellationError() }
                try await PHPhotoLibrary.shared().performChanges {
                    PHAssetCreationRequest.forAsset().addResource(with: .photo, fileURL: file, options: nil)
                }
            })
            guard !Task.isCancelled, session == url else { return }
            message = "New screenshots download while Frame Control is open."
        } catch {
            guard !Task.isCancelled, session == url else { return }
            message = "\(error.localizedDescription) Downloads retry while the app is open."
        }
        refresh()
    }

    private static func get(_ path: String, id: String? = nil, from page: URL) async throws -> Data {
        let original = URLComponents(url: page, resolvingAgainstBaseURL: false)
        let key = original?.queryItems?.first(where: { $0.name == "key" })?.value
        var parts = original!
        parts.path = path
        parts.queryItems = id.map { [URLQueryItem(name: "id", value: $0)] }
        parts.fragment = nil
        var request = URLRequest(url: parts.url!, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30)
        request.setValue(key, forHTTPHeaderField: "X-Frame-UI")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw URLError(.badServerResponse) }
        return data
    }

    private static func photoPermission() async -> Bool {
        var status = PHPhotoLibrary.authorizationStatus(for: .addOnly)
        if status == .notDetermined, UIApplication.shared.applicationState == .active {
            status = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        }
        return status == .authorized || status == .limited
    }

    private func refresh() {
        guard let engine else { return }
        items = engine.journal.receipts.values.filter(\.downloaded).map { receipt in
            let status: String
            switch receipt.destination {
            case .saved: status = "Saved to Photos"
            case .appOnly: status = "In Frame Control"
            case .pending: status = "In Frame Control · waiting for Photos"
            case .committing: status = "In Frame Control · Photos save interrupted; check Photos before saving again"
            }
            return Item(id: receipt.shot.id, file: engine.file(for: receipt.shot.id),
                        date: Date(timeIntervalSince1970: receipt.shot.time), status: status)
        }.sorted { $0.date > $1.date }
    }
}
