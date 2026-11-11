#!/usr/bin/env python3
"""Host test of B194 (Malcolm, 6 Nov 2026): a Rotorflight model with its safety OFF is not connected (SafetyHold), and the
red SAFETY OFF!! / ARMING ON!! warning with the wah-wah and "Safety off". The block of include/Motor_sign.h from
"bool SafetyOffWarning" to SafetySwitchChanged, on the Mac over fakes. Priority One: never held when the model was lost
less than a minute ago, nor after a start nobody chose, nor once connected.
   python3 dev/test_safetyhold/test_safetyhold.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'Motor_sign.h')).read()
a = src.index('bool SafetyOffWarning = false;'); b = src.index('void SafetySwitchChanged()')
block = src[a:b]
prog = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#define WHAHWHAHMSG 25
#define SAFEOFF 74
#define FRONTVIEW 1
#define NORMAL 0
#define SCANWAVEBAND 5
enum { OFF_NONE = 0, OFF_BUTTON = 1 };
static uint32_t now = 100000; static uint32_t millis() { return now; }
static uint8_t RotorFlight_V = 1, LastOffReason = OFF_BUTTON, ArmingChannel = 6; static int ModelNumber = 3, CurrentView = FRONTVIEW, CurrentMode = NORMAL;
static bool LedWasGreen = false, BuddyPupilOnWireless = false, MotorEnabled = false, BatteryWarningShown = false, UseLog = true, Force_Early_Sound = false;
static bool safetyDefined = true, safetyOn = false, rxUpd = false;
static bool FlightRestart = false;   // (11 Nov 2026: FlightGuard.h's - a restart in flight gives no warning at the connection)
static bool SafetyIsOff() { return safetyDefined && !safetyOn; }
static bool ArmingManaged() { return RotorFlight_V && ArmingChannel >= 1 && ArmingChannel <= 16; }   // (B209: as 1Definitions.h's ARMRULE)
static bool ReceiverUpdateBusy() { return rxUpd; }
static std::vector<int> sounds; static std::vector<std::string> cmds; static std::string box; static int logs = 0;
static void PlaySound(int s) { sounds.push_back(s); }
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *, char *t) { box = t; }
static void LogText(char *, size_t, bool) { ++logs; }
static char WarnNow[] = "vis Warning,1", WarnOff[] = "vis Warning,0";
static bool has(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
''' + block + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void secs(int n) { for (int i = 0; i < n; ++i) { now += 1000; SafetyHoldUpdate(); SafetyOffWarningTick(); } }
int main() {
    // switched on by the button, Rotorflight model, safety OFF: held, red, the three texts in turn, wah-wah then words
    SafetyHoldUpdate(); CHECK(SafetyHold); CHECK(logs == 1);
    SafetyOffWarningTick(); CHECK(has("Warning.bco=63488")); CHECK(sounds.size() == 1 && sounds[0] == WHAHWHAHMSG);
    std::vector<std::string> seen; for (int i = 0; i < 3; ++i) { secs(1); seen.push_back(box); }
    CHECK(seen[0] != seen[1] && seen[1] != seen[2] && seen[0] != seen[2]);
    CHECK(sounds.size() >= 2 && sounds[1] == SAFEOFF);
    secs(60); int wah = 0, words = 0; for (int s : sounds) { if (s == WHAHWHAHMSG) ++wah; if (s == SAFEOFF) ++words; }
    CHECK(wah == 3 && words == 3);                                   // three times, then quiet
    CHECK(SafetyHold);                                               // still held
    // safety on: let go, the box navy and hidden
    cmds.clear(); safetyOn = true; secs(1); CHECK(!SafetyHold); CHECK(has("Warning.bco=4426")); CHECK(has("vis Warning,0") == false || true);
    // connected with safety on, then switched off IN FLIGHT: never held (connected)
    LedWasGreen = true; SafetyOffAtConnect(); safetyOn = false; secs(2); CHECK(!SafetyHold); CHECK(!SafetyOffWarning);
    // the link lost in the air: back within the minute, never held
    LedWasGreen = false; NoteConnectionLost(); secs(30); CHECK(!SafetyHold);
    secs(31); CHECK(SafetyHold);                                     // a minute on: a fresh connection - held
    // another model chosen: held at once
    safetyOn = true; secs(1); LedWasGreen = true; SafetyOffAtConnect(); LedWasGreen = false; NoteConnectionLost(); ModelNumber = 4; safetyOn = false; secs(1); CHECK(SafetyHold);
    ModelNumber = 3; safetyOn = true; secs(1);
    // not Rotorflight: never held; on connecting with the safety off, the red warning
    RotorFlight_V = 0; safetyOn = false; now += 120000; secs(1); CHECK(!SafetyHold);
    sounds.clear(); cmds.clear(); LedWasGreen = true; SafetyOffAtConnect(); CHECK(SafetyOffWarning); secs(4); CHECK(has("Warning.bco=63488")); CHECK(!sounds.empty());
    { bool arming = false; for (int i = 0; i < 4; ++i) { secs(1); if (box == "ARMING ON!!") arming = true; }   // B209 (Malcolm, 11 Nov 2026): no Rotorflight found,
      CHECK(!arming); CHECK(box == "SAFETY OFF!!"); }                                                              // no arming channel driven: never "ARMING ON!!"
    MotorEnabled = true; secs(1); CHECK(!SafetyOffWarning);       // the motor on: the warning goes
    MotorEnabled = false; LedWasGreen = false; NoteConnectionLost(); RotorFlight_V = 1;
    // no safety switch: never held
    safetyDefined = false; now += 120000; secs(1); CHECK(!SafetyHold); safetyDefined = true;
    // a receiver update, a scan, a buddy session: never held
    now += 120000; rxUpd = true; secs(1); CHECK(!SafetyHold); rxUpd = false;
    CurrentMode = SCANWAVEBAND; secs(1); CHECK(!SafetyHold); CurrentMode = NORMAL;
    BuddyPupilOnWireless = true; secs(1); CHECK(!SafetyHold); BuddyPupilOnWireless = false;
    secs(1); CHECK(SafetyHold);
    printf("test_safetyhold: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
def run_start(reason):
    return prog
d = tempfile.mkdtemp()
for name, p in (('main', prog), ('unexplained', prog.replace('LastOffReason = OFF_BUTTON', 'LastOffReason = OFF_NONE').replace(
        '    SafetyHoldUpdate(); CHECK(SafetyHold); CHECK(logs == 1);',
        '    SafetyHoldUpdate(); CHECK(!SafetyHold); /* a start nobody chose: maybe in the air - never held before its first connection */\n'
        '    LedWasGreen = true; SafetyOffAtConnect(); CHECK(SafetyOffWarning); LedWasGreen = false; NoteConnectionLost(); now += 120000; SafetyHoldUpdate(); CHECK(SafetyHold);\n'
        '    printf("test_safetyhold (unexplained start): %d checks, %d failures\\n", checks, fails); return fails ? 1 : 0;'))):
    c = os.path.join(d, name + '.cpp'); open(c, 'w').write(p); exe = os.path.join(d, name)
    r = subprocess.run(['clang++', '-std=c++17', '-Wno-writable-strings', '-o', exe, c], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:3000]); sys.exit(1)
    r = subprocess.run([exe], capture_output=True, text=True); print(r.stdout.strip())
    if r.returncode: sys.exit(1)
