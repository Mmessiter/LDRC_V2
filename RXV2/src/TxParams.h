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
//  Parameter IDs (V1 1Definitions.h) and ack-send states
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

// Which block the ack-payload is currently streaming back to the TX. Mirrors
// V1 SendRotorFlightParametresNow. Cleared when the read window (duration the
// TX asked for) expires.
enum ParamSend : uint8_t {
    PSEND_NONE = 0, PSEND_PID = 1, PSEND_RATES = 2, PSEND_RATES_ADV = 3,
    PSEND_PID_ADV = 4, PSEND_GOV_CONFIG = 5, PSEND_GOV_PROFILE = 6
};
inline ParamSend paramSend      = PSEND_NONE;
inline uint32_t  paramSendUntil = 0;

//*********************************************************************
//  Cached ack bytes (built from the FC's MSP_RC_TUNING response)
//*********************************************************************
// RATES ack order (V1 StoreRatesBytesForAckPayload): per axis Centre, Max, Expo
//   [0]type [1]RollC [2]RollMax [3]RollExpo [4]PitchC [5]PitchMax [6]PitchExpo
//   [7]YawC [8]YawMax [9]YawExpo [10]CollC [11]CollMax [12]CollExpo
inline uint8_t ratesAck[13]  = {0};
// ADVANCED RATES ack order (V1 StoreAdvancedRatesBytesForAckPayload):
//   [0..3] Response time R,P,Y,C  [4..7] Setpoint-boost gain R,P,Y,C
//   [8..11] Setpoint-boost cutoff R,P,Y,C
//   [12] Yaw dyn ceiling gain  [13] Yaw dyn deadband gain  [14] Yaw dyn deadband filter
inline uint8_t advRatesAck[15] = {0};
inline bool    ratesAckValid   = false;     // both blocks come from one RC_TUNING read

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
inline uint8_t wResp[4]       = {0};   // response time R,P,Y,C
inline uint8_t wBoostGain[4]  = {0};   // setpoint-boost gain R,P,Y,C
inline uint8_t wBoostCutoff[4]= {0};   // setpoint-boost cutoff R,P,Y,C
inline uint8_t wYawDyn[3]     = {0};   // ceiling gain, deadband gain, deadband filter

// write requests raised by the packet parser, serviced by txParamsLoop()
inline bool ratesWriteReq    = false;  // basic rates only (ID 14, word[7]==0)
inline bool ratesAdvWriteReq = false;  // basic + advanced together (ID 16)

//*********************************************************************
//  Async MSP state machine
//*********************************************************************
enum ParamMspState : uint8_t {
    PM_IDLE, PM_RATES_READ, PM_RATES_ORIG, PM_RATES_EEPROM
};
inline ParamMspState pmState   = PM_IDLE;
inline uint32_t      pmStateAt = 0;
inline bool          pmWriteAdv = false;       // current write includes advanced fields
inline uint8_t       pmScratch[64] = {0};      // read-modify-write buffer
inline uint32_t      lastParamFetchMs = 0;     // last RC_TUNING re-poll (continuous refresh)

inline bool txParamMspFree() {
    return currentProtocol == PROTO_CRSF && !mspBridgeActive && mspWaitFunction == 0xFF;
}

//*********************************************************************
//  Build the cached ack bytes from a raw MSP_RC_TUNING response
//*********************************************************************
// MSP RC_TUNING per-axis order: Centre(rcRate), Expo(rcExpo), Max(srate),
// Response, Accel(2). The TX wants basic rates as Centre, Max, Expo.
inline void buildRatesFromMsp(const uint8_t* p, uint16_t len) {
    if (len < 25) return;
    ratesAck[0]  = p[0];                                   // rates type
    ratesAck[1]  = p[1];  ratesAck[2]  = p[3];  ratesAck[3]  = p[2];   // Roll  C,Max,Expo
    ratesAck[4]  = p[7];  ratesAck[5]  = p[9];  ratesAck[6]  = p[8];   // Pitch
    ratesAck[7]  = p[13]; ratesAck[8]  = p[15]; ratesAck[9]  = p[14];  // Yaw
    ratesAck[10] = p[19]; ratesAck[11] = p[21]; ratesAck[12] = p[20];  // Collective

    // Advanced rates live in the per-axis Response byte (o4/10/16/22) and the
    // API-12.8 tail. The boost tail is INTERLEAVED per axis: o25 Roll-gain,
    // o26 Roll-cutoff, o27 Pitch-gain, o28 Pitch-cutoff, o29 Yaw-gain,
    // o30 Yaw-cutoff, o31 Coll-gain, o32 Coll-cutoff, o33/34/35 yaw dynamics.
    // The ack wants them grouped: gains R,P,Y,C then cutoffs R,P,Y,C.
    if (len >= 36) {
        advRatesAck[0]  = p[4];  advRatesAck[1]  = p[10]; advRatesAck[2]  = p[16]; advRatesAck[3]  = p[22];
        advRatesAck[4]  = p[25]; advRatesAck[5]  = p[27]; advRatesAck[6]  = p[29]; advRatesAck[7]  = p[31]; // gains R,P,Y,C
        advRatesAck[8]  = p[26]; advRatesAck[9]  = p[28]; advRatesAck[10] = p[30]; advRatesAck[11] = p[32]; // cutoffs R,P,Y,C
        advRatesAck[12] = p[33]; advRatesAck[13] = p[34]; advRatesAck[14] = p[35];
    }
    ratesAckValid = true;
}

//*********************************************************************
//  Incoming parameter packet parser  (V1 ReadExtraParameters)
//*********************************************************************
// Called from radioPoll() for every received packet whose ChannelBitMask == 0.

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
        // ---- RATES (read) ----
        case PID_SEND_RATES:                    // 12 — "send rates now"
            if (w[1] == 321) {
                paramSend        = PSEND_RATES;
                paramSendUntil   = millis() + w[2];
                lastParamFetchMs = 0;           // fetch immediately (don't wait for the re-poll tick)
            }
            break;
        // ---- ADVANCED RATES (read) ----
        case PID_SEND_RATES_ADV:                // 15 — "send advanced rates now"
            if (w[1] == 321) {
                paramSend        = PSEND_RATES_ADV;
                paramSendUntil   = millis() + w[2];
                lastParamFetchMs = 0;
            }
            break;

        // ---- RATES (write) ----
        case PID_RATES_FIRST7:                  // 13 — type + Roll + Pitch (C,Max,Expo)
            wRatesType = (uint8_t)w[1];
            wRoll[0]  = (uint8_t)w[2]; wRoll[1]  = (uint8_t)w[3]; wRoll[2]  = (uint8_t)w[4];
            wPitch[0] = (uint8_t)w[5]; wPitch[1] = (uint8_t)w[6]; wPitch[2] = (uint8_t)w[7];
            break;
        case PID_RATES_SECOND6:                 // 14 — Yaw + Collective; word[7]==0 => write basic now
            wYaw[0]  = (uint8_t)w[1]; wYaw[1]  = (uint8_t)w[2]; wYaw[2]  = (uint8_t)w[3];
            wColl[0] = (uint8_t)w[4]; wColl[1] = (uint8_t)w[5]; wColl[2] = (uint8_t)w[6];
            if (!w[7]) ratesWriteReq = true;    // basic only (no advanced batch pending)
            break;

        // ---- ADVANCED RATES (write): FIRST_7 = ID 17, SECOND_8 = ID 16 (16 triggers combined write) ----
        case PID_RATES_ADV_FIRST7:              // 17
            wResp[0] = (uint8_t)w[1]; wResp[1] = (uint8_t)w[2]; wResp[2] = (uint8_t)w[3]; wResp[3] = (uint8_t)w[4];
            wBoostGain[0] = (uint8_t)w[5]; wBoostGain[1] = (uint8_t)w[6]; wBoostGain[2] = (uint8_t)w[7];
            break;
        case PID_RATES_ADV_SECOND8:             // 16 — completes advanced; triggers rates+advanced write
            wBoostGain[3]   = (uint8_t)w[1];
            wBoostCutoff[0] = (uint8_t)w[2]; wBoostCutoff[1] = (uint8_t)w[3];
            wBoostCutoff[2] = (uint8_t)w[4]; wBoostCutoff[3] = (uint8_t)w[5];
            wYawDyn[0] = (uint8_t)w[6]; wYawDyn[1] = (uint8_t)w[7]; wYawDyn[2] = (uint8_t)w[8];
            ratesAdvWriteReq = true;
            break;

        default:
            break;                              // PIDs / governor — added next
    }
}

//*********************************************************************
//  Loop-driven async MSP state machine  (V1 CheckMSPSerial, non-blocking)
//*********************************************************************

inline void txParamsLoop() {
    if (currentProtocol != PROTO_CRSF) return;
    const uint32_t now = millis();

    // Expire the ack-send window the TX asked for.
    if (paramSend != PSEND_NONE && (int32_t)(now - paramSendUntil) > 0) paramSend = PSEND_NONE;

    const bool ratesWindow = (paramSend == PSEND_RATES || paramSend == PSEND_RATES_ADV);

    switch (pmState) {
        case PM_IDLE:
            // Writes take priority over the read re-poll.
            if ((ratesWriteReq || ratesAdvWriteReq) && txParamMspFree()) {
                pmWriteAdv     = ratesAdvWriteReq;
                ratesWriteReq  = false;
                ratesAdvWriteReq = false;
                mspAsyncFunc = MSP_RC_TUNING; mspAsyncReady = false;
                mspSendRequest(MSP_RC_TUNING);          // read-modify-write: get current first
                pmState = PM_RATES_ORIG; pmStateAt = now; txParamBusy = true;
            } else if (ratesWindow && txParamMspFree() &&
                       (int32_t)(now - lastParamFetchMs) >= 80) {   // continuous re-poll (V1 ~50ms)
                lastParamFetchMs = now;
                mspAsyncFunc = MSP_RC_TUNING; mspAsyncReady = false;
                mspSendRequest(MSP_RC_TUNING);
                pmState = PM_RATES_READ; pmStateAt = now; txParamBusy = true;
            }
            break;

        case PM_RATES_READ:
            if (mspAsyncReady && mspAsyncFunc == MSP_RC_TUNING) {
                buildRatesFromMsp(mspAsyncBuf, mspAsyncLen);
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            } else if ((int32_t)(now - pmStateAt) > 400) {     // FC didn't answer — let the next tick retry
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            }
            break;

        case PM_RATES_ORIG:
            if (mspAsyncReady && mspAsyncFunc == MSP_RC_TUNING) {
                uint16_t n = mspAsyncLen;
                if (n > sizeof(pmScratch)) n = sizeof(pmScratch);
                memcpy(pmScratch, mspAsyncBuf, n);
                mspAsyncFunc = 0xFF;
                if (n >= 25) {
                    // basic rates — MSP order Centre, Expo, Max
                    pmScratch[0]  = wRatesType;
                    pmScratch[1]  = wRoll[0];  pmScratch[2]  = wRoll[2];  pmScratch[3]  = wRoll[1];
                    pmScratch[7]  = wPitch[0]; pmScratch[8]  = wPitch[2]; pmScratch[9]  = wPitch[1];
                    pmScratch[13] = wYaw[0];   pmScratch[14] = wYaw[2];   pmScratch[15] = wYaw[1];
                    pmScratch[19] = wColl[0];  pmScratch[20] = wColl[2];  pmScratch[21] = wColl[1];
                    // advanced rates (only when the TX sent the advanced batch)
                    if (pmWriteAdv && n >= 36) {
                        pmScratch[4]  = wResp[0]; pmScratch[10] = wResp[1]; pmScratch[16] = wResp[2]; pmScratch[22] = wResp[3];
                        // interleaved gain,cutoff per axis (Roll,Pitch,Yaw,Coll)
                        pmScratch[25] = wBoostGain[0]; pmScratch[26] = wBoostCutoff[0];   // Roll
                        pmScratch[27] = wBoostGain[1]; pmScratch[28] = wBoostCutoff[1];   // Pitch
                        pmScratch[29] = wBoostGain[2]; pmScratch[30] = wBoostCutoff[2];   // Yaw
                        pmScratch[31] = wBoostGain[3]; pmScratch[32] = wBoostCutoff[3];   // Collective
                        pmScratch[33] = wYawDyn[0];    pmScratch[34] = wYawDyn[1];    pmScratch[35] = wYawDyn[2];
                    }
                    mspSendRequest(MSP_SET_RC_TUNING, pmScratch, (uint8_t)n);
                    pmState = PM_RATES_EEPROM; pmStateAt = now;
                } else {
                    pmState = PM_IDLE; txParamBusy = false;
                }
            } else if ((int32_t)(now - pmStateAt) > 500) {
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            }
            break;

        case PM_RATES_EEPROM:
            if ((int32_t)(now - pmStateAt) > 120) {     // give SET time to land, then persist
                mspSendRequest(MSP_EEPROM_WRITE);
                events.add(pmWriteAdv ? "TX edit: RATES+advanced -> FC" : "TX edit: RATES -> FC");
                ratesAckValid = false;                  // force a fresh read so the TX re-reads the saved values
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
// Returns true if it filled a parameter block (so the caller knows this slot is
// param data). Only fills when the matching read is active and bytes are valid.

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
    }
    return false;
}

#endif // _SRC_TXPARAMS_H
