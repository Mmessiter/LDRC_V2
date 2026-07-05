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
    }

    @Published var state: State = .idle
    @Published var found: [Discovered] = []

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
    private var timeoutTimer: Timer?

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

    func connect(_ d: Discovered) {
        stopScan()
        state = .connecting(d.name)
        peripheral = d.peripheral
        d.peripheral.delegate = self
        central.connect(d.peripheral, options: nil)
    }

    func disconnect() {
        if let p = peripheral { central.cancelPeripheralConnection(p) }
        cleanupConnection(message: nil)
        state = .idle
    }

    /// Perform one HTTP-ish request over BLE.
    func request(method: String, path: String, headers: [String: String] = [:],
                 body: Data? = nil,
                 completion: @escaping (Result<BleResponse, Error>) -> Void) {
        var text = "\(method) \(path)\n"
        for (k, v) in headers { text += "\(k): \(v)\n" }
        text += "\n"
        var payload = Data(text.utf8)
        if let b = body { payload.append(b) }
        queue.append(Pending(payload: payload, completion: completion))
        pump()
    }

    // MARK: - internals

    private func pump() {
        guard inFlight == nil, let next = queue.first,
              let p = peripheral, let req = reqChr, case .ready = state else { return }
        queue.removeFirst()
        inFlight = next
        rxHeader = Data(); rxBody = Data(); rxExpected = -1

        // frame + chunk the request
        let maxLen = max(20, p.maximumWriteValueLength(for: .withResponse))
        var first = Data("Q\(next.payload.count)|".utf8)
        var offset = 0
        let room = maxLen - first.count
        let take = min(room, next.payload.count)
        first.append(next.payload.prefix(take))
        offset = take
        p.writeValue(first, for: req, type: .withResponse)
        while offset < next.payload.count {
            var cont = Data("+".utf8)
            let n = min(maxLen - 1, next.payload.count - offset)
            cont.append(next.payload.subdata(in: offset..<offset + n))
            offset += n
            p.writeValue(cont, for: req, type: .withResponse)
        }

        timeoutTimer?.invalidate()
        timeoutTimer = Timer.scheduledTimer(withTimeInterval: 12, repeats: false) { [weak self] _ in
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
        guard inFlight != nil else { return }
        if rxExpected < 0 {
            // still collecting the header line
            rxHeader.append(data)
            guard let nl = rxHeader.firstIndex(of: 0x0A) else { return }
            let headLine = String(decoding: rxHeader[rxHeader.startIndex..<nl], as: UTF8.self)
            let rest = rxHeader[(nl + 1)...]
            // "R<code>|<type>|<len>|<location>"
            guard headLine.hasPrefix("R") else {
                finish(.failure(NSError(domain: "BleLink", code: 502,
                    userInfo: [NSLocalizedDescriptionKey: "Bad response framing"])))
                return
            }
            let parts = headLine.dropFirst().split(separator: "|", maxSplits: 3,
                                                   omittingEmptySubsequences: false)
            rxCode = Int(parts.count > 0 ? parts[0] : "0") ?? 0
            rxType = parts.count > 1 ? String(parts[1]) : "text/plain"
            rxExpected = Int(parts.count > 2 ? parts[2] : "0") ?? 0
            rxLocation = parts.count > 3 ? String(parts[3]) : ""
            rxBody = Data(rest)
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

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?) {
        cleanupConnection(message: "Receiver disconnected")
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
}
