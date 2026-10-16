// ilat-capture: record the microphone and the system audio of a call into two WAV files.
//
//   ilat-capture --out-dir DIR --name NAME [--duration SECONDS] [--no-mic] [--no-system]
//                [--levels]
//
// Writes DIR/NAME.mic.wav (microphone), DIR/NAME.system.wav (system audio, through a Core Audio
// process tap: no virtual driver needed, the audio keeps playing) and DIR/NAME.capture.json.
// Stops after --duration, or on SIGINT / SIGTERM. Requires macOS 14.2+ (decision 0013).
// With --levels, prints the peak level of each track (dBFS) to stderr four times a second:
//   LEVELS {"mic": -31.2, "system": -12.5}

import AVFoundation
import AudioToolbox
import CoreAudio
import Foundation

// MARK: - Helpers

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(("ilat-capture: " + message + "\n").data(using: .utf8)!)
    exit(1)
}

func check(_ status: OSStatus, _ what: String) {
    if status != noErr { fail("\(what) failed (OSStatus \(status))") }
}

func log(_ message: String) {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
}

func property<T>(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector, _ initial: T) -> T {
    var address = AudioObjectPropertyAddress(
        mSelector: selector, mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var size = UInt32(MemoryLayout<T>.size)
    var value = initial
    check(AudioObjectGetPropertyData(object, &address, 0, nil, &size, &value),
          "reading property \(selector)")
    return value
}

func deviceUID(_ device: AudioDeviceID) -> String {
    let uid: CFString = property(device, kAudioDevicePropertyDeviceUID, "" as CFString)
    return uid as String
}

func deviceName(_ device: AudioDeviceID) -> String {
    let name: CFString = property(device, kAudioObjectPropertyName, "" as CFString)
    return name as String
}

// MARK: - Options

struct Options {
    var outDir = URL(fileURLWithPath: ".")
    var name = "call"
    var duration: Double?
    var mic = true
    var system = true
    var levels = false
}

func parseOptions() -> Options {
    var o = Options()
    var args = CommandLine.arguments.dropFirst().makeIterator()
    func value(_ flag: String) -> String {
        guard let v = args.next() else { fail("\(flag) needs a value") }
        return v
    }
    while let arg = args.next() {
        switch arg {
        case "--out-dir": o.outDir = URL(fileURLWithPath: value(arg))
        case "--name": o.name = value(arg)
        case "--duration":
            guard let d = Double(value(arg)), d > 0 else { fail("--duration needs seconds") }
            o.duration = d
        case "--no-mic": o.mic = false
        case "--no-system": o.system = false
        case "--levels": o.levels = true
        case "-h", "--help":
            print("usage: ilat-capture --out-dir DIR --name NAME [--duration S] [--no-mic] [--no-system] [--levels]")
            exit(0)
        default: fail("unknown argument \(arg)")
        }
    }
    if !o.mic && !o.system { fail("nothing to record") }
    return o
}

// MARK: - Writers

final class Track {
    let file: AVAudioFile
    let format: AVAudioFormat
    var frames: Int64 = 0
    // Peak absolute sample since the last LEVELS line (read and reset on the main queue).
    var peak: Float = 0

    init(url: URL, format: AVAudioFormat) throws {
        self.format = format
        file = try AVAudioFile(
            forWriting: url, settings: format.settings, commonFormat: format.commonFormat,
            interleaved: format.isInterleaved)
    }

    func write(_ buffer: AVAudioPCMBuffer) {
        if let data = buffer.floatChannelData {
            let interleaved = buffer.format.isInterleaved
            let channels = Int(buffer.format.channelCount)
            let n = Int(buffer.frameLength) * (interleaved ? channels : 1)
            var p = peak
            for c in 0..<(interleaved ? 1 : channels) {
                for i in 0..<n { p = max(p, abs(data[c][i])) }
            }
            peak = p
        }
        do {
            try file.write(from: buffer)
            frames += Int64(buffer.frameLength)
        } catch {
            log("ilat-capture: write error: \(error)")
        }
    }

    var seconds: Double { Double(frames) / format.sampleRate }
}

// MARK: - System audio (process tap + private aggregate device)

final class SystemCapture {
    var tapID = AudioObjectID(kAudioObjectUnknown)
    var aggregateID = AudioObjectID(kAudioObjectUnknown)
    var procID: AudioDeviceIOProcID?
    let queue = DispatchQueue(label: "ilat.capture.system")
    var track: Track?
    var outputName = ""

    func start(url: URL) throws {
        let output: AudioDeviceID = property(
            AudioObjectID(kAudioObjectSystemObject), kAudioHardwarePropertyDefaultSystemOutputDevice,
            AudioDeviceID(kAudioObjectUnknown))
        outputName = deviceName(output)

        // Stereo mixdown of every process; unmuted, so the call keeps playing.
        let description = CATapDescription(stereoGlobalTapButExcludeProcesses: [])
        description.uuid = UUID()
        description.name = "ilat system tap"
        description.isPrivate = true
        description.muteBehavior = .unmuted
        check(AudioHardwareCreateProcessTap(description, &tapID), "creating the process tap")

        let aggregate: [String: Any] = [
            kAudioAggregateDeviceNameKey: "ilat-capture",
            kAudioAggregateDeviceUIDKey: UUID().uuidString,
            kAudioAggregateDeviceMainSubDeviceKey: deviceUID(output),
            kAudioAggregateDeviceIsPrivateKey: true,
            kAudioAggregateDeviceIsStackedKey: false,
            kAudioAggregateDeviceTapAutoStartKey: true,
            kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: deviceUID(output)]],
            kAudioAggregateDeviceTapListKey: [
                [kAudioSubTapDriftCompensationKey: true, kAudioSubTapUIDKey: description.uuid.uuidString]
            ],
        ]
        check(AudioHardwareCreateAggregateDevice(aggregate as CFDictionary, &aggregateID),
              "creating the aggregate device")

        var asbd: AudioStreamBasicDescription = property(
            tapID, kAudioTapPropertyFormat, AudioStreamBasicDescription())
        guard let format = AVAudioFormat(streamDescription: &asbd) else {
            fail("unsupported tap format")
        }
        let track = try Track(url: url, format: format)
        self.track = track
        check(AudioDeviceCreateIOProcIDWithBlock(&procID, aggregateID, queue) { _, input, _, _, _ in
            guard let buffer = AVAudioPCMBuffer(
                pcmFormat: format, bufferListNoCopy: input, deallocator: nil) else { return }
            track.write(buffer)
        }, "creating the IO proc")
        check(AudioDeviceStart(aggregateID, procID), "starting the system capture")
    }

    func stop() {
        if aggregateID != kAudioObjectUnknown {
            AudioDeviceStop(aggregateID, procID)
            if let procID { AudioDeviceDestroyIOProcID(aggregateID, procID) }
            queue.sync {}  // let pending buffers be written
            AudioHardwareDestroyAggregateDevice(aggregateID)
        }
        if tapID != kAudioObjectUnknown { AudioHardwareDestroyProcessTap(tapID) }
    }
}

// MARK: - Microphone

final class MicCapture {
    let engine = AVAudioEngine()
    let queue = DispatchQueue(label: "ilat.capture.mic")
    var track: Track?

    func start(url: URL) throws {
        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: granted = true
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { ok in granted = ok; semaphore.signal() }
            semaphore.wait()
        default: granted = false
        }
        if !granted {
            fail("microphone access denied: allow it in System Settings > Privacy & Security > Microphone")
        }
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        let track = try Track(url: url, format: format)
        self.track = track
        let queue = self.queue
        // installTap is deprecated in macOS 27 but still works; to revisit with its replacement.
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { buffer, _ in
            queue.async { track.write(buffer) }
        }
        try engine.start()
    }

    func stop() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        queue.sync {}
    }
}

// MARK: - Main

let options = parseOptions()
try? FileManager.default.createDirectory(at: options.outDir, withIntermediateDirectories: true)
let micURL = options.outDir.appendingPathComponent("\(options.name).mic.wav")
let systemURL = options.outDir.appendingPathComponent("\(options.name).system.wav")
let started = Date()

let mic = MicCapture()
let system = SystemCapture()
do {
    if options.system { try system.start(url: systemURL) }
    if options.mic { try mic.start(url: micURL) }
} catch {
    system.stop()
    fail("could not start: \(error)")
}
log("ilat-capture: recording (stop with Ctrl-C)")

func dbfs(_ peak: Float) -> Double { peak > 0 ? max(-90, 20 * log10(Double(peak))) : -90 }

let levelTimer = DispatchSource.makeTimerSource(queue: .main)
if options.levels {
    levelTimer.schedule(deadline: .now() + 0.25, repeating: 0.25)
    levelTimer.setEventHandler {
        var parts: [String] = []
        if let t = mic.track { parts.append("\"mic\": \(String(format: "%.1f", dbfs(t.peak)))"); t.peak = 0 }
        if let t = system.track {
            parts.append("\"system\": \(String(format: "%.1f", dbfs(t.peak)))"); t.peak = 0
        }
        log("LEVELS {" + parts.joined(separator: ", ") + "}")
    }
    levelTimer.resume()
}

func finish() -> Never {
    if options.mic { mic.stop() }
    if options.system { system.stop() }
    var meta: [String: Any] = [
        "started_at": ISO8601DateFormatter().string(from: started),
        "elapsed_seconds": Date().timeIntervalSince(started),
    ]
    if let t = mic.track {
        meta["mic"] = ["file": micURL.lastPathComponent, "sample_rate": t.format.sampleRate,
                       "channels": t.format.channelCount, "seconds": t.seconds]
    }
    if let t = system.track {
        meta["system"] = ["file": systemURL.lastPathComponent, "sample_rate": t.format.sampleRate,
                          "channels": t.format.channelCount, "seconds": t.seconds,
                          "output_device": system.outputName]
    }
    let data = try! JSONSerialization.data(withJSONObject: meta, options: [.prettyPrinted, .sortedKeys])
    try! data.write(to: options.outDir.appendingPathComponent("\(options.name).capture.json"))
    print(String(data: data, encoding: .utf8)!)
    exit(0)
}

signal(SIGINT, SIG_IGN)
signal(SIGTERM, SIG_IGN)
let sources = [SIGINT, SIGTERM].map { sig -> DispatchSourceSignal in
    let s = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    s.setEventHandler { finish() }
    s.resume()
    return s
}
if let duration = options.duration {
    DispatchQueue.main.asyncAfter(deadline: .now() + duration) { finish() }
}
_ = sources
dispatchMain()
