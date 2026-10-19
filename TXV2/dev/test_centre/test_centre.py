#!/usr/bin/env python3
"""Host test of B126, the centre note (Malcolm, 19 Oct 2026: "when the transmitter boots up, if it sees Rotorflight is used
for this model, and if it also sees that the centre position of Aileron, elevator, or rudder is not where it should be,
1500, then it should warn the user of this as well as which flight mode is not properly centred"). CentreNote and
StagesAfterInputs are lifted out of main.cpp, with the real RerouteOutputs and ServoReverse, and run on the Mac over fake
sticks and fake curve, trim and subtrim stages: nothing said without Rotorflight or when all is well; a bank's curve, trim
or subtrim that moves a cyclic or tail channel off 1500 is named with its bank; the throttle or collective stick's
channels, the motor channel, the arming channel and the knobs are left alone; a routed channel is read where it went; a
reversed channel is read reversed; three lines at most, in bank order; the box's room; the bank and the frame's buffers
put back from the sticks afterwards. Then the flow as source: the tick's guards, the sound, the two places it is set.
   python3 dev/test_centre/test_centre.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
def lift(rel, head):
    lines = src(rel).split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
    raise SystemExit('cannot lift %s from %s' % (head, rel))
main = src('src/main.cpp'); defs1 = src('include/1Definitions.h'); util = src('include/Utilities.h'); menu = src('include/MenuOptions.h')
DEFS = '\n'.join(l for l in defs1.split('\n') if re.match(r'#define (CHANNELSUSED|MINMICROS|MAXMICROS|WHAHWHAHMSG) ', l)) + '\n'
assert DEFS.count('#define') == 4, DEFS
PROG = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <type_traits>
#define FLASHMEM
#define FASTRUN
#define constrain(a, l, h) ((a) < (l) ? (l) : ((a) > (h) ? (h) : (a)))
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
template <class T, class A, class B, class C, class D>
long map(T _x, A _in_min, B _in_max, C _out_min, D _out_max, typename std::enable_if<std::is_integral<T>::value>::type * = 0)
{   // Teensy 4's map(): the whole-number one rounds
    long x = _x, in_min = _in_min, in_max = _in_max, out_min = _out_min, out_max = _out_max;
    long in_range = in_max - in_min, out_range = out_max - out_min;
    if (in_range == 0) return out_min + out_range / 2;
    long num = (x - in_min) * out_range;
    if (out_range >= 0) num += in_range / 2; else num -= in_range / 2;
    long result = num / in_range + out_min;
    if (out_range >= 0) { if (in_range * num < 0) return result - 1; } else { if (in_range * num >= 0) return result + 1; }
    return result;
}
''' + DEFS + r'''
static uint8_t RotorFlight_V = 2, Bank = 1, MotorChannel = 4, ArmingChannel = 6;
static uint8_t InPutStick[CHANNELSUSED] = {0, 1, 2, 3, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};   // the Havok's: channel 5, the throttle, from the collective stick
static uint16_t ChannelCentre[CHANNELSUSED + 1] = {2010, 2030, 1990, 2050, 2000, 2000, 2000, 2000};
static uint8_t ChannelOutPut[17] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
static uint16_t InputsBuffer[CHANNELSUSED + 1], PreMixBuffer[CHANNELSUSED + 1], SendBuffer[CHANNELSUSED + 1];
static uint16_t ReversedChannelBITS = 0;
static char ChannelNames[CHANNELSUSED][11] = {{"Aileron"}, {"Elevator"}, {"Collective"}, {"Rudder"}, {"Throttle"}, {"Arming"}, {"Bank"}, {"Ch8"}, {"Ch9"}, {"Rescue"}, {"Ch11"}, {"Ch12"}, {"Ch13"}, {"Ch14"}, {"Ch15"}, {"Ch16"}};
static bool InputIsSwitch(uint8_t) { return false; }
static uint16_t ReadThreePositionSwitch(uint8_t) { return 1500; }
// the fake stages: a curve as an offset at the centre and a straight slope, a trim per bank and stick, a subtrim per channel
static int curveOff[5][CHANNELSUSED], trimOff[5][8], subtrimOff[CHANNELSUSED];
static int stickRaw[8];                                   // what the sticks read now
static int stagesRun = 0;
static void GetAllInputs() { for (int ch = 0; ch < CHANNELSUSED; ++ch) InputsBuffer[ch] = InPutStick[ch] < 8 ? stickRaw[InPutStick[ch]] : 1500; }
static void MixInputs() {}
static void CalculateAllOutputs() { ++stagesRun; for (int ch = 0; ch < CHANNELSUSED; ++ch) { const uint8_t dev = InPutStick[ch]; const int in = dev < 8 ? (int) InputsBuffer[ch] - (int) ChannelCentre[dev] : 0; PreMixBuffer[ch] = SendBuffer[ch] = (uint16_t) (1500 + curveOff[Bank][ch] + in); } }
static void MixOutputs() {}
static void DoTrimsAndSubtrims() { for (int ch = 0; ch < CHANNELSUSED; ++ch) { const uint8_t dev = InPutStick[ch]; SendBuffer[ch] = (uint16_t) ((int) SendBuffer[ch] + subtrimOff[ch] * 5 + (dev < 8 ? trimOff[Bank][dev] : 0)); PreMixBuffer[ch] = SendBuffer[ch]; } }
''' + lift('src/main.cpp', 'void RerouteOutputs()') + lift('include/Utilities.h', 'FASTRUN void ServoReverse()') + lift('src/main.cpp', 'static void StagesAfterInputs()') + lift('src/main.cpp', 'FLASHMEM void CentreNote(char *out, size_t n)') + r'''
static void reset() {
    memset(curveOff, 0, sizeof(curveOff)); memset(trimOff, 0, sizeof(trimOff)); memset(subtrimOff, 0, sizeof(subtrimOff));
    for (int d = 0; d < 8; ++d) stickRaw[d] = ChannelCentre[d];
    for (int i = 0; i < 17; ++i) ChannelOutPut[i] = i;
    ReversedChannelBITS = 0; RotorFlight_V = 2; Bank = 1; MotorChannel = 4; ArmingChannel = 6;
}
static std::string note() { char out[200]; memset(out, 'x', sizeof(out)); CentreNote(out, sizeof(out)); return std::string(out); }
static int lines(const std::string &s) { int n = 1; for (char c : s) if (c == '\n') ++n; return n; }
static int longest(const std::string &s) { int best = 0, cur = 0; for (char c : s) { if (c == '\r') continue; if (c == '\n') { if (cur > best) best = cur; cur = 0; } else ++cur; } return cur > best ? cur : best; }
int main() {
    // 1. nothing to say
    reset(); RotorFlight_V = 0; curveOff[4][1] = -44; CHECK(note() == ""); CHECK(stagesRun == 0);   // no Rotorflight: not even looked at
    reset(); CHECK(note() == ""); CHECK(stagesRun == 5);                                            // four banks looked at, the frame put back
    // 2. the Havok's case: Bank 4's elevator curve off at the centre
    reset(); Bank = 3; curveOff[4][1] = -44;
    { const std::string s = note();
      CHECK(s.rfind("Bank 4: Elevator is 1456", 0) == 0);
      CHECK(s.find("with the stick centred.\r\nPlease put it to the centre\r\nbefore flying.") != std::string::npos);   // (B128: Malcolm's words)
      CHECK(s.find("curve") == std::string::npos);                                               // (B127, Malcolm: the line about curves, trims and subtrims is not needed)
      CHECK(s.size() <= 180 && lines(s) <= 6 && longest(s) <= 40);                                 // the popup's box: 180 characters, 7 lines of 28 px in 218, ~40 characters wide
      CHECK(Bank == 3); }
    // 3. what is left alone: the collective stick's channels (the collective and the throttle), the arming channel, a knob
    reset(); curveOff[1][2] = 60; curveOff[2][4] = -300; curveOff[1][5] = 200; curveOff[3][7] = 90; CHECK(note() == "");
    reset(); MotorChannel = 2; curveOff[1][2] = 60; curveOff[1][4] = 70; CHECK(note() == "");          // the motor channel IS the collective: its stick's other channel (the throttle) is left alone too
    reset(); ArmingChannel = 0; curveOff[1][5] = 200; CHECK(note() == "");                        // (channel 6 from knob 4: a knob is never named)
    // 4. the threshold
    reset(); curveOff[2][0] = 10; CHECK(note() == ""); curveOff[2][0] = 11; CHECK(note().rfind("Bank 2: Aileron is 1511", 0) == 0);
    reset(); curveOff[2][0] = -10; CHECK(note() == ""); curveOff[2][0] = -11; CHECK(note().rfind("Bank 2: Aileron is 1489", 0) == 0);
    // 5. a trim in one bank, a subtrim in every bank: three lines at most, in bank order
    reset(); trimOff[2][0] = 15; subtrimOff[3] = 5;
    { const std::string s = note();
      CHECK(s.rfind("Bank 1: Rudder is 1525\r\nBank 2: Aileron is 1515\r\nBank 2: Rudder is 1525\r\nwith the stick centred.", 0) == 0);
      CHECK(s.size() <= 180 && lines(s) <= 6 && longest(s) <= 40); }
    // 6. routed outputs: the aileron goes out on output 4 and the rudder on output 1; the note still names the aileron
    reset(); ChannelOutPut[0] = 3; ChannelOutPut[3] = 0; curveOff[1][0] = 40; CHECK(note().rfind("Bank 1: Aileron is 1540", 0) == 0);
    // 7. a reversed channel is read as it is sent
    reset(); ReversedChannelBITS = 1 << 1; curveOff[1][1] = -44; CHECK(note().rfind("Bank 1: Elevator is 1544", 0) == 0);
    // 8. the frame's buffers afterwards are the sticks', in the pilot's bank
    reset(); Bank = 2; stickRaw[0] = ChannelCentre[0] + 100; curveOff[4][1] = -44; curveOff[2][0] = 0; note();
    CHECK(Bank == 2 && SendBuffer[0] == 1600 && SendBuffer[1] == 1500);
    // 9. the longest names in three banks still fit the box
    reset(); strcpy(ChannelNames[0], "Collective"); strcpy(ChannelNames[1], "Collective"); strcpy(ChannelNames[3], "Collective"); curveOff[1][0] = 389; curveOff[2][1] = -389; curveOff[3][3] = 389;
    { const std::string s = note(); CHECK(s.size() <= 180 && lines(s) <= 6 && longest(s) <= 40); CHECK(s.rfind("Bank 1: Collective is 1889\r\nBank 2: Collective is 1111\r\nBank 3: Collective is 1889\r\n", 0) == 0); }
    printf("test_centre: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 't.cpp'), 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-Wall', '-Wno-unused-function', '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    bad = r.returncode != 0
# ---- the flow, as source
fl = 0; flfail = False
def check(ok, what):
    global fl, flfail
    fl += 1
    if not ok: flfail = True; print('FAIL:', what)
tick = main[main.find('void CentreNoteTick()'):]; tick = tick[:tick.find('\n}\n') + 3]
check('CentreNoteTick()' in main and all(g in tick for g in ('!CentreNotePending', 'FwTrialRunning', 'CurrentView != FRONTVIEW', 'ModelMatched', 'ModalWaits')), "the tick waits for the front page, nothing connected, no question open, no firmware on trial")
check(tick.index('CentreNotePending = false;') < tick.index('CentreNote(note, sizeof(note));') < tick.index('PlaySound(WHAHWHAHMSG);') < tick.index('MsgBox(pFront, note);') < tick.index('GotoFrontView();'), 'the tick: said once, the sound, the box, the front page back')
check('if (!note[0])\n        return;' in tick, 'nothing said when the note is empty')
boot = main[main.find('ClockMessageTick(); // V2 B30/B62/B63'):][:300]
check('CentreNotePending = true;' in boot and 'CentreNoteTick();' in boot, 'set and tried at power-up, after the clock\'s word')
house = main[main.find('ClockMessageTick();        // B63'):][:200]
check('CentreNoteTick();' in house, 'tried once a second with the housekeeping, for after a trial or a model chosen')
mv = menu[menu.find('void ModelViewEnd()'):][:800]
check("if (Confirmed[0] != 'Y')" in mv and 'else\n            CentreNotePending = true;' in mv and mv.index('ReadOneModel(ModelNumber);') < mv.index('CentreNotePending = true;') < mv.index('SaveAllParameters();'), 'a model chosen and confirmed sets the note pending; a refused choice does not')
gn = lift('src/main.cpp', 'FASTRUN void GetNewChannelValues()')
order = [s for s in ('GetAllInputs();', 'MixInputs();', 'CalculateAllOutputs();', 'SlowAnyServos();', 'MixOutputs();', 'DoTrimsAndSubtrims();', 'RerouteOutputs();', 'ServoReverse();') if s in gn]
st = lift('src/main.cpp', 'static void StagesAfterInputs()')
check([s for s in order if s in st] == ['MixInputs();', 'CalculateAllOutputs();', 'MixOutputs();', 'DoTrimsAndSubtrims();', 'RerouteOutputs();', 'ServoReverse();'] and 'SlowAnyServos' not in st, "the note's stages are a frame's, in a frame's order, less the slow servos")
check('bool CentreNotePending = false;' in defs1 and 'void CentreNoteTick();' in defs1 and 'void CentreNote(char *out, size_t n);' in defs1, 'declared for every file')
help_c = open(os.path.join(ROOT, 'Help files for SD', 'CALIB.TXT')).read()
check('At power-up, and when a model is chosen, a Rotorflight model is checked' in help_c, 'CALIB.TXT says so')
print('flow: %d checks%s' % (fl, ', FAILED' if flfail else ''))
sys.exit(1 if (bad or flfail) else 0)
