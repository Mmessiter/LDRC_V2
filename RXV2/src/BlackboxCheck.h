// BlackboxCheck.h — the Vibration check (0.9.661): stream the flight
// controller's black box over USB through BlackboxDecode.h, from loop(),
// one 512-byte MSP 71 chunk per tick, and serve the spectra as JSON parts
// for rotorflight-filtercheck.html. Nothing is stored: the analyser
// accumulates as the bytes go by, so a 10 MB flight costs ~60 kB of PSRAM.
//
// Rules (Malcolm's 10 ms doctrine and the one-request-at-a-time rule):
//  - USB only (over the CRSF tunnel a 512-byte read would be clipped to the
//    FC's 320-byte link buffer anyway) and never while armed, never with the
//    transmitter on (a receiver), never with the command line open;
//  - exactly one MSP request outstanding; the heartbeat probe, the TX-param
//    machine and /api/msp all stand down while bbCheckActive;
//  - one chunk per loop() pass: ~0.5 ms of decoding, plus ~2 ms of FFTs when a
//    Welch window completes (every 256 samples).
#ifndef _SRC_BLACKBOXCHECK_H
#define _SRC_BLACKBOXCHECK_H

#include <new>
#include <esp_heap_caps.h>
#include "1Defs.h"
#include "MspFc.h"
#include "UsbHostMsp.h"
#include "BlackboxDecode.h"

namespace BbCheck {

constexpr uint8_t MSP_DATAFLASH_SUMMARY = 70;   // u8 flags, u32 sectors, u32 total, u32 used
constexpr uint8_t MSP_DATAFLASH_READ    = 71;   // u32 addr, u16 size, u8 compress → u32 addr, u16 got, u8 comp, data

enum State : uint8_t { IDLE = 0, SUMMARY, STREAM, DONE, FAILED };
inline State    state = IDLE;
inline char     reason[120] = "";
inline uint32_t addr = 0, endAddr = 0, startAddr = 0, totalBytes = 0, usedBytes = 0;
inline uint32_t startMs = 0, endMs = 0, reqSentMs = 0;
inline uint8_t  retries = 0, reqFn = 0;
inline bool     reqOut = false;
inline uint32_t chunks = 0, bytesDone = 0;
inline int      wantLog = 0;
inline BbDec::Decoder* dec = nullptr;
inline BbAn::Analyser* an  = nullptr;
inline char*    jsonBuf = nullptr;
constexpr size_t   JSON_CAP = 24 * 1024;
constexpr uint16_t CHUNK = 512;                 // reply = 7 + 512 = 519 B, inside the 640-byte MSP parser
constexpr uint32_t REQ_TIMEOUT_MS = 1500;

inline bool running() { return state == SUMMARY || state == STREAM; }
inline uint32_t rd32(const uint8_t* p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
inline void* psAlloc(size_t n) { void* p = heap_caps_malloc(n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); if (!p) p = heap_caps_malloc(n, MALLOC_CAP_8BIT); return p; }
inline void freeWork() { if (dec) { dec->~Decoder(); heap_caps_free(dec); dec = nullptr; } }
inline void freeAll()  { freeWork(); if (an) { an->~Analyser(); heap_caps_free(an); an = nullptr; } if (jsonBuf) { heap_caps_free(jsonBuf); jsonBuf = nullptr; } }

inline void stopLink() { reqOut = false; mspAsyncFunc = 0xFF; mspAsyncReady = false; bbCheckActive = false; endMs = millis(); }
inline void fail(const char* why) {
    snprintf(reason, sizeof reason, "%s", why);
    state = FAILED; stopLink(); freeWork();
    char m[EventLog::MSG_LEN]; snprintf(m, sizeof m, "Vibration check stopped: %.55s", why); events.add(m);
}
inline void done() {
    if (dec && an) dec->finish(*an);
    state = DONE; stopLink();
    char m[EventLog::MSG_LEN];
    snprintf(m, sizeof m, "Vibration check: %lu kB in %lu s, %d log(s), %lu frames", (unsigned long)(bytesDone / 1024), (unsigned long)((endMs - startMs) / 1000), an ? an->nLogs : 0, (unsigned long)(dec ? dec->stats.iFrames + dec->stats.pFrames : 0));
    events.add(m);
    freeWork();
}

inline void sendReq(uint8_t fn, const uint8_t* d, uint8_t n) {
    mspAsyncFunc = fn; mspAsyncReady = false; reqFn = fn;
    mspSendRequest(fn, d, n);
    reqOut = true; reqSentMs = millis(); mspLastForegroundMs = millis();
}
inline void sendRead() {
    uint8_t q[7]; uint16_t sz = CHUNK;
    if (endAddr > addr && endAddr - addr < sz) sz = (uint16_t)(endAddr - addr);
    q[0] = (uint8_t)addr; q[1] = (uint8_t)(addr >> 8); q[2] = (uint8_t)(addr >> 16); q[3] = (uint8_t)(addr >> 24);
    q[4] = (uint8_t)sz; q[5] = (uint8_t)(sz >> 8); q[6] = 0;
    sendReq(MSP_DATAFLASH_READ, q, 7);
}

// nullptr = may start; else the reason, for a 409
inline const char* refuse() {
    if (running()) return "a check is already running";
    if (!UsbHostMsp::active()) return "needs the USB cable: connect the flight controller's USB socket to the receiver's (or the dongle's)";
    if (UsbHostMsp::cliMode) return "the command line is open - exit it first";
    if (fcInfo.armed) return "the flight controller is armed - disarm first";
    if (!dongleEnabled && rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 3000) return "switch the transmitter off first: the check needs the flight controller to itself for a minute";
    if (txParamBusy || mspWaitFunction != 0xFF || mspBridgeActive) return "the receiver is busy talking to the flight controller - try again in a moment";
    return nullptr;
}

inline const char* start(uint32_t fromAddr, uint32_t maxLen, int logIdx) {
    const char* why = refuse(); if (why) return why;
    freeAll();
    dec = (BbDec::Decoder*)psAlloc(sizeof(BbDec::Decoder));
    an  = (BbAn::Analyser*)psAlloc(sizeof(BbAn::Analyser));
    jsonBuf = (char*)psAlloc(JSON_CAP);
    if (!dec || !an || !jsonBuf) { freeAll(); return "not enough memory for the check"; }
    new (dec) BbDec::Decoder(); new (an) BbAn::Analyser();
    an->wantLog = logIdx; wantLog = logIdx;
    startAddr = addr = fromAddr; endAddr = maxLen ? fromAddr + maxLen : 0; usedBytes = totalBytes = 0;
    bytesDone = 0; chunks = 0; retries = 0; reason[0] = 0; startMs = millis(); endMs = 0;
    bbCheckActive = true; state = SUMMARY;
    sendReq(MSP_DATAFLASH_SUMMARY, nullptr, 0);
    events.add("Vibration check: reading the black box over USB");
    return nullptr;
}
inline void cancel() { if (running()) fail("cancelled"); }

inline void handleSummary(const uint8_t* p, uint16_t n) {
    if (n < 13) { fail("the flight controller gave no memory summary"); return; }
    const uint8_t flags = p[0]; totalBytes = rd32(p + 5); usedBytes = rd32(p + 9);
    if (!(flags & 1)) { fail("this flight controller has no memory chip for the black box"); return; }
    if (!(flags & 2)) { fail("the black-box memory is busy (erasing?) - try again in a minute"); return; }
    if (usedBytes == 0) { fail("the black box is empty: nothing has been recorded"); return; }
    if (endAddr == 0 || endAddr > usedBytes) endAddr = usedBytes;
    if (addr >= endAddr) { fail("nothing recorded beyond that address"); return; }
    state = STREAM; sendRead();
}
inline void handleRead(const uint8_t* p, uint16_t n) {
    if (n < 7) { fail("short read reply"); return; }
    const uint32_t a = rd32(p); const uint16_t got = (uint16_t)(p[4] | (p[5] << 8)); const uint8_t comp = p[6];
    if (a != addr) { if (++retries > 3) { fail("the flight controller answered the wrong address"); return; } sendRead(); return; }
    if (comp != 0) { fail("compressed reply - not supported"); return; }
    if (got == 0 || n < 7 + got) { done(); return; }          // end of the volume
    dec->feed(p + 7, got, *an);
    bytesDone += got; addr += got; chunks++; retries = 0;
    if (an->selectedDone || addr >= endAddr) { done(); return; }
    sendRead();
}

// loop(): one reply handled per pass, one request outstanding at most.
inline void tick() {
    if (!running()) return;
    if (!UsbHostMsp::active()) { fail("the USB cable was unplugged"); return; }
    if (UsbHostMsp::cliMode)   { fail("the command line was opened"); return; }
    if (fcInfo.armed)          { fail("the flight controller was armed"); return; }
    if (!dongleEnabled && rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000) { fail("the transmitter came on"); return; }
    if (!reqOut) { if (state == SUMMARY) sendReq(MSP_DATAFLASH_SUMMARY, nullptr, 0); else sendRead(); return; }
    if (mspAsyncReady && mspAsyncFunc == reqFn) {
        static uint8_t copy[640];
        uint16_t n = mspAsyncLen; if (n > sizeof copy) n = sizeof copy;
        memcpy(copy, mspAsyncBuf, n);            // our own copy: mspAsyncBuf is shared
        reqOut = false; mspAsyncReady = false; mspAsyncFunc = 0xFF;
        if (reqFn == MSP_DATAFLASH_SUMMARY) handleSummary(copy, n); else handleRead(copy, n);
        return;
    }
    if ((uint32_t)(millis() - reqSentMs) > REQ_TIMEOUT_MS) {
        if (++retries > 3) { fail("the flight controller stopped answering"); return; }
        reqOut = false; mspAsyncFunc = 0xFF;      // the next pass re-sends
    }
}

inline const char* stateName() { switch (state) { case IDLE: return "idle"; case SUMMARY: return "summary"; case STREAM: return "reading"; case DONE: return "done"; default: return "failed"; } }
inline String statusJson() {
    String s; s.reserve(400);
    const uint32_t span = (endAddr > startAddr) ? endAddr - startAddr : 0;
    const uint32_t ms = (running() ? millis() : (endMs ? endMs : millis())) - startMs;
    s += "{\"state\":\""; s += stateName(); s += "\",\"reason\":\""; s += reason; s += "\"";
    s += ",\"addr\":" + String(addr) + ",\"start\":" + String(startAddr) + ",\"end\":" + String(endAddr) + ",\"used\":" + String(usedBytes) + ",\"total\":" + String(totalBytes);
    s += ",\"bytes\":" + String(bytesDone) + ",\"chunks\":" + String(chunks) + ",\"ms\":" + String(state == IDLE ? 0 : ms);
    s += ",\"pct\":" + String(span ? (int)((uint64_t)bytesDone * 100 / span) : 0);
    s += ",\"logs\":" + String(an ? an->nLogs : 0) + ",\"frames\":" + String(dec ? dec->stats.iFrames + dec->stats.pFrames : 0);
    s += ",\"rate\":" + String(an ? an->rate : 0.0f, 0) + ",\"hs\":" + String(an ? an->hsMedian() : 0.0f, 0) + ",\"flyWin\":" + String(an ? an->flyWin : 0);
    s += ",\"resyncs\":" + String(dec ? dec->stats.resyncs : 0) + ",\"usb\":"; s += UsbHostMsp::active() ? "true" : "false";
    s += ",\"result\":"; s += (state == DONE && an) ? "true" : "false";
    s += "}";
    return s;
}

inline void registerRoutes() {
    server.on("/rotorflight-filtercheck", []() { if (!serveLittleFsFile("/rotorflight-filtercheck.html", "text/html")) server.send(503, "text/plain", "page missing - update the web files"); });
    server.on("/api/blackbox/check", HTTP_POST, []() {
        const uint32_t from = server.hasArg("addr") ? (uint32_t)strtoul(server.arg("addr").c_str(), nullptr, 10) : 0;
        const uint32_t len  = server.hasArg("len")  ? (uint32_t)strtoul(server.arg("len").c_str(), nullptr, 10)  : 0;
        const int logIdx    = server.hasArg("log")  ? server.arg("log").toInt() : 0;
        const char* why = start(from, len, logIdx);
        server.sendHeader("Cache-Control", "no-store");
        if (why) server.send(409, "text/plain", why); else server.send(200, "application/json", "{\"ok\":true}");
    });
    server.on("/api/blackbox/cancel", HTTP_POST, []() { cancel(); server.sendHeader("Cache-Control", "no-store"); server.send(200, "application/json", "{\"ok\":true}"); });
    server.on("/api/blackbox/status", HTTP_GET, []() { server.sendHeader("Cache-Control", "no-store"); server.send(200, "application/json", statusJson()); });
    server.on("/api/blackbox/result", HTTP_GET, []() {
        server.sendHeader("Cache-Control", "no-store");
        if (state != DONE || !an || !jsonBuf) { server.send(409, "text/plain", "no result yet"); return; }
        const int part = server.hasArg("part") ? server.arg("part").toInt() : 0;
        const size_t L = an->toJson(part, jsonBuf, JSON_CAP);
        if (!L) { server.send(500, "text/plain", "result part too big"); return; }
        server.send(200, "application/json", String(jsonBuf));
    });
}

} // namespace BbCheck
#endif // _SRC_BLACKBOXCHECK_H
