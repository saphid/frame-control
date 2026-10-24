import Foundation

/// The persisted SSH target and its editable, lossless address form.
struct FrameSettings: Codable, Equatable {
    var host: String
    var port: Int = 22
    var user: String = "steamos"

    var address: String {
        let name = host.contains(":") ? "[\(host)]" : host
        return port == 22 ? name : "\(name):\(port)"
    }

    static func parse(host: String, user: String) -> FrameSettings? {
        var host = host.trimmingCharacters(in: .whitespacesAndNewlines)
        let user = user.trimmingCharacters(in: .whitespacesAndNewlines)
        var port = 22
        if host.hasPrefix("[") {
            guard let close = host.firstIndex(of: "]") else { return nil }
            let rest = host[host.index(after: close)...]
            if !rest.isEmpty {
                guard rest.hasPrefix(":"), let value = Int(rest.dropFirst()) else { return nil }
                port = value
            }
            host = String(host[host.index(after: host.startIndex)..<close])
        } else if host.filter({ $0 == ":" }).count == 1, let colon = host.lastIndex(of: ":") {
            guard let value = Int(host[host.index(after: colon)...]) else { return nil }
            port = value
            host = String(host[..<colon])
        }
        guard !host.isEmpty, !user.isEmpty, (1...65535).contains(port) else { return nil }
        return FrameSettings(host: host, port: port, user: user)
    }
}

/// Each search owns its callbacks. Cancelling invalidates even probes that cannot
/// be cancelled while Network.framework finishes opening a connection.
struct FrameSearchState {
    private(set) var generation = UUID()
    private(set) var manualAddress: String?

    mutating func start(manualAddress: String?) -> UUID {
        generation = UUID()
        let typed = manualAddress?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        self.manualAddress = typed.isEmpty ? nil : typed
        return generation
    }

    mutating func stop() { generation = UUID() }
    func accepts(_ generation: UUID) -> Bool { self.generation == generation }
    var discovers: Bool { manualAddress == nil }

    static func address(manual: String, discovered: String?) -> String {
        let typed = manual.trimmingCharacters(in: .whitespacesAndNewlines)
        return typed.isEmpty ? (discovered ?? "frame.local") : typed
    }
}

/// One automatic recovery per session; only a deliberate retry or a new session
/// replenishes it. A successful load alone must not create a process-crash loop.
struct WebDocumentState {
    struct Delivery: Equatable {
        let generation: UUID
        let documentID: String
    }

    private(set) var generation = UUID()
    private(set) var documentID: String?
    private(set) var delivering = false
    private var reloads = 0

    mutating func beginDocument() {
        generation = UUID()
        documentID = nil
        delivering = false
    }

    mutating func resetSession() {
        reloads = 0
        beginDocument()
    }

    mutating func shouldReloadAfterFailure() -> Bool {
        beginDocument()
        guard reloads < 1 else { return false }
        reloads += 1
        return true
    }

    mutating func ready(_ id: String, generation: UUID) {
        guard self.generation == generation else { return }
        documentID = id
    }

    mutating func beginDelivery() -> Delivery? {
        guard !delivering, let documentID else { return nil }
        delivering = true
        return Delivery(generation: generation, documentID: documentID)
    }

    /// Only acknowledgement from the same live document may consume a link.
    mutating func finishDelivery(_ delivery: Delivery, acknowledged: Bool) -> Bool {
        guard delivery.generation == generation, delivering, delivery.documentID == documentID else { return false }
        delivering = false
        if !acknowledged { documentID = nil }
        return acknowledged
    }
}

/// Small app-scoped preferences survive the tunnel's intentionally ephemeral port.
struct FramePreferences {
    private let defaults: UserDefaults
    private static let keys = ["mvSeparate", "padUsed"]
    private static let prefix = "frame.control.preference."

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    func read() -> [String: String] {
        var result: [String: String] = [:]
        for key in Self.keys {
            if let value = defaults.object(forKey: Self.prefix + key) as? String, ["0", "1"].contains(value) {
                result[key] = value
            }
        }
        return result
    }

    @discardableResult
    func write(key: String, value: String) -> Bool {
        guard Self.keys.contains(key), ["0", "1"].contains(value) else { return false }
        defaults.set(value, forKey: Self.prefix + key)
        return true
    }
}

/// True for the first caller only.
final class Once: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false
    func claim() -> Bool { lock.withLock { defer { done = true }; return !done } }
}

