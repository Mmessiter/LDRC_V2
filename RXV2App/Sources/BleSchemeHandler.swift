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

// Screen-awake hold for the length of an install (Malcolm 2026-09-18: "The
// iPhone screen timed out during update causing a hiccup"). The Bluetooth
// background mode (project.yml) keeps the transfer alive even when the
// screen does lock or Mail is opened; this stops the timeout in the common
// case, so the progress stays on screen. Held for a bounded time, released
// early when the OTA runner finishes.
enum ScreenAwake {
    private static var until = Date.distantPast
    static func hold(seconds: TimeInterval) {
        DispatchQueue.main.async {
            let u = Date().addingTimeInterval(seconds)
            if u > until { until = u }
            UIApplication.shared.isIdleTimerDisabled = true
            DispatchQueue.main.asyncAfter(deadline: .now() + seconds + 1) {
                if Date() >= until { UIApplication.shared.isIdleTimerDisabled = false }
            }
        }
    }
    static func release() {
        DispatchQueue.main.async {
            until = .distantPast
            UIApplication.shared.isIdleTimerDisabled = false
        }
    }
}
import WebKit
import UIKit
import UniformTypeIdentifiers
import CryptoKit

// md5 hex of a downloaded image — used for the receiver-side fingerprint skip.
func md5Hex(_ d: Data) -> String {
    Insecure.MD5.hash(data: d).map { String(format: "%02x", $0) }.joined()
}

final class BleSchemeHandler: NSObject, WKURLSchemeHandler {
    /// The handler currently serving the web view, so the static state.json
    /// helpers can reach the per-instance `live` set when they need to fail a
    /// task safely. Weak: the web screen owns its handler's lifetime.
    private(set) static weak var current: BleSchemeHandler?
    private let link: BleLink
    private let demo: Bool
    private let demoRole: String
    /// Which demo the scanner chose (set at the tap, read when every demo page is served).
    static var demoRole = "receiver"
    private let replay: Bool   // "Review last session" — serve SessionCache, never touch BLE
    private var live = Set<ObjectIdentifier>()
    private lazy var ota = BleOta(link: link)

    init(link: BleLink, demo: Bool = false, replay: Bool = false, demoRole: String = "receiver") {
        self.link = link
        self.demo = demo
        self.demoRole = demoRole
        self.replay = replay
    }

    private static let mime: [String: String] = [
        "html": "text/html", "css": "text/css", "js": "application/javascript",
        "svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "json": "application/json", "ico": "image/x-icon",
    ]

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        BleSchemeHandler.current = self
        live.insert(ObjectIdentifier(task))
        guard let url = task.request.url else { return fail(task, "bad URL") }
        let path = url.path.isEmpty ? "/" : url.path
        let method = (task.request.httpMethod ?? "GET").uppercased()

        // 0) BLE OTA push — handled by the APP (phone downloads on WiFi/5G,
        //    then streams the images over Bluetooth). Never reaches the radio.
        if path == "/app/bleota/start" {
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems
            let fw = items?.first(where: { $0.name == "fw" })?.value
            let fs = items?.first(where: { $0.name == "fs" })?.value
            let ok = (fw != nil && !demo && !replay)
            if ok { BleLink.noteRebootish(seconds: 600, window: 240); ScreenAwake.hold(seconds: 900); ota.start(fw: fw!, fs: fs) }
            deliver(task, url: url, code: 200, type: "application/json",
                    body: Data("{\"ok\":\(ok)}".utf8))
            return
        }
        if path == "/app/snapshot/start" {
            let ok = !demo && !replay
            if ok { SessionPrefetcher.run(link: link, fast: true, explicit: true) }   // the pilot's own backup — sticky
            // The ONLY way this refuses is demo/replay — so say that, rather
            // than "connect to the receiver first", which sent Malcolm looking
            // for a connection he already had, on a dongle (2026-09-17).
            deliver(task, url: url, code: 200, type: "application/json",
                    body: Data("{\"ok\":\(ok)\(ok ? "" : ",\"error\":\"this is the demo \u{2014} nothing here is really connected\"")}".utf8))
            return
        }
        if path == "/app/snapshot/progress" {
            // In review the phone IS the store — the page hides its save
            // button when it sees phase:"replay".
            deliver(task, url: url, code: 200, type: "application/json",
                    body: replay ? Data("{\"phase\":\"replay\",\"done\":0,\"total\":0}".utf8)
                                 : SessionPrefetcher.progressJSON)
            return
        }
        // Restore-from-recording (Malcolm 2026-08-06): the phone's session
        // becomes a full-settings parachute for pilots with no backups.
        if path == "/app/restore/info" {
            let cache = SessionCache.shared
            var connName = cache.modelName
            if case .ready(let n) = link.state { connName = n }
            let avail = !demo && !replay && !cache.restoreItems().isEmpty
                     && cache.modelName == connName
            var when = ""
            if let at = cache.restorePointDate() {
                let f = DateFormatter(); f.dateStyle = .short; f.timeStyle = .short
                when = f.string(from: at)
            }
            // explicit = the pilot's own "Back up" / an imported file (sticky);
            // false = the automatic freeze taken at connection.
            // items = every setting the restore point holds, by name, so the
            // page can show a human what is in it (Malcolm 2026-09-17: the
            // exported JSON "means little to a mere human").
            let items = cache.restoreItems().map { $0.label }
            // Two slots since 0.9.800: the pilot's own and the automatic copy.
            // "choices" lets the page name both and let him pick.
            let f = DateFormatter(); f.dateStyle = .short; f.timeStyle = .short
            var choices: [[String: Any]] = []
            if cache.modelName == connName, !demo, !replay {
                for mine in [true, false] {
                    let n = cache.restoreItems(mine: mine).count
                    guard n > 0 else { continue }
                    var c: [String: Any] = ["which": mine ? "yours" : "auto", "items": n]
                    if let at = cache.restorePointDate(mine: mine) { c["when"] = f.string(from: at) }
                    choices.append(c)
                }
            }
            let obj: [String: Any] = ["available": avail, "when": when,
                                      "explicit": cache.restorePointIsExplicit(),
                                      "choices": choices, "items": items]
            let body = (try? JSONSerialization.data(withJSONObject: obj)) ?? Data("{\"available\":false}".utf8)
            deliver(task, url: url, code: 200, type: "application/json", body: body)
            return
        }
        if path == "/app/restore/start" {
            if demo || replay {
                deliver(task, url: url, code: 200, type: "application/json",
                        body: Data("{\"ok\":false,\"error\":\"this is the demo \u{2014} nothing here is really connected\"}".utf8))
                return
            }
            // Foolish-user guard: refuse outright with the transmitter on.
            link.request(method: "GET", path: "/api/state.json", headers: [:], body: nil) { [weak self] result in
                guard let self else { return }
                var txLive = false
                if case .success(let resp) = result,
                   let obj = try? JSONSerialization.jsonObject(with: resp.body) as? [String: Any],
                   let rf = obj["rf"] as? [String: Any],
                   let lastPkt = rf["last_pkt_ms"] as? Double {
                    txLive = lastPkt >= 0 && lastPkt < 3000
                }
                DispatchQueue.main.async {
                    if txLive {
                        self.deliver(task, url: url, code: 200, type: "application/json",
                                     body: Data("{\"ok\":false,\"error\":\"switch the transmitter OFF first\"}".utf8))
                    } else {
                        // Which backup to write back (0.9.800). Absent = the
                        // pilot's own when he has one.
                        let which = URLComponents(url: url, resolvingAgainstBaseURL: false)?
                            .queryItems?.first(where: { $0.name == "which" })?.value
                        RestoreRunner.useMine = which == "yours" ? true : which == "auto" ? false : nil
                        RestoreRunner.run(link: self.link)
                        self.deliver(task, url: url, code: 200, type: "application/json",
                                     body: Data("{\"ok\":true}".utf8))
                    }
                }
            }
            return
        }
        // Declared write-only settings + portable backup files
        // (Malcolm 2026-08-30).
        if path == "/app/declare" {
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems
            let key = items?.first(where: { $0.name == "key" })?.value ?? ""
            let hex = items?.first(where: { $0.name == "hex" })?.value ?? ""
            let ok = !key.isEmpty && !hex.isEmpty && !demo && !replay
            if ok { SessionCache.shared.declare(key: key, hex: hex) }
            deliver(task, url: url, code: 200, type: "application/json", body: Data("{\"ok\":\(ok)}".utf8))
            return
        }
        // COMPARE (0.9.833): saved backups, read-only, for rotorflight-compare.
        if path == "/app/compare/models" {
            let body = (try? JSONSerialization.data(withJSONObject: SessionCache.compareModels())) ?? Data("[]".utf8)
            deliver(task, url: url, code: 200, type: "application/json", body: body)
            return
        }
        if path == "/app/compare/entries" {
            let m = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "model" }?.value ?? ""
            let body = (try? JSONSerialization.data(withJSONObject: SessionCache.compareEntries(model: m))) ?? Data("{}".utf8)
            deliver(task, url: url, code: 200, type: "application/json", body: body)
            return
        }
        if path == "/app/declared" {
            let d = SessionCache.shared.declared()
            let body = (try? JSONSerialization.data(withJSONObject: d)) ?? Data("{}".utf8)
            deliver(task, url: url, code: 200, type: "application/json", body: body)
            return
        }
        // SEND DEBUG DATA (0.9.816). The page gathers the receiver's side and
        // posts it here as plain text; the app appends what IT did — the link
        // log the receiver cannot see — and hands the lot to the share sheet.
        // For testers with boards of their own: "it didn't work" becomes
        // something traceable (Malcolm 2026-09-20).
        if path == "/app/debug/export" {
            let subject = URLComponents(url: url, resolvingAgainstBaseURL: false)?
                .queryItems?.first(where: { $0.name == "subject" })?.value ?? "LDRC debug report"
            var report = String(data: task.request.httpBody ?? Data(), encoding: .utf8) ?? ""
            if report.isEmpty { report = "(the page sent nothing)" }
            report += "\n\nWHAT THE APP DID (this phone)\n"
            let log = link.log
            report += log.isEmpty ? "  (nothing recorded)\n" : log.map { "  " + $0 }.joined(separator: "\n")
            let appVer = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?"
            report += "\n\nPHONE\n  app \(appVer) on iOS \(UIDevice.current.systemVersion), \(UIDevice.current.model)\n"
            let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd-HHmm"
            let safe = String(SessionCache.shared.modelName.map { $0.isLetter || $0.isNumber ? $0 : "_" })
            let file = FileManager.default.temporaryDirectory
                .appendingPathComponent("\(safe.isEmpty ? "LDRC" : safe)-debug-\(df.string(from: Date())).txt")
            try? report.data(using: .utf8)?.write(to: file, options: .atomic)
            DispatchQueue.main.async {
                let av = UIActivityViewController(activityItems: [DebugShareItem(file: file, subject: subject)],
                                                  applicationActivities: nil)
                if let top = BackupFilePicker.topViewController() {
                    av.popoverPresentationController?.sourceView = top.view
                    av.popoverPresentationController?.sourceRect = CGRect(x: top.view.bounds.midX, y: top.view.bounds.midY, width: 1, height: 1)
                    top.present(av, animated: true)
                }
            }
            deliver(task, url: url, code: 200, type: "application/json", body: Data("{\"ok\":true}".utf8))
            return
        }
        if path == "/app/backup/export" {
            guard let json = SessionCache.shared.exportRestoreJSON() else {
                deliver(task, url: url, code: 200, type: "application/json",
                        body: Data("{\"ok\":false,\"error\":\"no backup on this phone for this model yet\"}".utf8))
                return
            }
            let safe = SessionCache.shared.modelName.map { $0.isLetter || $0.isNumber ? $0 : "_" }
            let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd"
            let file = FileManager.default.temporaryDirectory
                .appendingPathComponent("\(String(safe).isEmpty ? "model" : String(safe))-LDRC-backup-\(df.string(from: Date())).json")
            try? json.write(to: file, options: .atomic)
            DispatchQueue.main.async {
                let av = UIActivityViewController(activityItems: [file], applicationActivities: nil)
                if let top = BackupFilePicker.topViewController() {
                    av.popoverPresentationController?.sourceView = top.view
                    av.popoverPresentationController?.sourceRect = CGRect(x: top.view.bounds.midX, y: top.view.bounds.midY, width: 1, height: 1)
                    top.present(av, animated: true)
                }
            }
            deliver(task, url: url, code: 200, type: "application/json", body: Data("{\"ok\":true}".utf8))
            return
        }
        if path == "/app/backup/import" {
            var connName = SessionCache.shared.modelName
            if case .ready(let n) = link.state { connName = n }
            if demo || replay || connName.isEmpty {
                deliver(task, url: url, code: 200, type: "application/json",
                        body: Data("{\"ok\":false,\"error\":\"\((demo || replay) ? "this is the demo \u{2014} nothing here is really connected" : "connect to the receiver or dongle first")\"}".utf8))
                return
            }
            BackupFilePicker.shared.pick(forModel: connName)
            deliver(task, url: url, code: 200, type: "application/json", body: Data("{\"ok\":true}".utf8))
            return
        }
        if path == "/app/backup/import/status" {
            deliver(task, url: url, code: 200, type: "application/json", body: BackupFilePicker.shared.statusJSON)
            return
        }
        if path == "/app/restore/progress" {
            deliver(task, url: url, code: 200, type: "application/json",
                    body: RestoreRunner.progressJSON)
            return
        }
        if path == "/app/bleota/progress" {
            deliver(task, url: url, code: 200, type: "application/json",
                    body: ota.progressJSON)
            return
        }
        // The pages ask the APP for the public release manifest — the phone
        // has internet at the field, the receiver (Bluetooth-only) does not.
        if path == "/app/manifest" {
            // Review mode must NEVER offer updates — there is no receiver to
            // update (Malcolm 2026-08-04: offered one offline, it 'failed').
            if demo || replay {
                deliver(task, url: url, code: 404, type: "application/json",
                        body: Data("{}".utf8))
                return
            }
            var req = URLRequest(url: URL(string: "https://messiter.com/rxv2/release/manifest.json")!)
            req.cachePolicy = .reloadIgnoringLocalCacheData
            URLSession.shared.dataTask(with: req) { [weak self] data, resp, _ in
                DispatchQueue.main.async {
                    guard let self else { return }
                    if let data, (resp as? HTTPURLResponse)?.statusCode == 200 {
                        self.deliver(task, url: url, code: 200, type: "application/json", body: data)
                    } else {
                        self.deliver(task, url: url, code: 502, type: "application/json",
                                     body: Data("{}".utf8))
                    }
                }
            }.resume()
            return
        }

        // 1) bundle-served static content (GET only). In demo mode the demo
        //    shim is injected into every page: it intercepts fetch() with
        //    canned receiver data, so nothing ever touches Bluetooth.
        if method == "GET", var (data, type) = bundled(path: path) {
            if demo && type == "text/html" {
                data = Data("<script>window.__demoRole=\"\(demoRole == "receiver" ? BleSchemeHandler.demoRole : demoRole)\";</script><script src=\"/demo-shim.js\"></script>".utf8) + data
            }
            deliver(task, url: url, code: 200, type: type, body: data)
            return
        }
        if demo {   // nothing else exists in the demo — never touch BLE
            deliver(task, url: url, code: 404, type: "text/plain", body: Data())
            return
        }
        if replay { // armchair review: the recording answers, the radio sleeps
            var pathAndQuery = path
            if let q = url.query, !q.isEmpty { pathAndQuery += "?\(q)" }
            // Offline Rotorflight EDITS: capture supported MSP writes for the
            // reconnect offer; EEPROM/reboot get polite empty echoes so the
            // pages' save flows complete naturally.
            if path == "/api/msp" {
                let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems
                let fn = Int(items?.first(where: { $0.name == "fn" })?.value ?? "") ?? -1
                let dataHex = items?.first(where: { $0.name == "data" })?.value
                if fn == 210 {   // bank select is part of the pages' READ flow —
                    // note it (the cache keys banked reads by it), nod politely.
                    if let hex = dataHex { SessionCache.shared.noteBankSelect(dataHex: hex) }
                    deliver(task, url: url, code: 200, type: "text/plain", body: Data())
                    return
                }
                // fn=174 (mixer input) and fn=154 (RPM notch) are READS whose
                // index rides in data= - the recorder knows (cacheable), and so
                // must the review, or Travel extents answers "this change cannot
                // be made in review" (Malcolm 2026-09-24, Goblin770 review).
                if let hex = dataHex, !hex.isEmpty, !SessionCache.indexedReadFns.contains(fn) {
                    if SessionCache.shared.captureOfflineWrite(fn: fn, dataHex: hex) {
                        deliver(task, url: url, code: 200, type: "text/plain", body: Data())
                    } else {
                        deliver(task, url: url, code: 409, type: "text/plain",
                                body: Data("receiver offline — this change cannot be made in review".utf8))
                    }
                    return
                }
                if fn == 250 || fn == 68 {   // EEPROM save / reboot: nod politely
                    deliver(task, url: url, code: 200, type: "text/plain", body: Data())
                    return
                }
            }
            if method == "GET", let hit = SessionCache.shared.lookup(pathAndQuery: pathAndQuery) {
                deliver(task, url: url, code: 200, type: hit.type, body: hit.body)
                return
            }
            if method == "POST", path == "/api/time" {   // pages teach the time; nod politely
                deliver(task, url: url, code: 200, type: "application/json",
                        body: Data("{\"ok\":true}".utf8))
                return
            }
            let code = method == "GET" ? 404 : 409
            deliver(task, url: url, code: code, type: "application/json",
                    body: Data("{\"ok\":false,\"error\":\"receiver offline — reviewing the last session\"}".utf8))
            return
        }

        // 1a) App Store builds never render HTML or JS fetched from the
        //     receiver. App Review guideline 2.5.2 forbids downloading code
        //     that adds features the reviewed build did not have, and the
        //     receiver can serve whole pages — so in a RELEASE build a page
        //     that is missing from the bundle is a stale app, not a fetch.
        //     Data still crosses Bluetooth freely: /api/* and /app/* are how
        //     the app talks to the receiver at all.
        //     DEBUG builds keep the old behaviour on purpose: that is the
        //     development loop, where a new receiver page must appear in the
        //     app before the app has been rebuilt.
        #if !DEBUG
        if method == "GET", !path.hasPrefix("/api/"), !path.hasPrefix("/app/") {
            let html = """
            <!doctype html><meta charset=utf-8>
            <meta name=viewport content="width=device-width,initial-scale=1">
            <title>Update this app</title>
            <style>body{font:16px -apple-system,system-ui,sans-serif;margin:0;\
            padding:2.2em 1.4em;background:#eef2f5;color:#22303a}\
            .c{background:#fff;border-radius:14px;padding:1.4em;max-width:26em;\
            margin:0 auto;box-shadow:0 1px 4px rgba(0,0,0,.13)}\
            h1{font-size:1.25em;margin:0 0 .6em}p{margin:.6em 0;line-height:1.45}</style>
            <div class=c><h1>This app is older than your receiver</h1>
            <p><b>Update the app from the App Store.</b></p>
            <p>Your receiver has a page this version of the app does not know
            about yet. Everything else still works.</p></div>
            """
            deliver(task, url: url, code: 200, type: "text/html", body: Data(html.utf8))
            return
        }
        #endif

        // 2) everything else goes over Bluetooth
        // Page-originated MSP: stamp it so the background sweep yields —
        // interleaved bank selects made pages read the WRONG bank's values.
        if path == "/api/msp" {
            SessionPrefetcher.lastPageMspMs = Date().timeIntervalSince1970 * 1000
        }
        // Reboot-ish traffic (anything that can restart or silence the
        // receiver deliberately): keep the ride-through reconnect armed.
        // Plain browsing never arms it — a disconnect then = model off.
        // A config-save reboot drops the link within ~3 s of its POST, so
        // 15 s suffices; only a firmware install disconnects minutes later
        // (Malcolm 2026-08-08: power-off after setting up a NEW receiver
        // sat in the old 180 s window instead of jumping to the scanner).
        if method == "POST" && path != "/api/time" {
            if path == "/api/firmware/install" { BleLink.noteRebootish(seconds: 300, window: 240); ScreenAwake.hold(seconds: 420) }
            else { BleLink.noteRebootish(seconds: 15) }
        }
        var pathAndQuery = path
        if let q = url.query, !q.isEmpty { pathAndQuery += "?\(q)" }
        var headers: [String: String] = [:]
        if let ct = task.request.value(forHTTPHeaderField: "Content-Type") {
            headers["Content-Type"] = ct
        }
        // ---- /api/state.json: single-flight + micro-cache --------------------
        // MEASURED 2026-09-14: state.json is 4,414 bytes, and the app asks for
        // it from several places at once — app.js's own poll, the armed banner,
        // and each page's startPolling — 1.2 to 3.2 times a SECOND, with no
        // sharing between them. Over Bluetooth the link carries roughly 24 kB/s,
        // so that one document was occupying a large and permanent fraction of
        // it before the user touched anything. Everything else queued behind it,
        // which is what "much too slow" actually was.
        //
        // So: concurrent askers share ONE fetch, and a reply less than 600 ms
        // old is served straight from memory. 600 ms is well inside the armed
        // banner's own 1.2 s cadence, so nothing safety-relevant gets staler
        // than it already was. WiFi is untouched — this handler is the
        // Bluetooth path only.
        if method == "GET", path == "/api/state.json", url.query?.isEmpty != false {
            let now = Date()
            if let c = Self.stateCache, now.timeIntervalSince(c.at) < 0.6 {
                deliver(task, url: url, code: 200, type: "application/json", body: c.body)
                return
            }
            Self.stateWaiters.append((task, url))
            if Self.stateInFlight { return }            // someone is already asking
            Self.stateInFlight = true
            bleFetch(method: "GET", pathAndQuery: pathAndQuery, headers: headers,
                     body: nil, hops: 0) { [weak self] result in
                guard let self else { return }
                let waiters = Self.stateWaiters
                Self.stateWaiters.removeAll()
                Self.stateInFlight = false
                switch result {
                case .success(let resp):
                    let body = resp.body
                    if resp.code == 200 || resp.code == 0 { Self.stateCache = (body, Date()) }
                    for (t, u) in waiters {
                        self.deliver(t, url: u, code: resp.code == 0 ? 200 : resp.code,
                                     type: "application/json", body: body)
                    }
                case .failure(let e):
                    // MUST go through fail(): it checks `live` first. Calling
                    // didFailWithError on a task WKWebView has already stopped
                    // (a page navigation during the fetch) raises an Obj-C
                    // exception and takes the app down.
                    for (t, _) in waiters { self.fail(t, e.localizedDescription) }
                }
            }
            return
        }

        bleFetch(method: method, pathAndQuery: pathAndQuery, headers: headers,
                 body: task.request.httpBody, hops: 0) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let resp):
                // A rename that the receiver ACCEPTED: remember the NEW name now.
                // The list's auto-connect looks for lastDeviceName, and until
                // this it still held the name the user TAPPED - a board that no
                // longer exists once it reboots as the new one. Malcolm named a
                // dongle "Fred" and had to quit and reopen the app twice before
                // it would connect (2026-09-22). The identifier is unchanged, so
                // fastConnect still finds it; now the label agrees too.
                if method == "POST", (path == "/api/firstrun" || path == "/api/name"),
                   (resp.code == 0 || resp.code == 200),
                   let b = task.request.httpBody, let form = String(data: b, encoding: .utf8) {
                    let newName = form.split(separator: "&")
                        .compactMap { kv -> String? in
                            let p = kv.split(separator: "=", maxSplits: 1).map(String.init)
                            return p.count == 2 && p[0] == "name" ? p[1].removingPercentEncoding : nil
                        }.first?.trimmingCharacters(in: .whitespaces) ?? ""
                    if !newName.isEmpty { self.link.noteRenamed(newName) }
                }
                // Bank selects steer the recorder's keys for banked MSP reads.
                if path == "/api/msp", let q = url.query, q.contains("fn=210"),
                   (resp.code == 0 || resp.code == 200),
                   let d = q.split(separator: "&").first(where: { $0.hasPrefix("data=") }) {
                    SessionCache.shared.noteBankSelect(dataHex: String(d.dropFirst(5)))
                }
                // Armchair-review recorder: tee every successful read so the
                // session can be replayed after the receiver is switched off.
                if method == "GET", (resp.code == 0 || resp.code == 200),
                   SessionCache.cacheable(path: path, query: url.query) {
                    SessionCache.shared.record(pathAndQuery: pathAndQuery, path: path,
                                               type: resp.contentType, body: resp.body)
                }
                self.deliver(task, url: url, code: resp.code == 0 ? 200 : resp.code,
                             type: resp.contentType, body: resp.body)
            case .failure(let err):
                // Plain text, 504: pages show e.message and used to print this
                // as raw HTML, and 502 is the firmware's own "FC rejected" code
                // (2026-09-16 review).
                self.deliver(task, url: url, code: 504, type: "text/plain",
                             body: Data("no answer from the receiver (\(err.localizedDescription))".utf8))
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

    /// Shared state.json reply and the tasks waiting on the one fetch in flight.
    /// Cleared on disconnect so a new receiver never serves the old one's state.
    static var stateCache: (body: Data, at: Date)?
    static var stateInFlight = false
    static var stateWaiters: [(WKURLSchemeTask, URL)] = []
    /// Called on every disconnect. Waiters MUST be failed, not merely dropped:
    /// a page whose status poll was in flight when the receiver rebooted would
    /// otherwise never get an answer and would stop polling for good, leaving a
    /// permanently frozen status display until the page was reloaded.
    static func forgetStateCache() {
        stateCache = nil
        stateInFlight = false
        let orphans = stateWaiters
        stateWaiters.removeAll()
        for (t, _) in orphans { current?.fail(t, "Receiver disconnected") }
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

// MARK: - BLE OTA push runner
//
// Mirrors the Android RXV2App implementation: download firmware.bin (+
// littlefs.bin) with the phone's own internet, then stream them to the
// receiver as 0xA5 raw chunks over the BLE request characteristic while the
// firmware writes flash incrementally (/api/bleota/begin → chunks →
// /api/bleota/status resyncs → /api/bleota/end → /api/bleota/reboot).

final class BleOta {
    private let link: BleLink
    private let lock = NSLock()
    // phase: idle|download|fw|fs|rebooting|error|done  (firmware.html contract)
    private var phase = "idle"
    private var msg = ""
    private var sent: Int64 = 0
    private var total: Int64 = 0
    // false with phase "done" = the receiver never reappeared over Bluetooth
    // to confirm the version. firmware.html then returns to the model list
    // instead of reloading over a link that is not back (5.99).
    private var confirmed = true
    private var running = false

    // Any install in flight, app-wide (0.9.834): the background backup
    // (SessionPrefetcher) will not start, and a running one stops, so no
    // bank switch or flight-controller read shares the link with an update.
    private static let busyLock = NSLock()
    private static var busyFlag = false
    static var busy: Bool {
        get { busyLock.lock(); defer { busyLock.unlock() }; return busyFlag }
        set { busyLock.lock(); busyFlag = newValue; busyLock.unlock() }
    }

    init(link: BleLink) { self.link = link }

    var progressJSON: Data {
        lock.lock(); defer { lock.unlock() }
        let esc = msg.replacingOccurrences(of: "\\", with: "\\\\")
                     .replacingOccurrences(of: "\"", with: "\\\"")
        return Data("{\"phase\":\"\(phase)\",\"msg\":\"\(esc)\",\"sent\":\(sent),\"total\":\(total),\"confirmed\":\(confirmed)}".utf8)
    }

    func start(fw: String, fs: String?) {
        lock.lock()
        if running { lock.unlock(); return }
        running = true
        BleOta.busy = true
        phase = "download"; msg = "Downloading with the phone's internet…"
        sent = 0; total = 0; confirmed = true
        lock.unlock()
        DispatchQueue.global(qos: .userInitiated).async { self.run(fwUrl: fw, fsUrl: fs) }
    }

    private func set(_ p: String, _ m: String) {
        lock.lock(); phase = p; msg = m; lock.unlock()
    }

    private func phaseNow() -> String {
        lock.lock(); defer { lock.unlock() }
        return phase
    }

    private func run(fwUrl: String, fsUrl: String?) {
        defer { lock.lock(); running = false; lock.unlock(); BleOta.busy = false; ScreenAwake.release() }
        do {
            let fw = try download(fwUrl)
            var fs: Data? = nil
            if let u = fsUrl, !u.isEmpty { fs = try? download(u) }
            // Older on-receiver pages omit &fs= — derive the pages image from
            // the release-directory convention so web pages always ship too.
            if fs == nil, fwUrl.hasSuffix("firmware.bin") {
                fs = try? download(String(fwUrl.dropLast("firmware.bin".count)) + "littlefs.bin")
            }
            // Fingerprint skip (2026-07-31): if the receiver reports it already
            // runs an identical pages image (info.fs_md5 in state.json), don't
            // rewrite the filesystem — the 20 saved flights and Rotorflight
            // backups stay untouched and the update is much faster.
            //
            // EXCEPTION (Malcolm 2026-08-14): reinstalling the version that is
            // ALREADY RUNNING is the user's "something's wrong — reflash
            // everything" gesture, so the skip must never apply then. The
            // fs_md5 stamp is only a record of the last image we SENT — if a
            // frozen/failed install left the stamp ahead of reality, the skip
            // would otherwise block the pages forever (the missing Travel
            // extents button: fw 0.9.355 running, pages stale, every
            // reinstall skipped the fs on a lying stamp).
            if let f = fs,
               let st = try? reqSync("GET", "/api/state.json"),
               let obj = (try? JSONSerialization.jsonObject(with: st.body)) as? [String: Any],
               let info = obj["info"] as? [String: Any] {
                var isReinstall = false
                if let cur = info["fw_version"] as? String,
                   let tagRange = fwUrl.range(of: #"v\d+\.\d+\.\d+"#, options: .regularExpression) {
                    let tag = String(fwUrl[tagRange].dropFirst())   // "0.9.355"
                    isReinstall = cur.contains(tag)
                }
                if isReinstall {
                    set("download", "Reinstall — rewriting the web pages too…")
                } else if let have = info["fs_md5"] as? String, have.count == 32,
                          md5Hex(f) == have.lowercased() {
                    fs = nil
                    set("download", "Web pages unchanged — keeping flights…")
                }
            }
            lock.lock(); total = Int64(fw.count + (fs?.count ?? 0)); lock.unlock()
            // one clean restart per image: /begin resets the receiver side,
            // so a transfer that died mid-way gets a second, fresh attempt
            func sendImage(_ type: String, _ bytes: Data, _ base: Int64, _ label: String) throws {
                do { try streamImage(type: type, bytes: bytes, base: base) } catch {
                    let m = error.localizedDescription
                    if m.contains("too old") || m.hasPrefix("refused:") { throw error }   // a refusal is final: no retry
                    set(phaseNow(), "Bluetooth hiccup — starting the \(label) again…")
                    Thread.sleep(forTimeInterval: 2)
                    try streamImage(type: type, bytes: bytes, base: base)
                }
            }
            set("fw", "Sending firmware over Bluetooth…")
            try sendImage("fw", fw, 0, "firmware")
            if let fs {
                set("fs", "Sending web pages over Bluetooth…")
                try sendImage("fs", fs, Int64(fw.count), "web pages")
            }
            set("rebooting", "Waiting for the receiver to come back…")
            _ = try? reqSync("POST", "/api/bleota/reboot")   // reply may die with the radio
            // The receiver reboots straight back into BLE mode (config-reboot
            // flag) and the link layer auto-reconnects for 240 s (the window
            // stamped at /app/bleota/start) — poll until it answers, then
            // report the version it now runs. Was 120 s against a 90 s
            // reconnect window: DongleSim 2026-09-18 "just sat there" and the
            // page never learned the update had gone in.
            Thread.sleep(forTimeInterval: 4)
            var newVer = ""
            let deadline = Date().addingTimeInterval(240)
            while Date() < deadline {
                if let st = try? reqSync("GET", "/api/state.json"), st.code == 200,
                   let j = (try? JSONSerialization.jsonObject(with: st.body)) as? [String: Any],
                   let info = j["info"] as? [String: Any],
                   let v = info["fw_version"] as? String, !v.isEmpty {
                    newVer = v
                    break
                }
                Thread.sleep(forTimeInterval: 3)
            }
            lock.lock(); confirmed = !newVer.isEmpty; lock.unlock()
            set("done", newVer.isEmpty
                ? "installed; the receiver didn't reappear on Bluetooth to confirm — reopen the app to check it"
                : "now running \(newVer)")
        } catch {
            set("error", error.localizedDescription)
            _ = try? reqSync("POST", "/api/bleota/status")   // lets the 30 s watchdog abort cleanly
        }
    }

    // MARK: sync helpers (all called on the background runner thread)

    private func fault(_ m: String) -> Error {
        NSError(domain: "BleOta", code: 1, userInfo: [NSLocalizedDescriptionKey: m])
    }

    private func reqSync(_ method: String, _ path: String) throws -> BleResponse {
        let sem = DispatchSemaphore(value: 0)
        var result: Result<BleResponse, Error>?
        DispatchQueue.main.async {
            self.link.request(method: method, path: path) { r in result = r; sem.signal() }
        }
        if sem.wait(timeout: .now() + 30) == .timedOut {
            throw fault("BLE request timed out: \(path)")
        }
        return try result!.get()
    }

    private func sendSync(_ frames: [Data]) throws {
        let sem = DispatchSemaphore(value: 0)
        var failure: Error?
        link.otaSend(frames) { r in
            if case .failure(let e) = r { failure = e }
            sem.signal()
        }
        if sem.wait(timeout: .now() + 60) == .timedOut { throw fault("chunk batch stalled") }
        if let failure { throw failure }
    }

    /// Hosts a firmware image may be fetched from. The URL arrives from the
    /// page in `fw=`, so without this the web content could name any server.
    /// Firmware is the one download that ends up executing on the hardware,
    /// so it comes from Malcolm's own site over TLS or it does not come.
    private static let firmwareHosts = ["messiter.com", "www.messiter.com"]

    private func download(_ url: String) throws -> Data {
        guard let u = URL(string: url) else { throw fault("bad URL \(url)") }
        #if !DEBUG    // DEBUG keeps the local dev firmware server usable
        guard u.scheme?.lowercased() == "https",
              let host = u.host?.lowercased(),
              Self.firmwareHosts.contains(host) else {
            throw fault("firmware may only be downloaded over https from messiter.com")
        }
        #endif
        let sem = DispatchSemaphore(value: 0)
        var data: Data?
        var failure: Error?
        let task = URLSession.shared.dataTask(with: u) { d, resp, e in
            if let e { failure = e }
            else if let http = resp as? HTTPURLResponse, http.statusCode != 200 {
                failure = self.fault("HTTP \(http.statusCode) for \(url)")
            } else { data = d }
            sem.signal()
        }
        task.resume()
        if sem.wait(timeout: .now() + 60) == .timedOut {
            task.cancel(); throw fault("download timed out")
        }
        if let failure { throw failure }
        guard let data, !data.isEmpty else { throw fault("empty download") }
        return data
    }

    private func streamImage(type: String, bytes: Data, base: Int64) throws {
        let begin = try reqSync("POST", "/api/bleota/begin?type=\(type)&size=\(bytes.count)")
        if begin.code == 404 {
            throw fault("this receiver's firmware is too old for Bluetooth updates — do this one update over WiFi, then Bluetooth works from now on")
        }
        guard begin.code == 200 else {
            // The receiver's own sentence ("ARMED - …", "turn the transmitter off first - …"), marked final.
            throw fault("refused: " + (String(data: begin.body, encoding: .utf8) ?? "the receiver refused to start the update"))
        }
        var chunkData = 64
        DispatchQueue.main.sync { chunkData = self.link.otaChunkSize() }
        var off = 0
        // A BLE hiccup mid-stream is NOT fatal: the receiver keeps the
        // transfer open (it only ever accepts the next in-sequence chunk),
        // so on any error we re-ask where it got to and carry on from there.
        // Only give up after several consecutive failures with no progress.
        var fails = 0
        func status() throws -> [String: Any] {
            let st = try reqSync("GET", "/api/bleota/status")
            return (try? JSONSerialization.jsonObject(with: st.body)) as? [String: Any] ?? [:]
        }
        while off < bytes.count {
            do {
                var frames: [Data] = []
                var o = off
                while o < bytes.count && frames.count < 128 {
                    let n = min(chunkData, bytes.count - o)
                    var f = Data([0xA5,
                                  UInt8(o & 0xFF), UInt8((o >> 8) & 0xFF),
                                  UInt8((o >> 16) & 0xFF), UInt8((o >> 24) & 0xFF)])
                    f.append(bytes.subdata(in: o..<o + n))
                    frames.append(f)
                    o += n
                }
                try sendSync(frames)
                // resync: the receiver only accepts in-sequence chunks
                let j = try status()
                if let e = j["error"] as? String, !e.isEmpty { throw fault("receiver: \(e)") }
                if let a = j["active"] as? Bool, !a { throw fault("receiver abandoned the transfer") }
                let got = (j["got"] as? NSNumber)?.intValue ?? o
                fails = got > off ? 0 : fails + 1
                if fails >= 5 { throw fault("no progress after 5 attempts at \(off / 1024) KB") }
                off = got
                lock.lock(); sent = base + Int64(off); lock.unlock()
            } catch {
                let m = error.localizedDescription
                if m.hasPrefix("receiver") || m.hasPrefix("no progress") || m.contains("too old") { throw error }
                fails += 1
                if fails >= 5 { throw error }
                Thread.sleep(forTimeInterval: 1.5)   // transient (timeout / stalled batch) — resync and retry
                if let j = try? status(), let g = (j["got"] as? NSNumber)?.intValue { off = g }
            }
        }
        let end = try reqSync("POST", "/api/bleota/end")
        guard end.code == 200 else {
            throw fault("end(\(type)): \(String(data: end.body, encoding: .utf8) ?? "")")
        }
    }
}


// MARK: - Backup file import picker (Malcolm 2026-08-30: "email the setup to a
// friend who has exactly the same helicopter"). Presents the document picker,
// adopts the chosen file as the restore point for the CONNECTED model, and
// reports through /app/backup/import/status for the page to narrate.
final class BackupFilePicker: NSObject, UIDocumentPickerDelegate {
    static let shared = BackupFilePicker()
    private var forModel = ""
    private var phase = "idle"        // idle | picking | done | failed
    private var fileModel = ""
    private var count = 0
    private var mechanics = true     // false = another model's file: servo/mixer items left out
    var statusJSON: Data {
        let m = fileModel.replacingOccurrences(of: "\"", with: "'")
        return Data("{\"phase\":\"\(phase)\",\"model\":\"\(m)\",\"count\":\(count),\"mechanics\":\(mechanics)}".utf8)
    }
    static func topViewController() -> UIViewController? {
        guard let scene = UIApplication.shared.connectedScenes
                  .compactMap({ $0 as? UIWindowScene })
                  .first(where: { $0.activationState == .foregroundActive }),
              let root = (scene.windows.first(where: { $0.isKeyWindow }) ?? scene.windows.first)?
                  .rootViewController else { return nil }
        var top = root
        while let next = top.presentedViewController { top = next }
        return top
    }
    func pick(forModel model: String) {
        forModel = model; phase = "picking"; fileModel = ""; count = 0; mechanics = true
        DispatchQueue.main.async {
            let p = UIDocumentPickerViewController(forOpeningContentTypes: [.json, .plainText, .data], asCopy: true)
            p.delegate = self
            p.allowsMultipleSelection = false
            Self.topViewController()?.present(p, animated: true)
        }
    }
    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard let u = urls.first, let d = try? Data(contentsOf: u) else { phase = "failed"; return }
        let r = SessionCache.shared.importRestore(json: d, forModel: forModel)
        fileModel = r.fileModel; count = r.count; mechanics = r.mechanics
        phase = r.ok ? "done" : "failed"
    }
    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) { phase = "idle" }
}

/// Shares the debug file with a subject line, so a tester who picks Mail gets
/// "LDRC debug — RAW420 MCM — 0.9.816" rather than an untitled attachment.
/// A bare URL in the share sheet carries no subject at all.
final class DebugShareItem: NSObject, UIActivityItemSource {
    private let file: URL
    private let subject: String
    init(file: URL, subject: String) { self.file = file; self.subject = subject }

    func activityViewControllerPlaceholderItem(_ c: UIActivityViewController) -> Any { file }
    func activityViewController(_ c: UIActivityViewController, itemForActivityType t: UIActivity.ActivityType?) -> Any? { file }
    func activityViewController(_ c: UIActivityViewController, subjectForActivityType t: UIActivity.ActivityType?) -> String { subject }
}
