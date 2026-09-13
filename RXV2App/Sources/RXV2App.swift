// LockDownRadioControl — RXV2App  ::  RXV2App.swift
//
// Scan for receivers advertising the RXV2 config service, connect, and show
// the receiver's own web UI over Bluetooth. The web interface over WiFi is
// untouched — this app is simply a second, fuss-free door to the same
// configuration engine.

import SwiftUI
import PhotosUI

@main
struct RXV2App: App {
    @StateObject private var link = BleLink()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(link)
        }
    }
}

struct RootView: View {
    @EnvironmentObject var link: BleLink
    @Environment(\.scenePhase) private var scenePhase
    @State private var backgroundedAt: Date? = nil
    @State private var demoMode = false
    @State private var demoDongle = false     // which demo: receiver (false) or dongle (true)
    @State private var reviewMode = false
    @State private var sessionStarted = false
    @State private var txOnNoticeShown = false
    @State private var showPendingOffer = false
    @State private var pendingSummary = ""
    @State private var pendingEdits: [SessionCache.PendingEdit] = []
    // Send-progress panel (Malcolm 2026-08-04: "I did not know when the
    // upload had finished"): solid overlay with a bar, then a done tick.
    @State private var sendShowing = false
    @State private var sendDone = 0
    @State private var sendTotal = 0
    @State private var sendResult: String? = nil   // nil while sending
    // A backup file opened from Messages, Mail or Files (Malcolm 2026-09-10:
    // "I sent a backup to myself over iMessage - how do I get it in?").
    @State private var importNotice: String? = nil

    var body: some View {
        NavigationStack {
            switch link.state {
            case .ready(let name), .reconnecting(let name):
                // Full-screen, like the web UI added to the home screen: no
                // navigation bar. Disconnect lives on the page's Bluetooth
                // badge (bottom-right), via the rxv2 JS message bridge.
                WebScreen(link: link)
                    .ignoresSafeArea()
                    .toolbar(.hidden, for: .navigationBar)
                    .onAppear { onConnected(name) }
                    .onChange(of: link.state) { st in
                        if case .ready = st { SessionPrefetcher.run(link: link) }
                    }
                    .alert("Settings edited offline", isPresented: $showPendingOffer) {
                        if pendingEdits.isEmpty {
                            Button("OK") { }                      // discard notice (TX was on)
                        } else {
                            Button("Send to model") { sendPendingEdits() }
                            Button("Discard offline edits", role: .destructive) {
                                SessionCache.savePending(model: "", edits: [])
                            }
                            Button("Not now", role: .cancel) { }  // keep them for later
                        }
                    } message: {
                        Text(pendingSummary)
                    }
                    .overlay {
                        if sendShowing {
                            VStack(spacing: 12) {
                                Text(sendResult ?? "Sending edits… \(sendDone) / \(sendTotal)")
                                    .font(.headline)
                                    .multilineTextAlignment(.center)
                                if sendResult == nil {
                                    ProgressView(value: Double(sendDone),
                                                 total: Double(max(sendTotal, 1)))
                                        .frame(width: 220)
                                    Text("Keep the transmitter OFF and the model ON until this finishes.")
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                        .multilineTextAlignment(.center)
                                }
                            }
                            .padding(24)
                            .frame(maxWidth: 300)
                            .background(RoundedRectangle(cornerRadius: 16)
                                .fill(Color(.systemBackground))
                                .shadow(radius: 12))
                        }
                    }
            default:
                ScannerView(demoMode: $demoMode, reviewMode: $reviewMode, demoDongle: $demoDongle)
                    .onAppear {
                        sessionStarted = false
                        // "--demo" launch argument: straight into demo mode (website screenshots)
                        if ProcessInfo.processInfo.arguments.contains("--demo") { demoMode = true }
                    }
            }
        }
        // No receiver? Let anyone play: canned data from a real receiver,
        // with animated channels.
        // Armchair review (Malcolm's lodge idea): the recorded last session
        // served to the same pages — receiver asleep in its case.
        // Fresh start after a real absence (Malcolm 2026-08-06: on reopening
        // "usually I want to connect to a different model"): away >1 min with
        // a live link → drop it and land on the model list. Quick app-switches
        // keep the connection; demo and armchair review are left alone.
        .onOpenURL { url in importBackupFile(url) }
        .alert("Backup file", isPresented: Binding(get: { importNotice != nil }, set: { if !$0 { importNotice = nil } })) {
            Button("OK") { }
        } message: { Text(importNotice ?? "") }
        .onChange(of: scenePhase) { phase in
            switch phase {
            case .background:
                backgroundedAt = Date()
            case .active:
                if let at = backgroundedAt,
                   Date().timeIntervalSince(at) > 60,
                   !demoMode, !reviewMode {
                    // Robust: any non-idle state drops to the scanner
                    // (Malcolm 2026-08-07: "sometimes didn't return to the
                    // model selection page" — a .connecting/.failed limbo
                    // slipped through the old .ready/.reconnecting cases).
                    switch link.state {
                    case .idle: break
                    default: link.disconnect()
                    }
                }
                backgroundedAt = nil
            default: break
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .rxv2LeaveWeb)) { _ in demoMode = false; reviewMode = false }
        .fullScreenCover(isPresented: $reviewMode) {
            ZStack(alignment: .topTrailing) {
                WebScreen(link: link, replay: true)
                    .ignoresSafeArea()
                Button {
                    reviewMode = false
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                        .padding(10)
                }
            }
        }
        .fullScreenCover(isPresented: $demoMode) {
            ZStack(alignment: .topTrailing) {
                WebScreen(link: link, demo: true, demoDongle: demoDongle)
                    .ignoresSafeArea()
                Button {
                    demoMode = false
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                        .padding(10)
                }
            }
        }
    }
}

extension RootView {
    /// Once per connection: offer any offline edits (SAME model only), then
    /// prefetch the whole session in the background (Malcolm's refinement 1).
    /// A backup file handed to the app by another app: keep it on the phone
    /// as the restore point for the model named inside it.
    private func importBackupFile(_ url: URL) {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let d = try? Data(contentsOf: url) else { importNotice = "Could not read that file."; return }
        let root = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any]
        let model = ((root?["model"] as? String) ?? "").trimmingCharacters(in: .whitespaces)
        guard (root?["format"] as? String) == "rxv2-backup-1", !model.isEmpty else {
            importNotice = "That file is not an LDRC backup."; return
        }
        let r = SessionCache.shared.importRestore(json: d, forModel: model)
        importNotice = r.ok
            ? "Backup for \"\(model)\" is now on this phone (\(r.count) settings). Connect to \(model), open Backup & restore, and tap Restore."
            : "That backup could not be read."
    }

    func onConnected(_ name: String) {
        guard !sessionStarted else { return }
        sessionStarted = true
        let (model, edits) = SessionCache.loadPending()
        if !edits.isEmpty && model == name {
            // Malcolm's rule (2026-08-04): send ONLY when the transmitter is
            // OFF — then the app controls the bank, so edits land in the
            // right place. With the TX live, the physical switch owns the
            // bank and a send could hit the wrong profile.
            link.request(method: "GET", path: "/api/state.json", headers: [:], body: nil) { result in
                var txLive = false
                if case .success(let resp) = result,
                   let obj = try? JSONSerialization.jsonObject(with: resp.body) as? [String: Any],
                   let rf = obj["rf"] as? [String: Any],
                   let lastPkt = rf["last_pkt_ms"] as? Double {
                    // last_pkt_ms is an AGE (ms since the last TX packet;
                    // -1 = never) — NOT a timestamp. Bug found 2026-08-04:
                    // uptime-minus-age made the TX always look off.
                    txLive = lastPkt >= 0 && lastPkt < 3000
                }
                DispatchQueue.main.async {
                    let what = edits.map(\.label).joined(separator: ", ")
                    // Malcolm 2026-08-04: TX on → never offered; edits are
                    // DISCARDED with a clear notice (no stale-edit limbo).
                    if txLive {
                        // Malcolm 2026-08-04: keep the edits — they stay until
                        // overwritten by a newer offline edit (or sent later).
                        // Un-latch so a TX-off reconnect still gets the offer;
                        // the notice itself shows once per launch (no nagging
                        // on every between-flights reconnect).
                        sessionStarted = false
                        guard !txOnNoticeShown else { return }
                        txOnNoticeShown = true
                        pendingEdits = []   // no Send button in this alert
                        pendingSummary = "Your offline edits (\(what)) cannot be sent "
                            + "because the transmitter is on.\n\nThey are kept — "
                            + "connect with the transmitter off to send them."
                        showPendingOffer = true
                        return
                    }
                    // Banks are handled automatically (each edit remembers its
                    // own) — the user needs no bank talk here.
                    pendingEdits = edits
                    pendingSummary = "While offline you edited: \(what).\n\n"
                        + "Send the edits to the model now, or discard them and "
                        + "keep what the model already has?\n\n"
                        + "While sending, keep the transmitter OFF and the "
                        + "model powered."
                    showPendingOffer = true
                }
            }
        }
        SessionPrefetcher.run(link: link)
    }

    func sendPendingEdits() {
        let edits = pendingEdits
        let banked = edits.contains(where: { $0.bank != nil })
        func select(_ b: Int) -> String { "/api/msp?fn=210&data=" + String(format: "%02X", b) }
        // Each edit lands in the bank it was made in: select first (fn=210,
        // 0x80|idx for rates), then write. Bankless edits (gov global) go bare.
        // `orig` = the FC's own banks (MSP 101) noted before the first select:
        // the FC is put back on them BEFORE the save, because the EEPROM save
        // persists the current bank and Rotorflight re-applies the pilot's
        // switch only when it MOVES — a model saved on the last edit's bank
        // would fly on that bank with the switch still saying another.
        var queue: [String] = []
        func buildQueue(orig: (pid: Int, rate: Int)?) {
            var curPid = orig?.pid, curRate = orig?.rate
            for e in edits {
                if let b = e.bank {
                    if b & 0x80 != 0 {
                        if curRate != (b & 0x7F) { queue.append(select(b)); curRate = b & 0x7F }
                    } else if curPid != b {
                        queue.append(select(b)); curPid = b
                    }
                }
                queue.append("/api/msp?fn=\(e.fn)&data=\(e.hex)")
            }
            if let o = orig {
                if curPid != o.pid { queue.append(select(o.pid)) }
                if curRate != o.rate { queue.append(select(0x80 | o.rate)) }
            }
            queue.append("/api/msp?fn=250")                       // save to EEPROM
            if edits.contains(where: { $0.fn == 143 }) {
                queue.append("/api/msp?fn=68")                    // gov config needs an FC reboot
            }
        }
        sendTotal = edits.count + 1
        sendDone = 0
        sendResult = nil
        sendShowing = true
        var failures = 0
        func finish(_ msg: String, keepEdits: Bool) {
            if !keepEdits { SessionCache.savePending(model: "", edits: []) }
            sendResult = msg
            DispatchQueue.main.asyncAfter(deadline: .now() + (keepEdits ? 6 : 3)) {
                sendShowing = false
            }
        }
        func next() {
            guard !queue.isEmpty else {
                if failures == 0 {
                    finish("✅ Edits sent to the model!", keepEdits: false)
                } else {
                    // A step never arrived (model off? radio drop?) — the
                    // edits are NOT lost; offer again next time.
                    finish("⚠️ \(failures) step(s) didn't arrive — the edits are "
                         + "kept. Check the model is powered and try again "
                         + "(transmitter off).", keepEdits: true)
                }
                return
            }
            let p = queue.removeFirst()
            // The send's bank selects must not interleave with the sweep's.
            SessionPrefetcher.lastPageMspMs = Date().timeIntervalSince1970 * 1000
            link.request(method: "GET", path: p, headers: [:], body: nil) { result in
                if case .success(let resp) = result, resp.code == 0 || resp.code == 200 {
                    // step landed
                } else {
                    failures += 1
                }
                sendDone += 1
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { next() }
            }
        }
        // Foolish-user guard: the offer dialog may have sat open a while —
        // re-check the transmitter at PRESS time, not just at connect time.
        link.request(method: "GET", path: "/api/state.json", headers: [:], body: nil) { result in
            var txLive = false
            if case .success(let resp) = result,
               let obj = try? JSONSerialization.jsonObject(with: resp.body) as? [String: Any],
               let rf = obj["rf"] as? [String: Any],
               let lastPkt = rf["last_pkt_ms"] as? Double {
                txLive = lastPkt >= 0 && lastPkt < 3000
            }
            DispatchQueue.main.async {
                if txLive {
                    finish("⚠️ The transmitter came on — nothing was sent. The "
                         + "edits are kept; try again with the transmitter off.",
                           keepEdits: true)
                } else if !banked {
                    buildQueue(orig: nil)
                    sendTotal = queue.count
                    next()
                } else {
                    // Note the FC's own banks before any select (see buildQueue).
                    // Unreadable → nothing is sent: we could neither put the FC
                    // back nor be sure which bank a write landed in.
                    SessionPrefetcher.lastPageMspMs = Date().timeIntervalSince1970 * 1000
                    link.request(method: "GET", path: "/api/msp?fn=101", headers: [:], body: nil) { r in
                        var orig: (pid: Int, rate: Int)? = nil
                        if case .success(let resp) = r, resp.code == 0 || resp.code == 200,
                           let hex = String(data: resp.body, encoding: .utf8) {
                            orig = SessionCache.fcBanks(statusHex: hex)
                        }
                        DispatchQueue.main.async {
                            guard let o = orig else {
                                finish("⚠️ Could not read which bank the flight controller "
                                     + "is on — nothing was sent. The edits are kept; check "
                                     + "the model is powered and try again.", keepEdits: true)
                                return
                            }
                            buildQueue(orig: o)
                            sendTotal = queue.count
                            next()
                        }
                    }
                }
            }
        }
    }
}

struct ScannerView: View {
    // Friendly "when" for the saved reviews: Today / Yesterday keep the time
    // alone, older ones gain a short date (Malcolm 2026-08-22 — several were
    // days old and time alone was ambiguous).
    static func friendlyWhen(_ d: Date) -> String {
        let cal = Calendar.current
        let time = d.formatted(date: .omitted, time: .shortened)
        if cal.isDateInToday(d)     { return "Today \(time)" }
        if cal.isDateInYesterday(d) { return "Yesterday \(time)" }
        let day = d.formatted(.dateTime.day().month(.abbreviated))
        return "\(day), \(time)"
    }

    @EnvironmentObject var link: BleLink
    @Binding var demoMode: Bool
    @Binding var reviewMode: Bool
    @Binding var demoDongle: Bool
    // Auto-connect to the receiver used last time (Malcolm 2026-08-16):
    // short cancellable countdown once it appears; the list stays live so a
    // different model can be chosen instead.
    @AppStorage("lastDeviceName") private var lastUsedName = ""
    @State private var autoTarget: String? = nil
    @State private var autoWork: DispatchWorkItem? = nil
    @State private var sessionRev = 0   // bump to refresh the saved-session list after a delete
    // Model photos (Malcolm 2026-09-05): long-press a receiver → choose /
    // take / remove. photoRev redraws the thumbnails after a change.
    @State private var photoRev = 0
    @State private var photoFor: String? = nil
    @State private var pickerItem: PhotosPickerItem? = nil
    @State private var showPhotoPicker = false
    @State private var showCamera = false
    /// A receiver tapped while its signal was too weak to be worth trying.
    @State private var weakTarget: BleLink.Discovered? = nil

    private func cancelAuto() {
        autoWork?.cancel(); autoWork = nil; autoTarget = nil
        link.scannerAutoDone = true
    }
    private func maybeArmAuto(_ list: [BleLink.Discovered]) {
        // Instant (Malcolm 2026-08-17: "straight to the front screen without
        // going round the houses") — the moment the remembered receiver is
        // spotted, connect. No countdown, no banner. Choosing a different
        // model is still easy: disconnect returns here with auto-connect
        // disarmed for the rest of the launch (scannerAutoDone).
        guard !link.scannerAutoDone, !lastUsedName.isEmpty,
              let d = list.first(where: { $0.name == lastUsedName }) else { return }
        // Never connect by ourselves to something we can already see is too far:
        // it half-connects and everything after that is slow (Malcolm 2026-09-12,
        // Dongle 4 at -94 dBm). Show the list instead, with the reason on the row.
        if BleLink.tooWeak(d.rssi) { cancelAuto(); link.scannerAutoDone = true; return }
        // More than one receiver in range: show the list and let the pilot
        // choose (Malcolm 2026-09-11: the app went to the dongle when he wanted
        // Test1). Alone, connect as before - after a one-second look-around so
        // a second receiver that advertises a beat later still gets its say.
        if list.count > 1 { cancelAuto(); return }
        if autoTarget == d.name { return }          // already looking around
        autoTarget = d.name
        let name = d.name
        let work = DispatchWorkItem {
            guard !link.scannerAutoDone, autoTarget == name else { return }
            if link.found.count > 1 { cancelAuto(); return }
            guard let now = link.found.first(where: { $0.name == name }) else { autoTarget = nil; return }
            if BleLink.tooWeak(now.rssi) { cancelAuto(); link.scannerAutoDone = true; return }
            link.scannerAutoDone = true
            autoTarget = nil
            link.connect(now)
        }
        autoWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0, execute: work)
    }

    var body: some View {
        List {
            Section {
                // "Searching…" lives IN the list, not floating over it: as an
                // overlay it was drawn centred on the screen, on top of the
                // Review rows and the demo button (Malcolm 2026-09-06 screenshot).
                if link.found.isEmpty {
                    HStack(alignment: .top, spacing: 12) {
                        ProgressView()
                            .padding(.top, 2)
                        VStack(alignment: .leading, spacing: 4) {
                            Label("Searching…", systemImage: "dot.radiowaves.left.and.right")
                                .font(.headline)
                            Text(statusText)
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 6)
                }
                ForEach(link.found) { d in
                    Button {
                        cancelAuto()
                        // Do not start a connection the signal says will fail
                        // (Malcolm 2026-09-12: "perhaps it'd be better to not
                        // even try if it's too weak?"). RSSI wanders, so this
                        // asks rather than forbids.
                        if BleLink.tooWeak(d.rssi) { weakTarget = d } else {
                            lastUsedName = d.name
                            link.connect(d)
                        }
                    } label: {
                        HStack {
                            let _ = photoRev
                            ModelThumb(name: d.name, side: 60)
                            VStack(alignment: .leading) {
                                Text(d.name).font(.headline)
                                Text("\(BleLink.signalWord(d.rssi)) — \(d.rssi) dBm"
                                     + (BleLink.tooWeak(d.rssi) ? " — get closer" : ""))
                                    .font(.caption)
                                    .foregroundStyle(BleLink.tooWeak(d.rssi) ? Color.orange : Color.secondary)
                            }
                            if d.name == lastUsedName {
                                Image(systemName: "clock.arrow.circlepath")
                                    .foregroundStyle(.secondary)
                                    .accessibilityLabel("used last time")
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundStyle(.tertiary)
                        }
                    }
                    .contextMenu {
                        Button { photoFor = d.name; showPhotoPicker = true } label: { Label("Choose photo…", systemImage: "photo") }
                        if UIImagePickerController.isSourceTypeAvailable(.camera) {
                            Button { photoFor = d.name; showCamera = true } label: { Label("Take photo…", systemImage: "camera") }
                        }
                        if ModelPhotos.has(d.name) {
                            Button(role: .destructive) { ModelPhotos.remove(d.name); photoRev += 1 } label: { Label("Remove photo", systemImage: "trash") }
                        }
                    }
                }
            } header: {
                Text(headerText)
            } footer: {
                Text("Power the receiver with the transmitter OFF so its "
                   + "config radios come up (same rule as the WiFi portal). "
                   + "Press and hold a receiver to give it a photograph. "
                   + "Not everybody has an iPhone — the WiFi web interface "
                   + "still works exactly as before.")
            }
            // Recordings come AFTER the live receivers (Malcolm 2026-09-11 tapped
            // "Review: Goblin770" at the top and took it for a live connection).
            // One recording per MODEL (Malcolm 2026-08-04): connecting a
            // different model parks this one's session, never erases it.
            let _ = sessionRev   // touch so a delete forces this list to recompute
            let sessions = SessionCache.savedSessions()
            if !sessions.isEmpty {
                Section {
                    ForEach(sessions, id: \.model) { s in
                        Button {
                            SessionCache.shared.activate(model: s.model)
                            reviewMode = true
                        } label: {
                            HStack(spacing: 10) {
                                let _ = photoRev
                                ModelThumb(name: s.model, side: 44)
                                VStack(alignment: .leading) {
                                    Text("Review:  \(s.model)").font(.headline)
                                    Text(Self.friendlyWhen(s.savedAt)).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                        // Swipe left to delete an old review (Malcolm
                        // 2026-08-22). allowsFullSwipe:false so it takes a
                        // deliberate tap on Delete, not an accidental flick —
                        // these hold flight recordings.
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                SessionCache.deleteSession(model: s.model)
                                sessionRev += 1
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                    }
                } footer: {
                    Text("Flight data and Rotorflight settings recorded during each "
                       + "model's last connection — browse them with everything "
                       + "switched off.")
                }
            }
            // A real, REACHABLE receiver in sight → the demo offer just muddies
            // the water. But a receiver that is merely *visible* and too far to
            // connect is not a reason to take the demo away (Malcolm 2026-09-13:
            // "I wanted to load the demo, but was not able to when a slightly
            // out of range dongle was discovered"). Same trap would catch an App
            // Review tester with any stray LDRC board in the building.
            if link.found.allSatisfy({ BleLink.tooWeak($0.rssi) }) {
                // Two demos, chosen here (Malcolm 2026-09-11): the dongle
                // switch inside the demo was buried too deep, so it is gone.
                Section {
                    Button {
                        demoDongle = false; BleSchemeHandler.demoDongle = false; demoMode = true
                    } label: {
                        Label("No receiver yet?  Try the receiver demo",
                              systemImage: "theatermasks")
                    }
                    Button {
                        demoDongle = true; BleSchemeHandler.demoDongle = true; demoMode = true
                    } label: {
                        Label("Try the dongle demo", systemImage: "theatermasks")
                    }
                } footer: {
                    Text("The same pages on canned data. The receiver demo flies a model; the dongle demo shows the app on a Rotorflight dongle.")
                }
            }
        }
        .navigationTitle("RXV2 Receivers")
        .photosPicker(isPresented: $showPhotoPicker, selection: $pickerItem, matching: .images)
        .onChange(of: pickerItem) { item in
            guard let item, let name = photoFor else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self), let img = UIImage(data: data) {
                    ModelPhotos.save(name, img)
                    await MainActor.run { photoRev += 1 }
                }
                await MainActor.run { pickerItem = nil }
            }
        }
        .sheet(isPresented: $showCamera) {
            CameraPicker { img in
                if let name = photoFor { ModelPhotos.save(name, img); photoRev += 1 }
            }
        }
        .alert("Too far away", isPresented: Binding(get: { weakTarget != nil },
                                                    set: { if !$0 { weakTarget = nil } })) {
            Button("Cancel", role: .cancel) { weakTarget = nil }
            Button("Try anyway") {
                if let d = weakTarget { lastUsedName = d.name; link.connect(d) }
                weakTarget = nil
            }
        } message: {
            if let d = weakTarget {
                Text("\(d.name) is only \(d.rssi) dBm — too weak to connect reliably. Walk closer to the model and it will connect at once.")
            }
        }
        .onReceive(link.$found) { maybeArmAuto($0) }
        .onAppear { link.startScan() }
        .onDisappear { link.stopScan() }
        .refreshable { link.startScan() }
    }

    private var headerText: String {
        switch link.state {
        case .connecting(let n): return "Connecting to \(n)…"
        case .failed(let m):     return m
        default:                 return "Nearby receivers"
        }
    }

    private var statusText: String {
        if let note = link.connectNote { return note }
        switch link.state {
        case .failed(let m): return m
        default: return "Bring the receiver within a few metres and make sure it is in config mode (LED behaviour as usual)."
        }
    }
}
