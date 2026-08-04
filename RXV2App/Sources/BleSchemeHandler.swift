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
import CryptoKit

// md5 hex of a downloaded image — used for the receiver-side fingerprint skip.
func md5Hex(_ d: Data) -> String {
    Insecure.MD5.hash(data: d).map { String(format: "%02x", $0) }.joined()
}

final class BleSchemeHandler: NSObject, WKURLSchemeHandler {
    private let link: BleLink
    private let demo: Bool
    private let replay: Bool   // "Review last session" — serve SessionCache, never touch BLE
    private var live = Set<ObjectIdentifier>()
    private lazy var ota = BleOta(link: link)

    init(link: BleLink, demo: Bool = false, replay: Bool = false) {
        self.link = link
        self.demo = demo
        self.replay = replay
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

        // 0) BLE OTA push — handled by the APP (phone downloads on WiFi/5G,
        //    then streams the images over Bluetooth). Never reaches the radio.
        if path == "/app/bleota/start" {
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems
            let fw = items?.first(where: { $0.name == "fw" })?.value
            let fs = items?.first(where: { $0.name == "fs" })?.value
            let ok = (fw != nil && !demo && !replay)
            if ok { ota.start(fw: fw!, fs: fs) }
            deliver(task, url: url, code: 200, type: "application/json",
                    body: Data("{\"ok\":\(ok)}".utf8))
            return
        }
        if path == "/app/snapshot/start" {
            let ok = !demo && !replay
            if ok { SessionPrefetcher.run(link: link, fast: true) }
            deliver(task, url: url, code: 200, type: "application/json",
                    body: Data("{\"ok\":\(ok)\(ok ? "" : ",\"error\":\"connect to the receiver first\"")}".utf8))
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
                data = Data("<script src=\"/demo-shim.js\"></script>".utf8) + data
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
                if let hex = dataHex, !hex.isEmpty {
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
    private var running = false

    init(link: BleLink) { self.link = link }

    var progressJSON: Data {
        lock.lock(); defer { lock.unlock() }
        let esc = msg.replacingOccurrences(of: "\\", with: "\\\\")
                     .replacingOccurrences(of: "\"", with: "\\\"")
        return Data("{\"phase\":\"\(phase)\",\"msg\":\"\(esc)\",\"sent\":\(sent),\"total\":\(total)}".utf8)
    }

    func start(fw: String, fs: String?) {
        lock.lock()
        if running { lock.unlock(); return }
        running = true
        phase = "download"; msg = "Downloading with the phone's internet…"
        sent = 0; total = 0
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
        defer { lock.lock(); running = false; lock.unlock() }
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
            if let f = fs,
               let st = try? reqSync("GET", "/api/state.json"),
               let obj = (try? JSONSerialization.jsonObject(with: st.body)) as? [String: Any],
               let info = obj["info"] as? [String: Any],
               let have = info["fs_md5"] as? String, have.count == 32,
               md5Hex(f) == have.lowercased() {
                fs = nil
                set("download", "Web pages unchanged — keeping flights…")
            }
            lock.lock(); total = Int64(fw.count + (fs?.count ?? 0)); lock.unlock()
            // one clean restart per image: /begin resets the receiver side,
            // so a transfer that died mid-way gets a second, fresh attempt
            func sendImage(_ type: String, _ bytes: Data, _ base: Int64, _ label: String) throws {
                do { try streamImage(type: type, bytes: bytes, base: base) } catch {
                    if error.localizedDescription.contains("too old") { throw error }
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
            // flag) and the link layer auto-reconnects for 90 s — poll until
            // it answers, then report the version it now runs.
            Thread.sleep(forTimeInterval: 4)
            var newVer = ""
            let deadline = Date().addingTimeInterval(120)
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

    private func download(_ url: String) throws -> Data {
        guard let u = URL(string: url) else { throw fault("bad URL \(url)") }
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
            throw fault("begin(\(type)): \(String(data: begin.body, encoding: .utf8) ?? "")")
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
