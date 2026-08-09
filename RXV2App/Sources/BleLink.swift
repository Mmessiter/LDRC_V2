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
        let payload: Data
        let completion: (Result<BleResponse, Error>) -> Void
    }
    private var queue: [Pending] = []
    private var inFlight: Pending?
    private var rxHeader = Data()
    private var rxBody = Data()
    private var rxExpected = -1
    private var rxCode = 0
    private var rxType = ""
    private var rxLocation = ""
    private var rxDiscarded = 0        // stale bytes skipped while hunting the header
    private var timeoutTimer: Timer?

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
        guard central.state == .poweredOn else { state = .scanning; return }
        state = .scanning
        central.scanForPeripherals(withServices: [Self.serviceUUID], options: nil)
    }

    func stopScan() { central.stopScan() }

    private var lastName = "RXV2"
    private var userDisconnect = false
    private var reconnectUntil: Date?

    func connect(_ d: Discovered) {
        stopScan()
        lastName = d.name
        userDisconnect = false
        state = .connecting(d.name)
        peripheral = d.peripheral
        d.peripheral.delegate = self
        central.connect(d.peripheral, options: nil)
    }

    func disconnect() {
        userDisconnect = true
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
        var text = "\(method) \(path)\n"
        for (k, v) in headers { text += "\(k): \(v)\n" }
        text += "\n"
        var payload = Data(text.utf8)
        if let b = body { payload.append(b) }
        queue.append(Pending(payload: payload, completion: completion))
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
        armTimeout(4)   // generous first-byte window; each chunk re-arms 3 s
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
                        rxCode = code
                        rxType = String(parts[1])
                        rxExpected = len
                        rxLocation = parts.count > 3 ? String(parts[3]) : ""
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
        } else {
            rxBody.append(data)
        }
        if rxExpected >= 0 && rxBody.count >= rxExpected {
            let resp = BleResponse(code: rxCode, contentType: rxType,
                                   location: rxLocation, body: rxBody.prefix(rxExpected))
            finish(.success(resp))
        }
    }

    private func cleanupConnection(message: String?) {
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
        if central.state == .poweredOn, case .scanning = state {
            central.scanForPeripherals(withServices: [Self.serviceUUID], options: nil)
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
           peripheral.identifier == self.peripheral?.identifier || name == wanted {
            central.stopScan()
            if let old = self.peripheral, old !== peripheral {
                central.cancelPeripheralConnection(old)
            }
            self.peripheral = peripheral
            peripheral.delegate = self
            central.connect(peripheral, options: nil)
            return
        }
        if let i = found.firstIndex(where: { $0.id == peripheral.identifier }) {
            found[i] = Discovered(id: peripheral.identifier, name: name,
                                  rssi: RSSI.intValue, peripheral: peripheral)
        } else {
            found.append(Discovered(id: peripheral.identifier, name: name,
                                    rssi: RSSI.intValue, peripheral: peripheral))
        }
        found.sort { $0.rssi > $1.rssi }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.discoverServices([Self.serviceUUID])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral,
                        error: Error?) {
        state = .failed(error?.localizedDescription ?? "Connection failed")
        cleanupConnection(message: nil)
    }

    // A disconnect is only worth RIDING THROUGH when the receiver is known
    // to be rebooting deliberately (firmware install, protocol/name/WiFi
    // save, fly-mode). Anything else means the model was switched off —
    // and the pilot wants the model list, not a hopeful spinner (Malcolm
    // 2026-08-07). The scheme handler stamps this on reboot-ish traffic.
    static var rebootishUntil = Date.distantPast
    static func noteRebootish(seconds: TimeInterval) {
        let until = Date().addingTimeInterval(seconds)
        if until > rebootishUntil { rebootishUntil = until }
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?) {
        cleanupConnection(message: "Receiver disconnected")
        // Unexpected drop while in use — retry quietly for 90 s ONLY if a
        // deliberate reboot is plausibly in progress; otherwise the model
        // was switched off: straight back to the scanner.
        let wasActive: Bool
        if case .ready = state { wasActive = true }
        else if case .reconnecting = state { wasActive = true }
        else { wasActive = false }
        if !userDisconnect && wasActive && Date() < Self.rebootishUntil {
            if case .ready = state { reconnectUntil = Date().addingTimeInterval(90) }
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
                central.scanForPeripherals(withServices: [Self.serviceUUID], options: nil)
                // Deadline watchdog: a pending connect to a POWERED-OFF
                // board never calls back on iOS, so .reconnecting could
                // last forever. When the window closes, give up cleanly.
                let grace = max(2, (until.timeIntervalSinceNow) + 2)
                DispatchQueue.main.asyncAfter(deadline: .now() + grace) { [weak self] in
                    guard let self, case .reconnecting = self.state else { return }
                    self.central.stopScan()
                    if let p = self.peripheral { self.central.cancelPeripheralConnection(p) }
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
