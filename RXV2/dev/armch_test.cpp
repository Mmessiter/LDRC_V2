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
    printf("%s: %d checks, %d failures\n", fails ? "FAILED" : "ALL PASS", checks, fails);
    return fails ? 1 : 0;
}
