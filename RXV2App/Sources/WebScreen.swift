// LockDownRadioControl — RXV2App  ::  WebScreen.swift
//
// The receiver's own web UI inside a WKWebView, with all traffic carried
// over Bluetooth by BleSchemeHandler. A WKUserScript converts any classic
// <form> submission into fetch() — WKWebView drops POST bodies for custom
// URL schemes on form submits, and this shim sidesteps that WebKit quirk.

import SwiftUI
import WebKit

struct WebScreen: UIViewRepresentable {
    let link: BleLink
    var demo: Bool = false
    var demoRole: String = "receiver"   // which demo: receiver | dongle | simif
    var replay: Bool = false   // armchair review of the recorded last session

    static let formShim = """
    document.addEventListener('submit', function (ev) {
        const f = ev.target;
        if (!(f instanceof HTMLFormElement)) return;
        // A page that handles its own submit (fetch + in-page feedback) calls
        // preventDefault — the shim must step aside, or it document.writes a
        // raw JSON reply over the page (the blank white/black screen on save).
        // Bubble phase (not capture) so page handlers run first and this flag
        // is visible here.
        if (ev.defaultPrevented) return;
        ev.preventDefault();
        const method = (f.method || 'GET').toUpperCase();
        const action = f.getAttribute('action') || location.pathname;
        const data = new URLSearchParams(new FormData(f)).toString();
        if (method === 'GET') {
            location.href = action + (data ? ('?' + data) : '');
            return;
        }
        fetch(action, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: data,
        }).then(r => r.text().then(t => {
            document.open(); document.write(t); document.close();
            if (r.redirected) history.replaceState(null, '', r.url);
        })).catch(e => alert('Send failed: ' + e));
    }, false);
    """

    func makeCoordinator() -> Coordinator { Coordinator(link: link) }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BleSchemeHandler(link: link, demo: demo, replay: replay, demoRole: demoRole), forURLScheme: "ble")
        let shim = WKUserScript(source: Self.formShim,
                                injectionTime: .atDocumentEnd,
                                forMainFrameOnly: false)
        cfg.userContentController.addUserScript(shim)
        // JS → app bridge: the page's link badge posts 'disconnect' here
        // (window.webkit.messageHandlers.rxv2). The web UI runs full-screen
        // with no native chrome, so the badge IS the disconnect button.
        cfg.userContentController.add(context.coordinator, name: "rxv2")
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.uiDelegate = context.coordinator   // alert()/confirm()/prompt() → native dialogs
        web.isOpaque = false
        web.scrollView.contentInsetAdjustmentBehavior = .automatic
        context.coordinator.attach(web)
        // Launch argument "--page /some-page" opens straight onto that page
        // (screenshots for the website, 2026-09-07); default is the front page.
        var path = "/"
        let args = ProcessInfo.processInfo.arguments
        if let i = args.firstIndex(of: "--page"), i + 1 < args.count, args[i + 1].hasPrefix("/") { path = args[i + 1] }
        web.load(URLRequest(url: URL(string: "ble://rx" + path)!))
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKScriptMessageHandler {
        private let link: BleLink
        private weak var webView: WKWebView?
        init(link: BleLink) { self.link = link }

        // Pushed channel frames → the page's window.__rxStream(line).
        // Frames are digits/commas/pipes only; anything else is dropped, so
        // the single-quoted JS injection below is safe.
        func attach(_ web: WKWebView) {
            webView = web
            link.onStreamFrame = { [weak self] line in
                let clean = line.trimmingCharacters(in: .whitespacesAndNewlines)
                guard clean.hasPrefix("S|"),
                      clean.dropFirst(2).allSatisfy({ $0.isNumber || $0 == "," || $0 == "|" || $0 == "-" })
                else { return }
                self?.webView?.evaluateJavaScript(
                    "window.__rxStream && window.__rxStream('\(clean)')",
                    completionHandler: nil)
            }
        }

        func userContentController(_ ucc: WKUserContentController,
                                   didReceive message: WKScriptMessage) {
            guard message.name == "rxv2" else { return }
            if (message.body as? String) == "disconnect" {
                DispatchQueue.main.async {
                    self.link.disconnect()
                    // In the demo or a recording there is no link to drop: the front
                    // page's "Load another model" must still get you back to the list.
                    NotificationCenter.default.post(name: .rxv2LeaveWeb, object: nil)
                }
            }
        }
    }
}

// WKWebView implements NONE of the JS dialogs itself — without this
// delegate, alert() vanishes, confirm() returns false and prompt()
// returns null (why Setup's Rename did nothing on iOS while Android,
// whose WebChromeClient provides dialogs, was fine). Every handler must
// call its completion exactly once, even when nothing can be presented.
extension WebScreen.Coordinator: WKUIDelegate {

    private func present(_ a: UIAlertController) -> Bool {
        guard let scene = UIApplication.shared.connectedScenes
                  .compactMap({ $0 as? UIWindowScene })
                  .first(where: { $0.activationState == .foregroundActive }),
              let root = (scene.windows.first(where: { $0.isKeyWindow }) ?? scene.windows.first)?
                  .rootViewController
        else { return false }
        var top = root
        while let next = top.presentedViewController { top = next }
        top.present(a, animated: true)
        return true
    }

    func webView(_ webView: WKWebView,
                 runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping () -> Void) {
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
        if !present(a) { completionHandler() }
    }

    func webView(_ webView: WKWebView,
                 runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping (Bool) -> Void) {
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "Cancel", style: .cancel)  { _ in completionHandler(false) })
        a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
        if !present(a) { completionHandler(false) }
    }

    func webView(_ webView: WKWebView,
                 runJavaScriptTextInputPanelWithPrompt prompt: String,
                 defaultText: String?,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping (String?) -> Void) {
        let a = UIAlertController(title: nil, message: prompt, preferredStyle: .alert)
        a.addTextField { $0.text = defaultText }
        a.addAction(UIAlertAction(title: "Cancel", style: .cancel)  { _ in completionHandler(nil) })
        a.addAction(UIAlertAction(title: "OK", style: .default) { [weak a] _ in
            completionHandler(a?.textFields?.first?.text ?? "")
        })
        if !present(a) { completionHandler(nil) }
    }
}

extension Notification.Name {
    /// A page asked to leave ("Load another model"): closes the demo or recording cover.
    static let rxv2LeaveWeb = Notification.Name("rxv2.leaveWeb")
}
