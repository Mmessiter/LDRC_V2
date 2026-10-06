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

static bool bleJoin() {                                        // in the task: scan, pick, connect, subscribe
    bleState = BLE_SCANNING;
    NimBLEScan *scan = NimBLEDevice::getScan(); scan->setActiveScan(true); scan->setInterval(45); scan->setWindow(30); scan->setMaxResults(20);
    NimBLEScanResults res = scan->getResults(2500, false);
    std::vector<BleSeen> seen; const NimBLEAdvertisedDevice *best = nullptr;
    for (int i = 0; i < res.getCount(); ++i) {
        const NimBLEAdvertisedDevice *d = res.getDevice(i);
        if (!d->isAdvertisingService(NimBLEUUID(ldrc::BLE_SVC_UUID))) continue;
        BleSeen s; s.name = d->getName(); s.addr = d->getAddress().toString(); s.rssi = d->getRSSI(); seen.push_back(s);
        const bool wanted = bleTarget.empty() ? (!best || d->getRSSI() > best->getRSSI()) : (s.name == bleTarget);
        if (wanted) best = d;
    }
    if (xSemaphoreTake(bleMutex, pdMS_TO_TICKS(100)) == pdTRUE) { bleSeen = seen; xSemaphoreGive(bleMutex); }
    if (!best) { bleWhy = seen.empty() ? "no receiver in reach" : "the receiver named is not in reach"; scan->clearResults(); return false; }
    bleState = BLE_CONNECTING;
    bleClient = NimBLEDevice::createClient(); bleClient->setClientCallbacks(&bleClientCb, false); bleClient->setConnectTimeout(5000);
    const std::string name = best->getName();
    if (!bleClient->connect(best, true, false, true)) { bleWhy = "could not connect to " + name; NimBLEDevice::deleteClient(bleClient); bleClient = nullptr; scan->clearResults(); return false; }
    scan->clearResults();
    NimBLERemoteService *svc = bleClient->getService(NimBLEUUID(ldrc::BLE_SVC_UUID));
    bleReqChr = svc ? svc->getCharacteristic(NimBLEUUID(ldrc::BLE_REQ_UUID)) : nullptr; bleRespChr = svc ? svc->getCharacteristic(NimBLEUUID(ldrc::BLE_RESP_UUID)) : nullptr;
    if (!bleReqChr || !bleRespChr || !bleRespChr->canNotify() || !bleRespChr->subscribe(true, bleNotify, true)) { bleWhy = name + " has no bridge"; bleClient->disconnect(); return false; }
    bleJoined = name; bleMtu = bleClient->getMTU(); bleState = BLE_READY;
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
static void bleTask(void *) {
    for (;;) {
        if (bleOrder == 2 || (bleState == BLE_FAILED && bleOrder != 1)) {   // off (or failed and not asked again): down with the stack
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
}
static void bleWeb() {
    doorOn("/ble/on", HTTP_POST, []() { if (tx.armed) { web.send(409, "text/plain", "the model could be flying"); return; } bleTarget = web.arg("name").c_str(); bleStartTask(); bleOrder = 1; web.send(200, "text/plain", "joining"); });
    doorOn("/ble/off", HTTP_POST, []() { bleOrder = 2; web.send(200, "text/plain", "leaving"); });
    doorOn("/ble/status", HTTP_GET, []() {
        std::string out = std::string("{\"state\":\"") + bleStateName(bleState) + "\",\"why\":\"" + bleWhy + "\",\"joined\":\"" + bleJoined + "\",\"mtu\":" + std::to_string(bleMtu) + ",\"seen\":[";
        if (bleMutex && xSemaphoreTake(bleMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
            for (size_t i = 0; i < bleSeen.size(); ++i) out += (i ? "," : "") + std::string("{\"name\":\"") + bleSeen[i].name + "\",\"addr\":\"" + bleSeen[i].addr + "\",\"rssi\":" + std::to_string(bleSeen[i].rssi) + "}";
            xSemaphoreGive(bleMutex);
        }
        out += "],\"pending\":" + std::string(bleReqPending ? "true" : "false") + ",\"heap\":" + std::to_string(ESP.getFreeHeap()) + "}";
        web.send(200, "application/json", out.c_str());
    });
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
