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
    void onDisconnect(NimBLEClient *, int reason) override { if (bleState == BLE_READY) { bleState = BLE_FAILED; bleWhy = "the receiver dropped the connection (" + std::to_string(reason) + ")"; } }
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
static bool bleConnectTo(const NimBLEAdvertisedDevice *d, std::string &why) {   // in the task: connect and find the bridge
    bleClient = NimBLEDevice::createClient(); bleClient->setClientCallbacks(&bleClientCb, false); bleClient->setConnectTimeout(5000);
    const std::string name = d->getName();
    if (!bleClient->connect(d, true, false, true)) { why = "could not connect to " + name; NimBLEDevice::deleteClient(bleClient); bleClient = nullptr; return false; }
    NimBLERemoteService *svc = bleClient->getService(NimBLEUUID(ldrc::BLE_SVC_UUID));
    bleReqChr = svc ? svc->getCharacteristic(NimBLEUUID(ldrc::BLE_REQ_UUID)) : nullptr; bleRespChr = svc ? svc->getCharacteristic(NimBLEUUID(ldrc::BLE_RESP_UUID)) : nullptr;
    if (!bleReqChr || !bleRespChr || !bleRespChr->canNotify() || !bleRespChr->subscribe(true, bleNotify, true)) { why = name + " has no bridge"; bleClient->disconnect(); NimBLEDevice::deleteClient(bleClient); bleClient = nullptr; bleReqChr = bleRespChr = nullptr; return false; }
    bleJoined = name; bleMtu = bleClient->getMTU();
    return true;
}
static bool bleJoin() {                                        // in the task: scan, then the candidates strongest first; the identity checked on each one's state page
    bleState = BLE_SCANNING;
    NimBLEScan *scan = NimBLEDevice::getScan(); scan->setActiveScan(true); scan->setInterval(45); scan->setWindow(30); scan->setMaxResults(20);
    NimBLEScanResults res = scan->getResults(2500, false);
    std::vector<BleSeen> seen; std::vector<const NimBLEAdvertisedDevice *> cands;
    for (int i = 0; i < res.getCount(); ++i) {
        const NimBLEAdvertisedDevice *d = res.getDevice(i);
        if (!d->isAdvertisingService(NimBLEUUID(ldrc::BLE_SVC_UUID))) continue;
        BleSeen s; s.name = d->getName(); s.addr = d->getAddress().toString(); s.rssi = d->getRSSI(); seen.push_back(s);
        if (bleTarget.empty() || s.name == bleTarget) cands.push_back(d);
    }
    if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(100)) == pdTRUE) { bleSeen = seen; xSemaphoreGive(bleMutex); }
    std::sort(cands.begin(), cands.end(), [](const NimBLEAdvertisedDevice *a, const NimBLEAdvertisedDevice *b) { return a->getRSSI() > b->getRSSI(); });
    if (cands.empty()) { bleWhy = seen.empty() ? "no receiver in reach" : "the receiver named is not in reach"; scan->clearResults(); return false; }
    bleState = BLE_CONNECTING;
    std::string why; bool ok = false;
    for (size_t i = 0; i < cands.size() && !ok; ++i) {
        if (!bleConnectTo(cands[i], why)) continue;
        if (bleWantMac.empty()) { ok = true; break; }
        ldrc::BleReply r; std::string err;                       // the receiver's identity: its state page says
        if (bleServeNow("GET", "/api/state.json", "", "", r, err) && r.code == 200) {
            const size_t k = r.body.find("\"board_mac\":\"");
            const std::string mac = k == std::string::npos ? "" : bleUpper(r.body.substr(k + 13, 12));
            if (mac == bleWantMac) { ok = true; break; }
            why = "not the model's receiver (" + bleJoined + ")";
        } else why = "no answer from " + bleJoined + (err.empty() ? "" : ": " + err);
        bleLeave();
    }
    scan->clearResults();
    if (!ok) { bleWhy = why; return false; }
    bleState = BLE_READY;
    return true;
}
static void bleLeave() {
    if (bleClient) { if (bleClient->isConnected()) bleClient->disconnect(); NimBLEDevice::deleteClient(bleClient); bleClient = nullptr; }
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
        if (bleServeNow("POST", "/api/txparams", words, "text/plain", r, err) && r.code == 200) {
            int id = atoi(words.c_str()); const char *c = strchr(words.c_str(), ','); const int w1 = c ? atoi(c + 1) : 0; const char *c2 = c ? strchr(c + 1, ',') : nullptr; const int w2 = c2 ? atoi(c2 + 1) : 0;
            if (w1 == 321 && (id == 9 || id == 12 || id == 15 || id == 18 || id == 27 || id == 28)) { blePollUntil = millis() + (uint32_t) std::min(std::max(w2, 1000), 15000); bleTelLast.clear(); }   // "send me the block": watch it
            bleTellItems(r.body);
        } else { bleWhy = "the receiver refused a parameter (" + (err.empty() ? std::to_string(r.code) : err) + ")"; bleMailPost("ldrcpipe=3"); blePollUntil = 0; }
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
            bleOrder = 0; bleState = BLE_STOPPING; bleLeave(); NimBLEDevice::deinit(true); bleState = BLE_OFF;
        } else if (bleOrder == 1) {
            bleOrder = 0;
            if (bleState == BLE_OFF || bleState == BLE_FAILED) {
                bleState = BLE_STARTING;
                if (!NimBLEDevice::isInitialized()) { NimBLEDevice::init("ldrc-screen"); NimBLEDevice::setMTU(247); }
                if (!bleJoin()) { bleLeave(); bleState = BLE_FAILED; }
            }
        } else if (bleReqPending && !bleReqDone && bleState == BLE_READY) bleServe();
        else if (bleReqPending && !bleReqDone) { bleReqError = "not joined"; bleReqPending = false; bleReqDone = true; }
        else if (bleState == BLE_READY) bleTxServe();
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
static void bleStartTask() { if (!bleMutex) bleMutex = xSemaphoreCreateMutex(); if (!bleTaskHandle) xTaskCreatePinnedToCore(bleTask, "ldrcble", 8192, nullptr, 1, &bleTaskHandle, 0); }
// loop(): the radio rule, and the bench
static bool bleAsk(const std::string &method, const std::string &path, const std::string &body, const std::string &type) {   // false: busy or not joined
    if (bleReqPending || bleState != BLE_READY) return false;
    bleReq.method = method; bleReq.path = path; bleReq.body = body; bleReq.type = type; bleReq.id = bleNextId++;
    bleReqDone = false; bleReqError.clear(); bleReqStartedAt = millis(); bleReqPending = true;
    return true;
}
static void blePoll() {
    static bool wasArmed = false;
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
    blog("ble", "from the main board: pipe " + a);
    if (a.rfind("on", 0) == 0) { bleWantMac = bleUpper(a.size() > 3 ? a.substr(3) : ""); bleTarget.clear(); bleTelLast.clear(); if (tx.armed) return; bleStartTask(); bleOrder = 1; }
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
    out += "],\"pending\":" + std::string(bleReqPending ? "true" : "false") + ",\"queued\":" + std::to_string(bleTxQueue.size()) + ",\"heap\":" + std::to_string(ESP.getFreeHeap()) + "}";
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
