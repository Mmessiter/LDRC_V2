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

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BleSchemeHandler(link: link), forURLScheme: "ble")
        let shim = WKUserScript(source: Self.formShim,
                                injectionTime: .atDocumentEnd,
                                forMainFrameOnly: false)
        cfg.userContentController.addUserScript(shim)
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.isOpaque = false
        web.scrollView.contentInsetAdjustmentBehavior = .automatic
        web.load(URLRequest(url: URL(string: "ble://rx/")!))
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
