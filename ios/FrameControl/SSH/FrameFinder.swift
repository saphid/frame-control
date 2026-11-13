import Combine
import Foundation
import Network

/// Finds the Frame on the local network so nobody has to type its address.
/// A Frame in Developer Mode advertises Valve's devkit service over Bonjour
/// (`_steamos-devkit._tcp`); failing that, `fallback` (the saved address, or
/// frame.local) is checked by opening its SSH port. Both repeat until stopped.
@MainActor
final class FrameFinder: ObservableObject {
    struct Found: Equatable {
        let host: String   // what to connect to
        let name: String   // what to call it
    }

    @Published private(set) var found: Found?
    /// When the search began, to tell "still looking" from "can't find it".
    @Published private(set) var since = Date()

    private var browser: NWBrowser?
    private var probeTask: Task<Void, Never>?
    private var search = FrameSearchState()
    private let probe: @Sendable (String) async -> Bool
    private let discoveryEnabled: Bool

    init(probe: @escaping @Sendable (String) async -> Bool = { await FrameFinder.sshAnswers(host: $0) },
         discoveryEnabled: Bool = true) {
        self.probe = probe
        self.discoveryEnabled = discoveryEnabled
    }

    func start(fallback: String?, manual: Bool = false) {
        stop()
        let mine = search.start(manualAddress: manual ? fallback : nil)
        let host = FrameSearchState.address(manual: search.manualAddress ?? "", discovered: fallback)
        found = nil
        since = Date()
        if search.discovers && discoveryEnabled { browse(generation: mine) }
        probeTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self, self.search.accepts(mine) else { return }
                if self.found == nil {
                    let answers = await self.probe(host)
                    guard !Task.isCancelled, self.search.accepts(mine) else { return }
                    if answers, self.found == nil { self.found = Found(host: host, name: host) }
                }
                try? await Task.sleep(nanoseconds: 3_000_000_000)
            }
        }
    }

    func stop() {
        search.stop()
        browser?.cancel()
        browser = nil
        probeTask?.cancel()
        probeTask = nil
    }

    private func browse(generation: UUID) {
        let browser = NWBrowser(for: .bonjour(type: "_steamos-devkit._tcp", domain: nil), using: .tcp)
        browser.browseResultsChangedHandler = { [weak self] results, _ in
            for result in results {
                guard case let .service(name, _, _, _) = result.endpoint else { continue }
                Self.resolve(result.endpoint) { host in
                    Task { @MainActor in
                        guard let self, self.search.accepts(generation), self.search.discovers, let host else { return }
                        // A found device is used over the fallback probe.
                        self.found = Found(host: host, name: name)
                    }
                }
            }
        }
        browser.start(queue: .main)
        self.browser = browser
    }

    /// The device's IP address: connect to the service and read where it went.
    nonisolated private static func resolve(_ endpoint: NWEndpoint, done: @escaping @Sendable (String?) -> Void) {
        let connection = NWConnection(to: endpoint, using: .tcp)
        let once = Once()
        connection.stateUpdateHandler = { state in
            switch state {
            case .ready:
                var host: String?
                if case let .hostPort(h, _)? = connection.currentPath?.remoteEndpoint {
                    host = "\(h)".components(separatedBy: "%").first  // drop an IPv6 interface suffix
                }
                connection.cancel()
                if once.claim() { done(host) }
            case .failed, .cancelled:
                if once.claim() { done(nil) }
            default:
                break
            }
        }
        connection.start(queue: .global())
        DispatchQueue.global().asyncAfter(deadline: .now() + 5) {
            connection.cancel()
            if once.claim() { done(nil) }
        }
    }

    /// Whether something answers on the SSH port of "host" or "host:port" within a few seconds.
    nonisolated static func sshAnswers(host address: String) async -> Bool {
        guard let target = FrameSettings.parse(host: address, user: "steamos") else { return false }
        return await sshAnswers(host: target.host, port: UInt16(target.port))
    }

    nonisolated static func sshAnswers(host: String, port: UInt16) async -> Bool {
        await withCheckedContinuation { (c: CheckedContinuation<Bool, Never>) in
            let connection = NWConnection(host: NWEndpoint.Host(host), port: NWEndpoint.Port(rawValue: port) ?? 22, using: .tcp)
            let once = Once()
            connection.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    connection.cancel()
                    if once.claim() { c.resume(returning: true) }
                case .failed, .waiting:
                    connection.cancel()
                    if once.claim() { c.resume(returning: false) }
                default:
                    break
                }
            }
            connection.start(queue: .global())
            DispatchQueue.global().asyncAfter(deadline: .now() + 3) {
                connection.cancel()
                if once.claim() { c.resume(returning: false) }
            }
        }
    }
}
