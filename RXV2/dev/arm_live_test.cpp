// 0.9.886 arm-live test - run by dev/arm_live_test.sh. The receiver answers MSP_RC (105) from its own output while the
// model is armed: the numbers must be what Rotorflight itself reports for the CRSF frame we send (0.62477 x crsf + 881).
#include <cstdio>
#include <cstdint>
#include <cstring>
static uint16_t channelMicros[16];
#include ARM_BLOCK
static int fails = 0, checks = 0;
static void ok(bool c, const char* what) { ++checks; if (!c) ++fails; printf("%s %s\n", c ? "PASS" : "FAIL", what); }
// What Rotorflight does with a CRSF channel value (rx_crsf.c crsfReadRawRC), and what buildCrsfFrame sends (Output.h), both verbatim.
static float rfDecode(long crsf) { return (0.62477120195241f * (float)crsf) + 881; }
static long txEncode(uint16_t us) { long v = (long)us - 1500; long c = (v * 819L) / 500L + 992L; if (c < 172) c = 172; if (c > 1811) c = 1811; return c; }
int main() {
    // 1. The anchors: 1000 us encodes to CRSF 173 (819/500 is a shade under 1.638), which Rotorflight reads as 989;
    //    1500 -> 1500/1501; 2000 -> 2012.
    ok(fcRcMicrosFromTx(1000) == 989, "1000 us from the transmitter reads as 989 us at the flight controller (CRSF 173)");
    ok(fcRcMicrosFromTx(1500) == 1501 || fcRcMicrosFromTx(1500) == 1500, "1500 us reads as the centre (1500 or 1501)");
    ok(fcRcMicrosFromTx(2000) == 2012, "2000 us reads as 2012 us");
    // 2. The transmitter's arming values (FixArmingChannel: 667 safe, 2233 armed) sit at the rails, as the FC sees 988 and 2012.
    ok(fcRcMicrosFromTx(667) == 988 && fcRcMicrosFromTx(2233) == 2012, "the safety's 667/2233 us arrive as 988/2012: the rails");
    ok(fcRcMicrosFromTx(0) == 988 && fcRcMicrosFromTx(65535) == 2012, "nothing escapes the rails");
    // 3. Every value 800..2200 is within 1 us of Rotorflight's own decode of our own encode, and never goes backwards.
    bool close = true, mono = true; uint16_t last = 0;
    for (int us = 800; us <= 2200; ++us) {
        const uint16_t got = fcRcMicrosFromTx((uint16_t)us);
        const float rf = rfDecode(txEncode((uint16_t)us));
        if (got + 1.0f < rf || got - 1.0f > rf) close = false;
        if (got < last) mono = false;
        last = got;
    }
    ok(close, "800-2200 us: within 1 us of Rotorflight's own decode of the frame we send");
    ok(mono, "800-2200 us: never goes backwards");
    // 4. The hex answer: 16 channels, low byte first, exactly as handleMspApi spells a flight-controller reply.
    for (int i = 0; i < 16; ++i) channelMicros[i] = 1500;
    channelMicros[0] = 1000; channelMicros[5] = 2233; channelMicros[15] = 667;
    char hex[65]; memset(hex, 'x', sizeof hex); mspRcFromLink(hex);
    ok(strlen(hex) == 64, "64 hex digits, NUL-ended");
    ok(strncmp(hex, "DD03", 4) == 0, "channel 1 at 989 us -> DD03 (0x03DD, low byte first)");
    ok(strncmp(hex + 5 * 4, "DC07", 4) == 0, "channel 6 at 2012 us -> DC07 (0x07DC)");
    ok(strncmp(hex + 15 * 4, "DC03", 4) == 0, "channel 16 at 988 us -> DC03");
    const char* mid = fcRcMicrosFromTx(1500) == 1501 ? "DD05" : "DC05";
    bool centres = true; for (int i = 1; i < 15; ++i) if (i != 5 && strncmp(hex + i * 4, mid, 4) != 0) centres = false;
    ok(centres, "the other 13 channels at the centre");
    printf("%s: %d checks, %d failures\n", fails ? "FAILED" : "ALL PASS", checks, fails);
    return fails ? 1 : 0;
}
