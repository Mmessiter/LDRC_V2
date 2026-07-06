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

    var body: some View {
        NavigationStack {
            switch link.state {
            case .ready:
                // Full-screen, like the web UI added to the home screen: no
                // navigation bar. Disconnect lives on the page's Bluetooth
                // badge (bottom-right), via the rxv2 JS message bridge.
                WebScreen(link: link)
                    .ignoresSafeArea()
                    .toolbar(.hidden, for: .navigationBar)
            default:
                ScannerView()
            }
        }
    }
}

struct ScannerView: View {
    @EnvironmentObject var link: BleLink

    var body: some View {
        List {
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
