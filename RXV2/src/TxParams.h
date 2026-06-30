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
//   * READ: we fetch the block from the FC over MSP and stream the bytes back
//     in the ack-payload (slots 25..30/32..34, selected by `paramSend`).
//   * WRITE: we accumulate the batches, then read-modify-write to the FC over
//     MSP (preserving the fields the TX doesn't edit) + save to EEPROM.
//
// Everything here is NON-BLOCKING: MSP requests are sent with mspSendRequest()
// and their responses captured asynchronously (MspFc.h mspAsync*), advanced by
// txParamsLoop() across loop iterations — so a live TX link is never stalled
// (unlike the blocking mspRequestAndWait the web handlers use).
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
//  RATES — cached ack bytes + staged write values
//*********************************************************************
// ack byte order (V1 StoreRatesBytesForAckPayload): per axis Centre, Max, Expo
//   [0]type [1]RollC [2]RollMax [3]RollExpo [4]PitchC [5]PitchMax [6]PitchExpo
//   [7]YawC [8]YawMax [9]YawExpo [10]CollC [11]CollMax [12]CollExpo
inline uint8_t ratesAck[13]  = {0};
inline bool    ratesAckValid = false;

// staged write values from the TX, [Centre, Max, Expo] per axis
inline uint8_t wRatesType = 0;
inline uint8_t wRoll[3]  = {0};
inline uint8_t wPitch[3] = {0};
inline uint8_t wYaw[3]   = {0};
inline uint8_t wColl[3]  = {0};

// pending requests raised by the packet parser, serviced by txParamsLoop()
inline bool ratesReadReq  = false;
inline bool ratesWriteReq = false;

//*********************************************************************
//  Async MSP state machine
//*********************************************************************
enum ParamMspState : uint8_t {
    PM_IDLE, PM_RATES_READ, PM_RATES_ORIG, PM_RATES_EEPROM
};
inline ParamMspState pmState   = PM_IDLE;
inline uint32_t      pmStateAt = 0;
inline uint8_t       pmScratch[64] = {0};   // read-modify-write buffer

// True only while a parameter MSP request is outstanding (so mspFcPoll yields).
inline bool txParamMspFree() {
    return currentProtocol == PROTO_CRSF && !mspBridgeActive && mspWaitFunction == 0xFF;
}

//*********************************************************************
//  Build the rates ack bytes from a raw MSP_RC_TUNING response
//*********************************************************************
// MSP RC_TUNING per-axis order is Centre, Expo, Max, Response, Accel(2). We
// repack into the TX's expected Centre, Max, Expo order.
inline void buildRatesAckFromMsp(const uint8_t* p, uint16_t len) {
    if (len < 25) return;
    ratesAck[0]  = p[0];                                   // rates type
    ratesAck[1]  = p[1];  ratesAck[2]  = p[3];  ratesAck[3]  = p[2];   // Roll  C,Max,Expo
    ratesAck[4]  = p[7];  ratesAck[5]  = p[9];  ratesAck[6]  = p[8];   // Pitch
    ratesAck[7]  = p[13]; ratesAck[8]  = p[15]; ratesAck[9]  = p[14];  // Yaw
    ratesAck[10] = p[19]; ratesAck[11] = p[21]; ratesAck[12] = p[20];  // Collective
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

    switch (id) {
        // ---- RATES ----
        case PID_SEND_RATES:                    // 12 — "send rates now"
            if (!fcIsRotorflightConfigCapable()) break;
            if (w[1] == 321) {
                ratesReadReq   = true;
                paramSend      = PSEND_RATES;
                paramSendUntil = millis() + w[2];
            }
            break;
        case PID_RATES_FIRST7:                  // 13 — type + Roll + Pitch (C,Max,Expo)
            if (!fcIsRotorflightConfigCapable()) break;
            wRatesType = (uint8_t)w[1];
            wRoll[0]  = (uint8_t)w[2]; wRoll[1]  = (uint8_t)w[3]; wRoll[2]  = (uint8_t)w[4];
            wPitch[0] = (uint8_t)w[5]; wPitch[1] = (uint8_t)w[6]; wPitch[2] = (uint8_t)w[7];
            break;
        case PID_RATES_SECOND6:                 // 14 — Yaw + Collective; word[7]==0 => write now
            if (!fcIsRotorflightConfigCapable()) break;
            wYaw[0]  = (uint8_t)w[1]; wYaw[1]  = (uint8_t)w[2]; wYaw[2]  = (uint8_t)w[3];
            wColl[0] = (uint8_t)w[4]; wColl[1] = (uint8_t)w[5]; wColl[2] = (uint8_t)w[6];
            if (!w[7]) ratesWriteReq = true;    // basic rates only (no advanced batch pending)
            break;

        default:
            break;                              // PIDs / advanced / governor — added next
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

    switch (pmState) {
        case PM_IDLE:
            // Writes take priority over reads.
            if (ratesWriteReq && txParamMspFree()) {
                ratesWriteReq = false;
                mspAsyncFunc = MSP_RC_TUNING; mspAsyncReady = false;
                mspSendRequest(MSP_RC_TUNING);          // read-modify-write: get current first
                pmState = PM_RATES_ORIG; pmStateAt = now; txParamBusy = true;
            } else if (ratesReadReq && txParamMspFree()) {
                ratesReadReq = false;
                mspAsyncFunc = MSP_RC_TUNING; mspAsyncReady = false;
                mspSendRequest(MSP_RC_TUNING);
                pmState = PM_RATES_READ; pmStateAt = now; txParamBusy = true;
            }
            break;

        case PM_RATES_READ:
            if (mspAsyncReady && mspAsyncFunc == MSP_RC_TUNING) {
                buildRatesAckFromMsp(mspAsyncBuf, mspAsyncLen);
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            } else if ((int32_t)(now - pmStateAt) > 600) {     // FC didn't answer
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
                    // Overwrite only the editable fields, in MSP order (Centre,Expo,Max).
                    pmScratch[0]  = wRatesType;
                    pmScratch[1]  = wRoll[0];  pmScratch[2]  = wRoll[2];  pmScratch[3]  = wRoll[1];
                    pmScratch[7]  = wPitch[0]; pmScratch[8]  = wPitch[2]; pmScratch[9]  = wPitch[1];
                    pmScratch[13] = wYaw[0];   pmScratch[14] = wYaw[2];   pmScratch[15] = wYaw[1];
                    pmScratch[19] = wColl[0];  pmScratch[20] = wColl[2];  pmScratch[21] = wColl[1];
                    mspSendRequest(MSP_SET_RC_TUNING, pmScratch, (uint8_t)n);
                    pmState = PM_RATES_EEPROM; pmStateAt = now;
                } else {
                    pmState = PM_IDLE; txParamBusy = false;
                }
            } else if ((int32_t)(now - pmStateAt) > 600) {
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            }
            break;

        case PM_RATES_EEPROM:
            if ((int32_t)(now - pmStateAt) > 120) {     // give SET time to land, then persist
                mspSendRequest(MSP_EEPROM_WRITE);
                events.add("TX edit: RATES written to FC");
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
// `item` is the telemetry-item index (25..34); `ack` is the 6-byte ack buffer
// (ack[0] already = item). Returns true if it filled a parameter block (so the
// caller knows this slot is param data, not telemetry). Only fills when the
// matching read is active and the cached bytes are valid.

inline bool fillParamAck(uint8_t item, uint8_t* ack) {
    if (paramSend == PSEND_RATES && ratesAckValid) {
        switch (item) {
            case 25: ack[1]=ratesAck[0];  ack[2]=ratesAck[1];  ack[3]=ratesAck[2];  ack[4]=ratesAck[3];  return true;
            case 26: ack[1]=ratesAck[4];  ack[2]=ratesAck[5];  ack[3]=ratesAck[6];                       return true;
            case 27: ack[1]=ratesAck[7];  ack[2]=ratesAck[8];  ack[3]=ratesAck[9];  ack[4]=ratesAck[10]; return true;
            case 28: ack[1]=ratesAck[11]; ack[2]=ratesAck[12];                                           return true;
        }
    }
    return false;
}

#endif // _SRC_TXPARAMS_H
