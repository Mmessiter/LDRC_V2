#!/usr/bin/env python3
"""Host test of B209 (Malcolm, 11 Nov 2026): "When Rotorflight is NOT detected, and was not detected at last connection
(if not yet connected) arming channel should be entirely ignored. No gaps should be ignored - the arming channel is never
forced high or low. And any other arming channel functions are not needed."
The ARMRULE block of include/1Definitions.h, FixArmingChannel (src/main.cpp), ModelSeemsArmed (include/Parameters.h)
and the receiver's item 31 in include/transceiver.h, lifted and run on the Mac over a fake model; then the sources:
every arming-channel function asks ArmingManaged(), the model file reads and writes through the session rule.
Priority One: within a session the rule never goes from Rotorflight to none - a heli never loses its arming in the air.
   python3 dev/test_armrule/test_armrule.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
def lift(rel, start):
    s = src(rel); i = s.index(start); j = s.index('{', i); d = 0
    for k in range(j, len(s)):
        if s[k] == '{': d += 1
        elif s[k] == '}':
            d -= 1
            if d == 0: return s[i:k + 1] + '\n'
    raise SystemExit('unbalanced: ' + start)
defs = src('include/1Definitions.h')
a = defs.index('// ARMRULE-BEGIN'); b = defs.index('// ARMRULE-END')
RULE = defs[a:b]
trx = src('include/transceiver.h')
m = re.search(r'\n(\s*RfAnswer\(v\);\n.*?RotorFlight_Version = RFVersions\[RotorFlight_V\];)', trx, re.S)
assert m, "item 31's handling not found in transceiver.h"
ITEM31 = m.group(1)
PROG = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#define CHANNELSUSED 16
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static uint32_t ModelNumber = 3;
static uint8_t ArmingChannel = 6;
static uint8_t RotorFlight_V = 0;
static float RotorFlight_Version = 0, RFVersions[3] = {0, 2.2f, 2.3f};
static bool Armed = false, BindingEnabled = false, BuddyPupilOnWireless = false, SafetyON = true;
static uint16_t SendBuffer[CHANNELSUSED + 1];
''' + RULE + lift('src/main.cpp', 'void FixArmingChannel()') + lift('include/Parameters.h', 'bool ModelSeemsArmed(char *why, size_t n)') + r'''
static void Answer31(uint8_t v) {''' + ITEM31 + r'''
}
static void Read(uint32_t mnum, uint8_t fileByte) { RotorFlight_V = RfFlagAfterRead(mnum, fileByte); }   // as ReadOneModel
static void Secs(int n, bool connected, int answer) { for (int i = 0; i < n; ++i) { if (answer >= 0) Answer31((uint8_t)answer); RfRecordTick(connected); } }
static bool SeemsArmed() { char w[128]; return ModelSeemsArmed(w, sizeof(w)); }
static void PowerUp() { RfSessionModel = 0xFFFFFFFF; }
int main() {
    // 1. a model never found to be Rotorflight (file 0), not yet connected: the arming channel is ignored entirely
    PowerUp(); Read(3, 0);
    CHECK(!ArmingManaged());
    SendBuffer[5] = 1500; Armed = false; FixArmingChannel(); CHECK(SendBuffer[5] == 1500);   // never forced low...
    Armed = true; FixArmingChannel(); CHECK(SendBuffer[5] == 1500); Armed = false;           // ...nor high
    SendBuffer[5] = 2000; CHECK(!SeemsArmed());                    // no "Model may be armed: channel 6" (B45's check, gone)
    // 2. connected, the receiver says "none" for a minute: still ignored, and the file is told "none"
    Secs(60, true, 0); CHECK(!ArmingManaged()); CHECK(RfFlagToSave(3) == 0);
    // 3. the receiver says Rotorflight 2.3: managed at once - the safety drives the channel - and the file keeps it
    Answer31(2); CHECK(ArmingManaged()); CHECK(RotorFlight_V == 2);
    SendBuffer[5] = 1500; FixArmingChannel(); CHECK(SendBuffer[5] == 667);
    Armed = true; FixArmingChannel(); CHECK(SendBuffer[5] == 2233); Armed = false;
    SafetyON = false; CHECK(SeemsArmed()); SafetyON = true; CHECK(!SeemsArmed());
    CHECK(RfFlagToSave(3) == 2);
    // 4. the next session: found at the last connection, so managed BEFORE the receiver says anything ("not yet connected")
    PowerUp(); Read(3, 2); CHECK(ArmingManaged());
    // 5. this time it hears only "none": managed for the WHOLE session (B46: the flight controller may not have answered
    //    the receiver yet - and a heli in the air never loses its arming); after 30 s connected the file is told "none"
    Secs(29, true, 0); CHECK(ArmingManaged()); CHECK(RfFlagToSave(3) == 2);
    Secs(2, true, 0); CHECK(ArmingManaged()); CHECK(RotorFlight_V == 2); CHECK(RfFlagToSave(3) == 0);
    SendBuffer[5] = 1500; FixArmingChannel(); CHECK(SendBuffer[5] == 667);      // still driven by the safety
    // 6. a re-read of the same model in the session (after a calibration, a buddy session) keeps what the session had
    Read(3, 0); CHECK(ArmingManaged()); CHECK(RotorFlight_V == 2);
    // 7. a moment's read of ANOTHER model is that model's own data; the session is untouched
    Read(4, 1); CHECK(RotorFlight_V == 1); Read(3, 0); CHECK(RotorFlight_V == 2); CHECK(RfFlagToSave(4) == RotorFlight_V);
    // 8. the session after: not found at the last connection, not yet found now - ignored again, until the receiver says so
    PowerUp(); Read(3, 0); CHECK(!ArmingManaged());
    Secs(5, true, 0); CHECK(!ArmingManaged());
    Answer31(1); CHECK(ArmingManaged()); CHECK(RfFlagToSave(3) == 1);
    // 9. a receiver that never answers item 31 (or a session too short to say): the file keeps what it had
    PowerUp(); Read(3, 2); Secs(120, true, -1); CHECK(ArmingManaged()); CHECK(RfFlagToSave(3) == 2);
    PowerUp(); Read(3, 2); Secs(10, true, 0); CHECK(RfFlagToSave(3) == 2);
    // 10. seconds NOT connected are not counted
    PowerUp(); Read(3, 2); Answer31(0); Secs(100, false, -1); CHECK(RfFlagToSave(3) == 2);
    // 11. a model reset to its defaults (B06: the old flag must not come back): the session is over, RAM's 0 is saved
    PowerUp(); Read(3, 2); RotorFlight_V = 0; RfSessionModel = 0xFFFFFFFF; CHECK(RfFlagToSave(3) == 0); CHECK(!ArmingManaged());
    // 12. a corrupt byte in the file is no Rotorflight
    PowerUp(); Read(3, 7); CHECK(RotorFlight_V == 0); CHECK(!ArmingManaged());
    // 13. an arming channel out of range is never touched, Rotorflight or not
    PowerUp(); Read(3, 2); ArmingChannel = 0; CHECK(!ArmingManaged()); SendBuffer[0] = 1234; FixArmingChannel(); CHECK(SendBuffer[0] == 1234);
    ArmingChannel = 17; CHECK(!ArmingManaged()); ArmingChannel = 6;
    // 14. binding and a buddy pupil: managed, but the transmitter does not drive it then (as before)
    BindingEnabled = true; SendBuffer[5] = 1500; FixArmingChannel(); CHECK(SendBuffer[5] == 1500); BindingEnabled = false;
    printf("test_armrule: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp()
open(os.path.join(d, 't.cpp'), 'w').write(PROG)
r = subprocess.run(['c++', '-std=c++17', '-Wall', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')],
                   capture_output=True, text=True)
if r.returncode:
    print(r.stderr[:3000]); sys.exit(1)
r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
print(r.stdout.strip()); bad = r.returncode != 0

# ---- the sources: every arming-channel function asks the rule
checks = fails = 0
def check(c, what):
    global checks, fails
    checks += 1
    if not c: fails += 1; print('FAIL (source):', what)
main = src('src/main.cpp'); par = src('include/Parameters.h'); mot = src('include/Motor_sign.h'); sd = src('include/SDcard.h')
fix = lift('src/main.cpp', 'void FixArmingChannel()')
check('ArmingManaged()' in fix and 'RotorFlight_V' not in fix, 'FixArmingChannel asks ArmingManaged')
gap = lift('include/transceiver.h', 'void CheckGap()')
check('GapStartedDisarmed = ArmingManaged() && !Armed' in gap, 'CheckGap: no gap left out without Rotorflight')
msa = lift('include/Parameters.h', 'bool ModelSeemsArmed(char *why, size_t n)')
check(re.search(r'if \(!ArmingManaged\(\)\)\s*return false;', msa) is not None, 'ModelSeemsArmed: nothing to ask without Rotorflight')
check('const bool hold = ArmingManaged() && SafetyIsOff()' in mot, 'SafetyHoldUpdate: held only where the safety drives the arming channel')
check('ArmingManaged() ? 2 : 1' in mot, 'the red box: no "ARMING ON!!" without an arming channel driven')
check(main.count('(ArmingManaged() && ch == ArmingChannel - 1)') == 2, 'the calibration notes leave the arming channel out only when forced')
check('RfFlagAfterRead(Mnum, SDRead8BITS(SDCardAddress))' in sd, 'ReadOneModel reads the flag through the session rule')
check('SDUpdate8BITS(SDCardAddress, RfFlagToSave(mnum))' in sd, 'SaveOneModel writes the session answer')
check('RfRecordTick(LedWasGreen);' in main, 'the once-a-second round counts the seconds connected')
check('RfSessionModel = 0xFFFFFFFF; // B209' in main, 'the defaults end a session (B06)')
check(re.search(r'\bif \(ArmingChannel >= 1 && ch == ArmingChannel - 1\)', main) is None, 'no arming-channel use left that ignores the rule')
# the only RotorFlight_V-gated arming uses left are the Rotorflight pages' own (RF_Switches.h)
for rel in ('src/main.cpp', 'include/transceiver.h', 'include/Parameters.h', 'include/Motor_sign.h'):
    s = src(rel)
    check(re.search(r'RotorFlight_V\s*&&\s*ArmingChannel', s) is None, rel + ': no "RotorFlight_V && ArmingChannel" left')
print('test_armrule (sources): %d checks, %d failures' % (checks, fails))
sys.exit(1 if (bad or fails) else 0)
