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

    static let formShim = """
    document.addEventListener('submit', function (ev) {
        const f = ev.target;
        if (!(f instanceof HTMLFormElement)) return;
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
    }, true);
    """

    func makeCoordinator() -> Coordinator { Coordinator(link: link) }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BleSchemeHandler(link: link, demo: demo), forURLScheme: "ble")
        let shim = WKUserScript(source: Self.formShim,
                                injectionTime: .atDocumentEnd,
                                forMainFrameOnly: false)
        cfg.userContentController.addUserScript(shim)
        // JS → app bridge: the page's link badge posts 'disconnect' here
        // (window.webkit.messageHandlers.rxv2). The web UI runs full-screen
        // with no native chrome, so the badge IS the disconnect button.
        cfg.userContentController.add(context.coordinator, name: "rxv2")
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.isOpaque = false
        web.scrollView.contentInsetAdjustmentBehavior = .automatic
        context.coordinator.attach(web)
        web.load(URLRequest(url: URL(string: "ble://rx/")!))
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
                DispatchQueue.main.async { self.link.disconnect() }
            }
        }
    }
}
