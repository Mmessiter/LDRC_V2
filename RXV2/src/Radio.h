// LockDownRadioControl — RXV2  ::  Radio.h
//
// nRF24L01+ control: self-test, dual-radio detection + swap-on-loss, v1
// listen configuration, bind, ack-payload rotation, and the radio polling
// loop. Mirrors v1's ReceiverCode/src/utilities/radio.h pattern.
//
//*********************************************************************

#ifndef _SRC_RADIO_H
#define _SRC_RADIO_H

#include "1Defs.h"
#include "Storage.h"        // saveBindToNvs()
#include "Channels.h"       // decompress(), decompressedSize(), decodeChannelData()
#include "TxParams.h"       // readExtraParameters(), fillParamAck() — TX Rotorflight editing

//*********************************************************************
//  Data-rate name (for the self-test report)
//*********************************************************************

inline const char* dataRateName(rf24_datarate_e d) {
    switch (d) {
        case RF24_1MBPS:   return "1 Mbps";
        case RF24_2MBPS:   return "2 Mbps";
        case RF24_250KBPS: return "250 kbps";
        default:           return "?";
    }
}

//*********************************************************************
//  Radio1 self-test (runs once at boot)
//*********************************************************************
// Confirms SPI wiring, chip presence, and register read/write. Result lands
// in the rfTest global so /diagnostics can show "PASS" / "FAIL" with detail.

inline void runRadioSelfTest() {
    rfTest.ran = true;

    // Park ALL THREE radio slots' CSN HIGH and CE LOW before we touch
    // the SPI bus. Without this, slots 2 and 3 leave their CSN pins in
    // INPUT mode (default) — and nRF24L01+ has no internal pull-up on
    // CSN, so a floating CSN can drift LOW through PCB leakage. That
    // would select slots 2 and/or 3 *simultaneously* with slot 1 the
    // first time we drive SPI, multiple chips drive MISO at once, and
    // slot 1's self-test reads garbage → "radio 1 not present" even
    // though slot 1's hardware is perfectly fine. The symptom: one
    // radio installed = bind works; add a second physical radio = the
    // CSN floating wrecks slot 1's detection.
    pinMode(PIN_NRF_CSN,  OUTPUT); digitalWrite(PIN_NRF_CSN,  HIGH);
    pinMode(PIN_NRF_CSN2, OUTPUT); digitalWrite(PIN_NRF_CSN2, HIGH);
    pinMode(PIN_NRF_CSN3, OUTPUT); digitalWrite(PIN_NRF_CSN3, HIGH);
    pinMode(PIN_NRF_CE,   OUTPUT); digitalWrite(PIN_NRF_CE,   LOW);
    pinMode(PIN_NRF_CE2,  OUTPUT); digitalWrite(PIN_NRF_CE2,  LOW);
    pinMode(PIN_NRF_CE3,  OUTPUT); digitalWrite(PIN_NRF_CE3,  LOW);

    // Override variant defaults — route MISO off the BOOT-strap pin.
    SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, -1);
    delay(50);

    rfTest.beginOk = radio1.begin();
    if (rfTest.beginOk) {
        radio1.printDetails();
    } else {
        rfTest.verdict = "radio1.begin() failed — see wiring checklist";
        Serial.println("[rf] radio1.begin() FAILED — chip not responding on SPI");
        return;
    }

    rfTest.chipConnected = radio1.isChipConnected();

    radio1.setChannel(76);
    delayMicroseconds(150);
    rfTest.channelRead = radio1.getChannel();
    rfTest.channelOk   = (rfTest.channelRead == 76);

    radio1.setDataRate(RF24_250KBPS);
    delayMicroseconds(150);
    rf24_datarate_e dr = radio1.getDataRate();
    rfTest.dataRateRead = static_cast<uint8_t>(dr);
    rfTest.dataRateOk   = (dr == RF24_250KBPS);

    bool allOk = rfTest.beginOk && rfTest.chipConnected
              && rfTest.channelOk && rfTest.dataRateOk;
    rfTest.verdict = allOk
        ? "PASS — radio responds, registers writable, ready to receive"
        : "FAIL — see details (likely a wiring fault)";

    Serial.printf("[rf] radio1 begin=%d chip=%d ch=%d dr=%d  %s\n",
                  rfTest.beginOk, rfTest.chipConnected,
                  rfTest.channelOk, rfTest.dataRateOk,
                  rfTest.verdict);
}

//*********************************************************************
//  Probe each of the three radio slots (single / dual / triple PCB)
//*********************************************************************
// Probes slots 2 and 3 (slot 1 already covered by runRadioSelfTest). Each
// slot's presence is recorded independently — if slot 1 has failed but
// slot 3 still answers, swap-on-loss can use whichever radios actually
// respond. Slots that are absent are simply skipped by swapRadios().

inline bool probeRadioSlot(RF24& r, uint8_t cePin, uint8_t csnPin, uint8_t idxForLog) {
    pinMode(cePin,  OUTPUT);
    pinMode(csnPin, OUTPUT);
    digitalWrite(cePin,  LOW);
    digitalWrite(csnPin, HIGH);
    delay(5);
    if (!r.begin() || !r.isChipConnected()) {
        Serial.printf("[rf] radio%u not present\n", idxForLog);
        return false;
    }
    r.setChannel(76);
    delayMicroseconds(150);
    bool channelOk = (r.getChannel() == 76);
    Serial.printf("[rf] radio%u DETECTED, channel r/w %s\n",
                  idxForLog, channelOk ? "ok" : "FAIL");
    return channelOk;
}

inline void detectAllRadios() {
    // Slot 1 is the SPI-bench from runRadioSelfTest — read its verdict.
    // MUST include channelOk: a bare board with no nRF24 leaves MISO floating,
    // which often reads back as 0xFF. begin()/isChipConnected() are both fooled
    // by that (address-width 0xFF&3 = 3 looks "valid"), so without the channel
    // write/read-back test we'd hallucinate a radio — and then a phantom "TX
    // heard" at boot suppresses WiFi and no AP ever appears. The r/w test is the
    // robust discriminator (matches probeRadioSlot for slots 2/3).
    radioPresent[0] = rfTest.beginOk && rfTest.chipConnected && rfTest.channelOk;
    radioPresent[1] = probeRadioSlot(radio2, PIN_NRF_CE2, PIN_NRF_CSN2, 2);
    radioPresent[2] = probeRadioSlot(radio3, PIN_NRF_CE3, PIN_NRF_CSN3, 3);
    numRadiosPresent = (uint8_t)(radioPresent[0] + radioPresent[1] + radioPresent[2]);

    // currentRadio defaults to radio1; if it's missing, pick the first
    // slot that did respond so the receiver still works.
    if (!radioPresent[0]) {
        for (uint8_t i = 1; i < 3; i++) {
            if (radioPresent[i]) { currentRadio = radios[i]; activeRadioIdx = i + 1; break; }
        }
    }

    char buf[64];
    snprintf(buf, sizeof(buf), "Radios detected: %u (1:%s 2:%s 3:%s)",
             numRadiosPresent,
             radioPresent[0] ? "ok" : "-",
             radioPresent[1] ? "ok" : "-",
             radioPresent[2] ? "ok" : "-");
    events.add(buf);
    Serial.printf("[rf] %s\n", buf);
}

//*********************************************************************
//  Swap active radio (CE-line swap) — rotates through present slots only
//*********************************************************************
// Skips absent slots so a 3-slot PCB with one dead chip keeps cycling
// only the working two. With one radio there's nothing to swap to.

inline void swapRadios() {
    if (numRadiosPresent < 2) return;

    uint8_t startIdx = activeRadioIdx - 1;   // 0-based
    uint8_t nextIdx  = startIdx;
    for (uint8_t step = 0; step < 3; step++) {
        nextIdx = (nextIdx + 1) % 3;
        if (radioPresent[nextIdx]) break;
    }
    if (nextIdx == startIdx) return;         // nothing else present

    // (Active-time accounting is now done continuously in loop(), so there's
    // no per-swap banking to do here — loop() just starts crediting the new
    // active slot on its next pass.)
    currentRadio->stopListening();
    delayMicroseconds(150);
    currentRadio   = radios[nextIdx];
    activeRadioIdx = nextIdx + 1;
    currentRadio->startListening();
    delayMicroseconds(150);
    // Re-prime the ack-payload FIFO on the new active radio — the previous
    // one's queued payloads stay with it.
    loadNextAck();
    loadNextAck();
    loadNextAck();

    radioSwaps++;
    // Bill the FLIGHT for this swap only if it happened on a recently-live
    // link, after the connect grace, and outside BLE quarantine — bench
    // hunting and phone-induced desense are not the flight's fault. 2.5 s
    // horizon (was 1 s): matches the 'genuine failover' definition below —
    // Malcolm's 9m36s flight handed over R1→R2 yet billed ZERO swaps.
    // Unbilled-but-recent swaps leave a breadcrumb naming the reason.
    {
        uint32_t sinceLive = rx.lastMillis ? (uint32_t)(millis() - rx.lastMillis) : 0xFFFFFFFF;
        if (sinceLive < 2500 && linkStats.graceDone && !bleStatsQuarantine())
            linkStats.flightSwaps++;
        else if (sinceLive < 8000) {
            // One breadcrumb per 5 s: the dead-link hunt swaps once a second
            // for the whole 8 s window, which wrote 7 identical lines after
            // every TX-off (seen 0.9.551) — noise a pilot would read as a fault.
            static uint32_t lastCrumbMs = 0;
            if ((uint32_t)(millis() - lastCrumbMs) >= 5000) {
                lastCrumbMs = millis();
                char ub[40];
                snprintf(ub, sizeof(ub), "Swap unbilled (%s)",
                         !linkStats.graceDone ? "grace" : bleStatsQuarantine() ? "BT" : "stale link");
                events.add(ub);
            }
        }
    }
    lastRadioSwapMs = millis();
    // Only log genuine failovers (a packet arrived within the last ~2 s, so the
    // link was live and this swap is a real response to a glitch). Dead-link
    // probe swaps are silent — otherwise they'd flood the blackbox + serial.
    if ((uint32_t)(millis() - rx.lastMillis) < 2000) {
        char buf[60];
        snprintf(buf, sizeof(buf), "Swapped to radio %u", activeRadioIdx);
        events.add(buf);
        Serial.printf("[rf] %s\n", buf);
    }
}

//*********************************************************************
//  Build the next ack payload
//*********************************************************************
// Mirrors v1's LoadAckPayload(). First MAC_ACK_THRESHOLD acks carry our
// 8-byte board ID (so TX can identify us); after that we rotate items 0..35.
// Items we don't have sensors for return zeros — v1 ignores zero values
// cleanly. byte[0] also carries the FHSS HOP flag (high bit) when it's time
// to switch channel; byte[5] carries the FHSS table index so the TX knows
// where we're going.

// Active seconds for radio slot idx (0..2). radioActiveMs[] is accrued every
// loop in main.cpp for whichever radio is currently active, so this just reads
// it back. That keeps the active radio's counter ticking once/second the whole
// time we're running — the old "live-delta" form left BOTH counters frozen on a
// solid (no-swap) link, which is wrong (V1 always increments one).
inline uint32_t radioElapsedSec(uint8_t idx) {
    return radioActiveMs[idx] / 1000;
}

inline void loadNextAck() {
    uint8_t ack[ACK_PAYLOAD_BYTES] = {0};

    // MAC-delivery window (mirrors v1's LoadAckPayload). The v1 TX's pre-match
    // parser reads ack slots 0/1 as the two halves of our 8-byte board ID on
    // *every* packet until it has assembled a full value and matched the model.
    // So we must put the MAC on slots 0/1 densely at the START of each
    // connection — but ONLY at the start: once the TX has matched it expects
    // *telemetry* in the acks. A TX that keeps getting MAC instead of telemetry
    // hiccups the link about every 10-15 s (a momentary RX-loss that flashes
    // every channel to zero in the FC) and never shows the RX version or the
    // per-radio "active time" counters. So: send the MAC for the first
    // MAC_ACK_THRESHOLD acks of each connection (dense — a half on every ack,
    // alternating, so both halves land within milliseconds even across radio
    // swaps), then hand over to the telemetry rotation for the rest of the
    // connection. Re-armed on every fresh connection: a >500 ms ack gap resets
    // macAcksSent below, so each reconnection re-delivers the MAC, exactly like
    // v1's reset-on-link-loss.
    //
    // HISTORY: 0.9.x briefly broadcast the MAC until a stick moved
    // ("beingFlown"), to keep feeding the TX's "Model IDs" identify screen
    // (which holds the TX permanently unmatched). That starved telemetry the
    // whole time you were connected-but-not-flying — the cause of the 10-15 s
    // zero-flash and the frozen version/counters. Steady-state telemetry is
    // flight-critical and wins; the identify screen re-reads the MAC on the next
    // (re)connect. macAcksSent is counted only on MAC acks actually written, so
    // the threshold is robust to the extra loadNextAck() calls swapRadios makes.
    static uint32_t lastAckEntryMs = 0;
    const uint32_t  now            = millis();
    if (lastAckEntryMs == 0 || (uint32_t)(now - lastAckEntryMs) > 500) {
        macAcksSent = 0;          // fresh connection → reset diagnostic counter
    }
    lastAckEntryMs = now;
    const bool inMacWindow = (macAcksSent < MAC_ACK_THRESHOLD);
    idBroadcasting = inMacWindow;

    // FHSS hop decision — suppressed during the MAC window so we never advance
    // the channel index without telling the TX (the window keeps ack[5] = 0).
    bool hopThisAck = false;
    if (fhssEnabled && !inMacWindow && !hopPending &&
        (uint32_t)(millis() - lastHopMs) >= HOP_TIME_MS) {
        nextChannelIdx = (nextChannelIdx + 1) % 83;
        hopThisAck = true;
        // Stamp the DECISION, not just the execution (also gated on !hopPending
        // above): swapRadios()/tryBind() preload 3 acks back-to-back, and with
        // HOP_TIME_MS only 8 ms each preload used to advance nextChannelIdx
        // again — FIFO acks promising N+1/N+2/N+3 while we tune only to N+3,
        // desyncing the TX. Latent until fhssEnabled is turned on.
        lastHopMs = millis();
    }

    if (inMacWindow) {
        // MAC ack format (v1 SendMacAddress) — alternate the two 4-byte halves.
        ackByteZero = ackByteZero ? 0 : 1;        // toggles 0,1,0,1 → which MAC half
        ack[0] = ackByteZero;                     // HOP bit stays clear during MAC window
        uint8_t base = ackByteZero ? 4 : 0;
        ack[1] = boardMac[base + 0];
        ack[2] = boardMac[base + 1];
        ack[3] = boardMac[base + 2];
        ack[4] = boardMac[base + 3];
        if (macAcksSent < 0xFFFFFFFFu) macAcksSent++;  // kept for state.json / diagnostics
    } else {
        // Telemetry rotation (v1 LoadAckPayload switch, simplified). Reached
        // only after the MAC window, by which point a TX that has our model
        // saved has matched and stopped reading slots 0/1 as the MAC.
        if (++telemetryItem > MAX_TELEMETRY_ITEM) telemetryItem = 0;
        // V1 idle-skip (LoadAckPayload): 25-30/32-34 are MSP param slots. The
        // TX starts reading the moment its screen opens — BEFORE its "send
        // now" request has reached us — and the global-governor screen latches
        // whatever arrives (an all-zero slot counts as "received") then stops
        // listening, so the real bytes moments later are ignored. V1 never
        // emits these slots unless actively serving; neither may we. Gate on
        // the read window being open AND the requested block having valid
        // bytes; otherwise fall through to 31 / 35 exactly like V1.
        if ((telemetryItem >= 25 && telemetryItem <= 30) ||
            (telemetryItem >= 32 && telemetryItem <= 34)) {
            uint8_t probe[ACK_PAYLOAD_BYTES] = {0};
            if (!paramReadWindowOpen() || !fillParamAck(telemetryItem, probe))
                telemetryItem = (telemetryItem <= 30) ? 31 : 35;
        }
        // Item 37 carries phone-true LOCAL time so the TX can correct its own
        // RTC (Malcolm's idea: most models never carry GPS, but every model
        // meets a phone). ONLY when this boot's clock came from a phone —
        // never echo back time we learned from the TX itself.
        if (telemetryItem == 37 && !epochFromPhone) telemetryItem = 0;
        ack[0] = telemetryItem;
        bool versionCase = false;

        if (fltPardonAnnounceLeft > 0) {
            // Flight-save imminent: override the rotation with item 38 so the
            // pardon reaches the TX BEFORE the flash-erase stall it excuses.
            // Old transmitters ignore the item (default case).
            fltPardonAnnounceLeft--;
            ack[0] = 38;
            packU32(ack, fltPardonMsToSend);   // 3000 = pardon; 0 = save done, unignore
        }
        else switch (telemetryItem) {
            case 0:
                // Mirror v1's SendVersionNumberToAckPayload: byte 1 = active
                // transceiver, then the firmware version, so the TX shows both.
                ack[1] = activeRadioIdx;
                ack[2] = RXV2_V_MAJOR;
                ack[3] = RXV2_V_MINOR;
                ack[4] = RXV2_V_MINIMUS;
                ack[5] = (uint8_t)RXV2_V_EXTRA;
                versionCase = true;
                break;
            case 1:
                packU32(ack, rx.packets);  // SuccessfulPackets (v1 parity)
                break;
            case 2:   packU32(ack, radioSwaps);                     break;  // RadioSwaps
            case 3:   packU32(ack, radioElapsedSec(0));             break;  // Transceiver 1 active time (sec)
            case 4:   packU32(ack, radioElapsedSec(1));             break;  // Transceiver 2 active time (sec)
            case 36:  packU32(ack, radioElapsedSec(2));             break;  // Transceiver 3 active time (sec) — matches TX's RX3TotalTime handler
            case 5: {
                // Battery voltage. Prefer FC's reported voltage; fall back to 0 if
                // no CRSF telemetry. v1 TX has a backward-compat quirk: if it
                // receives above 6S max it assumes 12S pre-halved and ×2. We pre-halve.
                constexpr float V_6S_MAX = 25.2f;        // 6 × 4.2 V
                // Prefer the receiver's own divider (wired deliberately) over
                // FC-reported volts; fall back to the FC, then 0.
                // The V1 TX screen gets the EXTRA-slow copy (vbatVoltsTx) so
                // the number sits still up there; the app/blackbox use the
                // responsive vbatVolts elsewhere (Malcolm 2026-08-21).
                float v = (vbatGpio() && vbatVoltsTx > 0.5f) ? vbatVoltsTx
                          : ((fcTelem.valid && fcTelem.fcBattVolts > 0.1f) ? fcTelem.fcBattVolts : 0.0f);
                float vTx = (v > V_6S_MAX) ? (v * 0.5f) : v;
                packF32(ack, vTx);
                break;
            }
            case 6:   packF32(ack, 0.0f);                           break;  // baro altitude
            case 7:   packF32(ack, 0.0f);                           break;  // baro temperature
            case 19:  packF32(ack, 0.0f);                           break;  // rate of climb
            case 20: {
                // Head speed (rotor RPM) — motor RPM from the FC's CRSF RPM frame
                // divided by the user's gear ratio (1.0 = direct drive). Matches
                // v1 (SendIntToAckPayload(RotorRPM) with RotorRPM = motorRPM/Ratio).
                float hs = (gearRatio > 0.1f) ? (fcTelem.fcMotorRPM / gearRatio) : (float)fcTelem.fcMotorRPM;
                packU32(ack, (uint32_t)(hs + 0.5f));
                break;
            }
            case 21:
                // Battery current (Rotorflight). Forward FC's measured current.
                if (fcTelem.valid) packF32(ack, fcTelem.fcBattAmps);
                break;
            case 22:
                // Battery capacity used (mAh, Rotorflight).
                if (fcTelem.valid) packF32(ack, (float)fcTelem.fcBattMah);
                break;
            case 23:
                // Receiver type index into the TX's Rx_type[] table:
                //   0=Unknown, 1=TRX:1 PWM:8, 2=TRX:2 PWM:8, 3=TRX:2 PWM:11,
                //   4=TRX:1 V2,  5=TRX:2 V2,  6=TRX:3 V2
                // RXV2 reports 4 / 5 / 6 based on radios actually detected
                // (e.g. a 3-slot PCB with one dead chip reports as 2-radio).
                ack[1] = (uint8_t)(3 + numRadiosPresent);  // 1→4, 2→5, 3→6
                break;
            case 24:  packF32(ack, fcTelem.fcEscTempC);             break;  // ESC temp (CRSF temperature frame 0x0D)
            case 25: case 26: case 27: case 28:
            case 29: case 30: case 32: case 33: case 34:
                // Rotorflight parameter blocks streamed to the TX (rates/PIDs/
                // governor). fillParamAck loads ack[1..4] from the cached block
                // when the matching read is active; otherwise leaves them zero
                // (the TX ignores param slots unless it is reading that block).
                fillParamAck(telemetryItem, ack);
                break;
            case 31:
                // Rotorflight version for the TX (its RotorFlight_V): 0 none, 1 = RF 2.2,
                // 2 = RF 2.3+. The TX uses this to (a) enable the Rotorflight screens and
                // (b) choose the rate-display factor table — sending a flat "1" forced the
                // 2.2 factors and mis-scaled 2.3 rates. Falls back to a 0/1 telemetry flag
                // if the FC is only telemetry-detected (API not yet probed).
                {
                    uint8_t rfv = rotorflightTxVersion();
                    if (rfv == 0 && fcTelem.valid) rfv = 1;
                    packU32(ack, rfv);
                }
                break;
            case 35:  packU32(ack, buildDays);                      break;  // BuildAge in days since 2020-01-01
            case 37:  // phone-true LOCAL wall time (epoch s) — TX corrects its RTC from this
                packU32(ack, (uint32_t)((int64_t)epochNowS() + (int64_t)tzOffsetMin * 60));
                break;
            default:  break;
        }
        if (hopThisAck) {
            ack[0] |= 0x80;
            hopPending = true;
        }
        if (!versionCase) {
            ack[5] = nextChannelIdx;
        }
    }

    if (currentRadio->writeAckPayload(V1_PIPE_NUMBER, ack, ACK_PAYLOAD_BYTES)) {
        rx.acksWritten++;
    }
}

//*********************************************************************
//  Try to extract a bind from an incoming packet
//*********************************************************************
// Mirrors v1's GetNewPipe(). When unbound and the packet looks like a bind
// frame (channels 1..5 carry the new 5-byte pipe address), extract the pipe
// and re-open the reading pipe on both radios.

inline void tryBind(const uint8_t* payload, uint8_t size) {
    if (bindState.bound)   return;
    if (size < 10)    return;
    uint16_t mask = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
    if ((mask & 0x003E) != 0x003E) return;       // channels 1..5 must all be flagged

    bindState.attempts++;

    uint16_t compressed[16] = {0};
    uint8_t  nDataBytes = size - 2;
    for (uint8_t i = 0; i + 1 < nDataBytes; i += 2) {
        compressed[i / 2] = (uint16_t)payload[2 + i] | ((uint16_t)payload[2 + i + 1] << 8);
    }

    uint16_t raw[24] = {0};
    decompress(raw, compressed, decompressedSize(size));

    uint16_t channel[16] = {0};
    uint8_t p = 0;
    for (uint8_t i = 0; i < 16; ++i) {
        if (mask & (1u << i)) {
            channel[i] = raw[p++];
        }
    }

    // v1 GetNewPipe reverses the byte order when copying into the pipe address.
    for (uint8_t i = 0; i < 5; ++i) {
        bindState.pipe[4 - i] = (uint8_t)(channel[i + 1] & 0xff);
    }

    // Switch the radio's reading pipe to the new address, and flip from
    // silent (autoACK off, no ack-payload FIFO) back to noisy now that
    // we know who we're talking to. Stay on channel 82.
    currentRadio->stopListening();
    delayMicroseconds(150);
    currentRadio->flush_tx();
    currentRadio->flush_rx();
    currentRadio->enableAckPayload();
    currentRadio->setAutoAck(true);
    currentRadio->openReadingPipe(V1_PIPE_NUMBER, bindState.pipe);
    currentRadio->startListening();
    delayMicroseconds(150);
    // Mirror the new pipe + noisy config to every OTHER present radio so
    // any subsequent swap lands on a slot already configured for the bind.
    for (uint8_t i = 0; i < 3; i++) {
        if (!radioPresent[i] || radios[i] == currentRadio) continue;
        radios[i]->stopListening();
        delayMicroseconds(150);
        radios[i]->flush_tx();
        radios[i]->flush_rx();
        radios[i]->enableAckPayload();
        radios[i]->setAutoAck(true);
        radios[i]->openReadingPipe(V1_PIPE_NUMBER, bindState.pipe);
        // Other slots stay in standby (CE low) — only currentRadio has CE high.
    }

    loadNextAck();
    loadNextAck();
    loadNextAck();

    bindState.bound       = true;
    bindState.boundMillis = millis();
    saveBindToNvs();

    char buf[80];
    snprintf(buf, sizeof(buf), "Bound to TX, pipe %02X %02X %02X %02X %02X",
             bindState.pipe[0], bindState.pipe[1], bindState.pipe[2], bindState.pipe[3], bindState.pipe[4]);
    events.add(buf);

    Serial.printf("[bind] new pipe %02X %02X %02X %02X %02X (after %u attempts)\n",
                  bindState.pipe[0], bindState.pipe[1], bindState.pipe[2], bindState.pipe[3], bindState.pipe[4],
                  (unsigned)bindState.attempts);
}

//*********************************************************************
//  Configure radio(s) for v1-compatible listen
//*********************************************************************
// Mirrors v1's ConfigureRadio(). Both radios get identical settings — Radio1
// active (CE high), Radio2 in standby (CE low) so only one is receiving at
// any moment.

inline void radioBeginListenV1() {
    // Was guarded on rfTest.beginOk (radio1-specific). That gated out the
    // valid case where slot 1 is empty but slot 2 or 3 has a working chip
    // — nothing got configured and the TX couldn't connect. Now we only
    // bail when literally zero radios are present.
    if (numRadiosPresent == 0) return;

    // Stay silent on the air while unbound — no auto-ack, no ack-payload
    // FIFO. The chip is then indistinguishable from "no receiver present"
    // to a TX that's scanning. Required because the V1 TX firmware has a
    // latent bug: when it receives autoACK replies on the default pipe
    // carrying our board-MAC payload (dynamic length, V2-specific), its
    // parser locks up and the TX becomes unresponsive until the battery
    // is disconnected. V1 receivers don't trigger this because they don't
    // send the same first-N-acks-carry-MAC payload format. tryBind() flips
    // both flags back on for every present radio the moment a real bind
    // packet arrives, so the normal bind handshake still works.
    const bool isBound = bindState.bound;
    auto configureOne = [isBound](RF24& r, const uint8_t* pipe) {
        r.setPALevel(RF24_PA_MAX);
        r.setDataRate(RF24_250KBPS);
        if (isBound) r.enableAckPayload();
        r.setRetries(2, 2);
        r.enableDynamicPayloads();
        r.setAddressWidth(5);
        r.setCRCLength(RF24_CRC_16);
        r.setAutoAck(isBound);
        r.maskIRQ(1, 1, 1);
        r.setChannel(V1_RECOVERY_CH);
        r.openReadingPipe(V1_PIPE_NUMBER, pipe);
    };
    const uint8_t* pipe = bindState.bound ? bindState.pipe : V1_DEFAULT_PIPE;
    for (uint8_t i = 0; i < 3; i++) {
        if (radioPresent[i]) configureOne(*radios[i], pipe);
    }
    // Start listening on the first present slot — usually radio1, but if it
    // was missing at boot the active pointer was already pointed elsewhere
    // by detectAllRadios(), so honour that.
    if (!radioPresent[0]) {
        for (uint8_t i = 0; i < 3; i++) {
            if (radioPresent[i]) { currentRadio = radios[i]; activeRadioIdx = i + 1; break; }
        }
    } else {
        currentRadio = &radio1;
        activeRadioIdx = 1;
    }
    currentRadio->startListening();
    radioActiveStartMs = millis();   // start counting time on the initial active radio
    Serial.printf("[rf] %s pipe %02X %02X %02X %02X %02X on channel %u %s\n",
                  bindState.bound ? "bound" : "default",
                  pipe[0], pipe[1], pipe[2], pipe[3], pipe[4], V1_RECOVERY_CH,
                  isBound ? "(noisy)" : "(silent — autoACK off)");
    (void)V1_DEFAULT_PIPE;

    if (isBound) {
        // Pre-load ack-payload FIFO so the very first incoming packet's ACK
        // already carries telemetry bytes. Skipped while unbound — see the
        // 0.9.66 debug comment above configureOne.
        loadNextAck();
        loadNextAck();
        loadNextAck();
    }

    lastHopMs = millis();
}

//*********************************************************************
//  Per-loop poll for incoming packets
//*********************************************************************

// Flight telemetry sampler — one sample/second while connected + FC telemetry is
// valid. Reset on a fresh connection (new flight). Call from loop().
inline void telemetrySampleTick() {
    const uint32_t now = millis();
    // A fresh connection restarts the log so it holds only the current flight.
    static uint32_t lastConnStart = 0xFFFFFFFF;
    if (linkStats.connStartMs != lastConnStart) {
        lastConnStart = linkStats.connStartMs;
        teleCount = 0; teleHead = 0; teleLastSampleMs = now;
    }
    if ((uint32_t)(now - teleLastSampleMs) < 1000) return;
    teleLastSampleMs = now;
    bool connected = (rx.lastMillis != 0) && ((uint32_t)(now - rx.lastMillis) < 2000);
    if (!connected) return;
    // Skip the first moments of a connection: the battery ADC's first reads
    // after boot/attenuation setup can be wildly high (a 25 V spike on an 11 V
    // pack graphed at the lodge) — two skipped samples cost nothing.
    if ((uint32_t)(now - linkStats.connStartMs) < 2500) return;
    // A plane with plain servos has NO flight controller, so fcTelem never
    // goes valid — this sampler used to skip EVERY second of such a flight:
    // the graph stayed empty and, worse, teleCount stayed 0, so
    // saveFlightToLittleFS refused to save and the flight list said
    // "none yet" forever (Malcolm's field session, 2026-07-23). Now we log a
    // sample every second while connected: FC-only fields go to zero when
    // absent, and battery volts fall back to the receiver's own divider
    // (vbatVolts) — planes get a real voltage trace AND saveable flights.
    TeleSample& s = teleRing[teleHead];
    if (fcTelem.valid) {
        // ESC temp is a SIGNED deci-degC CRSF field — clamp before the uint8_t
        // store (negative float → unsigned is UB; a frosty morning must log 0°,
        // not garbage).
        float tc = fcTelem.fcEscTempC + 0.5f;
        s.escC = (tc < 0.0f) ? 0u : (tc > 255.0f) ? 255u : (uint8_t)tc;
        uint32_t hs = (gearRatio > 0.1f) ? (uint32_t)(fcTelem.fcMotorRPM / gearRatio + 0.5f) : fcTelem.fcMotorRPM;
        s.headRpm = (hs > 65535u) ? 65535u : (uint16_t)hs;
        float cv = fcTelem.fcBattVolts * 100.0f + 0.5f;
        s.cV = (cv > 65535.0f) ? 65535u : (uint16_t)cv;
        float da = fcTelem.fcBattAmps * 10.0f + 0.5f;
        s.dA = (da < 0.0f) ? 0u : (da > 65535.0f) ? 65535u : (uint16_t)da;
    } else {
        s.escC = 0; s.headRpm = 0; s.dA = 0;
        float cv = vbatVolts * 100.0f + 0.5f;               // RX divider, 0 if none fitted
        s.cV = (cv <= 0.5f) ? 0u : (cv > 65535.0f) ? 65535u : (uint16_t)cv;
    }
    teleHead = (uint16_t)((teleHead + 1) % TELE_RING);
    if (teleCount < TELE_RING) teleCount++;
}

inline void radioPoll() {
    uint8_t pipe = 0;
    if (currentRadio->available(&pipe)) {
        uint8_t size = currentRadio->getDynamicPayloadSize();
        if (size > 0 && size <= 32) {
            currentRadio->read(rx.lastBytes, size);
            rx.lastPayload = size;
            if (size > rx.maxPayload) {
                rx.maxPayload = size;
                memcpy(rx.maxBytes, rx.lastBytes, size);
            }
        } else {
            // Corrupted R_RX_PL_WID (size 0 or >32): flush and BAIL OUT of the
            // whole handler. Falling through used to hand the bogus `size`
            // (e.g. 255) to decodeChannelData/tryBind/readExtraParameters,
            // which then wrote ~200 bytes past their stack buffers — a single
            // RF glitch could crash the receiver MID-FLIGHT. It also isn't a
            // packet: don't count it in link stats or bump rx.lastMillis.
            currentRadio->flush_rx();
            rx.lastPayload = 0;
            return;
        }
        // --- per-flight link statistics (gaps, frame rate, histogram) ---
        {
            uint32_t nowMs = millis();
            uint32_t nowUs = micros();
            if (rx.lastMillis == 0 || (uint32_t)(nowMs - rx.lastMillis) >= FLIGHT_SAVE_AFTER_MS) {
                // A NEW flight starts only after the link was gone long enough
                // for the previous one to have been saved (same threshold as
                // maybeSaveFlight). A shorter mid-flight dropout — the very
                // event the blackbox exists for — continues the SAME flight:
                // stats + telemetry ring keep accumulating, and the dropout
                // shows up honestly as the longest gap. (Was >500 ms, which
                // wiped the whole recording on any brief failsafe/reconnect.)
                linkStats.connStartMs = nowMs;
                linkStats.packets  = 0; linkStats.maxGapUs = 0; linkStats.maxGapAtMs = 0;
                linkStats.gapSumUs = 0; linkStats.gapCount = 0;
                linkStats.expectedGapUs = 0;   // re-learn the spacing (solo vs buddy-box may have changed)
                linkStats.secWindowStartMs = 0;
                linkStats.secWindowCount   = 0;
                for (uint8_t i = 0; i < 6; ++i) linkStats.hist[i] = 0;
                for (auto &g : linkStats.recent) g = {};
                linkStats.recentIdx = 0;
                linkStats.paramOps = 0;
                linkStats.swapsAtStart = radioSwaps;
                linkStats.swapsAtLive  = radioSwaps;
                linkStats.flightSwaps  = 0;
                linkStats.graceDone    = false;   // baselines re-snap when the handshake grace expires
                for (uint8_t i = 0; i < 3; ++i) {
                    linkStats.radioMsAtStart[i] = radioActiveMs[i];
                    linkStats.radioMsAtLive[i]  = radioActiveMs[i];
                }
            } else if ((uint32_t)(nowMs - linkStats.connStartMs) >= LINK_STATS_GRACE_MS) {
                // Gaps only count once the connection is 3 s old (Malcolm,
                // 2026-07-23; 2 s left a 55 ms straggler). The V1 TX
                // 'hesitates' right after first contact — bind confirm /
                // model-ID handshake before its green light — and V1 itself
                // wipes its stats 4-6 s after the green light for exactly
                // this reason (main.cpp: 'clear the long gaps that might
                // occur while binding'). Handshake ritual, not link quality.
                if (!linkStats.graceDone) {
                    // The flight's stats officially begin HERE: re-baseline
                    // the swap count and per-radio time so handshake churn
                    // (the TX pausing makes us hunt across both radios)
                    // isn't billed to the flight.
                    linkStats.graceDone     = true;
                    linkStats.swapsAtStart  = radioSwaps;
                    linkStats.swapsAtLive   = radioSwaps;
                    linkStats.flightSwaps   = 0;
                    for (uint8_t i = 0; i < 3; ++i) {
                        linkStats.radioMsAtStart[i] = radioActiveMs[i];
                        linkStats.radioMsAtLive[i]  = radioActiveMs[i];
                    }
                }
                uint32_t gapUs = nowUs - linkStats.lastPktUs;
                // Expected slot spacing, measured THE V1 WAY (Malcolm): count
                // packets across ~1-second windows and divide — exactly how
                // his TX computes its ack rate, so the two ends must agree.
                // Interval statistics failed twice here: a mean-EMA absorbed
                // retry delays (483 vs 503), a floor tracker collapsed into
                // FIFO read-bursts (two packets drained in one loop pass
                // look microseconds apart). Counting is immune to all of it.
                // Windows pause during BLE quarantine — desense-eaten packets
                // must not dilute the rate.
                if (bleStatsQuarantine()) {
                    linkStats.secWindowStartMs = 0;
                    linkStats.secWindowCount   = 0;
                } else if (!linkStats.secWindowStartMs) {
                    linkStats.secWindowStartMs = nowMs;
                    linkStats.secWindowCount   = 1;
                } else {
                    linkStats.secWindowCount++;
                    uint32_t elapsed = nowMs - linkStats.secWindowStartMs;
                    if (elapsed >= 1000) {
                        if (linkStats.secWindowCount >= 100) {
                            uint32_t est = (uint32_t)((uint64_t)elapsed * 1000ULL
                                                      / linkStats.secWindowCount);
                            linkStats.expectedGapUs = linkStats.expectedGapUs
                                ? (linkStats.expectedGapUs * 3 + est) / 4 : est;
                        }
                        linkStats.secWindowStartMs = nowMs;
                        linkStats.secWindowCount   = 0;
                    }
                }
                // A packet is only LATE by the part beyond the expected
                // spacing — an 8 ms wait at 2 ms spacing is a 6 ms lateness,
                // and ordinary on-time packets are not "gaps" at all
                // (Malcolm 2026-07-27: the <4 ms bucket was just counting
                // every normal packet). Below gapMinMs late: not recorded.
                uint32_t lateUs = (linkStats.expectedGapUs && gapUs > linkStats.expectedGapUs)
                                  ? gapUs - linkStats.expectedGapUs : 0;
                // BLE quarantine: while a phone is attached (or just around
                // connect/disconnect), deaf spells are OUR BT radio desensing
                // the nRF24s — never billed to the RF link.
                if (lateUs >= (uint32_t)gapMinMs * 1000UL && !bleStatsQuarantine()) {
                    if (lateUs > linkStats.maxGapUs) { linkStats.maxGapUs = lateUs; linkStats.maxGapAtMs = nowMs; }
                    linkStats.gapSumUs += lateUs; linkStats.gapCount++;
                    uint32_t lateMs = lateUs / 1000;
                    uint8_t b = lateMs < 8 ? 0 : lateMs < 16 ? 1 : lateMs < 32 ? 2 : lateMs < 64 ? 3 : lateMs < 150 ? 4 : 5;
                    linkStats.hist[b]++;
                    // EVERY counted gap enters the ring so the shutdown trim
                    // can drop trailing artifacts of ANY size — the V1 TX's
                    // power-off ritual also produces sub-150 ms hesitations
                    // (52 ms at 00:00:54 in Malcolm's lodge flight). Since
                    // only >=threshold lateness is recorded at all now, the
                    // old flood-of-2ms-entries problem cannot recur.
                    linkStats.recent[linkStats.recentIdx] = { lateUs, nowMs, b };
                    linkStats.recentIdx = (uint8_t)((linkStats.recentIdx + 1) % 6);
                    if (lateUs >= SHUTDOWN_TRIM_MIN_US) {
                        // Blackbox breadcrumb: a failsafe-class gap on a LIVE
                        // link always deserves an explanation — its neighbours
                        // in the event log show what the chip was doing then.
                        char gb[32];
                        snprintf(gb, sizeof(gb), "Link late %lu ms", (unsigned long)lateMs);
                        events.add(gb);
                    }
                }
            }
            linkStats.lastPktUs = nowUs;
            linkStats.packets++;
        }

        rx.packets   += 1;
        rx.lastMillis = millis();

        // tryBind switches pipes and pre-loads acks itself if it fires.
        if (!bindState.bound) {
            tryBind(rx.lastBytes, size);
        } else {
            // ChannelBitMask == 0 marks a PARAMETER packet (Rotorflight edits
            // from the TX), not channel data — route it to the param parser.
            uint16_t mask = (size >= 2) ? ((uint16_t)rx.lastBytes[0] | ((uint16_t)rx.lastBytes[1] << 8)) : 0xFFFF;
            if (mask == 0) readExtraParameters(rx.lastBytes, size);
            else           decodeChannelData(rx.lastBytes, size);
        }

        loadNextAck();

        // If we just told the TX to hop, hop ourselves now so we're both on
        // the new channel when the next packet flies (v1 UseReceivedData).
        if (hopPending) {
            hopPending = false;
            currentRadio->stopListening();
            delayMicroseconds(100);
            currentRadio->setChannel(FHSS_CHANNELS[nextChannelIdx]);
            currentRadio->startListening();
            delayMicroseconds(100);
            lastHopMs = millis();
        }
    }
}

#endif // _SRC_RADIO_H
