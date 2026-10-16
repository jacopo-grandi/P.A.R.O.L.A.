// swift-tools-version: 5.10
// The native shell of P.A.R.O.L.A. (decision 0028): menu bar, window, and the Python engine
// started as a child process. Built by app/build.sh, which also assembles the .app bundle.
import PackageDescription

let package = Package(
    name: "PAROLA",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "PAROLA", path: "Sources/PAROLA")
    ]
)
