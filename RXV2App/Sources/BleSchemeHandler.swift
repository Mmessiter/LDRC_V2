// LockDownRadioControl — RXV2App  ::  BleSchemeHandler.swift
//
// WKURLSchemeHandler for "ble://rx/...": the receiver's own web UI runs in a
// WKWebView, and this handler decides where each request goes:
//
//   • Static pages & assets (the files from RXV2/data, bundled in webroot/)
//     are served instantly from the app bundle — no radio traffic at all.
//   • Everything else (all /api/*.json, every POST) crosses Bluetooth via
//     BleLink, hitting the SAME firmware handlers as the WiFi portal.
//
// Redirects (Location) from POST handlers are followed internally so the
// web view always receives a final 200.

import Foundation
import WebKit

final class BleSchemeHandler: NSObject, WKURLSchemeHandler {
    private let link: BleLink
    private let demo: Bool
    private var live = Set<ObjectIdentifier>()

    init(link: BleLink, demo: Bool = false) {
        self.link = link
        self.demo = demo
    }

    private static let mime: [String: String] = [
        "html": "text/html", "css": "text/css", "js": "application/javascript",
        "svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "json": "application/json", "ico": "image/x-icon",
    ]

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        live.insert(ObjectIdentifier(task))
        guard let url = task.request.url else { return fail(task, "bad URL") }
        let path = url.path.isEmpty ? "/" : url.path
        let method = (task.request.httpMethod ?? "GET").uppercased()

        // 1) bundle-served static content (GET only). In demo mode the demo
        //    shim is injected into every page: it intercepts fetch() with
        //    canned receiver data, so nothing ever touches Bluetooth.
        if method == "GET", var (data, type) = bundled(path: path) {
            if demo && type == "text/html" {
                data = Data("<script src=\"/demo-shim.js\"></script>".utf8) + data
            }
            deliver(task, url: url, code: 200, type: type, body: data)
            return
        }
        if demo {   // nothing else exists in the demo — never touch BLE
            deliver(task, url: url, code: 404, type: "text/plain", body: Data())
            return
        }

        // 2) everything else goes over Bluetooth
        var pathAndQuery = path
        if let q = url.query, !q.isEmpty { pathAndQuery += "?\(q)" }
        var headers: [String: String] = [:]
        if let ct = task.request.value(forHTTPHeaderField: "Content-Type") {
            headers["Content-Type"] = ct
        }
        bleFetch(method: method, pathAndQuery: pathAndQuery, headers: headers,
                 body: task.request.httpBody, hops: 0) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let resp):
                self.deliver(task, url: url, code: resp.code == 0 ? 200 : resp.code,
                             type: resp.contentType, body: resp.body)
            case .failure(let err):
                let html = """
                <html><body style="font-family:-apple-system;padding:2em;text-align:center">
                <h2>Receiver not reachable</h2><p>\(err.localizedDescription)</p>
                <p><a href="ble://rx/">Try again</a></p></body></html>
                """
                self.deliver(task, url: url, code: 502, type: "text/html",
                             body: Data(html.utf8))
            }
        }
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {
        live.remove(ObjectIdentifier(task))
    }

    // MARK: - helpers

    /// GET over BLE, following up to 3 redirects (POST → 303 → GET pattern).
    private func bleFetch(method: String, pathAndQuery: String,
                          headers: [String: String], body: Data?, hops: Int,
                          completion: @escaping (Result<BleResponse, Error>) -> Void) {
        link.request(method: method, path: pathAndQuery, headers: headers, body: body) {
            [weak self] result in
            guard let self else { return }
            if case .success(let resp) = result,
               (300...399).contains(resp.code), !resp.location.isEmpty, hops < 3 {
                // follow the redirect; redirected targets may also be bundled pages
                let loc = resp.location.hasPrefix("/") ? resp.location : "/" + resp.location
                let bare = loc.split(separator: "?").first.map(String.init) ?? loc
                if let (data, type) = self.bundled(path: bare) {
                    completion(.success(BleResponse(code: 200, contentType: type,
                                                    location: "", body: data)))
                    return
                }
                self.bleFetch(method: "GET", pathAndQuery: loc, headers: [:],
                              body: nil, hops: hops + 1, completion: completion)
                return
            }
            completion(result)
        }
    }

    /// Map a portal path onto a file bundled in webroot/ (mirrors the
    /// firmware's route→file convention: "/" → index.html, "/wifi" →
    /// wifi.html, assets keep their own names).
    private func bundled(path: String) -> (Data, String)? {
        var name = path == "/" ? "index.html" : String(path.dropFirst())
        if !name.contains(".") { name += ".html" }
        // The demo shim lives outside webroot so data syncs can't delete it.
        let dir = name.hasPrefix("demo-") ? "demo" : "webroot"
        guard !name.contains(".."),
              let url = Bundle.main.url(forResource: name, withExtension: nil,
                                        subdirectory: dir),
              let data = try? Data(contentsOf: url) else { return nil }
        let ext = (name as NSString).pathExtension.lowercased()
        return (data, Self.mime[ext] ?? "application/octet-stream")
    }

    private func deliver(_ task: WKURLSchemeTask, url: URL, code: Int,
                         type: String, body: Data) {
        guard live.contains(ObjectIdentifier(task)) else { return }
        let resp = HTTPURLResponse(url: url, statusCode: code,
                                   httpVersion: "HTTP/1.1",
                                   headerFields: ["Content-Type": type,
                                                  "Content-Length": String(body.count),
                                                  "Cache-Control": "no-store"])!
        task.didReceive(resp)
        task.didReceive(body)
        task.didFinish()
        live.remove(ObjectIdentifier(task))
    }

    private func fail(_ task: WKURLSchemeTask, _ msg: String) {
        guard live.contains(ObjectIdentifier(task)) else { return }
        task.didFailWithError(NSError(domain: "BleScheme", code: 400,
                                      userInfo: [NSLocalizedDescriptionKey: msg]))
        live.remove(ObjectIdentifier(task))
    }
}
