// The screen's Bluetooth client to the receiver (screen 1.11.0, 2026-10-06): a NimBLE central that finds a Version 2
// receiver, joins its bridge (RXV2 src/BleConfig.h, framed in lib/LdrcBle) and relays requests for whoever asks - the
// bench through the workshop door for now, the main board's Rotorflight pages next (Malcolm: "those we already support
// should go via Bluetooth rather than the current method which can be removed"; the processing stays on the Teensy,
// the screen is the pipe).
//
// Everything that blocks (the scan, the connection, a write that waits for its acknowledgement) runs in a task of its
// own, so the Nextion wire is never starved: loop() only posts orders and reads results. The stack is brought up on
// demand and taken down after (it costs some 50 kB of RAM while up, and battery). The radio rule is the WiFi's: never
// while the model could be flying.
#pragma once
#include <NimBLEDevice.h>
#include "LdrcBle.h"
#include <algorithm>

enum BleState : uint8_t { BLE_OFF = 0, BLE_STARTING, BLE_SCANNING, BLE_CONNECTING, BLE_READY, BLE_FAILED, BLE_STOPPING };
static const char *bleStateName(int s) { static const char *n[] = { "off", "starting", "scanning", "connecting", "ready", "failed", "stopping" }; return s >= 0 && s <= 6 ? n[s] : "?"; }
struct BleSeen { std::string name, addr; int rssi; };
static volatile BleState bleState = BLE_OFF;
static std::string bleWhy;                                     // (failed) why
static std::vector<BleSeen> bleSeen;                           // the receivers the last scan found
static std::string bleTarget;                                  // the receiver wanted, by name ("" = the strongest found)
static std::string bleJoined; static int bleMtu = 0;           // what we are joined to
static SemaphoreHandle_t bleMutex = nullptr;
static TaskHandle_t bleTaskHandle = nullptr;
static volatile bool bleGone = false;                           // (1.11.15) the disconnect event has arrived
static volatile bool bleWifiKick = false;                      // (1.11.11) the stack has just gone down: the WiFi joins afresh (loop())
// 1.11.13 (Malcolm: "Sometimes connecting to Bluetooth takes a very long time, and sometimes it's quicker"): the last
// 24 happenings with their time, from either side, in /ble/status and /status ("log"): each join's timeline.
static std::string bleLog[24]; static int bleLogN = 0;
static void bleNote(const std::string &what) {
    if (!bleMutex) bleMutex = xSemaphoreCreateMutex();
    if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(50)) == pdTRUE) { bleLog[bleLogN % 24] = std::to_string(millis()) + " " + what; ++bleLogN; xSemaphoreGive(bleMutex); }
}
static unsigned bleStackSpare() { return bleTaskHandle ? (unsigned) uxTaskGetStackHighWaterMark(bleTaskHandle) : 0u; }   // (1.11.8) for /status
// one request at a time
struct BleRequest { std::string method, path, body, type; uint32_t id = 0; };
static BleRequest bleReq; static volatile bool bleReqPending = false, bleReqDone = false; static ldrc::BleReply bleLast; static std::string bleReqError;
static uint32_t bleNextId = 1, bleReqStartedAt = 0;
// The main board's pipe (1.11.1): its Rotorflight parameter packets, as words, to the receiver's /api/txparams, and the
// block being read back to it as telemetry items ("ldrctel 25:AABBCCDD 26:..."), the way the radio link's acks carried
// them. The main board names the receiver by its board id (what it learned at binding), so the right one is joined.
static std::string bleWantMac;                                 // "" = the nearest receiver will do
static std::vector<std::string> bleTxQueue;                    // parameter packets waiting ("12,321,5000,0,...")
static uint32_t blePollUntil = 0, blePollLast = 0;             // a read is open: ask for the block until then
static std::string bleTelLast;                                 // the items as last told to the main board
static std::vector<std::string> bleMail;                       // texts for the main board, sent from loop() (the task must not write the wire)
static int blePipeTold = -1;                                   // the pipe state as last told (0 off, 1 joining, 2 ready, 3 failed)
static volatile int bleOrder = 0;                              // 1 on, 2 off (from loop())
static ldrc::BleBridge bleBridge;
static NimBLEClient *bleClient = nullptr; static NimBLERemoteCharacteristic *bleReqChr = nullptr, *bleRespChr = nullptr;
static volatile bool bleReplyReady = false;

struct BleClientCb : public NimBLEClientCallbacks {
    void onDisconnect(NimBLEClient *, int reason) override { bleGone = true; bleNote("disconnected (" + std::to_string(reason) + ")"); if (bleState == BLE_READY) { bleState = BLE_FAILED; bleWhy = "the receiver dropped the connection (" + std::to_string(reason) + ")"; } }
};
static BleClientCb bleClientCb;

static void bleNotify(NimBLERemoteCharacteristic *, uint8_t *data, size_t len, bool) {
    if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(50)) != pdTRUE) return;
    if (bleReqPending && bleBridge.feed(data, len, bleReq.id)) { bleLast = bleBridge.reply(); bleReplyReady = true; }
    xSemaphoreGive(bleMutex);
}

static bool bleServeNow(const std::string &method, const std::string &path, const std::string &body, const std::string &type, ldrc::BleReply &out, std::string &err);   // (the task, below)
static void bleLeave();
static std::string bleUpper(std::string s) { for (auto &c : s) c = (char) toupper((unsigned char) c); return s; }
// 1.11.14 (Malcolm: "Sometimes connecting to Bluetooth takes a very long time"): the scan stops the moment the model's
// receiver is heard, rather than at the end of its window. Its Bluetooth address is its board id or that plus one to
// three (the ESP32 derives its addresses from one base); heard with such an address it is connected to at once and the
// identity check by its state page is skipped. Any other receiver heard waits for the window to end, as before.
struct BleFound { bool have = false; NimBLEAddress addr; std::string name; int rssi = 0; };
static BleFound bleFound;
static std::string bleScanWant, bleScanTarget;                 // what the scan looks for, copied before it starts (the callback runs in the host task; the main board may change its mind meanwhile)
static bool bleAddrNear(const std::string &adv, const std::string &want) {        // "e0:72:a1:fa:54:bd" against "E072A1FA54BC"
    if (want.size() != 12) return false;
    std::string a; for (char c : adv) if (c != ':') a += (char) toupper((unsigned char) c);
    if (a.size() != 12 || a.compare(0, 10, want, 0, 10) != 0) return false;
    const int x = (int) strtol(a.substr(10).c_str(), nullptr, 16), w = (int) strtol(want.substr(10).c_str(), nullptr, 16);
    return x >= w && x - w <= 3;
}
class BleScanCb : public NimBLEScanCallbacks {
    void onResult(const NimBLEAdvertisedDevice *d) override {
        if (bleFound.have || !d->isAdvertisingService(NimBLEUUID(ldrc::BLE_SVC_UUID))) return;
        const std::string name = d->getName(), addr = d->getAddress().toString();
        if (!bleScanTarget.empty() ? name != bleScanTarget : (!bleScanWant.empty() && !bleAddrNear(addr, bleScanWant))) return;   // not the one wanted: the window goes on
        bleFound.addr = d->getAddress(); bleFound.name = name; bleFound.rssi = d->getRSSI(); bleFound.have = true;
    }
};
static BleScanCb bleScanCb;
static bool bleBridgeUp(const std::string &name, std::string &why);
// 1.11.16: ONE client for the whole session. THE CRASH of 7 Oct (the core dump, read with 1.11.15: task ldrcble, a load
// from address 0x28 in NimBLEClient::setClientCallbacks, called from bleJoin): a client was created for every attempt
// and "deleted" after a failed one - but NimBLE only marks a client that is still connecting or parting for deletion
// later, and it counts until then; at three the next createClient() gives nothing, and 1.11.14 used it without looking.
static bool bleClientReady() {
    if (!bleClient) bleClient = NimBLEDevice::getDisconnectedClient();
    if (!bleClient) bleClient = NimBLEDevice::createClient();
    if (!bleClient) return false;
    bleClient->setClientCallbacks(&bleClientCb, false); bleClient->setConnectTimeout(4000);
    NimBLEClient::Config cfg = bleClient->getConfig(); cfg.connectFailRetries = 1; cfg.deleteOnDisconnect = false; cfg.deleteOnConnectFail = false; bleClient->setConfig(cfg);   // (a dead attempt costs ~8 s, not 15; the client stays ours)
    return true;
}
static bool bleConnectTo(const NimBLEAdvertisedDevice *d, std::string &why) {   // in the task: connect and find the bridge
    const std::string name = d->getName();
    if (!bleClientReady()) { why = "no Bluetooth client to connect with"; vTaskDelay(pdMS_TO_TICKS(400)); return false; }
    if (!bleClient->connect(d, true, false, true)) { why = "could not connect to " + name; vTaskDelay(pdMS_TO_TICKS(400)); return false; }   // (the stack has just cancelled: a moment before the next attempt)
    return bleBridgeUp(name, why);
}
static bool bleConnectAddr(const NimBLEAddress &addr, const std::string &name, std::string &why) {   // (1.11.14) the one the scan stopped for
    if (!bleClientReady()) { why = "no Bluetooth client to connect with"; vTaskDelay(pdMS_TO_TICKS(400)); return false; }
    if (!bleClient->connect(addr, true, false, true)) { why = "could not connect to " + name; vTaskDelay(pdMS_TO_TICKS(400)); return false; }
    return bleBridgeUp(name, why);
}
static void bleHangUp() {                                      // the goodbye, and the wait for it to have gone (1.11.15): the receiver advertises again at once
    if (!bleClient || !bleClient->isConnected()) return;
    bleGone = false;
    bleClient->disconnect();
    for (int i = 0; i < 150 && !bleGone; ++i) vTaskDelay(pdMS_TO_TICKS(10));   // until the DISCONNECT EVENT (isConnected() turns false the moment the goodbye is asked for, long before it has gone out: the receiver saw timeouts, 0x08, every time)
    bleNote(bleGone ? "goodbye said" : "goodbye not answered in 1.5 s");
}
static bool bleBridgeUp(const std::string &name, std::string &why) {           // connected: the service and its two characteristics
    NimBLERemoteService *svc = bleClient->getService(NimBLEUUID(ldrc::BLE_SVC_UUID));
    bleReqChr = svc ? svc->getCharacteristic(NimBLEUUID(ldrc::BLE_REQ_UUID)) : nullptr; bleRespChr = svc ? svc->getCharacteristic(NimBLEUUID(ldrc::BLE_RESP_UUID)) : nullptr;
    if (!bleReqChr || !bleRespChr || !bleRespChr->canNotify() || !bleRespChr->subscribe(true, bleNotify, true)) { why = name + " has no bridge"; bleReqChr = bleRespChr = nullptr; bleHangUp(); return false; }
    bleJoined = name; bleMtu = bleClient->getMTU();
    return true;
}
static bool bleJoin() {                                        // in the task: scan, then the candidates strongest first; the identity checked on each one's state page
    bleState = BLE_SCANNING;
    NimBLEScan *scan = NimBLEDevice::getScan(); scan->setActiveScan(true); scan->setInterval(45); scan->setWindow(30); scan->setMaxResults(20);
    // 1.11.6: the receiver shuts its Bluetooth 30 s after it hears the transmitter at its power-on, so the main board now
    // ASKS it (over the radio link, B44 + receiver 0.9.875) when this menu opens, and it comes up a second or two later.
    // So the scan, and the attempt on what it finds, are repeated for up to about fifteen seconds, unless the pipe is
    // called off meanwhile (the menu left).
    std::string why = "no receiver in reach";
    for (int round = 0; round < 5 && bleOrder != 2; ++round) {
        if (round) { vTaskDelay(pdMS_TO_TICKS(500)); bleState = BLE_SCANNING; }
        scan->clearResults();
        bleFound = BleFound(); bleScanWant = bleWantMac; bleScanTarget = bleTarget; scan->setScanCallbacks(&bleScanCb, false);
        const uint32_t t0 = millis();
        scan->start(2500, false, true);                           // (1.11.14) ends early when the one wanted is heard
        while (scan->isScanning() && !bleFound.have && bleOrder != 2) vTaskDelay(pdMS_TO_TICKS(20));
        if (scan->isScanning()) scan->stop();
        NimBLEScanResults res = scan->getResults();
        bleNote("scan " + std::to_string(round + 1) + ": " + std::to_string(res.getCount()) + " devices in " + std::to_string(millis() - t0) + " ms" + (bleFound.have ? ", " + bleFound.name + " heard" : ""));
        std::vector<BleSeen> seen; std::vector<const NimBLEAdvertisedDevice *> cands;
        for (int i = 0; i < res.getCount(); ++i) {
            const NimBLEAdvertisedDevice *d = res.getDevice(i);
            if (!d->isAdvertisingService(NimBLEUUID(ldrc::BLE_SVC_UUID))) continue;
            BleSeen s; s.name = d->getName(); s.addr = d->getAddress().toString(); s.rssi = d->getRSSI(); seen.push_back(s);
            if (bleTarget.empty() || s.name == bleTarget) cands.push_back(d);
        }
        if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(100)) == pdTRUE) { bleSeen = seen; xSemaphoreGive(bleMutex); }
        std::sort(cands.begin(), cands.end(), [](const NimBLEAdvertisedDevice *a, const NimBLEAdvertisedDevice *b) { return a->getRSSI() > b->getRSSI(); });
        if (bleFound.have && bleOrder != 2) {                          // (1.11.14) the one the scan stopped for: straight in
            bleState = BLE_CONNECTING;
            bleNote("connecting to " + bleFound.name + " (" + std::to_string(bleFound.rssi) + " dBm, by its address)");
            if (bleConnectAddr(bleFound.addr, bleFound.name, why)) { scan->clearResults(); bleState = BLE_READY; bleNote("ready: " + bleJoined + ", MTU " + std::to_string(bleMtu)); return true; }
            bleNote(why);
        }
        if (cands.empty()) { why = seen.empty() ? "no receiver in reach" : "the receiver named is not in reach"; bleNote("no receiver among them"); continue; }
        bleState = BLE_CONNECTING;
        for (size_t i = 0; i < cands.size() && bleOrder != 2; ++i) {
            bleNote("connecting to " + cands[i]->getName() + " (" + std::to_string(cands[i]->getRSSI()) + " dBm)");
            if (!bleConnectTo(cands[i], why)) { bleNote(why); continue; }
            if (bleWantMac.empty()) { scan->clearResults(); bleState = BLE_READY; bleNote("ready: " + bleJoined + " (any receiver)"); return true; }
            ldrc::BleReply r; std::string err;                   // the receiver's identity: its state page says
            if (bleServeNow("GET", "/api/state.json", "", "", r, err) && r.code == 200) {
                const size_t k = r.body.find("\"board_mac\":\"");
                const std::string mac = k == std::string::npos ? "" : bleUpper(r.body.substr(k + 13, 12));
                if (mac == bleWantMac) { scan->clearResults(); bleState = BLE_READY; bleNote("ready: " + bleJoined + ", MTU " + std::to_string(bleMtu)); return true; }
                why = "not the model's receiver (" + bleJoined + ")";
            } else why = "no answer from " + bleJoined + (err.empty() ? "" : ": " + err);
            bleNote(why);
            bleLeave();
        }
    }
    scan->clearResults();
    bleWhy = bleOrder == 2 ? "called off" : why;
    bleNote("failed: " + bleWhy);
    return false;
}
static void bleLeave() {                                       // the link, not the client: that is kept for the next attempt (1.11.16), and goes with the stack
    bleHangUp();
    bleReqChr = bleRespChr = nullptr; bleJoined.clear(); bleMtu = 0;
}
static void bleServe() {                                       // in the task: one request, written in frames; the reply comes by notification
    if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(100)) != pdTRUE) return;
    bleBridge.reset(); bleReplyReady = false; bleReqError.clear();
    const std::vector<std::string> frames = ldrc::BleBridge::frames(bleReq.method, bleReq.path, bleReq.body, bleReq.id, std::min(ldrc::BLE_WRITE_CHUNK, bleMtu > 23 ? bleMtu - 3 : 20), bleReq.type);
    xSemaphoreGive(bleMutex);
    for (auto &f : frames) {
        if (!bleReqChr || !bleClient->isConnected() || !bleReqChr->writeValue((const uint8_t *) f.data(), f.size(), true)) { bleReqError = "the write failed"; bleReqPending = false; bleReqDone = true; return; }
    }
    const uint32_t t0 = millis();
    while (!bleReplyReady && millis() - t0 < 6000 && bleClient && bleClient->isConnected()) vTaskDelay(pdMS_TO_TICKS(10));
    if (!bleReplyReady) bleReqError = bleClient && bleClient->isConnected() ? "no reply in 6 s" : "the connection went";
    bleReqPending = false; bleReqDone = true;
}
static bool bleServeNow(const std::string &method, const std::string &path, const std::string &body, const std::string &type, ldrc::BleReply &out, std::string &err) {
    if (!bleReqChr || !bleClient || !bleClient->isConnected()) { err = "not joined"; return false; }
    if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(100)) != pdTRUE) { err = "busy"; return false; }
    bleReq.method = method; bleReq.path = path; bleReq.body = body; bleReq.type = type; bleReq.id = bleNextId++; bleReqPending = true;
    bleBridge.reset(); bleReplyReady = false;
    const std::vector<std::string> frames = ldrc::BleBridge::frames(method, path, body, bleReq.id, std::min(ldrc::BLE_WRITE_CHUNK, bleMtu > 23 ? bleMtu - 3 : 20), type);
    xSemaphoreGive(bleMutex);
    for (auto &f : frames) if (!bleReqChr->writeValue((const uint8_t *) f.data(), f.size(), true)) { bleReqPending = false; err = "the write failed"; return false; }
    const uint32_t t0 = millis();
    while (!bleReplyReady && millis() - t0 < 6000 && bleClient && bleClient->isConnected()) vTaskDelay(pdMS_TO_TICKS(10));
    bleReqPending = false;
    if (!bleReplyReady) { err = bleClient && bleClient->isConnected() ? "no reply in 6 s" : "the connection went"; return false; }
    out = bleLast; return true;
}
static void bleMailPost(const std::string &s) { if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(100)) == pdTRUE) { bleMail.push_back(s); xSemaphoreGive(bleMutex); } }
// The block the receiver has, told to the main board as telemetry items - only when they changed
static void bleTellItems(const std::string &json) {
    const std::string tel = ldrc::bleItemsWord(json);          // "ldrctel 25:AABBCCDD 26:..."
    if (tel.empty() || tel == bleTelLast) return;
    bleTelLast = tel; bleMailPost(tel);
}
static void bleTxServe() {                                     // in the task: the next parameter packet, and the block being read
    std::string words;
    if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(100)) == pdTRUE) { if (!bleTxQueue.empty()) { words = bleTxQueue.front(); bleTxQueue.erase(bleTxQueue.begin()); } xSemaphoreGive(bleMutex); }
    if (!words.empty()) {
        ldrc::BleReply r; std::string err;
        // 1.11.12: as a FORM ("w=9,321,...", the receiver's handler reads "w" when there is no raw body): the receiver's
        // Bluetooth bridge hands a POST's body to its handlers only as form fields, never as the raw "plain" the WiFi
        // server gives - so every parameter sent as text/plain was refused (400), and until 1.11.9 that quietly put the
        // main board back on the radio link ("By Bluetooth", yet the values came by radio); from 1.11.9 the values were
        // simply never read ("all the values it reads are zero", Malcolm, 7 Oct).
        if (bleServeNow("POST", "/api/txparams", "w=" + words, "application/x-www-form-urlencoded", r, err) && r.code == 200) {
            int id = atoi(words.c_str()); const char *c = strchr(words.c_str(), ','); const int w1 = c ? atoi(c + 1) : 0; const char *c2 = c ? strchr(c + 1, ',') : nullptr; const int w2 = c2 ? atoi(c2 + 1) : 0;
            if (w1 == 321 && (id == 9 || id == 12 || id == 15 || id == 18 || id == 27 || id == 28)) { blePollUntil = millis() + (uint32_t) std::min(std::max(w2, 1000), 15000); bleTelLast.clear(); }   // "send me the block": watch it
            bleTellItems(r.body);
        } else if (err.empty()) {                              // 1.11.9: the receiver answered, but not 200 (one bad packet): noted for /status, the pipe stays
            bleWhy = "the receiver refused a parameter (" + std::to_string(r.code) + "): " + words.substr(0, 40);
            blog("ble", bleWhy); bleNote(bleWhy);
        } else { bleWhy = "the receiver refused a parameter (" + err + ")"; bleMailPost("ldrcpipe=3"); blePollUntil = 0; }   // no answer at all, or the link went: the main board goes back to the radio link
        return;
    }
    if (blePollUntil && (int32_t) (millis() - blePollUntil) < 0 && millis() - blePollLast > 200) {
        blePollLast = millis(); ldrc::BleReply r; std::string err;
        if (bleServeNow("GET", "/api/txparams/ack", "", "", r, err) && r.code == 200) bleTellItems(r.body);
    } else if (blePollUntil && (int32_t) (millis() - blePollUntil) >= 0) blePollUntil = 0;
}
static void bleTask(void *) {
    for (;;) {
        if (bleOrder == 2) {                                   // off: down with the stack (a failed join keeps its reason until then)
            bleOrder = 0; bleState = BLE_STOPPING; bleNote("stopping"); bleLeave(); NimBLEDevice::deinit(true); bleClient = nullptr; bleState = BLE_OFF; bleWifiKick = true; bleNote("off");   // (deinit deletes every client)
        } else if (bleOrder == 1) {
            bleOrder = 0;
            if (bleState == BLE_OFF || bleState == BLE_FAILED) {
                bleState = BLE_STARTING; bleNote("starting");
                if (!NimBLEDevice::isInitialized()) { NimBLEDevice::init("ldrc-screen"); NimBLEDevice::setMTU(247); }
                if (!bleJoin()) { bleLeave(); bleState = BLE_FAILED; }
            }
        } else if (bleReqPending && !bleReqDone && bleState == BLE_READY) bleServe();
        else if (bleReqPending && !bleReqDone) { bleReqError = "not joined"; bleReqPending = false; bleReqDone = true; }
        else if (bleState == BLE_READY) bleTxServe();
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
static void bleStartTask() { if (!bleMutex) bleMutex = xSemaphoreCreateMutex(); if (!bleTaskHandle) xTaskCreatePinnedToCore(bleTask, "ldrcble", 12288, nullptr, 1, &bleTaskHandle, 0); /* 1.11.7: 8 kB was never measured; the screen restarted once mid-session, cause unknown */ }
// loop(): the radio rule, and the bench
static bool bleAsk(const std::string &method, const std::string &path, const std::string &body, const std::string &type) {   // false: busy or not joined
    if (bleReqPending || bleState != BLE_READY) return false;
    bleReq.method = method; bleReq.path = path; bleReq.body = body; bleReq.type = type; bleReq.id = bleNextId++;
    bleReqDone = false; bleReqError.clear(); bleReqStartedAt = millis(); bleReqPending = true;
    return true;
}
// 1.11.10 (Malcolm: "It's very easy to try to view the PIDs while it says Bluetooth connecting ... a much more obvious
// banner that says please wait, connecting Bluetooth"): while the screen is joining the receiver, a box over the
// Rotorflight menu's four buttons says so, in the biggest letters we have; it goes when the join ends. The main board
// refuses those pages meanwhile (B47), with the same words.
static bool pipeNoticeUp = false; static int pipeNoticePage = -1;
static const int PN_X = 420, PN_Y = 78, PN_W = 356, PN_H = 226;
static void pipeNoticeDraw() {
    gfx->fillRect(PN_X, PN_Y, PN_W, PN_H, OUR_PANEL);
    gfx->drawRect(PN_X, PN_Y, PN_W, PN_H, OUR_INK); gfx->drawRect(PN_X + 1, PN_Y + 1, PN_W - 2, PN_H - 2, OUR_INK);
    gfx->startWrite();
    const std::string a = "Connecting", b = "Bluetooth", c = "please wait a moment";
    int y = PN_Y + 18;
    drawGlyphs(PN_X + (PN_W - textWidth(1, a)) / 2, y, 1, OUR_INK, a); y += fontHeight(1) + 2;
    drawGlyphs(PN_X + (PN_W - textWidth(1, b)) / 2, y, 1, OUR_INK, b); y += fontHeight(1) + 14;
    drawGlyphs(PN_X + (PN_W - textWidth(2, c)) / 2, y, 2, OUR_INK, c);
    gfx->endWrite();
    memoTouched(PN_X, PN_Y, PN_W, PN_H); dirty(PN_X, PN_Y, PN_W, PN_H); damage(PN_X, PN_Y, PN_W, PN_H);
}
static void pipeNoticeClear() {
    restoreRect(PN_X, PN_Y, PN_W, PN_H);
    for (auto &c : page.comps) if (c.x < PN_X + PN_W && c.x + c.w > PN_X && c.y < PN_Y + PN_H && c.y + c.h > PN_Y) drawComp(c);
    memoTouched(PN_X, PN_Y, PN_W, PN_H); dirty(PN_X, PN_Y, PN_W, PN_H);
}
static void pipeNoticePoll() {
    const bool joining = bleState == BLE_STARTING || bleState == BLE_SCANNING || bleState == BLE_CONNECTING;
    const bool want = joining && page.id == 8 && !topOn && !loadingPage;
    if (pipeNoticeUp && page.id != pipeNoticePage) pipeNoticeUp = false;   // the page went: it was drawn afresh without us
    if (want && !pipeNoticeUp) { pipeNoticeDraw(); pipeNoticeUp = true; pipeNoticePage = page.id; }
    else if (!want && pipeNoticeUp) { pipeNoticeUp = false; pipeNoticeClear(); }
}
static void blePoll() {
    static bool wasArmed = false;
    pipeNoticePoll();
    // 1.11.11 (Malcolm, 7 Oct: "I could not update, or rather could not join the Wi-Fi usefully until I had switched the
    // transmitter off and on again. This happened yesterday"): both times after a Bluetooth session. The one radio serves
    // both; when the Bluetooth stack goes down the WiFi link may be left looking joined and carrying nothing. So the WiFi
    // joins afresh after every Bluetooth session: a few seconds, on the ground.
    if (bleWifiKick) { bleWifiKick = false; if (radiosLive) { blog("ble", "stack down: the WiFi joins again"); bleNote("the WiFi joins again"); WiFi.disconnect(); wifiAutoStep = 0; } }
    if (tx.armed && !wasArmed && bleState != BLE_OFF) bleOrder = 2;   // the model could be flying: Bluetooth down, as the WiFi goes
    wasArmed = tx.armed;
    static int logged = -1;
    if ((int) bleState != logged) { logged = bleState; blog("ble", std::string(bleStateName(bleState)) + (bleState == BLE_FAILED ? ": " + bleWhy : bleState == BLE_READY ? ": " + bleJoined + ", MTU " + std::to_string(bleMtu) : "")); }
    const int st = bleState == BLE_READY ? 2 : bleState == BLE_FAILED ? 3 : bleState == BLE_OFF ? 0 : 1;
    if (st != blePipeTold && !teensyLink.running()) { blePipeTold = st; flushOut(); const std::string t = "ldrcpipe=" + std::to_string(st); Serial.write((const uint8_t *) t.data(), t.size()); }
    if (!bleMail.empty() && bleMutex && xSemaphoreTake(bleMutex, pdMS_TO_TICKS(5)) == pdTRUE) {   // the task's words for the main board, one a pass
        std::string m = bleMail.front(); bleMail.erase(bleMail.begin()); xSemaphoreGive(bleMutex);
        if (!teensyLink.running()) { flushOut(); Serial.write((const uint8_t *) m.data(), m.size()); blog("ble", "to the main board: " + m.substr(0, 60)); }
    }
}
// From the main board: "ldrcpipe on AABBCCDDEEFF" (the receiver's board id, as it learned at binding; "on" alone = the
// nearest), "ldrcpipe off", and "ldrctx 12,321,5000,0,0,0,0,0,0,0,0,0" (a parameter packet, as words)
static void blePipeCommand(const std::string &a) {
    blog("ble", "from the main board: pipe " + a); bleNote("main board: pipe " + a);
    if (a.rfind("on", 0) == 0) {
        if (bleState == BLE_STARTING || bleState == BLE_SCANNING || bleState == BLE_CONNECTING) { bleNote("joining already: left to it"); return; }   // 1.11.15: a second "on" mid-join (the menu opened while Model setup's join runs) changes nothing
        bleWantMac = bleUpper(a.size() > 3 ? a.substr(3) : ""); bleTarget.clear(); bleTelLast.clear();
        if (tx.armed) return;
        if (bleState == BLE_READY) { blePipeTold = -1; return; }   // 1.11.9: already joined (the menu was re-entered from one of its pages): say so again, or the main board waits on "joining"
        bleStartTask(); bleOrder = 1;
    }
    else if (a == "off") { bleOrder = 2; blePollUntil = 0; if (bleMutex && xSemaphoreTake(bleMutex, pdMS_TO_TICKS(5)) == pdTRUE) { bleTxQueue.clear(); xSemaphoreGive(bleMutex); } }
}
static void bleTxCommand(const std::string &words) {
    blog("ble", "from the main board: " + words);
    if (bleMutex && xSemaphoreTake(bleMutex, pdMS_TO_TICKS(5)) == pdTRUE) { if (bleTxQueue.size() < 16) bleTxQueue.push_back(words); xSemaphoreGive(bleMutex); }
}
static std::string bleStatusJson() {
    std::string out = std::string("{\"state\":\"") + bleStateName(bleState) + "\",\"why\":\"" + bleWhy + "\",\"wanted\":\"" + bleWantMac + "\",\"joined\":\"" + bleJoined + "\",\"mtu\":" + std::to_string(bleMtu) + ",\"told\":" + std::to_string(blePipeTold) + ",\"seen\":[";
    if (bleMutex && xSemaphoreTake(bleMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
        for (size_t i = 0; i < bleSeen.size(); ++i) out += (i ? "," : "") + std::string("{\"name\":\"") + bleSeen[i].name + "\",\"addr\":\"" + bleSeen[i].addr + "\",\"rssi\":" + std::to_string(bleSeen[i].rssi) + "}";
        xSemaphoreGive(bleMutex);
    }
    out += "],\"pending\":" + std::string(bleReqPending ? "true" : "false") + ",\"queued\":" + std::to_string(bleTxQueue.size()) + ",\"heap\":" + std::to_string(ESP.getFreeHeap()) + ",\"log\":[";
    if (bleMutex && xSemaphoreTake(bleMutex, pdMS_TO_TICKS(50)) == pdTRUE) {           // (1.11.13) the last 24 happenings, oldest first
        bool first = true;
        for (int i = bleLogN > 24 ? bleLogN - 24 : 0; i < bleLogN; ++i) { std::string l = bleLog[i % 24]; for (auto &c : l) if (c == '"' || c == '\\') c = '\''; out += (first ? "\"" : ",\"") + l + "\""; first = false; }
        xSemaphoreGive(bleMutex);
    }
    out += "]}";
    return out;
}
static void bleWeb() {
    doorOn("/ble/on", HTTP_POST, []() { if (tx.armed) { web.send(409, "text/plain", "the model could be flying"); return; } bleTarget = web.arg("name").c_str(); bleStartTask(); bleOrder = 1; web.send(200, "text/plain", "joining"); });
    doorOn("/ble/off", HTTP_POST, []() { bleOrder = 2; web.send(200, "text/plain", "leaving"); });
    doorOn("/ble/status", HTTP_GET, []() { web.send(200, "application/json", bleStatusJson().c_str()); });
    doorOn("/ble/req", HTTP_POST, []() {               // /ble/req?method=GET&path=/api/state.json [body in the POST] : starts it; /ble/reply fetches the answer
        const std::string method = web.arg("method").length() ? web.arg("method").c_str() : "GET", path = web.arg("path").c_str(), body = web.arg("plain").c_str();
        if (path.empty()) { web.send(400, "text/plain", "path?"); return; }
        if (!bleAsk(method, path, body, web.arg("type").c_str())) { web.send(409, "text/plain", bleState == BLE_READY ? "busy" : "not joined"); return; }
        web.send(200, "text/plain", std::to_string(bleReq.id).c_str());
    });
    doorOn("/ble/reply", HTTP_GET, []() {
        if (bleReqPending || !bleReqDone) { web.send(202, "text/plain", "waiting"); return; }
        if (!bleReqError.empty()) { web.send(502, "text/plain", bleReqError.c_str()); return; }
        std::string out = "R" + std::to_string(bleLast.code) + "|" + bleLast.type + "|" + std::to_string(bleLast.body.size()) + "|" + bleLast.location + "\n" + bleLast.body;
        web.send(200, "text/plain", out.c_str());
    });
}
