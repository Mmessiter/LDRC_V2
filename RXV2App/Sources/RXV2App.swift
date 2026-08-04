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
    @State private var showPendingOffer = false
    @State private var pendingSummary = ""
    @State private var pendingEdits: [SessionCache.PendingEdit] = []

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
                    .alert("Settings edited offline", isPresented: $showPendingOffer) {
                        if pendingEdits.isEmpty {
                            Button("OK") { }                      // TX on: informational only
                            Button("Discard offline edits", role: .destructive) {
                                SessionCache.savePending(model: "", edits: [])
                            }
                        } else {
                            Button("Send to model") { sendPendingEdits() }
                            Button("Discard offline edits", role: .destructive) {
                                SessionCache.savePending(model: "", edits: [])
                            }
                            Button("Not now", role: .cancel) { }  // keep them for a TX-off visit
                        }
                    } message: {
                        Text(pendingSummary)
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
                   let info = obj["info"] as? [String: Any],
                   let lastPkt = rf["last_pkt_ms"] as? Double,
                   let upS = info["uptime_s"] as? Double {
                    txLive = lastPkt > 0 && (upS * 1000 - lastPkt) < 3000
                }
                DispatchQueue.main.async {
                    let what = edits.map(\.label).joined(separator: ", ")
                    if txLive {
                        pendingEdits = []
                        pendingSummary = "Offline edits are waiting (\(what)) — but the "
                            + "transmitter is ON, so its switch owns the bank. To send them "
                            + "to the right place: switch the transmitter OFF and reconnect."
                    } else {
                        pendingEdits = edits
                        pendingSummary = "While offline you edited: \(what).\n\n"
                            + "The transmitter is off, so the app controls the bank — if the "
                            + "edits belong to a particular bank, select it on the Rotorflight "
                            + "pages first.\n\nSend the edits to the model now, or discard "
                            + "them and keep what the model already has?"
                    }
                    showPendingOffer = true
                }
            }
        }
        SessionPrefetcher.run(link: link)
    }

    func sendPendingEdits() {
        let edits = pendingEdits
        var queue: [String] = edits.map { "/api/msp?fn=\($0.fn)&data=\($0.hex)" }
        queue.append("/api/msp?fn=250")                       // save to EEPROM
        if edits.contains(where: { $0.fn == 143 }) {
            queue.append("/api/msp?fn=68")                    // gov config needs an FC reboot
        }
        func next() {
            guard !queue.isEmpty else {
                SessionCache.savePending(model: "", edits: [])
                return
            }
            let p = queue.removeFirst()
            link.request(method: "GET", path: p, headers: [:], body: nil) { _ in
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { next() }
            }
        }
        next()
    }
}

struct ScannerView: View {
    @EnvironmentObject var link: BleLink
    @Binding var demoMode: Bool
    @Binding var reviewMode: Bool

    var body: some View {
        List {
            if SessionCache.shared.available {
                Section {
                    Button {
                        reviewMode = true
                    } label: {
                        Label("Review last session:  \(SessionCache.shared.label)",
                              systemImage: "clock.arrow.circlepath")
                    }
                } footer: {
                    Text("Flight data and Rotorflight settings recorded during the "
                       + "last connection — browse them with everything switched off.")
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
