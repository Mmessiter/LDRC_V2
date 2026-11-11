// ElrsCrsf.h - an ExpressLRS transmitter module INSIDE the transmitter, driven by CRSF (Malcolm, 11 Nov 2026: "My vote is
// for ELRS, internally, switchable, and by serial link so that we get a higher frame rate and telemetry ... maybe we can
// address this by soldering one wire to the Teensy?").
//
// THE WIRE. Teensy 4.1 pin 24 is Serial6's transmit pin, and on the main board its pad goes nowhere (the board's netlist,
// Circuits/Transmitter - CADCAM: T1-24 is on the "no connection" net). One wire from it, through a ~1 kOhm resistor (the
// Teensy's pins do not take 5 V), to the module's signal pin. A module bay's CRSF line is ONE wire used both ways, and the
// Teensy core does exactly that (SERIAL_HALF_DUPLEX: the receiver listens on the transmit pin between frames, and pin 25,
// Serial6's own receive pin, is left alone - it belongs to a switch). Ground, and the battery's 6.5-8.4 V, from the
// TX_MODULE header; that header's own signal pin (Teensy pin 6, the old PPM) is not touched.
//
// WHAT THE MODULE EXPECTS (read from ExpressLRS's source, src/lib/Handset/CRSFHandset.cpp, 11 Nov 2026): frames that start
// with 0xEE (its address) or 0xC8, a good CRC, and enough of them, or it looks for us at its next baud rate and polarity
// (400000 first, then 115200, 5250000, 3750000, 1870000, 921600, 2250000; inverted and not). Its own frames to us start
// with 0xC8. Every 200 ms it says its packet interval and how early or late our frames arrive (a 0x3A frame, subcommand
// 0x10, both in tenths of a microsecond).
//
// PHASE 1 = THE BENCH TEST, in TEST BUILDS ONLY (-DELRS_TEST, flashed to one transmitter; never in a release): the
// channels the LDRC link sends (SendBuffer, 500..2500 us) also go out as CRSF channel frames, at the module's own packet
// interval once it has said it; what the module sends back (its link statistics, the receiver's telemetry, its timing) is
// read and written to the log every 5 s. The LDRC link is untouched, so BOTH radios transmit: bench only, blades off.
// Phase 2 (a model setting, LDRC's radio quiet while ELRS flies, the module's power switched by pin 10, the telemetry in
// the usual front-screen boxes) comes after the bench test says the wire and the frames are right.
// TO REMOVE IT (Malcolm, 11 Nov 2026: "In case of unexpected failure, please do the code in such a way that if necessary,
// it could be easily removed again!"): delete this file, dev/test_elrs, and the lines marked ELRS in src/main.cpp (each
// inside #ifdef ELRS_TEST; dev/test_elrs lists them all and fails if any ELRS line is found elsewhere). Nothing else in
// the transmitter knows of ELRS, and a release build does not contain it.
#pragma once
#include <stdint.h>
#include <string.h>

// ELRS-CRSF-BEGIN (dev/test_elrs/test_elrs.py compiles this block on the Mac)
namespace ElrsCrsf
{
constexpr uint8_t ADDR_MODULE = 0xEE;   // CRSF_ADDRESS_CRSF_TRANSMITTER: the module - where our channel frames go
constexpr uint8_t ADDR_HANDSET = 0xEA;  // CRSF_ADDRESS_RADIO_TRANSMITTER: us
constexpr uint8_t SYNC_BYTE = 0xC8;     // the module starts its frames to us with this (CRSFHandset.cpp: data[0] = CRSF_SYNC_BYTE)
constexpr uint8_t T_BATTERY = 0x08, T_RPM = 0x0C, T_TEMP = 0x0D, T_LINK_STATS = 0x14, T_RC = 0x16, T_ATTITUDE = 0x1E,
                  T_FLIGHT_MODE = 0x21, T_HANDSET = 0x3A;
constexpr uint8_t SUB_TIMING = 0x10;    // CRSF_HANDSET_SUBCMD_TIMING
constexpr uint8_t RC_FRAME_LEN = 26;    // address, length 24, type, 22 bytes of channels, CRC
constexpr uint8_t MAX_FRAME = 64;       // a CRSF frame is at most 64 bytes, its length byte at most 62
constexpr uint32_t DEFAULT_PERIOD_US = 4000;  // 250 Hz until the module has told us its interval
constexpr uint32_t TIMING_FRESH_MS = 1000;    // its interval counts this long (it repeats it every 200 ms)

// CRC-8/DVB-S2 (polynomial 0xD5), over the type and the payload - the same as the receiver's crsfCrc8 (RXV2 Output.h).
inline uint8_t crc8(const uint8_t *d, uint8_t n)
{
    uint8_t crc = 0;
    for (uint8_t i = 0; i < n; ++i)
    {
        crc ^= d[i];
        for (uint8_t b = 0; b < 8; ++b)
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0xD5) : (uint8_t)(crc << 1);
    }
    return crc;
}
// Microseconds to CRSF's 11-bit value: EXACTLY the receiver's rc11bit (RXV2 Output.h), so Rotorflight sees the same
// microseconds whichever link carried them: 1000 -> 173, 1500 -> 992, 2000 -> 1811, clamped to 172..1811.
inline uint16_t usToTicks(uint16_t us)
{
    long v = ((long)us - 1500) * 819L / 500L + 992L;
    if (v < 172) v = 172;
    if (v > 1811) v = 1811;
    return (uint16_t)v;
}
// The 16 channels as one CRSF channel frame to the module: 11 bits each, the lowest bits first.
inline void buildRcFrame(const uint16_t *us, uint8_t *out)
{
    out[0] = ADDR_MODULE;
    out[1] = 24;   // type + 22 + CRC
    out[2] = T_RC;
    uint32_t bits = 0;
    uint8_t nbits = 0, k = 3;
    for (uint8_t c = 0; c < 16; ++c)
    {
        bits |= ((uint32_t)usToTicks(us[c]) & 0x7FFu) << nbits;
        nbits += 11;
        while (nbits >= 8)
        {
            out[k++] = (uint8_t)(bits & 0xFFu);
            bits >>= 8;
            nbits -= 8;
        }
    }
    out[25] = crc8(&out[2], 23);
}

// What the module tells us. Each part has the millis() it last came (0 = never).
struct Telemetry
{
    // link statistics (0x14): the receiver's view of us (up) and ours of it (down)
    int16_t upRssi1 = 0, upRssi2 = 0;   // dBm (negative)
    uint8_t upLq = 0;                   // % of packets the receiver got
    int8_t upSnr = 0;
    uint8_t antenna = 0, rfMode = 0, txPower = 0;   // txPower: CRSF's enum (0 0 mW, 1 10, 2 25, 3 100, 4 500, 5 1000, 6 2000, 7 250, 8 50 mW)
    int16_t downRssi = 0;
    uint8_t downLq = 0;
    int8_t downSnr = 0;
    uint32_t linkMs = 0;
    // the model's battery (0x08), from the flight controller or the receiver
    uint16_t battDeciVolts = 0, battDeciAmps = 0;
    uint32_t battMah = 0;
    uint8_t battPct = 0;
    uint32_t battMs = 0;
    // head speed (0x0C, the first value; Rotorflight's is already the head's) and the first temperature (0x0D)
    int32_t rpm = 0;
    uint32_t rpmMs = 0;
    int16_t tempDeciC = 0;
    uint32_t tempMs = 0;
    // attitude (0x1E, CRSF's units) and the flight mode (0x21)
    int16_t pitch = 0, roll = 0, yaw = 0;
    char flightMode[16] = {0};
    // the module's timing (0x3A / 0x10), tenths of a microsecond
    int32_t intervalTenthsUs = 0, offsetTenthsUs = 0;
    uint32_t timingMs = 0;
    // counts
    uint32_t framesOk = 0, badCrc = 0, badLength = 0, unknownType = 0;
};

inline int32_t be32(const uint8_t *p) { return (int32_t)(((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]); }
inline uint16_t be16(const uint8_t *p) { return (uint16_t)(((uint16_t)p[0] << 8) | p[1]); }

// One whole, checked frame: type and payload (n = the payload's length).
inline void decode(uint8_t type, const uint8_t *p, uint8_t n, Telemetry &t, uint32_t nowMs)
{
    switch (type)
    {
    case T_LINK_STATS:
        if (n < 10) return;
        t.upRssi1 = -(int16_t)p[0];
        t.upRssi2 = -(int16_t)p[1];
        t.upLq = p[2];
        t.upSnr = (int8_t)p[3];
        t.antenna = p[4];
        t.rfMode = p[5];
        t.txPower = p[6];
        t.downRssi = -(int16_t)p[7];
        t.downLq = p[8];
        t.downSnr = (int8_t)p[9];
        t.linkMs = nowMs ? nowMs : 1;
        break;
    case T_BATTERY:
        if (n < 8) return;
        t.battDeciVolts = be16(p);
        t.battDeciAmps = be16(p + 2);
        t.battMah = ((uint32_t)p[4] << 16) | ((uint32_t)p[5] << 8) | p[6];
        t.battPct = p[7];
        t.battMs = nowMs ? nowMs : 1;
        break;
    case T_RPM: // [source][int24 BE] x N: the first
    {
        if (n < 4) return;
        int32_t r = ((int32_t)p[1] << 16) | ((int32_t)p[2] << 8) | p[3];
        if (r & 0x800000) r |= ~0xFFFFFF;
        t.rpm = r;
        t.rpmMs = nowMs ? nowMs : 1;
        break;
    }
    case T_TEMP: // [source][int16 BE, tenths of a degree] x N: the first
        if (n < 3) return;
        t.tempDeciC = (int16_t)be16(p + 1);
        t.tempMs = nowMs ? nowMs : 1;
        break;
    case T_ATTITUDE:
        if (n < 6) return;
        t.pitch = (int16_t)be16(p);
        t.roll = (int16_t)be16(p + 2);
        t.yaw = (int16_t)be16(p + 4);
        break;
    case T_FLIGHT_MODE:
    {
        uint8_t k = 0;
        while (k < n && k < sizeof(t.flightMode) - 1 && p[k]) { t.flightMode[k] = (char)p[k]; ++k; }
        t.flightMode[k] = 0;
        break;
    }
    case T_HANDSET: // an extended frame: [destination][origin][subcommand][...]
        if (n < 11 || p[2] != SUB_TIMING) return;
        t.intervalTenthsUs = be32(p + 3);
        t.offsetTenthsUs = be32(p + 7);
        t.timingMs = nowMs ? nowMs : 1;
        break;
    default:
        ++t.unknownType;   // fine: the router passes on whatever the receiver sends
        break;
    }
}

// Assembles frames from the bytes as they come. Anything that is not a frame is skipped, a byte at a time.
struct Parser
{
    uint8_t buf[MAX_FRAME];
    uint8_t len = 0;
    // One byte. True when it completed a good frame (decoded into t).
    bool feed(uint8_t b, Telemetry &t, uint32_t nowMs)
    {
        if (len == 0)
        {
            if (b == SYNC_BYTE || b == ADDR_HANDSET || b == ADDR_MODULE || b == 0xEC)
                buf[len++] = b;
            return false;
        }
        if (len == 1)
        {
            if (b < 2 || b > MAX_FRAME - 2) { ++t.badLength; len = 0; return false; }
            buf[len++] = b;
            return false;
        }
        buf[len++] = b;
        const uint8_t total = (uint8_t)(buf[1] + 2);
        if (len < total) return false;
        len = 0;
        if (crc8(&buf[2], (uint8_t)(total - 3)) != buf[total - 1]) { ++t.badCrc; return false; }
        ++t.framesOk;
        decode(buf[2], &buf[3], (uint8_t)(total - 4), t, nowMs);
        return true;
    }
};

// How often to send: the module's own packet interval while its word is fresh, bounded to 1..20 ms whatever a frame
// might say; 4 ms (250 Hz) until then. (Phase 1 follows the interval only. Its offset is logged: how to steer by it is
// decided on the bench, from real numbers.)
inline uint32_t sendPeriodUs(const Telemetry &t, uint32_t nowMs)
{
    if (t.timingMs && (uint32_t)(nowMs - t.timingMs) < TIMING_FRESH_MS && t.intervalTenthsUs >= 10000 && t.intervalTenthsUs <= 200000)
        return (uint32_t)(t.intervalTenthsUs / 10);
    return DEFAULT_PERIOD_US;
}
} // namespace ElrsCrsf
// ELRS-CRSF-END

#ifdef ELRS_TEST
// ---------------------------------------------------------------------------------------------------------------------
// The bench-test driver: Serial6 (TX6 = pin 24), one wire, 400000 baud, not inverted (in half duplex the Teensy holds the
// line up with its pad's pull-up between bytes, which is a non-inverted line's idle; the module tries both polarities).
static ElrsCrsf::Parser ElrsParser;
static ElrsCrsf::Telemetry ElrsTelem;
static uint32_t ElrsLastSendUs = 0, ElrsLastLogMs = 0, ElrsSent = 0, ElrsSkipped = 0;
static bool ElrsStarted = false;

FLASHMEM void ElrsTestLog()
{
    using namespace ElrsCrsf;
    char line[150];
    const uint32_t now = millis();
    const bool link = ElrsTelem.linkMs && (now - ElrsTelem.linkMs) < 2000;
    snprintf(line, sizeof(line), "ELRS test: sent %lu (skipped %lu), frames back %lu (bad CRC %lu), %s LQ %u%% RSSI %d dBm, rate %ld us (offset %ld/10 us)",
             (unsigned long)ElrsSent, (unsigned long)ElrsSkipped, (unsigned long)ElrsTelem.framesOk, (unsigned long)ElrsTelem.badCrc,
             link ? "LINK" : "no link", (unsigned)ElrsTelem.upLq, (int)ElrsTelem.upRssi1,
             (long)(ElrsTelem.intervalTenthsUs / 10), (long)ElrsTelem.offsetTenthsUs);
    LogText(line, strlen(line), false);
    if (ElrsTelem.battMs && (now - ElrsTelem.battMs) < 5000)
    {
        snprintf(line, sizeof(line), "ELRS test: model battery %u.%u V, %u.%u A, %lu mAh, rpm %ld, mode %s",
                 ElrsTelem.battDeciVolts / 10, ElrsTelem.battDeciVolts % 10, ElrsTelem.battDeciAmps / 10, ElrsTelem.battDeciAmps % 10,
                 (unsigned long)ElrsTelem.battMah, (long)ElrsTelem.rpm, ElrsTelem.flightMode);
        LogText(line, strlen(line), false);
    }
}

// Every pass of loop() in NORMAL mode: read what came, send when it is time, log every 5 s. Never waits: a frame that
// would not fit the serial buffer whole is skipped (and counted), not queued.
FASTRUN void ElrsTestTick()
{
    if (!ElrsStarted)
    {
        Serial6.begin(400000, SERIAL_8N1_HALF_DUPLEX);
        ElrsStarted = true;
    }
    while (Serial6.available())
        ElrsParser.feed((uint8_t)Serial6.read(), ElrsTelem, millis());
    const uint32_t nowUs = micros();
    if ((uint32_t)(nowUs - ElrsLastSendUs) >= ElrsCrsf::sendPeriodUs(ElrsTelem, millis()))
    {
        ElrsLastSendUs = nowUs;
        uint8_t f[ElrsCrsf::RC_FRAME_LEN];
        ElrsCrsf::buildRcFrame(SendBuffer, f);
        if (Serial6.availableForWrite() >= (int)sizeof(f))
        {
            Serial6.write(f, sizeof(f));
            ++ElrsSent;
        }
        else
            ++ElrsSkipped;
    }
    if (millis() - ElrsLastLogMs >= 5000)
    {
        ElrsLastLogMs = millis();
        ElrsTestLog();
    }
}
#endif
