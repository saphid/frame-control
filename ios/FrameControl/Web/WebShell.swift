import SwiftUI
import UIKit
import WebKit
import UserNotifications

/// The Frame Control page, served by the server on the headset, in a web view.
/// window.frameApp (the same bridge the desktop app's preload.js provides) lets
/// the page use the phone: clipboard, saving images, other apps, install links.
struct WebShell: UIViewRepresentable {
    let url: URL
    @ObservedObject var model: AppModel

    func makeCoordinator() -> Coordinator { Coordinator(model: model) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let content = WKUserContentController()
        content.addUserScript(WKUserScript(source: Self.bridge, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        content.addScriptMessageHandler(context.coordinator, contentWorld: .page, name: "frameApp")
        config.userContentController = content
        config.allowsInlineMediaPlayback = true
        let web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = context.coordinator
        web.uiDelegate = context.coordinator
        web.isOpaque = false
        web.backgroundColor = UIColor(red: 0.055, green: 0.078, blue: 0.106, alpha: 1)
        web.scrollView.backgroundColor = web.backgroundColor
        web.scrollView.contentInsetAdjustmentBehavior = .never  // the page pads for the safe area itself
        web.allowsBackForwardNavigationGestures = false
        #if DEBUG
        web.isInspectable = true
        #endif
        context.coordinator.web = web
        context.coordinator.load(url, reloadID: model.webReloadID)
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {
        if context.coordinator.loaded != url || context.coordinator.reloadID != model.webReloadID {
            context.coordinator.load(url, reloadID: model.webReloadID)
        }
        context.coordinator.deliverInstallLinks()
    }

    static let bridge = """
    (() => {
      const call = (name, arg) => window.webkit.messageHandlers.frameApp.postMessage({ name, arg: arg ?? null });
      let installCb = null;
      window.__frameDocumentID = crypto.randomUUID();
      window.frameApp = {
        platform: "ios",
        preferences: {
          read: () => call("preferencesRead"),
          write: (key, value) => call("preferencesWrite", { key, value }),
        },
        notify: (message, request) => call("notify", { message, request }),
        readClipboard: () => call("readClipboard"),
        writeClipboard: (text) => call("writeClipboard", text),
        setUpConnection: () => call("setUpConnection"),
        open: (what) => call("open", what),
        saveImages: (images) => call("saveImages", images),
        screenshotDownloads: () => call("screenshotDownloads"),
        onInstallLink: (cb) => { installCb = cb; return call("installLinkReady", window.__frameDocumentID); },
      };
      window.__frameInstallLink = (req) => { if (!installCb) return false; installCb(req); return true; };
    })();
    """

    final class Coordinator: NSObject, WKScriptMessageHandlerWithReply, WKNavigationDelegate, WKUIDelegate, UNUserNotificationCenterDelegate {
        let model: AppModel
        weak var web: WKWebView?
        var loaded: URL?
        private(set) var document = WebDocumentState()
        private(set) var reloadID = 0
        private var activeNavigation: WKNavigation?
        private let preferences = FramePreferences()

        @MainActor
        func load(_ url: URL, reloadID: Int) {
            loaded = url
            self.reloadID = reloadID
            document.resetSession()
            activeNavigation = web?.load(URLRequest(url: url))
        }

        init(model: AppModel) {
            self.model = model
            super.init()
            UNUserNotificationCenter.current().delegate = self
        }

        func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                    withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
            completionHandler([.banner, .sound, .list])
        }

        static func notificationContent(_ message: String) -> UNMutableNotificationContent? {
            guard !message.isEmpty, message.count <= 500 else { return nil }
            let content = UNMutableNotificationContent()
            content.title = "Frame Control"
            content.body = message
            content.sound = .default
            return content
        }

        // MARK: bridge

        @MainActor
        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage,
                                   replyHandler: @escaping (Any?, String?) -> Void) {
            guard let body = message.body as? [String: Any], let name = body["name"] as? String else {
                return replyHandler(nil, "bad message")
            }
            let arg = body["arg"]
            switch name {
            case "notify":
                guard message.frameInfo.isMainFrame,
                      message.frameInfo.securityOrigin.host == "127.0.0.1",
                      let args = arg as? [String: Any], let text = args["message"] as? String,
                      let content = Self.notificationContent(text) else {
                    return replyHandler(nil, "Invalid notification")
                }
                let center = UNUserNotificationCenter.current()
                let send: (Bool, Error?) -> Void = { allowed, error in
                    guard allowed else {
                        return replyHandler(nil, error?.localizedDescription ?? "Notifications are off. Enable them in iOS Settings.")
                    }
                    let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
                    center.add(request) { error in replyHandler(error == nil, error?.localizedDescription) }
                }
                if args["request"] as? Bool == true {
                    center.requestAuthorization(options: [.alert, .sound], completionHandler: send)
                } else {
                    center.getNotificationSettings { settings in
                        send(settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional, nil)
                    }
                }
            case "preferencesRead":
                replyHandler(preferences.read(), nil)
            case "preferencesWrite":
                guard let args = arg as? [String: Any], let key = args["key"] as? String,
                      let value = args["value"] as? String, preferences.write(key: key, value: value) else {
                    return replyHandler(nil, "Invalid preference")
                }
                replyHandler(true, nil)
            case "readClipboard":
                replyHandler(UIPasteboard.general.string ?? "", nil)
            case "writeClipboard":
                guard let text = arg as? String else { return replyHandler(nil, "Expected text") }
                UIPasteboard.general.string = text
                replyHandler(true, nil)
            case "setUpConnection":
                model.showSetup()
                replyHandler(nil, nil)
            case "open":
                let result = open(arg as? String ?? "")
                replyHandler(result.message.map { ["message": $0] }, result.error)
            case "saveImages":
                let images = (arg as? [[String: Any]] ?? []).compactMap { item -> UIImage? in
                    guard let b64 = item["data"] as? String, let data = Data(base64Encoded: b64) else { return nil }
                    return UIImage(data: data)
                }
                guard !images.isEmpty else { return replyHandler(nil, "No images to save") }
                share(images)
                replyHandler(["message": "Choose Save Image to keep \(images.count == 1 ? "it" : "them") in Photos"], nil)
            case "screenshotDownloads":
                model.showScreenshotDownloads = true
                replyHandler(true, nil)
            case "installLinkReady":
                guard let id = arg as? String, let web,
                      let data = try? JSONSerialization.data(withJSONObject: id, options: .fragmentsAllowed),
                      let json = String(data: data, encoding: .utf8) else {
                    return replyHandler(nil, "Invalid document")
                }
                let generation = document.generation
                web.evaluateJavaScript("window.__frameDocumentID === \(json)") { [weak self] result, error in
                    guard let self else { return replyHandler(nil, "Page closed") }
                    if error == nil, result as? Bool == true {
                        self.document.ready(id, generation: generation)
                        self.deliverInstallLinks()
                    }
                    replyHandler(nil, nil)
                }
            default:
                replyHandler(nil, "unknown request \(name)")
            }
        }

        @MainActor
        func deliverInstallLinks() {
            guard let web, let loaded, model.phase == .ready(loaded), reloadID == model.webReloadID,
                  let link = model.pendingInstallLinks.first, let delivery = document.beginDelivery() else { return }
            let req = ["kind": link.kind.rawValue, "target": link.target]
            guard let json = try? JSONSerialization.data(withJSONObject: req),
                  let text = String(data: json, encoding: .utf8),
                  let idData = try? JSONSerialization.data(withJSONObject: delivery.documentID, options: .fragmentsAllowed),
                  let id = String(data: idData, encoding: .utf8) else {
                _ = document.finishDelivery(delivery, acknowledged: false)
                return
            }
            // Keep the head queued until the live document confirms its callback ran.
            web.evaluateJavaScript("window.__frameDocumentID === \(id) && window.__frameInstallLink(\(text)) === true") { [weak self] result, error in
                guard let self, let loaded = self.loaded, self.model.phase == .ready(loaded),
                      self.reloadID == self.model.webReloadID else { return }
                guard self.document.finishDelivery(delivery, acknowledged: error == nil && result as? Bool == true) else { return }
                if self.model.pendingInstallLinks.first == link { self.model.pendingInstallLinks.removeFirst() }
                self.deliverInstallLinks()
            }
        }

        /// SSH, SFTP, Steam Link and remote desktop open in the apps that handle them.
        @MainActor
        private func open(_ what: String) -> (message: String?, error: String?) {
            guard let s = model.settings else { return (nil, "Not paired with a Frame") }
            let host = s.host.contains(":") ? "[\(s.host)]" : s.host
            let target: (url: String, app: String, store: String)
            switch what {
            case "terminal": target = ("ssh://\(s.user)@\(host):\(s.port)", "an SSH app such as Blink Shell or Termius", "https://apps.apple.com/search?term=ssh")
            case "sftp": target = ("sftp://\(s.user)@\(host):\(s.port)", "an SFTP app such as Termius or Secure ShellFish", "https://apps.apple.com/search?term=sftp")
            case "steamlink": target = ("steamlink://", "Steam Link", "https://apps.apple.com/app/steam-link/id1246969117")
            case "rdp": target = ("rdp://full%20address=s:\(s.host):3389", "Windows App (Microsoft Remote Desktop)", "https://apps.apple.com/app/windows-app/id714464092")
            default: return (nil, "Can't open \(what) on this \(model.deviceName)")
            }
            guard let url = URL(string: target.url) else { return (nil, "Bad address") }
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url)
                return ("Opening \(target.app)", nil)
            }
            if let store = URL(string: target.store) { UIApplication.shared.open(store) }
            return (nil, "Install \(target.app) to open this; opening the App Store")
        }

        @MainActor
        private func share(_ images: [UIImage]) {
            guard let web, let root = web.window?.rootViewController else { return }
            let sheet = UIActivityViewController(activityItems: images, applicationActivities: nil)
            sheet.popoverPresentationController?.sourceView = web
            sheet.popoverPresentationController?.sourceRect = CGRect(x: web.bounds.midX, y: web.bounds.midY, width: 1, height: 1)
            (root.presentedViewController ?? root).present(sheet, animated: true)
        }

        // A new document cannot receive links using the previous page's callback.
        @MainActor
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            activeNavigation = navigation
            document.beginDocument()
        }

        @MainActor
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            recover(webView, message: "The app page stopped responding. Try loading it again, or change headset.")
        }

        @MainActor
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            navigationFailed(webView, navigation: navigation, error: error)
        }

        @MainActor
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            navigationFailed(webView, navigation: navigation, error: error)
        }

        @MainActor
        private func navigationFailed(_ webView: WKWebView, navigation: WKNavigation?, error: Error) {
            guard navigation === activeNavigation, (error as NSError).code != NSURLErrorCancelled else { return }
            recover(webView, message: "Couldn't load the app page. \(error.localizedDescription)")
        }

        @MainActor
        private func recover(_ webView: WKWebView, message: String) {
            guard let loaded, model.phase == .ready(loaded), reloadID == model.webReloadID,
                  model.webRecoveryMessage == nil else { return }
            activeNavigation = nil
            if document.shouldReloadAfterFailure() {
                // Reload the original authenticated URL, including its session key.
                activeNavigation = webView.load(URLRequest(url: loaded))
            } else {
                model.webContentFailed(at: loaded, message: message)
            }
        }

        /// Simulator test hook: FRAME_TEST_JS runs in the page once it has loaded.
        @MainActor
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            #if DEBUG
            guard let js = ProcessInfo.processInfo.environment["FRAME_TEST_JS"] else { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 4) { webView.evaluateJavaScript(js) }
            #endif
        }

        // MARK: navigation: the app's page stays here; other sites open in Safari

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = action.request.url else { return decisionHandler(.cancel) }
            if url.host == "127.0.0.1" || url.scheme == "about" || url.scheme == "blob" || url.scheme == "data" {
                return decisionHandler(.allow)
            }
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
        }

        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = action.request.url { UIApplication.shared.open(url) }  // target="_blank" links
            return nil
        }

        // MARK: alert() and confirm(), which the page uses before removing things

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            present(message, actions: [UIAlertAction(title: "OK", style: .default) { _ in completionHandler() }], fallback: completionHandler)
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            present(message, actions: [
                UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) },
                UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) },
            ], fallback: { completionHandler(false) })
        }

        private func present(_ message: String, actions: [UIAlertAction], fallback: @escaping () -> Void) {
            guard let root = web?.window?.rootViewController else { return fallback() }
            let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            actions.forEach(alert.addAction)
            (root.presentedViewController ?? root).present(alert, animated: true)
        }
    }
}
