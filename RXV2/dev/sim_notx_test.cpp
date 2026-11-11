// What the simulator is given while no transmitter is heard (0.9.924) - run by dev/sim_notx_test.sh against the REAL
// block of src/1Defs.h (SIM-NOTX-BEGIN .. END), with the failsafe block beside it (B29-FAILSAFE-MASK) so the whole
// morning can be played: Test1 on the simulator, transmitter off, restarted by an update.
// Malcolm, 11 Nov 2026: "Suddenly and unexpectedly it turned on the sim motor - which was noisy so I disconnected it!!"
#include <cstdio>
#include <cstdint>
#include <cstring>
static uint16_t channelMicros[16];
static bool     failsafeSet = false;
static uint16_t failsafeMicros[16];
static uint16_t failsafeMask = 0;
#include FS_BLOCK
#include SIM_BLOCK
static int fails = 0;
static void expect(const char* what, long got, long want) {
    if (got != want) fails++;
    printf("%s %-100s %ld\n", got == want ? "PASS" : "FAIL", what, got);
}
// One pass of the simulator part of loop(), as main.cpp has it: returns what goes to the simulator on the motor channel.
static const uint32_t HOLD = 3000;
static uint16_t pass(bool everHeard, uint32_t quietMs, uint8_t motorCh, bool inverted) {
    const bool lost = simGivenFailsafe(everHeard, quietMs, HOLD);
    const bool driven = lost && failsafeDrive();
    const uint16_t offUs = simMotorOffUs(everHeard, driven, motorCh, inverted);
    if (offUs) channelMicros[motorCh - 1] = offUs;
    return channelMicros[5];                                    // channel 6: Test1's motor (HIGH = off)
}
static void bootDefaults() { for (int i = 0; i < 16; ++i) channelMicros[i] = i < 5 ? 1500 : 500; }   // setup(): sticks centred, switches low

int main() {
    // the rule
    expect("never heard a transmitter: the saved positions are given (it was: only after one had been heard and lost)", simGivenFailsafe(false, 0, HOLD), 1);
    expect("never heard, an hour after the start: still given", simGivenFailsafe(false, 3600000, HOLD), 1);
    expect("heard, quiet for 1 s: not yet (the receiver holds the last positions)", simGivenFailsafe(true, 1000, HOLD), 0);
    expect("heard, quiet for exactly the hold (3 s): not yet", simGivenFailsafe(true, 3000, HOLD), 0);
    expect("heard, quiet for 3.001 s: given", simGivenFailsafe(true, 3001, HOLD), 1);
    expect("motor-off: never heard, no failsafe driving, motor on channel 6 inverted (HIGH = off): 2500", simMotorOffUs(false, false, 6, true), 2500);
    expect("motor-off: ... not inverted: 500", simMotorOffUs(false, false, 6, false), 500);
    expect("motor-off: the throttle stick's channel 3, not inverted: 500, not the centred 1500 of the start", simMotorOffUs(false, false, 3, false), 500);
    expect("motor-off: a saved failsafe is driving: left alone", simMotorOffUs(false, true, 6, true), 0);
    expect("motor-off: a transmitter has been heard: left alone", simMotorOffUs(true, false, 6, true), 0);
    expect("motor-off: no motor channel chosen: left alone", simMotorOffUs(false, false, 0, true), 0);
    expect("motor-off: a channel number out of range: left alone", simMotorOffUs(false, false, 17, true), 0);

    // 11 Nov 2026, Test1: the failsafe Malcolm saved from the transmitter (motor off = channel 6 HIGH), all 16 ticked
    const uint16_t saved[16] = { 1502, 1501, 959, 1498, 2055, 2055, 2055, 945, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 667 };
    memcpy(failsafeMicros, saved, sizeof saved); failsafeSet = true; failsafeMask = 0xFFFF;
    bootDefaults();
    expect("Test1 restarted, transmitter off, before 0.9.924: channel 6 at the start-up 500 = the sim's motor ON", channelMicros[5], 500);
    expect("Test1 restarted, transmitter off, the first pass of loop(): channel 6 at the saved 2055 = motor OFF", pass(false, 12, 6, true), 2055);
    expect("... and the throttle stick's channel 3 at the saved 959, not centred", channelMicros[2], 959);
    expect("... every one of the 16 as saved", memcmp(channelMicros, saved, sizeof saved) == 0, 1);
    expect("... still so ten minutes later", pass(false, 600000, 6, true), 2055);
    // the transmitter comes on: its own channels arrive, and are left alone
    for (int i = 0; i < 16; ++i) channelMicros[i] = 1500;
    channelMicros[5] = 667;                                     // the pilot switches the motor ON
    expect("transmitter heard, motor switched on: the sim gets the pilot's 667, nothing overrides it", pass(true, 2, 6, true), 667);
    expect("transmitter off again, 2 s: held as it was", pass(true, 2000, 6, true), 667);
    expect("transmitter off 3.5 s: the saved positions - motor OFF", pass(true, 3500, 6, true), 2055);

    // only some channels ticked: the others are not touched (B29)
    bootDefaults(); failsafeMask = (1u << 5);                   // channel 6 only
    expect("only channel 6 ticked: it is driven at the start (2055)", pass(false, 5, 6, true), 2055);
    expect("... and an unticked channel keeps its start-up value", channelMicros[2], 1500);

    // no failsafe saved at all: the motor channel the spool-up knows of is held off instead
    bootDefaults(); failsafeSet = false; failsafeMask = 0;
    expect("no failsafe saved, motor on channel 6 inverted: held at 2500 = motor OFF", pass(false, 5, 6, true), 2500);
    bootDefaults();
    expect("no failsafe saved and no motor channel chosen: the start-up positions, as before", pass(false, 5, 0, true), 500);
    bootDefaults(); channelMicros[5] = 700;
    expect("no failsafe saved, a transmitter heard: the pilot's own value is never overridden", pass(true, 5, 6, true), 700);
    expect("... nor when it goes quiet with nothing saved (the sim freezes at the last values, as before)", pass(true, 9000, 6, true), 700);

    printf("\n%s\n", fails ? "FAILED" : "ALL PASS");
    return fails ? 1 : 0;
}
