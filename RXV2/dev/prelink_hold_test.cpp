// Pre-link safety hold test (0.9.834) - run by dev/prelink_hold_test.sh, a release gate.
// Malcolm 2026-09-24: the swash hit its stops mid-update because the hold pinned
// channel 3 (Rotorflight collective) instead of the FC throttle (channel 5).
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#include <string>
#include <vector>
static uint32_t fakeMs = 0;
static uint32_t millis() { return fakeMs; }
static uint8_t throttleChannel = 3;
static bool fcTelemetryEnabled = true;
struct { bool detected = false; char variant[5] = {0}; uint8_t throttleCh = 0; uint8_t rcMap[8] = {0}; uint8_t rcMapLen = 0; } fcInfo;
static uint8_t bootMapNvs[8] = {0};   // (0.9.926) the channel map the FC answered last time (NVS)
static uint8_t bootMapNvsLen = 0;
static uint16_t channelMicros[16];
constexpr uint16_t THROTTLE_SAFE_US = 885;
struct { std::vector<std::string> log; void add(const char* m) { log.push_back(m); } } events;
#include HOLD_BLOCK
static int fails = 0;
static void expect(const char* what, int ch, uint16_t want) {
    bool ok = channelMicros[ch - 1] == want;
    if (!ok) fails++;
    printf("%s %-58s ch%d=%u (want %u)\n", ok ? "PASS" : "FAIL", what, ch, channelMicros[ch - 1], want);
}
static void boot() { for (int i = 0; i < 16; ++i) channelMicros[i] = i < 5 ? 1500 : 500; }
int main() {
    // 1. Black Thunder 2 today: thr_ch 3 (default), learned RF throttle 5, FC not answered yet.
    boot(); throttleChannel = 3; fcInfo.throttleCh = 5; fcInfo.detected = false; fakeMs = 1000;
    applyPreLinkHolds(true, true);
    expect("power-up, FC not answered: real throttle held low", 5, 885);
    expect("power-up, FC not answered: ch3 at the normal bottom only", 3, 988);
    // 2. The FC answers as Rotorflight.
    fcInfo.detected = true; strcpy(fcInfo.variant, "RTFL"); fakeMs = 2500;
    applyPreLinkHolds(true, true);
    expect("Rotorflight answered: collective (ch3) centred", 3, 1500);
    expect("Rotorflight answered: throttle (ch5) still low", 5, 885);
    // 3. A transmitter connects: first 25 packets hold the throttle only; ch3 follows the TX.
    channelMicros[2] = 1234; channelMicros[4] = 1900;
    applyPreLinkHolds(true, false);
    expect("TX first packets: throttle held", 5, 885);
    expect("TX first packets: collective is the TX's", 3, 1234);
    applyPreLinkHolds(false, false); channelMicros[4] = 1900;
    expect("TX stable: throttle is the TX's", 5, 1900);
    // 3b. The FC goes quiet later (rebooting after a restore): "FC lost" must
    //     not move the hold back onto the collective.
    fcInfo.detected = false; fakeMs = 60000;
    for (int i = 0; i < 16; ++i) channelMicros[i] = i < 5 ? 1500 : 500;
    applyPreLinkHolds(true, true);
    expect("FC lost after 10 s: collective (ch3) stays centred", 3, 1500);
    expect("FC lost after 10 s: throttle (ch5) still held", 5, 885);
    // 4. Plane with a stale learned 5, fc_telem on, no FC ever answers.
    holdRfSeen = false;   // a new power-up
    boot(); fcInfo = {}; fcInfo.throttleCh = 5; throttleChannel = 3; fakeMs = 500;
    { static uint8_t dummy; (void)dummy; }
    applyPreLinkHolds(true, true);
    expect("plane, first seconds: its throttle (ch3) at ESC-off floor", 3, 988);
    fakeMs = 11000;
    applyPreLinkHolds(true, true);
    expect("plane, no FC after 10 s: ch3 fully held", 3, 885);
    expect("plane, no FC after 10 s: stale ch5 released", 5, 1500);
    // 5. Betaflight FC answers: learned value ignored.
    holdRfSeen = false;
    boot(); fcInfo = {}; fcInfo.throttleCh = 5; fcInfo.detected = true; strcpy(fcInfo.variant, "BTFL"); fakeMs = 3000;
    applyPreLinkHolds(true, true);
    expect("Betaflight FC: the setting's channel (3) held", 3, 885);
    expect("Betaflight FC: ch5 released", 5, 1500);
    // 6. fc_telem off (PWM converter): the setting rules.
    holdRfSeen = false;
    boot(); fcInfo = {}; fcInfo.throttleCh = 5; fcTelemetryEnabled = false; fakeMs = 100;
    applyPreLinkHolds(true, true);
    expect("fc_telem off: setting's channel held", 3, 885);
    expect("fc_telem off: ch5 untouched", 5, 1500);
    fcTelemetryEnabled = true;
    // 7. Setting already matches the FC: one hold.
    holdRfSeen = false;
    boot(); fcInfo = {}; fcInfo.throttleCh = 5; throttleChannel = 5; fakeMs = 100;
    applyPreLinkHolds(true, true);
    expect("setting = FC throttle: ch5 held", 5, 885);
    expect("setting = FC throttle: ch3 centred", 3, 1500);
    // 8. (0.9.926, the night review of 11 Nov 2026) THE POSTURE FOLLOWS ROTORFLIGHT'S CHANNEL MAP: roll, pitch, yaw and
    //    collective centred, the throttle and every AUX low - by the map answered this power-up, else the one kept (NVS).
    static const uint8_t ldrcMap[8] = {0, 1, 3, 2, 4, 5, 6, 7};   // AECRT123: Black Thunder 2's own (its backup, "64=0001030204050607")
    static const uint8_t elrsMap[8] = {0, 1, 3, 2, 5, 4, 6, 7};   // AECR1T23: the arm switch on channel 5 for ExpressLRS
    static const uint8_t colOn5[8]  = {0, 1, 2, 4, 3, 5, 6, 7};   // AERTC123: the collective on channel 5 (another pilot's)
    static const uint8_t badMap[8]  = {0, 1, 3, 2, 4, 4, 6, 7};   // channel 5 twice: not a whole map
    auto bd = [](const char* what, int ch, uint16_t want) {
        const uint16_t got = bootDefaultMicros((uint8_t)(ch - 1)); const bool ok = got == want; if (!ok) fails++;
        printf("%s %-58s ch%d=%u (want %u)\n", ok ? "PASS" : "FAIL", what, ch, got, want); };
    fcInfo = {}; bootMapNvsLen = 0;
    bd("no map: the old shape, ch5 centred", 5, 1500); bd("no map: ch6 low", 6, 500);
    memcpy(fcInfo.rcMap, ldrcMap, 8); fcInfo.rcMapLen = 8;
    bd("AECRT123: ch1 roll centred", 1, 1500); bd("AECRT123: ch3 collective centred", 3, 1500); bd("AECRT123: ch4 yaw centred", 4, 1500);
    bd("AECRT123: ch5 the throttle low", 5, 500); bd("AECRT123: ch6 AUX1 (arm) low", 6, 500); bd("AECRT123: ch12 low", 12, 500);
    memcpy(fcInfo.rcMap, elrsMap, 8);
    bd("AECR1T23: ch5 = AUX1 = ARM, LOW (was 1500)", 5, 500); bd("AECR1T23: ch6 the throttle low", 6, 500); bd("AECR1T23: ch4 yaw centred", 4, 1500);
    fcInfo.rcMapLen = 0; memcpy(bootMapNvs, elrsMap, 8); bootMapNvsLen = 8;
    bd("not answered yet: the map kept (NVS) - ch5 arm LOW", 5, 500);
    memcpy(fcInfo.rcMap, colOn5, 8); fcInfo.rcMapLen = 8;
    bd("answered this power-up wins over the kept one: ch5 collective centred", 5, 1500); bd("... ch4 its throttle low", 4, 500);
    memcpy(fcInfo.rcMap, badMap, 8); bootMapNvsLen = 0;
    bd("a map that is not whole: the old shape", 5, 1500);
    // 9. THE HOLE IT CLOSES: the first power-up after the pilot moved arming to channel 5 (the phone's Transmitter channels
    //    page: map AECR1T23, the receiver's throttle setting 6). The learned throttle kept in NVS is still 5: held low
    //    until the FC answers. Then the FC says throttle 6: the hold moves, and channel 5 - now the arm switch - is let go.
    //    Before 0.9.926 it went back to 1500, an arm edge with the transmitter off. Now: LOW.
    holdRfSeen = false; fcInfo = {}; bootMapNvsLen = 0; throttleChannel = 6; fcInfo.throttleCh = 5; fakeMs = 1000;
    for (int i = 0; i < 16; ++i) channelMicros[i] = bootDefaultMicros((uint8_t)i);
    applyPreLinkHolds(true, true);
    expect("arm on 5, first seconds: the old throttle (5) held", 5, 885);
    expect("arm on 5, first seconds: the setting (6) at the floor", 6, 988);
    fcInfo.detected = true; strcpy(fcInfo.variant, "RTFL"); memcpy(fcInfo.rcMap, elrsMap, 8); fcInfo.rcMapLen = 8; fcInfo.throttleCh = 6; fakeMs = 7000;
    applyPreLinkHolds(true, true);
    expect("FC answered AECR1T23: the throttle (6) held", 6, 885);
    expect("FC answered AECR1T23: ch5 (ARM) let go LOW, not 1500", 5, 500);
    for (auto& m : events.log) printf("  event: %s\n", m.c_str());
    printf(fails ? "%d FAILED\n" : "ALL PASS\n", fails);
    return fails ? 1 : 0;
}
