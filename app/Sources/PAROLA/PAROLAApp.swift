// P.A.R.O.L.A.: an icon in the menu bar and a window, around the Python engine (decision 0028).

import AppKit
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    var engine: Engine?

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { engine?.stop() }  // never leave the engine (or a capture) running
    }
}

@main
struct PAROLAApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var engine = Engine()

    var body: some Scene {
        Window("P.A.R.O.L.A.", id: "main") {
            MainView()
                .environmentObject(engine)
                .frame(minWidth: 820, minHeight: 520)
                .onAppear {
                    delegate.engine = engine
                    engine.start()
                }
        }
        .defaultSize(width: 1200, height: 800)

        MenuBarExtra {
            MenuContent().environmentObject(engine)
        } label: {
            Image(systemName: engine.recordingState == "recording" ? "record.circle.fill" : "waveform")
        }
    }
}

struct MainView: View {
    @EnvironmentObject var engine: Engine

    var body: some View {
        switch engine.state {
        case .starting:
            VStack(spacing: 10) {
                ProgressView()
                Text("Avvio di P.A.R.O.L.A.…").foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.black)
        case .ready(let url):
            WebView(url: url).background(Color.black)
        case .failed(let message):
            VStack(spacing: 10) {
                Text("P.A.R.O.L.A. non è partita").font(.headline)
                Text(message).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(40)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.black)
        }
    }
}

struct MenuContent: View {
    @EnvironmentObject var engine: Engine
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        switch engine.recordingState {
        case "recording":
            Text("● In registrazione")
            Button("Ferma e trascrivi") { engine.record("stop") }
        case "transcribing":
            Text("Trascrizione in corso…")
        default:
            Button("Registra una call") { engine.record("start") }
                .disabled(engine.url == nil)
        }
        Divider()
        Button("Apri P.A.R.O.L.A.") {
            openWindow(id: "main")
            NSApp.activate(ignoringOtherApps: true)
        }
        Divider()
        Button("Esci") { NSApp.terminate(nil) }
            .keyboardShortcut("q")
    }
}
