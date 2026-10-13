// B29 failsafe ticks test - run by dev/failsafe_mask_test.sh.
#include <cstdio>
#include <cstdint>
#include <cstring>
static uint16_t channelMicros[16];
#include FS_BLOCK
static int fails = 0, checks = 0;
static void ok(bool c, const char* what) { ++checks; if (!c) ++fails; printf("%s %s\n", c ? "PASS" : "FAIL", what); }
// V1 transmitter (TransmitterCode/src/main.cpp MakeTwobytes), verbatim.
static uint16_t MakeTwobytes(bool* f) { uint16_t tb = 0; for (int i = 0; i < 16; ++i) { if (f[15 - i] == true) { tb |= 1 << (i); } } return tb; }
// V1 receiver (ReceiverCode/src/main.cpp RebuildFlags), verbatim.
static void RebuildFlags(bool* f, uint16_t tb) { for (uint8_t i = 0; i < 16; ++i) f[15 - i] = (tb & (1 << i)); }
// What the transmitter puts in parameter 1 (Parameters.h): word[1] = high byte, word[2] = low byte.
static void txWords(bool* ticks, uint16_t* w1, uint16_t* w2) { const uint16_t tb = MakeTwobytes(ticks); *w1 = (uint8_t)(tb >> 8); *w2 = (uint8_t)(tb & 0xFF); }
int main() {
    bool ticks[16]; uint16_t w1, w2;
    // 1. Channel 1 only (index 0): bit 15 -> word[1] = 0x80, word[2] = 0 -> mask bit 0.
    memset(ticks, 0, sizeof ticks); ticks[0] = true; txWords(ticks, &w1, &w2);
    ok(w1 == 0x80 && w2 == 0, "transmitter: channel 1 ticked travels as word[1]=0x80 word[2]=0");
    ok(failsafeMaskFromTx(w1, w2) == 0x0001, "receiver: channel 1 ticked -> mask bit 0");
    // 2. Channel 16 only: bit 0 -> word[2] = 1 -> mask bit 15.
    memset(ticks, 0, sizeof ticks); ticks[15] = true; txWords(ticks, &w1, &w2);
    ok(failsafeMaskFromTx(w1, w2) == 0x8000, "channel 16 ticked -> mask bit 15");
    // 3. All and none.
    memset(ticks, 1, sizeof ticks); txWords(ticks, &w1, &w2); ok(failsafeMaskFromTx(w1, w2) == 0xFFFF, "all ticked -> 0xFFFF");
    memset(ticks, 0, sizeof ticks); txWords(ticks, &w1, &w2); ok(failsafeMaskFromTx(w1, w2) == 0, "none ticked -> 0");
    // 4. Every pattern agrees with V1's own RebuildFlags, channel by channel.
    bool agree = true;
    for (uint32_t pat = 0; pat < 65536; pat += 37) {
        for (int i = 0; i < 16; ++i) ticks[i] = (pat >> i) & 1;
        txWords(ticks, &w1, &w2);
        const uint16_t mask = failsafeMaskFromTx(w1, w2);
        bool v1[16]; RebuildFlags(v1, (uint16_t)((w1 << 8) | w2));
        for (int i = 0; i < 16; ++i) if (((mask >> i) & 1) != (v1[i] ? 1 : 0) || v1[i] != ticks[i]) agree = false;
    }
    ok(agree, "1772 patterns: the mask names the same channels as V1's RebuildFlags, and as the ticks sent");
    // 5. Driving: ticked channels move, the rest hold where they were.
    for (int i = 0; i < 16; ++i) { failsafeMicros[i] = 1000 + i * 10; channelMicros[i] = 1500; }
    failsafeSet = true; failsafeMask = 0x0023;   // channels 1, 2, 6
    ok(failsafeDrive() == true, "mask 1,2,6: drive says it drove");
    ok(channelMicros[0] == 1000 && channelMicros[1] == 1010 && channelMicros[5] == 1050, "channels 1, 2, 6 at their saved positions");
    bool held = true; for (int i = 0; i < 16; ++i) if (i != 0 && i != 1 && i != 5 && channelMicros[i] != 1500) held = false;
    ok(held, "the other 13 channels hold their last position");
    ok(failsafeMaskCount() == 3, "3 of 16 ticked");
    // 6. No channel ticked: nothing moves, and the caller is told so.
    for (int i = 0; i < 16; ++i) channelMicros[i] = 1500;
    failsafeMask = 0;
    ok(failsafeDrive() == false, "mask 0: nothing to drive");
    held = true; for (int i = 0; i < 16; ++i) if (channelMicros[i] != 1500) held = false;
    ok(held, "mask 0: every channel holds");
    // 7. A failsafe saved before this build (no mask in NVS = 0xFFFF): all 16 move, as before.
    failsafeMask = 0xFFFF;
    ok(failsafeDrive() == true, "old NVS (all 16): drives");
    bool all = true; for (int i = 0; i < 16; ++i) if (channelMicros[i] != 1000 + i * 10) all = false;
    ok(all, "old NVS: all 16 channels at their saved positions");
    ok(failsafeMaskCount() == 16, "16 of 16 ticked");
    // 8. Nothing saved: nothing moves whatever the mask.
    for (int i = 0; i < 16; ++i) channelMicros[i] = 1500;
    failsafeSet = false; ok(failsafeDrive() == false && channelMicros[3] == 1500, "no failsafe saved: nothing moves");
    printf("%s: %d checks, %d failed\n", fails ? "FAILED" : "ALL PASS", checks, fails);
    return fails ? 1 : 0;
}
