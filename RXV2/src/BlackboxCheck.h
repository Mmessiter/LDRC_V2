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
constexpr uint8_t MSP_STATUS_FN         = 101;  // flight-mode flags bit 0 = armed: mspDeliverResponse keeps fcInfo.armed fresh
constexpr uint32_t STATUS_EVERY_MS      = 1000; // while the heartbeat probe stands down, the check asks for itself
inline uint32_t lastStatusMs = 0;
inline uint32_t notBeforeMs = 0;                // no request before this (MSP 70 busy back-off)
inline bool     armedKnown = false;             // the FC has answered MSP 101 since this check started
inline uint8_t* rxBuf = nullptr;                // PSRAM: a whole 4 kB dataflash reply (too big for mspAsyncBuf)
inline uint16_t rxLen = 0;
inline volatile bool rxReady = false;
constexpr uint16_t RX_CAP = 4200;

enum State : uint8_t { IDLE = 0, SUMMARY, STREAM, DONE, FAILED };
inline State    state = IDLE;
inline char     reason[120] = "";
inline uint32_t addr = 0, endAddr = 0, startAddr = 0, totalBytes = 0, usedBytes = 0;
inline uint32_t startMs = 0, endMs = 0, reqSentMs = 0;
inline uint32_t runStartMs = 0;                 // start of the whole run: the auto-widen re-stamps startMs, this one never moves
inline uint8_t  retries = 0, reqFn = 0;
inline bool     reqOut = false;
inline uint32_t chunks = 0, bytesDone = 0;
inline int      wantLog = 0;
inline BbDec::Decoder* dec = nullptr;
inline BbAn::Analyser* an  = nullptr;
inline char*    jsonBuf = nullptr;
constexpr size_t   JSON_CAP = 24 * 1024;
constexpr uint16_t CHUNK = 4096;                // the most the FC will give in one reply (MSP_PORT_OUTBUF_SIZE); 512 B chunks ran at 25 kB/s on the bench
constexpr uint32_t REQ_TIMEOUT_MS = 1500;
// A check must never own the flight controller for longer than this. Reading
// the whole 256 MB of a full black box at 65 kB/s would take over an hour;
// nothing legitimate runs past 20 minutes, so anything that does is wedged.
constexpr uint32_t MAX_RUN_MS = 20u * 60u * 1000u;
// The flight controller answers ~2 kB per request and ~30 requests a second
// (measured on the Goblin, 62 kB/s), so reading a FULL 256 MB black box would
// take over an hour. The check wants the newest flight, so it starts this far
// back from the write head and lets the decoder find the first header there.
// If that window holds no log at all it widens itself, up to WINDOW_MAX.
constexpr uint32_t WINDOW_DEFAULT = 12u * 1024 * 1024;
constexpr uint32_t WINDOW_MAX     = 96u * 1024 * 1024;
inline uint32_t windowBytes = WINDOW_DEFAULT;
inline bool     autoWindow  = false;   // no explicit address asked for: we choose, and may widen

inline bool running() { return state == SUMMARY || state == STREAM; }
inline uint32_t rd32(const uint8_t* p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
inline void* psAlloc(size_t n) { return heap_caps_malloc(n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }   // PSRAM only: ~70 kB of internal heap is not for this
inline void freeWork() { if (dec) { dec->~Decoder(); heap_caps_free(dec); dec = nullptr; } if (rxBuf) { heap_caps_free(rxBuf); rxBuf = nullptr; } }
inline void freeAll()  { freeWork(); if (an) { an->~Analyser(); heap_caps_free(an); an = nullptr; } if (jsonBuf) { heap_caps_free(jsonBuf); jsonBuf = nullptr; } }

// The parser hands a dataflash reply straight to us: 4 kB will not fit
// mspAsyncBuf. Same task as tick(), so a plain flag is enough.
inline bool bigReply(uint8_t func, const uint8_t* p, uint16_t n) {
    if (func != MSP_DATAFLASH_READ || !rxBuf || !bbCheckActive) return false;
    if (n > RX_CAP) n = RX_CAP;
    memcpy(rxBuf, p, n); rxLen = n; rxReady = true;
    return true;                                 // taken: the 640-byte wait/async buffers never see it
}

inline void sendRead();          // defined below (done() may start another pass)
inline void restartWork();
inline void stopLink() { reqOut = false; mspAsyncFunc = 0xFF; mspAsyncReady = false; rxReady = false; mspBigReplyHook = nullptr; bbCheckActive = false; endMs = millis(); }
inline void fail(const char* why) {
    snprintf(reason, sizeof reason, "%s", why);
    state = FAILED; stopLink(); freeWork();
    char m[EventLog::MSG_LEN]; snprintf(m, sizeof m, "Vibration check stopped: %.55s", why); events.add(m);
}
inline void done() {
    if (dec && an) dec->finish(*an);
    // Nothing found in our window and there is more behind it: widen and go again.
    if (autoWindow && an && an->nLogs == 0 && startAddr > 0 && windowBytes < WINDOW_MAX) {
        windowBytes *= 4; if (windowBytes > WINDOW_MAX) windowBytes = WINDOW_MAX;
        char m[EventLog::MSG_LEN]; snprintf(m, sizeof m, "Vibration check: no log in the last %lu MB - looking %lu MB back", (unsigned long)((usedBytes - startAddr) / 1048576), (unsigned long)(windowBytes / 1048576));
        events.add(m);
        restartWork();
        startAddr = addr = (usedBytes > windowBytes) ? usedBytes - windowBytes : 0;
        state = STREAM; startMs = millis(); sendRead();
        return;
    }
    state = DONE; stopLink();
    char m[EventLog::MSG_LEN];
    snprintf(m, sizeof m, "Vibration check: %lu kB in %lu s, %d log(s), %lu frames", (unsigned long)(bytesDone / 1024), (unsigned long)((endMs - startMs) / 1000), an ? an->nLogs : 0, (unsigned long)(dec ? dec->stats.iFrames + dec->stats.pFrames : 0));
    events.add(m);
    freeWork();
}

inline void sendReq(uint8_t fn, const uint8_t* d, uint8_t n) {
    mspAsyncFunc = fn; mspAsyncReady = false; reqFn = fn;
    bbCheckOwnSend = true; mspSendRequest(fn, d, n); bbCheckOwnSend = false;
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
    if (txParamBusy || mspWaitFunction != 0xFF || mspBridgeActive || mspProbeOutstanding()) return "the receiver is busy talking to the flight controller - try again in a moment";
    // The check owns the link for minutes, and bankPutBackTick stands down while
    // it runs. If a phone session has left the flight controller on a bank that
    // is not the switch's, that put-back MUST happen first: were the transmitter
    // to come on during the check, the put-back is abandoned and the model would
    // fly on the phone's bank. Wait for it - it needs 5 quiet seconds.
    if (bankHeld()) return "the receiver is putting the flight controller's PID banks back where your switch has them - try again in a few seconds";
    // Mid-sequence, too: a restore or a page save is many requests with gaps
    // between them, and none of the single-request tests above sees the gap.
    if (banks.lastClientMs && (uint32_t)(millis() - banks.lastClientMs) < BANK_IDLE_MS) return "a page is still talking to the flight controller - try again in a few seconds";
    return nullptr;
}

inline void restartWork() {                     // fresh decoder + analyser for another pass
    if (dec) { dec->~Decoder(); new (dec) BbDec::Decoder(); }
    if (an)  { an->~Analyser();  new (an) BbAn::Analyser(); an->wantLog = wantLog; }
    bytesDone = 0; chunks = 0; retries = 0; rxReady = false; notBeforeMs = 0;
}

inline const char* start(uint32_t fromAddr, uint32_t maxLen, int logIdx) {
    const char* why = refuse(); if (why) return why;
    freeAll();
    dec = (BbDec::Decoder*)psAlloc(sizeof(BbDec::Decoder));
    an  = (BbAn::Analyser*)psAlloc(sizeof(BbAn::Analyser));
    jsonBuf = (char*)psAlloc(JSON_CAP);
    rxBuf   = (uint8_t*)psAlloc(RX_CAP);
    if (!dec || !an || !jsonBuf || !rxBuf) { freeAll(); return "not enough memory for the check"; }
    new (dec) BbDec::Decoder(); new (an) BbAn::Analyser();
    an->wantLog = logIdx; wantLog = logIdx;
    startAddr = addr = fromAddr; endAddr = maxLen ? fromAddr + maxLen : 0; usedBytes = totalBytes = 0;
    autoWindow = (fromAddr == 0 && maxLen == 0);       // nothing asked for: the newest flight, from our own window
    windowBytes = WINDOW_DEFAULT;
    bytesDone = 0; chunks = 0; retries = 0; reason[0] = 0; startMs = runStartMs = millis(); endMs = 0; notBeforeMs = 0;
    bbCheckActive = true; state = SUMMARY; armedKnown = false; rxReady = false;
    mspBigReplyHook = bigReply;                  // dataflash replies come straight to rxBuf
    // The FC's own word before a single byte is read. fcInfo.armed is shared
    // state (every page's armed refusal reads it) so it is never forced here:
    // the check simply does not look at it until MSP 101 has answered.
    sendReq(MSP_STATUS_FN, nullptr, 0); lastStatusMs = millis();
    events.add("Vibration check: reading the black box over USB");
    return nullptr;
}
inline void cancel() { if (running()) fail("cancelled"); }

inline void handleSummary(const uint8_t* p, uint16_t n) {
    if (n < 13) { fail("the flight controller gave no memory summary"); return; }
    const uint8_t flags = p[0]; totalBytes = rd32(p + 5); usedBytes = rd32(p + 9);
    if (!(flags & 2)) { fail("this flight controller has no memory chip for the black box"); return; }   // MSP_FLASHFS_FLAG_SUPPORTED = 2
    if (!(flags & 1)) {                                       // MSP_FLASHFS_FLAG_READY = 1: an erase still finishing after landing takes a few seconds
        if ((uint32_t)(millis() - startMs) < 6000) { notBeforeMs = millis() + 500; return; }   // ask again shortly (tick re-sends 70)
        fail("the black-box memory is busy (erasing?) - try again in a minute"); return;
    }
    if (usedBytes == 0) { fail("the black box is empty: nothing has been recorded"); return; }
    if (endAddr == 0 || endAddr > usedBytes) endAddr = usedBytes;
    if (autoWindow) {                                  // the newest flight, not the whole memory
        startAddr = addr = (usedBytes > windowBytes) ? usedBytes - windowBytes : 0;
        endAddr = usedBytes;
    }
    if (addr >= endAddr) { fail("nothing recorded beyond that address"); return; }
    state = STREAM; sendRead();
}
inline void handleRead(const uint8_t* p, uint16_t n) {
    if (n < 7) { fail("short read reply"); return; }
    const uint32_t a = rd32(p); const uint16_t got = (uint16_t)(p[4] | (p[5] << 8)); const uint8_t comp = p[6];
    if (a != addr) {                                          // a late reply to an earlier (re-sent) read: ignore it, keep waiting for ours
        if (++retries > 6) { fail("the flight controller keeps answering the wrong address"); return; }
        mspAsyncFunc = MSP_DATAFLASH_READ; mspAsyncReady = false; rxReady = false; reqOut = true;   // re-arm without sending: one request outstanding
        return;
    }
    if (comp != 0) { fail("compressed reply - not supported"); return; }
    if (got == 0 || n < 7 + got) { done(); return; }          // end of the volume
    dec->feed(p + 7, got, *an);
    bytesDone += got; addr += got; chunks++; retries = 0;
    if (an->selectedDone || addr >= endAddr) { done(); return; }
    sendRead();
}

// loop(): one reply handled per pass, one request outstanding at most.
inline void tick() {
    if (!running()) {
        // Safety net: bbCheckActive gates every other MSP sender in the
        // firmware, so it must never outlive the check that set it. If the
        // state machine ever stops without clearing it, clear it here.
        if (bbCheckActive) { bbCheckActive = false; bbCheckOwnSend = false; mspBigReplyHook = nullptr; events.add("Vibration check: link handed back (watchdog)"); }
        return;
    }
    if ((uint32_t)(millis() - runStartMs) > MAX_RUN_MS) { fail("the check took too long - the link is back with the flight controller"); return; }
    if (!UsbHostMsp::active()) { fail("the USB cable was unplugged"); return; }
    if (UsbHostMsp::cliMode)   { fail("the command line was opened"); return; }
    if (armedKnown && fcInfo.armed) { fail("the flight controller was armed"); return; }   // only after MSP 101 has answered us (0.9.663)
    if (!dongleEnabled && rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000) { fail("the transmitter came on"); return; }
    if (!reqOut) {
        if (notBeforeMs && (int32_t)(notBeforeMs - millis()) > 0) return;
        notBeforeMs = 0;
        // Between chunks, ask the FC whether it is armed (the heartbeat probe
        // is gated off while we own the link, so nobody else would notice).
        if ((uint32_t)(millis() - lastStatusMs) >= STATUS_EVERY_MS) { lastStatusMs = millis(); sendReq(MSP_STATUS_FN, nullptr, 0); return; }
        if (state == SUMMARY) sendReq(MSP_DATAFLASH_SUMMARY, nullptr, 0); else sendRead();
        return;
    }
    if (rxReady && reqFn == MSP_DATAFLASH_READ) {     // a 4 kB dataflash reply, straight from the parser
        rxReady = false; reqOut = false; mspAsyncFunc = 0xFF; mspAsyncReady = false;
        handleRead(rxBuf, rxLen);
        return;
    }
    if (mspAsyncReady && mspAsyncFunc == reqFn) {
        static uint8_t copy[640];
        uint16_t n = mspAsyncLen; if (n > sizeof copy) n = sizeof copy;
        memcpy(copy, mspAsyncBuf, n);            // our own copy: mspAsyncBuf is shared
        reqOut = false; mspAsyncReady = false; mspAsyncFunc = 0xFF;
        if (reqFn == MSP_STATUS_FN) {            // mspDeliverResponse has already parsed it into fcInfo.armed
            if (n < 10) { fail("the flight controller gave no status"); return; }
            armedKnown = true;
            if (fcInfo.armed) { fail("the flight controller is armed"); return; }
            if (state == SUMMARY) sendReq(MSP_DATAFLASH_SUMMARY, nullptr, 0); else sendRead();
            return;
        }
        if (reqFn == MSP_DATAFLASH_SUMMARY) handleSummary(copy, n); else handleRead(copy, n);
        return;
    }
    if ((uint32_t)(millis() - reqSentMs) > REQ_TIMEOUT_MS) {
        if (++retries > 3) { fail("the flight controller stopped answering"); return; }
        reqOut = false; mspAsyncFunc = 0xFF; rxReady = false;      // the next pass re-sends
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
    const uint32_t rateBs = (ms > 500 && bytesDone) ? (uint32_t)((uint64_t)bytesDone * 1000 / ms) : 0;
    s += ",\"bps\":" + String(rateBs);
    s += ",\"eta\":" + String((rateBs && endAddr > addr) ? (uint32_t)((endAddr - addr) / rateBs) : 0);
    s += ",\"window\":" + String(windowBytes);
    s += ",\"logs\":" + String(an ? an->nLogs : 0) + ",\"frames\":" + String(dec ? dec->stats.iFrames + dec->stats.pFrames : 0);
    s += ",\"rate\":" + String(an ? an->rateNow() : 0.0f, 0) + ",\"hs\":" + String(an ? an->hsMedian() : 0.0f, 0) + ",\"flyWin\":" + String(an ? an->flyWinNow() : 0);
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
