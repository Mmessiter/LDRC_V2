// dev/armch_test.sh: armChannelFromModeRanges (src/MspFc.h) against mode tables built from Rotorflight 'aux' lines:
// aux <slot> <mode id> <aux channel> <start us> <end us> ... -> MSP 34: id, aux, (start-900)/25, (end-900)/25 per slot.
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
#include ARMCH_BLOCK
static int checks = 0, fails = 0;
static void ok(bool c, const char* what) { ++checks; if (!c) { ++fails; printf("   FAIL: %s\n", what); } }
struct Slot { int id, aux, start, end; };
static std::vector<uint8_t> table(const std::vector<Slot>& s) {
    std::vector<uint8_t> b;
    for (auto& x : s) { b.push_back(x.id); b.push_back(x.aux); b.push_back((x.start - 900) / 25); b.push_back((x.end - 900) / 25); }
    return b;
}
static std::vector<Slot> empty20() { return std::vector<Slot>(20, Slot{0, 0, 900, 900}); }
int main() {
    // Mehul's RAW 420 (RAW420MP-for-NEXUS_X.txt): aux 0 0 0 1500 2100, the other 19 slots empty (aux N 0 0 900 900)
    std::vector<Slot> m = empty20(); m[0] = {0, 0, 1500, 2100};
    std::vector<uint8_t> b = table(m);
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size()) == 6, "Mehul's RAW 420: ARM on AUX1 = channel 6");
    // empty slots read id 0 (ARM!) with an empty range: never counted
    std::vector<Slot> e = empty20(); b = table(e);
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size()) == 0, "no arm switch set up: 0");
    // another mode first (RESCUE, id 53, on AUX2), ARM on AUX3 in slot 2
    std::vector<Slot> r = empty20(); r[0] = {53, 1, 1700, 2100}; r[2] = {0, 2, 1300, 2100};
    b = table(r);
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size()) == 8, "rescue first, ARM on AUX3 = channel 8");
    // an aux channel past 16 is not a channel of ours
    std::vector<Slot> h = empty20(); h[0] = {0, 11, 1500, 2100};
    b = table(h);
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size()) == 0, "AUX12 = channel 17: not ours, 0");
    // AUX11 = channel 16, the last one
    h[0] = {0, 10, 1500, 2100}; b = table(h);
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size()) == 16, "AUX11 = channel 16");
    // a short or empty reply: nothing read past its end
    b = table(m);
    ok(armChannelFromModeRanges(b.data(), 3) == 0, "a reply of 3 bytes: not a slot");
    ok(armChannelFromModeRanges(nullptr, 0) == 0, "no reply: 0");

    // 0.9.925: THROUGH ROTORFLIGHT'S CHANNEL MAP (MSP_RX_MAP, 8 bytes: the channel, 0-based, feeding A E R C T 1 2 3).
    // Black Thunder 2's own backup (Black_Thunder_2.rfb, "64=0001030204050607") = `map AECRT123`: AUX1 is channel 6.
    const uint8_t ldrc[8]  = {0, 1, 3, 2, 4, 5, 6, 7};
    // Arming on channel 5 for ExpressLRS (Malcolm, 11 Nov 2026) = `map AECR1T23`: AUX1 from channel 5, throttle from 6.
    const uint8_t elrs[8]  = {0, 1, 3, 2, 5, 4, 6, 7};
    b = table(m);                                                     // ARM on AUX1
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), ldrc, 8) == 6, "LDRC's map AECRT123: ARM on AUX1 = channel 6 (as before)");
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), elrs, 8) == 5, "map AECR1T23: ARM on AUX1 = channel 5, NOT the throttle on 6");
    ok(elrs[4] + 1 == 6, "map AECR1T23: the throttle (byte 4) is channel 6");
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), elrs, 0) == 6, "map not read (length 0): the default, channel 6");
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), nullptr, 8) == 6, "no map pointer: the default, channel 6");
    // AUX3 is the last mapped one (byte 7); AUX4 on is past the eight and is itself
    std::vector<Slot> a3 = empty20(); a3[0] = {0, 2, 1500, 2100}; b = table(a3);
    const uint8_t swap3[8] = {0, 1, 2, 3, 4, 5, 6, 9};                // AUX3 fed by channel 10
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), swap3, 8) == 10, "AUX3 mapped to channel 10");
    std::vector<Slot> a4 = empty20(); a4[0] = {0, 3, 1500, 2100}; b = table(a4);
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), elrs, 8) == 9, "AUX4 is past the map: channel 9 whatever the map");
    // a short map (5 bytes, the A E R C T only) leaves the AUX channels as themselves
    b = table(m);
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), elrs, 5) == 6, "a 5-byte map: AUX1 = channel 6");
    // a nonsense map byte is no channel of ours
    const uint8_t bad[8] = {0, 1, 2, 3, 4, 200, 6, 7};
    ok(armChannelFromModeRanges(b.data(), (uint16_t)b.size(), bad, 8) == 0, "a map byte of 200: not ours, 0");
    // auxToChannel by itself (the page-write path, WebPages.h)
    ok(auxToChannel(0, elrs, 8) == 5 && auxToChannel(1, elrs, 8) == 7 && auxToChannel(0, ldrc, 8) == 6,
       "auxToChannel: AUX1 -> 5 / AUX2 -> 7 on AECR1T23, AUX1 -> 6 on AECRT123");
    ok(auxToChannel(10, nullptr, 0) == 16 && auxToChannel(11, nullptr, 0) == 0, "auxToChannel: AUX11 = 16, AUX12 = not ours");
    printf("%s: %d checks, %d failures\n", fails ? "FAILED" : "ALL PASS", checks, fails);
    return fails ? 1 : 0;
}
