// The engine's interface in a native window: what the browser gave for free (choosing a file,
// saving an export, printing to PDF) is handled here.

import AppKit
import SwiftUI
import WebKit

struct WebView: NSViewRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.mediaTypesRequiringUserActionForPlayback = []
        // window.print() does nothing in a WKWebView: the page asks the app instead.
        let printScript = WKUserScript(
            source: "window.parolaNative = true; window.print = () => window.webkit.messageHandlers.print.postMessage(null);",
            injectionTime: .atDocumentStart, forMainFrameOnly: true)
        config.userContentController.addUserScript(printScript)
        config.userContentController.add(context.coordinator, name: "print")
        let view = WKWebView(frame: .zero, configuration: config)
        view.navigationDelegate = context.coordinator
        view.uiDelegate = context.coordinator
        view.setValue(false, forKey: "drawsBackground")  // black page, no white flash
        context.coordinator.webView = view
        view.load(URLRequest(url: url))
        return view
    }

    func updateNSView(_ view: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate,
        WKScriptMessageHandler
    {
        weak var webView: WKWebView?

        // "Trascrivi un file audio o video": the file input opens the system panel.
        func webView(
            _ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
            initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void
        ) {
            let panel = NSOpenPanel()
            panel.allowsMultipleSelection = parameters.allowsMultipleSelection
            panel.canChooseDirectories = false
            panel.allowedContentTypes = [.audio, .movie, .audiovisualContent]
            panel.begin { completionHandler($0 == .OK ? panel.urls : nil) }
        }

        // Exports (txt, md, docx, json) arrive as attachments: save them in Downloads.
        func webView(
            _ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
            decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void
        ) {
            let response = navigationResponse.response as? HTTPURLResponse
            let disposition = response?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
            decisionHandler(disposition.hasPrefix("attachment") ? .download : .allow)
        }

        func webView(
            _ webView: WKWebView, navigationResponse: WKNavigationResponse,
            didBecome download: WKDownload
        ) {
            download.delegate = self
        }

        func download(
            _ download: WKDownload, decideDestinationUsing response: URLResponse,
            suggestedFilename: String, completionHandler: @escaping (URL?) -> Void
        ) {
            let folder = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
            var target = folder.appendingPathComponent(suggestedFilename)
            var n = 2
            while FileManager.default.fileExists(atPath: target.path) {
                let base = (suggestedFilename as NSString).deletingPathExtension
                let ext = (suggestedFilename as NSString).pathExtension
                target = folder.appendingPathComponent("\(base) \(n).\(ext)")
                n += 1
            }
            completionHandler(target)
        }

        func downloadDidFinish(_ download: WKDownload) {
            NSSound(named: "Glass")?.play()
        }

        // window.print() from the page: the system print panel, which also saves as PDF.
        func userContentController(
            _ controller: WKUserContentController, didReceive message: WKScriptMessage
        ) {
            guard message.name == "print", let webView, let window = webView.window else { return }
            let operation = webView.printOperation(with: NSPrintInfo.shared)
            operation.view?.frame = webView.bounds
            operation.runModal(for: window, delegate: nil, didRun: nil, contextInfo: nil)
        }
    }
}
