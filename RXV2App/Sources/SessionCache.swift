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
