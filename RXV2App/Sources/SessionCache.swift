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

    private let fileURL: URL = {
        let docs = FileManager.default.urls(for: .documentDirectory,
                                            in: .userDomainMask)[0]
        return docs.appendingPathComponent("lastSession.json")
    }()

    private struct FileShape: Codable {
        var model: String
        var savedAt: Date
        var entries: [String: Entry]
    }

    private var saveScheduled = false

    private init() { load() }

    var available: Bool { !entries.isEmpty }

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
        entries[pathAndQuery] = Entry(type: type, body: body)
        if path == "/api/state.json",
           let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
           let info = obj["info"] as? [String: Any],
           let name = info["name"] as? String, !name.isEmpty {
            if name != modelName && !modelName.isEmpty {
                // Different receiver — the old recording is another model's;
                // start fresh so the review is never a chimera of two crafts.
                entries = [pathAndQuery: Entry(type: type, body: body)]
            }
            modelName = name
        }
        savedAt = Date()
        scheduleSave()
    }

    func lookup(pathAndQuery: String) -> Entry? { entries[pathAndQuery] }

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
        guard let data = try? Data(contentsOf: fileURL),
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
        var (model, edits) = Self.loadPending()
        if model != modelName { edits = [] }               // stale edits for another model
        edits.removeAll { $0.fn == fn }                    // newest edit of a kind wins
        edits.append(Self.PendingEdit(fn: fn, hex: dataHex,
                                      label: Self.writeLabels[fn] ?? "settings"))
        Self.savePending(model: modelName, edits: edits)
        // The pages read back exactly what they wrote (symmetric MSP layouts).
        record(pathAndQuery: "/api/msp?fn=\(readFn)", path: "/api/msp",
               type: "text/plain", body: Data(dataHex.uppercased().utf8))
        return true
    }
}

// MARK: - Whole-session prefetch (Malcolm 2026-08-04, refinement 1)
//
// Record EVERYTHING, not just what the user happened to view: shortly after
// connecting, walk the flight list and the tuning reads in the background,
// paced gently so the user's own page loads keep priority on the one radio.

final class SessionPrefetcher {
    private static var running = false
    static func run(link: BleLink) {
        // Re-run on EVERY (re)connection — an OTA reboot or a walk-away cut
        // the first attempt short (Malcolm 2026-08-04: "could not view this
        // morning's data"); recording is idempotent, so repeats are free.
        guard !running else { return }
        running = true
        var paths = ["/api/state.json", "/api/flights.json", "/api/events.json",
                     "/api/msp?fn=111", "/api/msp?fn=112", "/api/msp?fn=94",
                     "/api/msp?fn=142", "/api/msp?fn=148"]
        func next() {
            guard !paths.isEmpty else { running = false; return }
            let p = paths.removeFirst()
            link.request(method: "GET", path: p, headers: [:], body: nil) { result in
                if case .success(let resp) = result, resp.code == 0 || resp.code == 200 {
                    let bare = p.split(separator: "?").first.map(String.init) ?? p
                    let q = p.contains("?") ? String(p.split(separator: "?")[1]) : nil
                    if SessionCache.cacheable(path: bare, query: q) {
                        SessionCache.shared.record(pathAndQuery: p, path: bare,
                                                   type: resp.contentType, body: resp.body)
                    }
                    // The flight list seeds one fetch per saved flight.
                    if p == "/api/flights.json",
                       let arr = try? JSONSerialization.jsonObject(with: resp.body) as? [[String: Any]] {
                        for f in arr {
                            if let i = f["i"] as? Int, i > 0 {
                                paths.append("/api/flightlog.json?f=\(i)")
                            }
                        }
                    }
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { next() }
            }
        }
        // Let the front page settle first; then record the world.
        DispatchQueue.main.asyncAfter(deadline: .now() + 6) { next() }
    }
}
