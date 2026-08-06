// LockDownRadioControl — RXV2App  ::  SessionCache.swift
//
// The armchair review (Malcolm's lodge idea, 2026-08-04): while connected,
// every successful read the receiver answers is teed in here — the flight
// list, each flight viewed, live state, the Rotorflight settings pages'
// MSP reads. After everything is switched off, "Review last session" serves
// this recording to the very same bundled pages, so the last model's data
// and settings can be inspected with the receiver asleep in its case.
//
// Persistence: one JSON file in Documents; survives app restarts. A new
// connection starts a fresh recording the moment a different receiver name
// appears (same receiver = the session keeps accumulating, so a battery
// swap doesn't wipe the morning's flights from the phone).

import Foundation

final class SessionCache {
    static let shared = SessionCache()

    struct Entry: Codable {
        let type: String
        let body: Data
    }

    private var entries: [String: Entry] = [:]   // "pathAndQuery" → response
    private(set) var modelName: String = ""
    private(set) var savedAt: Date?

    // Per-model session files (Malcolm 2026-08-04: connecting another model
    // must never erase this one's recording): session-<model>.json each.
    private static var docs: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }
    private static func sessionURL(for model: String) -> URL {
        let safe = model.isEmpty ? "last"
            : String(model.map { $0.isLetter || $0.isNumber ? $0 : "_" })
        return docs.appendingPathComponent("session-\(safe).json")
    }
    private var fileURL: URL { Self.sessionURL(for: modelName) }

    private struct FileShape: Codable {
        var model: String
        var savedAt: Date
        var entries: [String: Entry]
    }

    /// All saved sessions, newest first — one per model.
    static func savedSessions() -> [(model: String, savedAt: Date)] {
        let files = (try? FileManager.default.contentsOfDirectory(
            at: docs, includingPropertiesForKeys: nil)) ?? []
        var out: [(String, Date)] = []
        for f in files where f.lastPathComponent.hasPrefix("session-") {
            if let d = try? Data(contentsOf: f),
               let s = try? JSONDecoder().decode(FileShape.self, from: d),
               !s.entries.isEmpty {
                out.append((s.model, s.savedAt))
            }
        }
        return out.sorted { $0.1 > $1.1 }
    }

    /// Load a saved model's recording as the active one (for review).
    func activate(model: String) {
        guard model != modelName else { return }
        saveNow()   // persist whatever is in memory first
        entries = [:]
        modelName = model
        savedAt = nil
        if let d = try? Data(contentsOf: Self.sessionURL(for: model)),
           let s = try? JSONDecoder().decode(FileShape.self, from: d) {
            entries = s.entries
            savedAt = s.savedAt
        }
    }

    private var saveScheduled = false

    private init() { load() }

    var available: Bool { !entries.isEmpty }

    // MARK: bank-aware keys (Malcolm 2026-08-04: "the PID values fail to
    // differ by bank"). Rotorflight keeps 4 PID-side banks (fn=210, byte
    // 0-3) and 4 rate banks (fn=210, byte 0x80|idx); the reads 112/94/148
    // follow the PID bank and 111 the rate bank, so the cache must key
    // those reads by the bank that was selected when they were made.
    private(set) var pidBank = 0
    private(set) var rateBank = 0

    /// Every fn=210 select that passes the app — live, replay or prefetch —
    /// lands here so the cache always knows which bank a read belongs to.
    func noteBankSelect(dataHex: String) {
        guard let b = Int(dataHex.prefix(2), radix: 16) else { return }
        if b & 0x80 != 0 { rateBank = b & 0x7f } else { pidBank = b }
    }

    private static let pidBankFns: Set<String> = ["112", "94", "148"]

    private func keyFor(_ pathAndQuery: String) -> String {
        guard pathAndQuery.hasPrefix("/api/msp?"), !pathAndQuery.contains("data=") else {
            return pathAndQuery
        }
        let q = String(pathAndQuery.dropFirst("/api/msp?".count))
        let fn = q.split(separator: "&")
            .first(where: { $0.hasPrefix("fn=") })?.dropFirst(3) ?? ""
        if Self.pidBankFns.contains(String(fn)) { return pathAndQuery + "&bank=\(pidBank)" }
        if fn == "111" { return pathAndQuery + "&bank=\(rateBank)" }
        return pathAndQuery
    }

    /// Human label for the review button: "RAW420MCM — 13:05" style.
    var label: String {
        let name = modelName.isEmpty ? "last receiver" : modelName
        guard let at = savedAt else { return name }
        let fmt = DateFormatter()
        fmt.dateStyle = .none
        fmt.timeStyle = .short
        return "\(name) — \(fmt.string(from: at))"
    }

    /// Should this request be recorded / replayed? Reads only: /api/* GETs,
    /// except MSP WRITES (an msp call with a data= payload changes the FC —
    /// replaying its success echo would fake a save).
    static func cacheable(path: String, query: String?) -> Bool {
        guard path.hasPrefix("/api/") else { return false }
        if path == "/api/msp", let q = query, q.contains("data=") { return false }
        if path == "/api/firmware/check" { return false }   // no update offers offline
        return true
    }

    func record(pathAndQuery: String, path: String, type: String, body: Data) {
        entries[keyFor(pathAndQuery)] = Entry(type: type, body: body)
        if path == "/api/state.json",
           let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
           let info = obj["info"] as? [String: Any],
           let name = info["name"] as? String, !name.isEmpty {
            if name != modelName && !modelName.isEmpty {
                // Different receiver: park the old model's recording in its
                // own file and RESUME the new model's (never a chimera, and
                // never an erasure — Malcolm 2026-08-04).
                let keep = entries[keyFor(pathAndQuery)]
                saveNow()
                entries = [:]
                modelName = name
                if let d = try? Data(contentsOf: fileURL),
                   let s = try? JSONDecoder().decode(FileShape.self, from: d) {
                    entries = s.entries
                }
                if let keep { entries[keyFor(pathAndQuery)] = keep }
            }
            modelName = name
        }
        savedAt = Date()
        scheduleSave()
    }

    func lookup(pathAndQuery: String) -> Entry? { entries[keyFor(pathAndQuery)] }

    // MARK: persistence (debounced — recording fires on every poll tick)

    private func scheduleSave() {
        guard !saveScheduled else { return }
        saveScheduled = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self else { return }
            self.saveScheduled = false
            self.saveNow()
        }
    }

    private func saveNow() {
        guard let at = savedAt else { return }
        let shape = FileShape(model: modelName, savedAt: at, entries: entries)
        if let data = try? JSONEncoder().encode(shape) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }

    private func load() {
        // One-time migration: the old single lastSession.json becomes that
        // model's own session file.
        let legacy = Self.docs.appendingPathComponent("lastSession.json")
        if let data = try? Data(contentsOf: legacy),
           let shape = try? JSONDecoder().decode(FileShape.self, from: data) {
            try? data.write(to: Self.sessionURL(for: shape.model), options: .atomic)
            try? FileManager.default.removeItem(at: legacy)
        }
        // Wake up with the newest model's session active.
        guard let newest = Self.savedSessions().first,
              let data = try? Data(contentsOf: Self.sessionURL(for: newest.model)),
              let shape = try? JSONDecoder().decode(FileShape.self, from: data)
        else { return }
        entries = shape.entries
        modelName = shape.model
        savedAt = shape.savedAt
    }
}

// MARK: - Offline Rotorflight edits (Malcolm 2026-08-04, refinement 2)
//
// In review mode the tuning pages may SAVE. The write is captured here (and
// the cached read image updated so the page's own verification passes) — then
// on the next connection to the SAME model the user chooses: send the edits
// to the model, or discard them and keep what the model already has.

extension SessionCache {
    static let writeToRead: [Int: Int] = [204: 111, 202: 112, 95: 94, 143: 142, 149: 148]
    static let writeLabels: [Int: String] = [204: "rates", 202: "PIDs", 95: "advanced PIDs",
                                             143: "governor (global)", 149: "governor profile"]

    struct PendingEdit: Codable {
        let fn: Int
        let hex: String
        let label: String
        // fn=210 select byte to send BEFORE this write (0x80|idx for rates),
        // so each edit lands in the bank it was made in. nil = bankless
        // (governor global). Optional so pre-bank recordings still decode.
        let bank: Int?
    }

    private static var pendingKey: String { "pendingEdits.json" }
    private static var pendingURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(pendingKey)
    }
    private struct PendingShape: Codable { var model: String; var edits: [PendingEdit] }

    static func loadPending() -> (model: String, edits: [PendingEdit]) {
        guard let d = try? Data(contentsOf: pendingURL),
              let s = try? JSONDecoder().decode(PendingShape.self, from: d)
        else { return ("", []) }
        return (s.model, s.edits)
    }

    static func savePending(model: String, edits: [PendingEdit]) {
        if edits.isEmpty { try? FileManager.default.removeItem(at: pendingURL); return }
        if let d = try? JSONEncoder().encode(PendingShape(model: model, edits: edits)) {
            try? d.write(to: pendingURL, options: .atomic)
        }
    }

    /// Capture an offline MSP write: remember it for the reconnect offer, and
    /// update the cached READ so the page's own read-back verification passes.
    /// Returns true when the write is a supported offline edit.
    func captureOfflineWrite(fn: Int, dataHex: String) -> Bool {
        guard let readFn = Self.writeToRead[fn] else { return false }
        // Which bank does this edit belong to? Rates follow the rate bank,
        // gov global has none, everything else follows the PID-side bank.
        let bank: Int? = fn == 143 ? nil : (fn == 204 ? 0x80 | rateBank : pidBank)
        var label = Self.writeLabels[fn] ?? "settings"
        if let b = bank { label += " (bank \((b & 0x7f) + 1))" }
        var (model, edits) = Self.loadPending()
        if model != modelName { edits = [] }               // stale edits for another model
        edits.removeAll { $0.fn == fn && $0.bank == bank } // newest edit of a kind+bank wins
        edits.append(Self.PendingEdit(fn: fn, hex: dataHex, label: label, bank: bank))
        Self.savePending(model: modelName, edits: edits)
        // The pages read back exactly what they wrote (symmetric MSP layouts).
        record(pathAndQuery: "/api/msp?fn=\(readFn)", path: "/api/msp",
               type: "text/plain", body: Data(dataHex.uppercased().utf8))
        return true
    }
}

// MARK: - Restore-from-recording (Malcolm 2026-08-06)
//
// The confused pilot's parachute: the recording holds every bank's tuning
// reads in exactly the byte layout the SET commands accept, so the whole
// lot can be written back — even when no Rotorflight backup was ever made.

extension SessionCache {
    struct RestoreItem {
        let selectByte: Int?   // fn=210 payload to send first (nil = bankless)
        let writeFn: Int
        let readFn: Int        // for post-write verification
        let hex: String
        let label: String      // named in the UI if it fails to verify
    }

    // The rolling recording tees EVERY read — including the read-backs of
    // the very edits a confused pilot wants to undo (Malcolm's closed-loop
    // test caught this: the restore faithfully re-wrote the random edits).
    // The parachute therefore restores from a FROZEN restore point, written
    // only when a full TX-off sweep completes — at connection (before any
    // editing) and on each explicit "Save session to phone".
    private static func restoreURL(for model: String) -> URL {
        let safe = model.isEmpty ? "last"
            : String(model.map { $0.isLetter || $0.isNumber ? $0 : "_" })
        return docs.appendingPathComponent("restore-\(safe).json")
    }
    private struct RestoreShape: Codable {
        var model: String
        var savedAt: Date
        var entries: [String: Entry]
    }

    private static let restoreKeyPrefixes =
        ["/api/msp?fn=112&bank=", "/api/msp?fn=94&bank=",
         "/api/msp?fn=148&bank=", "/api/msp?fn=111&bank="]

    /// Freeze the tuning reads currently in the rolling cache.
    func snapshotRestorePoint() {
        var keep: [String: Entry] = [:]
        for (k, v) in entries {
            if Self.restoreKeyPrefixes.contains(where: { k.hasPrefix($0) }) || k == "/api/msp?fn=142" {
                keep[k] = v
            }
        }
        guard !keep.isEmpty else { return }
        let shape = RestoreShape(model: modelName, savedAt: Date(), entries: keep)
        if let d = try? JSONEncoder().encode(shape) {
            try? d.write(to: Self.restoreURL(for: modelName), options: .atomic)
        }
    }

    /// When was the current model's restore point frozen? nil = none.
    func restorePointDate() -> Date? {
        guard let d = try? Data(contentsOf: Self.restoreURL(for: modelName)),
              let s = try? JSONDecoder().decode(RestoreShape.self, from: d) else { return nil }
        return s.savedAt
    }

    /// Everything restorable from the FROZEN restore point, in write order.
    func restoreItems() -> [RestoreItem] {
        guard let d = try? Data(contentsOf: Self.restoreURL(for: modelName)),
              let shape = try? JSONDecoder().decode(RestoreShape.self, from: d)
        else { return [] }
        let frozen = shape.entries
        var out: [RestoreItem] = []
        func hexAt(_ key: String) -> String? {
            guard let e = frozen[key],
                  let s = String(data: e.body, encoding: .utf8),
                  s.count >= 2, s.allSatisfy({ $0.isHexDigit }) else { return nil }
            return s.uppercased()
        }
        for b in 0...3 {
            if let h = hexAt("/api/msp?fn=112&bank=\(b)") { out.append(RestoreItem(selectByte: b, writeFn: 202, readFn: 112, hex: h, label: "PIDs bank \(b + 1)")) }
            if let h = hexAt("/api/msp?fn=94&bank=\(b)")  { out.append(RestoreItem(selectByte: b, writeFn: 95,  readFn: 94,  hex: h, label: "advanced PIDs bank \(b + 1)")) }
            if let h = hexAt("/api/msp?fn=148&bank=\(b)") { out.append(RestoreItem(selectByte: b, writeFn: 149, readFn: 148, hex: h, label: "governor profile bank \(b + 1)")) }
        }
        for r in 0...3 {
            if let h = hexAt("/api/msp?fn=111&bank=\(r)") { out.append(RestoreItem(selectByte: 0x80 | r, writeFn: 204, readFn: 111, hex: h, label: "rates bank \(r + 1)")) }
        }
        if let h = hexAt("/api/msp?fn=142") { out.append(RestoreItem(selectByte: nil, writeFn: 143, readFn: 142, hex: h, label: "governor global")) }
        return out
    }
}

final class RestoreRunner {
    private static var running = false
    static var phase = "idle"      // idle | running | done
    static var done = 0
    static var total = 0
    static var failures = 0
    static var failedLabels: [String] = []
    static var progressJSON: Data {
        let names = failedLabels.map { "\"\($0)\"" }.joined(separator: ",")
        return Data("{\"phase\":\"\(phase)\",\"done\":\(done),\"total\":\(total),\"failures\":\(failures),\"failed\":[\(names)]}".utf8)
    }

    static func run(link: BleLink) {
        guard !running else { return }
        running = true
        phase = "running"; done = 0; failures = 0; failedLabels = []
        let items = SessionCache.shared.restoreItems()
        total = items.count + 1   // + EEPROM save

        func req(_ p: String) -> (ok: Bool, body: String) {
            let sem = DispatchSemaphore(value: 0)
            var ok = false, body = ""
            DispatchQueue.main.async {
                // The restore's bank selects must never interleave with the sweep's.
                SessionPrefetcher.lastPageMspMs = Date().timeIntervalSince1970 * 1000
                link.request(method: "GET", path: p, headers: [:], body: nil) { result in
                    if case .success(let resp) = result, resp.code == 0 || resp.code == 200 {
                        ok = true
                        body = String(data: resp.body, encoding: .utf8) ?? ""
                    }
                    sem.signal()
                }
            }
            _ = sem.wait(timeout: .now() + 20)
            Thread.sleep(forTimeInterval: 0.25)
            return (ok, body)
        }

        DispatchQueue.global(qos: .userInitiated).async {
            // Note the FC's own banks first — the walk ends on bank 3, and
            // the EEPROM save would PERSIST that as the boot profile
            // (Malcolm's re-test: everything identical except 'profile 3').
            var origPid = 0, origRate = 0
            let st = req("/api/msp?fn=101").body
            if st.count >= 54,
               let p = Int(st.dropFirst(48).prefix(2), radix: 16),
               let r = Int(st.dropFirst(52).prefix(2), radix: 16) {
                origPid = p; origRate = r
            }
            var wroteGov = false
            for it in items {
                // TWO attempts — a single radio hiccup among ~50 sequential
                // MSP ops must not fail the parachute (Malcolm 2026-08-06:
                // "One was not verified I see").
                var itemOk = false
                for attempt in 1...2 {
                    var ok = true
                    if let b = it.selectByte {
                        ok = req("/api/msp?fn=210&data=" + String(format: "%02X", b)).ok
                    }
                    if ok { ok = req("/api/msp?fn=\(it.writeFn)&data=\(it.hex)").ok }
                    if ok {
                        // Verify: read back, compare (reply may be longer — prefix).
                        let back = req("/api/msp?fn=\(it.readFn)").body.uppercased()
                        ok = back.hasPrefix(it.hex) || it.hex.hasPrefix(back) && !back.isEmpty
                    }
                    if ok { itemOk = true; break }
                    if attempt == 1 { Thread.sleep(forTimeInterval: 0.6) }
                }
                if !itemOk { failures += 1; failedLabels.append(it.label) }
                if it.writeFn == 143 && itemOk { wroteGov = true }
                done += 1
            }
            // Put the FC back on its own banks BEFORE the EEPROM save.
            _ = req("/api/msp?fn=210&data=" + String(format: "%02X", origPid))
            _ = req("/api/msp?fn=210&data=" + String(format: "%02X", 0x80 | origRate))
            _ = req("/api/msp?fn=250")                     // save to EEPROM
            if wroteGov { _ = req("/api/msp?fn=68") }      // gov config needs FC reboot
            done += 1
            phase = "done"
            running = false
        }
    }
}

// MARK: - Whole-session prefetch (Malcolm 2026-08-04, refinement 1)
//
// Record EVERYTHING, not just what the user happened to view: shortly after
// connecting, walk the flight list and the tuning reads in the background,
// paced gently so the user's own page loads keep priority on the one radio.

final class SessionPrefetcher {
    private static var running = false
    // A tuning page mid-read must never interleave with the sweep's bank
    // selects — the page would show ANOTHER bank's values (Malcolm
    // 2026-08-06: "occasionally it reads the wrong values"). The scheme
    // handler stamps this on every page-originated MSP call; the sweep's
    // MSP section waits for a 10 s quiet gap (bounded, then skips).
    static var lastPageMspMs: Double = 0
    private static func pageMspQuiet() -> Bool {
        Date().timeIntervalSince1970 * 1000 - lastPageMspMs > 10_000
    }
    // Progress for the "Save session to phone" button (Malcolm 2026-08-04):
    // explicit and verifiable — press save, watch the count, read "done".
    static var phase = "idle"      // idle | running | done
    static var done = 0
    static var total = 0
    static var progressJSON: Data {
        Data("{\"phase\":\"\(phase)\",\"done\":\(done),\"total\":\(total)}".utf8)
    }

    static func run(link: BleLink, fast: Bool = false) {
        // Re-run on EVERY (re)connection — an OTA reboot or a walk-away cut
        // the first attempt short (Malcolm 2026-08-04: "could not view this
        // morning's data"); recording is idempotent, so repeats are free.
        guard !running else { return }
        running = true
        phase = "running"; done = 0; total = 3
        let pace = fast ? 0.15 : 0.4

        // Blocking GET on this background thread; tees into the recording.
        func req(_ p: String) -> Data? {
            let sem = DispatchSemaphore(value: 0)
            var body: Data?
            DispatchQueue.main.async {
                link.request(method: "GET", path: p, headers: [:], body: nil) { result in
                    if case .success(let resp) = result, resp.code == 0 || resp.code == 200 {
                        body = resp.body
                        let bare = p.split(separator: "?").first.map(String.init) ?? p
                        let q = p.contains("?") ? String(p.split(separator: "?")[1]) : nil
                        if SessionCache.cacheable(path: bare, query: q) {
                            SessionCache.shared.record(pathAndQuery: p, path: bare,
                                                       type: resp.contentType, body: resp.body)
                        }
                    }
                    sem.signal()
                }
            }
            _ = sem.wait(timeout: .now() + 20)
            done += 1
            Thread.sleep(forTimeInterval: pace)
            return body
        }
        func selectBank(_ byte: Int) {
            let hex = String(format: "%02X", byte)
            SessionCache.shared.noteBankSelect(dataHex: hex)
            _ = req("/api/msp?fn=210&data=\(hex)")
        }

        DispatchQueue.global(qos: .utility).async {
            Thread.sleep(forTimeInterval: fast ? 0.1 : 6)
            var flightPaths: [String] = []
            var txLive = false
            if let st = req("/api/state.json"),
               let obj = (try? JSONSerialization.jsonObject(with: st)) as? [String: Any] {
                // last_pkt_ms is an AGE in ms (-1 = no TX heard yet), not a
                // timestamp — the sweep must NEVER run when this is small.
                let lastPkt = ((obj["rf"] as? [String: Any])?["last_pkt_ms"] as? NSNumber)?.int64Value ?? -1
                txLive = lastPkt >= 0 && lastPkt < 3000
            }
            if let fl = req("/api/flights.json"),
               let arr = (try? JSONSerialization.jsonObject(with: fl)) as? [[String: Any]] {
                for f in arr {
                    if let i = f["i"] as? Int, i > 0 { flightPaths.append("/api/flightlog.json?f=\(i)") }
                }
            }
            _ = req("/api/events.json")
            // Rotorflight reads — banked (Malcolm 2026-08-04: each of the 4
            // PID-side banks and 4 rate banks is its own set of values).
            // ONLY with the transmitter off: never switch a bank under a
            // live TX. The FC's current banks come from MSP_STATUS (fn=101,
            // bytes 24/26 — verified on the RAW420 by switching and reading
            // back) and are restored exactly after the sweep.
            // A foolish-user guard (Malcolm 2026-08-04): if the transmitter
            // comes ON mid-sweep, stop switching banks IMMEDIATELY and put
            // the FC back on its own banks — never fly on a sweep leftover.
            func txAppeared() -> Bool {
                guard let st = req("/api/state.json"),
                      let obj = (try? JSONSerialization.jsonObject(with: st)) as? [String: Any],
                      let lastPkt = ((obj["rf"] as? [String: Any])?["last_pkt_ms"] as? NSNumber)?.int64Value
                else { return false }
                return lastPkt >= 0 && lastPkt < 3000
            }
            // Yield to the user's tuning pages: wait (up to 2 min) for a
            // 10 s gap in page MSP traffic before ANY bank switching; if the
            // user keeps reading, skip the MSP sweep entirely this run.
            var waited = 0.0
            while !pageMspQuiet() && waited < 120 { Thread.sleep(forTimeInterval: 2); waited += 2 }
            var sweepOK = false
            if !txLive, pageMspQuiet(), let st = req("/api/msp?fn=101"),
               let hex = String(data: st, encoding: .utf8), hex.count >= 54,
               let origPid = Int(hex.dropFirst(48).prefix(2), radix: 16),
               let origRate = Int(hex.dropFirst(52).prefix(2), radix: 16) {
                total += 1 + 4 * 5 + 4 * 3 + 2   // 142 + pid sweep + rate sweep + restores
                _ = req("/api/msp?fn=142")       // governor global — bankless
                var aborted = false
                for b in 0...3 {
                    if txAppeared() { aborted = true; break }
                    selectBank(b)
                    _ = req("/api/msp?fn=112")
                    _ = req("/api/msp?fn=94")
                    _ = req("/api/msp?fn=148")
                }
                if !aborted {
                    for r in 0...3 {
                        if txAppeared() { aborted = true; break }
                        selectBank(0x80 | r)
                        _ = req("/api/msp?fn=111")
                    }
                }
                selectBank(origPid)              // put the FC back exactly —
                selectBank(0x80 | origRate)      // always, aborted or not
                sweepOK = !aborted
            }
            // Full sweep completed → freeze the restore point (the rolling
            // cache keeps updating; this copy never follows the edits).
            if sweepOK { SessionCache.shared.snapshotRestorePoint() }
            total += flightPaths.count
            for p in flightPaths { _ = req(p) }
            running = false
            phase = "done"
        }
    }
}
