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

    /// Delete a saved model's recording + its restore point (Malcolm
    /// 2026-08-22: "otherwise they accumulate rather excessively!").
    /// Swipe-to-delete on the scanner list calls this.
    static func deleteSession(model: String) {
        try? FileManager.default.removeItem(at: sessionURL(for: model))
        try? FileManager.default.removeItem(at: restoreURL(for: model))
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

    private static let pidBankFns: Set<String> = ["112", "94", "148", "146"]

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
        if path == "/api/msp", let q = query, q.contains("data=") {
            // fn=174 (GET_MIXER_INPUT) is the one READ whose parameter — the
            // input index — rides in data=. Without this exception the
            // Travel-extents reads were never recorded, so backup/restore
            // silently forgot the mixer (Malcolm 2026-08-15, 6 am in bed).
            if !q.contains("fn=174") { return false }
        }
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
        let hex: String        // the WRITE payload
        let label: String      // named in the UI if it fails to verify
        // Mixer inputs (171/174): the read needs the input index as data=,
        // and the write payload carries a leading index byte the read-back
        // won't echo — so the verify compares against verifyHex instead.
        var readData: String? = nil
        var verifyHex: String? = nil
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
        // true = the pilot pressed "Back up" (or imported a file): STICKY —
        // the automatic freeze at connection must never overwrite it
        // (review 2026-09-04: it did, so a deliberate backup lived only
        // until the next battery). Optional so older files still decode.
        var explicit: Bool? = nil
    }

    private static let restoreKeyPrefixes =
        ["/api/msp?fn=112&bank=", "/api/msp?fn=94&bank=",
         "/api/msp?fn=148&bank=", "/api/msp?fn=146&bank=", "/api/msp?fn=111&bank=",
         "/api/msp?fn=174&data="]   // mixer inputs (Travel extents)

    /// The mechanical items — servo centres/travel (fn 120) and the mixer's
    /// limits, trims and input travel (42, 174). A backup from ANOTHER model
    /// leaves these out on import: they belong to that airframe's linkage.
    static let mechanicsKeyPrefixes = ["/api/msp?fn=120", "/api/msp?fn=42", "/api/msp?fn=174&data="]

    /// The FC's current banks from MSP_STATUS (fn=101): byte 23 = PID
    /// profile, byte 25 = rate profile, bytes 24/26 = the profile COUNTS
    /// (Rotorflight 4.6 — checked against the Goblin's own reply, where
    /// byte 24 reads 06). The earlier code read 24/26, i.e. the counts, so
    /// every "put the FC back on its own bank" selected bank 6 → RF clamps
    /// that to bank 1. nil when the reply doesn't make sense.
    static func fcBanks(statusHex: String) -> (pid: Int, rate: Int)? {
        let h = Array(statusHex.uppercased())
        guard h.count >= 54 else { return nil }
        func byte(_ i: Int) -> Int? { Int(String(h[(2 * i)..<(2 * i + 2)]), radix: 16) }
        guard let p = byte(23), let pc = byte(24), let r = byte(25), let rc = byte(26),
              pc > 0, pc <= 8, rc > 0, rc <= 8, p < pc, r < rc else { return nil }
        return (p, r)
    }

    /// Freeze the tuning reads currently in the rolling cache. `explicit` =
    /// the pilot's own "Back up" tap; an automatic (connection) freeze never
    /// replaces an explicit one. Returns false when nothing was written.
    @discardableResult
    func snapshotRestorePoint(explicit: Bool = false) -> Bool {
        if !explicit, restorePointIsExplicit() { return false }
        var keep: [String: Entry] = [:]
        for (k, v) in entries {
            if Self.restoreKeyPrefixes.contains(where: { k.hasPrefix($0) })
                || k == "/api/msp?fn=142" || k == "/api/msp?fn=42"
                || k == "/api/msp?fn=120" || k.hasPrefix("/app/declared/") {
                keep[k] = v
            }
        }
        guard !keep.isEmpty else { return false }
        let shape = RestoreShape(model: modelName, savedAt: Date(), entries: keep, explicit: explicit)
        guard let d = try? JSONEncoder().encode(shape) else { return false }
        do { try d.write(to: Self.restoreURL(for: modelName), options: .atomic) } catch { return false }
        return true
    }

    /// When was the current model's restore point frozen? nil = none.
    func restorePointDate() -> Date? {
        guard let d = try? Data(contentsOf: Self.restoreURL(for: modelName)),
              let s = try? JSONDecoder().decode(RestoreShape.self, from: d) else { return nil }
        return s.savedAt
    }

    /// Was the current restore point a deliberate backup (or an import)?
    func restorePointIsExplicit() -> Bool {
        guard let d = try? Data(contentsOf: Self.restoreURL(for: modelName)),
              let s = try? JSONDecoder().decode(RestoreShape.self, from: d) else { return false }
        return s.explicit ?? false
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
            if let h = hexAt("/api/msp?fn=146&bank=\(b)") { out.append(RestoreItem(selectByte: b, writeFn: 147, readFn: 146, hex: h, label: "rescue bank \(b + 1)")) }
        }
        for r in 0...3 {
            if let h = hexAt("/api/msp?fn=111&bank=\(r)") { out.append(RestoreItem(selectByte: 0x80 | r, writeFn: 204, readFn: 111, hex: h, label: "rates bank \(r + 1)")) }
        }
        if let h = hexAt("/api/msp?fn=142") { out.append(RestoreItem(selectByte: nil, writeFn: 143, readFn: 142, hex: h, label: "governor global")) }
        // Mixer (Travel extents, bankless): config block, then each input —
        // 171 takes ONE input per frame (index byte + rate/min/max).
        if let h = hexAt("/api/msp?fn=42") { out.append(RestoreItem(selectByte: nil, writeFn: 43, readFn: 42, hex: h, label: "mixer limits & trims")) }
        let axisNames = [1: "roll", 2: "pitch", 3: "yaw", 4: "collective"]
        for i in [1, 2, 3, 4] {
            let key = String(format: "%02X", i)
            if let h = hexAt("/api/msp?fn=174&data=\(key)") {
                out.append(RestoreItem(selectByte: nil, writeFn: 171, readFn: 174,
                                       hex: key + h, label: "mixer input — \(axisNames[i]!)",
                                       readData: key, verifyHex: h))
            }
        }
        // Servos (bankless): the stored fn-120 image is count(1B) + 16 B per
        // servo; fn 212 writes ONE servo (index byte + its 16 B). Verify is
        // structural for all but the last servo (the fn-120 read-back mixes
        // written and not-yet-written servos mid-restore), then the LAST
        // item compares the whole image byte-for-byte.
        if let full = hexAt("/api/msp?fn=120"), full.count >= 2,
           let count = Int(full.prefix(2), radix: 16), count > 0,
           full.count >= 2 + count * 32 {
            let roles = ["swash 1", "swash 2", "swash 3", "TAIL", "5", "6", "7", "8"]
            for i in 0..<count {
                let start = full.index(full.startIndex, offsetBy: 2 + i * 32)
                let end = full.index(start, offsetBy: 32)
                let slice = String(full[start..<end])
                let idx = String(format: "%02X", i)
                let last = (i == count - 1)
                out.append(RestoreItem(selectByte: nil, writeFn: 212, readFn: 120,
                                       hex: idx + slice,
                                       label: "servo \(i + 1) (\(roles[min(i, 7)]))",
                                       readData: nil,
                                       verifyHex: last ? full : String(full.prefix(2))))
            }
        }
        // Declared items (Malcolm 2026-08-30): settings the FC cannot read
        // back over the radio — the bank/rates selector adjustment ranges
        // (MSP 53, ~590-byte table vs the FC's 320-byte telemetry buffer).
        // Restored verbatim, readFn 0 = "no verify possible".
        for (k, e) in frozen where k.hasPrefix("/app/declared/adj") {
            guard let h = String(data: e.body, encoding: .utf8), h.count >= 4,
                  h.allSatisfy({ $0.isHexDigit }) else { continue }
            let label = k.hasSuffix("adj40") ? "bank selector switch"
                      : k.hasSuffix("adj41") ? "rates selector switch" : "declared \(k)"
            out.append(RestoreItem(selectByte: nil, writeFn: 53, readFn: 0, hex: h.uppercased(), label: label))
        }
        return out
    }

    // MARK: - Declared items, export & import (Malcolm 2026-08-30: "store in
    // our backup ALL the data, even though some of it had to be derived
    // locally — then restore to another phone, or email it to a friend").

    /// Record a write-only setting (e.g. adjustment range slot 40) so backup
    /// and restore carry it. Patched straight into the frozen restore point
    /// too, so a declaration made AFTER the sweep is never lost.
    func declare(key: String, hex: String) {
        let k = "/app/declared/" + key
        let e = Entry(type: "text/plain", body: Data(hex.utf8))
        entries[k] = e
        savedAt = Date()
        if let d = try? JSONEncoder().encode(FileShape(model: modelName, savedAt: Date(), entries: entries)) {
            try? d.write(to: fileURL, options: .atomic)
        }
        var shape = (try? Data(contentsOf: Self.restoreURL(for: modelName)))
            .flatMap { try? JSONDecoder().decode(RestoreShape.self, from: $0) }
            ?? RestoreShape(model: modelName, savedAt: Date(), entries: [:])
        shape.entries[k] = e
        if let d = try? JSONEncoder().encode(shape) {
            try? d.write(to: Self.restoreURL(for: modelName), options: .atomic)
        }
    }

    /// key → hex of every declared item known for this model.
    func declared() -> [String: String] {
        var out: [String: String] = [:]
        if let d = try? Data(contentsOf: Self.restoreURL(for: modelName)),
           let shape = try? JSONDecoder().decode(RestoreShape.self, from: d) {
            for (k, e) in shape.entries where k.hasPrefix("/app/declared/") {
                out[String(k.dropFirst("/app/declared/".count))] = String(data: e.body, encoding: .utf8) ?? ""
            }
        }
        for (k, e) in entries where k.hasPrefix("/app/declared/") {
            out[String(k.dropFirst("/app/declared/".count))] = String(data: e.body, encoding: .utf8) ?? ""
        }
        return out
    }

    /// Portable backup file (same shape on Android): the frozen restore point.
    func exportRestoreJSON() -> Data? {
        guard let d = try? Data(contentsOf: Self.restoreURL(for: modelName)),
              let shape = try? JSONDecoder().decode(RestoreShape.self, from: d),
              !shape.entries.isEmpty else { return nil }
        var es: [String: Any] = [:]
        for (k, e) in shape.entries { es[k] = ["type": e.type, "b64": e.body.base64EncodedString()] }
        let root: [String: Any] = ["format": "rxv2-backup-1", "model": shape.model,
                                   "savedAtMs": Int(shape.savedAt.timeIntervalSince1970 * 1000),
                                   "entries": es]
        return try? JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
    }

    /// Adopt a backup file as the restore point for `model` (the connected
    /// receiver). A file from ANOTHER model (different name) comes without
    /// its mechanics — servo centres/travel and mixer limits stay this
    /// airframe's own, as the Import dialog promises. Returns the file's own
    /// model name, the item count and whether mechanics were kept.
    func importRestore(json: Data, forModel model: String) -> (ok: Bool, fileModel: String, count: Int, mechanics: Bool) {
        guard let root = try? JSONSerialization.jsonObject(with: json) as? [String: Any],
              (root["format"] as? String) == "rxv2-backup-1",
              let es = root["entries"] as? [String: [String: Any]], !es.isEmpty else { return (false, "", 0, false) }
        let fileModel = (root["model"] as? String) ?? ""
        let sameModel = fileModel.trimmingCharacters(in: .whitespaces).lowercased()
                     == model.trimmingCharacters(in: .whitespaces).lowercased()
        var entries: [String: Entry] = [:]
        for (k, v) in es {
            if !sameModel, Self.mechanicsKeyPrefixes.contains(where: { k.hasPrefix($0) }) { continue }
            guard let b64 = v["b64"] as? String, let body = Data(base64Encoded: b64) else { continue }
            entries[k] = Entry(type: (v["type"] as? String) ?? "text/plain", body: body)
        }
        guard !entries.isEmpty else { return (false, fileModel, 0, false) }
        let shape = RestoreShape(model: model, savedAt: Date(), entries: entries, explicit: true)
        guard let d = try? JSONEncoder().encode(shape) else { return (false, fileModel, 0, false) }
        do { try d.write(to: Self.restoreURL(for: model), options: .atomic) } catch { return (false, fileModel, 0, false) }
        return (true, fileModel, entries.count, sameModel)
    }
}

final class RestoreRunner {
    private static var running = false
    static var phase = "idle"      // idle | running | done
    static var done = 0
    static var total = 0
    static var failures = 0
    static var failedLabels: [String] = []
    static var error = ""          // non-empty = the run stopped early; the page shows it
    static var progressJSON: Data {
        let names = failedLabels.map { "\"\($0)\"" }.joined(separator: ",")
        let err = error.replacingOccurrences(of: "\"", with: "'")
        return Data("{\"phase\":\"\(phase)\",\"done\":\(done),\"total\":\(total),\"failures\":\(failures),\"failed\":[\(names)],\"error\":\"\(err)\"}".utf8)
    }

    static func run(link: BleLink) {
        guard !running else { return }
        running = true
        phase = "running"; done = 0; failures = 0; failedLabels = []; error = ""
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
        // The FC's banks right now (nil = MSP_STATUS unreadable).
        func fcBanks() -> (pid: Int, rate: Int)? { SessionCache.fcBanks(statusHex: req("/api/msp?fn=101").body) }
        // Is a transmitter talking to the receiver? (last_pkt_ms = AGE, -1 = never)
        func txLive() -> Bool {
            let st = req("/api/state.json").body
            guard let obj = try? JSONSerialization.jsonObject(with: Data(st.utf8)) as? [String: Any],
                  let age = ((obj["rf"] as? [String: Any])?["last_pkt_ms"] as? NSNumber)?.int64Value else { return false }
            return age >= 0 && age < 3000
        }

        DispatchQueue.global(qos: .userInitiated).async {
            // Note the FC's own banks first — the walk ends on bank 3, and
            // the EEPROM save would PERSIST that as the boot profile
            // (Malcolm's re-test: everything identical except 'profile 3').
            // Unreadable → nothing is written: without them we could neither
            // put the FC back nor tell which bank a write landed in.
            guard let orig = fcBanks() else {
                error = "could not read the flight controller's bank (MSP 101) — nothing was written"
                done = total; phase = "done"; running = false
                return
            }
            var wroteGov = false
            var curPid = orig.pid, curRate = orig.rate
            var stopped = false
            for it in items {
                if stopped { failures += 1; failedLabels.append(it.label); done += 1; continue }
                // TWO attempts — a single radio hiccup among ~50 sequential
                // MSP ops must not fail the parachute (Malcolm 2026-08-06:
                // "One was not verified I see").
                var itemOk = false
                for attempt in 1...2 {
                    var ok = true
                    // Skip selects that are already true — each one stalls
                    // the FC on a flash write (the swash twitch).
                    if let b = it.selectByte {
                        let isRate = (b & 0x80) != 0
                        let target = b & 0x7f
                        if (isRate ? curRate : curPid) != target {
                            ok = req("/api/msp?fn=210&data=" + String(format: "%02X", b)).ok
                            if ok { if isRate { curRate = target } else { curPid = target } }
                        }
                    }
                    if ok { ok = req("/api/msp?fn=\(it.writeFn)&data=\(it.hex)").ok }
                    if ok && it.readFn != 0 {      // readFn 0 = declared item, no read-back exists
                        // Verify: read back, compare (reply may be longer — prefix).
                        // Mixer inputs read with their index in data= and are
                        // compared against verifyHex (write payload minus the
                        // leading index byte the read never echoes).
                        let rq = "/api/msp?fn=\(it.readFn)" + (it.readData.map { "&data=\($0)" } ?? "")
                        let want = it.verifyHex ?? it.hex
                        let back = req(rq).body.uppercased()
                        ok = back.hasPrefix(want) || want.hasPrefix(back) && !back.isEmpty
                    }
                    // Banked item: the FC must STILL be on the bank we chose.
                    // A transmitter switched on mid-restore drags the FC onto
                    // its own switch position — the write (and its read-back!)
                    // would then land in that bank and "verify" perfectly.
                    if ok, let b = it.selectByte {
                        let isRate = (b & 0x80) != 0
                        if let now = fcBanks() {
                            curPid = now.pid; curRate = now.rate
                            if (isRate ? now.rate : now.pid) != (b & 0x7f) { ok = false }
                        } else { ok = false }
                        if !ok && txLive() {
                            error = "the transmitter came on — restore stopped (switch it off and run the restore again)"
                            stopped = true
                        }
                    }
                    if ok { itemOk = true; break }
                    if stopped || attempt == 2 { break }
                    Thread.sleep(forTimeInterval: 0.6)
                }
                if !itemOk { failures += 1; failedLabels.append(it.label) }
                if it.writeFn == 143 && itemOk { wroteGov = true }
                done += 1
            }
            // Put the FC back on its own banks BEFORE the EEPROM save — unless
            // a live transmitter now owns the bank switch.
            if !stopped {
                if curPid != orig.pid { _ = req("/api/msp?fn=210&data=" + String(format: "%02X", orig.pid)) }
                if curRate != orig.rate { _ = req("/api/msp?fn=210&data=" + String(format: "%02X", 0x80 | orig.rate)) }
            }
            // Save to EEPROM — verified: an unsaved restore evaporates at the
            // next power-up while the page said "restored".
            var saved = req("/api/msp?fn=250").ok
            if !saved { Thread.sleep(forTimeInterval: 0.6); saved = req("/api/msp?fn=250").ok }
            if !saved { failures += 1; failedLabels.append("save to flight controller memory (EEPROM) — run the restore again") }
            if wroteGov && saved { _ = req("/api/msp?fn=68") }      // gov config needs FC reboot
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
    // ok = this run completed the whole Rotorflight sweep with every read
    // answered, so the frozen restore point is fresh and complete. Anything
    // less says why in `error` (the page shows ⚠️ and keeps the old backup).
    static var ok = false
    static var error = ""
    static var progressJSON: Data {
        let err = error.replacingOccurrences(of: "\"", with: "'")
        return Data("{\"phase\":\"\(phase)\",\"done\":\(done),\"total\":\(total),\"ok\":\(ok),\"error\":\"\(err)\"}".utf8)
    }

    /// explicit = the pilot pressed "Back up" (or imported a file): the
    /// restore point it freezes is sticky — later automatic sweeps at
    /// connection never overwrite it (they still refresh the rolling cache).
    static func run(link: BleLink, fast: Bool = false, explicit: Bool = false) {
        // Re-run on EVERY (re)connection — an OTA reboot or a walk-away cut
        // the first attempt short (Malcolm 2026-08-04: "could not view this
        // morning's data"); recording is idempotent, so repeats are free.
        guard !running else { return }
        running = true
        phase = "running"; done = 0; total = 3; ok = false; error = ""
        let pace = fast ? 0.15 : 0.4
        var failures = 0      // MSP reads that never answered (after one retry)

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
        // A Rotorflight read the backup depends on: one retry, then it
        // counts as a failure — a missing answer must never let a stale
        // value from an earlier session pass as today's backup.
        func mspRead(_ p: String) {
            if req(p) != nil { return }
            Thread.sleep(forTimeInterval: 0.5)
            if req(p) == nil { failures += 1 }
        }
        func selectBank(_ byte: Int) {
            let hex = String(format: "%02X", byte)
            SessionCache.shared.noteBankSelect(dataHex: hex)
            _ = req("/api/msp?fn=210&data=\(hex)")
        }
        // The FC's banks now, from MSP_STATUS bytes 23/25 (nil = no answer).
        func fcBanks() -> (pid: Int, rate: Int)? {
            guard let st = req("/api/msp?fn=101"), let hex = String(data: st, encoding: .utf8) else { return nil }
            return SessionCache.fcBanks(statusHex: hex)
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
            _ = req("/api/events-prev.json")   // previous boot's persisted tail
            // Rotorflight reads — banked (Malcolm 2026-08-04: each of the 4
            // PID-side banks and 4 rate banks is its own set of values).
            // ONLY with the transmitter off: never switch a bank under a
            // live TX. The FC's current banks come from MSP_STATUS (fn=101,
            // bytes 23/25 = current PID / rate profile; 24/26 are the COUNTS
            // — the 2026-09-04 review found the old code reading those, so
            // every sweep parked the FC on bank 1 instead of putting it
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
            // After a bank's reads: is the FC STILL on that bank? A TX that
            // came on between the select and the reads drags the FC onto its
            // switch's bank — the reads would then be another bank's values
            // filed under this one. nil (no answer) counts as not verified.
            func stillOn(pid: Int?, rate: Int?) -> Bool {
                guard let now = fcBanks() else { return false }
                if let p = pid, now.pid != p { return false }
                if let r = rate, now.rate != r { return false }
                return true
            }
            // Yield to the user's tuning pages: wait (up to 2 min) for a
            // 10 s gap in page MSP traffic before ANY bank switching; if the
            // user keeps reading, skip the MSP sweep entirely this run.
            var waited = 0.0
            while !pageMspQuiet() && waited < 120 { Thread.sleep(forTimeInterval: 2); waited += 2 }
            var sweepOK = false
            if txLive {
                error = "the transmitter is on — switch it off, then back up"
            } else if !pageMspQuiet() {
                error = "a Rotorflight page was busy reading — back up again in a moment"
            } else if let orig = fcBanks() {
                total += 7 + 4 * 6 + 4 * 3 + 2   // 142 + mixer(5) + servos + pid sweep + rate sweep + restores
                mspRead("/api/msp?fn=142")       // governor global — bankless
                // Mixer — Travel extents' blocks, bankless (Malcolm
                // 2026-08-15: the backup must not forget yesterday's
                // additions). Config + one read per input 1..4.
                mspRead("/api/msp?fn=42")
                for i in 1...4 { mspRead(String(format: "/api/msp?fn=174&data=%02X", i)) }
                // Servos — bankless, one bulk read (chunked; RX 0.9.383+).
                // Malcolm 2026-08-19: the backup must include the new screen.
                mspRead("/api/msp?fn=120")
                // Every bank select makes the FC write flash — a brief servo
                // stall (the swash twitch Malcolm noticed 2026-08-06). Skip
                // selects that are already true.
                var curPid = orig.pid, curRate = orig.rate
                var aborted = false
                for b in 0...3 {
                    if txAppeared() { aborted = true; break }
                    if b != curPid { selectBank(b); curPid = b }
                    else { SessionCache.shared.noteBankSelect(dataHex: String(format: "%02X", b)) }
                    mspRead("/api/msp?fn=112")
                    mspRead("/api/msp?fn=94")
                    mspRead("/api/msp?fn=148")
                    mspRead("/api/msp?fn=146")   // Rescue (per bank)
                    if !stillOn(pid: b, rate: nil) { aborted = true; break }
                }
                if !aborted {
                    for r in 0...3 {
                        if txAppeared() { aborted = true; break }
                        if r != curRate { selectBank(0x80 | r); curRate = r }
                        else { SessionCache.shared.noteBankSelect(dataHex: String(format: "%02X", 0x80 | r)) }
                        mspRead("/api/msp?fn=111")
                        if !stillOn(pid: nil, rate: r) { aborted = true; break }
                    }
                }
                // Put the FC back exactly — always — unless a live TX now
                // owns the bank switch (our select would fight it).
                if !txAppeared() {
                    if curPid != orig.pid { selectBank(orig.pid) }
                    if curRate != orig.rate { selectBank(0x80 | orig.rate) }
                }
                if aborted {
                    error = "the transmitter came on (or the flight controller changed bank) mid-backup — switch it off and back up again"
                } else if failures > 0 {
                    error = "\(failures) read\(failures == 1 ? "" : "s") got no answer — back up again"
                }
                sweepOK = !aborted && failures == 0
            } else {
                error = "could not read the flight controller's bank (MSP 101) — is it powered and connected?"
            }
            // Full sweep completed → freeze the restore point (the rolling
            // cache keeps updating; this copy never follows the edits).
            // A pilot's own backup (explicit) is sticky: the automatic sweep
            // at connection must never replace it with today's values.
            if sweepOK {
                let froze = SessionCache.shared.snapshotRestorePoint(explicit: explicit)
                ok = froze || !explicit
                if !ok { error = "the backup file could not be written on the phone" }
            }
            total += flightPaths.count
            for p in flightPaths { _ = req(p) }
            running = false
            phase = "done"
        }
    }
}
