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
    @State private var demoRole = "receiver"  // which demo: receiver | dongle | simif
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
        Group {
            switch link.state {
            case .ready(let name), .reconnecting(let name):
                // Full-screen, like the web UI added to the home screen, and
                // OUTSIDE the navigation stack: connecting tears the whole
                // stack down, pushed pages included (2026-09-19 — with the
                // pages as the stack's root, the pushed Connect page stayed
                // on top and a live link looked like "Searching…").
                // Disconnect lives on the page's Bluetooth badge.
                WebScreen(link: link)
                    .ignoresSafeArea()
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
                NavigationStack {
                    ScannerView(demoMode: $demoMode, reviewMode: $reviewMode, demoRole: $demoRole)
                        .onAppear {
                            sessionStarted = false
                            // "--demo" launch argument: straight into demo mode (website screenshots)
                            if ProcessInfo.processInfo.arguments.contains("--demo") { demoMode = true }
                        }
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
                    case .idle, .scanning, .failed: break   // nothing to hang up
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
                WebScreen(link: link, demo: true, demoRole: demoRole)
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
    @Binding var demoRole: String
    /// The "?" every other screen has (Malcolm 2026-09-19).
    @State private var showHelp = false

    // Four doors instead of one crowded list (Malcolm 2026-09-19): Connect,
    // Reviews, Backups, Demos — each a button in the app's usual style, each
    // its own page. Scanning still runs HERE, so the model used last still
    // connects by itself without going round the houses.
    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                HomeMasthead()

                // Only a problem is worth saying here. "Connecting…" speaks for
                // itself — the model's own pages arrive a second later
                // (Malcolm 2026-09-19: "a superfluous message").
                if case .failed(let m) = link.state {
                    noticeCard(m, systemImage: "exclamationmark.triangle")
                }

                NavigationLink {
                    ConnectListView()
                } label: {
                    HomeTile(icon: "\u{1F4E1}", tint: Color(red: 0.42, green: 0.67, blue: 0.37),
                             title: "Connect")
                }
                NavigationLink {
                    ReviewsListView(reviewMode: $reviewMode)
                } label: {
                    HomeTile(icon: "\u{1F570}\u{FE0F}", tint: Color(red: 0.29, green: 0.56, blue: 0.79),
                             title: "Reviews")
                }
                NavigationLink {
                    BackupsListView()
                } label: {
                    HomeTile(icon: "\u{1F4BE}", tint: Color(red: 0.79, green: 0.54, blue: 0.29),
                             title: "Backups")
                }
                NavigationLink {
                    DemosView(demoMode: $demoMode, demoRole: $demoRole)
                } label: {
                    HomeTile(icon: "\u{1F3AD}", tint: Color(red: 0.42, green: 0.56, blue: 0.69),
                             title: "Demos")
                }
            }
            .padding(18)
        }
        .background(ScannerBackdrop())
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showHelp = true } label: {
                    Image(systemName: "questionmark.circle").font(.title3)
                }
                .accessibilityLabel("Help")
            }
        }
        .sheet(isPresented: $showHelp) { ScannerHelpView(page: .home) }
        .onAppear { link.stopScan() }
    }

    @ViewBuilder private func noticeCard(_ text: String, systemImage: String) -> some View {
        Label(text, systemImage: systemImage)
            .font(.callout)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color(.secondarySystemGroupedBackground),
                        in: RoundedRectangle(cornerRadius: 14))
    }
}

extension Color {
    /// The web pages' ink (#2c3e50), lightened for a dark phone.
    static let ldrcInk = Color(uiColor: UIColor { t in
        t.userInterfaceStyle == .dark ? UIColor(white: 0.93, alpha: 1)
                                      : UIColor(red: 0.173, green: 0.243, blue: 0.314, alpha: 1) })
    /// The app's teal (#5fa099).
    static let ldrcTeal = Color(uiColor: UIColor { t in
        t.userInterfaceStyle == .dark ? UIColor(red: 0.46, green: 0.74, blue: 0.71, alpha: 1)
                                      : UIColor(red: 0.373, green: 0.627, blue: 0.600, alpha: 1) })
}

/// Every page's heading: the web pages' h1 — light, letter-spaced, centred on
/// a solid chip (Malcolm 2026-09-19: the inline navigation titles were "a
/// little disappointing").
struct PageHeading: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text)
            .font(.system(size: 26, weight: .light))
            .tracking(2)
            .foregroundStyle(Color.ldrcInk)
            .lineLimit(1).minimumScaleFactor(0.6)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 13)
            .background(Color(.secondarySystemGroupedBackground),
                        in: RoundedRectangle(cornerRadius: 16))
            .shadow(color: .black.opacity(0.10), radius: 3, y: 2)
            .padding(.horizontal, 18)
            .padding(.top, 2)
            .padding(.bottom, 8)
    }
}

/// The front door's masthead. It carries more weight than a page heading
/// because it is the first thing anyone sees (Malcolm 2026-09-19: "should be
/// a bit more IMPORTANT looking because it's the very first").
struct HomeMasthead: View {
    var body: some View {
        VStack(spacing: 7) {
            Text("LockDown Radio Control")
                .font(.system(size: 29, weight: .semibold))
                .foregroundStyle(Color.ldrcInk)
                .multilineTextAlignment(.center)
                .lineLimit(2).minimumScaleFactor(0.65)
            Text("RXV2")
                .font(.system(size: 15, weight: .semibold))
                .tracking(7)
                .foregroundStyle(Color.ldrcTeal)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 22).padding(.horizontal, 18)
        .background(Color(.secondarySystemGroupedBackground),
                    in: RoundedRectangle(cornerRadius: 22))
        .shadow(color: .black.opacity(0.14), radius: 6, y: 3)
        .padding(.bottom, 4)
    }
}

/// A big coloured button in the app's usual style: what it does, and one line
/// saying what is behind it.
struct HomeTile: View {
    /// The same emoji the receiver's own pages use for the same idea
    /// (Malcolm 2026-09-19: "might be better to use same ones as on this
    /// page" — Fly now already carries the helicopter and the aeroplane).
    let icon: String
    let tint: Color
    let title: String

    var body: some View {
        HStack(spacing: 16) {
            Text(icon).font(.title2).frame(width: 52, alignment: .leading)
            Text(title).font(.title3.weight(.semibold))
            Spacer(minLength: 8)
            Image(systemName: "chevron.right").font(.footnote).opacity(0.85)
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 18).padding(.vertical, 22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(tint, in: RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.18), radius: 4, y: 2)
    }
}

/// CONNECT — the live search that used to be the whole first screen.
struct ConnectListView: View {
    @EnvironmentObject var link: BleLink
    @AppStorage("lastDeviceName") private var lastUsedName = ""
    @State private var photoRev = 0
    @State private var photoFor: String? = nil
    @State private var pickerItem: PhotosPickerItem? = nil
    @State private var showPhotoPicker = false
    @State private var showCamera = false
    @State private var weakTarget: BleLink.Discovered? = nil
    // Auto-connect to the receiver used last time (Malcolm 2026-08-16) — but
    // only once Connect has been tapped (2026-09-19: "leaping directly to the
    // last used model should only happen AFTER hitting connect").
    @State private var autoTarget: String? = nil
    @State private var autoWork: DispatchWorkItem? = nil
    @State private var showHelp = false
    @Environment(\.scenePhase) private var scenePhase

    private func cancelAuto() {
        autoWork?.cancel(); autoWork = nil; autoTarget = nil
        link.scannerAutoDone = true
    }
    private func maybeArmAuto(_ list: [BleLink.Discovered]) {
        guard !link.scannerAutoDone, !lastUsedName.isEmpty,
              let d = list.first(where: { $0.name == lastUsedName }) else { return }
        // Never connect by ourselves to something we can already see is too far:
        // it half-connects and everything after that is slow (Malcolm 2026-09-12).
        if BleLink.tooWeak(d.rssi) { cancelAuto(); link.scannerAutoDone = true; return }
        // More than one in range: let the pilot choose (Malcolm 2026-09-11).
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
                // What the app is doing, ON THIS PAGE and on a card — a timed-out
                // connection used to fail in silence here (Malcolm 2026-09-19).
                switch link.state {
                case .connecting(let n):
                    HStack(spacing: 12) {
                        ProgressView()
                        Text("Connecting to \(n)…").font(.headline)
                    }
                    .padding(.vertical, 6)
                case .failed(let m):
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "exclamationmark.triangle").foregroundStyle(.orange)
                        Text(m).font(.callout).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.vertical, 6)
                default:
                    if link.found.isEmpty {
                        HStack(alignment: .top, spacing: 12) {
                            ProgressView().padding(.top, 2)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(link.scanSeconds >= 12 ? "No receivers or dongles found nearby"
                                     : link.scanSeconds < 3 ? "Searching…" : "Searching… \(link.scanSeconds) s")
                                    .font(.headline)
                                    .fixedSize(horizontal: false, vertical: true)
                                if link.scanSeconds >= 12 {
                                    Text("Power the model with the transmitter OFF, and bring the phone within a few metres. If it is on, another phone or tablet may be holding it: a receiver takes one at a time.")
                                        .font(.footnote).foregroundStyle(.secondary)
                                        .fixedSize(horizontal: false, vertical: true)
                                    Text("Still looking…")
                                        .font(.caption2).foregroundStyle(.tertiary)
                                }
                            }
                        }
                        .padding(.vertical, 6)
                    }
                }
                ForEach(link.found) { d in
                    Button {
                        // A deliberate choice here ends any automatic connecting.
                        cancelAuto()
                        // Do not start a connection the signal says will fail
                        // (Malcolm 2026-09-12). RSSI wanders, so this asks.
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
                            Image(systemName: "chevron.right").foregroundStyle(.tertiary)
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
            }
            .listRowBackground(Color(.secondarySystemGroupedBackground))
        }
        .scrollContentBackground(.hidden)
        .background(ScannerBackdrop())
        .safeAreaInset(edge: .top) { PageHeading("Connect") }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showHelp = true } label: { Image(systemName: "questionmark.circle").font(.title3) }
                    .accessibilityLabel("Help")
            }
        }
        .sheet(isPresented: $showHelp) { ScannerHelpView(page: .connect, log: link.log) }
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
        // The search must never be left dead on this page: if the link falls
        // idle here (a drop's ride-out gave up, the app was away), search again.
        .onChange(of: link.state) { st in if case .idle = st { link.startScan() } }
        .onChange(of: scenePhase) { ph in if ph == .active { link.startScan() } }
        .onAppear { link.startScan() }
        .onDisappear { link.stopScan() }
        .refreshable { link.startScan() }
    }

}

/// REVIEWS — one recording per model, made automatically at every connection.
struct ReviewsListView: View {
    @Binding var reviewMode: Bool
    @State private var showHelp = false
    @State private var sessionRev = 0
    @State private var photoRev = 0

    var body: some View {
        let _ = sessionRev
        let sessions = SessionCache.savedSessions()
        List {
            if sessions.isEmpty {
                Section {
                    Text("Nothing recorded yet. Connect to a model and one is kept for you.")
                        .font(.callout).foregroundStyle(.secondary)
                }
                .listRowBackground(Color(.secondarySystemGroupedBackground))
            } else {
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
                                    Text(s.model).font(.headline)
                                    Text("Last session · \(ScannerView.friendlyWhen(s.savedAt))")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right").foregroundStyle(.tertiary)
                            }
                        }
                        // Deliberate tap on Delete, not an accidental flick —
                        // these hold flight recordings (Malcolm 2026-08-22).
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                SessionCache.deleteSession(model: s.model)
                                sessionRev += 1
                            } label: { Label("Delete", systemImage: "trash") }
                        }
                    }
                }
                .listRowBackground(Color(.secondarySystemGroupedBackground))
            }
        }
        .scrollContentBackground(.hidden)
        .background(ScannerBackdrop())
        .safeAreaInset(edge: .top) { PageHeading("Reviews") }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showHelp = true } label: { Image(systemName: "questionmark.circle").font(.title3) }
                    .accessibilityLabel("Help")
            }
        }
        .sheet(isPresented: $showHelp) { ScannerHelpView(page: .reviews) }
    }
}

/// BACKUPS — what this phone has saved for each model, and when.
struct BackupsListView: View {
    @State private var showHelp = false
    @State private var rev = 0
    @State private var opened: OpenedBackup? = nil
    struct OpenedBackup: Identifiable { let id: String; let model: String; let when: String; let explicit: Bool }

    var body: some View {
        let _ = rev
        // Two kinds per model since 0.9.800 — key on both so SwiftUI keeps
        // them apart.
        let backups = SessionCache.savedBackups()
            .map { (key: "\($0.model)|\($0.explicit)", model: $0.model, savedAt: $0.savedAt,
                    explicit: $0.explicit, items: $0.items) }
        List {
            if backups.isEmpty {
                Section {
                    Text("No backups yet. Open a model, go to Rotorflight → Backup & restore, and tap Back up: the settings are kept here on the phone.")
                        .font(.callout).foregroundStyle(.secondary)
                }
                .listRowBackground(Color(.secondarySystemGroupedBackground))
            } else {
                Section {
                    ForEach(backups, id: \.key) { b in
                        Button {
                            opened = OpenedBackup(id: b.key, model: b.model,
                                                  when: ScannerView.friendlyWhen(b.savedAt),
                                                  explicit: b.explicit)
                        } label: {
                            HStack(spacing: 10) {
                                ModelThumb(name: b.model, side: 44)
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(b.model).font(.headline)
                                    Text("\(b.explicit ? "Your backup" : "Automatic") · \(ScannerView.friendlyWhen(b.savedAt))")
                                        .font(.caption).foregroundStyle(.secondary)
                                    HStack(spacing: 6) {
                                        Image(systemName: "list.bullet.rectangle")
                                        Text("What\u{2019}s in it — \(b.items) settings")
                                    }
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(Color.accentColor)
                                    .padding(.vertical, 6).padding(.horizontal, 11)
                                    .background(Color.accentColor.opacity(0.14), in: Capsule())
                                    .padding(.top, 1)
                                }
                                Spacer()
                                Image(systemName: "chevron.right").font(.footnote).foregroundStyle(.tertiary)
                            }
                        }
                    }
                }
                .listRowBackground(Color(.secondarySystemGroupedBackground))
            }
        }
        .scrollContentBackground(.hidden)
        .background(ScannerBackdrop())
        .safeAreaInset(edge: .top) { PageHeading("Backups") }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showHelp = true } label: { Image(systemName: "questionmark.circle").font(.title3) }
                    .accessibilityLabel("Help")
            }
        }
        .sheet(isPresented: $showHelp) { ScannerHelpView(page: .backups) }
        .sheet(item: $opened) { b in BackupContentsView(model: b.model, when: b.when, explicit: b.explicit) }
    }
}

/// WHAT'S IN THE BACKUP — the same plain lines the receiver's own Backup &
/// restore page shows, for a backup this phone holds (Malcolm 2026-09-19).
struct BackupContentsView: View {
    let model: String
    let when: String
    let explicit: Bool
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        let lines = SessionCache.backupSummary(model: model, mine: explicit)
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("\(model) — \(explicit ? "your backup" : "automatic, taken when you connected") · \(when)")
                        .font(.callout).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(12)
                        .background(Color(.secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 12))
                    if lines.isEmpty {
                        Text("Nothing readable in this backup yet.")
                            .font(.callout)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                            .background(Color(.secondarySystemGroupedBackground),
                                        in: RoundedRectangle(cornerRadius: 12))
                    } else {
                        VStack(alignment: .leading, spacing: 9) {
                            ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                                Text(line).font(.callout)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(14)
                        .background(Color(.secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 12))
                        Text(explicit
                             ? "Rotorflight settings only — no flight data. This one is yours: the app never overwrites it. Connect to the model and use Backup & restore to put it back."
                             : "Rotorflight settings only — no flight data. This copy is refreshed every time you connect. Connect to the model and use Backup & restore to put it back.")
                            .font(.footnote).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                            .background(Color(.secondarySystemGroupedBackground),
                                        in: RoundedRectangle(cornerRadius: 12))
                    }
                }
                .padding(18)
            }
            .background(ScannerBackdrop())
            .safeAreaInset(edge: .top) { PageHeading("What\u{2019}s in the backup") }
            .navigationTitle("")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}

/// DEMOS — the same pages on canned data, for anyone with no hardware.
struct DemosView: View {
    @Binding var demoMode: Bool
    @Binding var demoRole: String
    @State private var showHelp = false

    private func play(_ role: String) {
        demoRole = role
        BleSchemeHandler.demoRole = role
        demoMode = true
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                Button { play("receiver") } label: {
                    HomeTile(icon: "\u{1F681}\u{2708}\u{FE0F}", tint: Color(red: 0.42, green: 0.67, blue: 0.37),
                             title: "Receiver")
                }
                Button { play("dongle") } label: {
                    HomeTile(icon: "\u{1F50C}", tint: Color(red: 0.37, green: 0.63, blue: 0.60),
                             title: "Rotorflight dongle")
                }
                Button { play("simif") } label: {
                    HomeTile(icon: "\u{1F3AE}", tint: Color(red: 0.42, green: 0.56, blue: 0.69),
                             title: "Simulator interface")
                }
            }
            .padding(18)
        }
        .background(ScannerBackdrop())
        .safeAreaInset(edge: .top) { PageHeading("Demos") }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showHelp = true } label: { Image(systemName: "questionmark.circle").font(.title3) }
                    .accessibilityLabel("Help")
            }
        }
        .sheet(isPresented: $showHelp) { ScannerHelpView(page: .demos) }
    }
}

/// The flying-field photograph the web pages use (`style.css` .bg-photo),
/// with the same wash over it so headings and footnotes stay legible against
/// sky and meadow. Loaded from the bundled webroot, so there is one copy of
/// the picture in the app (Malcolm 2026-09-19: make the first screen look
/// "more like our other screens").
struct ScannerBackdrop: View {
    static let photo: UIImage? = {
        guard let u = Bundle.main.url(forResource: "flying-field", withExtension: "jpg",
                                      subdirectory: "webroot"),
              let d = try? Data(contentsOf: u) else { return nil }
        return UIImage(data: d)
    }()

    var body: some View {
        ZStack {
            Color(.systemGroupedBackground)
            if let img = Self.photo {
                Image(uiImage: img).resizable().scaledToFill().opacity(0.92)
            }
            // The web pages' own vignette (style.css .bg-wash) and nothing
            // more: bright at the top so headings read against the sky,
            // darker at the foot so cards read against the meadow. The
            // photograph stays in FULL COLOUR (Malcolm 2026-09-19).
            RadialGradient(colors: [Color.white.opacity(0.20), .clear],
                           center: UnitPoint(x: 0.5, y: 0.08),
                           startRadius: 0, endRadius: 620)
            RadialGradient(colors: [Color(red: 0.18, green: 0.27, blue: 0.35).opacity(0.18), .clear],
                           center: UnitPoint(x: 0.5, y: 1.0),
                           startRadius: 0, endRadius: 700)
        }
        .ignoresSafeArea()
    }
}

/// The scanner's "?" — the first screen now explains itself as fully as every
/// other page does, instead of carrying blocks of small print.
struct ScannerHelpView: View {
    enum Page { case home, connect, reviews, backups, demos }
    let page: Page
    /// The link's own account of itself (Connect only): read, don't guess.
    var log: [String] = []
    @Environment(\.dismiss) private var dismiss

    struct Topic: Identifiable {
        let id = UUID()
        let icon: String
        let title: String
        let body: String
    }

    private var heading: String {
        switch page {
        case .home:    return "About this app"
        case .connect: return "About Connect"
        case .reviews: return "About Reviews"
        case .backups: return "About Backups"
        case .demos:   return "About the demos"
        }
    }

    private var intro: String {
        switch page {
        case .home:
            return "Four doors: Connect to a model, browse a Review of an earlier session, see the Backups this phone holds, or try a Demo with no hardware at all."
        case .connect:
            return "Find a LockDown receiver or dongle over Bluetooth and open its pages."
        case .reviews:
            return "A recording of a model's last connection, kept for you automatically."
        case .backups:
            return "The Rotorflight settings this phone has saved for each model."
        case .demos:
            return "The whole app on canned data — every page, nothing connected."
        }
    }

    private var topics: [Topic] {
        switch page {
        case .home: return [
            .init(icon: "antenna.radiowaves.left.and.right", title: "Connect",
                  body: "Searches for receivers and dongles nearby and opens the one you "
                      + "choose. The model you used last connects by itself once you are in "
                      + "there, if it is the only one in range."),
            .init(icon: "clock", title: "Reviews",
                  body: "One recording per model, made at every connection: the flights and "
                      + "the settings as they were, to go through indoors with everything "
                      + "switched off."),
            .init(icon: "tray.and.arrow.down", title: "Backups",
                  body: "What this phone has saved for each model, and when — settings you "
                      + "can put back if a change goes wrong."),
            .init(icon: "theatermasks", title: "Demos",
                  body: "The same pages driven by canned data: a receiver in a model, a "
                      + "Rotorflight dongle, or a simulator interface. Nothing to buy first."),
            .init(icon: "globe", title: "No phone needed at all",
                  body: "Everything here is also in the receiver's own WiFi pages, in any web "
                      + "browser. The app simply carries the same pages over Bluetooth, so "
                      + "there is no network to switch at the field."),
        ]
        case .connect: return [
            .init(icon: "power", title: "Getting a model to appear",
                  body: "Power the model with the transmitter OFF, so the board's own config "
                      + "radios come up — the same rule as the WiFi portal. A dongle has no "
                      + "transmitter of its own, so just power the model it is plugged into. "
                      + "Bring the phone within a few metres."),
            .init(icon: "wifi", title: "Signal strength",
                  body: "Each row says how strong the signal is. Below about −85 dBm a "
                      + "connection half-forms and everything afterwards is slow, so the app "
                      + "asks before trying rather than leaving you to guess."),
            .init(icon: "clock.arrow.circlepath", title: "The model you used last",
                  body: "It carries a small clock, and connects by itself when it is the only "
                      + "board in range. With more than one in range the list waits for you "
                      + "to choose."),
            .init(icon: "photo", title: "Photographs",
                  body: "Press and hold any row to give that board a photograph of its "
                      + "model — quicker to recognise than a name when several are similar."),
        ]
        case .reviews: return [
            .init(icon: "clock", title: "What a review holds",
                  body: "The flights and the black box, and every Rotorflight setting as it "
                      + "was at that connection. Enough to sit indoors and go through a "
                      + "model with everything switched off."),
            .init(icon: "square.stack.3d.up", title: "One per model",
                  body: "Connecting a different model never erases another's. A review is "
                      + "kept until you swipe it away."),
            .init(icon: "lifepreserver", title: "The safety net",
                  body: "A review can also put a model's tuning back — which is what saves "
                      + "the day when no backup was ever made."),
            .init(icon: "tray.and.arrow.down", title: "Not a backup",
                  body: "A backup is one you make on purpose, holds the settings only, and "
                      + "is what you should take before changing anything. A review is a "
                      + "record of what happened."),
        ]
        case .backups: return [
            .init(icon: "tray.and.arrow.down", title: "What a backup is",
                  body: "Every Rotorflight setting the model had when you tapped Back up: "
                      + "PIDs, rates, governor, servos, the lot. No flight data."),
            .init(icon: "iphone", title: "Where it lives",
                  body: "Here, on the phone — one per model, so it survives anything that "
                      + "happens to the model or its card. You can also send one to yourself "
                      + "as a file and open it again later."),
            .init(icon: "plus.circle", title: "Making one",
                  body: "Connect to the model, open Rotorflight → Backup & restore, and tap "
                      + "Back up. Do it before you change anything, and after a session you "
                      + "are happy with."),
            .init(icon: "arrow.uturn.backward", title: "Putting it back",
                  body: "On the same page, with the transmitter off and blades off. The app "
                      + "writes each setting and reads it back to check it landed."),
            .init(icon: "list.bullet.rectangle", title: "What's in one",
                  body: "Tap any model here to see what its backup holds, folded into plain "
                      + "lines — \"PIDs — banks 1–6\", \"Servos — 8\" — so a glance says whether "
                      + "everything was saved."),
            .init(icon: "checkmark.seal", title: "Two kinds, both kept",
                  body: "“Your backup” is one you asked for, and nothing ever overwrites "
                      + "it — only another Back up replaces it. “Automatic” is the copy the "
                      + "app takes by itself each time you connect with the transmitter off. "
                      + "Both are kept side by side, and Backup & restore offers each by "
                      + "name and date."),
            .init(icon: "arrow.uturn.backward.circle", title: "What the automatic copy is for",
                  body: "It holds the settings as they were WHEN YOU CONNECTED, before "
                      + "anything you changed in this session — so it undoes an afternoon's "
                      + "experimenting. It is not an archive: next time you connect it is "
                      + "taken again, and then it holds your changes too. A change that "
                      + "restarts the receiver (protocol, name, WiFi) refreshes it on the "
                      + "spot, so that undo is gone. Anything you want to keep beyond today "
                      + "belongs in your own backup."),
            .init(icon: "airplane.circle", title: "Never while you fly",
                  body: "Arming takes the receiver's Bluetooth down, so nothing can be read "
                      + "in the air at all. A backup also refuses to start if the "
                      + "transmitter is on, and stops at once if it comes on part way "
                      + "through — a half-read sweep is never kept."),
        ]
        case .demos: return [
            .init(icon: "cpu", title: "One board, three jobs",
                  body: "Every demo here is the same little XIAO ESP32-S3 running the same "
                      + "firmware. What it does depends only on what is fitted to it and "
                      + "which role you choose in its settings — not on buying a different "
                      + "product."),
            .init(icon: "airplane", title: "Receiver",
                  body: "With transceivers fitted it flies the model: it takes your "
                      + "transmitter's signal and drives the flight controller, records the "
                      + "flight, and gives you every Rotorflight page from your phone."),
            .init(icon: "cable.connector", title: "Rotorflight dongle",
                  body: "The same board with no transceivers, plugged into a flight "
                      + "controller. Your own radio and receiver still fly the model; the "
                      + "dongle just gives the app to any Rotorflight helicopter."),
            .init(icon: "gamecontroller", title: "Simulator interface",
                  body: "The same bare board again, with a receiver wired to it, turning "
                      + "that receiver into a USB joystick for RealFlight or neXt. It works "
                      + "out for itself whether the receiver speaks CRSF, SBUS, IBUS or PPM."),
            .init(icon: "sparkles", title: "And a receiver does all three",
                  body: "A LockDown receiver needs no dongle for the app, and flies a "
                      + "simulator on its own over USB. The other two roles are for spare "
                      + "boards and for people flying someone else's radio."),
        ]
        }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text(intro)
                        .font(.callout)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 12))
                    ForEach(topics) { t in
                        VStack(alignment: .leading, spacing: 6) {
                            Label(t.title, systemImage: t.icon).font(.headline)
                            Text(t.body).font(.callout)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 12))
                    }
                    if !log.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Label("What the app did", systemImage: "list.bullet.rectangle").font(.headline)
                            ForEach(Array(log.suffix(30).enumerated()), id: \.offset) { _, line in
                                Text(line).font(.system(.caption, design: .monospaced))
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 12))
                    }
                    if page == .home {
                        Text("App version \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "")")
                            .font(.footnote).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity)
                    }
                }
                .padding(18)
            }
            .background(ScannerBackdrop())
            .safeAreaInset(edge: .top) { PageHeading(heading) }
            .navigationTitle("")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
        }
    }
}
