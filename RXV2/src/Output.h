// LockDownRadioControl — RXV2  ::  Output.h
//
// All RC-output protocol code: frame builders (SBUS, CRSF, IBUS, FBUS, PPM),
// UART/RMT configuration, and the periodic sbusTick() that drives whichever
// protocol is active.
//
// Same pin (D6) for all of them — the chip reconfigures it as either an
// inverted/non-inverted UART or as an RMT pulse generator at boot, depending
// on the user's saved protocol choice.
//
//*********************************************************************

#ifndef _SRC_OUTPUT_H
#define _SRC_OUTPUT_H

#include "1Defs.h"

//*********************************************************************
//  Protocol name / description (for UI)
//*********************************************************************

inline const char* protocolName(Protocol p) {
    switch (p) {
        case PROTO_SBUS:  return "SBUS";
        case PROTO_CRSF:  return "CRSF";
        case PROTO_IBUS:  return "IBUS";
        case PROTO_PPM:   return "PPM";
        case PROTO_FBUS:  return "FBUS";
        case PROTO_IBUS2: return "IBUS2";
    }
    return "?";
}

//*********************************************************************

inline const char* protocolDesc(Protocol p) {
    switch (p) {
        case PROTO_SBUS:  return "FrSky/Futaba, 100 kbaud 8E2 inverted, ~71 Hz";
        case PROTO_CRSF:  return "Crossfire/ELRS, 420 kbaud 8N1, ~250 Hz";
        case PROTO_IBUS:  return "FlySky, 115200 8N1, ~140 Hz";
        case PROTO_PPM:   return "Single-pin pulse train, 8 ch, ~45 Hz (RMT)";
        case PROTO_FBUS:  return "FrSky FBUS, 115200 8N1 inverted, RC frames only (no FC telemetry yet)";
        case PROTO_IBUS2: return "FlySky IBUS2 servo path, 115200 8N1 — same RC frames as IBUS, separate menu entry";
    }
    return "";
}

//*********************************************************************
//  SBUS frame (FrSky / Futaba)
//*********************************************************************
// 25 bytes: start byte 0x0F, 16 channels × 11 bits packed, flags, end byte.

inline void buildSbusFrame(bool frameLost, bool failsafe) {
    memset(sbusFrame, 0, sizeof(sbusFrame));
    sbusFrame[0] = 0x0F;

    uint32_t bits     = 0;
    uint8_t  bitCount = 0;
    uint8_t  idx      = 1;
    for (uint8_t c = 0; c < 16; ++c) {
        // Mirror v1 MapToSBUS: map(value, 500, 2500, 0, 2047)
        long v = (long)channelMicros[c] - 500;
        long s = (v * 2047L) / 2000L;
        if (s < 0)    s = 0;
        if (s > 2047) s = 2047;
        bits |= ((uint32_t)s & 0x07FFu) << bitCount;
        bitCount += 11;
        while (bitCount >= 8) {
            sbusFrame[idx++] = (uint8_t)(bits & 0xFFu);
            bits >>= 8;
            bitCount -= 8;
        }
    }
    sbusFrame[23] = (frameLost ? 0x04 : 0) | (failsafe ? 0x08 : 0);
    sbusFrame[24] = 0x00;
}

//*********************************************************************
//  CRSF CRC-8 (poly 0xD5)
//*********************************************************************

inline uint8_t crsfCrc8(const uint8_t* data, uint8_t len) {
    uint8_t crc = 0;
    for (uint8_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; ++b) {
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0xD5) : (uint8_t)(crc << 1);
        }
    }
    return crc;
}

//*********************************************************************
//  CRSF "packed RC channels" frame (type 0x16)
//*********************************************************************
// 26 bytes total. CRSF channel value 172 = 988 us, 992 = 1500 us, 1811 = 2012 us
// — same 11-bit container as SBUS but shifted/centred.

inline void buildCrsfFrame() {
    crsfFrame[0] = 0xC8;                                 // dest: flight controller
    crsfFrame[1] = 24;                                   // length of (type + payload + crc)
    crsfFrame[2] = 0x16;                                 // type: packed RC channels

    uint32_t bits     = 0;
    uint8_t  bitCount = 0;
    uint8_t  idx      = 3;
    for (uint8_t c = 0; c < 16; ++c) {
        long v       = (long)channelMicros[c] - 1500;    // centre at zero
        long crsfval = (v * 819L) / 500L + 992L;         // 819/500 ≈ 1.638
        if (crsfval < 172)  crsfval = 172;
        if (crsfval > 1811) crsfval = 1811;
        bits |= ((uint32_t)crsfval & 0x07FFu) << bitCount;
        bitCount += 11;
        while (bitCount >= 8) {
            crsfFrame[idx++] = (uint8_t)(bits & 0xFFu);
            bits >>= 8;
            bitCount -= 8;
        }
    }
    crsfFrame[25] = crsfCrc8(&crsfFrame[2], 23);
}

//*********************************************************************
//  FBUS RC frame (FrSky FBUS, control / channel data)  -- dormant
//*********************************************************************
// Best-effort encoding based on common public references — not yet verified
// against a real FC.
//   [0]  length = 0x18 (24 bytes following: header + 23 payload bytes)
//   [1]  header = 0xFF (control / RC frame type)
//   [2..23]  22 bytes of 16 channels × 11 bits packed (same as SBUS/CRSF)
//   [24] flags (frame_lost = bit2, failsafe = bit3)
//   [25] CRC8 over bytes [1..24], poly 0xD5

inline void buildFbusFrame(bool frameLost, bool failsafe) {
    memset(fbusFrame, 0, sizeof(fbusFrame));
    fbusFrame[0] = 0x18;
    fbusFrame[1] = 0xFF;

    uint32_t bits     = 0;
    uint8_t  bitCount = 0;
    uint8_t  idx      = 2;
    for (uint8_t c = 0; c < 16; ++c) {
        long v = (long)channelMicros[c] - 500;
        long s = (v * 2047L) / 2000L;
        if (s < 0)    s = 0;
        if (s > 2047) s = 2047;
        bits |= ((uint32_t)s & 0x07FFu) << bitCount;
        bitCount += 11;
        while (bitCount >= 8) {
            fbusFrame[idx++] = (uint8_t)(bits & 0xFFu);
            bits >>= 8;
            bitCount -= 8;
        }
    }
    fbusFrame[24] = (frameLost ? 0x04 : 0) | (failsafe ? 0x08 : 0);
    fbusFrame[25] = crsfCrc8(&fbusFrame[1], 24);
}

//*********************************************************************
//  IBUS frame (FlySky)
//*********************************************************************
// 32 bytes: header 0x20 0x40, 14 channels × uint16_t little-endian (1000-2000 µs),
// 16-bit checksum = 0xFFFF - sum of preceding bytes.

inline void buildIbusFrame() {
    ibusFrame[0] = 0x20;
    ibusFrame[1] = 0x40;
    for (uint8_t c = 0; c < 14; ++c) {
        uint16_t v = channelMicros[c];
        if (v < 1000) v = 1000;
        if (v > 2000) v = 2000;
        ibusFrame[2 + c * 2]     = (uint8_t)(v & 0xFFu);
        ibusFrame[2 + c * 2 + 1] = (uint8_t)((v >> 8) & 0xFFu);
    }
    uint16_t cksum = 0xFFFF;
    for (uint8_t i = 0; i < 30; ++i) cksum -= ibusFrame[i];
    ibusFrame[30] = (uint8_t)(cksum & 0xFFu);
    ibusFrame[31] = (uint8_t)((cksum >> 8) & 0xFFu);
}

//*********************************************************************
//  PPM RMT items (8 channels)
//*********************************************************************
// Positive PPM (ppmInverted=false): idle LOW, 300 µs HIGH sync pulse leads each
//   channel slot, then LOW for remainder.
// Negative PPM (ppmInverted=true): idle HIGH, 300 µs LOW sync, HIGH for remainder.
// Final entry: long pulse at idle level to fill the 22.5 ms frame.

inline void buildPpmRmtItems() {
    uint8_t sync_lvl = ppmInverted ? 0 : 1;
    uint8_t idle_lvl = ppmInverted ? 1 : 0;
    uint32_t total = 0;
    for (uint8_t c = 0; c < PPM_CHANNELS; ++c) {
        uint16_t v = channelMicros[c];
        if (v < 1000) v = 1000;
        if (v > 2000) v = 2000;
        ppmItems[c].duration0 = PPM_SYNC_US;
        ppmItems[c].level0    = sync_lvl;
        ppmItems[c].duration1 = v - PPM_SYNC_US;
        ppmItems[c].level1    = idle_lvl;
        total += v;
    }
    uint32_t gap = (total < PPM_FRAME_US) ? (PPM_FRAME_US - total) : 1000;
    if (gap > 30000) gap = 30000;
    // The frame gap must START with a sync pulse: PPM measures each channel
    // between consecutive pulse LEADING edges, so without this closing pulse
    // channel 8 has no end marker — decoders lump it into the sync gap and
    // deliver only 7 channels. (gap is always ≥1000 µs, > PPM_SYNC_US.)
    ppmItems[PPM_CHANNELS].duration0 = PPM_SYNC_US;
    ppmItems[PPM_CHANNELS].level0    = sync_lvl;
    ppmItems[PPM_CHANNELS].duration1 = (uint16_t)(gap - PPM_SYNC_US);
    ppmItems[PPM_CHANNELS].level1    = idle_lvl;
}

//*********************************************************************
//  Configure output driver from saved protocol selection
//*********************************************************************
// Called once from setup() after loading NVS. Brings up UART or RMT on D6 (and
// D5 for the bidirectional protocols) per the chosen protocol.

inline void configureOutputDriver(Protocol p) {
    if (p == PROTO_PPM) {
        // arduino-esp32 v2 RMT API: rmtInit(pin, tx_not_rx, memsize). tx_not_rx=true → TX mode.
        // RMT_MEM_128 gives plenty of headroom (32 items, we use 9).
        ppmRmt = rmtInit(PIN_SBUS_TX, /*tx_not_rx=*/true, RMT_MEM_128);
        if (ppmRmt) {
            rmtSetTick(ppmRmt, 1000.0f);
            ppmRmtReady = true;
            Serial.printf("[out] PPM via RMT on GPIO %d\n", PIN_SBUS_TX);
        } else {
            Serial.println("[out] PPM RMT init failed");
            ppmRmtReady = false;
        }
        return;
    }
    switch (p) {
        case PROTO_SBUS:
            // TX-only — SBUS has no telemetry path back from the FC.
            Serial1.begin(100000, SERIAL_8E2, -1, PIN_SBUS_TX, true);
            Serial.printf("[out] SBUS inverted UART on GPIO %d (100 kbaud 8E2)\n", PIN_SBUS_TX);
            break;
        case PROTO_CRSF:
            // Bidirectional — D6 sends RC, D5 receives FC telemetry + MSP responses.
            // 2 KB RX FIFO (0.9.563, default 256 B): at the fast telemetry
            // link rate (1000/1) the FC sends ~34 frames/s and a jumbo MSP
            // reply lands as a burst of 64-byte chunks — a loop stall (NVS
            // write, WiFi join) longer than a few ms overflowed 256 B and
            // cost a chunk. Must be set before begin() — it is ignored after.
            Serial1.setRxBufferSize(2048);
            Serial1.begin(420000, SERIAL_8N1, PIN_FC_RX, PIN_SBUS_TX, false);
            Serial.printf("[out] CRSF UART tx=D6 rx=D5 (420 kbaud 8N1)\n");
            break;
        case PROTO_IBUS:
            // TX-only IBUS — no sensor polling here; pick IBUS2 if you want telemetry.
            Serial1.begin(115200, SERIAL_8N1, -1, PIN_SBUS_TX, false);
            Serial.printf("[out] IBUS UART on GPIO %d (115200 8N1)\n", PIN_SBUS_TX);
            break;
        case PROTO_FBUS:
            // FBUS is single-wire half-duplex: tie D6 and D5 together externally to the FC's
            // FBUS pad. We transmit on D6 and listen on D5 for the FC's downlink queries.
            Serial1.begin(115200, SERIAL_8N1, PIN_FC_RX, PIN_SBUS_TX, true);
            Serial.printf("[out] FBUS UART tx=D6 rx=D5 (115200 8N1 inverted)\n");
            break;
        case PROTO_IBUS2:
            // FlySky IBUS2: servo bus on D6 (TX), sensor bus on D5 (RX). The FC polls D5
            // for sensor data; we respond by writing the response back via the same UART.
            Serial1.begin(115200, SERIAL_8N1, PIN_FC_RX, PIN_SBUS_TX, false);
            Serial.printf("[out] IBUS2 UART tx=D6 rx=D5 (115200 8N1)\n");
            break;
        default: break;
    }
}

//*********************************************************************
//  Period selector per protocol
//*********************************************************************

inline uint32_t protocolPeriodMs(Protocol p) {
    switch (p) {
        case PROTO_SBUS:  return SBUS_PERIOD_MS;
        case PROTO_CRSF:  // configurable: some CRSF-to-PWM converters choke above ~100 Hz
            return (crsfRateHz >= 50 && crsfRateHz <= 250) ? (1000u / crsfRateHz) : CRSF_PERIOD_MS;
        case PROTO_IBUS:  return IBUS_PERIOD_MS;
        case PROTO_PPM:   return PPM_PERIOD_MS;
        case PROTO_FBUS:  return FBUS_PERIOD_MS;
        case PROTO_IBUS2: return IBUS_PERIOD_MS;
    }
    return SBUS_PERIOD_MS;
}

//*********************************************************************
//  Periodic output tick — drives whichever protocol is active
//*********************************************************************
// Name is "sbusTick" for historical reasons; it actually dispatches to the
// selected protocol's frame builder + write.

// Idle-HIGH protocols: when running, the UART peripheral holds GPIO 21
// HIGH between frames, which keeps the on-board LED (active-low, shared
// pin) dark. To let heartbeat() drive the LED on these protocols when
// the link is lost we suspend the UART entirely during failsafe — which
// matches the CRSF convention anyway (the FC infers loss from absence
// of frames). When packets resume we re-attach the UART. SBUS/FBUS/PPM
// idle the pin LOW which already lights the LED, so they're untouched.
inline bool isIdleHighProto(Protocol p) {
    return (p == PROTO_CRSF) || (p == PROTO_IBUS) || (p == PROTO_IBUS2);
}

inline bool bleAdvertising();   // BleConfig.h (included later): Bluetooth config up
inline bool bleHasClient();
inline bool outputDetachedForFailsafe = false;

inline void sbusTick() {
    // A dongle has no RC output at all: its Serial1 is the flight controller's
    // MSP port, and a sim board's is idle. Every caller is meant to guard this
    // (loop, keepFlyingTick, safeOutputParkAndRestart) — one slipped through
    // for a year (mspRequestAndWait, 2026-09-16 review), so guard it HERE too.
    if (dongleEnabled || simEnabled) return;
    // Suspend RC frame transmission while the MSP bridge has a client connected.
    // The user is configuring (TX is off, we're not flying); the FC's CRSF UART
    // is being driven by Configurator over the bridge instead. Sending RC frames
    // here would interleave with MSP traffic and corrupt both directions.
    if (mspBridgeActive) {
        if (outputDetachedForFailsafe) {
            configureOutputDriver(currentProtocol);
            outputDetachedForFailsafe = false;
        }
        return;
    }

    if ((uint32_t)(millis() - lastSbusMs) < protocolPeriodMs(currentProtocol)) return;
    lastSbusMs = millis();

    // Failsafe is "has the bound TX gone quiet" — a property of the LINK, not of
    // whether the most recent packet happened to carry channel data. With the
    // sticks held still the TX sends only *changed* channels, so between moves it
    // sends runs of parameter / no-change packets (mask==0) that
    // decodeChannelData() drops (Channels.h) BEFORE refreshing lastChannelDataMs.
    // Basing failsafe on lastChannelDataMs therefore made the link look "lost"
    // for a moment every few seconds even though packets never stopped — and in
    // CRSF (idle-high) that briefly detached the UART, so the FC saw RXLOSS and
    // every channel flashed to zero in the Configurator before snapping back.
    // rx.lastMillis updates on EVERY received packet, so it tracks the true link
    // state; hold the last channel values meanwhile (correct — nothing changed).
    // Fall back to lastChannelDataMs pre-bind / before the first packet.
    uint32_t linkRef   = (bindState.bound && rx.lastMillis) ? rx.lastMillis
                                                            : lastChannelDataMs;
    uint32_t age       = millis() - linkRef;
    bool     frameLost = age > 100;
    bool     failsafe  = age > OUTPUT_FAILSAFE_MS;   // v1 FAILSAFE_TIMEOUT — hold last good values below this

    // In-flight signal loss → output the saved failsafe posture (the user's
    // choice; v1 behaviour). Gated on everConnected so a no-transmitter BOOT
    // keeps the guaranteed disarmed-safe default and never these values (which
    // may have the arm switch off).
    //
    // BUT NOT on CRSF: a Rotorflight FC OVERRULES streamed channels once it
    // detects link loss — over CRSF the FC's own failsafe is the authority, and
    // streaming preset positions only delays it seeing the dropout. So on CRSF we
    // skip this and fall through to the detach below (FC takes over — the better
    // authority on that FC). On the other protocols (SBUS/FBUS/IBUS/PPM), which
    // may drive systems that rely on the receiver's failsafe, we DO drive the
    // outputs to the saved positions and present them as valid RC.
    static bool inFailsafePosture = false;
    bool everConnected = (lastChannelDataMs != 0);
    // SAFETY: hold the throttle LOW until the link has produced a STABLE
    // stream (25 channel packets ≈ half a second) — covers the no-TX boot
    // (channels default to mid-stick), AND the first moments after binding,
    // when a V1 TX in bind mode bypasses its own motor-low overrides and the
    // earliest packets may be junk (the propeller blipped during a field
    // rebind, prop fitted, hands near the model).
    if ((!everConnected || channelPacketsRx < 25) && throttleChannel >= 1 && throttleChannel <= 16)
        channelMicros[throttleChannel - 1] = THROTTLE_SAFE_US;
    // Gate is "not CRSF", NOT "not idle-high": IBUS/IBUS2 are idle-high too but
    // have no FC-side failsafe authority (no in-frame loss flag either), so they
    // rely on the receiver applying the captured posture like SBUS/PPM do.
    // ClaudeFix-16-7-2026 CRSF with the FC-telemetry switch OFF means there is no FC —
    // just a PWM converter — so the receiver IS the failsafe authority there
    // too. (Previously CRSF always went silent and the converter drifted.)
    bool fsAuthority = failsafe && everConnected &&
                       (currentProtocol != PROTO_CRSF || !fcTelemetryEnabled);
    if (fsAuthority && failsafeSet) {
        for (uint8_t i = 0; i < 16; ++i) channelMicros[i] = failsafeMicros[i];
        if (!inFailsafePosture) { inFailsafePosture = true; events.add("Signal lost — RX failsafe positions applied"); }
    } else if (inFailsafePosture) {
        inFailsafePosture = false;
        events.add("Link restored — left RX failsafe");
    }
    // BLE-ready announce (Malcolm 2026-07-23): wave the chosen channels
    // (waveChannelMask, default ch1 — his plane is 1+6) whenever Bluetooth
    // becomes available, POWER-ON INCLUDED, so the user can SEE the receiver
    // is reachable. Gentle (±150 µs), time-boxed, non-blocking. Rides on
    // whatever the outputs are doing — failsafe posture, held last-good
    // values, boot defaults, even a live link during the boot BLE window.
    // The THROTTLE channel never waves. Skipped on CRSF with an FC (the FC
    // is channel authority during failsafe).
    // Rotor watch, EVERY tick (0.9.756): the last moment the head was seen
    // turning. It used to be sampled only inside the wave block below, which
    // first runs at the disarm revival - by then the motor already reads 0 in
    // the normal landing order (motor off, head coasts, safety on), so the
    // 20 s coast wait never engaged and the tail waggled on a turning head.
    // One comparison per tick; nothing else in the control path changes.
    static uint32_t rotorTurningMs = 0;
    const bool rpmFresh = fcTelem.rpmMs && (uint32_t)(millis() - fcTelem.rpmMs) < 3000;
    if (rpmFresh && fcTelem.fcMotorRPM >= 60) rotorTurningMs = millis();

    if (bleWaveStartMs) {
        // FC models (CRSF + FC telemetry) wave too now — Malcolm's field
        // report 2026-07-31: the announce never showed on the repaired heli.
        // After landing the FC is DISARMED and passes cyclic straight to the
        // swash, so the wave is visible and safe (throttle and the arming
        // channel never wave).
        // 0.9.569 (Malcolm 2026-09-05: "when the transmitter becomes
        // disarmed and Bluetooth and Wi-Fi are re-enabled, the wiggle
        // should happen immediately to remind the user he can now use his
        // phone"): an FC model now waves on a LIVE link too — only when the
        // model is DISARMED and the rotor has STOPPED. "Immediately" is
        // the moment the head speed reads zero: a tail wiggle on a
        // coasting rotor yaws the model on its skids. Until then the wave
        // waits (up to 90 s). Never armed on a live link (the in-flight
        // brownout-reboot boot window), and never with no arming channel
        // to tell us — those keep the old rule: FC models wave only once
        // the TX has gone quiet.
        const bool fcModel   = (currentProtocol == PROTO_CRSF) && fcTelemetryEnabled;
        const bool linkQuiet = (rx.lastMillis == 0) ||
                               (uint32_t)(millis() - rx.lastMillis) > 2000;
        const bool armKnown  = armingChannel >= 1 && armingChannel <= 16;
        const bool armedLive = armKnown && rx.lastMillis &&
                               (uint32_t)(millis() - rx.lastMillis) < 500 &&
                               channelMicros[armingChannel - 1] > 1500;
        const bool disarmedLive = armKnown && !linkQuiet && channelMicros[armingChannel - 1] < 1500;
        // Rotor stopped = head speed zero on FRESH RPM telemetry (a stale
        // zero could be a dead sensor on a turning rotor); with no RPM
        // telemetry at all, disarmed 30 s straight (a 770 coasts ~20 s).
        static uint32_t disarmedSinceMs = 0;
        if (disarmedLive) { if (!disarmedSinceMs) disarmedSinceMs = millis(); } else disarmedSinceMs = 0;
        // Head speed here is the ESC's motor RPM times the gear ratio, and on
        // a helicopter the motor stops the instant the throttle is cut while
        // the head coasts on its one-way bearing for ~20 s. So a fresh ZERO
        // means the MOTOR stopped, not the rotor (Malcolm, the 09-16 flights:
        // "as the head speed decayed, the tail waggled like an excited
        // puppy"). Wait out the coast from the last reading that showed the
        // head turning — and never inside 5 s of the safety switch going on,
        // whatever the telemetry says (his rule). Both apply once the head
        // has been SEEN turning this power-up; a plain power-up with the TX
        // on keeps its prompt boot wiggle. (A brownout reboot in flight is
        // covered by armedLive above — the TX still says armed.)
        const bool coastOver    = !rotorTurningMs || (uint32_t)(millis() - rotorTurningMs) > ROTOR_COAST_MS;
        const bool disarmedLong = !rotorTurningMs ||
                                  (disarmedSinceMs && (uint32_t)(millis() - disarmedSinceMs) > WAVE_AFTER_DISARM_MS);
        const bool rotorStopped = rpmFresh ? (fcTelem.fcMotorRPM < 60 && coastOver && disarmedLong)
                                           : (disarmedSinceMs && (uint32_t)(millis() - disarmedSinceMs) > 30000);
        const bool waveAllowed  = !fcModel || linkQuiet || (disarmedLive && rotorStopped);
        static uint32_t waveWaitSinceMs = 0;     // waiting for the rotor to stop (0 = not waiting)
        uint32_t t = (uint32_t)(millis() - bleWaveStartMs);
        static uint32_t waveEpoch = 0;
        static uint16_t waveBase[16];
        // Settle every waved channel back EXACTLY where it started — a
        // boot-default 500 µs AUX must not be left parked at a wave value,
        // and on a live link a rudder left 150 µs off would FLY that way
        // until the stick next moved (the TX sends only changed channels).
        // Also the abort path (armed mid-wave).
        auto settle = [&]() {
            if (waveEpoch == bleWaveStartMs && waveChannelMask)
                for (uint8_t i = 0; i < 16; ++i)
                    if ((waveChannelMask & (1u << i)) &&
                        throttleChannel != i + 1 && armingChannel != i + 1)
                        channelMicros[i] = waveBase[i];
            bleWaveStartMs = 0;
            waveWaitSinceMs = 0;
        };
        if (t >= BLE_WAVE_MS) {
            settle();
        } else if (waveAllowed && waveChannelMask && !armedLive) {
            if (waveEpoch != bleWaveStartMs) {
                waveEpoch = bleWaveStartMs;
                for (uint8_t i = 0; i < 16; ++i) waveBase[i] = channelMicros[i];
                if (fcModel && disarmedLive)
                    events.add(waveWaitSinceMs ? "Rotor stopped: servo wiggle — the phone can connect now"
                                               : "Disarmed: servo wiggle — the phone can connect now");
                waveWaitSinceMs = 0;
            }
            float   ph  = (float)t * (2.0f * (float)M_PI * BLE_WAVE_HZ / 1000.0f);
            int32_t off = (int32_t)(BLE_WAVE_AMPL_US * sinf(ph));
            for (uint8_t i = 0; i < 16; ++i) {
                if (!(waveChannelMask & (1u << i))) continue;
                if (throttleChannel == i + 1) continue;    // never wave the throttle
                if (armingChannel   == i + 1) continue;    // never wave the arm switch
                // Swing around a sensible CENTRE. A channel parked OUTSIDE
                // the real servo range (boot parks AUX at 500 µs) waves
                // around 1500 — near its parked extreme the surface sits
                // against its mechanical stop and the wiggle is invisible
                // (RIOT bench, 2026-07-23: data waved, servo didn't). A
                // channel HOLDING a genuine in-range value waves close to it.
                int32_t ctr = (int32_t)waveBase[i];
                if (ctr < 1000 || ctr > 2000) ctr = 1500;
                else if (ctr < 1000 + BLE_WAVE_AMPL_US) ctr = 1000 + BLE_WAVE_AMPL_US;
                else if (ctr > 2000 - BLE_WAVE_AMPL_US) ctr = 2000 - BLE_WAVE_AMPL_US;
                channelMicros[i] = (uint16_t)(ctr + off);
            }
            // Present valid RC while waving — converters ignore channels
            // flagged as failsafe.
            frameLost = false;
            failsafe  = false;
        } else if (fcModel && disarmedLive && waveChannelMask && !rotorStopped && waveEpoch != bleWaveStartMs) {
            // Landed on a live link, rotor still turning: hold the wave for
            // the stop — the 1.6 s window starts then. Give up after 90 s.
            if (!waveWaitSinceMs) waveWaitSinceMs = millis();
            if ((uint32_t)(millis() - waveWaitSinceMs) > 90000) {
                events.add("Servo wiggle skipped: rotor still turning 90 s after disarming");
                bleWaveStartMs = 0;
                waveWaitSinceMs = 0;
            } else {
                bleWaveStartMs = millis();   // re-base: t stays ~0 while waiting
            }
        } else {
            settle();   // armed, no arming channel, mask empty, or a live TX with no verdict: no wave
        }
    }
    // Present the frames as valid RC while the posture is being driven.
    if (fsAuthority && failsafeSet) {
        frameLost = false;
        failsafe  = false;
    }

    // Idle-HIGH protocol failsafe handling — detach the UART so the LED
    // pin can be driven by heartbeat() in Network.h. Only flips on the
    // edge so we don't thrash Serial1 every tick.
    //
    // Critical: only detach AFTER the link has genuinely been live at
    // least once. On a cold boot lastChannelDataMs is still zero and
    // "failsafe" trips immediately — tearing Serial1 down before the FC
    // has had a chance to send its first telemetry frame killed the D5
    // RX line on CRSF and hid the Rotorflight config button until the
    // user power-cycled while the TX was already on. The everConnected
    // guard makes "no link" a state we only enter after having had a
    // link, which is what the user actually wants the LED to warn about.
    if (isIdleHighProto(currentProtocol)) {
        // Keep the UART ATTACHED whenever WiFi is up (bench / config mode). The
        // detach kills the D5 RX line, so MSP to the FC stops and the web UI loses
        // its Rotorflight options until a reboot — and after a TX session
        // (everConnected) that's exactly what happens once the TX is switched off
        // and WiFi auto-re-enables. NB auto-WiFi also comes up ~10 s after an
        // IN-FLIGHT signal loss, re-attaching this UART — the "silence while
        // failsafe" guard below the detach block is what keeps that safe.
        // NET_WIFI_CONNECTING counts too (2026-08-02, field report): at the
        // flying field the STA retries can last ~2 minutes before AP fallback,
        // and the detach starved MSP the whole time — Black box showed "no
        // flight-controller telemetry" with the battery plugged in. Safety
        // unchanged: the silence-while-failsafe guard below already covers
        // auto-WiFi coming up after an IN-FLIGHT loss (same as NET_WIFI_UP).
        bool wifiConfigUp  = (netMode == NET_WIFI_UP || netMode == NET_AP ||
                              netMode == NET_WIFI_CONNECTING);
        // ...and whenever Bluetooth config is up (0.9.580). A FIELD landing
        // revives Bluetooth alone (Network.h: no WiFi hunt away from home),
        // so the transmitter going off after a flight parked this UART with
        // the phone still connected — every Rotorflight read answered "did
        // not respond within 1200 ms" until a reboot (Malcolm 2026-09-07,
        // Goblin 770, first flight-test morning: governor page, first-time
        // basics). The lamp on this pin is the price: no "no link" LED while
        // a phone can be talking to the flight controller.
        bool bleConfigUp   = bleAdvertising() || bleHasClient();
        bool wantDetach    = everConnected && failsafe && !wifiConfigUp && !bleConfigUp;
        if (wantDetach && !outputDetachedForFailsafe) {
            Serial1.end();
            pinMode(PIN_SBUS_TX, OUTPUT);
            digitalWrite(PIN_SBUS_TX, HIGH);   // park HIGH so LED starts off
            outputDetachedForFailsafe = true;
            Serial.println("[out] failsafe: UART released, LED owns the pin");
            { char b[64]; snprintf(b, sizeof(b), "DIAG CRSF-DETACH age=%lums (output silent)", (unsigned long)age); events.add(b); }
            return;                            // no frame this tick
        }
        if (!wantDetach && outputDetachedForFailsafe) {
            configureOutputDriver(currentProtocol);
            outputDetachedForFailsafe = false;
            Serial.println("[out] link restored: UART re-attached");
            events.add("DIAG CRSF-REATTACH (output resumed)");
        }
        if (outputDetachedForFailsafe) return; // skip TX while detached
    }

    // SAFETY: link lost after a real session and no captured failsafe applied
    // above — CRSF/IBUS/PPM frames have NO in-frame loss flag, so the only
    // safe output is NONE (absence of frames IS their loss signal). Without
    // this, a CRSF UART kept attached for WiFi (bench, or auto-WiFi coming up
    // ~10 s after an in-flight signal loss) would resume streaming the held
    // pre-loss channels — arm switch and collective included — as valid RC,
    // letting the FC leave failsafe on a downed model. SBUS/FBUS keep sending
    // because their frames carry explicit frameLost/failsafe flag bits.
    if (failsafe && everConnected &&
        (currentProtocol == PROTO_CRSF || currentProtocol == PROTO_IBUS ||
         currentProtocol == PROTO_IBUS2 || currentProtocol == PROTO_PPM)) {
        return;
    }

    switch (currentProtocol) {
        case PROTO_SBUS:
            buildSbusFrame(frameLost, failsafe);
            Serial1.write(sbusFrame, sizeof(sbusFrame));
            break;
        case PROTO_CRSF:
            // CRSF has no explicit frame-lost bit — the FC infers loss from absence of frames.
            (void)frameLost; (void)failsafe;
            buildCrsfFrame();
            Serial1.write(crsfFrame, sizeof(crsfFrame));
            break;
        case PROTO_IBUS:
        case PROTO_IBUS2:
            (void)frameLost; (void)failsafe;
            buildIbusFrame();
            Serial1.write(ibusFrame, sizeof(ibusFrame));
            break;
        case PROTO_FBUS:
            buildFbusFrame(frameLost, failsafe);
            Serial1.write(fbusFrame, sizeof(fbusFrame));
            break;
        case PROTO_PPM:
            if (ppmRmtReady && ppmRmt) {
                buildPpmRmtItems();
                // Non-blocking. Each frame is ~22 ms; PPM_PERIOD_MS is 25 ms so the
                // previous transmission has plenty of time to complete before the next
                // write reuses the buffer. If hardware is still busy we skip this frame.
                rmtWrite(ppmRmt, ppmItems, PPM_CHANNELS + 1);
            }
            break;
    }
    sbusFramesOut++;
}

#endif // _SRC_OUTPUT_H
