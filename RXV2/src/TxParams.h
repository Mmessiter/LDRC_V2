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
// advanced PID (26 compact bytes, V1 PID_Advanced_Bytes order)
inline uint8_t wAdvPid[26]     = {0};

// ADVANCED PID — 26 compact bytes. MSP_PID_PROFILE scatters these across the
// 43-byte profile; ADV_PID_MAP[i] = the MSP byte offset of compact byte i.
// Used for BOTH read (advPidAck[i] = p[MAP[i]]) and write (p[MAP[i]] = wAdvPid[i]).
//   0 Piro comp        1 Ground error decay
//   2-4 Cutoff R/P/Y   5-7 Error limit R/P/Y   8-9 HSI offset limit R/P
//   10-12 HSI bandwidth R/P/Y   13-15 D cutoff R/P/Y   16-18 B cutoff R/P/Y
//   19 CW yaw stop  20 CCW yaw stop  21 Yaw precomp cutoff
//   22 Cyclic FF gain  23 Collective FF gain  24 Inertia precomp gain  25 Inertia precomp cutoff
inline const uint8_t ADV_PID_MAP[26] = {
    6, 1, 17, 18, 19, 7, 8, 9, 36, 37, 10, 11, 12, 13, 14, 15,
    38, 39, 40, 20, 21, 22, 23, 24, 41, 42
};
inline uint8_t advPidAck[26]   = {0};
inline bool    advPidAckValid  = false;

// GOVERNOR (RF 2.3+ only). One ack array spans profile [0..17] + config [18..45]
// (V1 GovAckPayload). Profile and config come from separate MSP reads, so they
// have separate validity flags. Field order here is V1's, NOT the MSP order —
// build/apply functions remap to/from the scattered MSP layouts.
//  profile [0]RF23-flag [1/2]Headspeed [3]Gain [4]P [5]I [6]D [7]F [8]TTAgain
//          [9]TTAlimit [10]MaxThr [11]MinThr [12]FallbackDrop [13]YawW [14]CycW
//          [15]CollW [16/17]Flags
//  config  [18]Mode [19]Handover [20/21]Startup [22/23]Spoolup [24/25]Spooldown
//          [26/27]Tracking [28/29]Recovery [30/31]HoldTimeout [32/33]AutorotTimeout
//          [34]RpmF [35]PwrF [36]DF [37]FfF [38]TtaF [39]ThrType [40]Idle [41]Auto
inline uint8_t govAck[46]      = {0};
inline uint8_t govWrite[46]    = {0};
inline bool    govProfileValid = false;
inline bool    govConfigValid  = false;

// write requests raised by the packet parser, serviced by txParamsLoop()
inline bool ratesWriteReq    = false;   // basic rates only (ID 14, word[7]==0)
inline bool ratesAdvWriteReq = false;   // advanced (ID 16); + basic too if basicRatesPending
// True once the TX has sent the basic-rates batch (ID 13/14) since the last rates
// write. Distinguishes a RESTORE of rates+advanced (basic IS sent → write it) from
// an advanced-only EDIT (basic NOT sent → preserve the FC's basic, don't zero it).
inline bool basicRatesPending = false;
inline bool pidWriteReq      = false;   // PIDs (ID 11)
inline bool advPidWriteReq   = false;   // advanced PID (ID 21)
inline bool govProfileWriteReq = false; // governor profile (ID 30)
inline bool govConfigWriteReq  = false; // governor config (ID 33)

//*********************************************************************
//  Async MSP state machine
//*********************************************************************
enum ParamMspState : uint8_t { PM_IDLE, PM_READ, PM_WRITE_ORIG, PM_WRITE_EEPROM };
enum WriteKind     : uint8_t { WK_NONE, WK_RATES, WK_RATES_ADV, WK_PID, WK_PID_ADV, WK_GOV_PROFILE, WK_GOV_CONFIG };

inline ParamMspState pmState     = PM_IDLE;
inline WriteKind     pmWriteKind = WK_NONE;
inline uint32_t      pmStateAt   = 0;
inline uint8_t       pmScratch[64] = {0};
inline uint16_t      pmScratchLen  = 0;
inline uint8_t       pmWriteRetries = 0;   // one automatic retry when the pre-write GET times out
inline uint32_t      lastParamFetchMs = 0;     // last read re-poll (continuous refresh)

inline bool txParamMspFree() {
    return currentProtocol == PROTO_CRSF && !mspBridgeActive && mspWaitFunction == 0xFF;
}

// MSP "get" function for the active read window.
inline uint8_t readGetFn() {
    if (paramSend == PSEND_PID)          return MSP_PID;
    if (paramSend == PSEND_PID_ADV)      return MSP_PID_PROFILE;
    if (paramSend == PSEND_GOV_PROFILE)  return MSP_GOVERNOR_PROFILE;
    if (paramSend == PSEND_GOV_CONFIG)   return MSP_GOVERNOR_CONFIG;
    return MSP_RC_TUNING;           // rates + advanced rates
}

// Governor is RF 2.3+ only (V1 gates on api100 >= 1209).
inline bool govSupported() { return rotorflightTxVersion() >= 2; }

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

// MSP_PID_PROFILE → compact 26 bytes via the scatter map.
inline void buildAdvPidFromMsp(const uint8_t* p, uint16_t len) {
    if (len < 43) return;
    for (uint8_t i = 0; i < 26; ++i) advPidAck[i] = p[ADV_PID_MAP[i]];
    advPidAckValid = true;
}

// MSP_GOVERNOR_PROFILE (17 bytes) → govAck[0..17] (V1 order).
inline void buildGovProfileFromMsp(const uint8_t* p, uint16_t len) {
    if (len < 17) return;
    govAck[0]  = govSupported() ? 1 : 0;        // RF2.3-required flag the TX checks
    govAck[1]  = p[0];  govAck[2]  = p[1];      // Headspeed lo/hi
    govAck[3]  = p[2];  govAck[4]  = p[3];  govAck[5] = p[4];  govAck[6] = p[5];  govAck[7] = p[6];  // Gain,P,I,D,F
    govAck[8]  = p[7];  govAck[9]  = p[8];      // TTA_Gain, TTA_Limit
    govAck[10] = p[12]; govAck[11] = p[13];     // Max_Throttle, Min_Throttle
    govAck[12] = p[14];                         // Fallback_Drop
    govAck[13] = p[9];  govAck[14] = p[10]; govAck[15] = p[11];   // Yaw/Cyclic/Collective weight
    govAck[16] = p[15]; govAck[17] = p[16];     // Flags lo/hi
    govProfileValid = true;
}

// MSP_GOVERNOR_CONFIG → govAck[18..41] (V1 order). We only read up to byte 32
// (Auto_Throttle); the bypass curve at 33+ is preserved on write but not read,
// so accept any response that reaches byte 32 — RF 2.3 may report a different
// total length than V1's 42, and a strict ==42 check left the global screen blank.
inline void buildGovConfigFromMsp(const uint8_t* p, uint16_t len) {
    if (len < 33) return;
    govAck[18] = p[0];                          // Gov_Mode
    govAck[19] = p[19];                         // Handover_Throttle
    govAck[20] = p[1];  govAck[21] = p[2];      // Startup
    govAck[22] = p[3];  govAck[23] = p[4];      // Spoolup
    govAck[24] = p[26]; govAck[25] = p[27];     // Spooldown
    govAck[26] = p[5];  govAck[27] = p[6];      // Tracking
    govAck[28] = p[7];  govAck[29] = p[8];      // Recovery
    govAck[30] = p[9];  govAck[31] = p[10];     // Throttle_Hold_Timeout
    govAck[32] = p[13]; govAck[33] = p[14];     // Autorotation_Timeout
    govAck[34] = p[21];                         // Rpm_Filter
    govAck[35] = p[20];                         // Pwr_Filter
    govAck[36] = p[25];                         // D_Filter
    govAck[37] = p[23];                         // Ff_Filter
    govAck[38] = p[22];                         // Tta_Filter
    govAck[39] = p[28];                         // Throttle_Type
    govAck[40] = p[31];                         // Idle_Throttle
    govAck[41] = p[32];                         // Auto_Throttle
    govConfigValid = true;
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
        case PID_SEND_PID_ADV:
            if (w[1] == 321) { paramSend = PSEND_PID_ADV;   paramSendUntil = millis() + w[2]; lastParamFetchMs = 0; }
            break;

        // ---- RATES write ----
        case PID_RATES_FIRST7:                  // 13 — type + Roll + Pitch (C,Max,Expo)
            wRatesType = (uint8_t)w[1];
            wRoll[0]  = (uint8_t)w[2]; wRoll[1]  = (uint8_t)w[3]; wRoll[2]  = (uint8_t)w[4];
            wPitch[0] = (uint8_t)w[5]; wPitch[1] = (uint8_t)w[6]; wPitch[2] = (uint8_t)w[7];
            basicRatesPending = true;
            break;
        case PID_RATES_SECOND6:                 // 14 — Yaw + Collective; word[7]==0 => basic write now, set => defer to ID16 combined
            wYaw[0]  = (uint8_t)w[1]; wYaw[1]  = (uint8_t)w[2]; wYaw[2]  = (uint8_t)w[3];
            wColl[0] = (uint8_t)w[4]; wColl[1] = (uint8_t)w[5]; wColl[2] = (uint8_t)w[6];
            basicRatesPending = true;
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

        // ---- ADVANCED PID write: 3 batches into wAdvPid[26]; ID 21 triggers ----
        case PID_PID_ADV_FIRST9:                // 19 — bytes 0..8
            for (uint8_t i = 0; i < 9; ++i) wAdvPid[i] = (uint8_t)w[i + 1];
            break;
        case PID_PID_ADV_SECOND9:               // 20 — bytes 9..17
            for (uint8_t i = 0; i < 9; ++i) wAdvPid[i + 9] = (uint8_t)w[i + 1];
            break;
        case PID_PID_ADV_THIRD8:                // 21 — bytes 18..25, then write
            for (uint8_t i = 0; i < 8; ++i) wAdvPid[i + 18] = (uint8_t)w[i + 1];
            advPidWriteReq = true;
            break;

        // ---- GOVERNOR (RF 2.3+ only) ----
        case PID_SEND_GOV_PROFILE:              // 27 — read governor profile
            if (govSupported() && w[1] == 321) { paramSend = PSEND_GOV_PROFILE; paramSendUntil = millis() + w[2]; lastParamFetchMs = 0; }
            break;
        case PID_SEND_GOV_CONFIG:               // 28 — read governor config
            if (govSupported() && w[1] == 321) { paramSend = PSEND_GOV_CONFIG;  paramSendUntil = millis() + w[2]; lastParamFetchMs = 0; }
            break;
        case PID_GOV_WR_PROFILE1:               // 29 — profile bytes 1..11
            if (govSupported()) for (uint8_t i = 0; i < 11; ++i) govWrite[i + 1] = (uint8_t)w[i + 1];
            break;
        case PID_GOV_WR_PROFILE2:               // 30 — profile bytes 12..17, then write
            if (govSupported()) { for (uint8_t i = 0; i < 6; ++i) govWrite[i + 12] = (uint8_t)w[i + 1]; govProfileWriteReq = true; }
            break;
        case PID_GOV_WR_CONFIG1:                // 31 — config bytes 18..28
            if (govSupported()) for (uint8_t i = 0; i < 11; ++i) govWrite[i + 18] = (uint8_t)w[i + 1];
            break;
        case PID_GOV_WR_CONFIG2:                // 32 — config bytes 29..39
            if (govSupported()) for (uint8_t i = 0; i < 11; ++i) govWrite[i + 29] = (uint8_t)w[i + 1];
            break;
        case PID_GOV_WR_CONFIG3:                // 33 — config bytes 40..45, then write
            if (govSupported()) { for (uint8_t i = 0; i < 6; ++i) govWrite[i + 40] = (uint8_t)w[i + 1]; govConfigWriteReq = true; }
            break;

        default:
            break;
    }
}

//*********************************************************************
//  Apply staged write values into the read-modify-write scratch buffer
//*********************************************************************
// Basic rates → MSP RC_TUNING order (Centre, Expo, Max per axis).
inline void writeBasicRatesToScratch() {
    pmScratch[0]  = wRatesType;
    pmScratch[1]  = wRoll[0];  pmScratch[2]  = wRoll[2];  pmScratch[3]  = wRoll[1];
    pmScratch[7]  = wPitch[0]; pmScratch[8]  = wPitch[2]; pmScratch[9]  = wPitch[1];
    pmScratch[13] = wYaw[0];   pmScratch[14] = wYaw[2];   pmScratch[15] = wYaw[1];
    pmScratch[19] = wColl[0];  pmScratch[20] = wColl[2];  pmScratch[21] = wColl[1];
}

// Returns false when the freshly-read block is too short to edit safely (FC
// error / truncated response) — the caller must then ABORT the write cycle
// rather than send an unmodified (or empty) SET + EEPROM_WRITE.
inline bool applyWriteToScratch() {
    // Each rates screen writes ONLY its own fields; everything else is preserved
    // from the freshly-read RC_TUNING in pmScratch. This is why basic and
    // advanced no longer clobber each other (the Advanced screen doesn't edit
    // the basic rates, so an advanced save must not touch them — and vice-versa).
    if (pmWriteKind == WK_RATES) {
        if (pmScratchLen < 25) return false;
        writeBasicRatesToScratch();
    } else if (pmWriteKind == WK_RATES_ADV) {
        if (pmScratchLen < 36) return false;
        // V1 writes basic + advanced together. Write basic only if the TX actually
        // sent it this transaction (restore) — otherwise (advanced-only edit) leave
        // the FC's basic as read, so we never zero it.
        if (basicRatesPending) writeBasicRatesToScratch();
        pmScratch[4]  = wResp[0]; pmScratch[10] = wResp[1]; pmScratch[16] = wResp[2]; pmScratch[22] = wResp[3];
        pmScratch[25] = wBoostGain[0]; pmScratch[26] = wBoostCutoff[0];   // Roll  (interleaved gain,cutoff)
        pmScratch[27] = wBoostGain[1]; pmScratch[28] = wBoostCutoff[1];   // Pitch
        pmScratch[29] = wBoostGain[2]; pmScratch[30] = wBoostCutoff[2];   // Yaw
        pmScratch[31] = wBoostGain[3]; pmScratch[32] = wBoostCutoff[3];   // Collective
        pmScratch[33] = wYawDyn[0];    pmScratch[34] = wYawDyn[1];    pmScratch[35] = wYawDyn[2];
    } else if (pmWriteKind == WK_PID) {
        if (pmScratchLen < 34) return false;
        for (uint8_t i = 0; i < 17; ++i) {
            pmScratch[i * 2]     = (uint8_t)(wPid[i] & 0xFF);
            pmScratch[i * 2 + 1] = (uint8_t)(wPid[i] >> 8);
        }
    } else if (pmWriteKind == WK_PID_ADV) {
        if (pmScratchLen < 43) return false;
        for (uint8_t i = 0; i < 26; ++i) pmScratch[ADV_PID_MAP[i]] = wAdvPid[i];   // scatter back
    } else if (pmWriteKind == WK_GOV_PROFILE) {
        if (pmScratchLen < 17) return false;          // govWrite[1..17] → MSP profile order
        pmScratch[0]  = govWrite[1];  pmScratch[1]  = govWrite[2];   // Headspeed lo/hi
        pmScratch[2]  = govWrite[3];  pmScratch[3]  = govWrite[4];  pmScratch[4] = govWrite[5];  pmScratch[5] = govWrite[6];  pmScratch[6] = govWrite[7]; // Gain,P,I,D,F
        pmScratch[7]  = govWrite[8];  pmScratch[8]  = govWrite[9];   // TTA_Gain, TTA_Limit
        pmScratch[9]  = govWrite[13]; pmScratch[10] = govWrite[14]; pmScratch[11] = govWrite[15]; // Yaw/Cyclic/Collective weight
        pmScratch[12] = govWrite[10]; pmScratch[13] = govWrite[11]; // Max/Min throttle
        pmScratch[14] = govWrite[12];                               // Fallback_Drop
        pmScratch[15] = govWrite[16]; pmScratch[16] = govWrite[17]; // Flags lo/hi
    } else if (pmWriteKind == WK_GOV_CONFIG) {
        if (pmScratchLen < 33) return false;          // govWrite[18..41] → MSP config order (rest preserved; write keeps the FC's own length)
        pmScratch[0]  = govWrite[18];           // Gov_Mode
        pmScratch[1]  = govWrite[20]; pmScratch[2]  = govWrite[21]; // Startup
        pmScratch[3]  = govWrite[22]; pmScratch[4]  = govWrite[23]; // Spoolup
        pmScratch[5]  = govWrite[26]; pmScratch[6]  = govWrite[27]; // Tracking
        pmScratch[7]  = govWrite[28]; pmScratch[8]  = govWrite[29]; // Recovery
        pmScratch[9]  = govWrite[30]; pmScratch[10] = govWrite[31]; // Throttle_Hold_Timeout
        pmScratch[13] = govWrite[32]; pmScratch[14] = govWrite[33]; // Autorotation_Timeout
        pmScratch[19] = govWrite[19];           // Handover_Throttle
        pmScratch[20] = govWrite[35];           // Pwr_Filter
        pmScratch[21] = govWrite[34];           // Rpm_Filter
        pmScratch[22] = govWrite[38];           // Tta_Filter
        pmScratch[23] = govWrite[37];           // Ff_Filter
        pmScratch[25] = govWrite[36];           // D_Filter
        pmScratch[26] = govWrite[24]; pmScratch[27] = govWrite[25]; // Spooldown
        pmScratch[28] = govWrite[39];           // Throttle_Type
        pmScratch[31] = govWrite[40];           // Idle_Throttle
        pmScratch[32] = govWrite[41];           // Auto_Throttle
        // [11/12] lost-headspeed, [15-18] autorot bailout/min-entry, [24] spoolup-min,
        // [29/30] spare, [33-41] bypass curve — preserved from the read.
    }    return true;
}

inline uint8_t writeSetFn() {
    if (pmWriteKind == WK_PID)         return MSP_SET_PID;
    if (pmWriteKind == WK_PID_ADV)     return MSP_SET_PID_PROFILE;
    if (pmWriteKind == WK_GOV_PROFILE) return MSP_SET_GOVERNOR_PROFILE;
    if (pmWriteKind == WK_GOV_CONFIG)  return MSP_SET_GOVERNOR_CONFIG;
    return MSP_SET_RC_TUNING;
}
inline uint8_t writeGetFn() {
    if (pmWriteKind == WK_PID)         return MSP_PID;
    if (pmWriteKind == WK_PID_ADV)     return MSP_PID_PROFILE;
    if (pmWriteKind == WK_GOV_PROFILE) return MSP_GOVERNOR_PROFILE;
    if (pmWriteKind == WK_GOV_CONFIG)  return MSP_GOVERNOR_CONFIG;
    return MSP_RC_TUNING;
}

//*********************************************************************
//  Loop-driven async MSP state machine  (V1 CheckMSPSerial, non-blocking)
//*********************************************************************
inline void txParamsLoop() {
    if (currentProtocol != PROTO_CRSF) return;
    const uint32_t now = millis();

    // paramSend is STICKY — it keeps the last-read block selected so fillParamAck
    // always streams that block's cached bytes (stale at worst, never zeros). The
    // window (paramSendUntil) only gates RE-POLLING the FC below, so we stop
    // hammering the FC once the TX's read window ends but the TX never reads zeros
    // if it lingers on a screen past the window or its "send now" request drops.
    const bool pollWindowOpen = (int32_t)(now - paramSendUntil) < 0;

    switch (pmState) {
        case PM_IDLE: {
            WriteKind wk = ratesAdvWriteReq   ? WK_RATES_ADV
                         : ratesWriteReq      ? WK_RATES
                         : pidWriteReq        ? WK_PID
                         : advPidWriteReq     ? WK_PID_ADV
                         : govProfileWriteReq ? WK_GOV_PROFILE
                         : govConfigWriteReq  ? WK_GOV_CONFIG : WK_NONE;
            if (wk != WK_NONE && txParamMspFree()) {
                // Consume ONLY the selected request. A write cycle takes ~300 ms;
                // a different edit raised meanwhile must survive to the next
                // PM_IDLE pass, not be silently wiped with the others.
                // (WK_RATES_ADV also consumes ratesWriteReq: both target the same
                // RC_TUNING message, and the combined write applies the staged
                // basic rates via basicRatesPending.)
                switch (wk) {
                    case WK_RATES_ADV:   ratesAdvWriteReq = false; ratesWriteReq = false; break;
                    case WK_RATES:       ratesWriteReq      = false; break;
                    case WK_PID:         pidWriteReq        = false; break;
                    case WK_PID_ADV:     advPidWriteReq     = false; break;
                    case WK_GOV_PROFILE: govProfileWriteReq = false; break;
                    default:             govConfigWriteReq  = false; break;
                }
                pmWriteKind = wk;
                uint8_t fn = writeGetFn();
                mspAsyncFunc = fn; mspAsyncReady = false;
                mspSendRequest(fn);                       // read-modify-write: get current first
                pmState = PM_WRITE_ORIG; pmStateAt = now; txParamBusy = true;
            } else if (paramSend != PSEND_NONE && pollWindowOpen && txParamMspFree() &&
                       (int32_t)(now - lastParamFetchMs) >= 50) {   // continuous re-poll (matches V1 ~50ms), only within the window
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
                if      (mspAsyncFunc == MSP_RC_TUNING)       buildRatesFromMsp(mspAsyncBuf, mspAsyncLen);
                else if (mspAsyncFunc == MSP_PID)             buildPidsFromMsp(mspAsyncBuf, mspAsyncLen);
                else if (mspAsyncFunc == MSP_PID_PROFILE)     buildAdvPidFromMsp(mspAsyncBuf, mspAsyncLen);
                else if (mspAsyncFunc == MSP_GOVERNOR_PROFILE) buildGovProfileFromMsp(mspAsyncBuf, mspAsyncLen);
                else if (mspAsyncFunc == MSP_GOVERNOR_CONFIG)  buildGovConfigFromMsp(mspAsyncBuf, mspAsyncLen);
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            } else if ((int32_t)(now - pmStateAt) > 250) {   // missed round-trip → retry quickly
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
            }
            break;

        case PM_WRITE_ORIG:
            if (mspAsyncReady) {
                pmScratchLen = mspAsyncLen;
                if (pmScratchLen > sizeof(pmScratch)) pmScratchLen = sizeof(pmScratch);
                memcpy(pmScratch, mspAsyncBuf, pmScratchLen);
                mspAsyncFunc = 0xFF;
                if (!applyWriteToScratch()) {
                    // Read came back too short to edit safely (FC error /
                    // truncated) — ABORT: no SET, no EEPROM_WRITE. Used to fall
                    // through and write the unmodified scratch anyway.
                    events.add("TX edit: FC read too short — save aborted");
                    pmWriteRetries = 0; pmWriteKind = WK_NONE;
                    pmState = PM_IDLE; txParamBusy = false;
                    break;
                }
                pmWriteRetries = 0;
                basicRatesPending = false;       // staged basic consumed; next advanced-only edit preserves the FC's basic
                mspSendRequest(writeSetFn(), pmScratch, (uint8_t)pmScratchLen);
                pmState = PM_WRITE_EEPROM; pmStateAt = now;
            } else if ((int32_t)(now - pmStateAt) > 500) {
                // GET never answered. The request flag was consumed at PM_IDLE,
                // so without re-raising it the user's edit would vanish silently
                // while the TX believes it saved. One retry; then log + drop the
                // staged basic rates (a later advanced-only edit must not push
                // stale staged values).
                mspAsyncFunc = 0xFF; pmState = PM_IDLE; txParamBusy = false;
                if (pmWriteRetries < 1) {
                    pmWriteRetries++;
                    switch (pmWriteKind) {
                        case WK_RATES_ADV:   ratesAdvWriteReq   = true; break;
                        case WK_RATES:       ratesWriteReq      = true; break;
                        case WK_PID:         pidWriteReq        = true; break;
                        case WK_PID_ADV:     advPidWriteReq     = true; break;
                        case WK_GOV_PROFILE: govProfileWriteReq = true; break;
                        default:             govConfigWriteReq  = true; break;
                    }
                } else {
                    pmWriteRetries = 0;
                    basicRatesPending = false;
                    events.add("TX edit: FC not answering — save dropped");
                }
            }
            break;

        case PM_WRITE_EEPROM:
            if ((int32_t)(now - pmStateAt) > 120) {
                mspSendRequest(MSP_EEPROM_WRITE);
                // Governor CONFIG needs an FC restart to take effect (matches V1
                // RestartRotorflight). NB this reboots the FC — fine on the bench
                // while configuring; the RC link drops and re-establishes.
                if (pmWriteKind == WK_GOV_CONFIG) mspSendRequest(MSP_REBOOT);
                // Do NOT invalidate the cache here — the continuous re-poll picks
                // up the freshly-saved values within ~50ms. Blanking it would just
                // flash zeros to the TX until the next poll.
                events.add(pmWriteKind == WK_PID ? "TX edit: PIDs -> FC"
                         : pmWriteKind == WK_PID_ADV ? "TX edit: adv PID -> FC"
                         : pmWriteKind == WK_GOV_PROFILE ? "TX edit: gov profile -> FC"
                         : pmWriteKind == WK_GOV_CONFIG ? "TX edit: gov config -> FC (reboot)"
                         : pmWriteKind == WK_RATES_ADV ? "TX edit: RATES+adv -> FC"
                         : "TX edit: RATES -> FC");
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
    } else if (paramSend == PSEND_PID_ADV && advPidAckValid) {
        switch (item) {                          // 26 bytes, 4 per slot (last slot 2)
            case 25: ack[1]=advPidAck[0];  ack[2]=advPidAck[1];  ack[3]=advPidAck[2];  ack[4]=advPidAck[3];  return true;
            case 26: ack[1]=advPidAck[4];  ack[2]=advPidAck[5];  ack[3]=advPidAck[6];  ack[4]=advPidAck[7];  return true;
            case 27: ack[1]=advPidAck[8];  ack[2]=advPidAck[9];  ack[3]=advPidAck[10]; ack[4]=advPidAck[11]; return true;
            case 28: ack[1]=advPidAck[12]; ack[2]=advPidAck[13]; ack[3]=advPidAck[14]; ack[4]=advPidAck[15]; return true;
            case 29: ack[1]=advPidAck[16]; ack[2]=advPidAck[17]; ack[3]=advPidAck[18]; ack[4]=advPidAck[19]; return true;
            case 30: ack[1]=advPidAck[20]; ack[2]=advPidAck[21]; ack[3]=advPidAck[22]; ack[4]=advPidAck[23]; return true;
            case 32: ack[1]=advPidAck[24]; ack[2]=advPidAck[25];                                             return true;
        }
    } else if (paramSend == PSEND_GOV_PROFILE && govProfileValid) {
        switch (item) {                          // govAck[0..17]
            case 25: ack[1]=govAck[0];  ack[2]=govAck[1];  ack[3]=govAck[2];  ack[4]=govAck[3];  return true;
            case 26: ack[1]=govAck[4];  ack[2]=govAck[5];  ack[3]=govAck[6];  ack[4]=govAck[7];  return true;
            case 27: ack[1]=govAck[8];  ack[2]=govAck[9];  ack[3]=govAck[10]; ack[4]=govAck[11]; return true;
            case 28: ack[1]=govAck[12]; ack[2]=govAck[13]; ack[3]=govAck[14]; ack[4]=govAck[15]; return true;
            case 29: ack[1]=govAck[16]; ack[2]=govAck[17];                                       return true;
        }
    } else if (paramSend == PSEND_GOV_CONFIG && govConfigValid) {
        switch (item) {                          // govAck[18..41]
            case 25: ack[1]=govAck[18]; ack[2]=govAck[19]; ack[3]=govAck[20]; ack[4]=govAck[21]; return true;
            case 26: ack[1]=govAck[22]; ack[2]=govAck[23]; ack[3]=govAck[24]; ack[4]=govAck[25]; return true;
            case 27: ack[1]=govAck[26]; ack[2]=govAck[27]; ack[3]=govAck[28]; ack[4]=govAck[29]; return true;
            case 28: ack[1]=govAck[30]; ack[2]=govAck[31]; ack[3]=govAck[32]; ack[4]=govAck[33]; return true;
            case 29: ack[1]=govAck[34]; ack[2]=govAck[35]; ack[3]=govAck[36]; ack[4]=govAck[37]; return true;
            case 30: ack[1]=govAck[38]; ack[2]=govAck[39]; ack[3]=govAck[40]; ack[4]=govAck[41]; return true;
        }
    }
    return false;
}

#endif // _SRC_TXPARAMS_H
