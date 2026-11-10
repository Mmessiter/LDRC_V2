#!/usr/bin/env python3
"""Host test of the RESTART IN FLIGHT (11 Nov 2026, Malcolm: "If transmitter restarts in flight - and was quiet for less than
30 seconds, then it should avoid sending disarmed to allow continued flight."). Section 6 of include/FlightGuard.h, from
"#define FLIGHT_STAMP_REG" to its end, compiled on the Mac over a make-believe clock chip (its battery-backed RAM on a fake
Wire), a clock, the switches and the log:
  - while connected and flying, a stamp every 2 s (the time, armed or not); cleared when the flying stops; a lost link keeps it;
  - at the next start: less than 30 s old and no reason noted on the way out = a restart in flight; older, a switch-off on
    purpose, no stamp, a dead clock, or a second start = not; each stamp is looked at once;
  - FlightRestartArm: the arming as it was if the safety is still off, the motor switch as it stands, no "change" left for
    the first round of the switches; nothing at all on an ordinary start;
  - the restart ends at the next connection, or after 60 s; it is logged once.
   python3 dev/test_flightrestart/test_flightrestart.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'FlightGuard.h')).read()
a = src.index('#define FLIGHT_STAMP_REG'); b = src.rindex('#endif')
block = src[a:b]
prog = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#define FLASHMEM
#define PSTR(s) (s)
#define DS1307_ADDRESS 0x68
enum { OFF_NONE = 0, OFF_BUTTON = 1, OFF_INACTIVE = 2 };
static uint32_t nowMs = 100000; static uint32_t millis() { return nowMs; }
// ---- the clock chip: its seconds, and its 56 bytes of battery-backed RAM behind a fake Wire
static uint8_t chipRam[64]; static bool chipAnswers = true; static int chipWrites = 0;
static uint32_t chipSeconds = 1762800000UL;          // (10 Nov 2026)
struct FakeWire {
    uint8_t addr = 0, reg = 0; bool regSet = false; std::vector<uint8_t> out; uint8_t ptr = 0;
    void beginTransmission(uint8_t a) { addr = a; regSet = false; out.clear(); }
    size_t write(uint8_t v) { if (!regSet) { reg = v; regSet = true; } else out.push_back(v); return 1; }
    size_t write(const uint8_t *b, size_t n) { for (size_t i = 0; i < n; ++i) write(b[i]); return n; }
    uint8_t endTransmission() { if (!chipAnswers || addr != DS1307_ADDRESS) return 2; for (size_t i = 0; i < out.size(); ++i) chipRam[reg + i] = out[i]; if (!out.empty()) ++chipWrites; ptr = reg; return 0; }
    uint8_t requestFrom(uint8_t a, uint8_t n) { return (chipAnswers && a == DS1307_ADDRESS) ? n : 0; }
    int read() { return chipRam[ptr++]; }
} Wire;
struct tmElements_t { uint32_t s; } tm;
struct FakeRtc { bool read(tmElements_t &t) { t.s = chipSeconds; return chipAnswers; } } RTC;
static uint32_t makeTime(const tmElements_t &t) { return t.s; }
static uint32_t teensySeconds = 1762800000UL;        // (set from the chip at power-up, B169)
struct FakeTeensyClock { uint32_t get() { return teensySeconds; } } Teensy3Clock;
// ---- the transmitter
static bool ClockDead = false, LedWasGreen = false, UseLog = true;
static uint8_t LastOffReason = OFF_NONE;
static bool SafetyON = false, SafetyWasOn = false, MotorEnabled = false, MotorWasEnabled = false, Armed = false;
static uint32_t MotorStartTime = 0;
static bool safetyDefined = true, switchSafetyOn = false, switchMotorOn = true;
static void ReadSafetySwitch() { SafetyON = safetyDefined && switchSafetyOn; }
static void ReadAutoAndMotorSwitch() { MotorEnabled = switchMotorOn; }
static bool SafetyIsOff() { return safetyDefined && !SafetyON; }
static bool RadiosMustBeOff() { return safetyDefined ? SafetyIsOff() : MotorEnabled; }
static std::vector<std::string> logs;
static void LogText(char *t, uint16_t, bool) { logs.push_back(t); }
@BLOCK@
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static uint32_t stampTime() { return (uint32_t)chipRam[0x09] | ((uint32_t)chipRam[0x0A] << 8) | ((uint32_t)chipRam[0x0B] << 16) | ((uint32_t)chipRam[0x0C] << 24); }
// a restart: what the chip keeps stays, the Teensy's memory goes (its globals as they start)
static void reboot(uint32_t quietS, uint8_t offReason = OFF_NONE) {
    chipSeconds += quietS; teensySeconds = chipSeconds; nowMs = 900;
    FlightRestart = false; FlightRestartArmed = false; FlightRestartAt = 0; FlightRestartQuiet = 0; FlightRestartToLog = false; FlightStampOnChip = false; FlightStampLastMs = 0;
    LastOffReason = offReason; LedWasGreen = false; SafetyON = SafetyWasOn = MotorEnabled = MotorWasEnabled = Armed = false; MotorStartTime = 0;
    FlightRestartCheck();
}
static void fly(uint32_t seconds, bool armed) {    // connected, the safety off: the once-a-second round
    LedWasGreen = true; switchSafetyOn = false; SafetyON = false; Armed = armed; MotorEnabled = true;
    for (uint32_t i = 0; i < seconds; ++i) { nowMs += 1000; chipSeconds += 1; teensySeconds += 1; FlightStampTick(); }
}
int main() {
    memset(chipRam, 0xA5, sizeof chipRam);           // (a new chip's RAM holds anything)
    // ---- 1. an ordinary start (no stamp on a new chip): nothing
    reboot(0); CHECK(!FlightRestart);
    FlightRestartArm(); CHECK(!Armed && !MotorEnabled);  // (nothing touched on an ordinary start)
    // ---- 2. flying: a stamp every 2 s, the time and the armed bit
    chipWrites = 0; fly(10, true);
    CHECK(chipRam[0x08] == 0xF5 && chipRam[0x0D] == 1 && stampTime() >= chipSeconds - 2 && stampTime() <= chipSeconds);
    CHECK(chipWrites >= 4 && chipWrites <= 6);         // (every 2 s, not every second)
    // ---- 3. the power goes in flight; back 10 s later: a restart in flight, armed as it was, the motor as its switch
    switchSafetyOn = false; switchMotorOn = true;
    reboot(10); CHECK(FlightRestart && FlightRestartArmed && FlightRestartQuiet >= 10 && FlightRestartQuiet <= 12);
    CHECK(chipRam[0x08] == 0);                         // (looked at once: the stamp is gone)
    FlightRestartArm(); CHECK(Armed && MotorEnabled && MotorWasEnabled == MotorEnabled && SafetyWasOn == SafetyON && !SafetyON && MotorStartTime != 0);
    // the log says it once
    logs.clear(); nowMs += 1000; FlightStampTick(); nowMs += 1000; FlightStampTick();
    CHECK(logs.size() == 1 && logs[0].find("STARTED IN FLIGHT") == 0 && logs[0].find("armed as it was") != std::string::npos);
    // it lasts until the model is connected again
    CHECK(FlightRestart); LedWasGreen = true; nowMs += 1000; FlightStampTick(); CHECK(!FlightRestart);
    // ---- 4. the safety put ON during the restart: not armed, the motor off
    fly(6, true); switchSafetyOn = true; switchMotorOn = true;
    reboot(5); CHECK(FlightRestart); FlightRestartArm(); CHECK(!Armed && !MotorEnabled && SafetyON && SafetyWasOn);
    switchSafetyOn = false;
    // ---- 5. it was flying NOT armed (connected with the safety off, never cycled): not armed after the restart either
    fly(6, false); reboot(5); CHECK(FlightRestart && !FlightRestartArmed); FlightRestartArm(); CHECK(!Armed && MotorEnabled);
    // ---- 6. quiet for 30 s or more: the ground's rules
    fly(6, true); reboot(31); CHECK(!FlightRestart); FlightRestartArm(); CHECK(!Armed && !MotorEnabled);
    fly(6, true); reboot(30); CHECK(!FlightRestart);
    fly(6, true); reboot(28); CHECK(FlightRestart);
    // ---- 7. switched off on purpose (the power button, the inactivity time), however soon after: the ground's rules
    fly(6, true); reboot(3, OFF_BUTTON); CHECK(!FlightRestart && chipRam[0x08] == 0);
    fly(6, true); reboot(3, OFF_INACTIVE); CHECK(!FlightRestart);
    // ---- 8. a second start after a restart in flight: the stamp was looked at once
    fly(6, true); reboot(5); CHECK(FlightRestart); reboot(2); CHECK(!FlightRestart);
    // ---- 9. the flying stops (the safety on): the stamp is cleared; a link merely lost keeps it (to age)
    fly(6, true); CHECK(chipRam[0x08] == 0xF5);
    LedWasGreen = false; nowMs += 3000; FlightStampTick(); CHECK(chipRam[0x08] == 0xF5);   // lost link, still armed: kept
    switchSafetyOn = true; SafetyON = true; nowMs += 1000; FlightStampTick(); CHECK(chipRam[0x08] == 0);   // disarmed: cleared
    reboot(3); CHECK(!FlightRestart); switchSafetyOn = false;
    // ---- 10. a model with NO safety switch: flying = the motor on; never armed by the restart (it could not be armed)
    safetyDefined = false; fly(6, false); reboot(4); CHECK(FlightRestart); FlightRestartArm(); CHECK(!Armed && MotorEnabled); safetyDefined = true;
    // ---- 11. not connected again within 60 s: the ground's rules again
    fly(6, true); reboot(4); CHECK(FlightRestart); LedWasGreen = false; nowMs += 61000; FlightStampTick(); CHECK(!FlightRestart);
    // ---- 12. a dead clock, or a Teensy clock never set from the chip: no stamp, no restart in flight
    ClockDead = true; fly(6, true); CHECK(chipRam[0x08] == 0); reboot(3); CHECK(!FlightRestart); ClockDead = false;
    teensySeconds = 1546300800UL; LedWasGreen = true; nowMs += 3000; FlightStampTick(); CHECK(chipRam[0x08] == 0);   // (1 Jan 2019: unset)
    // ---- 13. a clock chip that stops answering at the start: the ground's rules
    fly(6, true); chipAnswers = false; reboot(3); CHECK(!FlightRestart); chipAnswers = true;
    printf("test_flightrestart: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''.replace('@BLOCK@', block)
with tempfile.TemporaryDirectory() as d:
    c = os.path.join(d, 't.cpp'); exe = os.path.join(d, 't'); open(c, 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-g', '-fsanitize=address,undefined', '-Wno-writable-strings', '-w', '-o', exe, c], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[:3000]); print('FAIL: test_flightrestart did not compile'); sys.exit(1)
    r = subprocess.run([exe], capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr[:3000])
    sys.exit(r.returncode)
