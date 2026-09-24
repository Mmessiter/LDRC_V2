// LockDownRadioControl — RXV2  ::  MspFc.h
//
// Active FC discovery via MSP-over-CRSF. At boot (and periodically thereafter
// while not detected), sends MSP_FC_VARIANT + MSP_FC_VERSION requests wrapped
// in CRSF type 0x7A frames. Parses CRSF type 0x7B responses to extract MSP
// payloads. Result lands in fcInfo (declared in 1Defs.h) and is surfaced on
// /api/state.json so the home page JS can conditionally show the
// "Rotorflight config" button when version ≥ 2.2 is detected.
//
// MSP-over-CRSF wire format used here (per BetaFlight / ELRS convention):
//
//   sync(C8) length 7A dest(C8) src(EA) status(10) {MSP v1 body} crc8
//
//   - status byte 0x10 = start-of-frame, sequence 0, MSP v1
//   - MSP v1 body for request: size(1) function(1) payload(N) checksum(1)
//   - MSP v1 body for response: same shape, function echoed back
//
// We send everything on Serial1 (which Output.h has already configured as
// CRSF at 420 kbaud 8N1 on D6/D5) and receive responses through the existing
// CRSF parser in Telemetry.h.
//
//*********************************************************************

#ifndef _SRC_MSPFC_H
#define _SRC_MSPFC_H

#include "1Defs.h"
#include "MspSerialCore.h"
#include "UsbHostMsp.h"      // dongle: MSP over USB when a flight controller is on the USB socket (0.9.615)
#include "Output.h"      // crsfCrc8()

//*********************************************************************
//  MSP function codes we care about
//*********************************************************************

constexpr uint8_t MSP_API_VERSION    = 1;     // 3 bytes: protoVer, apiMajor, apiMinor
constexpr uint8_t MSP_FC_VARIANT     = 2;     // 4 ASCII bytes (e.g. "RTFL")
constexpr uint8_t MSP_FC_VERSION     = 3;     // 3 bytes: major, minor, patch

// Rotorflight tuning commands (codes from v1's Nexus.h)
constexpr uint8_t MSP_RC             = 105;   // 0.9.702: N x uint16 channel values in us, as the FC receives them
constexpr uint8_t MSP_RC_TUNING      = 111;
constexpr uint8_t MSP_PID            = 112;
constexpr uint8_t MSP_SET_RC_TUNING  = 204;
constexpr uint8_t MSP_SET_PID        = 202;
constexpr uint8_t MSP_PID_PROFILE    = 94;
constexpr uint8_t MSP_SET_PID_PROFILE = 95;
constexpr uint8_t MSP_SELECT_SETTING = 210;
constexpr uint8_t MSP_GOVERNOR_CONFIG = 142;
constexpr uint8_t MSP_SET_GOVERNOR_CONFIG = 143;
constexpr uint8_t MSP_GOVERNOR_PROFILE = 148;
constexpr uint8_t MSP_SET_GOVERNOR_PROFILE = 149;
constexpr uint8_t MSP_BATTERY_STATE  = 130;   // byte 0 = cell count (the FC KNOWS — no more guessing 11S vs 12S from volts)
constexpr uint8_t MSP_RX_MAP         = 64;    // Rotorflight channel map: byte i = RX channel (0-based) feeding FC function i, functions in A E R C T order → [4] = throttle
constexpr uint8_t MSP_SET_FEATURE_CFG = 37;   // write the 32-bit feature mask
constexpr uint8_t MSP_EEPROM_WRITE   = 250;
constexpr uint8_t MSP_REBOOT         = 68;    // FC restart (governor config write needs it to apply, like V1)
constexpr uint8_t MSP_ESC_PARAMETERS = 217;   // ESC settings blob (Scorpion/Hobbywing forward programming)
constexpr uint8_t MSP_TELEMETRY_CONFIG     = 73;   // RF 4.6: 12-byte header (inverted, halfDuplex, u32, pinSwap, mode, rate u16, ratio u16) + 40 sensor-ID slots
constexpr uint8_t MSP_SET_TELEMETRY_CONFIG = 74;   // same layout; sensors apply at the next FC boot
constexpr uint8_t MSP_ADJUSTMENT_RANGES    = 52;   // 42 x 14 = 588 bytes — NEVER asked for, see below
constexpr uint8_t MSP_RESET_CONF           = 208;  // factory reset — never over the link
constexpr uint8_t MSP_SET_MOTOR            = 214;  // motor test — never from a phone
constexpr uint8_t MSP_STATUS               = 101;  // bytes 23/25 = the PID / rates bank the FC is on (RF 4.6 msp.c, verified 2026-09-05)

//*********************************************************************
//  Rotorflight 4.6 link-buffer bug (0.9.564) — RXV2/ROTORFLIGHT-MSP52-BUG.md
//*********************************************************************
// The FC answers MSP over CRSF out of a 320-byte buffer (msp_shared.c
// responseBuffer[MSP_TLM_OUTBUF_SIZE], = MSP_PORT_OUTBUF_SIZE_MIN) and the
// reply writers (sbufWriteU8...) never look at the end of it. The
// adjustments list, MSP 52, is 588 bytes: the tail spills over whatever
// the linker put after that buffer — the telemetry setup among it, which
// comes back ALL ZERO (rate, ratio, sensors, even halfDuplex — the image a
// defaults reset could never make). Proven on the Goblin 2026-09-04 15:24:
// FC restart → 73 good; read 120, 34, 172 → still good; read 52 → zero,
// every time. That was the "telemetry setup EMPTY" mystery of 09-03/09-04:
// each event followed a read of 52 (Mac-side tests; no page reads it). In
// RAM only — harmless in the air (crsf.c builds the schedule at boot) but
// carried into flash by the next save, after which the FC boots mute.
// So: 52 is never sent (the API refuses it with the reason), and any reply
// bigger than the FC's buffer — a fn nobody thought of — is logged and the
// telemetry setup re-checked and repaired at once.
constexpr uint16_t RF_TLM_OUTBUF_SIZE = 320;
inline bool mspReplyTooBigForFc(uint8_t fn) { return fn == MSP_ADJUSTMENT_RANGES && !UsbHostMsp::active(); }   // over USB the FC's 320-byte link buffer is not in the path (0.9.617)
// Rotorflight SET functions that read their payload from the request: with
// NO payload the FC reads whatever its request buffer held before (no
// bounds check in sbufReadU8) and applies THAT. Never forward such a
// request — a bare "probe" of fn 173 from the Mac was a 1-byte mixer-rule
// write (2026-09-04). Payload-less by design: 68 reboot, 72 erase, 205/206
// calibrations, 250 save.
inline bool mspSetNeedsPayload(uint8_t fn) {
    switch (fn) {
        case 11:  case 13:  case 15:  case 33:  case 35:  case 37:  case 39:  case 41:
        case 43:  case 45:  case 47:  case 49:  case 51:  case 53:  case 55:  case 57:
        case 60:  case 62:  case 65:  case 67:  case 74:  case 76:  case 78:  case 81:
        case 83:  case 85:  case 89:  case 91:  case 93:  case 95:  case 97:  case 99:
        case 124: case 135: case 136: case 143: case 145: case 147: case 149: case 151:
        case 153: case 155: case 159: case 171: case 173: case 176: case 181: case 183:
        case 185: case 186: case 191: case 193: case 195: case 196: case 200: case 201:
        case 202: case 204: case 210: case 211: case 212: case 213: case 214: case 215:
        case 216: case 218: case 219: case 220: case 221: case 222: case 223: case 225:
        case 226: case 227: case 228: case 239: case 244: case 245: case 246: case 248:
        case 249:
            return true;
        default:
            return false;
    }
}

// The FC's telemetry setup as read by MSP 73 — "bad" means Rotorflight will
// send no volts/RPM/attitude no matter how healthy everything else is:
// native mode schedules only the listed sensors, and a zero link rate or
// ratio starves the rate limiter (crsf.c, verified on the 4.6.0 source).
inline bool fcTelemCfgBad() {
    return fcInfo.telemCfgKnown &&
           (fcInfo.telemSensors == 0 || fcInfo.telemRate == 0 || fcInfo.telemRatio == 0);
}

//*********************************************************************
//  Sync-wait state for mspRequestAndWait()
//*********************************************************************

inline volatile uint8_t  mspWaitFunction = 0xFF;     // 0xFF = nothing pending
inline uint8_t           mspWaitRespBuf[640] = {0};   // jumbo-capable (MSP_ADJUSTMENT_RANGES = 588 B)
inline volatile uint16_t mspWaitRespLen = 0;
inline volatile bool     mspWaitRespReady = false;
inline volatile bool     mspWaitRespError = false;   // FC answered "MSP error" for the awaited function
// millis() of the last CRSF chunk accepted for the awaited reply (0 = none
// yet). Stamped by mspParseResponse; mspRequestAndWait pushes its deadline
// out on every stamp — see the note there (0.9.560).
inline volatile uint32_t mspWaitChunkMs = 0;
// millis() of the last reply a synchronous (page/app) request received —
// holds the heartbeat probe off while a client is reading; see mspFcPoll.
inline volatile uint32_t mspLastForegroundMs = 0;

//*********************************************************************
//  Bank put-back state (0.9.567) — see bankBeforeClientRequest below
//*********************************************************************
struct BankState {
    uint8_t  fcPid = 0xFF, fcRate = 0xFF;          // where the FC is now, as far as we know (0xFF = unknown)
    uint8_t  pidCount = 6, rateCount = 6;          // from MSP 101 bytes 24/26
    uint8_t  switchPid = 0xFF, switchRate = 0xFF;  // the switch's banks, noted before a phone's first select (0xFF = no hold)
    uint8_t  clientPid = 0xFF, clientRate = 0xFF;  // the phone's last selects — kept across a put-back, see the re-select
    uint8_t  savedPid = 0xFF, savedRate = 0xFF;    // the banks an EEPROM save in this hold made the boot banks (0xFF = none)
    uint8_t  tries = 0;
    bool     txWarned = false;
    uint32_t holdSinceMs = 0, lastClientMs = 0, lastTryMs = 0;
    uint32_t holds = 0, putBacks = 0;
};
inline BankState banks;
constexpr uint32_t BANK_IDLE_MS       = 5000;     // phone quiet this long → put the switch's banks back
constexpr uint32_t BANK_CLIENT_TTL_MS = 600000;   // a phone select older than this is not re-selected for a stray read
// millis() of a probe (or other fire-and-forget request) the FC has not yet
// answered, 0 = none outstanding. The other half of the 0.9.562 hold-off:
// Rotorflight keeps ONE request buffer, so a page read sent while a probe
// waits in it is thrown away unanswered ("did not respond", 14:21:50 on
// the Goblin, 2026-09-04). Every FC reply clears it; senders wait for it
// (bounded — see mspProbeOutstanding).
inline volatile uint32_t mspProbeSentMs = 0;
constexpr uint32_t       MSP_PROBE_REPLY_WAIT_MS = 500;
inline bool mspProbeOutstanding() {
    return mspProbeSentMs != 0 && (uint32_t)(millis() - mspProbeSentMs) < MSP_PROBE_REPLY_WAIT_MS;
}
// Forensics for the telemetry-setup mystery (0.9.563): the last sends to
// the FC, dumped into the event log the moment MSP 73 comes back empty —
// if a receiver-side write did it, it is in here with its timing.
struct MspSendRec { uint32_t ms; uint8_t fn; uint8_t len; };
constexpr uint8_t MSP_SEND_RING = 24;
inline MspSendRec mspSendRing[MSP_SEND_RING] = {};
inline uint8_t    mspSendRingPos = 0;
inline uint32_t   mspSendCount   = 0;
inline bool              escCatchArmed = false;      // Scorpion boot catcher (see escCatchTick)
inline bool              escCatchGot   = false;
inline const char*       escCatchResult = "none";    // how the last catch ended: captured | nothing | tx | cancelled | none

// Async response capture for the non-blocking TX-parameter state machine
// (TxParams.h). Unlike mspRequestAndWait (which blocks), the TX-param path
// must never stall the radio loop while a transmitter link is live, so it
// sends a request, sets mspAsyncFunc, and polls mspAsyncReady across loop
// iterations — the response is captured here by mspParseResponse as it arrives
// on the normal CRSF RX path. Matched by function code, so an interleaved probe
// response (e.g. FC_VERSION) can't be mistaken for the awaited block.
inline volatile uint8_t  mspAsyncFunc  = 0xFF;       // function TxParams is awaiting (0xFF = none)
inline uint8_t           mspAsyncBuf[640] = {0};
inline volatile uint16_t mspAsyncLen   = 0;
inline volatile bool     mspAsyncReady = false;
// Set by TxParams while a parameter MSP op is in flight, so mspFcPoll yields
// the UART (avoids two outstanding requests confusing the FC).
inline volatile bool     txParamBusy   = false;

//*********************************************************************
//  CRSF address constants
//*********************************************************************

constexpr uint8_t CRSF_ADDR_FC      = 0xC8;
constexpr uint8_t CRSF_ADDR_HANDSET = 0xEA;
constexpr uint8_t CRSF_TYPE_MSP_REQ = 0x7A;
constexpr uint8_t CRSF_TYPE_MSP_RSP = 0x7B;

//*********************************************************************
//  Build + send an MSP v1 request, wrapped in CRSF type 0x7A
//*********************************************************************

// One CRSF 0x7A frame: status byte + up to 57 MSP-body bytes (length byte ≤ 62).
inline void mspSendCrsfChunk(uint8_t status, const uint8_t* data, uint8_t dataLen) {
    uint8_t crsf[64];
    crsf[0] = CRSF_ADDR_FC;                  // sync
    crsf[1] = 5 + dataLen;                   // type + dest + src + status + data + crc
    crsf[2] = CRSF_TYPE_MSP_REQ;
    crsf[3] = CRSF_ADDR_FC;                  // dest = FC
    crsf[4] = CRSF_ADDR_HANDSET;             // src  = handset (us)
    crsf[5] = status;
    memcpy(&crsf[6], data, dataLen);
    uint8_t n = 6 + dataLen;                 // up to and including last MSP byte
    crsf[n] = crsfCrc8(&crsf[2], (uint8_t)(n - 2));
    Serial1.write(crsf, (size_t)(n + 1));
}

// Dongle mode: plain MSP v1 on the UART (MspSerialCore.h), the same
// mspDeliverResponse() at the far end so waiters, digests and the bank
// logic never know the difference.
inline void mspDeliverResponse(uint8_t func, const uint8_t* payload, uint16_t size);   // below
inline MspSerialParser mspSer;
inline void mspSerialOnFrame(void*, uint8_t cmd, const uint8_t* p, uint16_t n, bool isError) {
    fcInfo.lastResponseMs = millis();
    mspProbeSentMs = 0;
    if (isError) {
        if (cmd == mspWaitFunction && !mspWaitRespReady) mspWaitRespError = true;
        return;
    }
    // Any good reply on the wire IS a flight controller: mark it detected at
    // once so the 1 s MSP_STATUS poll (arming = radios off) starts from the
    // first phone request, not only after the identity probe (0.9.599).
    if (!fcInfo.detected) {
        fcInfo.detected = true;
        events.add(dongleEnabled ? "Dongle: the flight controller answered - connected" : "USB: the flight controller answered - connected");
    }
    mspDeliverResponse(cmd, p, n);
}
inline uint32_t mspSerBytes = 0;                       // every byte off the wire in dongle mode - the first thing to look at when the FC is silent
// Declared in 1Defs.h because UsbHostMsp.h is compiled before this file.
// A dropped byte mid-frame would otherwise hold the parser open until a whole
// reply's worth of bytes arrived - up to 4200 since 0.9.663.
inline void mspSerialResetParser() { mspSer.reset(); }
inline void mspSerialFeed(uint8_t b) { mspSerBytes++; mspSer.feed(b, mspSerialOnFrame, nullptr); }   // Telemetry.h's byte pump (prototype in 1Defs.h)
inline void mspSerialSend(uint8_t function, const uint8_t* payload, uint16_t len) {
    static uint8_t frame[8 + 300];
    const uint16_t n = mspSerialEncode(frame, sizeof(frame), function, payload, len);
    if (!n) return;
    if (UsbHostMsp::active()) { UsbHostMsp::send(frame, n); return; }   // USB first, UART otherwise
    if (!dongleEnabled) return;                                          // a receiver's Serial1 is the CRSF line: never a raw MSP frame on it (0.9.639)
    Serial1.write(frame, n);
}

inline void mspSendRequest(uint8_t function, const uint8_t* payload = nullptr, uint8_t payloadLen = 0) {
    // MSP v1 body inside CRSF is just: size(1) function(1) payload(N).
    // The inner XOR checksum is NOT transmitted — CRSF's CRC8 protects it.
    // A body longer than one CRSF frame (57 bytes) goes as chunks the FC
    // reassembles (msp_shared.c): the first carries the start bit and the
    // full MSP header, each later one carries seq+1 and the next bytes.
    // Silently dropping long payloads here is what made the 84-byte
    // Scorpion ESC write (fn 218) vanish (2026-09-02).
    if (payloadLen == 0xFF) return;          // 0xFF size = MSP jumbo marker, never send it
    if (bbCheckActive && !bbCheckOwnSend) {  // the vibration check owns the link (0.9.662): one request outstanding, ever
        static uint32_t lastDropLog = 0;
        if ((uint32_t)(millis() - lastDropLog) > 5000) { lastDropLog = millis(); char m[EventLog::MSG_LEN]; snprintf(m, sizeof m, "MSP %u not sent: the vibration check owns the link", function); events.add(m); }
        return;
    }
    if (mspReplyTooBigForFc(function)) {     // last line of defence — the API refuses it earlier, with the reason
        events.add("MSP 52 (adjustments) NOT sent: its reply overflows Rotorflight's link buffer (RF 4.6 bug)");
        return;
    }
    mspSendRing[mspSendRingPos] = { (uint32_t)millis(), function, payloadLen };
    mspSendRingPos = (uint8_t)((mspSendRingPos + 1) % MSP_SEND_RING);
    mspSendCount++;
    if (UsbHostMsp::cliMode) { if (dongleEnabled || UsbHostMsp::active()) return; }                   // an open command line owns the port: nothing typed into it (a receiver still has its radio-link tunnel)
    if (dongleEnabled || UsbHostMsp::active()) { mspSerialSend(function, payload, payloadLen); return; }   // plain MSP: the dongle's UART, or the USB cable on either (0.9.639)
    if (currentProtocol != PROTO_CRSF || !fcTelemetryEnabled) return;   // no CRSF tunnel on this line (SBUS/IBUS/PPM, or FC telemetry off): nothing to speak through - the caller times out (0.9.642)
    uint8_t body[2 + 255];
    body[0] = payloadLen;
    body[1] = function;
    if (payloadLen) memcpy(&body[2], payload, payloadLen);
    const uint16_t bodyLen = 2 + payloadLen;
    constexpr uint8_t CHUNK = 57;
    uint16_t pos = 0;
    uint8_t seq = 0;
    while (pos < bodyLen) {
        uint8_t n = (uint8_t)((bodyLen - pos > CHUNK) ? CHUNK : (bodyLen - pos));
        // bits 6-5 = 01 (MSP v1), bit 4 = start of frame (first chunk only), bits 3-0 = sequence
        uint8_t status = (uint8_t)(0x20 | (seq & 0x0F) | (pos == 0 ? 0x10 : 0));
        mspSendCrsfChunk(status, &body[pos], n);
        pos += n;
        seq++;
    }
}

//*********************************************************************
//  Parse a CRSF MSP response (type 0x7B) payload — called from Telemetry.h
//*********************************************************************
// `body` points to the CRSF frame's payload (the bytes after type), `bodyLen`
// is the count from dest through last MSP byte (exclusive of CRC — caller has
// already verified that). Layout: dest(1) src(1) status(1) mspBody(N).

// Deliver a COMPLETE MSP response (however many CRSF frames it took) to the
// waiters and the passive-info switch below. Split out of mspParseResponse
// when chunk reassembly arrived (2026-08-19, the Servos screen: RF's bulk
// MSP_SERVO_CONFIGURATIONS is 65 bytes — more than one ~57-byte CRSF frame
// can carry, and the FC answers in CHUNKS we previously threw away).
inline void mspDeliverResponse(uint8_t func, const uint8_t* payload, uint16_t size);

//*********************************************************************
//  Telemetry setup bookkeeping (0.9.563)
//*********************************************************************
// The FC's CRSF telemetry setup (MSP 73/74, 52 bytes: 12-byte header + 40
// sensor slots) has been found all-zero twice on the Goblin with nothing
// on the receiver writing it. Rotorflight's rate limiter and native sensor
// schedule are built at BOOT (crsf.c initCrsfTelemetry), so a zeroed copy
// in RAM changes nothing in the air — it bites only when an EEPROM save
// carries it into flash and the next power-up runs mute: no volts, no RPM.
// So the receiver keeps the last good image and puts it back before that
// can happen (the poll, the pre-save hooks in handleMspApi/TxParams).

// Link speed = header bytes 8-11 (rate u16 LE, ratio u16 LE). Rotorflight's
// default 250/8 = 31 five-byte slots a second, sized for an ELRS radio.
// Our UART runs 420 kbaud with nothing else on it: 1000/1 lets the FC
// answer a page read in ~15 ms instead of ~0.6 s and sends the native
// sensors ~4x more often (verified on the Goblin, 2026-09-04).
constexpr uint16_t TELEM_FAST_RATE = 1000, TELEM_FAST_RATIO = 1;
constexpr uint16_t TELEM_STD_RATE  = 250,  TELEM_STD_RATIO  = 8;
inline bool telemImageGood(const uint8_t* img, uint16_t size) {
    if (size < 52) return false;
    const uint16_t rate  = (uint16_t)(img[8]  | (img[9]  << 8));
    const uint16_t ratio = (uint16_t)(img[10] | (img[11] << 8));
    if (rate == 0 || ratio == 0) return false;
    for (uint16_t i = 12; i < 52; i++) if (img[i]) return true;
    return false;
}
inline bool telemGoodNvsDirty = false;   // fcInfo.telemGood changed; NVS at the next quiet moment
inline void telemRememberGood(const uint8_t* img, uint16_t size) {
    if (!telemImageGood(img, size)) return;
    if (fcInfo.telemGoodValid && memcmp(fcInfo.telemGood, img, 52) == 0) return;
    memcpy(fcInfo.telemGood, img, 52);
    fcInfo.telemGoodValid = true;
    telemGoodNvsDirty = true;
}
// The image the repair writes: the cached good one, else Rotorflight's own
// seven native sensors (flight mode, battery, RPM, temperature, attitude,
// altitude, GPS — the first-time page's ticks). Speed = the preference.
inline void telemBuildImage(uint8_t out[52], bool fast) {
    if (fcInfo.telemGoodValid) memcpy(out, fcInfo.telemGood, 52);
    else {
        static const uint8_t dflt[52] = { 0x00, 0x01, 0, 0, 0, 0, 0x00, 0x00, 0xFA, 0x00, 0x08, 0x00,
                                          89, 2, 108, 109, 64, 58, 72 };
        memcpy(out, dflt, 52);
    }
    const uint16_t rate = fast ? TELEM_FAST_RATE : TELEM_STD_RATE, ratio = fast ? TELEM_FAST_RATIO : TELEM_STD_RATIO;
    out[8] = (uint8_t)rate;  out[9]  = (uint8_t)(rate >> 8);
    out[10] = (uint8_t)ratio; out[11] = (uint8_t)(ratio >> 8);
}
inline const char* telemSpeedName(uint16_t rate, uint16_t ratio) {
    if (rate == TELEM_FAST_RATE && ratio == TELEM_FAST_RATIO) return "fast";
    if (rate == TELEM_STD_RATE  && ratio == TELEM_STD_RATIO)  return "standard";
    if (rate == 0 || ratio == 0) return "none";
    return "custom";
}
// The last sends to the FC, oldest first, as "fn@-secs" — a few lines.
inline void mspSendRingDump(const char* why) {
    char line[EventLog::MSG_LEN];
    int n = snprintf(line, sizeof(line), "%s - last MSP sends:", why);
    const uint32_t now = millis();
    const uint32_t count = mspSendCount < MSP_SEND_RING ? mspSendCount : MSP_SEND_RING;
    for (uint32_t k = 0; k < count; k++) {
        const MspSendRec& r = mspSendRing[(mspSendRingPos + MSP_SEND_RING - count + k) % MSP_SEND_RING];
        char item[24];
        snprintf(item, sizeof(item), " %u%s@-%lus", r.fn, r.len ? "w" : "", (unsigned long)((now - r.ms) / 1000));
        if (n + (int)strlen(item) >= (int)sizeof(line) - 1) {
            events.add(line);
            n = snprintf(line, sizeof(line), "  ...");
        }
        n += snprintf(line + n, sizeof(line) - n, "%s", item);
    }
    events.add(line);
}

inline void mspParseResponse(const uint8_t* body, uint8_t bodyLen) {
    if (bodyLen < 3 + 1) return;                     // dest+src+status + at least 1 MSP byte
    // body[0] = dest, body[1] = src, body[2] = status
    const uint8_t status = body[2];
    const uint8_t* msp = &body[3];
    uint8_t mspLen = (uint8_t)(bodyLen - 3);

    fcInfo.lastResponseMs = millis();                // even an error reply proves the FC is alive
    mspProbeSentMs = 0;                              // whatever was outstanding, the FC's buffer is free again

    // Status byte bit 7 = MSP ERROR. Never capture an error frame as a valid
    // response: its size is 0, and treating it as data used to hand empty
    // buffers to the waiters — the TX-param write machine would then send a
    // zero-length SET followed by EEPROM_WRITE. Let waiters time out + retry.
    // Rotorflight's error reply still names the command ([size][cmd][err]),
    // so a SYNCHRONOUS waiter for that command is told at once instead of
    // burning its full timeout: ESC-programming pages poll MSP 217 and the
    // FC answers "error" until the ESC has been cached — 1.2 s per poll of
    // blocked loop() was the price before (2026-09-02).
    if (status & 0x80) {
        if ((status & 0x10) && mspLen >= 2 && msp[1] == mspWaitFunction && !mspWaitRespReady)
            mspWaitRespError = true;
        return;
    }

    // ---- CRSF MSP chunking (status bits: 0-3 sequence, 4 start-of-frame) ----
    // A response bigger than one CRSF frame arrives as SoF (carrying MSP
    // size+func+first data) followed by continuation frames (pure data,
    // sequence incrementing mod 16). Reassemble; deliver when complete.
    static uint8_t  reBuf[640];
    static uint16_t reExpected = 0;   // total payload bytes we are waiting for
    static uint16_t reGot      = 0;
    static uint8_t  reFunc     = 0;
    static uint8_t  reSeq      = 0;
    static bool     reActive   = false;

    const uint8_t seq = status & 0x0F;
    const bool    sof = (status & 0x10) != 0;

    if (sof) {
        if (mspLen < 2) { reActive = false; return; }
        // MSP v1 JUMBO (Rotorflight telemetry/msp_shared.c sendMspReply): a
        // reply of >= 255 bytes is sent as [0xFF][cmd][size u16 LE][data...].
        // MSP_ADJUSTMENT_RANGES (42 x 14 = 588 B) needs this — without it the
        // profile-selector table could only be written, never read back
        // (Malcolm 2026-08-29: "use the buffer several times").
        uint16_t size;
        uint8_t  func = msp[1];
        const uint8_t* data;
        if (msp[0] == 0xFF) {
            if (mspLen < 4) { reActive = false; return; }
            size = (uint16_t)msp[2] | ((uint16_t)msp[3] << 8);
            data = &msp[4];
        } else {
            size = msp[0];
            data = &msp[2];
        }
        if (size > sizeof(reBuf)) { reActive = false; return; }     // beyond our capacity — drop
        uint16_t dataLen = (uint16_t)(mspLen - (data - msp));
        if (dataLen >= size) {
            // Whole response in one frame — the common fast path.
            reActive = false;
            mspDeliverResponse(func, data, size);
            return;
        }
        // Chunked: start reassembly.
        reActive   = true;
        reExpected = size;
        reFunc     = func;
        reSeq      = seq;
        reGot      = (uint16_t)dataLen;
        memcpy(reBuf, data, dataLen);
        if (func == mspWaitFunction) mspWaitChunkMs = millis();
        return;
    }

    // Continuation frame.
    if (!reActive) return;
    if (seq != (uint8_t)((reSeq + 1) & 0x0F)) { reActive = false; return; }   // lost a chunk
    reSeq = seq;
    uint16_t take = mspLen;
    if (reGot + take > sizeof(reBuf)) { reActive = false; return; }
    memcpy(&reBuf[reGot], msp, take);
    reGot += take;
    if (reFunc == mspWaitFunction) mspWaitChunkMs = millis();
    if (reGot >= reExpected) {
        reActive = false;
        mspDeliverResponse(reFunc, reBuf, reExpected);
    }
    return;
}

// A reply too big for the 640-byte wait/async buffers (only the vibration
// check's dataflash reads, over USB). Set by BlackboxCheck.h while it runs;
// returns true when it has taken the reply. Same task as the parser (loop).
inline bool (*mspBigReplyHook)(uint8_t func, const uint8_t* p, uint16_t n) = nullptr;

inline void mspDeliverResponse(uint8_t func, const uint8_t* payload, uint16_t size) {
    if (mspBigReplyHook && mspBigReplyHook(func, payload, size)) return;

    // Bigger than the FC's own reply buffer = the FC just overwrote part of
    // its memory to answer us (the MSP 52 bug, see the top of this file).
    // Never expected now that 52 is refused; if a fn nobody thought of does
    // it, say so and re-check + repair the telemetry setup straight away.
    if (size > RF_TLM_OUTBUF_SIZE && !UsbHostMsp::active()) {   // over USB a big reply is simply a big reply (0.9.620)
        char m[EventLog::MSG_LEN];
        snprintf(m, sizeof(m), "Rotorflight reply to MSP %u was %u B - more than its %u-byte link buffer: "
                 "FC memory overwritten (RF 4.6 bug); re-checking the telemetry setup. Restart the FC before flying",
                 func, size, RF_TLM_OUTBUF_SIZE);
        events.add(m);
        fcInfo.telemCfgKnown = false;
        fcInfo.telemCfgTries = 0;
        fcInfo.telemRecheck  = true;
    }

    // If a synchronous request is waiting for this function code, capture it.
    if (func == mspWaitFunction && !mspWaitRespReady) {
        if (size > sizeof(mspWaitRespBuf)) size = sizeof(mspWaitRespBuf);
        mspWaitRespLen = size;
        if (size > 0) memcpy(mspWaitRespBuf, payload, size);
        mspWaitRespReady = true;
    }

    // Async capture for the non-blocking TX-parameter state machine (TxParams.h).
    if (func == mspAsyncFunc && !mspAsyncReady) {
        if (size > sizeof(mspAsyncBuf)) size = sizeof(mspAsyncBuf);
        mspAsyncLen = size;
        if (size > 0) memcpy(mspAsyncBuf, payload, size);
        mspAsyncReady = true;
    }

    switch (func) {
        case MSP_FC_VARIANT:
            if (size >= 4) {
                memcpy(fcInfo.variant, payload, 4);
                fcInfo.variant[4] = '\0';
                fcInfo.detected = true;
            }
            break;
        case MSP_FC_VERSION:
            if (size >= 3) {
                fcInfo.fwMajor = payload[0];
                fcInfo.fwMinor = payload[1];
                fcInfo.fwPatch = payload[2];
                fcInfo.versionKnown = true;
            }
            break;
        case MSP_API_VERSION:
            if (size >= 3) {
                fcInfo.mspProto = payload[0];
                fcInfo.apiMajor = payload[1];
                fcInfo.apiMinor = payload[2];
            }
            break;
        case MSP_BATTERY_STATE:
            // 45.1 V is 11S nearly-full AND 12S at storage — voltage alone
            // can never decide (Malcolm 2026-08-05, Black-Thunder-2 shown
            // as 11S). The FC's configured/auto-detected count settles it.
            // Rotorflight 4.6 (msp.c): [0] battery STATE (0 ok, 1 warning,
            // 2 critical, 3 not present, 4 init), [1] cell count, [2-3]
            // capacity, [4-5] used mAh, [6-7] volts 10 mV, [8-9] amps 10 mA,
            // [10] charge %, [11] profile. Betaflight puts the count in byte
            // 0 and that is what this read until 0.9.580 — the Goblin's first
            // answer at power-up (state 3 = not present, before the ESC's
            // volts arrived) became "3S · 46.10 V · 15.37 V/cell" on the
            // Black box (Malcolm 2026-09-07), with the FC's real 12 ignored.
            if (size >= 2 && payload[1] > 0 && payload[1] <= 14)
                fcInfo.cells = payload[1];
            break;
        case MSP_ESC_PARAMETERS:
            if (size >= 2) escCatchGot = true;   // FC now holds the ESC's settings
            break;
        // Where the FC is (0.9.567): from our own reads and from any page's.
        // Rotorflight: bytes 23 = PID bank, 24 = count, 25 = rates bank, 26 = count.
        case MSP_STATUS:
            // Bytes 6-9 = flight-mode flags, bit 0 = BOXARM: the FC's own
            // "armed". The dongle has no arm channel of its own (2026-09-08).
            if (size >= 10) { fcInfo.armed = (payload[6] & 1) != 0; fcInfo.armedMs = millis(); }
            if (size >= 27) {
                banks.fcPid  = payload[23];
                banks.fcRate = payload[25];
                if (payload[24] >= 1 && payload[24] <= 8) banks.pidCount  = payload[24];
                if (payload[26] >= 1 && payload[26] <= 8) banks.rateCount = payload[26];
            }
            break;
        // Governor throttle watch inputs (0.9.551). These arrive from our own
        // probe AND from any page that reads them via /api/msp, so the values
        // track edits made on the phone. RAM only here — the probe may run
        // in the air (TX-on boot) and an NVS write is a flash stall, so the
        // watch tick commits them at the next quiet moment.
        case MSP_RX_MAP:
            // Rotorflight's order only (A E R C T: [4] = throttle). Betaflight
            // and INAV put AUX1 there, and this channel now decides which
            // channel the receiver holds low before a transmitter is heard.
            if (size >= 5 && payload[4] < 16 && strncmp(fcInfo.variant, "RTFL", 4) == 0) {
                uint8_t ch = payload[4] + 1;
                if (ch != fcInfo.throttleCh) {
                    fcInfo.throttleCh = ch;
                    fcInfoNvsDirty = true;
                    char m[64];
                    snprintf(m, sizeof(m), "Throttle channel found from Rotorflight: ch%u", ch);
                    events.add(m);
                }
            }
            break;
        case MSP_GOVERNOR_CONFIG:
            if (size >= 1 && payload[0] != fcInfo.govMode) {
                fcInfo.govMode = payload[0];
                fcInfoNvsDirty = true;
            }
            break;
        // Telemetry setup (0.9.556) — from our probe or a page's read; a
        // reply shorter than the 12-byte header is an older layout, ignored.
        case MSP_TELEMETRY_CONFIG:
            if (size >= 12) {
                const bool wasBad = fcTelemCfgBad();
                uint8_t n = 0;
                for (uint16_t i = 12; i < size; i++) if (payload[i]) n++;
                fcInfo.telemMode     = payload[7];
                fcInfo.telemRate     = (uint16_t)(payload[8] | (payload[9] << 8));
                fcInfo.telemRatio    = (uint16_t)(payload[10] | (payload[11] << 8));
                fcInfo.telemSensors  = n;
                fcInfo.telemCfgKnown = true;
                fcInfo.telemCfgTries = 0;
                fcInfo.telemRecheck  = false;
                fcInfo.telemCheckedMs = millis();
                telemRememberGood(payload, size);
                if (fcTelemCfgBad() && !wasBad) {
                    char m[128];
                    snprintf(m, sizeof(m), "Rotorflight telemetry setup EMPTY (%u sensors, link rate %u/%u) - "
                             "no volts/RPM after a save. Cause: a reply too big for the FC's link buffer (MSP 52, RF 4.6 bug) "
                             "or a Configurator/Lua write", n, fcInfo.telemRate, fcInfo.telemRatio);
                    events.add(m);
                    mspSendRingDump("telemetry setup empty");
                    // Put the cached good image back in RAM at the poll's
                    // next slot (no restart needed — nothing changes until
                    // a save, and this makes sure a save carries the good
                    // one). Capped: a repair the FC keeps losing is a bug
                    // to report, not a loop to run.
                    if (fcInfo.telemGoodValid && fcInfo.telemRepairs < 5) fcInfo.telemRepairDue = true;
                } else if (!fcTelemCfgBad() && wasBad) {
                    char m[80];
                    snprintf(m, sizeof(m), "Rotorflight telemetry setup OK again (%u sensors, link rate %u/%u)",
                             n, fcInfo.telemRate, fcInfo.telemRatio);
                    events.add(m);
                    fcInfo.telemRepairDue = false;
                }
            }
            break;
        default:
            break;
    }
}

//*********************************************************************
//  Governor throttle watch — call from loop(), self-paced at 1 Hz
//*********************************************************************
// Goblin 770, 2026-09-03: bank 1 "stable but far too slow", banks changed
// nothing, and after a visit to bank 3 the RPM "would not drop". The FC was
// fine — the V1 transmitter was still sending the ESC-governor-era throttle
// values (50 % in bank 1). Rotorflight's ELECTRIC governor uses the throttle
// only as permission: below ~99 % of the target head speed (or 95 %
// throttle) it sits in spool-up FOREVER, feeding the ESC whatever the TX
// sends. The receiver sees the throttle channel every frame, so it can catch
// this itself: a long armed spell in which the throttle never reached full
// gets a verdict on disarm, written to NVS at the next quiet moment, and the
// governor pages nag until a flight reaches 100 %. Only judged when the FC
// runs a real governor (electric/nitro) and told us its throttle channel.
inline bool govThrottleGoverned() { return fcInfo.govMode == 3 || fcInfo.govMode == 4; }

inline void govThrottleWatchTick() {
    if (bbCheckActive) return;   // the vibration check owns the link (0.9.662)
    static uint32_t lastMs = 0;
    static bool     wasArmed = false;
    static uint16_t armedS = 0, parkedS = 0;
    static uint32_t parkedPctSum = 0;
    static uint8_t  maxPct = 0;
    static bool     verdictDirty = false;    // govThrParkedPct/govThrMaxPct changed, NVS not yet written
    const uint32_t now = millis();
    if ((uint32_t)(now - lastMs) < 1000) return;
    lastMs = now;

    const bool linkLive = rx.lastMillis && (uint32_t)(now - rx.lastMillis) < 2000;
    const bool armed = linkLive && armingChannel >= 1 && armingChannel <= 16 &&
                       channelMicros[armingChannel - 1] > 1500;
    if (armed && !wasArmed) { armedS = parkedS = 0; parkedPctSum = 0; maxPct = 0; }
    if (armed) {
        armedS++;
        if (fcInfo.throttleCh >= 1 && fcInfo.throttleCh <= 16) {
            // Rotorflight reads throttle as (µs − 1000) / 10 %; our CRSF
            // output hands the FC the same µs the TX sent (988..2012 clamp).
            int pct = ((int)channelMicros[fcInfo.throttleCh - 1] - 1000) / 10;
            if (pct < 0) pct = 0;
            if (pct > 100) pct = 100;
            if (pct > maxPct) maxPct = (uint8_t)pct;
            if (pct >= 30 && pct <= 94) { parkedS++; parkedPctSum += pct; }
        }
    } else if (wasArmed && armedS >= 20 && fcInfo.throttleCh && govThrottleGoverned()) {
        // End of a real armed spell: judge it. ≥15 s between 30 and 94 % and
        // never full = parked. Reaching ≥95 % at any point clears an old
        // verdict — that is a governed flight. Anything else (a 0 % spell,
        // the ESC-off bank test) says nothing and changes nothing.
        uint8_t verdict = 0xFF;
        if (maxPct <= 94 && parkedS >= 15) {
            verdict = (uint8_t)(parkedPctSum / parkedS);
            char m[EventLog::MSG_LEN];
            snprintf(m, sizeof(m), "Throttle sat at %u%% while armed: governor never took over (needs 100%%)", verdict);
            events.add(m);
        } else if (maxPct >= 95) {
            if (govThrParkedPct) events.add("Throttle reached full while armed — governor check cleared");
            verdict = 0;
        }
        if (verdict != 0xFF) {
            govThrParkedPct = verdict;
            govThrMaxPct    = maxPct;
            verdictDirty    = true;
        }
    }
    wasArmed = armed;

    // NVS writes are flash stalls: only in a provably-quiet moment (the
    // flight-save doctrine — disarmed with sticks still 2 s, or TX off).
    // Also commits the throttle channel / governor mode the probe learned,
    // which may have arrived mid-flight on a TX-on boot.
    if ((verdictDirty || fcInfoNvsDirty || telemGoodNvsDirty) && !armed) {
        const bool sticksStill = lastChMoveMs && (uint32_t)(now - lastChMoveMs) >= 2000;
        const bool linkDead    = !rx.lastMillis || (uint32_t)(now - rx.lastMillis) > 3000;
        if (sticksStill || linkDead) {
            if (verdictDirty) {
                prefs.putUChar(NVS_KEY_GOV_THR_PARKED, govThrParkedPct);
                prefs.putUChar(NVS_KEY_GOV_THR_MAX, govThrMaxPct);
                verdictDirty = false;
            }
            if (fcInfoNvsDirty) {
                prefs.putUChar(NVS_KEY_FC_THR_CH, fcInfo.throttleCh);
                prefs.putUChar(NVS_KEY_FC_GOV_MODE, fcInfo.govMode);
                fcInfoNvsDirty = false;
            }
            if (telemGoodNvsDirty) {                 // the last good telemetry setup (0.9.563)
                prefs.putBytes(NVS_KEY_FC_TELEM_GOOD, fcInfo.telemGood, 52);
                telemGoodNvsDirty = false;
            }
        }
    }
}

//*********************************************************************
//  Synchronous MSP request: send and wait for response
//*********************************************************************
// Used by HTTP request handlers to talk to the FC. Blocks for up to
// timeoutMs while pumping Serial1 → CRSF parser → mspParseResponse, which
// will set mspWaitRespReady=true if the matching function code comes back.

// Big replies dribble (0.9.560). Rotorflight 4.6 meters ALL its CRSF
// telemetry — MSP chunks included — through a token bucket sized for an
// ELRS-style link: crsf_telemetry_link_rate / link_ratio (default 250/8)
// = 31 five-byte slots a second. A 64-byte MSP chunk costs 14 slots, so
// chunk N+1 follows chunk N only ~0.45-0.8 s later. A 224-byte reply
// (mixer rules, 4 chunks) takes ~2 s and the 588-byte adjustment table
// (11 chunks) ~6 s — both used to die at this 1.2 s wait and were blamed
// on "the FC's output buffer" (0.9.457) and then "1 read got no answer"
// (the Goblin's first phone backup, 2026-09-04). So: `timeoutMs` is the
// wait for the FIRST chunk; every accepted chunk of OUR reply earns
// another MSP_CHUNK_GRACE_MS, under an overall cap. The FC is answering —
// just slowly — and abandoning a reply midway is worse than waiting: the
// FC keeps sending the rest anyway and the NEXT request's answer queues
// behind it (that was the "spurious" 504 on the read after a failed one).
constexpr uint32_t MSP_CHUNK_GRACE_MS = 1500;    // worst measured gap ~0.8 s (bucket at -25)
constexpr uint32_t MSP_WAIT_CAP_MS    = 12000;   // 588 B = 11 chunks; never longer than this

inline bool mspRequestAndWait(uint8_t function, const uint8_t* req, uint8_t reqLen,
                              uint8_t* outBuf, uint16_t* outLen, uint32_t timeoutMs) {
    if (bbCheckActive) return false;   // the vibration check owns the link (0.9.662): no waiting, no second request
    extern void protocolRx();   // defined in Telemetry.h
    extern void sbusTick();     // defined in Output.h
    extern void radioPoll();    // defined in Radio.h
    // NEVER on a dongle or in sim mode: there D5/D6 are the FC's MSP UART, and
    // sbusTick() would write RC frames into it. cliWait() has always known this.
    
    // A probe the FC has not answered yet is sitting in its one request
    // buffer; ours would land behind it and be thrown away (0.9.563 — the
    // reverse of the 0.9.562 hold-off). Wait for that reply, bounded.
    while (mspProbeOutstanding()) {
        keepLinkTick();
        delay(1);
    }
    mspWaitFunction  = function;
    mspWaitRespReady = false;
    mspWaitRespError = false;
    mspWaitRespLen   = 0;
    mspWaitChunkMs   = 0;
    // The same bucket is drained by whatever the FC just sent us, so right
    // after a reply (any size) even the FIRST chunk of the next one can take
    // more than 1.2 s — 0.9.560's first live run: MSP 120 timed out straight
    // after a 2-chunk MSP 34. A recent MSP reply also proves the FC is alive,
    // so the longer wait never slows "no flight controller" detection.
    const uint32_t baseTimeoutMs = timeoutMs;
    if ((uint32_t)(millis() - fcInfo.lastResponseMs) < 3000) timeoutMs += 1500;
    mspSendRequest(function, req, reqLen);
    const uint32_t start = millis();
    uint32_t deadline  = start + timeoutMs;
    uint32_t lastChunk = 0;
    while (!mspWaitRespReady && !mspWaitRespError && (int32_t)(deadline - millis()) > 0) {
        // Keep FLYING while we wait (Malcolm 2026-09-01: an erroring ESC-
        // programming poll made the swash twitch every ~2 s — this wait
        // starved the channel stream and the FC flickered into failsafe).
        // The radio keeps channels fresh, sbusTick keeps frames flowing.
        keepLinkTick();            // receiver: keep flying. Dongle: DRAIN the FC's UART — the reply arrives on it
        delay(1);
        const uint32_t chunkMs = mspWaitChunkMs;
        if (chunkMs && chunkMs != lastChunk) {           // a chunk of OUR reply landed
            lastChunk = chunkMs;
            uint32_t ext = chunkMs + MSP_CHUNK_GRACE_MS;
            const uint32_t cap = start + MSP_WAIT_CAP_MS;
            if ((int32_t)(ext - cap) > 0) ext = cap;
            if ((int32_t)(ext - deadline) > 0) deadline = ext;
        }
    }
    bool ok = mspWaitRespReady;
    mspWaitFunction = 0xFF;
    if (ok) {
        mspLastForegroundMs = millis();
        if (outLen) *outLen = mspWaitRespLen;
        if (outBuf && mspWaitRespLen > 0) memcpy(outBuf, mspWaitRespBuf, mspWaitRespLen);
        // Evidence for the log: a reply that only made it thanks to the
        // per-chunk grace (it would have been a 504 before 0.9.560).
        const uint32_t took = millis() - start;
        if (took > baseTimeoutMs) {
            char b[EventLog::MSG_LEN];
            snprintf(b, sizeof(b), "MSP %u: %u-byte reply took %lu ms (FC telemetry rate limit, chunked)",
                     (unsigned)function, (unsigned)mspWaitRespLen, (unsigned long)took);
            events.add(b);
        }
    }
    return ok;
}

//*********************************************************************
//  Telemetry setup — synchronous helpers for the page/app paths (0.9.563)
//*********************************************************************
// All of these block like a page read does, so they run only from request
// handlers (never in flight: /api/msp is refused while armed).

// Fresh MSP 73 image. Returns the bytes copied (0 = no answer); the passive
// switch in mspDeliverResponse has already digested the reply.
inline uint16_t telemReadSync(uint8_t out[52]) {
    static uint8_t buf[640];
    uint16_t len = 0;
    if (!mspRequestAndWait(MSP_TELEMETRY_CONFIG, nullptr, 0, buf, &len, 1200)) return 0;
    if (len > 52) len = 52;
    memcpy(out, buf, len);
    return len;
}
// The bytes MSP 74 stores and MSP 73 echoes: inverted, halfDuplex, pinSwap,
// mode, rate, ratio, sensors. Bytes 2-5 are a legacy u32 the FC ignores.
inline bool telemImageSame(const uint8_t* a, const uint8_t* b) {
    return a[0] == b[0] && a[1] == b[1] && memcmp(a + 6, b + 6, 46) == 0;
}
// Write an image into FC RAM and read it back. True when the FC holds it.
// telemWriteWhy says which step failed (Malcolm 2026-09-10: "Not applied"
// on a fast-telemetry apply with no clue why) - shown to the user and logged.
inline char telemWriteWhy[100] = "";
inline bool telemWriteSync(const uint8_t img[52]) {
    static uint8_t buf[64];
    uint16_t len = 0;
    telemWriteWhy[0] = 0;
    if (!mspRequestAndWait(MSP_SET_TELEMETRY_CONFIG, img, 52, buf, &len, 1200)) {
        snprintf(telemWriteWhy, sizeof telemWriteWhy, mspWaitRespError ? "the flight controller rejected the write (MSP error)"
                                                                       : "no acknowledgement of the write within 1.2 s");
        return false;
    }
    uint8_t back[52] = {0};
    const uint16_t n = telemReadSync(back);
    if (n < 52) { snprintf(telemWriteWhy, sizeof telemWriteWhy, "the read-back answered %u bytes, not 52", (unsigned)n); return false; }
    if (!telemImageSame(back, img)) {
        int at = -1;
        if (back[0] != img[0]) at = 0; else if (back[1] != img[1]) at = 1;
        else for (int i = 6; i < 52; i++) if (back[i] != img[i]) { at = i; break; }
        snprintf(telemWriteWhy, sizeof telemWriteWhy, "the read-back differs at byte %d (sent %u, FC holds %u)%s",
                 at, at >= 0 ? img[at] : 0, at >= 0 ? back[at] : 0,
                 (at >= 8 && at <= 11) ? " - the link rate/ratio was not accepted" : "");
        return false;
    }
    return true;
}
// Before an EEPROM save asked for by a page, the app or the transmitter
// path: read the FC's RAM copy; if it is the empty one, put the cached good
// image back first, so the save can never carry the empty one into flash.
// 0 = fine (or repaired), 1 = empty and nothing to put back / repair
// failed, 2 = the FC did not answer the read (the save goes ahead — a busy
// FC is not an empty one; the watch re-checks within 30 s).
inline uint8_t telemGuardBeforeSave(const char* who) {
    if (dongleEnabled) return 0;   // a dongle never rewrites another model's telemetry setup
    uint8_t img[52] = {0};
    const uint16_t n = telemReadSync(img);
    if (n < 12) return 2;
    if (telemImageGood(img, n)) return 0;
    char m[EventLog::MSG_LEN];
    if (!fcInfo.telemGoodValid || fcInfo.telemRepairs >= 5) {
        snprintf(m, sizeof(m), "%s: telemetry setup EMPTY before save - nothing to put back", who);
        events.add(m);
        return 1;
    }
    const bool ok = telemWriteSync(fcInfo.telemGood);
    fcInfo.telemRepairs++;
    snprintf(m, sizeof(m), "%s: telemetry setup EMPTY before save - good copy put back %s", who, ok ? "OK" : "FAILED");
    events.add(m);
    return ok ? 0 : 1;
}
// Save + restart, each confirmed before the next (the FC answers 250; it
// does not answer 68 — it is gone). False = the save was never confirmed,
// nothing restarted.
inline bool telemSaveAndRestartSync() {
    static uint8_t buf[64];
    uint16_t len = 0;
    bool saved = mspRequestAndWait(MSP_EEPROM_WRITE, nullptr, 0, buf, &len, 1500);
    if (!saved) saved = mspRequestAndWait(MSP_EEPROM_WRITE, nullptr, 0, buf, &len, 1500);
    if (!saved) return false;
    // The FC never answers 68 — fire twice (a lost single frame once left
    // a saved setup silently not yet active), keeping the channels flowing.
    extern void protocolRx(); extern void sbusTick(); extern void radioPoll();
    mspSendRequest(MSP_REBOOT);
    for (uint32_t t0 = millis(); (uint32_t)(millis() - t0) < 100; ) { keepLinkTick(); delay(1); }
    mspSendRequest(MSP_REBOOT);
    fcInfo.telemCfgKnown = false;      // re-read once the FC is back
    fcInfo.telemCfgTries = 0;
    fcInfo.telemRecheck  = true;
    fcInfo.telemRepairDue = false;
    return true;
}
// Set the FC's telemetry link speed: read-modify-write of bytes 8-11 only,
// save, restart (the rate limiter and sensor schedule are built at boot).
// Returns true when the FC is restarting with the new speed saved; `msg`
// tells the page what happened either way. `changed` = false means the FC
// already ran that speed and nothing was written.
inline bool telemApplySpeedSync(bool fast, bool* changed, char* msg, size_t msgLen) {
    *changed = false;
    uint8_t img[52] = {0};
    uint16_t n = telemReadSync(img);
    if (n < 52) n = telemReadSync(img);
    if (n < 52) { snprintf(msg, msgLen, "the flight controller did not answer the telemetry read - try again"); return false; }
    const uint16_t rate = fast ? TELEM_FAST_RATE : TELEM_STD_RATE, ratio = fast ? TELEM_FAST_RATIO : TELEM_STD_RATIO;
    if (telemImageGood(img, n) &&
        (uint16_t)(img[8] | (img[9] << 8)) == rate && (uint16_t)(img[10] | (img[11] << 8)) == ratio) {
        snprintf(msg, msgLen, "the flight controller already runs %s telemetry - nothing to change", fast ? "fast" : "standard");
        return true;
    }
    if (!telemImageGood(img, n)) {
        if (!fcInfo.telemGoodValid) {
            snprintf(msg, msgLen, "the flight controller's telemetry setup is empty and no good copy is cached - "
                                  "use Restore telemetry sensors first");
            return false;
        }
        memcpy(img, fcInfo.telemGood, 52);   // repair on the way through
    }
    img[8]  = (uint8_t)rate;  img[9]  = (uint8_t)(rate >> 8);
    img[10] = (uint8_t)ratio; img[11] = (uint8_t)(ratio >> 8);
    if (!telemWriteSync(img)) {
        snprintf(msg, msgLen, "the flight controller did not take the new setup - nothing saved (%s)", telemWriteWhy);
        char e[EventLog::MSG_LEN]; snprintf(e, sizeof e, "Telemetry speed NOT applied: %s", telemWriteWhy); events.add(e);
        return false;
    }
    *changed = true;
    if (!telemSaveAndRestartSync()) {
        snprintf(msg, msgLen, "the flight controller did not confirm the save - not restarted, try again");
        return false;
    }
    telemRememberGood(img, 52);
    char m[EventLog::MSG_LEN];
    snprintf(m, sizeof(m), "Telemetry speed set to %s (link rate %u/%u), saved - FC restarting", fast ? "FAST" : "standard", rate, ratio);
    events.add(m);
    snprintf(msg, msgLen, "%s telemetry saved - the flight controller is restarting (about 10 s)", fast ? "fast" : "standard");
    return true;
}

//*********************************************************************
//  Bank put-back (0.9.567): the switch's banks come back after a phone session
//*********************************************************************
// Rotorflight re-applies a bank (profile) switch only when the switch MOVES:
// rc_adjustments.c processRcAdjustments calls cfgSet only when the value
// the channel maps to differs from the value the switch last applied, and a
// select over MSP 210 never updates that value (verified on 4.6.0,
// 2026-09-05). Every tuning page selects the bank it shows so the
// Configurator matches (Malcolm 2026-08-06) — and so the model is FLOWN on
// the page's bank until the switch moves. Malcolm's TX moves the PID bank
// at motor-on (bank 4 → 1/2/3); the rates switch does not move, so a rates
// page could hand the model a different rates bank (2026-09-04).
//
// The receiver closes the gap for every page and both apps at once:
//  - on a phone's first bank select it reads where the FC is — the
//    switch's banks, the transmitter being off — and holds them;
//  - once the phone has been quiet for BANK_IDLE_MS, transmitter off and
//    disarmed, it puts them back, and saves if the session's save had made
//    another bank the boot bank (so a power-up lands on the switch's too);
//  - never under a live transmitter: the switch may have moved (or been
//    moved to the very bank the page shows) and Rotorflight owns the
//    banks then — the hold is dropped, with a note. A TX-on session keeps
//    Rotorflight's native behaviour: every save re-loads the config and
//    re-applies the switch at once (config.c activateConfig →
//    adjustmentRangeInit), so only a page's post-save re-select can leave
//    the FC on the page's bank — flip the switch once before flying;
//  - the phone never notices: a bank-dependent request that arrives after
//    a put-back gets the phone's own bank re-selected first (the app's
//    restore runner skips selects it believes are already true — a
//    put-back in a long gap must not send its next write to the wrong
//    bank), and that re-select opens a new hold.
// Every exchange here is synchronous like a page's, from loop() only when
// no other MSP traffic is outstanding (one request at a time at the FC).

inline bool bankFnPidSide(uint8_t fn) {
    return fn == MSP_PID || fn == MSP_SET_PID || fn == MSP_PID_PROFILE || fn == MSP_SET_PID_PROFILE ||
           fn == 146 || fn == 147 ||                       // rescue profile read / write
           fn == MSP_GOVERNOR_PROFILE || fn == MSP_SET_GOVERNOR_PROFILE;
}
inline bool bankFnRateSide(uint8_t fn) { return fn == MSP_RC_TUNING || fn == MSP_SET_RC_TUNING; }
inline bool bankTxLive() {
    if (dongleEnabled) return true;          // unknown = assume the model's transmitter may be on: never switch banks unasked
    return rx.lastMillis != 0 && (uint32_t)(millis() - rx.lastMillis) < 2000;
}
inline bool bankHeld()   { return banks.switchPid != 0xFF; }
inline void bankRelease() { banks.switchPid = banks.switchRate = 0xFF; banks.savedPid = banks.savedRate = 0xFF; banks.tries = 0; }

// What the FC does with a 210 byte (msp.c MSP_SELECT_SETTING: bit 7 = rates,
// out of range → 0). Only a PHONE's select is the phone's choice — the
// receiver's own put-back selects must leave clientPid/clientRate alone,
// or the re-select below has nothing to re-select (bench, 0.9.567: the
// put-back overwrote them and a bankless read went to the switch's bank).
inline void bankNoteSelect(uint8_t b, bool fromPhone) {
    uint8_t v = (uint8_t)(b & 0x7F);
    if (b & 0x80) { if (v >= banks.rateCount) v = 0; banks.fcRate = v; if (fromPhone) banks.clientRate = v; }
    else          { if (v >= banks.pidCount)  v = 0; banks.fcPid  = v; if (fromPhone) banks.clientPid  = v; }
}
// Fresh MSP 101 — the passive digest fills banks.fcPid/fcRate. False = no usable answer.
inline bool bankReadSync() {
    static uint8_t buf[64];
    uint16_t len = 0;
    banks.fcPid = banks.fcRate = 0xFF;
    if (!mspRequestAndWait(MSP_STATUS, nullptr, 0, buf, &len, 1200)) return false;
    return banks.fcPid != 0xFF;
}
inline bool bankSelectSync(uint8_t b) {
    static uint8_t buf[16];
    uint16_t len = 0;
    if (!mspRequestAndWait(MSP_SELECT_SETTING, &b, 1, buf, &len, 1200)) return false;
    bankNoteSelect(b, false);
    return true;
}
// Open a hold if none: note the switch's banks before the phone moves them.
inline void bankOpenHold() {
    if (bankHeld()) return;
    if (dongleEnabled) {
        // The dongle cannot see the model's own transmitter, so it never
        // puts banks back by itself: a phone's bank stays until the switch
        // moves (Rotorflight re-applies the switch only on a change).
        if (!banks.txWarned) { banks.txWarned = true; events.add("Dongle: a phone's bank selection stays until the model's own bank switch is moved"); }
        return;
    }
    if (bankTxLive()) {
        if (!banks.txWarned) {
            banks.txWarned = true;
            events.add("A phone page selected a bank with the transmitter ON: the switch takes its bank back only when moved");
        }
        return;
    }
    if (!bankReadSync()) {
        events.add("Phone bank select: the FC did not say which banks it is on (MSP 101) - nothing to put back later");
        return;
    }
    banks.switchPid = banks.fcPid;
    banks.switchRate = banks.fcRate;
    banks.holdSinceMs = millis();
    banks.savedPid = banks.savedRate = 0xFF;
    banks.tries = 0;
    banks.holds++;
    char m[EventLog::MSG_LEN];
    snprintf(m, sizeof(m), "Phone is selecting banks: the switch had PID bank %u, rates bank %u - back when the phone is quiet",
             banks.switchPid + 1, banks.switchRate + 1);
    events.add(m);
}

// Called by handleMspApi for every page/app request, before it goes to the
// FC. May run MSP exchanges of its own first (snapshot, re-select).
inline void bankBeforeClientRequest(uint8_t fn, const uint8_t* data, uint8_t len) {
    const uint32_t now = millis();
    if (banks.lastClientMs && (uint32_t)(now - banks.lastClientMs) > BANK_CLIENT_TTL_MS)
        banks.clientPid = banks.clientRate = 0xFF;          // yesterday's page is not today's
    banks.lastClientMs = now;
    if (fn == MSP_REBOOT) { banks.fcPid = banks.fcRate = 0xFF; return; }   // boots on its saved banks
    if (fn == MSP_SELECT_SETTING) {
        if (len >= 1) bankOpenHold();
        return;
    }
    const bool pidSide  = bankFnPidSide(fn)  || fn == MSP_EEPROM_WRITE;
    const bool rateSide = bankFnRateSide(fn) || fn == MSP_EEPROM_WRITE;
    if (!pidSide && !rateSide) return;
    // The transparent re-select: the FC is not where this phone last put it
    // (a put-back, an FC restart) — put it there before the request lands.
    const bool needPid  = pidSide  && banks.clientPid  != 0xFF && banks.fcPid  != banks.clientPid;
    const bool needRate = rateSide && banks.clientRate != 0xFF && banks.fcRate != banks.clientRate;
    if (!needPid && !needRate) return;
    bankOpenHold();
    char m[EventLog::MSG_LEN];
    snprintf(m, sizeof(m), "Bank re-selected for the phone before MSP %u:%s%s", fn,
             needPid ? " PID" : "", needRate ? " rates" : "");
    events.add(m);
    if (needPid)  bankSelectSync(banks.clientPid);
    if (needRate) bankSelectSync((uint8_t)(0x80 | banks.clientRate));
}
// ...and after the FC answered (ok = it did).
inline void bankAfterClientRequest(uint8_t fn, const uint8_t* data, uint8_t len, bool ok) {
    if (!ok) return;
    if (fn == MSP_SELECT_SETTING && len >= 1) bankNoteSelect(data[0], true);
    // A phone that asks MSP_STATUS now BELIEVES the banks it was just told.
    // Until 0.9.582 the receiver kept the bank of the phone's LAST select
    // (10-minute TTL) and re-selected it before the next bank-side read -
    // so a backup sweep that started on the FC's current bank without
    // selecting it (the app skips a select it thinks is redundant) had the
    // FC moved under it to a bank left by an earlier, aborted sweep, saw
    // the move in its own MSP 101 check, and gave up with "the flight
    // controller changed bank mid-backup" - every time, at home, TX off
    // (Malcolm 2026-09-07 11:50; the first abort was a Mac script reading
    // the banks while the app auto-backed up at connection - my fault).
    else if (fn == MSP_STATUS) {
        banks.clientPid  = banks.fcPid;
        banks.clientRate = banks.fcRate;
    }
    else if (fn == MSP_EEPROM_WRITE) {
        // The banks selected at the save are now the boot banks. And the
        // save re-loads the config (config.c readEEPROM → activateConfig →
        // adjustmentRangeInit): the switch logic restarts from the current
        // bank and, with the FC receiving frames, re-applies the switch
        // at once — the FC may have moved by itself (seen on the bench,
        // 2026-09-05: rates bank 2 + save → FC back on bank 1 unasked).
        // So where it is now is unknown until the next MSP 101.
        if (bankHeld()) { banks.savedPid = banks.fcPid; banks.savedRate = banks.fcRate; }
        banks.fcPid = banks.fcRate = 0xFF;
    }
}

// From loop(): the put-back itself, when the phone has gone quiet.
inline void bankPutBackTick() {
    if (!bankHeld()) return;
    const uint32_t now = millis();
    if ((currentProtocol != PROTO_CRSF || !fcTelemetryEnabled) && !UsbHostMsp::active()) { bankRelease(); return; }   // over USB the banks are still ours to put back (0.9.640)
    if (bankTxLive()) {
        // Rotorflight owns the banks from here; a note says where it was left.
        char m[EventLog::MSG_LEN];
        snprintf(m, sizeof(m), "Transmitter on before the banks went back: FC left on PID bank %u, rates bank %u "
                 "(switch had %u/%u) - it follows the switch once moved",
                 banks.fcPid == 0xFF ? 0 : banks.fcPid + 1, banks.fcRate == 0xFF ? 0 : banks.fcRate + 1,
                 banks.switchPid + 1, banks.switchRate + 1);
        events.add(m);
        bankRelease();
        return;
    }
    // Only the MSP work waits for the vibration check (0.9.669): the transmitter
    // hand-over above must stay reachable, and bankReadSync/bankSelectSync would
    // fail instantly while the check owns the link and burn the retry count.
    if (bbCheckActive) return;
    if ((uint32_t)(now - banks.lastClientMs) < BANK_IDLE_MS) return;
    if (mspBridgeActive || txParamBusy || mspWaitFunction != 0xFF || mspProbeOutstanding()) return;
    if ((uint32_t)(now - banks.lastTryMs) < 2000) return;
    banks.lastTryMs = now;
    if (!bankReadSync()) {
        if (++banks.tries >= 5) { events.add("Bank put-back given up: the flight controller is not answering"); bankRelease(); }
        return;
    }
    const uint8_t wasPid = banks.fcPid, wasRate = banks.fcRate;
    bool ok = true;
    if (banks.fcPid  != banks.switchPid)  ok = bankSelectSync(banks.switchPid) && ok;
    if (banks.fcRate != banks.switchRate) ok = bankSelectSync((uint8_t)(0x80 | banks.switchRate)) && ok;
    const bool moved = wasPid != banks.switchPid || wasRate != banks.switchRate;
    // A save in this session made another bank the boot bank: save again on
    // the switch's, so a power-up lands there too. TX off, disarmed, phone
    // quiet — the same ground the page's own save stood on.
    const bool bootWrong = banks.savedPid != 0xFF && (banks.savedPid != banks.switchPid || banks.savedRate != banks.switchRate);
    bool saved = false;
    if (ok && bootWrong) {
        if (telemGuardBeforeSave("bank put-back") == 1) {
            events.add("Bank put-back: boot bank not saved - the FC's telemetry setup is empty (see the Rotorflight page)");
        } else {
            static uint8_t buf[16];
            uint16_t len = 0;
            saved = mspRequestAndWait(MSP_EEPROM_WRITE, nullptr, 0, buf, &len, 1500);
            if (!saved) saved = mspRequestAndWait(MSP_EEPROM_WRITE, nullptr, 0, buf, &len, 1500);
            ok = ok && saved;
        }
    }
    if (ok && (moved || saved)) ok = bankReadSync() && banks.fcPid == banks.switchPid && banks.fcRate == banks.switchRate;
    if (!ok && ++banks.tries < 3) return;                   // once more in 2 s
    char m[EventLog::MSG_LEN];
    if (ok) {
        if (moved) {
            banks.putBacks++;
            snprintf(m, sizeof(m), "Banks put back for the switch: PID bank %u, rates bank %u (phone had left %u/%u)%s",
                     banks.switchPid + 1, banks.switchRate + 1, wasPid + 1, wasRate + 1,
                     saved ? ", saved as the boot banks too" : "");
            events.add(m);
        } else if (saved) {
            banks.putBacks++;
            snprintf(m, sizeof(m), "Boot banks saved back for the switch: PID bank %u, rates bank %u (the phone's save had made %u/%u the boot banks)",
                     banks.switchPid + 1, banks.switchRate + 1, banks.savedPid + 1, banks.savedRate + 1);
            events.add(m);
        }
        // else: the phone put them back itself (copy-bank page, the app) — nothing to say
    } else {
        snprintf(m, sizeof(m), "Bank put-back FAILED: FC on PID bank %u, rates bank %u, switch had %u/%u - move the switch before flying",
                 banks.fcPid == 0xFF ? 0 : banks.fcPid + 1, banks.fcRate == 0xFF ? 0 : banks.fcRate + 1,
                 banks.switchPid + 1, banks.switchRate + 1);
        events.add(m);
    }
    if (bootWrong) { banks.savedPid = banks.switchPid; banks.savedRate = banks.switchRate; }
    bankRelease();
}

//*********************************************************************
//  Periodic probe — call from loop(), runs at low rate
//*********************************************************************
// While the FC is undetected, send MSP_FC_VARIANT + MSP_FC_VERSION +
// MSP_API_VERSION every PROBE_INTERVAL_MS. Once detected, slow down to a
// heartbeat that confirms the FC is still alive. If responses stop for
// PROBE_TIMEOUT_MS we mark detected=false again.

constexpr uint32_t PROBE_INTERVAL_MS    = 1000;   // while seeking
constexpr uint32_t PROBE_HEARTBEAT_MS   = 5000;   // once detected
constexpr uint32_t PROBE_TIMEOUT_MS     = 10000;  // declare FC lost after this
constexpr uint32_t PROBE_HOLDOFF_MS     = 1200;   // no probe this soon after a page/app reply
constexpr uint32_t TELEM_WATCH_MS       = 30000;  // re-read the telemetry setup (MSP 73) this often while idle

// Dongle mode: MSP_STATUS once a second so `armed` is never more than a
// beat stale - the radios go off when the model arms and come back after
// it disarms, exactly as auto fly mode does from the receiver's own channel.
inline void dongleStatusTick() {
    if (UsbHostMsp::cliMode) return;                    // the command line owns the port
    static uint32_t lastMs = 0;
    if (!dongleEnabled || !fcInfo.detected) return;
    if ((uint32_t)(millis() - lastMs) < 250) return;      // 4 Hz: a 30-byte reply, and the arming window shrinks to ~1 s (2026-09-16)
    if (txParamBusy || mspWaitFunction != 0xFF || mspProbeOutstanding()) return;
    lastMs = millis();
    mspSendRequest(MSP_STATUS);
    mspProbeSentMs = millis();
}

inline void mspFcPoll() {
    if (UsbHostMsp::cliMode) return;                    // command line open over USB: no MSP until save/exit (0.9.617)
    if (!fcTelemetryEnabled && !UsbHostMsp::active())
        return; // user says there is no FC on this line — don't probe (unless one is on the USB socket, 0.9.639)
    // Only meaningful in CRSF mode (D6 is wired as CRSF UART to FC) - or over USB.
    if (currentProtocol != PROTO_CRSF && !UsbHostMsp::active()) return;
    // Don't fight the bridge — if a Configurator client is talking to the FC
    // we'd just confuse both sides.
    if (mspBridgeActive) return;
    // Yield while the TX-parameter state machine has an MSP request in flight,
    // so we don't leave two outstanding requests for the FC to interleave.
    if (txParamBusy) return;
    if (bbCheckActive) return;                          // the vibration check owns the link (0.9.661)
    // Don't fight a synchronous /api/msp request that's mid-wait — sending
    // a competing probe causes the FC to interleave two responses, often
    // making the sync request time out and the page see "Read failed".
    if (mspWaitFunction != 0xFF) return;
    // ...nor just AFTER one (0.9.562). Rotorflight only looks at its MSP
    // request buffer when its telemetry rate bucket is back to zero — up to
    // 0.8 s after the last reply chunk — and if it finds TWO requests there
    // it answers the first and throws the second away (telemetry/crsf.c
    // handleCrsfMspFrameBuffer: mspRequestDataLength = 0 once a reply is
    // queued). A heartbeat probe fired in the gap between two page or app
    // reads always landed first, so the read behind it simply vanished:
    // "flight controller did not respond" on 1 in 14 back-to-back fn-120
    // reads on the Goblin (2026-09-04), and the "spurious" 504s on every
    // multi-read Rotorflight page before that. The reads prove the FC is
    // alive, so a probe this soon after a reply has nothing to learn.
    // Dongle (0.9.599): no hold-off. The FC is on its own UART, every request
    // gets its own reply in order, and the ring already allows one request at
    // a time - while a phone that connects the moment the board is plugged
    // in used to starve the identity probe forever: no Rotorflight button on
    // the home page and, worse, no MSP_STATUS polling, so arming was never
    // seen ("Dongle 3 and 4 show no Rotorflight option", Malcolm 2026-09-10).
    if (!dongleEnabled && !UsbHostMsp::active() && mspLastForegroundMs != 0 && (uint32_t)(millis() - mspLastForegroundMs) < PROBE_HOLDOFF_MS) return;   // USB: every request gets its own reply, no hold-off (0.9.639)
    // Don't probe the FC while a live RC link is streaming frames to it. Our
    // MSP-over-CRSF request is a second MSP master on the FC's wire; if a
    // Configurator is also polling the FC (its Receiver tab reads RC over MSP),
    // the two collide and the Configurator periodically reads a garbled/empty
    // frame — every channel flashes to zero on its display (the real RC output
    // is unaffected). It also competes for Serial1 bandwidth. So suppress
    // probing whenever flying — including dev mode (DEV_KEEP_WIFI). The FC
    // version is discovered when not flying, which is when the page wants it.
    // Normally we don't probe while a live RC link is streaming (collision with a
    // Configurator's Receiver-tab polling + Serial1 bandwidth). BUT if we booted
    // with the TX already on (a flight), we'd otherwise NEVER learn the FC's
    // variant/version/API — and the governor page needs the API (>=12.9). There's
    // no Configurator in the air (WiFi is off), and mspSendRequest is non-blocking
    // (it never stalls the RC output loop), so it's safe to get the FC identity
    // ONCE even while flying, then latch and stay quiet for the rest of the flight.
    // The API value persists (not cleared on the FC-lost timeout), so governor
    // stays available after landing.
    // 0.9.551: the identity now includes what the governor watch needs —
    // the FC's throttle channel (MSP_RX_MAP) and governor mode (MSP 142),
    // Rotorflight only. Capped tries, so an FC that stays silent on either
    // can't hold the latch open for a whole flight.
    static bool fcIdLatched = false;
    const bool isRf = strncmp(fcInfo.variant, "RTFL", 4) == 0;
    const bool wantRxMap = isRf && fcInfo.throttleCh == 0 && fcInfo.rxMapTries < 6;
    const bool wantGov   = isRf && fcInfo.govMode == 0xFF && fcInfo.govTries < 6;
    // 0.9.556: the telemetry setup too (MSP 73) — an emptied sensor list
    // is the one FC fault that looks exactly like a dead ESC or a broken
    // wire from the transmitter's side.
    const bool wantTelem = isRf && !fcInfo.telemCfgKnown && fcInfo.telemCfgTries < 6;
    if (fcInfo.versionKnown && fcInfo.apiMajor != 0 && !wantRxMap && !wantGov && !wantTelem) fcIdLatched = true;
    bool flying = (rx.lastMillis != 0) && ((uint32_t)(millis() - rx.lastMillis) < 500);
    if (flying && fcIdLatched) return;

    uint32_t now = millis();
    // Fast (1 s) until we have the full FC identity, then slow heartbeat. Using
    // fcIdLatched (variant+version+API) not just `detected` means the version and
    // API probes aren't slowed to 5 s right after the variant arrives.
    uint32_t interval = fcIdLatched ? PROBE_HEARTBEAT_MS : PROBE_INTERVAL_MS;
    if ((uint32_t)(now - fcInfo.lastProbeMs) < interval) return;
    // A paused probe (flying, bridge client, TX params) is not a silent FC:
    // after a pause longer than the timeout, the FC gets a fresh 10 s to
    // answer the probes actually sent — otherwise every landing logged a
    // false "FC lost" (seen 0.9.551, ~6 s after the radios came back).
    static uint32_t probeResumedMs = 0;
    if (fcInfo.lastProbeMs != 0 && (uint32_t)(now - fcInfo.lastProbeMs) > PROBE_TIMEOUT_MS)
        probeResumedMs = now;
    fcInfo.lastProbeMs = now;

    // Cycle through the three requests on successive probes so we eventually
    // get all three pieces of info even if some responses are dropped.
    // Rotorflight has never answered MSP_BATTERY_STATE on our FCs (cells
    // stays 0) — stop asking after a few silent tries rather than knock on
    // a door that never opens (2026-08-07, while chasing the field
    // telemetry dropout).
    static uint8_t batteryTries = 0;
    const bool askBattery = (fcInfo.cells == 0 && batteryTries < 6) || fcInfo.cells > 0;
    static uint8_t which = 0;
    // 0.9.563 — the telemetry setup takes the slot whenever it is due: the
    // repair write (cached good image back into FC RAM), a re-read right
    // after a write or restart, or the 30-s watch (one 52-byte reply — a
    // zeroed copy is found within a minute instead of at the next flight).
    // Never in the air: the flying latch above returns before this.
    const bool telemUrgent = isRf && (!fcInfo.telemCfgKnown || fcInfo.telemRecheck) && fcInfo.telemCfgTries < 6;
    const bool telemWatch  = isRf && fcInfo.telemCfgKnown && (uint32_t)(now - fcInfo.telemAskedMs) > TELEM_WATCH_MS;
    // Never on a DONGLE: the telemetry list is the RECEIVER's link, and a
    // dongle's "good copy" may be from a different helicopter entirely
    // (2026-09-16 review: two loan dongles going to a stranger's models).
    if (isRf && !dongleEnabled && fcInfo.telemRepairDue && fcInfo.telemGoodValid && currentProtocol == PROTO_CRSF) {   // the repair is for the CRSF-link corruption only (0.9.642)
        mspSendRequest(MSP_SET_TELEMETRY_CONFIG, fcInfo.telemGood, 52);
        fcInfo.telemRepairDue = false;
        fcInfo.telemRepairs++;
        fcInfo.telemRecheck = true;      // confirm at the next slot
        char m[EventLog::MSG_LEN];
        snprintf(m, sizeof(m), "Telemetry setup: good copy (%u/%u) written back to FC RAM, re-reading",
                 (unsigned)(fcInfo.telemGood[8] | (fcInfo.telemGood[9] << 8)),
                 (unsigned)(fcInfo.telemGood[10] | (fcInfo.telemGood[11] << 8)));
        events.add(m);
    } else if (telemUrgent || telemWatch) {
        mspSendRequest(MSP_TELEMETRY_CONFIG);
        fcInfo.telemAskedMs = now;
        if (telemUrgent) fcInfo.telemCfgTries++;
    } else switch (which++ % 7) {
        case 0: mspSendRequest(MSP_FC_VARIANT);   break;
        case 1: mspSendRequest(MSP_FC_VERSION);   break;
        case 2: mspSendRequest(MSP_API_VERSION);  break;
        case 3:
            if (askBattery) { mspSendRequest(MSP_BATTERY_STATE); if (fcInfo.cells == 0) batteryTries++; }
            else            { mspSendRequest(MSP_FC_VARIANT); }
            break;
        // Governor watch inputs (0.9.551) — asked until answered, then never
        // again (a page reading them via /api/msp keeps them fresh).
        case 4:
            if (wantRxMap) { mspSendRequest(MSP_RX_MAP); fcInfo.rxMapTries++; }
            else           { mspSendRequest(MSP_FC_VERSION); }
            break;
        case 5:
            if (wantGov)   { mspSendRequest(MSP_GOVERNOR_CONFIG); fcInfo.govTries++; }
            else           { mspSendRequest(MSP_API_VERSION); }
            break;
        case 6: mspSendRequest(MSP_FC_VARIANT);   break;
    }
    fcInfo.probesSent++;
    mspProbeSentMs = now;                // outstanding until the FC answers (any reply)

    // Detect timeout — if we were detected but responses have stopped
    // (counting from the probe resume, if that is more recent than the reply).
    uint32_t silentSince = fcInfo.lastResponseMs;
    if ((int32_t)(probeResumedMs - silentSince) > 0) silentSince = probeResumedMs;
    if (fcInfo.detected && fcInfo.lastResponseMs != 0 &&
        (uint32_t)(now - silentSince) > PROBE_TIMEOUT_MS) {
        fcInfo.detected     = false;
        fcInfo.versionKnown = false;
        events.add("FC lost — no MSP response in 10s");
    }
}

//*********************************************************************
//  Scorpion boot catcher — one-shot, armed by the ESC settings page
//*********************************************************************
// A Tribunus answers settings requests only for ~10 s after ITS power-on,
// then streams telemetry and goes deaf. Rotorflight reads the settings at
// FC-time 4 s but only publishes them (MSP 217) if it sees MSP activity
// within ~4 s of that read — a phone re-joining WiFi after the battery pull
// usually misses that window. So the page arms this flag, the user pulls
// the battery, and the receiver itself polls 217 from t≈2.5 s to t≈14 s.
// Never runs un-armed: a 217 poll aborts the ESC's telemetry mode.
// (escCatchArmed / escCatchGot are declared with the sync-wait state above.)

inline void escCatchTick() {
    if (bbCheckActive) return;   // the vibration check owns the link (0.9.662)
    if (!escCatchArmed) return;
    const uint32_t now = millis();
    if (currentProtocol != PROTO_CRSF) { escCatchArmed = false; return; }
    // A transmitter on at boot means the user is at the field, not at the
    // phone — a stale flag must never freeze the ESC's telemetry for a
    // flight. Wait for the boot window's verdict before the first poll.
    if (netMode == NET_WAITING_RF || netMode == NET_INIT) return;
    if (rx.packets > 0 || netMode == NET_NO_WIFI) {
        escCatchArmed = false;
        escCatchResult = "tx";
        events.add("ESC catcher: TX heard — cancelled");
        return;
    }
    if (now < 2500) return;
    if (escCatchGot || now > 14000) {
        escCatchArmed = false;
        escCatchResult = escCatchGot ? "captured" : "nothing";
        events.add(escCatchGot ? "ESC catcher: settings captured by the FC"
                               : "ESC catcher: FC never published ESC settings");
        return;
    }
    if (mspBridgeActive || txParamBusy || mspWaitFunction != 0xFF || mspProbeOutstanding()) return;
    static uint32_t last = 0;
    if ((uint32_t)(now - last) < 250) return;
    last = now;
    mspSendRequest(MSP_ESC_PARAMETERS);
    mspProbeSentMs = now;
}

//*********************************************************************
//  FC-telemetry watchdog (Malcolm 2026-08-07: "couldn't see voltage at
//  the end" at the field, cause unknown — give the dropout a voice).
//  Logs WHEN the CRSF telemetry stream stops and when it resumes, with
//  durations, so the event log pinpoints it relative to the landing.
//*********************************************************************

inline void fcTelemWatch() {
    if (bbCheckActive) return;   // the vibration check owns the link (0.9.662)
    static bool wasLive = false;
    static uint32_t stopLoggedAt = 0;
    const bool live = fcTelem.lastFrameMs &&
                      (uint32_t)(millis() - fcTelem.lastFrameMs) < 5000;
    if (wasLive && !live) {
        char b[72];
        snprintf(b, sizeof(b), "FC telemetry STOPPED (no frame for 5 s, proto=%s)",
                 protocolName(currentProtocol));
        events.add(b);
        stopLoggedAt = millis();
    } else if (!wasLive && live && stopLoggedAt) {
        char b[64];
        snprintf(b, sizeof(b), "FC telemetry resumed after %lu s",
                 (unsigned long)((millis() - stopLoggedAt) / 1000));
        events.add(b);
        stopLoggedAt = 0;
    }
    wasLive = live;
}

//*********************************************************************
//  Convenience: is this a Rotorflight 2.2+ FC?
//*********************************************************************

// Map MSP API version → Rotorflight major.minor. Rotorflight 2.x rides on the
// Betaflight 4.x MSP API 12.x: API 12.6 = RF 2.0, 12.7 = 2.1, 12.8 = 2.2,
// 12.9 = 2.3  (RF minor = apiMinor - 6, major = 2). Confirmed against live FCs:
// API 12.8 / fw 4.5.1 = RF 2.2, API 12.9 / fw 4.6.0 = RF 2.3. (This previously
// mis-mapped 12.8 to "1.x", which hid every Rotorflight option on a 2.2 FC.)
// Gate at API >= 12.8 (RF 2.2), matching V1's api100 >= 1208 — that's the
// minimum our config pages are built for. 12.8 -> RF 2.2, 12.9 -> RF 2.3, etc.
inline uint8_t rotorflightMajor() {
    if (fcInfo.apiMajor == 12 && fcInfo.apiMinor >= 8) return 2;
    return 0;
}
inline uint8_t rotorflightMinor() {
    if (fcInfo.apiMajor == 12 && fcInfo.apiMinor >= 8) return (uint8_t)(fcInfo.apiMinor - 6);
    return 0;
}

// Version code the way the V1 TX expects it in ack slot 31 (its RotorFlight_V):
//   0 = not Rotorflight,  1 = RF 2.2 (API 12.8),  2 = RF 2.3+ (API 12.9+).
// The TX picks its rate-display factor table from this (>=2 => RF 2.3 factors),
// so sending a plain "1" forced the 2.2 factors and mis-scaled the 2.3 rates.
// Mirrors V1's Rotorflight_Version (api100 1208 -> 1, >=1209 -> 2).
inline uint8_t rotorflightTxVersion() {
    if (fcInfo.apiMajor == 12 && fcInfo.apiMinor >= 9) return 2;   // RF 2.3+
    if (fcInfo.apiMajor == 12 && fcInfo.apiMinor == 8) return 1;   // RF 2.2
    return 0;
}

// Once Rotorflight has been seen this boot, it STAYS seen (Malcolm
// 2026-08-25: "the app sometimes does not give me access to the Rotorflight
// options at all — it seems to forget they are there"). Detection naturally
// flickers — the probe answers late, telemetry pauses — and no consumer of
// this flag (front-screen button, auto-fly forcing) may flap with it. An FC
// does not un-become Rotorflight without a reboot.
inline bool rfSeenThisBoot = false;
inline bool fcIsRotorflightConfigCapable() {
    if (rfSeenThisBoot) return true;
    // Strict check: only if MSP probe confirmed Rotorflight 2.2+.
    if (fcInfo.detected && fcInfo.versionKnown &&
        strncmp(fcInfo.variant, "RTFL", 4) == 0 &&
        rotorflightMajor() >= 2) {
        rfSeenThisBoot = true;
        return true;
    }
    // Fallback: in CRSF mode, if telemetry is actively flowing from the FC,
    // assume the user knows what they're connected to and surface the button.
    // (MSP-over-CRSF probe isn't reliable across all FC configurations.)
    if (currentProtocol == PROTO_CRSF &&
        fcTelem.framesParsed > 5 &&
        fcTelem.lastFrameMs != 0 &&
        (uint32_t)(millis() - fcTelem.lastFrameMs) < 2000) {
        rfSeenThisBoot = true;
        return true;
    }
    return false;
}

#endif // _SRC_MSPFC_H
