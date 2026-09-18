// LockDownRadioControl — RXV2App  ::  BleLink.swift
//
// CoreBluetooth transport speaking the firmware's HTTP-over-BLE framing
// (see RXV2/src/BleConfig.h). One request in flight at a time; requests
// queue and run in order.
//
//   request  (app → receiver):  first write "Q<totalLen>|" + payload,
//                               continuations "+" + payload
//   payload:                    "METHOD path[?query]\n{Header: v\n}\nbody"
//   response (receiver → app):  first notify "R<code>|<type>|<len>|<loc>\n"
//                               then raw body bytes until <len> received.

import Foundation
import CoreBluetooth
import UIKit

struct BleResponse {
    let code: Int
    let contentType: String
    let location: String
    let body: Data
}

final class BleLink: NSObject, ObservableObject {
    static let serviceUUID  = CBUUID(string: "8e400001-f315-4f60-9fb8-838830daea50")
    static let requestUUID  = CBUUID(string: "8e400002-f315-4f60-9fb8-838830daea50")
    static let responseUUID = CBUUID(string: "8e400003-f315-4f60-9fb8-838830daea50")

    struct Discovered: Identifiable {
        let id: UUID
        let name: String
        let rssi: Int
        let peripheral: CBPeripheral
    }

    enum State: Equatable {
        case idle, scanning, connecting(String), ready(String), failed(String)
        case reconnecting(String)
    }

    @Published var state: State = .idle
    @Published var found: [Discovered] = []

    /// Out-of-band "S|us0,..,us15|age" channel frames pushed by the receiver
    /// (View-channels live bars). Set by WebScreen; called on the main queue.
    var onStreamFrame: ((String) -> Void)?

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var reqChr: CBCharacteristic?
    private var respChr: CBCharacteristic?

    // single-request pipeline
    private struct Pending {
        let id: Int                        // echoed by the receiver as "#id" (0.9.746)
        let payload: Data
        let firstByteWindow: TimeInterval
        let completion: (Result<BleResponse, Error>) -> Void
    }
    private var queue: [Pending] = []
    private var inFlight: Pending?
    // Request ids (0.9.746). The bridge had no way to tie a reply to a request:
    // when we gave up on a slow one and sent the next, the receiver dropped
    // the new one and delivered the OLD reply, which we took as the answer to
    // the NEW request — and every reply after that was one behind. Malcolm's
    // update page read another endpoint's reply as state.json and announced
    // "no WiFi here" beside the router. Every request now carries "X-Req: n";
    // a receiver that knows about it echoes "#n" in the location slot, and a
    // reply whose id is not the one we are waiting for is swallowed and
    // dropped. Old receivers echo nothing, and behave exactly as before.
    private var nextReqId = 1
    private var rxStale = false        // swallowing a reply for a request we gave up on
    private var rxHeader = Data()
    private var rxBody = Data()
    private var rxExpected = -1
    private var rxCode = 0
    private var rxType = ""
    private var rxLocation = ""
    private var rxDiscarded = 0        // stale bytes skipped while hunting the header
    private var timeoutTimer: Timer?

    // CoreBluetooth's connect() never gives up: out of range it waits for
    // ever and the app looks frozen (Malcolm 2026-09-12: "it fails slowly
    // and I have to quit the app"). These give it a deadline and, when the
    // signal was weak to begin with, say so in plain words.
    private var connectWatchdog: Timer?
    private var connectingRssi = 0
    /// Shown under the spinner while connecting: a warning about a weak signal.
    @Published var connectNote: String? = nil
    /// Anything at or below this is too weak to WORK, which is stricter than
    /// too weak to connect: -85 let a link two rooms away connect and then fail
    /// (Malcolm 2026-09-12). BLE throughput collapses long before the connection
    /// does, and this link carries whole web pages.
    static let weakRssi = -78

    /// A plain word for a signal strength: dBm means nothing to most people.
    /// The words line up with the gate - anything not Strong or Good is refused.
    static func signalWord(_ rssi: Int) -> String {
        switch rssi {
        case (-65)...:      return "Strong"
        case (-77)...(-66): return "Good"
        default:            return "Too far"
        }
    }
    static func tooWeak(_ rssi: Int) -> Bool { rssi != 0 && rssi <= weakRssi }

    /// Smoothed signal per device, and the slow tick that publishes it.
    /// Advertisements arrive several times a second; showing each one made the
    /// number unreadable (Malcolm 2026-09-12: "it's a blur"). The average moves
    /// with every advert, the display only once a second.
    private var smoothRssi: [UUID: Double] = [:]
    private var publishTimer: Timer?
    private static let smoothing = 0.3          // ~0.7 s to follow a change
    private static let publishEvery = 1.0       // seconds

    /// CoreBluetooth reports a peripheral ONCE per scan unless duplicates are
    /// allowed, so without this the strength shown is frozen at the first
    /// sighting and walking closer changes nothing (Malcolm 2026-09-12:
    /// "it was necessary to quit the app and reload it").
    static let scanOptions: [String: Any] = [CBCentralManagerScanOptionAllowDuplicatesKey: true]

    // Raw OTA chunk lane: 0xA5-framed writes streamed write-without-response,
    // flow-controlled by canSendWriteWithoutResponse. Independent of the
    // request pipeline — the firmware routes 0xA5 frames straight to flash.
    private var otaFrames: [Data] = []
    private var otaIndex = 0
    private var otaCompletion: ((Result<Void, Error>) -> Void)?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }

    // MARK: - public API

    func startScan() {
        found = []
        smoothRssi.removeAll()
        guard central.state == .poweredOn else { state = .scanning; return }
        state = .scanning
        if fastConnect() { return }   // instant reconnect to last device — no advert wait
        central.scanForPeripherals(withServices: [Self.serviceUUID], options: Self.scanOptions)
        startPublishing()
    }

    func stopScan() { central.stopScan(); publishTimer?.invalidate(); publishTimer = nil }

    /// Copy the smoothed signals into the published list once a second.
    private func startPublishing() {
        publishTimer?.invalidate()
        publishTimer = Timer.scheduledTimer(withTimeInterval: Self.publishEvery, repeats: true) { [weak self] _ in
            guard let self else { return }
            var changed = false
            for i in self.found.indices {
                guard let s = self.smoothRssi[self.found[i].id] else { continue }
                let v = Int(s.rounded())
                if v != self.found[i].rssi {
                    self.found[i] = Discovered(id: self.found[i].id, name: self.found[i].name,
                                               rssi: v, peripheral: self.found[i].peripheral)
                    changed = true
                }
            }
            if changed { self.found.sort { $0.rssi > $1.rssi } }
        }
    }

    private var lastName = "RXV2"
    private var userDisconnect = false
    private var reconnectUntil: Date?
    /// True after an UNEXPECTED drop (not a reboot we asked for, not the
    /// pilot leaving) until the app reads it — so the scanner can re-arm
    /// auto-connect when the reconnect window closes (0.9.746).
    var lastDropUnexpected = false

    // Scanner auto-connect (Malcolm 2026-08-16): fire at most once per app
    // launch, never after a deliberate disconnect.
    var scannerAutoDone = false

    func connect(_ d: Discovered) {
        stopScan()
        // A fastConnect may still be pending toward a different peripheral
        // (machine off) — cancel it so the two never race.
        if let old = peripheral, old !== d.peripheral {
            central.cancelPeripheralConnection(old)
        }
        lastName = d.name
        userDisconnect = false
        state = .connecting(d.name)
        startConnectWatchdog(d.name, rssi: d.rssi)
        peripheral = d.peripheral
        d.peripheral.delegate = self
        // Remember the CoreBluetooth identifier so the NEXT launch can
        // connect directly (fastConnect) without waiting ~1.5 s for a fresh
        // advertisement to be scanned (Malcolm 2026-08-17).
        UserDefaults.standard.set(d.peripheral.identifier.uuidString,
                                  forKey: "lastDeviceId")
        UserDefaults.standard.set(d.rssi, forKey: "lastDeviceRssi")
        central.connect(d.peripheral, options: nil)
    }

    // Instant auto-connect: retrieve the last session's peripheral by its
    // stored identifier and connect WITHOUT scanning. iOS completes the
    // connection as soon as the radio hears the device — typically well
    // before a scan would have delivered an advertisement to the app.
    // Returns false when there's nothing stored or Bluetooth isn't up yet
    // (the caller falls back to scan + discovery auto-connect).
    @discardableResult
    func fastConnect() -> Bool {
        guard !scannerAutoDone, central.state == .poweredOn else { return false }
        switch state { case .idle, .scanning: break; default: return false }
        let defaults = UserDefaults.standard
        guard let name = defaults.string(forKey: "lastDeviceName"), !name.isEmpty,
              let idStr = defaults.string(forKey: "lastDeviceId"),
              let uuid = UUID(uuidString: idStr),
              let p = central.retrievePeripherals(withIdentifiers: [uuid]).first
        else { return false }
        // fastConnect has no RSSI to judge - it connects by stored identifier
        // without scanning. So use the strength recorded at the END of the last
        // session: if the model was far away then, scan and let the pilot choose
        // rather than connecting blind (Malcolm 2026-09-12).
        let lastRssi = defaults.integer(forKey: "lastDeviceRssi")
        if lastRssi != 0 && lastRssi <= Self.weakRssi { return false }
        scannerAutoDone = true
        stopScan()
        lastName = name
        userDisconnect = false
        state = .connecting(name)
        peripheral = p
        p.delegate = self
        central.connect(p, options: nil)
        // If the machine is off / out of range the pending connect would wait
        // forever with the UI saying "connecting". After 4 s, surface the
        // scanner (scan + list) while the pending connect keeps waiting in
        // the background — it still completes the moment the device appears.
        DispatchQueue.main.asyncAfter(deadline: .now() + 4.0) { [weak self] in
            guard let self else { return }
            if case .connecting = self.state, self.peripheral === p,
               p.state != .connected {
                self.connectNote = "\(name) has not answered — it may be switched off or too far away."
                self.state = .scanning
                self.central.scanForPeripherals(withServices: [Self.serviceUUID], options: Self.scanOptions)
            }
        }
        return true
    }

    // Give up on a connection that is going nowhere, and say why.
    private func startConnectWatchdog(_ name: String, rssi: Int, seconds: TimeInterval = 12) {
        connectWatchdog?.invalidate()
        connectingRssi = rssi
        connectNote = (rssi != 0 && rssi <= Self.weakRssi)
            ? "The signal is weak (\(rssi) dBm). Move closer to the model."
            : nil
        connectWatchdog = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in
            guard let self else { return }
            guard case .connecting = self.state else { return }
            if let p = self.peripheral { self.central.cancelPeripheralConnection(p) }
            self.cleanupConnection(message: nil)
            self.state = .failed(self.connectingRssi != 0 && self.connectingRssi <= Self.weakRssi
                ? "Too far away. The signal from \(name) was weak (\(self.connectingRssi) dBm) — get closer and tap it again."
                : "\(name) did not answer. Get closer, check it is switched on, and tap it again.")
            self.connectNote = nil
            // Keep scanning so the list refills and he can retry at once —
            // but do NOT set .scanning, which would wipe the message above.
            if self.central.state == .poweredOn {
                self.central.scanForPeripherals(withServices: [Self.serviceUUID], options: Self.scanOptions)
            }
        }
    }
    private func stopConnectWatchdog() { connectWatchdog?.invalidate(); connectWatchdog = nil; connectNote = nil }

    func disconnect() {
        stopConnectWatchdog()
        userDisconnect = true
        scannerAutoDone = true   // returning to the scanner MEANS "let me choose"
        if let p = peripheral { central.cancelPeripheralConnection(p) }
        cleanupConnection(message: nil)
        state = .idle
    }

    /// Perform one HTTP-ish request over BLE.
    func request(method: String, path: String, headers: [String: String] = [:],
                 body: Data? = nil,
                 completion: @escaping (Result<BleResponse, Error>) -> Void) {
        // Fail fast while the link is down (e.g. mid-reboot during a
        // firmware install) so page polls keep their cadence.
        if case .ready = state {} else {
            completion(.failure(NSError(domain: "BleLink", code: 503,
                userInfo: [NSLocalizedDescriptionKey: "Not connected"])))
            return
        }
        let id = nextReqId
        nextReqId = nextReqId >= 999_999 ? 1 : nextReqId + 1
        var text = "\(method) \(path)\n"
        text += "X-Req: \(id)\n"
        for (k, v) in headers { text += "\(k): \(v)\n" }
        text += "\n"
        var payload = Data(text.utf8)
        if let b = body { payload.append(b) }
        // First-byte window. This MUST be at least as long as the receiver is
        // willing to wait, or the app gives up on a request the receiver is
        // still working on — and then hands the page its own HTML timeout
        // notice, which the page tries to read as a reply.
        //
        // Malcolm 2026-09-14, on RAW420AJB: the command line "usually just
        // didn't respond at all", fast telemetry hung on "Working...", and the
        // telemetry error was WebKit's JSON complaint about that HTML page.
        // All ONE bug: this was a flat 4 s for everything except /api/msp,
        // while /api/cli alone can hold the receiver for 8.5 s (cliEnter 2.5 s
        // + cliExchange 6 s) and `diff` routinely does. Android's equivalent
        // was already 12 s, which is why it bit on the iPhone and not the
        // Pixel.
        //
        // Anything that reaches the flight controller now gets a window that
        // matches what the firmware will actually spend.
        let window: TimeInterval = Self.firstByteWindow(for: path)
        queue.append(Pending(id: id, payload: payload, firstByteWindow: window, completion: completion))
        pump()
    }

    // MARK: - raw OTA streaming

    /// Payload bytes per 0xA5 frame (frame = 1 tag + 4 offset + payload).
    /// Firmware caps BLE writes at 240 bytes.
    func otaChunkSize() -> Int {
        guard let p = peripheral else { return 64 }
        let cap = min(240, p.maximumWriteValueLength(for: .withoutResponse))
        return max(64, cap - 5)
    }

    /// Stream pre-built 0xA5 frames to the request characteristic.
    /// Completion fires once every frame has been handed to CoreBluetooth.
    /// Call from any thread; work happens on main alongside the pipeline.
    func otaSend(_ frames: [Data], completion: @escaping (Result<Void, Error>) -> Void) {
        DispatchQueue.main.async {
            guard case .ready = self.state, self.peripheral != nil, self.reqChr != nil else {
                completion(.failure(NSError(domain: "BleLink", code: 503,
                    userInfo: [NSLocalizedDescriptionKey: "Not connected"])))
                return
            }
            if let old = self.otaCompletion {   // stale batch (link hiccup) — supersede it
                self.otaFrames = []; self.otaIndex = 0; self.otaCompletion = nil
                old(.failure(NSError(domain: "BleLink", code: 409,
                    userInfo: [NSLocalizedDescriptionKey: "superseded"])))
            }
            self.otaFrames = frames
            self.otaIndex = 0
            self.otaCompletion = completion
            self.otaDrain()
        }
    }

    fileprivate func otaDrain() {
        guard otaCompletion != nil else { return }
        guard let p = peripheral, let req = reqChr, case .ready = state else {
            let done = otaCompletion
            otaFrames = []; otaIndex = 0; otaCompletion = nil
            done?(.failure(NSError(domain: "BleLink", code: 503,
                userInfo: [NSLocalizedDescriptionKey: "Link lost during update"])))
            return
        }
        while otaIndex < otaFrames.count {
            if !p.canSendWriteWithoutResponse { return }  // resumes in peripheralIsReady
            p.writeValue(otaFrames[otaIndex], for: req, type: .withoutResponse)
            otaIndex += 1
        }
        let done = otaCompletion
        otaFrames = []; otaIndex = 0; otaCompletion = nil
        done?(.success(()))
    }

    // MARK: - internals

    private func pump() {
        guard inFlight == nil, let next = queue.first,
              let p = peripheral, let req = reqChr, case .ready = state else { return }
        queue.removeFirst()
        inFlight = next
        rxHeader = Data(); rxBody = Data(); rxExpected = -1; rxDiscarded = 0

        // Small requests (polls — the vast majority) go write-WITHOUT-response
        // when the characteristic allows it: the reply can ride the very next
        // radio event instead of waiting for the write's own acknowledgement
        // first. That halves the per-poll latency. Multi-frame requests keep
        // acknowledged writes for ordering safety.
        let canWNR  = req.properties.contains(.writeWithoutResponse)
        let wnrLen  = max(20, p.maximumWriteValueLength(for: .withoutResponse))
        let ackLen  = max(20, p.maximumWriteValueLength(for: .withResponse))
        let prefix  = "Q\(next.payload.count)|"
        if canWNR && prefix.utf8.count + next.payload.count <= wnrLen {
            var first = Data(prefix.utf8)
            first.append(next.payload)
            p.writeValue(first, for: req, type: .withoutResponse)
        } else {
            var first = Data(prefix.utf8)
            var offset = 0
            let take = min(ackLen - first.count, next.payload.count)
            first.append(next.payload.prefix(take))
            offset = take
            p.writeValue(first, for: req, type: .withResponse)
            while offset < next.payload.count {
                var cont = Data("+".utf8)
                let n = min(ackLen - 1, next.payload.count - offset)
                cont.append(next.payload.subdata(in: offset..<offset + n))
                offset += n
                p.writeValue(cont, for: req, type: .withResponse)
            }
        }
        armTimeout(next.firstByteWindow)   // generous first-byte window; each chunk re-arms 3 s
    }

    /// How long to wait for the FIRST byte of a reply, by path. Each received
    /// chunk re-arms a shorter 3 s watchdog, so a healthy big reply streams
    /// freely; these numbers only cover the receiver's own thinking time.
    static func firstByteWindow(for path: String) -> TimeInterval {
        // The receiver waits cliEnter(2.5 s) + cliExchange(6 s) = 8.5 s, and a
        // Rotorflight `diff` or `dump` uses most of it.
        if path.hasPrefix("/api/cli")            { return 15 }
        // Telemetry speed/restore write settings, save EEPROM and restart the FC.
        if path.hasPrefix("/api/fc/telemetry")   { return 25 }
        // A big MSP read is metered out at ~0.5-0.8 s per 58-byte chunk; the
        // 588-byte adjustment table takes ~6 s and the receiver waits 12 s.
        if path.hasPrefix("/api/msp")            { return 14 }
        // These download or erase on the far side before answering at all.
        if path.hasPrefix("/api/firmware")       { return 60 }
        if path.hasPrefix("/api/backup")         { return 30 }
        if path.hasPrefix("/api/bb")             { return 30 }
        // begin reads 20 flights + 20 backups into RAM; end mounts/formats
        // LittleFS and writes them back — seconds, not milliseconds.
        if path.hasPrefix("/api/bleota")         { return 30 }
        // Everything else: pages and ordinary polls, which the receiver answers
        // in milliseconds. Stays at 4 s and MUST stay short.
        //
        // Malcolm 2026-09-14, minutes after I raised this to 12 s: "seems
        // slower than before, much slower". Of course it did — this queue is
        // SERIAL (one inFlight at a time), so the window is not just how long
        // one request may take, it is how long everything queued behind a
        // request that is never going to be answered has to wait. Tripling the
        // default tripled every stall in the app. Only the paths that genuinely
        // hold the receiver get a long window; the common case gets a short one.
        return 4
    }

    // Watchdog: instead of one long dead-air timeout, the timer re-arms on
    // every received chunk. A healthy response of any size streams freely;
    // a genuinely stuck one fails fast so the page can ask again.
    private func armTimeout(_ seconds: TimeInterval) {
        timeoutTimer?.invalidate()
        timeoutTimer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in
            self?.finish(.failure(NSError(domain: "BleLink", code: 504,
                userInfo: [NSLocalizedDescriptionKey: "Receiver did not answer (timeout)"])))
        }
    }

    private func finish(_ result: Result<BleResponse, Error>) {
        timeoutTimer?.invalidate(); timeoutTimer = nil
        rxStale = false
        let done = inFlight
        inFlight = nil
        done?.completion(result)
        pump()
    }

    private func handleNotify(_ data: Data) {
        guard inFlight != nil else {
            // Between requests the only traffic is pushed channel frames —
            // the firmware gates them so they never interleave a response.
            if data.first == UInt8(ascii: "S"),
               let s = String(data: data, encoding: .utf8), s.hasPrefix("S|") {
                onStreamFrame?(s)
            }
            return
        }
        armTimeout(3)   // bytes are flowing — keep the watchdog fed
        if rxExpected < 0 {
            // Hunting for the header line. After a timed-out predecessor,
            // leftover chunks of the abandoned response can arrive first —
            // discard line by line until something parses as a real
            // "R<code>|<type>|<len>|<location>" header (self-resync).
            rxHeader.append(data)
            while true {
                guard let nl = rxHeader.firstIndex(of: 0x0A) else {
                    if rxHeader.count + rxDiscarded > 32768 {
                        finish(.failure(NSError(domain: "BleLink", code: 502,
                            userInfo: [NSLocalizedDescriptionKey: "Bad response framing"])))
                    }
                    return
                }
                let headLine = String(decoding: rxHeader[rxHeader.startIndex..<nl], as: UTF8.self)
                if headLine.hasPrefix("S|") {
                    // a channel frame already queued when our request went out
                    onStreamFrame?(headLine)
                    rxHeader = Data(rxHeader[(nl + 1)...])
                    continue
                }
                if headLine.hasPrefix("R") {
                    let parts = headLine.dropFirst().split(separator: "|", maxSplits: 3,
                                                           omittingEmptySubsequences: false)
                    if parts.count >= 3, let code = Int(parts[0]), let len = Int(parts[2]),
                       code >= 100, code < 600, len >= 0 {
                        let loc = parts.count > 3 ? String(parts[3]) : ""
                        // Echoed request id: a reply for a request we gave up
                        // on is consumed and dropped, never handed to the one
                        // now waiting (0.9.746).
                        if loc.hasPrefix("#"), let rid = Int(loc.dropFirst()), let f = inFlight, rid != f.id {
                            rxStale = true
                        } else {
                            rxStale = false
                        }
                        rxCode = code
                        rxType = String(parts[1])
                        rxExpected = len
                        rxLocation = loc.hasPrefix("#") ? "" : loc
                        rxBody = Data(rxHeader[(nl + 1)...])
                        rxHeader = Data()
                        break
                    }
                }
                // stale line — skip it and keep hunting
                rxDiscarded += rxHeader.distance(from: rxHeader.startIndex, to: nl) + 1
                rxHeader = Data(rxHeader[(nl + 1)...])
                if rxDiscarded > 32768 {
                    finish(.failure(NSError(domain: "BleLink", code: 502,
                        userInfo: [NSLocalizedDescriptionKey: "Bad response framing"])))
                    return
                }
            }
        } else if rxStale, data.first == UInt8(ascii: "R"), Self.looksLikeHeader(data) {
            // The receiver abandoned the stale reply mid-body (our new request
            // reached it) and this packet is the header of OURS. A header is
            // always its own packet, so this test is safe.
            rxStale = false
            rxBody = Data(); rxExpected = -1; rxHeader = Data()
            handleNotify(data)
            return
        } else {
            rxBody.append(data)
        }
        if rxExpected >= 0 && rxBody.count >= rxExpected {
            if rxStale {
                // Swallowed the whole stale reply — back to waiting for ours.
                rxStale = false
                let rest = Data(rxBody.dropFirst(rxExpected))
                rxBody = Data(); rxExpected = -1; rxHeader = Data()
                armTimeout(inFlight?.firstByteWindow ?? 4)
                if !rest.isEmpty { handleNotify(rest) }
                return
            }
            let resp = BleResponse(code: rxCode, contentType: rxType,
                                   location: rxLocation, body: rxBody.prefix(rxExpected))
            finish(.success(resp))
        }
    }

    /// "R<code>|<type>|<len>|<loc>\n" at the start of a packet?
    private static func looksLikeHeader(_ d: Data) -> Bool {
        guard let nl = d.firstIndex(of: 0x0A) else { return false }
        let line = String(decoding: d[d.startIndex..<nl], as: UTF8.self)
        guard line.hasPrefix("R") else { return false }
        let parts = line.dropFirst().split(separator: "|", maxSplits: 3, omittingEmptySubsequences: false)
        guard parts.count >= 3, let code = Int(parts[0]), let len = Int(parts[2]) else { return false }
        return code >= 100 && code < 600 && len >= 0
    }

    private func cleanupConnection(message: String?) {
        // Never let one receiver's cached state be served to the next.
        BleSchemeHandler.forgetStateCache()
        timeoutTimer?.invalidate(); timeoutTimer = nil
        if let f = inFlight {
            f.completion(.failure(NSError(domain: "BleLink", code: 503,
                userInfo: [NSLocalizedDescriptionKey: message ?? "Disconnected"])))
        }
        inFlight = nil
        queue.forEach { $0.completion(.failure(NSError(domain: "BleLink", code: 503,
            userInfo: [NSLocalizedDescriptionKey: message ?? "Disconnected"]))) }
        queue.removeAll()
        peripheral = nil; reqChr = nil; respChr = nil
    }
}

// MARK: - CoreBluetooth delegates

extension BleLink: CBCentralManagerDelegate, CBPeripheralDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn {
            // Scan from .scanning — and from .failed/.idle too: Bluetooth
            // switched on AFTER launch used to leave "Bluetooth is switched
            // off" on screen until a relaunch (2026-09-16 review).
            var wants = false
            switch state { case .scanning, .idle, .failed: wants = true; default: break }
            if !wants { return }
            state = .scanning
            // Instant path first: connect by stored identifier, skipping the
            // advertisement wait entirely. Falls through to a normal scan
            // (with discovery auto-connect) when nothing is stored.
            if fastConnect() { return }
            central.scanForPeripherals(withServices: [Self.serviceUUID], options: Self.scanOptions)
        } else if central.state == .unauthorized {
            state = .failed("Bluetooth permission denied — enable it in Settings")
        } else if central.state == .poweredOff {
            state = .failed("Bluetooth is switched off")
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = (advertisementData[CBAdvertisementDataLocalNameKey] as? String)
                 ?? peripheral.name ?? "RXV2"
        // Reconnect via fresh discovery: the rebooted receiver reappears
        // here first — grab it the same way a manual tap would.
        if case .reconnecting(let wanted) = state,
           (self.peripheral != nil ? peripheral.identifier == self.peripheral!.identifier : name == wanted) {
            central.stopScan()
            if let old = self.peripheral, old !== peripheral {
                central.cancelPeripheralConnection(old)
            }
            self.peripheral = peripheral
            peripheral.delegate = self
            central.connect(peripheral, options: nil)
            return
        }
        // Every advertisement feeds the average; the timer publishes it.
        let id = peripheral.identifier, r = Double(RSSI.intValue)
        smoothRssi[id] = smoothRssi[id].map { $0 + Self.smoothing * (r - $0) } ?? r
        if found.firstIndex(where: { $0.id == id }) == nil {
            // A receiver appearing for the first time shows at once, not in a second.
            found.append(Discovered(id: id, name: name, rssi: RSSI.intValue, peripheral: peripheral))
            found.sort { $0.rssi > $1.rssi }
            if publishTimer == nil { startPublishing() }
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.discoverServices([Self.serviceUUID])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral,
                        error: Error?) {
        stopConnectWatchdog()
        let name = lastName ?? "The receiver"
        state = .failed(connectingRssi != 0 && connectingRssi <= Self.weakRssi
            ? "Too far away. The signal from \(name) was weak (\(connectingRssi) dBm) — get closer and tap it again."
            : (error?.localizedDescription ?? "Connection failed"))
        cleanupConnection(message: nil)
    }

    // A disconnect is only worth RIDING THROUGH when the receiver is known
    // to be rebooting deliberately (firmware install, protocol/name/WiFi
    // save, fly-mode). Anything else means the model was switched off —
    // and the pilot wants the model list, not a hopeful spinner (Malcolm
    // 2026-08-07). The scheme handler stamps this on reboot-ish traffic.
    static var rebootishUntil = Date.distantPast
    // How long the drop that follows is ridden out: 90 s covers a config-save
    // reboot; a firmware install asks for more (5.99 — DongleSim's update
    // "just sat there": the OTA runner was still polling after the link had
    // given up at 90 s, so the page never learned the update had gone in).
    static var rebootWindow: TimeInterval = 90
    static func noteRebootish(seconds: TimeInterval, window: TimeInterval = 90) {
        let until = Date().addingTimeInterval(seconds)
        if until > rebootishUntil { rebootishUntil = until; rebootWindow = window }
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?) {
        cleanupConnection(message: "Receiver disconnected")
        // Any unexpected drop from a live link is ridden out (0.9.746). A
        // deliberate reboot (install / save / fly) gets 90 s. A plain drop —
        // the receiver's radio hiccupped, the phone's stack gave up — gets
        // 30 s: long enough for the receiver to re-advertise, short enough
        // that a model that was simply switched off still lands on the
        // scanner promptly. Before this a plain drop went STRAIGHT to the
        // scanner (2026-08-07 rule) — Malcolm 2026-09-17: mid-session the app
        // "returned to the opening screen but the model wasn't selectable",
        // because the receiver was still tearing the old link down.
        let wasActive: Bool
        if case .ready = state { wasActive = true }
        else if case .reconnecting = state { wasActive = true }
        else { wasActive = false }
        let rebootish = Date() < Self.rebootishUntil
        // In the BACKGROUND with no install in flight, a drop is the receiver's
        // idle watchdog letting a silent app go (its pages stop polling when
        // iOS pauses the web view). Since the Bluetooth background mode (5.100)
        // the app is woken for that drop, and riding it out would reconnect
        // from the background, go silent again, be dropped again - every few
        // minutes, for as long as both are on. Land on idle instead; the
        // scanner is what the pilot sees on return (RXV2App drops any link
        // after a minute away in any case).
        if !rebootish && UIApplication.shared.applicationState == .background {
            state = .idle
            return
        }
        if !userDisconnect && wasActive {
            if case .ready = state {
                reconnectUntil = Date().addingTimeInterval(rebootish ? Self.rebootWindow : 30)
                lastDropUnexpected = !rebootish
            }
            if let until = reconnectUntil, Date() < until {
                self.peripheral = peripheral          // cleanup nilled it
                peripheral.delegate = self
                state = .reconnecting(lastName)
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                    guard let self, case .reconnecting = self.state,
                          let p = self.peripheral else { return }
                    self.central.connect(p, options: nil)
                }
                // Scan-assisted reconnect (Malcolm 2026-08-08: the manual
                // install stuck at 'waiting for it to come back'): a blind
                // pending connect can miss a rebooted stack, but a FRESH
                // discovery + connect is exactly the manual-tap path that
                // always works. didDiscover completes it.
                central.scanForPeripherals(withServices: [Self.serviceUUID], options: Self.scanOptions)
                // Deadline watchdog: a pending connect to a POWERED-OFF
                // board never calls back on iOS, so .reconnecting could
                // last forever. When the window closes, give up cleanly.
                let grace = max(2, (until.timeIntervalSinceNow) + 2)
                DispatchQueue.main.asyncAfter(deadline: .now() + grace) { [weak self] in
                    guard let self, case .reconnecting = self.state else { return }
                    self.central.stopScan()
                    if let p = self.peripheral { self.central.cancelPeripheralConnection(p) }
                    // The window after an UNEXPECTED drop has closed: land on
                    // the scanner with auto-connect ARMED, so the moment the
                    // receiver is seen again it connects by itself (0.9.746).
                    // A chosen parting (back / disconnect) still disarms it.
                    if self.lastDropUnexpected { self.lastDropUnexpected = false; self.scannerAutoDone = false }
                    self.state = .idle
                }
                return
            }
        }
        state = .idle
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let svc = peripheral.services?.first(where: { $0.uuid == Self.serviceUUID }) else {
            state = .failed("RXV2 service not found"); return
        }
        peripheral.discoverCharacteristics([Self.requestUUID, Self.responseUUID], for: svc)
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        for c in service.characteristics ?? [] {
            if c.uuid == Self.requestUUID  { reqChr = c }
            if c.uuid == Self.responseUUID { respChr = c; peripheral.setNotifyValue(true, for: c) }
        }
        if reqChr != nil && respChr != nil {
            let name = peripheral.name ?? "RXV2"
            stopConnectWatchdog()
            state = .ready(name)
            pump()
        } else {
            state = .failed("Characteristics missing")
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard characteristic.uuid == Self.responseUUID, let d = characteristic.value else { return }
        handleNotify(d)
    }

    func peripheralIsReady(toSendWriteWithoutResponse peripheral: CBPeripheral) {
        otaDrain()
    }
}
