#!/usr/bin/env python3
"""Host test of the buddy box's motor switch (11 Nov 2026, Malcolm: "If buddy has all switches then buddy should be able to stop
motor."). main.cpp FixMotorChannel and BuddyWireless.h BuddyMotorIsOurs / GetTheChannelData / GetTheChannelDataToMixWithOurs,
lifted by their first lines and compiled on the Mac over fakes; then the two transmitters end to end (the pupil's channels as
the master's BuddyBuffer). Whoever flies the motor channel, their motor switch stops the motor:
  - the pupil holding all the switches and flying the motor channel: the PUPIL's motor switch (before: nobody's);
  - the pupil not flying the motor channel: the master's motor switch (before, with all the switches: nobody's);
  - the pupil without the switches: the master's, as before; the master in control: the master's, as before.
   python3 dev/test_buddymotor/test_buddymotor.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def lift(rel, head):
    lines = open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read().split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
    raise SystemExit('cannot lift %s from %s' % (head, rel))
bw = open(os.path.join(TC, 'include/BuddyWireless.h'), encoding='utf-8', errors='replace').read()
code = (lift('src/main.cpp', 'void FixMotorChannel()') + (lift('include/BuddyWireless.h', 'bool BuddyMotorIsOurs()') if 'bool BuddyMotorIsOurs()' in bw else 'static bool BuddyMotorIsOurs() { return false; }   // (the code before 11 Nov 2026 had none)\n')
        + lift('include/BuddyWireless.h', 'void GetTheChannelData()') + lift('include/BuddyWireless.h', 'void GetTheChannelDataToMixWithOurs()'))
prog = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#define CHANNELSUSED 16
#define MINMICROS 500
#define MAXMICROS 2500
#define HALFMICROSRANGE ((MAXMICROS - MINMICROS) / 2)
#define BUDDY_OFF 0
#define BUDDY_NUDGE 1
#define BUDDY_ON 2
static long map(long x, long a, long b, long c, long d) { return (x - a) * (d - c) / (b - a) + c; }
template <class T, class L, class H> static T constrain(T x, L lo, H hi) { return x < (T)lo ? (T)lo : (x > (T)hi ? (T)hi : x); }
static uint16_t IntoHigherRes(uint8_t d) { return (uint16_t)map(d, 0, 180, MINMICROS, MAXMICROS); }
// one transmitter's state at a time (the test swaps the master's and the pupil's in and out)
static uint8_t MotorChannel = 2, MotorChannelZero = 30;
static bool MotorEnabled = false, BindingEnabled = false, BuddyPupilOnWireless = false, BuddyHasAllSwitches = true;
static uint8_t BuddyState = BUDDY_OFF; static uint16_t BuddyControlled = 0xFFFF;
static uint16_t SendBuffer[20], BuddyBuffer[20], PreMixBuffer[20];
@CODE@
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static const uint16_t LOW_ = 500 + (30 * 2000) / 180, STICK = 1800;
// the pupil's transmitter: its sticks (the throttle high), its own motor switch, then FixMotorChannel - what it sends to the master
static void pupilSends(bool allSwitches, bool motorOn) {
    BuddyPupilOnWireless = true; BuddyHasAllSwitches = allSwitches; BuddyState = BUDDY_OFF; MotorEnabled = motorOn;
    for (int i = 0; i < 16; ++i) SendBuffer[i] = STICK;
    FixMotorChannel();
    memcpy(BuddyBuffer, SendBuffer, sizeof SendBuffer);            // (what the master receives: its BuddyBuffer)
}
// the master's transmitter: its sticks (the throttle high too), its own motor switch, the buddy switch, then its loop's order
static uint16_t masterSends(bool allSwitches, bool masterMotorOn, uint8_t state, uint16_t pupilChannels) {
    BuddyPupilOnWireless = false; BuddyHasAllSwitches = allSwitches; BuddyState = state; MotorEnabled = masterMotorOn; BuddyControlled = pupilChannels;
    for (int i = 0; i < 16; ++i) { SendBuffer[i] = STICK; PreMixBuffer[i] = 1500; }
    if (state == BUDDY_ON) GetTheChannelData(); else if (state == BUDDY_NUDGE) GetTheChannelDataToMixWithOurs();
    FixMotorChannel();
    return SendBuffer[MotorChannel];
}
int main() {
    const uint16_t ALL = 0xFFFF, NOT_MOTOR = 0xFFFF & ~(1u << 2);
    for (uint8_t state : { BUDDY_ON, BUDDY_NUDGE }) {
        // the pupil holds all the switches and flies the motor channel: ITS motor switch decides (Malcolm's rule)
        pupilSends(true, false); CHECK(BuddyBuffer[2] == LOW_);
        CHECK(masterSends(true, true, state, ALL) == LOW_);           // the pupil's switch off: stopped, whatever the master's
        CHECK(masterSends(true, false, state, ALL) == LOW_);
        pupilSends(true, true);
        CHECK(masterSends(true, false, state, ALL) == STICK);         // the pupil's switch on: the pupil's stick (the master hands it all over)
        // the pupil holds all the switches but does NOT fly the motor channel: the master's stick, so the master's switch
        pupilSends(true, true);
        CHECK(masterSends(true, false, state, NOT_MOTOR) == LOW_);    // (before: STICK - nobody's switch stopped it)
        CHECK(masterSends(true, true, state, NOT_MOTOR) == STICK);
        // the pupil without the switches: the master's switch, as before
        pupilSends(false, true); CHECK(BuddyBuffer[2] == STICK);      // (a pupil without the switches forces nothing: the master does)
        CHECK(masterSends(false, false, state, ALL) == LOW_);
        CHECK(masterSends(false, true, state, ALL) == STICK);
    }
    // the master in control (the buddy switch off): the master's switch, as before, whatever the pupil's
    pupilSends(true, true);
    CHECK(masterSends(true, false, BUDDY_OFF, ALL) == LOW_);
    CHECK(masterSends(true, true, BUDDY_OFF, ALL) == STICK);
    // binding: nothing forced (as before)
    BindingEnabled = true; pupilSends(true, false); CHECK(BuddyBuffer[2] == STICK); CHECK(masterSends(true, false, BUDDY_OFF, ALL) == STICK); BindingEnabled = false;
    // a motor channel out of range: nothing written anywhere
    { MotorChannel = 200; uint16_t before[20]; for (int i = 0; i < 16; ++i) SendBuffer[i] = STICK; memcpy(before, SendBuffer, sizeof before);
      BuddyPupilOnWireless = true; BuddyHasAllSwitches = true; MotorEnabled = false; FixMotorChannel();
      BuddyPupilOnWireless = false; BuddyState = BUDDY_ON; GetTheChannelData(); GetTheChannelDataToMixWithOurs(); FixMotorChannel();
      CHECK(!BuddyMotorIsOurs()); MotorChannel = 2; }   // (ASan: nothing written past the buffer)
    printf("test_buddymotor: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''.replace('@CODE@', code)
with tempfile.TemporaryDirectory() as d:
    c = os.path.join(d, 't.cpp'); exe = os.path.join(d, 't'); open(c, 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-g', '-fsanitize=address,undefined', '-w', '-o', exe, c], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[:3000]); print('FAIL: test_buddymotor did not compile'); sys.exit(1)
    r = subprocess.run([exe], capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr[:3000])
    sys.exit(r.returncode)
