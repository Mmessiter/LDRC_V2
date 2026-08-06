// LockDownRadioControl — RXV2App  ::  RXV2App.swift
//
// Scan for receivers advertising the RXV2 config service, connect, and show
// the receiver's own web UI over Bluetooth. The web interface over WiFi is
// untouched — this app is simply a second, fuss-free door to the same
// configuration engine.

import SwiftUI

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
    @State private var demoMode = false
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
                ScannerView(demoMode: $demoMode, reviewMode: $reviewMode)
                    .onAppear { sessionStarted = false }
            }
        }
        // No receiver? Let anyone play: canned data from a real receiver,
        // with animated channels.
        // Armchair review (Malcolm's lodge idea): the recorded last session
        // served to the same pages — receiver asleep in its case.
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
                WebScreen(link: link, demo: true)
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
        // Each edit lands in the bank it was made in: select first (fn=210,
        // 0x80|idx for rates), then write. Bankless edits (gov global) go bare.
        var queue: [String] = []
        for e in edits {
            if let b = e.bank {
                queue.append("/api/msp?fn=210&data=" + String(format: "%02X", b))
            }
            queue.append("/api/msp?fn=\(e.fn)&data=\(e.hex)")
        }
        queue.append("/api/msp?fn=250")                       // save to EEPROM
        if edits.contains(where: { $0.fn == 143 }) {
            queue.append("/api/msp?fn=68")                    // gov config needs an FC reboot
        }
        sendTotal = queue.count
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
                } else {
                    next()
                }
            }
        }
    }
}

struct ScannerView: View {
    @EnvironmentObject var link: BleLink
    @Binding var demoMode: Bool
    @Binding var reviewMode: Bool

    var body: some View {
        List {
            // One recording per MODEL (Malcolm 2026-08-04): connecting a
            // different model parks this one's session, never erases it.
            let sessions = SessionCache.savedSessions()
            if !sessions.isEmpty {
                Section {
                    ForEach(sessions, id: \.model) { s in
                        Button {
                            SessionCache.shared.activate(model: s.model)
                            reviewMode = true
                        } label: {
                            Label("Review:  \(s.model) — \(s.savedAt.formatted(date: .omitted, time: .shortened))",
                                  systemImage: "clock.arrow.circlepath")
                        }
                    }
                } footer: {
                    Text("Flight data and Rotorflight settings recorded during each "
                       + "model's last connection — browse them with everything "
                       + "switched off.")
                }
            }
            // a real receiver in sight → the demo offer just muddies the water
            if link.found.isEmpty {
                Section {
                    Button {
                        demoMode = true
                    } label: {
                        Label("No receiver yet?  Try the demo",
                              systemImage: "theatermasks")
                    }
                }
            }
            Section {
                ForEach(link.found) { d in
                    Button {
                        link.connect(d)
                    } label: {
                        HStack {
                            Image(systemName: "antenna.radiowaves.left.and.right")
                                .foregroundStyle(.tint)
                            VStack(alignment: .leading) {
                                Text(d.name).font(.headline)
                                Text("Signal \(d.rssi) dBm")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundStyle(.tertiary)
                        }
                    }
                }
            } header: {
                Text(headerText)
            } footer: {
                Text("Power the receiver with the transmitter OFF so its "
                   + "config radios come up (same rule as the WiFi portal). "
                   + "Not everybody has an iPhone — the WiFi web interface "
                   + "still works exactly as before.")
            }
        }
        .navigationTitle("RXV2 Receivers")
        .overlay {
            if link.found.isEmpty {
                VStack(spacing: 12) {
                    ProgressView()
                    Label("Searching…", systemImage: "dot.radiowaves.left.and.right")
                        .font(.headline)
                    Text(statusText)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }
            }
        }
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
        switch link.state {
        case .failed(let m): return m
        default: return "Bring the receiver within a few metres and make sure it is in config mode (LED behaviour as usual)."
        }
    }
}
