#!/usr/bin/env python3
"""Host test of the stick calibration (Malcolm, 17 Oct 2026, going to bed: "Tomorrow I will test stick recalibration so
during the night you might like to check we have not inadvertently screwed it up!"). Calibrate.h's ReduceLimits,
CalibrateSticks, ChannelCentres and InitMaxMin are lifted out and run on the Mac over a fake ADC, with B110's StickMicros
and B113's range functions beside them: the ends found are the furthest readings, the centres and quarter points follow,
the switch inputs get 500 / 1500 / 2500, the bars during calibration run 0 to 100 whatever the model's own range, and the
curve page's Input then reads 1000 / 1500 / 2000 at the calibrated ends and centre. Then the flow in main.cpp as source:
start = the defaults (the range wide) + ReduceLimits, nothing saved; Next; Finish = the calibration saved and the model
(its range too) read back; OK part way = the card's values back; the Calibrate page's bars untouched by B109's numbers.
   python3 dev/test_calibrate/test_calibrate.py"""
import json, os, re, subprocess, sys, tempfile
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
main = src('src/main.cpp'); cal = src('include/Calibrate.h'); util = src('include/Utilities.h'); defs1 = src('include/1Definitions.h')
DEFS = '\n'.join(l for l in defs1.split('\n') if re.match(r'#define (RANGE_NARROW_LO|RANGE_NARROW_HI|MAXRESOLUTION|PROPOCHANNELS|CHANNELSUSED|MINMICROS|MAXMICROS) ', l)) + '\n'
assert DEFS.count('#define') == 7, DEFS
INLINES = '\n'.join(l for l in util.split('\n') if re.match(r'inline uint16_t (RangeLo|RangeHi|CurveMicros)\(', l)) + '\n'
assert INLINES.count('inline') == 3, INLINES
PROG = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <type_traits>
#define FLASHMEM
#define FASTRUN
#define constrain(a, l, h) ((a) < (l) ? (l) : ((a) > (h) ? (h) : (a)))
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// Teensy 4's map() (cores/teensy4/wiring.h): the whole-number one ROUNDS
template <class T, class A, class B, class C, class D>
long map(T _x, A _in_min, B _in_max, C _out_min, D _out_max, typename std::enable_if<std::is_integral<T>::value>::type * = 0)
{
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
static uint16_t ChannelMin[CHANNELSUSED + 1], ChannelMidLow[CHANNELSUSED + 1], ChannelCentre[CHANNELSUSED + 1], ChannelMidHi[CHANNELSUSED + 1], ChannelMax[CHANNELSUSED + 1];
static uint8_t MinDegrees[5][CHANNELSUSED + 1], MidLowDegrees[5][CHANNELSUSED + 1], CentreDegrees[5][CHANNELSUSED + 1], MidHiDegrees[5][CHANNELSUSED + 1], MaxDegrees[5][CHANNELSUSED + 1];
static uint8_t Bank = 1, MaxRangeNarrow = 0; static int DualRateValue = 0; static bool NewCompressNeeded = true;
static int reading[PROPOCHANNELS];                      // the fake ADC: what each input reads now
struct FakeAdc { int analogRead(int pin) { return reading[pin]; } };
static FakeAdc fakeAdc; static FakeAdc *adc = &fakeAdc;
static int AnalogueInput[PROPOCHANNELS] = {0, 1, 2, 3, 4, 5, 6, 7};
static int AnalogueReed(uint8_t i) { return reading[i]; }
static int inputsRead = 0, outputsDone = 0, barsShown = 0, pipelines = 0, edgeSwitches = 0;
static void GetAllInputs() { ++inputsRead; }
static void CalculateAllOutputs() { ++outputsDone; }
static void ShowServoPos() { ++barsShown; }
static void GetNewChannelValues() { ++pipelines; }
static void CalibrateEdgeSwitches() { ++edgeSwitches; }
''' + INLINES + lift('include/Utilities.h', 'uint8_t IntoLowerRes(uint16_t HiRes)') + lift('include/Calibrate.h', 'void ReduceLimits()') + lift('include/Calibrate.h', 'void CalibrateSticks()') + lift('include/Calibrate.h', 'void ChannelCentres()') + lift('include/Calibrate.h', 'FLASHMEM void InitMaxMin()') + lift('src/main.cpp', 'FLASHMEM int StickMicros(') + r'''
int main()
{
    // the sticks and knobs: each input its own ends and centre (none at the ADC's own ends, none at its middle)
    int lo[PROPOCHANNELS], hi[PROPOCHANNELS], mid[PROPOCHANNELS];
    for (int i = 0; i < PROPOCHANNELS; ++i) { lo[i] = 300 + 50 * i; hi[i] = 3900 - 40 * i; mid[i] = 2000 + 10 * i; }
    // 1. ReduceLimits: the limits pulled to the middle; the current bank's curves 0 / 90 / 180, the other banks' untouched
    Bank = 2;
    for (int b = 0; b <= 4; ++b) for (int i = 0; i < CHANNELSUSED; ++i) { MinDegrees[b][i] = 30; MidLowDegrees[b][i] = 60; CentreDegrees[b][i] = 90; MidHiDegrees[b][i] = 120; MaxDegrees[b][i] = 150; }
    ReduceLimits();
    for (int i = 0; i < CHANNELSUSED; ++i) CHECK(ChannelMax[i] == MAXRESOLUTION / 2 && ChannelMin[i] == MAXRESOLUTION / 2);
    for (int i = 0; i < CHANNELSUSED; ++i) CHECK(MaxDegrees[2][i] == 180 && CentreDegrees[2][i] == 90 && MinDegrees[2][i] == 0);
    for (int b = 1; b <= 4; ++b) if (b != 2) for (int i = 0; i < CHANNELSUSED; ++i) CHECK(MaxDegrees[b][i] == 150 && MinDegrees[b][i] == 30);
    // 2. CalibrateSticks, pass after pass while the pilot sweeps: the ends are the furthest readings seen; each pass works the outputs out and shows the bars
    for (int step = 0; step <= 20; ++step)
    {
        for (int i = 0; i < PROPOCHANNELS; ++i) reading[i] = lo[i] + (hi[i] - lo[i]) * step / 20;
        CalibrateSticks();
    }
    for (int i = 0; i < PROPOCHANNELS; ++i) { reading[i] = mid[i]; }
    CalibrateSticks();                                                          // (back towards the middle: the ends stay)
    for (int i = 0; i < PROPOCHANNELS; ++i) CHECK(ChannelMin[i] == lo[i] && ChannelMax[i] == hi[i]);
    for (int i = PROPOCHANNELS; i < CHANNELSUSED; ++i) CHECK(ChannelMin[i] == MAXRESOLUTION / 2 && ChannelMax[i] == MAXRESOLUTION / 2);   // (no ADC: left as ReduceLimits put them)
    CHECK(inputsRead == 22 && outputsDone == 22 && barsShown == 22 && DualRateValue == 100 && !NewCompressNeeded);
    // 3. ChannelCentres: the centre is the reading now; the quarter points half way to each end; the switch inputs 500 / 1500 / 2500
    for (int i = 0; i < PROPOCHANNELS; ++i) reading[i] = mid[i];
    ChannelCentres();
    for (int i = 0; i < PROPOCHANNELS; ++i)
    {
        CHECK(ChannelCentre[i] == mid[i]);
        CHECK(ChannelMidHi[i] == mid[i] + (hi[i] - mid[i]) / 2 && ChannelMidLow[i] == lo[i] + (mid[i] - lo[i]) / 2);
    }
    for (int i = PROPOCHANNELS; i < CHANNELSUSED; ++i) CHECK(ChannelMin[i] == 500 && ChannelCentre[i] == 1500 && ChannelMax[i] == 2500);
    CHECK(pipelines == 1 && barsShown == 23 && edgeSwitches == 1);
    // 4. B110's Input on the curve page, after this calibration: 1000 / 1500 / 2000 at the ends and centre, the quarter points 1250 / 1750
    for (int i = 0; i < 4; ++i)
    {
        CHECK(StickMicros((uint8_t)i, ChannelMin[i]) == 1000 && StickMicros((uint8_t)i, ChannelCentre[i]) == 1500 && StickMicros((uint8_t)i, ChannelMax[i]) == 2000);
        CHECK(abs(StickMicros((uint8_t)i, ChannelMidLow[i]) - 1250) <= 1 && abs(StickMicros((uint8_t)i, ChannelMidHi[i]) - 1750) <= 1);
        CHECK(StickMicros((uint8_t)i, 0) <= 1000 && StickMicros((uint8_t)i, MAXRESOLUTION) >= 2000);   // (the stick past its calibration: beyond, not back)
    }
    // 5. the bars during calibration: the curve ReduceLimits leaves (0 / 90 / 180) puts a stick's end, middle and end at 0 / 50 / 100 - on either range
    for (int narrow = 0; narrow <= 1; ++narrow)
    {
        MaxRangeNarrow = (uint8_t)narrow;
        CHECK(IntoLowerRes(CurveMicros(0)) == 0 && IntoLowerRes(CurveMicros(90)) == 50 && IntoLowerRes(CurveMicros(180)) == 100);
    }
    MaxRangeNarrow = 0;
    // 6. InitMaxMin (a reset): the ADC's whole span
    InitMaxMin();
    for (int i = 0; i < CHANNELSUSED; ++i) CHECK(ChannelMax[i] == 4095 && ChannelMidHi[i] == 3071 && ChannelCentre[i] == 2047 && ChannelMidLow[i] == 1023 && ChannelMin[i] == 0);
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp()
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(PROG)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:3000]); sys.exit(1)
r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
print('behaviour:', r.stdout.strip()); sys.stderr.write(r.stderr)
fails = r.returncode != 0
checks = 0
def check(ok, what):
    global checks, fails
    checks += 1
    if not ok: fails = True; print('FAIL:', what)
# ---- the flow, as source
i0 = main.find('Look("Starting calibration")'); seg = main[i0:main.find('CurrentMode = CALIBRATELIMITS', i0)]
check(i0 > 0 and 'SetDefaultValues(true);' in seg and 'ReduceLimits();' in seg and 'ResetSwitchNumbers();' in seg and 'Save' not in seg, 'start: the defaults for calibrating, the limits pulled in, nothing saved (B17)')
sdv = lift('src/main.cpp', 'void SetDefaultValues(bool Calibrating)')
check('MaxRangeNarrow = 0;' in sdv and sdv.index('MaxRangeNarrow = 0;') < sdv.index('if (Calibrating)'), "a calibration runs on the wide range (B113's byte reset with the other defaults): ReduceLimits's 0 / 180 reach the bars' ends")
check(re.search(r'case CALIBRATELIMITS:[^\n]*\n\s*CalibrateSticks\(\);', main) is not None and re.search(r'case CENTRESTICKS:[^\n]*\n\s*ChannelCentres\(\);', main) is not None, 'the two steps run from the main loop, nothing sent meanwhile')
i1 = main.find('if (CurrentMode == CENTRESTICKS)'); seg = main[i1:i1 + 700]
check('SaveTransmitterParameters();' in seg and seg.index('SaveTransmitterParameters();') < seg.index('LoadAllParameters();') and 'CurrentMode = NORMAL;' in seg, 'Finish: the calibration saved, then everything (the model too) read back from the card')
i2 = main.find('B17: OK part way through'); seg = main[i2 - 200:i2 + 500]
check('LoadAllParameters();' in seg and 'ReadOneModel(ModelNumber);' in seg, "OK part way: the card's values back, the model re-read")
sdc = src('include/SDcard.h')
lap = lift('include/SDcard.h', next(l for l in sdc.split('\n') if l.endswith('LoadAllParameters()') and not l.startswith(' ') and ';' not in l))
check('ReadOneModel(' in lap and 'ReadCheckSum32();\n    ReadModelExtension();' in sdc, "the model read back after a calibration brings its max range with it (B113's extension)")
sp = lift('src/main.cpp', 'FASTRUN void ShowServoPos()')
check('(CurrentView == STICKSVIEW) || (CurrentView == FRONTVIEW) || (CurrentView == CALIBRATEVIEW)' in sp and re.search(r'if \(CurrentView == STICKSVIEW\)\s*\n\s*ShowChannelMicros\(\);', sp) is not None, "the Calibrate page's eight bars as before; B109's numbers only on the Channels page")
check('MaxRange' not in cal and 'CurveMicros' not in cal and 'IntoHigherRes' not in cal and 'IntoLowerRes' not in cal, "Calibrate.h works in the ADC's own units: nothing of today's changes in it")
check('ChannelMin[i] = 500;' in cal and 'ChannelCentre[i] = 1500;' in cal and 'ChannelMax[i] = 2500;' in cal, "the switch inputs' fixed calibration (what ReadThreePositionSwitch returns)")
check('if (CurrentView == CALIBRATEVIEW)\n        return;' in util, 'the screen saver leaves the Calibrate page alone')
help_c = open(os.path.join(ROOT, 'Help files for SD', 'CALIB.TXT')).read()
check("Then press 'Next'." in help_c and "Then press 'Finish'." in help_c and 'Calibration saved' in help_c, 'CALIB.TXT describes the three presses')
EMU = os.path.join(ROOT, '..', 'ESP32-board2', 'board4', 'nextion-emulator')
P = os.path.join(EMU, 'sd', 'hmi', 'pages', '22.json')
if os.path.exists(P):
    pg = json.load(open(P)); by = {c['n']: c for c in pg['comps']}
    check(pg['name'] == 'CalibrateView' and all('Ch%d' % i in by and by['Ch%d' % i]['t'] == 'progress bar' for i in range(1, 9)) and 'Ch9' not in by, 'page 22: the eight bars')
    check(by['b0']['ev'].get('r') == 'print "Calibrate1"' and 'MainSetup' in by['b2']['ev'].get('r', ''), 'page 22: Calibrate sticks etc. and OK as the Teensy expects')
    check(not any(n.startswith('us') for n in by) and not any(n.startswith('mr') for n in by), "page 22: none of the Channels page's new parts")
else:
    print('(ESP32-board2 is not here: the page not checked)')
print('flow and page: %d checks%s' % (checks, ', FAILED' if fails else ''))
sys.exit(1 if fails else 0)
