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
constexpr uint8_t MSP_RX_MAP         = 64;    // Rotorflight channel map: byte i = RX channel (0-based) feeding FC function i, functions in A E R C T order → [4] = throttle
constexpr uint8_t MSP_SET_FEATURE_CFG = 37;   // write the 32-bit feature mask
constexpr uint8_t MSP_EEPROM_WRITE   = 250;
constexpr uint8_t MSP_REBOOT         = 68;    // FC restart (governor config write needs it to apply, like V1)
constexpr uint8_t MSP_ESC_PARAMETERS = 217;   // ESC settings blob (Scorpion/Hobbywing forward programming)
constexpr uint8_t MSP_TELEMETRY_CONFIG     = 73;   // RF 4.6: 12-byte header (inverted, halfDuplex, u32, pinSwap, mode, rate u16, ratio u16) + 40 sensor-ID slots
constexpr uint8_t MSP_SET_TELEMETRY_CONFIG = 74;   // same layout; sensors apply at the next FC boot

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

inline void mspSendRequest(uint8_t function, const uint8_t* payload = nullptr, uint8_t payloadLen = 0) {
    // MSP v1 body inside CRSF is just: size(1) function(1) payload(N).
    // The inner XOR checksum is NOT transmitted — CRSF's CRC8 protects it.
    // A body longer than one CRSF frame (57 bytes) goes as chunks the FC
    // reassembles (msp_shared.c): the first carries the start bit and the
    // full MSP header, each later one carries seq+1 and the next bytes.
    // Silently dropping long payloads here is what made the 84-byte
    // Scorpion ESC write (fn 218) vanish (2026-09-02).
    if (payloadLen == 0xFF) return;          // 0xFF size = MSP jumbo marker, never send it
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
        case MSP_ESC_PARAMETERS:
            if (size >= 2) escCatchGot = true;   // FC now holds the ESC's settings
            break;
        // Governor throttle watch inputs (0.9.551). These arrive from our own
        // probe AND from any page that reads them via /api/msp, so the values
        // track edits made on the phone. RAM only here — the probe may run
        // in the air (TX-on boot) and an NVS write is a flash stall, so the
        // watch tick commits them at the next quiet moment.
        case MSP_RX_MAP:
            if (size >= 5 && payload[4] < 16) {
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
                if (fcTelemCfgBad() && !wasBad) {
                    char m[128];
                    snprintf(m, sizeof(m), "Rotorflight telemetry setup EMPTY (%u sensors, link rate %u/%u) - "
                             "no volts/RPM. Restore it from the Rotorflight page", n, fcInfo.telemRate, fcInfo.telemRatio);
                    events.add(m);
                } else if (!fcTelemCfgBad() && wasBad) {
                    char m[80];
                    snprintf(m, sizeof(m), "Rotorflight telemetry setup OK again (%u sensors)", n);
                    events.add(m);
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
    if ((verdictDirty || fcInfoNvsDirty) && !armed) {
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
    extern void protocolRx();   // defined in Telemetry.h
    extern void sbusTick();     // defined in Output.h
    extern void radioPoll();    // defined in Radio.h
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
        radioPoll();
        sbusTick();
        protocolRx();
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
    if (mspLastForegroundMs != 0 && (uint32_t)(millis() - mspLastForegroundMs) < PROBE_HOLDOFF_MS) return;
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
    switch (which++ % 7) {
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
        case 6:
            if (wantTelem) { mspSendRequest(MSP_TELEMETRY_CONFIG); fcInfo.telemCfgTries++; }
            else           { mspSendRequest(MSP_FC_VARIANT); }
            break;
    }
    fcInfo.probesSent++;

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
    if (mspBridgeActive || txParamBusy || mspWaitFunction != 0xFF) return;
    static uint32_t last = 0;
    if ((uint32_t)(now - last) < 250) return;
    last = now;
    mspSendRequest(MSP_ESC_PARAMETERS);
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
