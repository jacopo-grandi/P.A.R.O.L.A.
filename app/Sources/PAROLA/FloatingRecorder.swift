// The floating recorder (phase 8, step 2): a small panel above every other window, Meet
// included, that can shrink to a blinking dot and be dragged anywhere. It shows up when a
// recording starts and goes away when it stops.

import AppKit
import Combine
import SwiftUI

/// A borderless panel that never takes the focus away from the call.
final class RecorderPanel: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

/// Dragging the panel by any spot that is not a button.
final class DraggableHostingView<Content: View>: NSHostingView<Content> {
    override var mouseDownCanMoveWindow: Bool { true }
}

@MainActor
final class FloatingRecorder {
    private let engine: Engine
    private let model = RecorderModel()
    private var panel: RecorderPanel?
    private var watch: AnyCancellable?

    static let full = NSSize(width: 252, height: 48)
    static let icon = NSSize(width: 40, height: 40)

    init(engine: Engine) {
        self.engine = engine
        model.onAction = { [weak engine] action in engine?.record(action) }
        model.onResize = { [weak self] compact in self?.resize(compact: compact) }
        watch = engine.$recording.sink { [weak self] status in
            Task { @MainActor in self?.update(status) }
        }
    }

    private func update(_ status: [String: Any]) {
        let recording = (status["state"] as? String) == "recording"
        model.apply(status)
        if recording { show() } else { hide() }
    }

    private func makePanel() -> RecorderPanel {
        let size = model.compact ? Self.icon : Self.full
        let panel = RecorderPanel(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        panel.isMovableByWindowBackground = true
        panel.hidesOnDeactivate = false
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = true
        panel.contentView = DraggableHostingView(rootView: RecorderView(model: model))
        // Where the user left it last time; the first time, top right of the screen.
        if !panel.setFrameUsingName("PAROLARecorder"), let screen = NSScreen.main?.visibleFrame {
            panel.setFrameOrigin(NSPoint(x: screen.maxX - size.width - 24, y: screen.maxY - size.height - 24))
        }
        panel.setFrameAutosaveName("PAROLARecorder")
        return panel
    }

    private func show() {
        if panel == nil { panel = makePanel() }
        panel?.orderFrontRegardless()
    }

    private func hide() {
        panel?.orderOut(nil)
    }

    /// Shrink to the dot or grow back, keeping the top-left corner where it is.
    private func resize(compact: Bool) {
        guard let panel else { return }
        let size = compact ? Self.icon : Self.full
        var frame = panel.frame
        frame.origin.y += frame.height - size.height
        frame.size = size
        panel.setFrame(frame, display: true, animate: true)
    }
}

@MainActor
final class RecorderModel: ObservableObject {
    @Published var elapsed: Double = 0
    @Published var paused = false
    @Published var levels: (mic: Double?, system: Double?) = (nil, nil)
    @Published var compact = UserDefaults.standard.bool(forKey: "PAROLARecorderCompact")
    // Toggled once when the panel appears; the animation repeats it forever. Kept here and not
    // in a SwiftUI @State, which needs Xcode's macro plugins to compile.
    @Published var blink = false
    private var fetchedAt = Date()
    var onAction: (String) -> Void = { _ in }
    var onResize: (Bool) -> Void = { _ in }

    func apply(_ status: [String: Any]) {
        elapsed = status["elapsed"] as? Double ?? 0
        paused = status["paused"] as? Bool ?? false
        let lv = status["levels"] as? [String: Double] ?? [:]
        levels = (lv["mic"], lv["system"])
        fetchedAt = Date()
    }

    /// The clock keeps running between two status updates of the engine.
    func time(at now: Date) -> String {
        let seconds = Int(elapsed + (paused ? 0 : now.timeIntervalSince(fetchedAt)))
        let h = seconds / 3600, m = (seconds % 3600) / 60, s = seconds % 60
        return h > 0 ? String(format: "%d:%02d:%02d", h, m, s) : String(format: "%02d:%02d", m, s)
    }

    func toggleSize() {
        compact.toggle()
        UserDefaults.standard.set(compact, forKey: "PAROLARecorderCompact")
        onResize(compact)
    }
}

struct RecorderView: View {
    @ObservedObject var model: RecorderModel
    private var blink: Bool { model.blink }

    var body: some View {
        Group {
            if model.compact { icon } else { full }
        }
        .onAppear { model.blink = true }
    }

    private var dot: some View {
        Circle()
            .fill(model.paused ? Color.gray : Color.red)
            .frame(width: 11, height: 11)
            .opacity(model.paused ? 0.6 : (blink ? 0.25 : 1))
            .animation(model.paused ? .default : .easeInOut(duration: 0.6).repeatForever(), value: blink)
    }

    private var icon: some View {
        Button(action: model.toggleSize) {
            ZStack {
                Circle().fill(Color.black.opacity(0.88))
                Circle().strokeBorder(Color.white.opacity(0.12))
                dot
            }
        }
        .buttonStyle(.plain)
        .help("In registrazione: clic per aprire")
        .frame(width: FloatingRecorder.icon.width, height: FloatingRecorder.icon.height)
    }

    private var full: some View {
        HStack(spacing: 10) {
            dot
            TimelineView(.periodic(from: .now, by: 1)) { context in
                Text(model.time(at: context.date))
                    .font(.system(size: 14, weight: .semibold).monospacedDigit())
                    .foregroundStyle(.white)
            }
            VStack(spacing: 3) {
                meter(model.levels.mic)
                meter(model.levels.system)
            }
            .frame(width: 44)
            .help("Livelli: tu, gli altri")
            Spacer(minLength: 0)
            control(model.paused ? "play.fill" : "pause.fill", model.paused ? "Riprendi" : "Pausa") {
                model.onAction(model.paused ? "resume" : "pause")
            }
            control("stop.fill", "Ferma e trascrivi") { model.onAction("stop") }
            control("minus", "Riduci a icona") { model.toggleSize() }
        }
        .padding(.horizontal, 14)
        .frame(width: FloatingRecorder.full.width, height: FloatingRecorder.full.height)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color.black.opacity(0.88)))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Color.white.opacity(0.12)))
    }

    /// -60 dBFS (silence) .. 0 dBFS (full scale).
    private func meter(_ db: Double?) -> some View {
        let value = db.map { max(0, min(1, ($0 + 60) / 60)) } ?? 0
        return GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Color.white.opacity(0.12))
                Capsule().fill(Color.white.opacity(0.7)).frame(width: geo.size.width * value)
            }
        }
        .frame(height: 3)
    }

    private func control(_ symbol: String, _ label: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.white.opacity(0.85))
                .frame(width: 26, height: 26)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(label)
        .accessibilityLabel(label)
    }
}
