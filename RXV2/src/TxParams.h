// LockDownRadioControl — RXV2  ::  TxParams.h
//
// TX-side Rotorflight parameter editing (V1-compatible). Lets a V1 transmitter
// READ and SET Rotorflight rates/PIDs/governor over the nRF24 link — the same
// thing the iPhone web UI does over WiFi, but driven from the handset.
//
// Protocol (ported byte-exact from V1 ReceiverCode/utilities/Parameters.h +
// Nexus.h + radio.h):
//   * Every TX→RX packet with ChannelBitMask == 0 is a PARAMETER packet. After
//     the 2 mask bytes the payload decompresses (same 3:4 scheme as channels)
//     to [ID, word1..word11]. The ID selects an action:
//       - "send me block X now"  (word[1]==321, word[2]=duration ms)  → READ
//       - "here are new X bytes"  (values in word[1..])               → WRITE
//   * READ: while the read window is open we re-poll the FC over MSP and stream
//     the bytes back in the ack-payload (slots 25..30/32..34, selected by
//     `paramSend`). Re-polling continuously (V1 does ~every 50 ms) keeps the
//     cached bytes fresh, so a bank switch / a single lost MSP round-trip never
//     leaves the TX reading zeros.
//   * WRITE: we accumulate the batches, then read-modify-write to the FC over
//     MSP (preserving the fields the TX doesn't edit) + save to EEPROM.
//
// Everything here is NON-BLOCKING: MSP requests are sent with mspSendRequest()
// and their responses captured asynchronously (MspFc.h mspAsync*), advanced by
// txParamsLoop() across loop iterations — so a live TX link is never stalled.
//
//*********************************************************************

#ifndef _SRC_TXPARAMS_H
#define _SRC_TXPARAMS_H

#include "1Defs.h"
#include "Channels.h"   // decompress(), decompressedSize()
#include "MspFc.h"      // mspSendRequest(), MSP codes, mspAsync* capture, fcIsRotorflightConfigCapable()

//*********************************************************************
//  Parameter IDs (V1 1Definitions.h)
//*********************************************************************

enum ParamId : uint8_t {
    PID_SEND_PID            = 9,
    PID_PID_FIRST6          = 10,
    PID_PID_SECOND11        = 11,
    PID_SEND_RATES          = 12,
    PID_RATES_FIRST7        = 13,
    PID_RATES_SECOND6       = 14,
    PID_SEND_RATES_ADV      = 15,
    PID_RATES_ADV_SECOND8   = 16,
    PID_RATES_ADV_FIRST7    = 17,
    PID_SEND_PID_ADV        = 18,
    PID_PID_ADV_FIRST9      = 19,
    PID_PID_ADV_SECOND9     = 20,
    PID_PID_ADV_THIRD8      = 21,
    PID_SEND_GOV_PROFILE    = 27,
    PID_SEND_GOV_CONFIG     = 28,
    PID_GOV_WR_PROFILE1     = 29,
    PID_GOV_WR_PROFILE2     = 30,
    PID_GOV_WR_CONFIG1      = 31,
    PID_GOV_WR_CONFIG2      = 32,
    PID_GOV_WR_CONFIG3      = 33,
    PARAM_MAX_ID            = 34,
};

// Which block the ack-payload is currently streaming back to the TX (V1
// SendRotorFlightParametresNow). Cleared when the read window expires.
enum ParamSend : uint8_t {
    PSEND_NONE = 0, PSEND_PID = 1, PSEND_RATES = 2, PSEND_RATES_ADV = 3,
    PSEND_PID_ADV = 4, PSEND_GOV_CONFIG = 5, PSEND_GOV_PROFILE = 6
};
inline ParamSend paramSend      = PSEND_NONE;
inline uint32_t  paramSendUntil = 0;

//*********************************************************************
//  Cached ack bytes
//*********************************************************************
// RATES (V1 order: per axis Centre, Max, Expo)
//   [0]type [1]RollC [2]RollMax [3]RollExpo [4]PitchC [5]PitchMax [6]PitchExpo
//   [7]YawC [8]YawMax [9]YawExpo [10]CollC [11]CollMax [12]CollExpo
inline uint8_t ratesAck[13]    = {0};
// ADVANCED RATES: [0..3] Response R,P,Y,C  [4..7] Boost gain R,P,Y,C
//   [8..11] Boost cutoff R,P,Y,C  [12] Yaw ceiling gain  [13] Yaw deadband gain  [14] Yaw deadband filter
inline uint8_t advRatesAck[15] = {0};
inline bool    ratesAckValid   = false;   // rates + advanced both come from one RC_TUNING read

// PIDs — 17 x 16-bit, V1 All_PIDs order:
//   [0..3] Roll P,I,D,FF  [4..7] Pitch P,I,D,FF  [8..11] Yaw P,I,D,FF
//   [12] Roll boost [13] Pitch boost [14] Yaw boost  [15] HSI offset Roll [16] HSI offset Pitch
inline uint16_t pidVals[17]    = {0};
inline bool     pidAckValid    = false;

//*********************************************************************
//  Staged write values from the TX
//*********************************************************************
// basic rates, [Centre, Max, Expo] per axis
inline uint8_t wRatesType = 0;
inline uint8_t wRoll[3]  = {0};
inline uint8_t wPitch[3] = {0};
inline uint8_t wYaw[3]   = {0};
inline uint8_t wColl[3]  = {0};
// advanced rates
inline uint8_t wResp[4]        = {0};   // response time R,P,Y,C
inline uint8_t wBoostGain[4]   = {0};   // setpoint-boost gain R,P,Y,C
inline uint8_t wBoostCutoff[4] = {0};   // setpoint-boost cutoff R,P,Y,C
inline uint8_t wYawDyn[3]      = {0};   // ceiling gain, deadband gain, deadband filter
// PIDs (16-bit, All_PIDs order)
inline uint16_t wPid[17]       = {0};

// write requests raised by the packet parser, serviced by txParamsLoop()
inline bool ratesWriteReq    = false;   // basic rates only (ID 14, word[7]==0)
inline bool ratesAdvWriteReq = false;   // basic + advanced together (ID 16)
inline bool pidWriteReq      = false;   // PIDs (ID 11)

//*********************************************************************
//  Async MSP state machine
//*********************************************************************
enum ParamMspState : uint8_t { PM_IDLE, PM_READ, PM_WRITE_ORIG, PM_WRITE_EEPROM };
enum WriteKind     : uint8_t { WK_NONE, WK_RATES, WK_RATES_ADV, WK_PID };

inline ParamMspState pmState     = PM_IDLE;
inline WriteKind     pmWriteKind = WK_NONE;
inline uint32_t      pmStateAt   = 0;
inline uint8_t       pmScratch[64] = {0};
inline uint16_t      pmScratchLen  = 0;
inline uint32_t      lastParamFetchMs = 0;     // last read re-poll (continuous refresh)

inline bool txParamMspFree() {
    return currentProtocol == PROTO_CRSF && !mspBridgeActive && mspWaitFunction == 0xFF;
}

// MSP "get" function for the active read window.
inline uint8_t readGetFn() {
    return (paramSend == PSEND_PID) ? MSP_PID : MSP_RC_TUNING;
}

//*********************************************************************
//  Build cached ack bytes from raw MSP responses
//*********************************************************************
// MSP RC_TUNING per-axis order: Centre(rcRate), Expo(rcExpo), Max(srate),
// Response, Accel(2). Advanced boost tail is INTERLEAVED per axis.
inline void buildRatesFromMsp(const uint8_t* p, uint16_t len) {
    if (len < 25) return;
    ratesAck[0]  = p[0];
    ratesAck[1]  = p[1];  ratesAck[2]  = p[3];  ratesAck[3]  = p[2];   // Roll  C,Max,Expo
    ratesAck[4]  = p[7];  ratesAck[5]  = p[9];  ratesAck[6]  = p[8];   // Pitch
    ratesAck[7]  = p[13]; ratesAck[8]  = p[15]; ratesAck[9]  = p[14];  // Yaw
    ratesAck[10] = p[19]; ratesAck[11] = p[21]; ratesAck[12] = p[20];  // Collective
    if (len >= 36) {
        advRatesAck[0]  = p[4];  advRatesAck[1]  = p[10]; advRatesAck[2]  = p[16]; advRatesAck[3]  = p[22];
        advRatesAck[4]  = p[25]; advRatesAck[5]  = p[27]; advRatesAck[6]  = p[29]; advRatesAck[7]  = p[31]; // gains R,P,Y,C
        advRatesAck[8]  = p[26]; advRatesAck[9]  = p[28]; advRatesAck[10] = p[30]; advRatesAck[11] = p[32]; // cutoffs R,P,Y,C
        advRatesAck[12] = p[33]; advRatesAck[13] = p[34]; advRatesAck[14] = p[35];
    }
    ratesAckValid = true;
}

// MSP_PID: 17 little-endian uint16 (lo,hi), index*2.
inline void buildPidsFromMsp(const uint8_t* p, uint16_t len) {
    if (len < 34) return;
    for (uint8_t i = 0; i < 17; ++i)
        pidVals[i] = (uint16_t)p[i * 2] | ((uint16_t)p[i * 2 + 1] << 8);
    pidAckValid = true;
}

// pack two uint16 into ack[1..4] (lo,hi,lo,hi) — V1 Send_2_x_uint16_t
inline void ackPair(uint8_t* ack, uint16_t a, uint16_t b) {
    ack[1] = (uint8_t)(a & 0xFF); ack[2] = (uint8_t)(a >> 8);
    ack[3] = (uint8_t)(b & 0xFF); ack[4] = (uint8_t)(b >> 8);
}

//*********************************************************************
//  Incoming parameter packet parser  (V1 ReadExtraParameters)
//*********************************************************************
inline void readExtraParameters(const uint8_t* payload, uint8_t size) {
    if (size <= 2) return;
    uint16_t compressed[16] = {0};
    uint8_t  nData = size - 2;
    for (uint8_t i = 0; i + 1 < nData; i += 2)
        compressed[i / 2] = (uint16_t)payload[2 + i] | ((uint16_t)payload[2 + i + 1] << 8);
    uint16_t w[24] = {0};                       // w[0]=ID, w[1..11]=words
    decompress(w, compressed, decompressedSize(size));
    const uint16_t id = w[0];
    if (id < 1 || id > PARAM_MAX_ID) return;
    if (!fcIsRotorflightConfigCapable()) return;

    switch (id) {
        // ---- reads: "send block now" (word[1]==321, word[2]=duration ms) ----
        case PID_SEND_RATES:
            if (w[1] == 321) { paramSend = PSEND_RATES;     paramSendUntil = millis() + w[2]; lastParamFetchMs = 0; }
            break;
        case PID_SEND_RATES_ADV:
            if (w[1] == 321) { paramSend = PSEND_RATES_ADV; paramSendUntil = millis() + w[2]; lastParamFetchMs = 0; }
            break;
        case PID_SEND_PID:
            if (w[1] == 321) { paramSend = PSEND_PID;       paramSendUntil = millis() + w[2]; lastParamFetchMs = 0; }
            break;

        // ---- RATES write ----
        case PID_RATES_FIRST7:                  // 13 — type + Roll + Pitch (C,Max,Expo)
            wRatesType = (uint8_t)w[1];
            wRoll[0]  = (uint8_t)w[2]; wRoll[1]  = (uint8_t)w[3]; wRoll[2]  = (uint8_t)w[4];
            wPitch[0] = (uint8_t)w[5]; wPitch[1] = (uint8_t)w[6]; wPitch[2] = (uint8_t)w[7];
            break;
        case PID_RATES_SECOND6:                 // 14 — Yaw + Collective; word[7]==0 => basic write now
            wYaw[0]  = (uint8_t)w[1]; wYaw[1]  = (uint8_t)w[2]; wYaw[2]  = (uint8_t)w[3];
            wColl[0] = (uint8_t)w[4]; wColl[1] = (uint8_t)w[5]; wColl[2] = (uint8_t)w[6];
            if (!w[7]) ratesWriteReq = true;
            break;

        // ---- ADVANCED RATES write: FIRST_7=ID17, SECOND_8=ID16 (16 triggers combined write) ----
        case PID_RATES_ADV_FIRST7:              // 17
            wResp[0] = (uint8_t)w[1]; wResp[1] = (uint8_t)w[2]; wResp[2] = (uint8_t)w[3]; wResp[3] = (uint8_t)w[4];
            wBoostGain[0] = (uint8_t)w[5]; wBoostGain[1] = (uint8_t)w[6]; wBoostGain[2] = (uint8_t)w[7];
            break;
        case PID_RATES_ADV_SECOND8:             // 16
            wBoostGain[3]   = (uint8_t)w[1];
            wBoostCutoff[0] = (uint8_t)w[2]; wBoostCutoff[1] = (uint8_t)w[3];
            wBoostCutoff[2] = (uint8_t)w[4]; wBoostCutoff[3] = (uint8_t)w[5];
            wYawDyn[0] = (uint8_t)w[6]; wYawDyn[1] = (uint8_t)w[7]; wYawDyn[2] = (uint8_t)w[8];
            ratesAdvWriteReq = true;
            break;

        // ---- PID write: FIRST_6=ID10, SECOND_11=ID11 (11 triggers write). 16-bit values. ----
        case PID_PID_FIRST6:                    // 10 — All_PIDs[0..5]
            for (uint8_t i = 0; i < 6; ++i) wPid[i] = w[i + 1];
            break;
        case PID_PID_SECOND11:                  // 11 — All_PIDs[6..16], then write
            for (uint8_t i = 0; i < 11; ++i) wPid[i + 6] = w[i + 1];
            pidWriteReq = true;
            break;

        default:
            break;                              // advanced PID / governor — added next
    }
}

//*********************************************************************
//  Apply staged write values into the read-modify-write scratch buffer
//*********************************************************************
inline void applyWriteToScratch() {
    if (pmWriteKind == WK_RATES || pmWriteKind == WK_RATES_ADV) {
        if (pmScratchLen < 25) return;
        pmScratch[0]  = wRatesType;             // MSP order Centre, Expo, Max
        pmScratch[1]  = wRoll[0];  pmScratch[2]  = wRoll[2];  pmScratch[3]  = wRoll[1];
        pmScratch[7]  = wPitch[0]; pmScratch[8]  = wPitch[2]; pmScratch[9]  = wPitch[1];
        pmScratch[13] = wYaw[0];   pmScratch[14] = wYaw[2];   pmScratch[15] = wYaw[1];
        pmScratch[19] = wColl[0];  pmScratch[20] = wColl[2];  pmScratch[21] = wColl[1];
        if (pmWriteKind == WK_RATES_ADV && pmScratchLen >= 36) {
            pmScratch[4]  = wResp[0]; pmScratch[10] = wResp[1]; pmScratch[16] = wResp[2]; pmScratch[22] = wResp[3];
            pmScratch[25] = wBoostGain[0]; pmScratch[26] = wBoostCutoff[0];   // Roll  (interleaved gain,cutoff)
            pmScratch[27] = wBoostGain[1]; pmScratch[28] = wBoostCutoff[1];   // Pitch
            pmScratch[29] = wBoostGain[2]; pmScratch[30] = wBoostCutoff[2];   // Yaw
            pmScratch[31] = wBoostGain[3]; pmScratch[32] = wBoostCutoff[3];   // Collective
            pmScratch[33] = wYawDyn[0];    pmScratch[34] = wYawDyn[1];    pmScratch[35] = wYawDyn[2];
        }
    } else if (pmWriteKind == WK_PID) {
        if (pmScratchLen < 34) return;
        for (uint8_t i = 0; i < 17; ++i) {
            pmScratch[i * 2]     = (uint8_t)(wPid[i] & 0xFF);
            pmScratch[i * 2 + 1] = (uint8_t)(wPid[i] >> 8);
        }
    }
}

inline uint8_t writeSetFn() { return (pmWriteKind == WK_PID) ? MSP_SET_PID : MSP_SET_RC_TUNING; }
inline uint8_t writeGetFn() { return (pmWriteKind == WK_PID) ? MSP_PID     : MSP_RC_TUNING; }

//*********************************************************************
//  Loop-driven async MSP state machine  (V1 CheckMSPSerial, non-blocking)
//*********************************************************************
inline void txParamsLoop() {
    if (currentProtocol != PROTO_CRSF) return;
    const uint32_t now = millis();

    if (paramSend != PSEND_NONE && (int32_t)(now - paramSendUntil) > 0) paramSend = PSEND_NONE;

    switch (pmState) {
        case PM_IDLE: {
            WriteKind wk = ratesAdvWriteReq ? WK_RATES_ADV
                         : ratesWriteReq    ? WK_RATES
                         : pidWriteReq      ? WK_PID : WK_NONE;
            if (wk != WK_NONE && txParamMspFree()) {
                ratesAdvWriteReq = ratesWriteReq = pidWriteReq = false;
                pmWriteKind = wk;
                uint8_t fn = writeGetFn();
                mspAsyncFunc = fn; mspAsyncReady = false;
                mspSendRequest(fn);                       // read-modify-write: get current first
                pmState = PM_WRITE_ORIG; pmStateAt = now; txParamBusy = true;
            } else if (paramSend != PSEND_NONE && txParamMspFree() &&
                       (int32_t)(now - lastParamFetchMs) >= 80) {   // continuous re-poll (V1 ~50ms)
                lastParamFetchMs = now;
                uint8_t fn = readGetFn();
                mspAsyncFunc = fn; mspAsyncReady = false;
                mspSendRequest(fn);
                pmState = PM_READ; pmStateAt = now; txParamBusy = true;
            }
            break;
        }

        case PM_READ:
            if (mspAsyncReady) {
                if      (mspAsyncFunc == MSP_RC_TUNING) buildRatesFromMsp(mspAsyncBuf, mspAsyncLen);
                else if (mspAsyncFunc == MSP_PID)       buildPidsFromMsp(mspAsyncBuf, mspAsyncLen);
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            } else if ((int32_t)(now - pmStateAt) > 400) {
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            }
            break;

        case PM_WRITE_ORIG:
            if (mspAsyncReady) {
                pmScratchLen = mspAsyncLen;
                if (pmScratchLen > sizeof(pmScratch)) pmScratchLen = sizeof(pmScratch);
                memcpy(pmScratch, mspAsyncBuf, pmScratchLen);
                mspAsyncFunc = 0xFF;
                applyWriteToScratch();
                mspSendRequest(writeSetFn(), pmScratch, (uint8_t)pmScratchLen);
                pmState = PM_WRITE_EEPROM; pmStateAt = now;
            } else if ((int32_t)(now - pmStateAt) > 500) {
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            }
            break;

        case PM_WRITE_EEPROM:
            if ((int32_t)(now - pmStateAt) > 120) {
                mspSendRequest(MSP_EEPROM_WRITE);
                if (pmWriteKind == WK_PID) { events.add("TX edit: PIDs -> FC");  pidAckValid = false; }
                else                       { events.add(pmWriteKind == WK_RATES_ADV ? "TX edit: RATES+adv -> FC" : "TX edit: RATES -> FC"); ratesAckValid = false; }
                pmWriteKind = WK_NONE;
                pmState = PM_IDLE; txParamBusy = false;
            }
            break;

        default:
            pmState = PM_IDLE; txParamBusy = false;
            break;
    }
}

//*********************************************************************
//  Ack-payload fill for parameter slots  (called from loadNextAck)
//*********************************************************************
inline bool fillParamAck(uint8_t item, uint8_t* ack) {
    if (paramSend == PSEND_RATES && ratesAckValid) {
        switch (item) {
            case 25: ack[1]=ratesAck[0];  ack[2]=ratesAck[1];  ack[3]=ratesAck[2];  ack[4]=ratesAck[3];  return true;
            case 26: ack[1]=ratesAck[4];  ack[2]=ratesAck[5];  ack[3]=ratesAck[6];                       return true;
            case 27: ack[1]=ratesAck[7];  ack[2]=ratesAck[8];  ack[3]=ratesAck[9];  ack[4]=ratesAck[10]; return true;
            case 28: ack[1]=ratesAck[11]; ack[2]=ratesAck[12];                                           return true;
        }
    } else if (paramSend == PSEND_RATES_ADV && ratesAckValid) {
        switch (item) {
            case 25: ack[1]=advRatesAck[0];  ack[2]=advRatesAck[1];  ack[3]=advRatesAck[2];  ack[4]=advRatesAck[3];  return true;
            case 26: ack[1]=advRatesAck[4];  ack[2]=advRatesAck[5];  ack[3]=advRatesAck[6];  ack[4]=advRatesAck[7];  return true;
            case 27: ack[1]=advRatesAck[8];  ack[2]=advRatesAck[9];  ack[3]=advRatesAck[10]; ack[4]=advRatesAck[11]; return true;
            case 28: ack[1]=advRatesAck[12]; ack[2]=advRatesAck[13]; ack[3]=advRatesAck[14];                         return true;
        }
    } else if (paramSend == PSEND_PID && pidAckValid) {
        switch (item) {                          // uint16 pairs, V1 Send_2_x_uint16_t
            case 25: ackPair(ack, pidVals[0],  pidVals[1]);  return true;   // Roll  P,I
            case 26: ackPair(ack, pidVals[2],  pidVals[3]);  return true;   // Roll  D,FF
            case 27: ackPair(ack, pidVals[4],  pidVals[5]);  return true;   // Pitch P,I
            case 28: ackPair(ack, pidVals[6],  pidVals[7]);  return true;   // Pitch D,FF
            case 29: ackPair(ack, pidVals[8],  pidVals[9]);  return true;   // Yaw   P,I
            case 30: ackPair(ack, pidVals[10], pidVals[11]); return true;   // Yaw   D,FF
            case 32: ackPair(ack, pidVals[12], pidVals[13]); return true;   // Roll boost, Pitch boost
            case 33: ackPair(ack, pidVals[14], 0);           return true;   // Yaw boost
            case 34: ackPair(ack, pidVals[15], pidVals[16]); return true;   // HSI offset Roll, Pitch
        }
    }
    return false;
}

#endif // _SRC_TXPARAMS_H
