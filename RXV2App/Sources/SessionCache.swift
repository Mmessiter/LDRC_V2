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
    /// Every model this phone holds a backup (restore point) for, newest
    /// first — what the Backups page lists with nothing connected
    /// (Malcolm 2026-09-19: "Backups shows what backups we made and when").
    static func savedBackups() -> [(model: String, savedAt: Date, explicit: Bool, items: Int)] {
        let files = (try? FileManager.default.contentsOfDirectory(
            at: docs, includingPropertiesForKeys: nil)) ?? []
        var out: [(String, Date, Bool, Int)] = []
        for f in files where f.lastPathComponent.hasPrefix("restore-")
                          || f.lastPathComponent.hasPrefix("backup-") {
            if let d = try? Data(contentsOf: f),
               let s = try? JSONDecoder().decode(RestoreShape.self, from: d),
               !s.entries.isEmpty {
                // The slot the file sits in is the truth (a migrated file may
                // carry either flag).
                out.append((s.model, s.savedAt, f.lastPathComponent.hasPrefix("backup-"), s.entries.count))
            }
        }
        return out.sorted { $0.1 > $1.1 }
    }

    /// "What's in the backup", in plain lines: the item names folded into
    /// "PIDs — banks 1–6" / "Servos — 8" (Malcolm 2026-09-17: the raw list
    /// "means little to a mere human"). Mirrors showContents() in
    /// rotorflight-backup.html so the app and the receiver agree.
    static func backupSummary(model: String, mine: Bool? = nil) -> [String] {
        let items = shared.restoreItems(for: model, mine: mine).map { $0.label }
        var banked: [String: Set<Int>] = [:], bankOrder: [String] = []
        var numbered: [String: Int] = [:], numOrder: [String] = []
        var plain: [String] = []
        for raw in items {
            if let r = raw.range(of: #" bank \d+$"#, options: .regularExpression),
               let n = Int(raw[r].replacingOccurrences(of: " bank ", with: "")) {
                let name = String(raw[raw.startIndex..<r.lowerBound])
                if banked[name] == nil { banked[name] = []; bankOrder.append(name) }
                banked[name]?.insert(n)
                continue
            }
            var t = raw                                        // "servo 3 (cyclic)"
            if let p = t.range(of: #" \(.*\)$"#, options: .regularExpression) { t.removeSubrange(p) }
            if let r = t.range(of: #" (?:ch)?\d+$"#, options: .regularExpression) {
                let name = String(t[t.startIndex..<r.lowerBound])
                numbered[name, default: 0] += 1
                if !numOrder.contains(name) { numOrder.append(name) }
                continue
            }
            plain.append(raw)
        }
        func cap(_ t: String) -> String { t.prefix(1).uppercased() + t.dropFirst() }
        func spread(_ set: Set<Int>) -> String {
            let a = set.sorted()
            if a.count == 1 { return "bank \(a[0])" }
            let run = a.enumerated().allSatisfy { i, v in i == 0 || v == a[i - 1] + 1 }
            return run ? "banks \(a[0])–\(a[a.count - 1])"
                       : "banks " + a.map(String.init).joined(separator: ", ")
        }
        var lines: [String] = []
        for k in bankOrder { lines.append(cap(k) + " — " + spread(banked[k]!)) }
        for k in numOrder  { lines.append(cap(k) + "s — \(numbered[k]!)") }
        lines += plain.map(cap)
        return lines
    }

    static func deleteSession(model: String) {
        try? FileManager.default.removeItem(at: sessionURL(for: model))
        try? FileManager.default.removeItem(at: restoreURL(for: model))
        try? FileManager.default.removeItem(at: restoreURL(for: model, mine: true))
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
    // differ by bank"). Rotorflight keeps up to SIX PID-side banks (fn=210,
    // byte 0-5) and six rate banks (fn=210, byte 0x80|idx) — the exact counts
    // come from MSP 101 bytes 24/26, see fcBankCounts; the reads 112/94/148
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
            // fn=174 (GET_MIXER_INPUT) and fn=154 (RPM filter notches, per
            // axis) are the READS whose parameter — the index — rides in
            // data=. Without this exception the Travel-extents reads were
            // never recorded, so backup/restore silently forgot the mixer
            // (Malcolm 2026-08-15, 6 am in bed).
            if !q.contains("fn=174") && !q.contains("fn=154") { return false }
        }
        if path == "/api/firmware/check" { return false }   // no update offers offline
        return true
    }

    /// Drop a recorded read — used when the FC says it does not support a
    /// read this firmware sends, so a value recorded from an earlier session
    /// (another FC version) can never be frozen as today's backup.
    func forget(pathAndQuery: String) {
        let work = {
            self.entries[self.keyFor(pathAndQuery)] = nil
            self.savedAt = Date()
            self.scheduleSave()
        }
        if Thread.isMainThread { work() } else { DispatchQueue.main.sync(execute: work) }   // the recording lives on main
    }

    // FLIGHTS BY IDENTITY (0.9.833, Malcolm 2026-09-24: "Viewing a review
    // often loads the wrong file"). The receiver numbers saved flights by
    // AGE (f=1 = newest), so every new flight shifts the numbers. The
    // recording used to key them by that number: a flight recorded as f=1
    // this morning was still "f=1" after the next flight saved, and the
    // review served the old flight for the new one's name. A saved flight is
    // now stored under its own identity (saved_at, count, dur_ms - fields in
    // both the list and the flight itself) and found through the recorded
    // list the page is showing. f=0 (the live flight) keeps its plain key.
    private static func flightNumber(_ pathAndQuery: String) -> Int? {
        guard pathAndQuery.hasPrefix("/api/flightlog.json?") else { return nil }
        let q = pathAndQuery.dropFirst("/api/flightlog.json?".count)
        guard let f = q.split(separator: "&").first(where: { $0.hasPrefix("f=") }),
              let n = Int(f.dropFirst(2)), n > 0 else { return nil }
        return n
    }
    private static func flightId(_ o: [String: Any]) -> String? {
        guard let c = (o["count"] as? NSNumber)?.intValue,
              let d = (o["dur_ms"] as? NSNumber)?.intValue else { return nil }
        let at = (o["saved_at"] as? NSNumber)?.intValue ?? 0
        return "flight#\(at)-\(c)-\(d)"
    }
    private static func flightId(body: Data) -> String? {
        guard let o = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any] else { return nil }
        return flightId(o)
    }
    /// The identity of flight number n in the flight list as recorded.
    private func listedFlightId(_ n: Int) -> String? {
        guard let l = entries["/api/flights.json"],
              let arr = (try? JSONSerialization.jsonObject(with: l.body)) as? [[String: Any]],
              let f = arr.first(where: { ($0["i"] as? NSNumber)?.intValue == n }) else { return nil }
        return Self.flightId(f)
    }

    func record(pathAndQuery: String, path: String, type: String, body: Data) {
        if Self.flightNumber(pathAndQuery) != nil, let id = Self.flightId(body: body) {
            entries[id] = Entry(type: type, body: body)
            entries[keyFor(pathAndQuery)] = nil      // never a by-number copy to go stale
            savedAt = Date()
            scheduleSave()
            return
        }
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

    func lookup(pathAndQuery: String) -> Entry? {
        if let n = Self.flightNumber(pathAndQuery) {
            // Only the flight the list names for that number - or nothing.
            guard let id = listedFlightId(n) else { return nil }
            if let hit = entries[id] { return hit }
            // A recording from before 0.9.833: serve its by-number copy only
            // if it really is that flight.
            if let old = entries[keyFor(pathAndQuery)], Self.flightId(body: old.body) == id { return old }
            return nil
        }
        return entries[keyFor(pathAndQuery)]
    }

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
        let writeFn: Int       // 0 = verify-only (nothing to write, the read must match)
        let readFn: Int        // for post-write verification (0 = no read-back exists)
        var hex: String        // the WRITE payload
        let label: String      // named in the UI if it fails to verify
        // Mixer inputs (171/174): the read needs the input index as data=,
        // and the write payload carries a leading index byte the read-back
        // won't echo — so the verify compares against verifyHex instead.
        var readData: String? = nil
        var verifyHex: String? = nil
        // Chunked images (servos 212, modes 35, rxfail 78, mixer rules 173,
        // meters 57/41): one FC read holds every chunk, each write sets one.
        // The chunk's own bytes must appear at chunkOffset (hex chars) of
        // the readFn image — that is both the "already identical, skip the
        // write" test and the verify.
        var chunkOffset: Int? = nil
        var chunkHex: String? = nil
        // Modes carry a second image (238: logic + link per slot) that the
        // 35 write also sets; a slot is skipped only when BOTH match.
        var extraFn: Int? = nil
        var extraOffset: Int? = nil
        var extraHex: String? = nil
        // Hex chars of the write payload that belong to the FC as it is NOW,
        // not to the backup: replaced by the FC's current bytes before the
        // compare and the write. Telemetry (73/74): the link rate/ratio
        // (bytes 8-11) is the receiver's Telemetry speed setting — a restore
        // of a backup taken at the old speed must not drag it back.
        var liveHexRange: Range<Int>? = nil

        /// The item with its live-owned bytes taken from the FC's current image.
        func withLive(from image: String) -> RestoreItem {
            guard let r = liveHexRange, image.count >= r.upperBound, hex.count >= r.upperBound else { return self }
            var copy = self
            let img = image.uppercased()
            let s = img.index(img.startIndex, offsetBy: r.lowerBound)
            let e = img.index(img.startIndex, offsetBy: r.upperBound)
            let hs = copy.hex.index(copy.hex.startIndex, offsetBy: r.lowerBound)
            let he = copy.hex.index(copy.hex.startIndex, offsetBy: r.upperBound)
            copy.hex.replaceSubrange(hs..<he, with: String(img[s..<e]))
            return copy
        }

        /// Does this FC image already carry the item? (prefix semantics for
        /// whole-image items — a reply may be longer than the write layout.)
        /// strict = the image must hold EVERY wanted byte: the "skip the
        /// write" decision must never rest on a short reply, the post-write
        /// verify keeps the old lenient rule.
        func matches(image: String, strict: Bool = false) -> Bool {
            let img = image.uppercased()
            if let off = chunkOffset, let want = chunkHex {
                guard img.count >= off + want.count else { return false }
                let s = img.index(img.startIndex, offsetBy: off)
                let e = img.index(s, offsetBy: want.count)
                return String(img[s..<e]) == want
            }
            let want = (verifyHex ?? hex).uppercased()
            if strict { return img.hasPrefix(want) }
            return !img.isEmpty && (img.hasPrefix(want) || want.hasPrefix(img))
        }
        func extraMatches(image: String) -> Bool {
            guard let off = extraOffset, let want = extraHex else { return true }
            let img = image.uppercased()
            guard img.count >= off + want.count else { return false }
            let s = img.index(img.startIndex, offsetBy: off)
            let e = img.index(s, offsetBy: want.count)
            return String(img[s..<e]) == want
        }
    }

    // MARK: the catalogue (Malcolm 2026-09-04: "let's cover all items")
    //
    // Every bankless Rotorflight read the backup freezes. Layouts checked
    // line by line against Rotorflight 4.6's msp.c: the SET payload is the
    // GET reply verbatim except motor config (222 = 131 without byte 6, the
    // motor count) and blackbox (81 = 80 without byte 0, the 'supported'
    // flag). NOT here, deliberately: ESC parameters (217/218 — Scorpion
    // programming freezes its telemetry), serial ports (54/55 — the
    // receiver's own link), LED/OSD/GPS/VTX, and the receiver's NVS.
    static let banklessReadFns: [Int] =
        [142, 42, 120,                                   // governor global, mixer, servos
         10, 36, 38, 61, 240, 96, 126,                   // name, features, board, arming, trims, sensors, alignment
         64, 44, 66, 75, 77, 50, 73,                     // channel map, receiver, sticks, failsafe, rxfail, RSSI, telemetry
         80, 92, 32, 123, 131,                           // blackbox, filters, battery, ESC telemetry, motor
         34, 238, 172, 56, 40]                           // modes (+extras), mixer rules, meters
    /// Verbatim read → write items, in restore order: (read fn, write fn, label).
    static let simpleItems: [(read: Int, write: Int, label: String)] =
        [(10, 11, "flight controller name"),
         (36, 37, "features"),
         (38, 39, "board alignment"),
         (61, 62, "arming (auto-disarm delay)"),
         (240, 239, "level trims"),
         (96, 97, "sensor selection"),
         (126, 220, "gyro alignment"),
         (64, 65, "channel map"),
         (44, 45, "receiver setup"),
         (66, 67, "stick centre & travel"),
         (75, 76, "failsafe"),
         (50, 51, "RSSI"),
         (73, 74, "telemetry sensors"),
         (92, 93, "gyro filters"),
         (32, 33, "battery"),
         (123, 216, "ESC telemetry setup")]
    /// Reads the FC may legitimately reject (older Rotorflight builds lack
    /// them): a 'rejected' answer is not a backup failure, the item is
    /// simply not in the backup. No answer at all still is.
    static let optionalReadFns: Set<Int> = [123, 154]
    /// A telemetry image (MSP 73, 52 bytes) worth restoring: link rate and
    /// ratio non-zero and at least one sensor in the 40 slots.
    static func telemImageGood(_ hex: String) -> Bool {
        let h = hex.uppercased()
        guard h.count >= 104 else { return false }
        func sub(_ a: Int, _ b: Int) -> Substring {
            h[h.index(h.startIndex, offsetBy: a)..<h.index(h.startIndex, offsetBy: b)]
        }
        return sub(16, 20) != "0000" && sub(20, 24) != "0000" && sub(24, 104).contains { $0 != "0" }
    }

    // The rolling recording tees EVERY read — including the read-backs of
    // the very edits a confused pilot wants to undo (Malcolm's closed-loop
    // test caught this: the restore faithfully re-wrote the random edits).
    // The parachute therefore restores from a FROZEN restore point, written
    // only when a full TX-off sweep completes — at connection (before any
    // editing) and on each explicit "Save session to phone".
    /// TWO backups per model (Malcolm 2026-09-19: "let's keep both backup
    /// types"). `backup-` is the pilot's own, written only when he asks and
    /// never touched by the app; `restore-` is the automatic copy, refreshed
    /// by every clean sweep. Either can be restored; yours is offered first.
    static func restoreURL(for model: String, mine: Bool = false) -> URL {
        let safe = model.isEmpty ? "last"
            : String(model.map { $0.isLetter || $0.isNumber ? $0 : "_" })
        return docs.appendingPathComponent("\(mine ? "backup" : "restore")-\(safe).json")
    }

    /// Before two slots existed, a deliberate backup lived in `restore-` with
    /// explicit:true. Move it to its own slot the first time we look, so no
    /// backup a pilot made is lost to the change.
    static func migrateRestorePoint(model: String) {
        let mine = restoreURL(for: model, mine: true)
        guard !FileManager.default.fileExists(atPath: mine.path),
              let d = try? Data(contentsOf: restoreURL(for: model)),
              let s = try? JSONDecoder().decode(RestoreShape.self, from: d),
              s.explicit == true else { return }
        try? d.write(to: mine, options: .atomic)
        try? FileManager.default.removeItem(at: restoreURL(for: model))
    }

    /// The backup a restore should use: the pilot's own when he has one.
    static func chosenIsMine(_ model: String) -> Bool {
        migrateRestorePoint(model: model)
        return FileManager.default.fileExists(atPath: restoreURL(for: model, mine: true).path)
    }
    /// For the Compare page (0.9.833): the saved models, one row each (the
    /// pilot's own backup preferred), and a model's MSP replies as hex.
    /// READ-ONLY - nothing here touches a flight controller.
    static func compareModels() -> [[String: Any]] {
        var seen = Set<String>(), out: [[String: Any]] = []
        for b in savedBackups() where !seen.contains(b.model) && !b.model.isEmpty {
            seen.insert(b.model)
            let mine = chosenIsMine(b.model)
            let at = savedBackups().first { $0.model == b.model && $0.explicit == mine }?.savedAt ?? b.savedAt
            out.append(["model": b.model, "savedAtMs": Int(at.timeIntervalSince1970 * 1000), "explicit": mine])
        }
        return out
    }
    static func compareEntries(model: String) -> [String: String] {
        guard let d = try? Data(contentsOf: restoreURL(for: model, mine: chosenIsMine(model))),
              let shape = try? JSONDecoder().decode(RestoreShape.self, from: d) else { return [:] }
        var out: [String: String] = [:]
        for (k, e) in shape.entries where k.hasPrefix("/api/msp?fn=") {
            if let h = String(data: e.body, encoding: .utf8), h.count >= 2, h.allSatisfy({ $0.isHexDigit }) { out[k] = h.uppercased() }
        }
        return out
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
         "/api/msp?fn=174&data=",   // mixer inputs (Travel extents)
         "/api/msp?fn=154&data="]   // RPM filter notches, per axis
    private static func isRestoreKey(_ k: String) -> Bool {
        if restoreKeyPrefixes.contains(where: { k.hasPrefix($0) }) { return true }
        if k.hasPrefix("/app/declared/") { return true }
        return banklessReadFns.contains { k == "/api/msp?fn=\($0)" }
    }

    /// This airframe's OWN items — servos, mixer, motor & gear, board and
    /// sensor alignment, level trims, features, battery & meters, receiver
    /// wiring, ESC telemetry, telemetry sensors, blackbox, name, modes,
    /// per-channel failsafe values, RPM notches. A backup from ANOTHER model
    /// leaves these out on import: they belong to that helicopter's hardware.
    /// What transfers is the TUNE ONLY: PIDs, advanced PIDs, rates, governor
    /// (and its global settings), rescue, filters, auto-disarm delay, RSSI.
    /// The channel map, stick centre & travel, failsafe and the bank/rates
    /// selector slots were added to this list on 2026-09-17 — they are the
    /// other pilot's RADIO, not his tune.
    static let mechanicsKeyPrefixes =
        ["/api/msp?fn=120", "/api/msp?fn=42", "/api/msp?fn=174&data=", "/api/msp?fn=172",
         "/api/msp?fn=131", "/api/msp?fn=38", "/api/msp?fn=126", "/api/msp?fn=96", "/api/msp?fn=240",
         "/api/msp?fn=36", "/api/msp?fn=32", "/api/msp?fn=56", "/api/msp?fn=40",
         "/api/msp?fn=44", "/api/msp?fn=123", "/api/msp?fn=73", "/api/msp?fn=80", "/api/msp?fn=10",
         "/api/msp?fn=34", "/api/msp?fn=238", "/api/msp?fn=77", "/api/msp?fn=154&data=",
         // The pilot's radio, not the tune (2026-09-16 review): channel map,
         // RSSI channel, RX config, and the bank/rates selector slots.
         "/api/msp?fn=64", "/api/msp?fn=66", "/api/msp?fn=75",   // channel map, stick centre & travel, failsafe
         "/app/declared/adj30", "/app/declared/adj31", "/app/declared/adj32", "/app/declared/adj33", "/app/declared/adj34", "/app/declared/adj35",
         "/app/declared/adj36", "/app/declared/adj37", "/app/declared/adj38", "/app/declared/adj39", "/app/declared/adj40", "/app/declared/adj41"]
    static func isMechanicsKey(_ k: String) -> Bool {
        mechanicsKeyPrefixes.contains { p in
            p.hasSuffix("=") ? k.hasPrefix(p) : (k == p || k.hasPrefix(p + "&"))
        }
    }

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

    /// How many banks this flight controller HAS — bytes 24 and 26 of the
    /// same reply (0.9.742). Rotorflight builds the counts from flash size,
    /// so they can differ: >256 kB gives 6 PID and 6 rate banks, >128 kB
    /// gives 3 PID but still 6 rate. The sweep used to walk 0...3 flat,
    /// which meant a full-size board's banks 5 and 6 were never backed up
    /// and never restored — silently, with the progress bar reading 100 %.
    /// Falls back to 4 (what the sweep always did) when the reply is junk.
    /// Rotorflight's own ceiling (upstream common_pre.h). Nothing may walk
    /// past this.
    static let maxBanks = 6

    static func fcBankCounts(statusHex: String) -> (pid: Int, rate: Int) {
        let h = Array(statusHex.uppercased())
        guard h.count >= 54 else { return (4, 4) }
        func byte(_ i: Int) -> Int? { Int(String(h[(2 * i)..<(2 * i + 2)]), radix: 16) }
        guard let pc = byte(24), let rc = byte(26), pc > 0, pc <= 8, rc > 0, rc <= 8 else { return (4, 4) }
        return (pc, rc)
    }

    /// Freeze the tuning reads currently in the rolling cache. `explicit` =
    /// the pilot's own "Back up" tap; an automatic (connection) freeze never
    /// replaces an explicit one. Returns false when nothing was written.
    @discardableResult
    func snapshotRestorePoint(explicit: Bool = false) -> Bool {
        Self.migrateRestorePoint(model: modelName)
        var keep: [String: Entry] = [:]
        for (k, v) in entries where Self.isRestoreKey(k) { keep[k] = v }
        guard !keep.isEmpty else { return false }
        let shape = RestoreShape(model: modelName, savedAt: Date(), entries: keep, explicit: explicit)
        guard let d = try? JSONEncoder().encode(shape) else { return false }
        // Each kind has its own slot now, so the automatic copy can stay
        // fresh without ever threatening the one the pilot made.
        do { try d.write(to: Self.restoreURL(for: modelName, mine: explicit), options: .atomic) }
        catch { return false }
        return true
    }

    /// When was the current model's restore point frozen? nil = none.
    func restorePointDate(mine: Bool? = nil) -> Date? {
        let m = mine ?? Self.chosenIsMine(modelName)
        guard let d = try? Data(contentsOf: Self.restoreURL(for: modelName, mine: m)),
              let s = try? JSONDecoder().decode(RestoreShape.self, from: d) else { return nil }
        return s.savedAt
    }

    /// Was the current restore point a deliberate backup (or an import)?
    func restorePointIsExplicit() -> Bool { Self.chosenIsMine(modelName) }

    /// Does this model have BOTH kinds? (the page then offers the choice)
    func hasBothBackups() -> Bool {
        Self.migrateRestorePoint(model: modelName)
        let f = FileManager.default
        return f.fileExists(atPath: Self.restoreURL(for: modelName, mine: true).path)
            && f.fileExists(atPath: Self.restoreURL(for: modelName).path)
    }

    /// Everything restorable from the FROZEN restore point, in write order.
    /// `model` names another model's backup (the Backups page shows them all).
    func restoreItems(for model: String? = nil, mine: Bool? = nil) -> [RestoreItem] {
        let name = model ?? modelName
        let m = mine ?? Self.chosenIsMine(name)
        guard let d = try? Data(contentsOf: Self.restoreURL(for: name, mine: m)),
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
        // Walk every bank Rotorflight can have (0.9.742). hexAt() returns
        // nil for a bank the file does not hold, so a 4-bank backup taken
        // before today restores exactly as it always did, and a 6-bank one
        // restores all six. Never ask the FC here — the file decides.
        for b in 0..<Self.maxBanks {
            if let h = hexAt("/api/msp?fn=112&bank=\(b)") { out.append(RestoreItem(selectByte: b, writeFn: 202, readFn: 112, hex: h, label: "PIDs bank \(b + 1)")) }
            if let h = hexAt("/api/msp?fn=94&bank=\(b)")  { out.append(RestoreItem(selectByte: b, writeFn: 95,  readFn: 94,  hex: h, label: "advanced PIDs bank \(b + 1)")) }
            if let h = hexAt("/api/msp?fn=148&bank=\(b)") { out.append(RestoreItem(selectByte: b, writeFn: 149, readFn: 148, hex: h, label: "governor profile bank \(b + 1)")) }
            if let h = hexAt("/api/msp?fn=146&bank=\(b)") { out.append(RestoreItem(selectByte: b, writeFn: 147, readFn: 146, hex: h, label: "rescue bank \(b + 1)")) }
        }
        for r in 0..<Self.maxBanks {
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
        func slice(_ s: String, _ off: Int, _ len: Int) -> String? {
            guard off >= 0, len > 0, s.count >= off + len else { return nil }
            let a = s.index(s.startIndex, offsetBy: off)
            return String(s[a..<s.index(a, offsetBy: len)])
        }
        // Servos (bankless): the stored fn-120 image is count(1B) + 16 B per
        // servo; fn 212 writes ONE servo (index byte + its 16 B), verified
        // as that servo's 16 B in the fn-120 read-back.
        if let full = hexAt("/api/msp?fn=120"), full.count >= 2,
           let count = Int(full.prefix(2), radix: 16), count > 0, count <= 8 {
            let roles = ["swash 1", "swash 2", "swash 3", "TAIL", "5", "6", "7", "8"]
            for i in 0..<count {
                guard let s = slice(full, 2 + i * 32, 32) else { break }
                out.append(RestoreItem(selectByte: nil, writeFn: 212, readFn: 120,
                                       hex: String(format: "%02X", i) + s,
                                       label: "servo \(i + 1) (\(roles[i]))",
                                       chunkOffset: 2 + i * 32, chunkHex: s))
            }
        }
        // Mixer rules (172 → 173, one rule per write: index + 7 B).
        if let full = hexAt("/api/msp?fn=172") {
            for i in 0..<(full.count / 14) {
                guard let s = slice(full, i * 14, 14) else { break }
                out.append(RestoreItem(selectByte: nil, writeFn: 173, readFn: 172,
                                       hex: String(format: "%02X", i) + s, label: "mixer rule \(i + 1)",
                                       chunkOffset: i * 14, chunkHex: s))
            }
        }
        // Motor & gear ratio: 222 takes the 131 reply WITHOUT byte 6 (motor
        // count) — exactly what the Gear ratio page writes; needs an FC
        // restart afterwards (the runner reboots after the EEPROM save).
        if let full = hexAt("/api/msp?fn=131"), full.count >= 58 {
            let w = String(full.prefix(12)) + String(full.dropFirst(14).prefix(44))
            out.append(RestoreItem(selectByte: nil, writeFn: 222, readFn: 131, hex: w,
                                   label: "motor & gear ratio", verifyHex: full))
        }
        // Blackbox: 81 takes the 80 reply WITHOUT byte 0 (the 'supported' flag).
        if let full = hexAt("/api/msp?fn=80"), full.count >= 26 {
            out.append(RestoreItem(selectByte: nil, writeFn: 81, readFn: 80,
                                   hex: String(full.dropFirst(2)), label: "blackbox setup", verifyHex: full))
        }
        // The verbatim items.
        for it in Self.simpleItems {
            if let h = hexAt("/api/msp?fn=\(it.read)") {
                if it.read == 73 {
                    // Telemetry: a backup holding an EMPTY sensor list (the
                    // 2026-09-03 fault, caught in a backup) must not be put
                    // back — the FC's own list stays; the receiver refuses
                    // such a write anyway. The link speed is live (above).
                    guard Self.telemImageGood(h) else { continue }
                    out.append(RestoreItem(selectByte: nil, writeFn: it.write, readFn: it.read, hex: h, label: it.label,
                                           liveHexRange: 16..<24))
                    continue
                }
                out.append(RestoreItem(selectByte: nil, writeFn: it.write, readFn: it.read, hex: h, label: it.label))
            }
        }
        // RPM filter notches (154 per axis → 155): axis byte + the axis image.
        for (a, name) in [(0, "roll"), (1, "pitch"), (2, "yaw")] {
            let key = String(format: "%02X", a)
            if let h = hexAt("/api/msp?fn=154&data=\(key)") {
                out.append(RestoreItem(selectByte: nil, writeFn: 155, readFn: 154, hex: key + h,
                                       label: "RPM notches — \(name)", readData: key, verifyHex: h))
            }
        }
        // Voltage (56 → 57) and current (40 → 41) meters: the reply is a
        // count then frames [len, id, type, values…] — 8 bytes on the wire
        // for a voltage meter (scale, divider, divmul), 7 for a current
        // meter (scale, offset); each write is id + values, verified as the
        // values in the frame.
        for (readFn, writeFn, frameLen, name) in [(56, 57, 8, "voltage meter"), (40, 41, 7, "current meter")] {
            guard let full = hexAt("/api/msp?fn=\(readFn)"), full.count >= 2,
                  let n = Int(full.prefix(2), radix: 16), n > 0, n <= 4 else { continue }
            for i in 0..<n {
                let f = 2 + i * frameLen * 2
                guard let id = slice(full, f + 2, 2), let vals = slice(full, f + 6, (frameLen - 3) * 2) else { break }
                out.append(RestoreItem(selectByte: nil, writeFn: writeFn, readFn: readFn, hex: id + vals,
                                       label: "\(name) \(i + 1)", chunkOffset: f + 6, chunkHex: vals))
            }
        }
        // Modes / arming switch (34 + 238 → 35, one slot per write: index,
        // box, channel, start, end, logic, link). A slot is skipped only when
        // both images already match; the 238 image is verified whole at the
        // end (the 34 read-back verifies each slot's range).
        if let ranges = hexAt("/api/msp?fn=34"), let extra = hexAt("/api/msp?fn=238"),
           let n = Int(extra.prefix(2), radix: 16), n > 0, n <= 32,
           ranges.count >= n * 8, extra.count >= 2 + n * 6 {
            for i in 0..<n {
                guard let r = slice(ranges, i * 8, 8), let x = slice(extra, 2 + i * 6 + 2, 4) else { break }
                out.append(RestoreItem(selectByte: nil, writeFn: 35, readFn: 34,
                                       hex: String(format: "%02X", i) + r + x, label: "mode slot \(i + 1)",
                                       chunkOffset: i * 8, chunkHex: r,
                                       extraFn: 238, extraOffset: 2 + i * 6 + 2, extraHex: x))
            }
            out.append(RestoreItem(selectByte: nil, writeFn: 0, readFn: 238, hex: extra, label: "mode logic & links"))
        }
        // Per-channel failsafe values (77 → 78: index + mode + value).
        if let full = hexAt("/api/msp?fn=77") {
            for i in 0..<min(full.count / 6, 18) {
                guard let s = slice(full, i * 6, 6) else { break }
                out.append(RestoreItem(selectByte: nil, writeFn: 78, readFn: 77,
                                       hex: String(format: "%02X", i) + s, label: "failsafe value ch\(i + 1)",
                                       chunkOffset: i * 6, chunkHex: s))
            }
        }
        // Declared items (Malcolm 2026-08-30): settings the FC cannot read
        // back over the radio — the bank/rates selector adjustment ranges
        // (MSP 53, ~590-byte table vs the FC's 320-byte telemetry buffer).
        // Restored verbatim, readFn 0 = "no verify possible".
        for (k, e) in frozen where k.hasPrefix("/app/declared/adj") {
            guard let h = String(data: e.body, encoding: .utf8), h.count >= 4,
                  h.allSatisfy({ $0.isHexDigit }) else { continue }
            // The live selector slots are adj30 (bank) and adj36 (rates);
            // 40/41 are legacy and cleared (rotorflight-txchannels.html).
            let label = k.hasSuffix("adj30") ? "bank selector switch"
                      : k.hasSuffix("adj36") ? "rates selector switch" : "declared \(k)"
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
        let mineNow = Self.chosenIsMine(modelName)
        var shape = (try? Data(contentsOf: Self.restoreURL(for: modelName, mine: mineNow)))
            .flatMap { try? JSONDecoder().decode(RestoreShape.self, from: $0) }
            ?? RestoreShape(model: modelName, savedAt: Date(), entries: [:])
        shape.entries[k] = e
        if let d = try? JSONEncoder().encode(shape) {
            try? d.write(to: Self.restoreURL(for: modelName, mine: mineNow), options: .atomic)
        }
    }

    /// key → hex of every declared item known for this model.
    func declared() -> [String: String] {
        var out: [String: String] = [:]
        if let d = try? Data(contentsOf: Self.restoreURL(for: modelName, mine: Self.chosenIsMine(modelName))),
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
        // Sending yourself a backup means the one you made, when you have one.
        guard let d = try? Data(contentsOf: Self.restoreURL(for: modelName, mine: Self.chosenIsMine(modelName))),
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
            if !sameModel, Self.isMechanicsKey(k) { continue }
            guard let b64 = v["b64"] as? String, let body = Data(base64Encoded: b64) else { continue }
            entries[k] = Entry(type: (v["type"] as? String) ?? "text/plain", body: body)
        }
        guard !entries.isEmpty else { return (false, fileModel, 0, false) }
        let shape = RestoreShape(model: model, savedAt: Date(), entries: entries, explicit: true)
        guard let d = try? JSONEncoder().encode(shape) else { return (false, fileModel, 0, false) }
        // An imported file is the pilot's own backup.
        do { try d.write(to: Self.restoreURL(for: model, mine: true), options: .atomic) } catch { return (false, fileModel, 0, false) }
        return (true, fileModel, entries.count, sameModel)
    }
}

final class RestoreRunner {
    /// Which backup the next run writes back: nil = the pilot's own if he has
    /// one (set from /app/restore/start?which=…).
    static var useMine: Bool? = nil
    private static var running = false
    static var phase = "idle"      // idle | running | done
    static var done = 0
    static var total = 0
    static var failures = 0
    static var failedLabels: [String] = []
    static var error = ""          // non-empty = the run stopped early; the page shows it
    // What the run actually did — the page's finishing line is built from
    // these (Malcolm 2026-09-04, back-up-then-restore: "I thought it was
    // going to skip them all" — it did, but the page said "restored").
    static var written = 0         // items written AND verified
    static var same = 0            // items the FC already held (reads only)
    static var blind = 0           // of `written`: declared items with no read-back (the switch assignments)
    static var writtenLabels: [String] = []   // the readable items that were written ("PIDs bank 1") — the page names them
    static var progressJSON: Data {
        let names = failedLabels.map { "\"\($0)\"" }.joined(separator: ",")
        let wnames = writtenLabels.map { "\"\($0.replacingOccurrences(of: "\"", with: "'"))\"" }.joined(separator: ",")
        let err = error.replacingOccurrences(of: "\"", with: "'")
        return Data("{\"phase\":\"\(phase)\",\"done\":\(done),\"total\":\(total),\"failures\":\(failures),\"failed\":[\(names)],\"error\":\"\(err)\",\"written\":\(written),\"same\":\(same),\"blind\":\(blind),\"writtenNames\":[\(wnames)]}".utf8)
    }

    static func run(link: BleLink) {
        guard !running else { return }
        running = true
        phase = "running"; done = 0; failures = 0; failedLabels = []; error = ""
        written = 0; same = 0; blind = 0; writtenLabels = []
        let items = SessionCache.shared.restoreItems(mine: useMine)
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
            var wroteGov = false, wroteMotor = false, wroteAny = false
            var curPid = orig.pid, curRate = orig.rate
            var stopped = false
            // The modes' second image (238), read once and again after any
            // mode write; nil = not read yet.
            var extraImages: [Int: String] = [:]
            for it0 in items {
                var it = it0
                if stopped { failures += 1; failedLabels.append(it.label); done += 1; continue }
                // TWO attempts — a single radio hiccup among ~50 sequential
                // MSP ops must not fail the parachute (Malcolm 2026-08-06:
                // "One was not verified I see").
                var itemOk = false, already = false
                for attempt in 1...2 {
                    var ok = true
                    already = false
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
                    // Read first: an item the FC already holds is not
                    // written again (a restore of an unchanged setup is
                    // then reads only — no flash stalls, no needless
                    // re-inits). Mixer inputs and RPM notches read with
                    // their index in data= and compare against verifyHex
                    // (the write payload minus its leading index byte);
                    // chunk items compare their slice of the image.
                    let rq = it.readFn != 0
                        ? "/api/msp?fn=\(it.readFn)" + (it.readData.map { "&data=\($0)" } ?? "") : ""
                    if ok && it.readFn != 0 {
                        let cur = req(rq).body
                        it = it0.withLive(from: cur)      // live-owned bytes (telemetry speed) come from the FC
                        var extraOk = true
                        if let xf = it.extraFn {
                            if extraImages[xf] == nil { extraImages[xf] = req("/api/msp?fn=\(xf)").body }
                            extraOk = it.extraMatches(image: extraImages[xf] ?? "")
                        }
                        already = it.matches(image: cur, strict: true) && extraOk
                    }
                    if ok && !already {
                        if it.writeFn == 0 {
                            ok = false                       // verify-only item that does not match
                        } else {
                            wroteAny = true
                            ok = req("/api/msp?fn=\(it.writeFn)&data=\(it.hex)").ok
                            // Verify: read back, compare (reply may be longer — prefix).
                            if ok && it.readFn != 0 { ok = it.matches(image: req(rq).body) }   // readFn 0 = declared item, no read-back exists
                            // ... and the extra image (mode logic/link bytes) — re-read,
                            // it changed with the write; a slot the FC ignored fails HERE.
                            if let xf = it.extraFn {
                                extraImages[xf] = req("/api/msp?fn=\(xf)").body
                                if ok { ok = it.extraMatches(image: extraImages[xf] ?? "") }
                            }
                        }
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
                if itemOk && already { same += 1 }
                if itemOk && !already {
                    written += 1
                    if it.readFn == 0 { blind += 1 }              // declared item: written unseen
                    else { writtenLabels.append(it.label) }
                    if it.writeFn == 143 { wroteGov = true }
                    if it.writeFn == 222 { wroteMotor = true }   // motor / gear ratio: FC restart needed
                }
                done += 1
            }
            // Put the FC back on its own banks BEFORE the EEPROM save — unless
            // a live transmitter now owns the bank switch.
            if !stopped {
                if curPid != orig.pid { _ = req("/api/msp?fn=210&data=" + String(format: "%02X", orig.pid)) }
                if curRate != orig.rate { _ = req("/api/msp?fn=210&data=" + String(format: "%02X", 0x80 | orig.rate)) }
            }
            // Save to EEPROM — verified: an unsaved restore evaporates at the
            // next power-up while the page said "restored". Nothing written
            // (the FC already held it all) → nothing to save, no flash stall.
            var saved = true
            if wroteAny {
                saved = req("/api/msp?fn=250").ok
                if !saved { Thread.sleep(forTimeInterval: 0.6); saved = req("/api/msp?fn=250").ok }
                if !saved { failures += 1; failedLabels.append("save to flight controller memory (EEPROM) — run the restore again") }
            }
            // Governor config and the motor block only take effect after an
            // FC restart — reboot only after a CONFIRMED save (an unsaved
            // reboot would throw the whole restore away).
            if (wroteGov || wroteMotor) && saved { _ = req("/api/msp?fn=68") }
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
    static var retries = 0         // reads that needed a second try: a weak link, shown live
    static var error = ""
    static var progressJSON: Data {
        let err = error.replacingOccurrences(of: "\"", with: "'")
        return Data("{\"phase\":\"\(phase)\",\"done\":\(done),\"total\":\(total),\"ok\":\(ok),\"retries\":\(retries),\"error\":\"\(err)\"}".utf8)
    }

    /// explicit = the pilot pressed "Back up" (or imported a file): the
    /// restore point it freezes is sticky — later automatic sweeps at
    /// connection never overwrite it (they still refresh the rolling cache).
    /// A "Back up" tap that lands while a sweep is already running. The guard
    /// below used to DROP it, so that sweep finished and wrote itself as an
    /// automatic copy — the pilot's deliberate backup vanished (Malcolm
    /// 2026-09-19: "I just made an explicit backup deliberately. But the
    /// screen still says it was automatic"). The sweep in flight adopts the
    /// intent; one that lands too late is honoured when the sweep ends.
    static var pendingExplicit = false

    static func run(link: BleLink, fast: Bool = false, explicit: Bool = false) {
        // Never beside an update (0.9.834, Malcolm 2026-09-24): a Bluetooth
        // install dropped the link, the reconnection started this sweep, and
        // its bank switches ran through the middle of the firmware transfer -
        // the swash hit its stops. The install owns the link until it is done.
        if BleOta.busy {
            if explicit {
                phase = "done"; ok = false
                error = "an update is being installed — back up again once it has finished"
            }
            return
        }
        // Re-run on EVERY (re)connection — an OTA reboot or a walk-away cut
        // the first attempt short (Malcolm 2026-08-04: "could not view this
        // morning's data"); recording is idempotent, so repeats are free.
        if explicit { pendingExplicit = true }
        guard !running else { return }
        running = true
        phase = "running"; done = 0; total = 4; ok = false; error = ""; retries = 0   // state, flights, events x2
        let pace = fast ? 0.15 : 0.4
        var failures = 0      // MSP reads that never answered (after one retry)
        var straightFails = 0 // ...in a row: five means the link is gone, not a hiccup
        var tooFar = false    // (Malcolm 2026-09-10: "it tried and tried" out of range)
        var updating = false  // an install started mid-sweep (0.9.834): stop, and freeze nothing

        // Blocking GET on this background thread; tees into the recording.
        // Returns the receiver's HTTP code too (0 = no answer at all): the
        // receiver says 502 when the FC REJECTED the request (an MSP this
        // Rotorflight build lacks) and 504 when it never answered.
        func reqCoded(_ p: String) -> (code: Int, body: Data?) {
            let sem = DispatchSemaphore(value: 0)
            var body: Data?
            var code = 0
            DispatchQueue.main.async {
                link.request(method: "GET", path: p, headers: [:], body: nil) { result in
                    switch result {
                    case .success(let resp):
                        code = resp.code == 0 ? 200 : resp.code
                        if resp.code == 0 || resp.code == 200 {
                            body = resp.body
                            let bare = p.split(separator: "?").first.map(String.init) ?? p
                            let q = p.contains("?") ? String(p.split(separator: "?")[1]) : nil
                            if SessionCache.cacheable(path: bare, query: q) {
                                SessionCache.shared.record(pathAndQuery: p, path: bare,
                                                           type: resp.contentType, body: resp.body)
                            }
                        }
                    case .failure:
                        code = -1          // transport trouble, not the receiver's verdict
                    }
                    sem.signal()
                }
            }
            _ = sem.wait(timeout: .now() + 20)
            // Progress counts PLANNED items (below), not requests: the bank
            // checks, selects and retries used to push "done" past "total"
            // (Malcolm 2026-09-07: "97/90 is beyond 100%").
            Thread.sleep(forTimeInterval: pace)
            return (code, body)
        }
        func req(_ p: String) -> Data? { reqCoded(p).body }
        // A Rotorflight read the backup depends on: one retry, then it
        // counts as a failure — a missing answer must never let a stale
        // value from an earlier session pass as today's backup. An
        // `optional` read the FC rejects (502 — older Rotorflight) is not a
        // failure: the item is dropped from the recording so the restore
        // point cannot carry a stale copy of it either.
        func mspRead(_ p: String, optional: Bool = false) {
            defer { done += 1 }                  // one planned item, however many tries
            if BleOta.busy { updating = true }   // an install started: leave the FC alone
            if tooFar || updating { return }     // the link is gone: skip the rest, finish fast
            let first = reqCoded(p)
            if first.body != nil { straightFails = 0; return }
            if optional && first.code == 502 { SessionCache.shared.forget(pathAndQuery: p); return }
            Thread.sleep(forTimeInterval: 0.5)
            let second = reqCoded(p)
            if second.body != nil { straightFails = 0; retries += 1; return }
            if optional && second.code == 502 { SessionCache.shared.forget(pathAndQuery: p); return }
            failures += 1
            straightFails += 1
            if straightFails >= 5 { tooFar = true }
        }
        func selectBank(_ byte: Int) {
            if BleOta.busy { updating = true; return }   // never switch a bank under an install
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
            done += 1
            if let fl = req("/api/flights.json"),
               let arr = (try? JSONSerialization.jsonObject(with: fl)) as? [[String: Any]] {
                for f in arr {
                    if let i = f["i"] as? Int, i > 0 { flightPaths.append("/api/flightlog.json?f=\(i)") }
                }
            }
            done += 1
            _ = req("/api/events.json"); done += 1
            _ = req("/api/events-prev.json"); done += 1   // previous boot's persisted tail
            // Rotorflight reads — banked (Malcolm 2026-08-04: each PID-side
            // bank and each rate bank is its own set of values; there are up
            // to six of each — the FC's own counts decide, see fcBankCounts).
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
                // How many banks this flight controller HAS (0.9.742). It used
                // to sweep four flat, so on a full-size board banks 5 and 6
                // were never saved — and the progress bar still read 100 %.
                let counts = SessionCache.fcBankCounts(
                    statusHex: req("/api/msp?fn=101").flatMap { String(data: $0, encoding: .utf8) } ?? "")
                let nPid  = min(counts.pid,  SessionCache.maxBanks)
                let nRate = min(counts.rate, SessionCache.maxBanks)
                // Exactly the planned reads: bankless + 4 mixer inputs + 3 RPM
                // notch axes + 4 reads per PID bank + 1 per rate bank. Bank
                // selects, MSP 101 checks and TX checks are not items.
                total += SessionCache.banklessReadFns.count + 4 + 3 + 4 * nPid + nRate
                // Every bankless setup block (Malcolm 2026-09-04: "cover all
                // items") — governor global, mixer, servos, modes, channel
                // map, motor & gear, battery & meters, features, alignment,
                // filters, telemetry, blackbox, name … the catalogue's
                // order. Reads an older Rotorflight rejects are optional.
                for fn in SessionCache.banklessReadFns {
                    mspRead("/api/msp?fn=\(fn)", optional: SessionCache.optionalReadFns.contains(fn))
                }
                // Mixer inputs — Travel extents' blocks (Malcolm 2026-08-15:
                // the backup must not forget yesterday's additions), one read
                // per input 1..4.
                for i in 1...4 { mspRead(String(format: "/api/msp?fn=174&data=%02X", i)) }
                // RPM filter notches, one read per axis (roll, pitch, yaw).
                for a in 0...2 { mspRead(String(format: "/api/msp?fn=154&data=%02X", a), optional: true) }
                // Every bank select makes the FC write flash — a brief servo
                // stall (the swash twitch Malcolm noticed 2026-08-06). Skip
                // selects that are already true.
                var curPid = orig.pid, curRate = orig.rate
                var aborted = false
                for b in 0..<nPid {
                    if tooFar || updating { break }
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
                    for r in 0..<nRate {
                        if tooFar || updating { break }
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
                if updating {
                    error = "an update started — back up again once it has finished"
                } else if tooFar {
                    error = "too far from the receiver — the link kept dropping. Move within a metre and back up again"
                } else if aborted {
                    error = "the transmitter came on (or the flight controller changed bank) mid-backup — switch it off and back up again"
                } else if failures > 0 {
                    error = "\(failures) read\(failures == 1 ? "" : "s") got no answer — back up again"
                }
                sweepOK = !aborted && !tooFar && !updating && failures == 0
            } else {
                error = "could not read the flight controller's bank (MSP 101) — is it powered and connected, and are you close enough?"
            }
            // Full sweep completed → freeze the restore point (the rolling
            // cache keeps updating; this copy never follows the edits).
            // A pilot's own backup (explicit) is sticky: the automatic sweep
            // at connection must never replace it with today's values.
            if sweepOK {
                let wanted = explicit || pendingExplicit
                let froze = SessionCache.shared.snapshotRestorePoint(explicit: wanted)
                if wanted { pendingExplicit = false }
                ok = froze || !wanted
                if !ok { error = "the backup file could not be written on the phone" }
            }
            total += flightPaths.count
            for p in flightPaths where !BleOta.busy { _ = req(p); done += 1 }
            if sweepOK && done < total { done = total }   // every planned item was attempted
            // A "Back up" that landed after the freeze still gets what it
            // asked for, from the reads this sweep just gathered.
            if pendingExplicit {
                if sweepOK { _ = SessionCache.shared.snapshotRestorePoint(explicit: true); ok = true }
                pendingExplicit = false
            }
            running = false
            phase = "done"
        }
    }
}
