// The Python engine (`parola serve`) as a child process on a free localhost port.

import Foundation

@MainActor
final class Engine: ObservableObject {
    enum State: Equatable {
        case starting
        case ready(URL)
        case failed(String)
    }

    @Published private(set) var state: State = .starting
    @Published private(set) var recording: [String: Any] = [:]
    private var process: Process?
    private var poll: Timer?

    var url: URL? {
        if case .ready(let url) = state { return url }
        return nil
    }

    /// Where the engine lives: the PAROLAEngine key written by build.sh (a development build
    /// points at the repo's virtualenv), or the PAROLA_ENGINE environment variable.
    private func engineCommand() -> String? {
        if let env = ProcessInfo.processInfo.environment["PAROLA_ENGINE"] { return env }
        return Bundle.main.object(forInfoDictionaryKey: "PAROLAEngine") as? String
    }

    private func dataDirectory() -> URL {
        if let dir = Bundle.main.object(forInfoDictionaryKey: "PAROLADataDir") as? String {
            return URL(fileURLWithPath: dir)
        }
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return support.appendingPathComponent("P.A.R.O.L.A./calls", isDirectory: true)
    }

    func start() {
        guard process == nil else { return }
        guard let command = engineCommand(), FileManager.default.isExecutableFile(atPath: command) else {
            state = .failed("Motore non trovato: ricostruisci l'app con app/build.sh.")
            return
        }
        let data = dataDirectory()
        try? FileManager.default.createDirectory(at: data, withIntermediateDirectories: true)
        let port = Engine.freePort()
        let p = Process()
        p.executableURL = URL(fileURLWithPath: command)
        p.arguments = ["serve", "--port", String(port), "--dir", data.path]
        // The engine resolves relative paths (bin/, data/) from its own location, not from here.
        p.currentDirectoryURL = URL(fileURLWithPath: command).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
        // Opened from Finder, the app gets only /usr/bin:/bin:/usr/sbin:/sbin, not the shell's
        // PATH: add where Homebrew puts ffmpeg (until step 3 bundles it).
        var env = ProcessInfo.processInfo.environment
        let path = (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin").split(separator: ":").map(String.init)
        let extra = ["/opt/homebrew/bin", "/usr/local/bin"].filter { !path.contains($0) }
        env["PATH"] = (extra + path).joined(separator: ":")
        p.environment = env
        p.terminationHandler = { [weak self] proc in
            Task { @MainActor in
                guard let self, self.process === proc else { return }
                self.process = nil
                self.state = .failed("Il motore si è fermato (codice \(proc.terminationStatus)).")
            }
        }
        do {
            try p.run()
        } catch {
            state = .failed("Il motore non parte: \(error.localizedDescription)")
            return
        }
        process = p
        let url = URL(string: "http://127.0.0.1:\(port)/")!
        Task { await waitUntilReady(url) }
    }

    private func waitUntilReady(_ url: URL) async {
        let status = url.appendingPathComponent("api/record/status")
        for _ in 0..<120 {  // up to a minute: the first start compiles the capture helper
            if let (_, response) = try? await URLSession.shared.data(from: status),
               (response as? HTTPURLResponse)?.statusCode == 200 {
                state = .ready(url)
                startPolling()
                return
            }
            try? await Task.sleep(nanoseconds: 500_000_000)
        }
        state = .failed("Il motore non risponde.")
    }

    // MARK: - Recording, for the menu bar

    private func startPolling() {
        poll?.invalidate()
        // Twice a second: the floating recorder's levels and state follow the capture closely.
        poll = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refresh() }
        }
    }

    func refresh() async {
        guard let url else { return }
        if let (data, _) = try? await URLSession.shared.data(from: url.appendingPathComponent("api/record/status")),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            recording = json
        }
    }

    var recordingState: String { recording["state"] as? String ?? "idle" }

    /// False until the first download of the speech models is done (asked in the window).
    var modelsReady: Bool { (recording["models"] as? String ?? "ready") == "ready" }

    func record(_ action: String) {
        guard let url else { return }
        var request = URLRequest(url: url.appendingPathComponent("api/record/\(action)"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = "{}".data(using: .utf8)
        Task {
            _ = try? await URLSession.shared.data(for: request)
            await refresh()
        }
    }

    // MARK: - Stopping

    /// SIGINT, like Ctrl-C: the engine stops a running capture cleanly before exiting.
    func stop() {
        poll?.invalidate()
        guard let p = process, p.isRunning else { return }
        process = nil
        p.interrupt()
        let deadline = Date().addingTimeInterval(10)
        while p.isRunning && Date() < deadline { usleep(100_000) }
        if p.isRunning { p.terminate() }
    }

    static func freePort() -> Int {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        defer { close(fd) }
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        addr.sin_port = 0
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafeMutablePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, len) }
        }
        _ = withUnsafeMutablePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &len) }
        }
        return Int(UInt16(bigEndian: addr.sin_port))
    }
}
