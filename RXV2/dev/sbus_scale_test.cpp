// SBUS scale test (0.9.898) - run by dev/sbus_scale_test.sh. The 11-bit value SBUS, CRSF and FBUS send is the one every
// flight controller turns back into microseconds as us = value * 5/8 + 880 (172 = 988, 992 = 1500, 1811 = 2012). Until
// 0.9.898 SBUS and FBUS spread the transmitter's whole 500..2500 over 0..2047 (copied from the V1 receiver): a flight
// controller on SBUS read centre as 1519 us and 1000..2000 as about 1200..1840.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cmath>
static uint16_t channelMicros[16];
static uint8_t sbusFrame[25], crsfFrame[26], fbusFrame[26];
#include SCALE_BLOCK
static int fails = 0, checks = 0;
static void ok(bool c, const char* what) { ++checks; if (!c) ++fails; printf("%s %s\n", c ? "PASS" : "FAIL", what); }
static uint16_t unpack(const uint8_t* p, int ch) { const int bit = ch * 11; uint32_t v = 0; for (int i = 0; i < 11; ++i) { const int b = bit + i; if (p[b >> 3] & (1u << (b & 7))) v |= 1u << i; } return (uint16_t)(v & 0x7FF); }
static double fcSbus(uint16_t v) { return v * 5.0 / 8.0 + 880.0; }           // Betaflight / Rotorflight sbus.c
static double fcCrsf(uint16_t v) { return 0.62477120195241 * v + 881.0; }     // crsf.c
static long oldV1(uint16_t us) { long v = (long)us - 500; long s = (v * 2047L) / 2000L; if (s < 0) s = 0; if (s > 2047) s = 2047; return s; }   // the V1 mapping, verbatim
static int32_t simDecode(uint16_t raw) { int32_t us = ((int32_t)raw - 992) * 5 / 8 + 1500; if (us < 880) us = 880; return us; }      // RcInput.h, the simulator interface's SBUS reader, verbatim
int main() {
    // 1. the landmarks
    ok(rc11bit(1500) == 992 && rc11bit(1000) == 173 && rc11bit(2000) == 1811, "1500 -> 992, 1000 -> 173, 2000 -> 1811 (the convention: 172 = 988 us, 1811 = 2012 us)");
    ok(rc11bit(500) == 172 && rc11bit(2500) == 1811 && rc11bit(0) == 172 && rc11bit(65535) == 1811, "the transmitter's 500 and 2500 clamp to 172 and 1811: never an invalid pulse");
    // 2. the fault that was: what a flight controller made of the V1 mapping
    ok(fabs(fcSbus(oldV1(1500)) - 1519.4) < 1.0, "the old centre read 1519 us");
    ok(fabs(fcSbus(oldV1(1000)) - 1199.4) < 1.5 && fabs(fcSbus(oldV1(2000)) - 1839.4) < 1.5, "the old 1000..2000 read about 1200..1840");
    // 3. now: on SBUS the flight controller reads what CRSF gives it, for every microsecond the transmitter can send
    double worst = 0;
    for (int us = 500; us <= 2500; ++us) { const uint16_t v = rc11bit((uint16_t)us); const double d = fabs(fcSbus(v) - fcCrsf(v)); if (d > worst) worst = d; }
    ok(worst < 2.0, "SBUS and CRSF readings agree within 2 us over 500..2500");
    ok(fabs(fcSbus(rc11bit(1500)) - 1500.0) < 0.01 && fabs(fcSbus(rc11bit(1000)) - 988.1) < 0.5 && fabs(fcSbus(rc11bit(2000)) - 2011.9) < 0.5, "centre reads 1500 exactly; 1000 and 2000 read 988 and 2012, as on CRSF and every standard radio");
    bool monotone = true; for (int us = 501; us <= 2500; ++us) if (rc11bit((uint16_t)us) < rc11bit((uint16_t)(us - 1))) monotone = false;
    ok(monotone, "never a step backwards");
    // 4. the frames carry it
    for (int c = 0; c < 16; ++c) channelMicros[c] = (uint16_t)(1000 + c * 66);
    channelMicros[3] = 1500; channelMicros[15] = 2500;
    buildSbusFrame(false, false); buildCrsfFrame(); buildFbusFrame(false, false);
    bool same = true;
    for (int c = 0; c < 16; ++c) { const uint16_t want = rc11bit(channelMicros[c]); if (unpack(&sbusFrame[1], c) != want || unpack(&crsfFrame[3], c) != want || unpack(&fbusFrame[2], c) != want) same = false; }
    ok(same, "all 16 channels unpack to rc11bit on SBUS, CRSF and FBUS alike");
    ok(unpack(&sbusFrame[1], 3) == 992 && unpack(&sbusFrame[1], 15) == 1811 && unpack(&sbusFrame[1], 0) == 173, "992 at centre, 1811 at the clamp, 173 for 1000 us, inside an SBUS frame");
    ok(sbusFrame[0] == 0x0F && sbusFrame[23] == 0 && sbusFrame[24] == 0, "SBUS header 0x0F, flags clear, end byte 0");
    buildSbusFrame(true, true); ok(sbusFrame[23] == 0x0C, "frame-lost and failsafe flags as before");
    ok(crsfFrame[0] == 0xC8 && crsfFrame[1] == 24 && crsfFrame[2] == 0x16 && crsfFrame[25] == crsfCrc8(&crsfFrame[2], 23), "CRSF header and CRC as before");
    // 5. an RXV2's SBUS into another RXV2's simulator interface reads as a flight controller would
    int worstSim = 0;
    for (int us = 500; us <= 2500; ++us) { const uint16_t v = rc11bit((uint16_t)us); const int d = (int)fabs(simDecode(v) - fcSbus(v)); if (d > worstSim) worstSim = d; }
    ok(worstSim <= 1 && simDecode(rc11bit(1500)) == 1500, "the simulator interface decodes within 1 us of the flight controller's reading; 1500 comes back as 1500");
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
