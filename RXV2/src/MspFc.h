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
#include "Output.h"      // crsfCrc8()

//*********************************************************************
//  MSP function codes we care about
//*********************************************************************

constexpr uint8_t MSP_API_VERSION    = 1;     // 3 bytes: protoVer, apiMajor, apiMinor
constexpr uint8_t MSP_FC_VARIANT     = 2;     // 4 ASCII bytes (e.g. "RTFL")
constexpr uint8_t MSP_FC_VERSION     = 3;     // 3 bytes: major, minor, patch

// Rotorflight tuning commands (codes from v1's Nexus.h)
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
constexpr uint8_t MSP_SET_FEATURE_CFG = 37;   // write the 32-bit feature mask
constexpr uint8_t MSP_EEPROM_WRITE   = 250;
constexpr uint8_t MSP_REBOOT         = 68;    // FC restart (governor config write needs it to apply, like V1)

//*********************************************************************
//  Sync-wait state for mspRequestAndWait()
//*********************************************************************

inline volatile uint8_t  mspWaitFunction = 0xFF;     // 0xFF = nothing pending
inline uint8_t           mspWaitRespBuf[640] = {0};   // jumbo-capable (MSP_ADJUSTMENT_RANGES = 588 B)
inline volatile uint16_t mspWaitRespLen = 0;
inline volatile bool     mspWaitRespReady = false;

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

inline void mspSendRequest(uint8_t function, const uint8_t* payload = nullptr, uint8_t payloadLen = 0) {
    // MSP v1 body inside CRSF is just: size(1) function(1) payload(N).
    // The inner XOR checksum is NOT transmitted — CRSF's CRC8 protects it.
    uint8_t mspBody[64];
    if (payloadLen > sizeof(mspBody) - 2) return;
    mspBody[0] = payloadLen;
    mspBody[1] = function;
    for (uint8_t i = 0; i < payloadLen; ++i) mspBody[2 + i] = payload[i];
    uint8_t mspBodyLen = 2 + payloadLen;

    // CRSF wrapper. Status byte 0x30 = SoF (bit 4) + MSP version 1 (bits 6-5 = 01).
    // length covers: type + dest + src + status + mspBody + crc.
    uint8_t crsf[80];
    crsf[0] = CRSF_ADDR_FC;                  // sync
    crsf[1] = 4 + mspBodyLen + 1;            // length byte
    crsf[2] = CRSF_TYPE_MSP_REQ;
    crsf[3] = CRSF_ADDR_FC;                  // dest = FC
    crsf[4] = CRSF_ADDR_HANDSET;             // src  = handset (us)
    crsf[5] = 0x30;                          // status: SoF + version v1
    memcpy(&crsf[6], mspBody, mspBodyLen);
    uint8_t crsfTotal = 6 + mspBodyLen;      // up to and including last MSP byte
    crsf[crsfTotal] = crsfCrc8(&crsf[2], (uint8_t)(crsfTotal - 2));
    Serial1.write(crsf, (size_t)(crsfTotal + 1));
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

inline void mspParseResponse(const uint8_t* body, uint8_t bodyLen) {
    if (bodyLen < 3 + 1) return;                     // dest+src+status + at least 1 MSP byte
    // body[0] = dest, body[1] = src, body[2] = status
    const uint8_t status = body[2];
    const uint8_t* msp = &body[3];
    uint8_t mspLen = (uint8_t)(bodyLen - 3);

    fcInfo.lastResponseMs = millis();                // even an error reply proves the FC is alive

    // Status byte bit 7 = MSP ERROR. Never capture an error frame as a valid
    // response: its size is 0, and treating it as data used to hand empty
    // buffers to the waiters — the TX-param write machine would then send a
    // zero-length SET followed by EEPROM_WRITE. Let waiters time out + retry.
    if (status & 0x80) return;

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
    if (reGot >= reExpected) {
        reActive = false;
        mspDeliverResponse(reFunc, reBuf, reExpected);
    }
    return;
}

inline void mspDeliverResponse(uint8_t func, const uint8_t* payload, uint16_t size) {

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
            if (size >= 1 && payload[0] > 0 && payload[0] <= 14)
                fcInfo.cells = payload[0];
            break;
        default:
            break;
    }
}

//*********************************************************************
//  Synchronous MSP request: send and wait for response
//*********************************************************************
// Used by HTTP request handlers to talk to the FC. Blocks for up to
// timeoutMs while pumping Serial1 → CRSF parser → mspParseResponse, which
// will set mspWaitRespReady=true if the matching function code comes back.

inline bool mspRequestAndWait(uint8_t function, const uint8_t* req, uint8_t reqLen,
                              uint8_t* outBuf, uint16_t* outLen, uint32_t timeoutMs) {
    extern void protocolRx();   // defined in Telemetry.h
    mspWaitFunction  = function;
    mspWaitRespReady = false;
    mspWaitRespLen   = 0;
    mspSendRequest(function, req, reqLen);
    uint32_t deadline = millis() + timeoutMs;
    while (!mspWaitRespReady && (int32_t)(deadline - millis()) > 0) {
        protocolRx();
        delay(1);
    }
    bool ok = mspWaitRespReady;
    mspWaitFunction = 0xFF;
    if (ok) {
        if (outLen) *outLen = mspWaitRespLen;
        if (outBuf && mspWaitRespLen > 0) memcpy(outBuf, mspWaitRespBuf, mspWaitRespLen);
    }
    return ok;
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

inline void mspFcPoll() {
    if (!fcTelemetryEnabled)
        return; // user says there is no FC on this line — don't probe
    // Only meaningful in CRSF mode (D6 is wired as CRSF UART to FC).
    if (currentProtocol != PROTO_CRSF) return;
    // Don't fight the bridge — if a Configurator client is talking to the FC
    // we'd just confuse both sides.
    if (mspBridgeActive) return;
    // Yield while the TX-parameter state machine has an MSP request in flight,
    // so we don't leave two outstanding requests for the FC to interleave.
    if (txParamBusy) return;
    // Don't fight a synchronous /api/msp request that's mid-wait — sending
    // a competing probe causes the FC to interleave two responses, often
    // making the sync request time out and the page see "Read failed".
    if (mspWaitFunction != 0xFF) return;
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
    static bool fcIdLatched = false;
    if (fcInfo.versionKnown && fcInfo.apiMajor != 0) fcIdLatched = true;
    bool flying = (rx.lastMillis != 0) && ((uint32_t)(millis() - rx.lastMillis) < 500);
    if (flying && fcIdLatched) return;

    uint32_t now = millis();
    // Fast (1 s) until we have the full FC identity, then slow heartbeat. Using
    // fcIdLatched (variant+version+API) not just `detected` means the version and
    // API probes aren't slowed to 5 s right after the variant arrives.
    uint32_t interval = fcIdLatched ? PROBE_HEARTBEAT_MS : PROBE_INTERVAL_MS;
    if ((uint32_t)(now - fcInfo.lastProbeMs) < interval) return;
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
    switch (which++ % 4) {
        case 0: mspSendRequest(MSP_FC_VARIANT);   break;
        case 1: mspSendRequest(MSP_FC_VERSION);   break;
        case 2: mspSendRequest(MSP_API_VERSION);  break;
        case 3:
            if (askBattery) { mspSendRequest(MSP_BATTERY_STATE); if (fcInfo.cells == 0) batteryTries++; }
            else            { mspSendRequest(MSP_FC_VARIANT); }
            break;
    }
    fcInfo.probesSent++;

    // Detect timeout — if we were detected but responses have stopped.
    if (fcInfo.detected && fcInfo.lastResponseMs != 0 &&
        (uint32_t)(now - fcInfo.lastResponseMs) > PROBE_TIMEOUT_MS) {
        fcInfo.detected     = false;
        fcInfo.versionKnown = false;
        events.add("FC lost — no MSP response in 10s");
    }
}

//*********************************************************************
//  FC-telemetry watchdog (Malcolm 2026-08-07: "couldn't see voltage at
//  the end" at the field, cause unknown — give the dropout a voice).
//  Logs WHEN the CRSF telemetry stream stops and when it resumes, with
//  durations, so the event log pinpoints it relative to the landing.
//*********************************************************************

inline void fcTelemWatch() {
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
