// LockDownRadioControl — RXV2  ::  BleConfig.h
//
// HTTP-over-BLE bridge: lets the iOS app configure the receiver over
// Bluetooth LE using the SAME handlers as the WiFi web portal, so there is
// exactly one configuration engine with two transports.
//
// How it works
// ------------
// 1. `ReqRouter g_bleRouter` is a thin proxy with the same call surface as
//    the global `WebServer server`. WebPages.h does `#define server
//    g_bleRouter`, so every route registration and every handler's
//    send()/arg()/... goes through the router. When no BLE request is in
//    flight the router forwards verbatim to the real WebServer — WiFi
//    behaviour is bit-for-bit unchanged. During a BLE request the router
//    instead captures the response into a buffer.
// 2. A NimBLE GATT service exposes two characteristics:
//       REQ  (write)  — the app sends a framed HTTP-ish request
//       RESP (notify) — we stream back a framed response in MTU-size chunks
// 3. NimBLE callbacks only enqueue bytes. The request is EXECUTED from
//    loop() via blePoll() — the same task that runs server.handleClient() —
//    so handlers never race the WiFi path over shared state.
//
// Safety: bleStart()/bleStop() are called from exactly the same places that
// start and stop WiFi (Network.h), so BLE obeys the flying rules the user
// already knows: TX heard at boot → no radios; /fly → radios off.
//
// Request frame (app → receiver), UTF-8:
//     first write:        'Q' <totalLen decimal> '|' <payload...>
//     continuation write: '+' <payload...>
// Payload format:
//     METHOD SP path[?query] '\n' { header ':' value '\n' } '\n' body
//
// Response frames (receiver → app):
//     first notify:  'R' code '|' contentType '|' bodyLen '|' location '\n'
//     then raw body bytes in chunks until bodyLen have been sent.
//
//*********************************************************************

#ifndef _SRC_BLECONFIG_H
#define _SRC_BLECONFIG_H

#include "1Defs.h"
#include <NimBLEDevice.h>
#include <Update.h>
#include <vector>
#include <map>

//*********************************************************************
//  Tunables
//*********************************************************************

static const char* BLE_SVC_UUID  = "8e400001-f315-4f60-9fb8-838830daea50";
static const char* BLE_REQ_UUID  = "8e400002-f315-4f60-9fb8-838830daea50";
static const char* BLE_RESP_UUID = "8e400003-f315-4f60-9fb8-838830daea50";

constexpr size_t BLE_MAX_REQUEST  = 16 * 1024;   // biggest POST we accept
constexpr size_t BLE_MAX_RESPONSE = 160 * 1024;  // bigger → 413 (app bundles big assets)
// How much of one loop() pass the BLE pump may take. This used to be a BYTE
// budget of 6 kB, and that was the "DIAG LOOP-STALL 192ms (ble 190ms)" the
// receiver kept logging with a phone connected (found 2026-09-14).
//
// Why bytes were the wrong unit: every notify() is a synchronous hand-off that
// ends up waiting on the controller's HCI semaphore, which the controller
// releases as it drains packets OVER THE AIR. 6 kB at a 182-byte iOS chunk is
// ~34 notifies; at a 15-30 ms connection interval and a few packets per event
// that is 170-250 ms in which loop() does NOTHING ELSE — no radioPoll, no
// sbusTick. At 250 Hz CRSF that is ~47 control frames never sent to the flight
// controller, which is well inside Rotorflight's RXLOSS window, and it happens
// on the bench with the transmitter on, which is exactly when the app is used.
//
// Every other blocking wait in this firmware already keeps the model flying
// while it waits (see MspFc.h: "Keep FLYING while we wait … this wait starved
// the channel stream and the FC flickered into failsafe"). The BLE transport
// was the one that did not. It is now bounded by TIME instead, so the loop
// always comes back.
//
// Throughput does not suffer: the loop turns ~500 times a second, so even a
// few chunks per pass offers far more than the BLE air interface can carry.
// The link stays the bottleneck; the control loop stops paying for it.
constexpr uint32_t BLE_PUMP_US        = 3000;    // normal: at most ~3 ms of loop()
constexpr uint32_t BLE_PUMP_US_FLYING = 1200;    // transmitter live: tighter still
constexpr size_t   BLE_PUMP_BUDGET    = 6 * 1024;  // hard ceiling, still honoured

//*********************************************************************
//  BLE request/response state (written by NimBLE task, executed in loop)
//*********************************************************************

inline volatile bool bleClientConnected = false;
inline bool          bleStarted         = false;   // advertising / accepting connections
inline bool          bleInited          = false;   // controller+stack up (once, at boot)
inline uint32_t      bleLastActivityMs  = 0;       // last connect or write from the app
inline uint32_t      bleAdvRestarts     = 0;       // watchdog: advertising restarted
inline uint32_t      blePhantomClears   = 0;       // watchdog: client flag with no connection
inline uint32_t      bleIdleDrops       = 0;       // watchdog: silent app dropped
inline uint32_t      bleAdvRefreshes    = 0;       // watchdog: idle advertising re-keyed
inline uint32_t      bleConnectedAtMs   = 0;       // when the current app connected
inline uint32_t      bleConnEvents      = 0;       // every connect/disconnect (forensics trigger)

// Continuous channel streaming ("View channels" live bars): when armed, the
// receiver pushes compact "S|us0,..,us15|age\n" frames on the notify
// characteristic whenever the bridge is otherwise idle. Push beats polling:
// no request leg, so stick-to-screen latency is one radio slot + frame gap.
inline bool     bleStreamOn   = false;
inline uint32_t bleStreamMs   = 50;      // frame interval (20-200 clamped)
inline uint32_t bleStreamLast = 0;
inline uint32_t bleStreamArm  = 0;       // page re-arms every ~25 s; auto-off at 60

inline String  bleInbox;            // accumulating request payload
inline size_t  bleInboxExpected = 0;
inline volatile bool bleReqReady = false;   // full request waiting for blePoll()

// ── BLE OTA push ────────────────────────────────────────────────────
// The app downloads firmware with the PHONE's internet (WiFi or 5G) and
// streams it here in raw chunks: [0xA5][u32 offset LE][payload]. Chunks are
// write-without-response for speed; the app resyncs via /api/bleota/status
// (which still flows through the normal 'Q' request lane between chunks).
inline volatile bool     bleOtaActive = false;
inline int               bleOtaCmd = 0;          // U_FLASH / U_SPIFFS
inline volatile uint32_t bleOtaSize = 0;
inline volatile uint32_t bleOtaGot  = 0;
inline volatile uint32_t bleOtaLastChunkMs = 0;
inline String            bleOtaError;
// Defined in WebPages.h (included after this header): the web-files lifeboat
// + the half-image wipe, shared with the stall watchdog in blePoll().
inline void fsFlashEnded(bool ok, size_t written);
inline int  restoreBackupsFromRam();
inline int  restoreFlightsFromRam();

// captured response
inline bool    bleActive   = false; // a handler is running against BLE
inline bool    bleSent     = false; // handler called send()
inline int     bleCode     = 200;
inline String  bleType;
inline String  bleBody;
inline String  bleLocation;
// Request id (0.9.746). The app numbers every request ("X-Req: 17") and we
// echo it in the reply header's location slot as "#17" whenever the reply is
// not a redirect. Before this the bridge had NO way to tie a reply to a
// request: when the app gave up on a slow one (4 s) and sent the next, the
// receiver silently dropped the new one (it was still inside the handler)
// and then delivered the OLD reply — which the app took as the answer to the
// NEW request, and every reply after that was one behind. Malcolm's update
// page read /api/time's {"ok":true} as state.json and announced "no WiFi
// here" beside a router at -33 dBm. Old apps ignore location on a 2xx, so
// this is invisible to them.
inline String  bleReqId;
// Set from the NimBLE task when a fresh 'Q' arrives while a handler is still
// running (the app has given up on it). The finished reply is then thrown
// away instead of pumped: a stale reply is never useful and, to an old app
// without ids, actively misleading.
inline volatile bool bleReplyStale = false;

// outbound pump
inline bool    blePumping  = false;
inline String  bleHeaderFrame;
inline size_t  bleTxOffset = 0;

inline NimBLECharacteristic* bleRespChr = nullptr;

// Real negotiated ATT MTU for the live connection, captured in onMTUChange.
// NimBLEDevice::getMTU() is the global PREFERRED value and does not track
// per-connection negotiation — on Android it read back tiny (59), forcing
// ~56-byte chunks so a 2.6 KB reply needed ~47 notifies, which exhausted
// the host mbuf pool after the first chunk and stalled the whole response.
inline uint16_t bleConnMtu = 23;

// parsed request context (valid while bleActive)
inline String bleMethod, blePath;
inline std::map<String, String> bleArgs;
inline std::map<String, String> bleHeaders;

//*********************************************************************
//  URL decoding + query/form parsing
//*********************************************************************

inline String bleUrlDecode(const String& s) {
    String out;
    out.reserve(s.length());
    for (size_t i = 0; i < s.length(); ++i) {
        char c = s[i];
        if (c == '+') out += ' ';
        else if (c == '%' && i + 2 < s.length()) {
            auto hex = [](char h) -> int {
                if (h >= '0' && h <= '9') return h - '0';
                if (h >= 'a' && h <= 'f') return h - 'a' + 10;
                if (h >= 'A' && h <= 'F') return h - 'A' + 10;
                return 0;
            };
            out += (char)((hex(s[i + 1]) << 4) | hex(s[i + 2]));
            i += 2;
        } else out += c;
    }
    return out;
}

inline void bleParseParams(const String& s) {
    size_t start = 0;
    while (start < s.length()) {
        int amp = s.indexOf('&', start);
        String pair = (amp < 0) ? s.substring(start) : s.substring(start, amp);
        int eq = pair.indexOf('=');
        if (eq > 0) bleArgs[bleUrlDecode(pair.substring(0, eq))] = bleUrlDecode(pair.substring(eq + 1));
        else if (pair.length()) bleArgs[bleUrlDecode(pair)] = "";
        if (amp < 0) break;
        start = amp + 1;
    }
}

//*********************************************************************
//  ReqRouter — WebServer look-alike; forwards to WiFi or captures for BLE
//*********************************************************************

struct BleRoute {
    String path;
    HTTPMethod method;                 // HTTP_ANY when registered without one
    WebServer::THandlerFunction fn;
};

class ReqRouter {
public:
    std::vector<BleRoute> routes;
    WebServer::THandlerFunction notFoundFn;

    // ---- registration (records for BLE dispatch, forwards to real server) ----
    void on(const String& path, WebServer::THandlerFunction fn) {
        routes.push_back({ path, HTTP_ANY, fn });
        ::server.on(path, fn);
    }
    void on(const String& path, HTTPMethod m, WebServer::THandlerFunction fn) {
        routes.push_back({ path, m, fn });
        ::server.on(path, m, fn);
    }
    void onNotFound(WebServer::THandlerFunction fn) {
        notFoundFn = fn;
        ::server.onNotFound(fn);
    }
    void collectHeaders(const char* names[], size_t count) {
        ::server.collectHeaders(names, count);   // BLE accepts any header already
    }

    // ---- request context ----
    String arg(const String& name) {
        if (bleActive) {
            auto it = bleArgs.find(name);
            return it == bleArgs.end() ? String() : it->second;
        }
        return ::server.arg(name);
    }
    bool hasArg(const String& name) {
        if (bleActive) return bleArgs.count(name) > 0;
        return ::server.hasArg(name);
    }
    String header(const String& name) {
        if (bleActive) {
            auto it = bleHeaders.find(name);
            return it == bleHeaders.end() ? String() : it->second;
        }
        return ::server.header(name);
    }

    // ---- response ----
    void sendHeader(const String& k, const String& v, bool first = false) {
        if (bleActive) {
            if (k.equalsIgnoreCase("Location")) bleLocation = v;
            return;                                 // other headers are moot over BLE
        }
        ::server.sendHeader(k, v, first);
    }
    void send(int code, const char* type, const String& body) {
        if (bleActive) { bleCode = code; bleType = type; bleBody = body; bleSent = true; return; }
        ::server.send(code, type, body);
    }
    void send(int code, const String& type, const String& body) { send(code, type.c_str(), body); }
    void send(int code, const char* type, const char* body)     { send(code, type, String(body)); }
    void send_P(int code, PGM_P type, PGM_P content) {
        if (bleActive) {
            bleCode = code;
            bleType = String(FPSTR(type));
            bleBody = String(FPSTR(content));
            bleSent = true;
            return;
        }
        ::server.send_P(code, type, content);
    }
    template <typename FileT>
    size_t streamFile(FileT& f, const String& contentType) {
        if (bleActive) {
            size_t len = f.size();
            if (len > BLE_MAX_RESPONSE) {
                bleCode = 413; bleType = "text/plain";
                bleBody = "too large for BLE — use WiFi";
                bleSent = true;
                return 0;
            }
            bleBody = "";
            bleBody.reserve(len);
            uint8_t buf[512];
            size_t n;
            while ((n = f.read(buf, sizeof(buf))) > 0) bleBody.concat((const char*)buf, n);
            bleCode = 200; bleType = contentType; bleSent = true;
            return bleBody.length();
        }
        return ::server.streamFile(f, contentType);
    }
};

inline ReqRouter g_bleRouter;

//*********************************************************************
//  NimBLE callbacks — enqueue only, never execute
//*********************************************************************

class BleReqCallbacks : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* c, NimBLEConnInfo& connInfo) override {
        bleLastActivityMs = millis();
        std::string v = c->getValue();
        if (v.empty()) return;
        if (bleReqReady) {
            // A handler is still running the previous request. A new 'Q' now
            // means the app gave up on it: its reply must NOT go out (0.9.746).
            // The new request itself is still lost — the app times out and
            // asks again — but it can no longer be answered with the wrong
            // body.
            if (v[0] == 'Q') bleReplyStale = true;
            return;
        }
        if (v[0] == 'Q') {                              // new request
            // The app is strictly one-request-at-a-time, so a new 'Q' while
            // we are still pumping means it gave up on that response (stall
            // timeout). Drop the stale pump immediately — otherwise its
            // leftover chunks arrive ahead of the new response and derail
            // the app's framing.
            if (blePumping) { blePumping = false; bleBody = ""; bleHeaderFrame = ""; }
            size_t bar = v.find('|');
            if (bar == std::string::npos) return;
            bleInboxExpected = strtoul(v.substr(1, bar - 1).c_str(), nullptr, 10);
            if (bleInboxExpected == 0 || bleInboxExpected > BLE_MAX_REQUEST) { bleInboxExpected = 0; return; }
            bleInbox = "";
            bleInbox.reserve(bleInboxExpected);
            bleInbox.concat(v.data() + bar + 1, v.size() - bar - 1);
        } else if (v[0] == '+') {                       // continuation
            if (!bleInboxExpected) return;
            bleInbox.concat(v.data() + 1, v.size() - 1);
        } else if ((uint8_t) v[0] == 0xA5) {            // raw OTA chunk
            if (!bleOtaActive || v.size() < 6) return;
            uint32_t off = (uint8_t) v[1] | ((uint8_t) v[2] << 8) |
                           ((uint8_t) v[3] << 16) | ((uint32_t)(uint8_t) v[4] << 24);
            if (off != bleOtaGot) return;               // out of sequence — app resyncs via status
            size_t n = v.size() - 5;
            if (Update.write((uint8_t *) v.data() + 5, n) == n)
                bleOtaGot += n;
            else if (bleOtaError.length() == 0) {
                bleOtaError = Update.errorString();
                events.add((String("BLE OTA write error at ") + (bleOtaGot / 1024) + " KB: " + bleOtaError).c_str());
            }
            bleOtaLastChunkMs = millis();
            return;
        } else return;
        if (bleInboxExpected && bleInbox.length() >= bleInboxExpected) {
            bleReplyStale = false;                       // this request is fresh
            bleReqReady = true;                          // blePoll() takes it from here
        }
    }
};

class BleServerCallbacks : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* s, NimBLEConnInfo& info) override {
        bleClientConnected = true;
        bleLastActivityMs  = millis();
        bleConnectedAtMs   = millis();
        bleConnEvents++;
        bleStatsClientUp   = true;                          // link stats: quarantine BLE desense
        bleStatsQuietUntilMs = millis() + 4000;
        bleConnMtu = 23;                                    // until the MTU exchange
        events.add("BLE app connected");
        // Ask for fast-ish connection parameters: good throughput, still polite.
        s->updateConnParams(info.getConnHandle(), 12, 24, 0, 400);
    }
    void onMTUChange(uint16_t mtu, NimBLEConnInfo& info) override {
        bleConnMtu = mtu;                                   // note the negotiated MTU
    }
    void onDisconnect(NimBLEServer* s, NimBLEConnInfo& info, int reason) override {
        bleClientConnected = false;
        bleStatsClientUp   = false;
        bleStatsQuietUntilMs = millis() + 4000;             // the disconnect burst desenses too
        bleConnMtu = 23;
        bleReqReady = false;
        blePumping  = false;
        // The HCI reason says WHO let go (0.9.746): 0x08 supervision timeout
        // (radio lost each other), 0x13 the phone ended it, 0x16 we ended
        // it, 0x3e never established. Malcolm's 2026-09-17 drop logged only
        // "disconnected", which settled nothing.
        { char m[56]; snprintf(m, sizeof m, "BLE app disconnected (reason 0x%02x)", (unsigned)(reason & 0xFF)); events.add(m); }
        bleConnEvents++;
        if (bleStarted) NimBLEDevice::startAdvertising();   // not when BLE is meant to be off
    }
};

//*********************************************************************
//  bleStart / bleStop — mirror the WiFi lifecycle exactly
//
//  The controller is initialised ONCE at boot (bleInitOnce, from setup)
//  and never de-initialised: enabling the BT controller while WiFi is
//  mid-connect trips the coexistence layer's abort() (seen on hardware
//  via the NET_NO_WIFI → "TX lost, WiFi back up" path, 0.9.207 bootloop).
//  An initialised stack that isn't advertising transmits nothing, so the
//  flying rule — no BLE emissions when WiFi is off — still holds;
//  start/stop below only gate advertising + live connections.
//*********************************************************************

inline void bleInitOnce() {
    if (bleInited) return;
    NimBLEDevice::init(g_effectiveName.c_str());        // GAP name = model name
    NimBLEDevice::setMTU(517);
    NimBLEDevice::setPower(ESP_PWR_LVL_P3);             // modest: bench-range only, kind to the nRF24s
    NimBLEServer* srv = NimBLEDevice::createServer();
    srv->setCallbacks(new BleServerCallbacks());
    NimBLEService* svc = srv->createService(BLE_SVC_UUID);
    NimBLECharacteristic* req = svc->createCharacteristic(
        BLE_REQ_UUID, NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
    req->setCallbacks(new BleReqCallbacks());
    bleRespChr = svc->createCharacteristic(BLE_RESP_UUID, NIMBLE_PROPERTY::NOTIFY);
    svc->start();
    NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
    adv->addServiceUUID(BLE_SVC_UUID);
    // NimBLE 2.x does NOT copy the init() name into the advert payload —
    // without setName() the scan list shows a nameless device (found on
    // hardware). ORDER MATTERS: enableScanResponse() must come FIRST.
    // setName() checks the scan-response flag at call time; with it still
    // false the name is forced into the main advert packet, where flags +
    // the 128-bit service UUID already use 21 of 31 bytes — any name over
    // 8 chars fails silently and the device advertises nameless (phones
    // then show a cached or placeholder name, e.g. "RXV2" for BenchTest).
    adv->enableScanResponse(true);
    adv->setName(g_effectiveName.c_str());
    bleInited = true;
    Serial.println("[ble] stack initialised (silent)");
}

inline bool bleAdvertising() { return bleStarted; }

inline void bleStart() {
    if (bleStarted) return;
    bleInitOnce();                       // normally already done in setup()
    NimBLEDevice::startAdvertising();
    bleStarted = true;
    bleStatsRadioOn = true;                   // gap/swap stats pause while BT is on at all
    bleStatsQuietUntilMs = millis() + 4000;   // the BT radio's first-keying burst desenses the nRF24s
    // Physical "Bluetooth is ready" cue: wave the chosen servo channels
    // (Output.h) when advertising starts — power-on included. Debounced:
    // one announcement per revival, however many triggers fire.
    if (autoWaveAllowed()) bleWaveStartMs = millis();
    Serial.printf("[ble] advertising as '%s'\n", g_effectiveName.c_str());
    events.add("BLE config on");
}

inline void bleStop() {
    if (!bleStarted) return;
    bleStarted = false;                  // first: stops onDisconnect re-advertising
    NimBLEDevice::stopAdvertising();
    NimBLEServer* srv = NimBLEDevice::getServer();
    if (srv) {                           // drop live phone links — truly silent now
        for (int i = 0; srv->getConnectedCount() > 0 && i < 50; i++) {
            srv->disconnect(srv->getPeerInfo(0));
            delay(10);                   // let the host task run the teardown
        }
    }
    bleClientConnected = false;
    bleStatsClientUp   = false;
    bleStatsRadioOn    = false;
    bleStatsQuietUntilMs = millis() + 4000;   // teardown burst; stats resume cleanly after
    bleReqReady = false;
    blePumping  = false;
    Serial.println("[ble] off");
    events.add("BLE config off");
}

//*********************************************************************
//  Request execution + chunked response pump — called from loop()
//*********************************************************************


// Early pump: push the CURRENT handler's captured response to the app NOW,
// from inside the handler. Needed by handlers that reboot or silence the
// radios right after replying — their reply is normally pumped from loop()
// AFTER the handler returns, which would be too late. Small replies only.
inline bool bleEarlyPumped = false;

inline void bleEarlyPump() {
    if (!bleActive || !bleSent || !bleClientConnected || !bleRespChr) return;
    const String loc = (bleLocation.length() || !bleReqId.length()) ? bleLocation : ("#" + bleReqId);
    String hdr = "R" + String(bleCode) + "|" + bleType + "|" +
                 String(bleBody.length()) + "|" + loc + "\n";
    for (int t = 0; t < 50 && !bleRespChr->notify((const uint8_t*)hdr.c_str(), hdr.length()); ++t)
        delay(10);
    size_t mtu   = bleConnMtu > 23 ? bleConnMtu : 23;
    size_t chunk = (mtu > 23 ? mtu - 3 : 20);
    if (chunk > 240) chunk = 240;
    size_t off = 0;
    int stalls = 0;
    while (off < bleBody.length() && stalls < 100) {
        size_t n = min(chunk, bleBody.length() - off);
        if (!bleRespChr->notify((const uint8_t*)bleBody.c_str() + off, n)) { delay(10); ++stalls; continue; }
        off += n;
    }
    delay(150);
    bleBody = "";
    bleEarlyPumped = true;
}

// Fly-quiet: stop advertising but KEEP the live phone connection, so the
// "RF-only mode" page keeps a working "return to menu" button. The link
// dies naturally when the user closes the app or walks away — and because
// bleStarted is false, onDisconnect will NOT re-advertise: true silence.
inline bool bleHasClient() { return bleClientConnected; }

inline void bleFlyQuiet() {
    if (!bleStarted) return;
    bleStarted = false;
    NimBLEDevice::stopAdvertising();
    // Stats: the RADIO-on flag clears here so that once the kept-alive phone
    // link drops (app closed / out of range), bleStatsClientUp goes false in
    // onDisconnect and the flight's gap/swap stats START RECORDING — without
    // this, a fly-mode entered with the phone attached would quarantine the
    // whole flight. While the client is still attached, bleStatsClientUp
    // keeps the quarantine correctly in force.
    bleStatsRadioOn = false;
    Serial.println("[ble] fly-quiet: advertising off, live link kept");
    events.add("BLE quiet (fly) — link kept until app closes");
}

inline void bleExecuteRequest() {
    // Parse the framed payload.
    bleMethod = ""; blePath = ""; bleArgs.clear(); bleHeaders.clear();
    int nl = bleInbox.indexOf('\n');
    if (nl < 0) { bleReqReady = false; return; }
    String reqLine = bleInbox.substring(0, nl);
    int sp = reqLine.indexOf(' ');
    if (sp < 0) { bleReqReady = false; return; }
    bleMethod = reqLine.substring(0, sp);
    String pathAndQuery = reqLine.substring(sp + 1);
    int qm = pathAndQuery.indexOf('?');
    blePath = (qm < 0) ? pathAndQuery : pathAndQuery.substring(0, qm);
    if (qm >= 0) bleParseParams(pathAndQuery.substring(qm + 1));

    // headers until blank line, body after
    int pos = nl + 1;
    while (pos < (int)bleInbox.length()) {
        int lineEnd = bleInbox.indexOf('\n', pos);
        if (lineEnd < 0) { pos = bleInbox.length(); break; }
        String line = bleInbox.substring(pos, lineEnd);
        pos = lineEnd + 1;
        if (line.length() == 0) break;                   // end of headers
        int colon = line.indexOf(':');
        if (colon > 0) {
            String k = line.substring(0, colon);
            String v = line.substring(colon + 1);
            v.trim();
            bleHeaders[k] = v;
        }
    }
    String body = bleInbox.substring(pos);
    if (bleMethod == "POST" && body.length()) bleParseParams(body);   // form-encoded
    bleReqId = "";
    { auto it = bleHeaders.find("X-Req"); if (it != bleHeaders.end()) bleReqId = it->second; }

    // Dispatch through the SAME handlers the web portal uses.
    HTTPMethod m = (bleMethod == "POST") ? HTTP_POST : HTTP_GET;
    WebServer::THandlerFunction fn = g_bleRouter.notFoundFn;
    for (auto& r : g_bleRouter.routes) {
        if (r.path == blePath && (r.method == HTTP_ANY || r.method == m)) { fn = r.fn; break; }
    }
    bleActive = true;
    bleSent = false;
    bleCode = 404; bleType = "text/plain"; bleBody = "not found"; bleLocation = "";
    if (fn) fn();
    bleActive = false;
    if (bleEarlyPumped) {                    // reply already sent from inside the handler
        bleEarlyPumped = false;
        bleBody = ""; bleHeaderFrame = "";
        blePumping = false;
        bleInbox = "";
        bleInboxExpected = 0;
        bleReqReady = false;
        return;
    }
    if (!bleSent) { bleCode = 500; bleType = "text/plain"; bleBody = "handler sent nothing"; }

    if (bleReplyStale) {
        // The app gave up on this request while we were answering it (a fresh
        // 'Q' arrived mid-handler). Nobody is waiting for this reply — drop it.
        bleReplyStale = false;
        bleBody = ""; bleHeaderFrame = "";
        bleInbox = ""; bleInboxExpected = 0;
        bleReqReady = false;
        return;
    }
    // Frame the response and start pumping. A non-redirect reply carries the
    // request id in the location slot so the app can match it (0.9.746).
    const String loc = (bleLocation.length() || !bleReqId.length()) ? bleLocation : ("#" + bleReqId);
    bleHeaderFrame = "R" + String(bleCode) + "|" + bleType + "|" +
                     String(bleBody.length()) + "|" + loc + "\n";
    bleTxOffset = 0;
    blePumping  = true;
    bleInbox = "";
    bleInboxExpected = 0;
    bleReqReady = false;
}

// Emit one channel frame when the bridge is idle and the interval elapsed.
// Never interleaves with a response (gated on !blePumping && !bleReqReady),
// so the app can only ever see an "S|" line BETWEEN responses — its header
// hunt forwards those out of band. Best-effort notify: a congested stack
// just drops the frame; the next one is 50 ms away.
inline void bleStreamPoll() {
    if (!bleStreamOn || !bleClientConnected || !bleRespChr || bleReqReady || blePumping) return;
    uint32_t now = millis();
    if ((uint32_t)(now - bleStreamArm) > 60000) { bleStreamOn = false; return; }   // page gone
    if ((uint32_t)(now - bleStreamLast) < bleStreamMs) return;
    bleStreamLast = now;
    char f[170];
    int n = snprintf(f, sizeof(f), "S|");
    for (int i = 0; i < 16; ++i)
        n += snprintf(f + n, sizeof(f) - n, "%u%s", (unsigned)channelMicros[i], (i < 15) ? "," : "");
    long age = lastChannelDataMs ? (long)(millis() - lastChannelDataMs) : -1;
    // trailing field: arming state (-1 no arming channel, 0 disarmed, 1 armed)
    // so the page's live ARMED indicator rides the stream instead of costing
    // a 2.5 kB state poll every second (which paused the stream — the
    // "brief pauses" Malcolm saw). Same computation as /api/state.json.
    bool live    = (rx.lastMillis != 0) && ((uint32_t)(millis() - rx.lastMillis) < 2000);
    bool armedNow = live && armingChannel >= 1 && armingChannel <= 16 &&
                    channelMicros[armingChannel - 1] > 1500;
    int armState = armingChannel ? (armedNow ? 1 : 0) : -1;
    n += snprintf(f + n, sizeof(f) - n, "|%ld|%d\n", age, armState);
    bleRespChr->notify((const uint8_t*)f, (size_t)n);
}

//*********************************************************************
//  Bluetooth watchdog (Malcolm 2026-09-10: the dongle ran all night on
//  WiFi, memory steady, yet the app could not connect until a reboot).
//  Every 10 s while BLE is meant to be on:
//   1. a client flag the stack no longer backs is forgotten (advertise again)
//   2. advertising that silently stopped with no client is restarted
//   3. an app silent for 10 min is dropped so another phone can connect
//      (a suspended phone app keeps its link open but never talks)
//  THIS CODE FLIES IN THE RECEIVER TOO (Malcolm 2026-09-10: a dongle fix
//  must never interrupt normal receiver functions in flight), so:
//   - `allowed` is decided by main.cpp: receiver = NO transmitter link on
//     the air (any TX heard in the last second = hands off, an advertising
//     restart or a disconnect burst desenses the nRF24s); dongle = the FC
//     says disarmed. Fly-quiet / bleStop also make bleStarted false.
//   - every condition must hold on TWO consecutive ticks (20 s) before an
//     action, so a connect/disconnect race can never be mistaken for a fault.
//  Counters go to state.json "ble".
//*********************************************************************
inline void bleWatchdogTick(bool allowed, uint32_t idleDropMs) {
    static uint32_t lastMs = 0, lastRefreshMs = 0;
    static uint8_t  phantomSeen = 0, advStoppedSeen = 0, idleSeen = 0;
    if (!bleInited || !bleStarted || !allowed) { phantomSeen = advStoppedSeen = idleSeen = 0; lastRefreshMs = millis(); return; }
    if ((uint32_t)(millis() - lastMs) < 10000) return;
    lastMs = millis();
    NimBLEServer* srv = NimBLEDevice::getServer();
    if (!srv) return;
    const uint8_t conns = srv->getConnectedCount();

    // 4. Belt and braces for a radio that the host THINKS is advertising:
    //    with nobody connected for 10 min, re-key the advertising (stop +
    //    start). Silent (counter only) - it is routine, not a fault.
    if (!bleClientConnected && conns == 0 && (uint32_t)(millis() - lastRefreshMs) > 10UL * 60UL * 1000UL) {
        lastRefreshMs = millis();
        NimBLEDevice::stopAdvertising();
        NimBLEDevice::startAdvertising();
        bleAdvRefreshes++;
        return;
    }
    if (bleClientConnected) lastRefreshMs = millis();

    const bool phantom = bleClientConnected && conns == 0;
    phantomSeen = phantom ? phantomSeen + 1 : 0;
    if (phantomSeen >= 2) {
        phantomSeen = 0;
        bleClientConnected = false;
        blePhantomClears++;
        events.add("BLE watchdog: phantom client forgotten - advertising again");
        NimBLEDevice::startAdvertising();
        return;
    }
    const bool advStopped = !bleClientConnected && conns == 0 && !NimBLEDevice::getAdvertising()->isAdvertising();
    advStoppedSeen = advStopped ? advStoppedSeen + 1 : 0;
    if (advStoppedSeen >= 2) {
        advStoppedSeen = 0;
        bleAdvRestarts++;
        events.add("BLE watchdog: advertising had stopped - restarted");
        NimBLEDevice::startAdvertising();
        return;
    }
    const bool idle = bleClientConnected && conns > 0 && !bleOtaActive &&
                      (uint32_t)(millis() - bleLastActivityMs) > idleDropMs;
    idleSeen = idle ? idleSeen + 1 : 0;
    if (idleSeen >= 2) {
        idleSeen = 0;
        bleIdleDrops++;
        char m[120]; snprintf(m, sizeof m, "BLE watchdog: app %s silent for %lu min - dropped so a phone can connect",
                              srv->getPeerInfo(0).getAddress().toString().c_str(), (unsigned long)(idleDropMs / 60000UL));
        events.add(m);
        srv->disconnect(srv->getPeerInfo(0));          // onDisconnect re-advertises
        bleLastActivityMs = millis();
    }
}

// state.json "ble" block - what the watchdog sees
inline void bleStateJson(String& j) {
    NimBLEServer* srv = bleInited ? NimBLEDevice::getServer() : nullptr;
    const bool adv = bleInited && NimBLEDevice::getAdvertising()->isAdvertising();
    const uint8_t conns = srv ? srv->getConnectedCount() : 0;
    std::string peer = conns ? srv->getPeerInfo(0).getAddress().toString() : "";
    char b[300];
    snprintf(b, sizeof(b), ",\"ble\":{\"on\":%s,\"adv\":%s,\"client\":%s,\"conns\":%u,\"peer\":\"%s\",\"since_s\":%lu,\"idle_s\":%lu,\"adv_restarts\":%lu,\"phantom\":%lu,\"idle_drops\":%lu,\"adv_refresh\":%lu}",
             bleStarted ? "true" : "false", adv ? "true" : "false", bleClientConnected ? "true" : "false",
             (unsigned)conns, peer.c_str(),
             (unsigned long)((conns && bleConnectedAtMs) ? (millis() - bleConnectedAtMs) / 1000 : 0),
             (unsigned long)((bleLastActivityMs ? (millis() - bleLastActivityMs) : 0) / 1000),
             (unsigned long)bleAdvRestarts, (unsigned long)blePhantomClears, (unsigned long)bleIdleDrops,
             (unsigned long)bleAdvRefreshes);
    j += b;
}

inline void blePoll() {
    // OTA stall watchdog: abandon a transfer whose chunks stop coming, so a
    // dropped link can't leave Update half-open (current firmware stays
    // bootable — nothing commits until end()).
    if (bleOtaActive && (uint32_t)(millis() - bleOtaLastChunkMs) > 30000) {
        Update.abort();
        bleOtaActive = false;
        bleOtaError = "transfer stalled";
        if (bleOtaCmd == U_SPIFFS) {
            // Web files: the partition may be half written and LittleFS is
            // unmounted since begin — wipe rather than ever mount a half image
            // (fsFlashEnded, WebPages.h), remount, put the lifeboat ashore.
            fsFlashEnded(false, bleOtaGot);
            littleFsMounted = LittleFS.begin(false) || LittleFS.begin(true);
            restoreBackupsFromRam();
            restoreFlightsFromRam();
            events.add(bleOtaGot ? "BLE OTA web files stalled — aborted, half image wiped"
                                 : "BLE OTA web files stalled — aborted (old pages intact)");
        } else events.add("BLE OTA stalled — aborted (old firmware intact)");
    }
    // Keep serving while a client is CONNECTED even when advertising is
    // off (fly-quiet mode keeps the one live phone link) — otherwise the
    // RF-only screen's buttons would be talking to a mute receiver.
    if (!bleStarted && !bleClientConnected) return;
    if (bleReqReady && !blePumping) bleExecuteRequest();
    if (!blePumping || !bleRespChr || !bleClientConnected) {
        if (blePumping && !bleClientConnected) blePumping = false;   // client gone — drop it
        bleStreamPoll();   // idle — the stream may speak
        return;
    }
    // Chunk size: honour the negotiated MTU, but CAP at 240 bytes. Some
    // phones (e.g. a Samsung Fold) advertise a big ATT MTU (517) yet
    // silently drop notifications larger than their true limit (~452) —
    // the app then receives one short chunk and stalls. 240 fits inside
    // one link-layer packet (251 B DLE) on every device, so nothing is
    // ever lost. Small replies still ride a single chunk. (Same lesson
    // proved on the MCP fuel station's BLE bridge.)
    size_t mtu   = bleConnMtu > 23 ? bleConnMtu : NimBLEDevice::getMTU();
    size_t chunk = (mtu > 23 ? mtu - 3 : 20);
    if (chunk > 240) chunk = 240;
    size_t sentThisCall = 0;

    // Forensics: a reply whose notifies keep being refused for 3 s is logged
    // ONCE (radio congested — WiFi hunting? — or the phone never subscribed).
    // "The app connects but nothing comes" is otherwise invisible in the log.
    static uint32_t stallSinceMs = 0;
    auto refused = [&]() {
        if (!stallSinceMs) stallSinceMs = millis();
        else if ((uint32_t)(millis() - stallSinceMs) > 3000) {
            stallSinceMs = 0;                            // re-arm: logs again after another 3 s
            events.add("BLE reply stalled 3 s — notifies refused (radio busy?)");
        }
    };

    // header frame first (fits one chunk by construction of our short types)
    if (bleTxOffset == 0 && bleHeaderFrame.length()) {
        if (!bleRespChr->notify((const uint8_t*)bleHeaderFrame.c_str(), bleHeaderFrame.length())) { refused(); return; }
        sentThisCall += bleHeaderFrame.length();   // the header's OWN length, not a whole chunk
        bleHeaderFrame = "";
    }
    // Time-bounded: whatever is left rides the next pass through bleTxOffset,
    // which already carries the position across calls — that is exactly what
    // blePumping was built for. With a transmitter linked the budget tightens,
    // because then a stall is dead air on the control link.
    const bool txLive = rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000;
    const uint32_t budgetUs = txLive ? BLE_PUMP_US_FLYING : BLE_PUMP_US;
    const uint32_t pumpT0 = micros();
    while (bleTxOffset < bleBody.length() && sentThisCall < BLE_PUMP_BUDGET) {
        if ((uint32_t)(micros() - pumpT0) > budgetUs) return;   // rest next pass
        size_t n = min(chunk, bleBody.length() - bleTxOffset);
        if (!bleRespChr->notify((const uint8_t*)bleBody.c_str() + bleTxOffset, n)) {
            refused();
            return;                                      // stack congested — retry next loop
        }
        bleTxOffset  += n;
        sentThisCall += n;
    }
    stallSinceMs = 0;
    if (bleTxOffset >= bleBody.length() && bleHeaderFrame.length() == 0) {
        blePumping = false;
        bleBody = "";
    }
}

#endif // _SRC_BLECONFIG_H
