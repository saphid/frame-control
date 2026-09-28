// "Separate" mode: a streamed window gets a virtual display of its own. The
// window is moved onto it and sized to fill it, and the whole display is
// captured, so its menus, sheets, popovers and tooltips come along, nothing
// can cover it, and clicks land on it without raising anything. On stop the
// window goes back where it was. See docs/mac-window-separation.md.
import AppKit
import ApplicationServices
import CoreMedia
import Foundation

@_silgen_name("_AXUIElementGetWindow")
private func axWindowID(_ element: AXUIElement, _ id: UnsafeMutablePointer<CGWindowID>) -> AXError

/// One of our virtual displays, HiDPI (2 pixels per point). Main thread only.
final class VirtualDisplay {
    static let vendor: UInt32 = 0xF0C0
    /// How often macOS composites our displays (FRAME_MAC_VIEW_VD_HZ to experiment).
    static let refreshRate = Double(ProcessInfo.processInfo.environment["FRAME_MAC_VIEW_VD_HZ"] ?? "") ?? 60
    private var display: CGVirtualDisplay?
    let id: CGDirectDisplayID
    /// The size asked for, in points (the display starts in another mode and
    /// switches a moment later).
    let size: (width: Int, height: Int)
    /// Removal is deferred while the Mac's screen sleeps, and an identity
    /// can't be reused until it's gone, so each display gets a fresh serial.
    private static var serial = (UInt32(truncatingIfNeeded: ProcessInfo.processInfo.processIdentifier) & 0xFFFF) << 12

    init?(name: String, width: Int, height: Int) {
        size = (width, height)
        var made: CGVirtualDisplay?
        for _ in 0..<8 where made == nil {
            VirtualDisplay.serial &+= 1
            let d = CGVirtualDisplayDescriptor()
            d.queue = DispatchQueue.main
            d.name = name
            d.maxPixelsWide = UInt32(2 * width)
            d.maxPixelsHigh = UInt32(2 * height)
            d.sizeInMillimeters = CGSize(width: Double(width) * 0.2646, height: Double(height) * 0.2646)
            d.vendorID = VirtualDisplay.vendor
            d.productID = 0x5E9A
            d.serialNum = VirtualDisplay.serial
            d.terminationHandler = { _, _ in }
            guard let vd = CGVirtualDisplay(descriptor: d) else { continue }
            let s = CGVirtualDisplaySettings()
            s.hiDPI = 1
            let hz = VirtualDisplay.refreshRate
            // Both modes: macOS then starts the display at 2x by itself, as long
            // as it's at least 800x600 points; smaller, its 2x mode is never
            // usable (probed 2026-09-28 on macOS 26.5.2).
            s.modes = [CGVirtualDisplayMode(width: UInt32(2 * width), height: UInt32(2 * height), refreshRate: hz)!,
                       CGVirtualDisplayMode(width: UInt32(width), height: UInt32(height), refreshRate: hz)!]
            if vd.apply(s), vd.displayID != 0 { made = vd }
        }
        guard let made else { return nil }
        display = made
        id = made.displayID
    }

    /// Where it should sit: left of everything else, touching the leftmost
    /// display. Otherwise macOS slots each new display in next to the main
    /// one and pushes earlier ones along, and a window placed a moment before
    /// ends up on the wrong display (seen 2026-09-28 with two windows).
    private var wantOrigin: CGPoint?
    private var modesSeen = -1
    private var modeAskedAt = Date.distantPast

    /// Applies the HiDPI mode and the position once macOS has registered the
    /// display (right after creation both fail: no modes yet, and error 1001
    /// for the origin). True once both are in place. Call until it is.
    func settle() -> Bool {
        if wantOrigin == nil {
            var ids = [CGDirectDisplayID](repeating: 0, count: 32)
            var n: UInt32 = 0
            CGGetOnlineDisplayList(32, &ids, &n)
            let others = ids.prefix(Int(n)).filter { $0 != id }.map { CGDisplayBounds($0) }
            let left = others.map(\.minX).min() ?? 0
            let top = others.first(where: { $0.minX == left })?.minY ?? 0
            wantOrigin = CGPoint(x: left - CGFloat(size.width), y: top)
        }
        let placed = bounds.origin == wantOrigin
        if isReady && placed { return true }
        let (width, height) = size
        // The HiDPI mode: `width` points drawn with twice the pixels.
        let modes = (CGDisplayCopyAllDisplayModes(id, [kCGDisplayShowDuplicateLowResolutionModes: true] as CFDictionary)
            as? [CGDisplayMode]) ?? []
        let hidpi = modes.first(where: {
            $0.width == width && $0.height == height && $0.pixelWidth == 2 * width && $0.refreshRate == VirtualDisplay.refreshRate
        }) ?? modes.first(where: { $0.width == width && $0.height == height && $0.pixelWidth == 2 * width })
        // Separately: a refused position would take the mode change down with it.
        // A mode switch takes a moment; asking again restarts it.
        if !isReady, let hidpi, Date().timeIntervalSince(modeAskedAt) > 1.5 {
            modeAskedAt = Date()
            let r = CGDisplaySetDisplayMode(id, hidpi, nil)  // only if macOS didn't start it at 2x
            agentLog("display \(id): set \(hidpi.width)x\(hidpi.height)@\(hidpi.pixelWidth) -> \(r.rawValue), "
                     + "usable \(hidpi.isUsableForDesktopGUI()), now \(CGDisplayCopyDisplayMode(id).map { "\($0.width)x\($0.height)@\($0.pixelWidth)" } ?? "?")")
        }
        if !placed, let o = wantOrigin {
            var cfg: CGDisplayConfigRef?
            CGBeginDisplayConfiguration(&cfg)
            CGConfigureDisplayOrigin(cfg, id, Int32(o.x), Int32(o.y))
            CGCompleteDisplayConfiguration(cfg, .forSession)
        }
        if modesSeen != modes.count {
            modesSeen = modes.count
            let cur = CGDisplayCopyDisplayMode(id).map { "\($0.width)x\($0.height)@\($0.pixelWidth)" } ?? "?"
            agentLog("display \(id): \(modes.count) modes [\(modes.map { "\($0.width)x\($0.height)@\($0.pixelWidth)\($0.isUsableForDesktopGUI() ? "u" : "")" }.joined(separator: " "))], "
                     + "hidpi \(hidpi.map { "\($0.width)x\($0.height)@\($0.pixelWidth)" } ?? "none"), current \(cur), now \(bounds)")
        }
        return false
    }

    var bounds: CGRect { CGDisplayBounds(id) }

    /// Moves several of our displays at once (one configuration, so they
    /// never land on each other half way), retrying for a second until
    /// macOS has them all where asked.
    static func arrange(_ origins: [(VirtualDisplay, CGPoint)], attempt: Int = 0) {
        let pending = origins.filter { $0.0.bounds.origin != $0.1 }
        guard !pending.isEmpty else { return }
        for (vd, p) in origins { vd.wantOrigin = p }
        var cfg: CGDisplayConfigRef?
        CGBeginDisplayConfiguration(&cfg)
        for (vd, p) in origins { CGConfigureDisplayOrigin(cfg, vd.id, Int32(p.x), Int32(p.y)) }
        CGCompleteDisplayConfiguration(cfg, .forSession)
        guard attempt < 10 else {
            agentLog("arrange: \(pending.count) displays not where asked")
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { arrange(origins, attempt: attempt + 1) }
    }

    var isHiDPI: Bool { CGDisplayCopyDisplayMode(id).map { $0.pixelWidth > $0.width } ?? false }

    /// In the mode asked for: HiDPI at the requested size.
    var isReady: Bool {
        guard let m = CGDisplayCopyDisplayMode(id) else { return false }
        return m.width == size.width && m.height == size.height && m.pixelWidth == 2 * size.width
    }

    var screen: NSScreen? {
        NSScreen.screens.first {
            ($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value == id
        }
    }

    /// Where a window may go, in global (top-left origin) points: the display
    /// minus its menu bar and anything else macOS reserves there.
    var usableRect: CGRect {
        let b = bounds
        guard let s = screen else { return b }
        let top = s.frame.maxY - s.visibleFrame.maxY, bottom = s.visibleFrame.minY - s.frame.minY
        let left = s.visibleFrame.minX - s.frame.minX, right = s.frame.maxX - s.visibleFrame.maxX
        return CGRect(x: b.minX + left, y: b.minY + top, width: b.width - left - right, height: b.height - top - bottom)
    }

    func release() { display = nil }

    static func isOurs(_ id: CGDirectDisplayID) -> Bool { CGDisplayVendorNumber(id) == vendor }
}

/// A window through the Accessibility API.
struct AXWindow {
    let element: AXUIElement

    init?(windowID: CGWindowID, pid: pid_t) {
        let app = AXUIElementCreateApplication(pid)
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &value) == .success,
              let windows = value as? [AXUIElement] else { return nil }
        guard let match = windows.first(where: { w in
            var id: CGWindowID = 0
            return axWindowID(w, &id) == .success && id == windowID
        }) else { return nil }
        element = match
    }

    var frame: CGRect? {
        var p: CFTypeRef?, s: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, kAXPositionAttribute as CFString, &p) == .success,
              AXUIElementCopyAttributeValue(element, kAXSizeAttribute as CFString, &s) == .success else { return nil }
        var point = CGPoint.zero, size = CGSize.zero
        AXValueGetValue(p as! AXValue, .cgPoint, &point)
        AXValueGetValue(s as! AXValue, .cgSize, &size)
        return CGRect(origin: point, size: size)
    }

    var isFullScreen: Bool {
        var v: CFTypeRef?
        return AXUIElementCopyAttributeValue(element, "AXFullScreen" as CFString, &v) == .success && (v as? Bool) == true
    }

    /// Moving to another display: position first (so the size fits there),
    /// then size, then position again in case the size change moved it.
    func setFrame(_ r: CGRect) {
        var origin = r.origin, size = r.size
        let pos = AXValueCreate(.cgPoint, &origin)!, sz = AXValueCreate(.cgSize, &size)!
        AXUIElementSetAttributeValue(element, kAXPositionAttribute as CFString, pos)
        AXUIElementSetAttributeValue(element, kAXSizeAttribute as CFString, sz)
        AXUIElementSetAttributeValue(element, kAXPositionAttribute as CFString, pos)
    }
}

/// A window on a display of its own, captured as that display.
final class SeparateSource: CaptureSource {
    let windowID: CGWindowID
    var onFrame: ((CVPixelBuffer, CMTime, Int64) -> Void)?
    var onEnded: ((String) -> Void)?
    var onChange: (() -> Void)?
    private(set) var title = ""
    private(set) var app = ""
    private(set) var pid: pid_t?
    private(set) var gone = false
    private var display: VirtualDisplay?
    private var inner: SCKSource?
    private var window: AXWindow?
    private var original: CGRect?
    private var crop: CGRect?  // display points, when only part of the display is captured
    private var poll: DispatchSourceTimer?
    private var stopped = false
    private let queue = DispatchQueue(label: "frame-mac-view.separate")

    init(windowID: CGWindowID) { self.windowID = windowID }

    var frameRect: CGRect { inner?.frameRect ?? .zero }
    var displayID: CGDirectDisplayID? { display?.id }
    var virtualDisplay: VirtualDisplay? { display }

    func start(maxLong: Int, fps: Int, completion: @escaping (String?) -> Void) {
        guard AXIsProcessTrusted() else {
            return completion("Separate windows need the Accessibility permission (to move the window)")
        }
        guard let info = WindowInfo.find(windowID) else {
            gone = true
            return completion("that window has closed")
        }
        title = info.title
        app = info.app
        pid = info.pid
        DispatchQueue.main.async { [self] in
            guard !stopped else { return }
            guard let w = AXWindow(windowID: windowID, pid: info.pid), let frame = w.frame else {
                return completion("couldn't reach that window through Accessibility")
            }
            if w.isFullScreen { return completion("take the window out of full screen first") }
            // A display the window's size, plus room for the menu bar, in
            // points; within what a panel can show sharply.
            // At least 800x600 points: smaller displays don't get a usable 2x
            // (sharp) mode on macOS 26. A smaller window is resized to fill it,
            // or cropped if it keeps its own size.
            let width = min(max(Int(frame.width.rounded()), 800), 2560) / 2 * 2
            let height = min(max(Int(frame.height.rounded()) + 40, 600), 1600) / 2 * 2
            guard let vd = VirtualDisplay(name: app.isEmpty ? "Frame Control" : "\(app) (Frame)", width: width, height: height) else {
                return completion("macOS wouldn't create a display for this window")
            }
            display = vd
            window = w
            original = frame
            agentLog("separate \(windowID) (\(app)): display \(vd.id) \(width)x\(height) pt for window \(frame)")
            // The new screen shows up in NSScreen a moment later; its menu bar
            // decides where the window can go.
            placeWindow(attempt: 0, maxLong: maxLong, fps: fps, completion: completion)
        }
    }

    private func placeWindow(attempt: Int, maxLong: Int, fps: Int, completion: @escaping (String?) -> Void) {
        guard !stopped, let vd = display, let w = window else { return }
        // Wait for the screen to appear, and for its HiDPI mode, so the
        // first frames are captured sharp.
        if !vd.settle() || vd.screen == nil, attempt < 30 {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                self.placeWindow(attempt: attempt + 1, maxLong: maxLong, fps: fps, completion: completion)
            }
            return
        }
        let target = vd.usableRect  // read now: displays may have moved meanwhile
        w.setFrame(target)
        if let now = w.frame, !vd.bounds.contains(CGPoint(x: now.midX, y: now.minY + 10)), attempt < 30 {
            // The arrangement changed under us: try again in a moment.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                self.placeWindow(attempt: attempt + 1, maxLong: maxLong, fps: fps, completion: completion)
            }
            return
        }
        agentLog("separate \(windowID): screen after \(attempt) waits, ready \(vd.isReady), display \(vd.bounds), target \(target), window now \(w.frame.map { "\($0)" } ?? "?")")
        guard let now = w.frame, vd.bounds.intersects(now) else {
            restore()
            return completion("macOS didn't let the window move to its own display (Stage Manager can prevent this)")
        }
        let sck = SCKSource(.display(vd.id))
        // A window that keeps its own size (Calculator, some dialogs) sits in
        // the display's top-left corner: send only that corner, menu bar
        // included, with room around it for menus, not a panel of wallpaper.
        let b = vd.bounds
        if now.width < target.width - 8 || now.height < target.height - 8 {
            let w = min(b.width, max(now.maxX - b.minX, 480)), h = min(b.height, max(now.maxY - b.minY, 360))
            crop = CGRect(x: 0, y: 0, width: (w / 2).rounded(.up) * 2, height: (h / 2).rounded(.up) * 2)
            sck.crop = crop
        }
        sck.onFrame = { [weak self] pb, pts, shown in self?.onFrame?(pb, pts, shown) }
        sck.onEnded = { [weak self] reason in self?.onEnded?(reason) }
        inner = sck
        sck.start(maxLong: maxLong, fps: fps) { [weak self] error in
            // Back on main, where stop() runs too, so a viewer that left during
            // startup can't leave a capture running.
            DispatchQueue.main.async {
                guard let self, !self.stopped else { return sck.stop() }
                if let error {
                    self.restore()
                    return completion(error)
                }
                self.startPolling()
                completion(nil)
            }
        }
    }

    /// The window can close or be retitled; ScreenCaptureKit won't say.
    private func startPolling() {
        let t = DispatchSource.makeTimerSource(queue: queue)
        t.schedule(deadline: .now() + 1, repeating: 1)
        t.setEventHandler { [weak self] in
            guard let self else { return }
            guard let info = WindowInfo.find(self.windowID) else {
                self.gone = true
                self.onEnded?("the window closed")
                return
            }
            if !info.title.isEmpty, info.title != self.title {
                self.title = info.title
                self.onChange?()
            }
            // Displays added at the same moment can rearrange each other, and
            // someone may drag the window away: put it back on its display.
            if !info.bounds.isEmpty {
                DispatchQueue.main.async { self.keepOnDisplay(info.bounds) }
            }
        }
        t.resume()
        poll = t
    }

    private func keepOnDisplay(_ now: CGRect) {
        guard !stopped, let vd = display, let w = window else { return }
        let b = vd.bounds
        if let c = crop {
            // Only part of the display is sent: the window must stay inside it.
            guard !c.offsetBy(dx: b.minX, dy: b.minY).insetBy(dx: -2, dy: -2).contains(now) else { return }
        } else {
            guard !b.contains(CGPoint(x: now.midX, y: now.minY + 10)) else { return }
        }
        let target = vd.usableRect
        w.setFrame(CGRect(origin: target.origin, size: now.size.width < target.width - 8 ? now.size : target.size))
    }

    /// Lifecycle state (stopped, inner, poll, window, display) is only touched on main.
    func stop() {
        DispatchQueue.main.async { [self] in
            stopped = true
            poll?.cancel()
            poll = nil
            inner?.stop()
            restore()
        }
    }

    /// Puts the window back where it was, then removes the display. In that
    /// order: removing a display first would let macOS pick where it goes.
    private func restore() {
        if let w = window, let r = original, WindowInfo.find(windowID) != nil { w.setFrame(r) }
        window = nil
        original = nil
        let vd = display
        display = nil
        // Give WindowServer a moment to move the window before the display goes.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { vd?.release() }
    }

    func setMaxLong(_ n: Int) { DispatchQueue.main.async { self.inner?.setMaxLong(n) } }

    func pointer(x: Double, y: Double, text: String?) {}
}
