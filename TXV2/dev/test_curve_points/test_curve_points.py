#!/usr/bin/env python3
"""Host test of B118: a channel's curve with 3, 5, 7 or 9 points (Malcolm, 17 Oct 2026: "Might it be possible for us now to
allow the user to choose 3 points, 5 points, 7 points, or 9 points?").
  1. With five points the flying maths is byte for byte what it was: the old StraightLine / CatmullSpline / Exponential
     interpolations and the old rates scaling (commit fcafc5e, before B118) compiled beside the new, over random curves,
     rates, both max ranges and every stick reading.
  2. 3, 7 and 9 points: Straight passes through every point and runs straight between them; Smooth passes through every
     point; Exponential uses the ends and the centre whatever the count.
  3. Changing the count (CurveResample): the ends and the centre are copied exactly, the new points lie on the old curve,
     5 -> 9 -> 5 comes back exactly, and every bank is done.
  4. The file: the five of old as a sampling of the curve (what a firmware before B118 reads), the curves' block after
     the max range's bytes - written only when wanted or already there, read only whole and sound (markers, counts,
     points, checksum), stale counts never survive a return to five.
  5. The curve page: which number boxes show for each count and shape, with the right values; the Points radios.
   python3 dev/test_curve_points/test_curve_points.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.environ.get('TXV1B_TC', os.path.join(ROOT, 'TransmitterCode'))
OLD_COMMIT = 'fcafc5e'   # B117 + its tests: the last five-point-only firmware
checks = fails = 0
def check(c, what):
    global checks, fails
    checks += 1
    if not c:
        fails += 1
        print('FAIL:', what)
SRC = {}
def src(rel):
    if rel not in SRC: SRC[rel] = open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
    return SRC[rel]
def lift_from(text, head, what):
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
    raise SystemExit('cannot lift %s (%s)' % (head, what))
def lift(rel, head): return lift_from(src(rel), head, rel)
def old(rel):
    r = subprocess.run(['git', 'show', OLD_COMMIT + ':TransmitterCode/' + rel], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return r.stdout if r.returncode == 0 else ''
old_main, old_rates = old('src/main.cpp'), old('include/DualRates.h')
HAVE_OLD = 'ChannelMidLow[InputChannel]' in old_main and 'MinDegrees[Bank][OutputChannel]' in old_rates
if not HAVE_OLD: print('NOTE: commit %s is not in this repository: the comparison with the old maths is skipped' % OLD_COMMIT)
defs = src('include/1Definitions.h'); util = src('include/Utilities.h'); sdc = src('include/SDcard.h'); main = src('src/main.cpp')
DEFS = '\n'.join(l for l in defs.split('\n') if re.match(r'#define (CURVE_POINTS_MAX|STRAIGHTLINES|SMOOTHEDCURVES|EXPONENTIALCURVES|RANGE_NARROW_LO|RANGE_NARROW_HI|MINMICROS|MAXMICROS|CHANNELSUSED|TX_EXT_MAGIC|TX_EXT_MAGIC2|TX_EXT_MAGIC3)\b', l)) + '\n'
assert DEFS.count('#define') == 12, DEFS
DEFS += '\n'.join(l for l in sdc.split('\n') if l.startswith('#define MODEL_EXT_OFFSET_B113 ') or l.startswith('#define MODEL_EXT2_')) + '\n'
assert DEFS.count('#define') == 15, DEFS
INLINES = '\n'.join(l for l in util.split('\n') if re.match(r'inline uint16_t (RangeLo|RangeHi|CurveMicros)\(', l)) + '\n'
assert INLINES.count('inline') == 3, INLINES
def rename(code, a, b): return code.replace(a, b, 1)
OLD = ''
if HAVE_OLD:
    OLD += rename(lift_from(old_main, 'uint16_t CatmullSplineInterpolation(', 'old'), 'CatmullSplineInterpolation(', 'CatmullSplineInterpolationOld(')
    OLD += rename(lift_from(old_main, 'uint16_t StraightLineInterpolation(', 'old'), 'StraightLineInterpolation(', 'StraightLineInterpolationOld(')
    OLD += rename(lift_from(old_main, 'uint16_t ExponentialInterpolation(', 'old'), 'ExponentialInterpolation(', 'ExponentialInterpolationOld(')
    OLD += rename(lift_from(old_rates, 'float CalculateRate(', 'old'), 'CalculateRate(', 'CalculateRateOld(')
    OLD += rename(lift_from(old_rates, 'float UseFullRate(', 'old'), 'UseFullRate(', 'UseFullRateOld(')
    OLD += rename(lift_from(old_rates, 'void GetCurveDots(', 'old'), 'GetCurveDots(', 'GetCurveDotsOld(').replace('CalculateRate(i,', 'CalculateRateOld(i,').replace('UseFullRate(i,', 'UseFullRateOld(i,')
TEENSY_MAP = r'''
#include <type_traits>
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
template <class T, class A, class B, class C, class D>
T map(T x, A in_min, B in_max, C out_min, D out_max, typename std::enable_if<std::is_floating_point<T>::value>::type * = 0)
{
    return (x - (T)in_min) * ((T)out_max - (T)out_min) / ((T)in_max - (T)in_min) + (T)out_min;
}
'''
PROGRAM = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <string>
#include <vector>
#define FASTRUN
#define FLASHMEM
#define constrain(a, l, h) ((a) < (l) ? (l) : ((a) > (h) ? (h) : (a)))
@DEFS@
@MAP@
#include "InterpolationLib.h"
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// the transmitter's state
uint16_t ChannelMin[CHANNELSUSED + 1], ChannelMidLow[CHANNELSUSED + 1], ChannelCentre[CHANNELSUSED + 1], ChannelMidHi[CHANNELSUSED + 1], ChannelMax[CHANNELSUSED + 1];
uint8_t MaxRangeNarrow = 0;
uint8_t CurvePointCount[CHANNELSUSED + 1], CurvePoint[5][CHANNELSUSED + 1][CURVE_POINTS_MAX];
uint8_t MinDegrees[5][CHANNELSUSED + 1], MidLowDegrees[5][CHANNELSUSED + 1], CentreDegrees[5][CHANNELSUSED + 1], MidHiDegrees[5][CHANNELSUSED + 1], MaxDegrees[5][CHANNELSUSED + 1];   // (the old firmware's)
uint8_t InterpolationTypes[5][CHANNELSUSED + 1], Exponential[5][CHANNELSUSED + 1], InPutStick[CHANNELSUSED + 1];
uint8_t Bank = 1, CurrentPoint = 1, ChanneltoSet = 1, DualRateValue = 100, DualRateChannels[8];
uint16_t CurveDots[CURVE_POINTS_MAX]; uint8_t CurveDotsN = 5;
double PointsCount = 5; double xPoints[CURVE_POINTS_MAX], yPoints[CURVE_POINTS_MAX];
uint32_t ModelNumber = 1;
static int saves = 0, redraws = 0; static void SaveOneModel(uint32_t) { ++saves; } static void DisplayCurve() { ++redraws; } static void ClearText() {}
@INLINES@
@CURVEN@
uint8_t CurveMid(uint8_t n) { return (n - 1) / 2; }
@CURVEX@
@LEGACY@
@STRAIGHT@
@MAPWITHEXPO@
@NEWINTERP@
uint16_t (*Interpolate[3])(uint16_t InputValue, uint16_t InputChannel, uint16_t OutputChannel){StraightLineInterpolation, CatmullSplineInterpolation, ExponentialInterpolation};
@NEWRATES@
@RANGEDEG@
@RESAMPLE@
bool CurveDotShown(uint8_t k);
void CheckInvisiblePoint();
@DOTSHOWN@
@INVISIBLE@
@CHOSEN@
@OLD@
// the screen's wire
static std::string stream;
struct FakeSerial { void print(const char *s) { stream += s; } } NEXTION;
@GRAPHCMD@
@LAYOUT@
// the card, as SdFat behaves (a seek beyond the end fails and the position stays; a write at the end appends)
static std::vector<uint8_t> card; static long FileCheckSum = 0; static bool DoingCheckSm = false; static int StartLocation = 0, SDCardAddress = 0;
static size_t cardPos = 0; static int seekWriteFails = 0;
struct FakeFile { size_t size() { return card.size(); } };
static FakeFile ModelsFileNumber;
static bool cardSeek(size_t a) { if (a > card.size()) return false; cardPos = a; return true; }
static uint8_t SDRead8BITS(int a) { cardSeek((size_t) a); const uint8_t r = cardPos < card.size() ? card[cardPos++] : 255; if (!DoingCheckSm) FileCheckSum += r * (a + 1); return r; }
static void SDUpdate8BITS(int a, uint8_t v) { if (!cardSeek((size_t) a)) ++seekWriteFails; if (!DoingCheckSm) FileCheckSum += v * (a + 1); if (cardPos >= card.size()) card.resize(cardPos + 1, 0); card[cardPos++] = v; }
@EXT@
// helpers
static uint32_t seed = 20261017;
static uint32_t rnd() { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static void calibrate(int ch, int lo, int mid, int hi) { ChannelMin[ch] = lo; ChannelCentre[ch] = mid; ChannelMax[ch] = hi; ChannelMidLow[ch] = lo + (mid - lo) / 2; ChannelMidHi[ch] = mid + (hi - mid) / 2; }   // (Calibrate.h ChannelCentres)
static void mirrorOld(int b, int ch) { MinDegrees[b][ch] = CurvePoint[b][ch][0]; MidLowDegrees[b][ch] = CurvePoint[b][ch][1]; CentreDegrees[b][ch] = CurvePoint[b][ch][2]; MidHiDegrees[b][ch] = CurvePoint[b][ch][3]; MaxDegrees[b][ch] = CurvePoint[b][ch][4]; }
static void randomCurve(int b, int ch, int n) { CurvePointCount[ch] = (uint8_t) n; for (int k = 0; k < CURVE_POINTS_MAX; ++k) CurvePoint[b][ch][k] = k < n ? (uint8_t) (rnd() % 181) : 0; }
static int commands(const std::string &s, const char *starting) { int c = 0; size_t at = 0; while (at < s.size()) { size_t e = s.find("\xFF\xFF\xFF", at); if (e == std::string::npos) e = s.size(); if (s.compare(at, strlen(starting), starting) == 0) ++c; at = e + 3; } return c; }
static bool has(const std::string &s, const std::string &cmd) { return s.find(cmd + "\xFF\xFF\xFF") != std::string::npos; }
int main()
{
    // ---- 1. five points: byte for byte the old maths
#ifndef NO_OLD
    long compared = 0, differ = 0;
    for (int trial = 0; trial < 400; ++trial) {
        const int ch = trial % 16, in = ch % 8;
        MaxRangeNarrow = trial % 2; Bank = 1 + trial % 4;
        calibrate(in, 300 + rnd() % 600, 1800 + rnd() % 500, 3200 + rnd() % 700);
        InPutStick[ch] = (uint8_t) in;
        randomCurve(Bank, ch, 5); mirrorOld(Bank, ch);
        InterpolationTypes[Bank][ch] = trial % 3; Exponential[Bank][ch] = (uint8_t) (rnd() % 201);
        for (int j = 0; j < 8; ++j) DualRateChannels[j] = 0;
        const int rate = (trial / 3) % 4 == 0 ? 100 : 30 + rnd() % 110;
        if (trial % 5 != 4) DualRateChannels[rnd() % 8] = (uint8_t) (ch + 1);   // (sometimes the channel has a rate, sometimes not)
        for (int input = 0; input <= 4095; input += 3) {
            GetCurveDotsOld(ch, rate); PointsCount = 5;
            uint16_t a = 0, b = 0;
            if (InterpolationTypes[Bank][ch] == STRAIGHTLINES) a = StraightLineInterpolationOld(input, in, ch); else if (InterpolationTypes[Bank][ch] == SMOOTHEDCURVES) a = CatmullSplineInterpolationOld(input, in, ch); else a = ExponentialInterpolationOld(input, in, ch);
            GetCurveDots(ch, rate);
            b = Interpolate[InterpolationTypes[Bank][ch]](input, in, ch);
            ++compared; if (a != b) { ++differ; if (differ < 4) fprintf(stderr, "differs: trial %d type %d input %d: old %u new %u\n", trial, InterpolationTypes[Bank][ch], input, a, b); }
        }
    }
    printf("five points: %ld outputs compared with the old maths, %ld different\n", compared, differ);
    CHECK(differ == 0 && compared > 500000);
#endif
    // ---- 2. three, seven and nine points
    Bank = 1; MaxRangeNarrow = 0; for (int j = 0; j < 8; ++j) DualRateChannels[j] = 0;
    for (int n : {3, 7, 9}) for (int trial = 0; trial < 60; ++trial) {
        const int ch = trial % 16, in = ch % 8; InPutStick[ch] = (uint8_t) in;
        calibrate(in, 400 + rnd() % 400, 1900 + rnd() % 300, 3300 + rnd() % 500);
        MaxRangeNarrow = trial % 2;
        randomCurve(1, ch, n);
        // straight: through every point, straight between
        InterpolationTypes[1][ch] = STRAIGHTLINES; GetCurveDots(ch, 100);
        CHECK(CurveDotsN == n);
        bool through = true, between = true;
        for (int k = 0; k < n; ++k) if (StraightLineInterpolation(CurveX(in, k, n), in, ch) != CurveMicros(CurvePoint[1][ch][k])) through = false;
        for (int k = 0; k + 1 < n; ++k) {
            const int x0 = CurveX(in, k, n), x1 = CurveX(in, k + 1, n); const int y0 = CurveMicros(CurvePoint[1][ch][k]), y1 = CurveMicros(CurvePoint[1][ch][k + 1]);
            for (int x = x0; x <= x1; x += 1 + (x1 - x0) / 23) { const int v = StraightLineInterpolation(x, in, ch), want = map(x, x0, x1, y0, y1); if (v != want) between = false; }
        }
        CHECK(through); CHECK(between);
        bool ordered = true; for (int k = 1; k < n; ++k) if (CurveX(in, k, n) <= CurveX(in, k - 1, n)) ordered = false;
        CHECK(ordered && CurveX(in, 0, n) == ChannelMin[in] && CurveX(in, CurveMid(n), n) == ChannelCentre[in] && CurveX(in, n - 1, n) == ChannelMax[in]);
        // smooth: through every point
        InterpolationTypes[1][ch] = SMOOTHEDCURVES; GetCurveDots(ch, 100);
        bool smoothThrough = true; for (int k = 0; k < n; ++k) if (abs((int) CatmullSplineInterpolation(CurveX(in, k, n), in, ch) - (int) CurveMicros(CurvePoint[1][ch][k])) > 1) smoothThrough = false;
        CHECK(smoothThrough);
        // exponential: the ends and the centre, as a five-point curve with the same three
        InterpolationTypes[1][ch] = EXPONENTIALCURVES; Exponential[1][ch] = (uint8_t) (rnd() % 201); GetCurveDots(ch, 100);
        std::vector<uint16_t> e9; for (int x = ChannelMin[in]; x <= ChannelMax[in]; x += 37) e9.push_back(ExponentialInterpolation(x, in, ch));   // (within the stick's travel: beyond it the expo runs negative, and a negative float into a uint16_t is not defined - the old code's behaviour there, untouched)
        const uint8_t lo = CurvePoint[1][ch][0], mid = CurvePoint[1][ch][CurveMid(n)], hi = CurvePoint[1][ch][n - 1];
        CurvePointCount[ch] = 5; CurvePoint[1][ch][0] = lo; CurvePoint[1][ch][2] = mid; CurvePoint[1][ch][4] = hi; GetCurveDots(ch, 100);
        bool sameExpo = true; int i = 0; for (int x = ChannelMin[in]; x <= ChannelMax[in]; x += 37) if (ExponentialInterpolation(x, in, ch) != e9[i++]) sameExpo = false;
        CHECK(sameExpo);
    }
    // ---- 3. changing the count: the new points on the old curve, the ends and the centre kept, 5 -> 9 -> 5 exact, every bank
    MaxRangeNarrow = 0; DualRateValue = 100;
    for (int trial = 0; trial < 120; ++trial) {
        const int ch = trial % 16, in = ch % 8; InPutStick[ch] = (uint8_t) in; ChanneltoSet = ch + 1;
        calibrate(in, 400 + rnd() % 400, 1900 + rnd() % 300, 3300 + rnd() % 500);
        MaxRangeNarrow = trial % 2;
        for (int b = 1; b <= 4; ++b) { randomCurve(b, ch, 5); InterpolationTypes[b][ch] = trial % 2 ? SMOOTHEDCURVES : STRAIGHTLINES; Exponential[b][ch] = 30; }
        uint8_t five[5][CURVE_POINTS_MAX]; memcpy(five, CurvePoint, 0); for (int b = 1; b <= 4; ++b) memcpy(five[b], CurvePoint[b][ch], CURVE_POINTS_MAX);
        // the old curve's values at the new positions, bank by bank, before the change
        uint16_t oldAt[5][CURVE_POINTS_MAX];
        for (int b = 1; b <= 4; ++b) { Bank = b; GetCurveDots(ch, 100); for (int k = 0; k < 9; ++k) oldAt[b][k] = constrain(Interpolate[InterpolationTypes[b][ch]](CurveX(in, k, 9), in, ch), RangeLo(), RangeHi()); }   // (a point cannot leave the range: a smooth curve's overshoot is clipped, as RangeDegrees clips it)
        Bank = 2;
        CurveResample(ch, 9);
        CHECK(CurveN(ch) == 9 && Bank == 2);
        bool onCurve = true, kept = true;
        for (int b = 1; b <= 4; ++b) {
            if (CurvePoint[b][ch][0] != five[b][0] || CurvePoint[b][ch][4] != five[b][2] || CurvePoint[b][ch][8] != five[b][4] || CurvePoint[b][ch][2] != five[b][1] || CurvePoint[b][ch][6] != five[b][3]) kept = false;
            for (int k = 1; k < 9; k += 2) if (abs((int) CurveMicros(CurvePoint[b][ch][k]) - (int) oldAt[b][k]) > 6) onCurve = false;   // (a degree is 6 to 11 us)
        }
        CHECK(kept); CHECK(onCurve);
        CurveResample(ch, 5);
        bool back = true; for (int b = 1; b <= 4; ++b) for (int k = 0; k < 5; ++k) if (CurvePoint[b][ch][k] != five[b][k]) back = false;
        CHECK(back && CurveN(ch) == 5);
        for (int b = 1; b <= 4; ++b) for (int k = 5; k < CURVE_POINTS_MAX; ++k) CHECK(CurvePoint[b][ch][k] == 0);
        // to 7 and 3: the ends and the centre exact, the rest on the old curve
        for (int n : {7, 3}) {
            for (int b = 1; b <= 4; ++b) { Bank = b; GetCurveDots(ch, 100); for (int k = 0; k < n; ++k) oldAt[b][k] = constrain(Interpolate[InterpolationTypes[b][ch]](CurveX(in, k, n), in, ch), RangeLo(), RangeHi()); }
            CurveResample(ch, n); Bank = 1;
            bool ok = true;
            for (int b = 1; b <= 4; ++b) {
                if (CurvePoint[b][ch][0] != five[b][0] || CurvePoint[b][ch][CurveMid(n)] != five[b][2] || CurvePoint[b][ch][n - 1] != five[b][4]) ok = false;
                for (int k = 1; k < n - 1; ++k) if (k != CurveMid(n) && abs((int) CurveMicros(CurvePoint[b][ch][k]) - (int) oldAt[b][k]) > 6) ok = false;
            }
            CHECK(ok);
            CurveResample(ch, 5);
        }
        // the tap: the same count asks nothing of the file; another saves and redraws
        saves = redraws = 0; CurvePointsChosen(5); CHECK(saves == 0 && redraws == 1);
        CurvePointsChosen(7); CHECK(saves == 1 && redraws == 2 && CurveN(ch) == 7);
        CurrentPoint = 9; CurvePointsChosen(3); CHECK(CurveN(ch) == 3 && CurrentPoint == 1);
        CurveResample(ch, 5);
    }
    // ---- 4. the file: the five of old, and the curves' block after the max range's bytes
    uint8_t f[5];
    CurvePointCount[0] = 5; { const uint8_t p[5] = {10, 40, 90, 140, 170}; for (int k = 0; k < 5; ++k) CurvePoint[1][0][k] = p[k]; } CurveLegacyFive(1, 0, f);
    CHECK(f[0] == 10 && f[1] == 40 && f[2] == 90 && f[3] == 140 && f[4] == 170);
    CurvePointCount[0] = 3; { const uint8_t p[3] = {10, 90, 170}; for (int k = 0; k < 3; ++k) CurvePoint[1][0][k] = p[k]; } CurveLegacyFive(1, 0, f);
    CHECK(f[0] == 10 && f[1] == 50 && f[2] == 90 && f[3] == 130 && f[4] == 170);
    CurvePointCount[0] = 7; { const uint8_t p[7] = {0, 20, 40, 90, 140, 160, 180}; for (int k = 0; k < 7; ++k) CurvePoint[1][0][k] = p[k]; } CurveLegacyFive(1, 0, f);
    CHECK(f[0] == 0 && f[1] == 30 && f[2] == 90 && f[3] == 150 && f[4] == 180);
    CurvePointCount[0] = 9; { const uint8_t p[9] = {0, 10, 30, 60, 90, 120, 150, 170, 180}; for (int k = 0; k < 9; ++k) CurvePoint[1][0][k] = p[k]; } CurveLegacyFive(1, 0, f);
    CHECK(f[0] == 0 && f[1] == 30 && f[2] == 90 && f[3] == 150 && f[4] == 180);
    CurvePointCount[0] = 5; CurveSetStraight(1, 0, 30, 150); CHECK(CurvePoint[1][0][0] == 30 && CurvePoint[1][0][1] == 60 && CurvePoint[1][0][2] == 90 && CurvePoint[1][0][3] == 120 && CurvePoint[1][0][4] == 150 && CurvePoint[1][0][5] == 0);
    CurvePointCount[0] = 9; CurveSetStraight(1, 0, 0, 180); CHECK(CurvePoint[1][0][1] == 23 && CurvePoint[1][0][4] == 90 && CurvePoint[1][0][8] == 180);
    CurvePointCount[0] = 0; CHECK(CurveN(0) == 5); CurvePointCount[0] = 6; CHECK(CurveN(0) == 5); CurvePointCount[0] = 9; CHECK(CurveN(0) == 9);
    auto record = [&](size_t len) { card.assign(len, 0); StartLocation = 0; SDCardAddress = (int) len; FileCheckSum = 0; seekWriteFails = 0; };
    auto legacyLoad = [&]() { for (int c = 0; c < CHANNELSUSED; ++c) { CurvePointCount[c] = 5; for (int b = 1; b <= 4; ++b) { CurveLegacyFive(b, c, f); for (int k = 0; k < 5; ++k) CurvePoint[b][c][k] = f[k]; for (int k = 5; k < 9; ++k) CurvePoint[b][c][k] = 0; } } };   // (ReadOneModel's five of old)
    for (int c = 0; c < CHANNELSUSED; ++c) for (int b = 1; b <= 4; ++b) randomCurve(b, c, 5);
    // (a) every channel five: in a .MOD nothing follows the checksum; in models.dat the max range's bytes only
    record(2016); MaxRangeNarrow = 0; SaveModelExtension(); CHECK(card.size() == 2016 && seekWriteFails == 0 && FileCheckSum == 0);
    record(512 + 5 * 3072); StartLocation = 512 + 3072; SDCardAddress = StartLocation + 2016; SaveModelExtension();
    CHECK(card[SDCardAddress] == 0x5A && card[SDCardAddress + 1] == 0xC3 && card[SDCardAddress + 2] == 0 && card[SDCardAddress + 3] == 0 && seekWriteFails == 0);
    // (b) a channel with seven points: the block, in a .MOD (an append) and read back whole
    for (int b = 1; b <= 4; ++b) randomCurve(b, 5, 7);
    for (int b = 1; b <= 4; ++b) randomCurve(b, 11, 9);
    uint8_t keep[5][CHANNELSUSED + 1][CURVE_POINTS_MAX]; memcpy(keep, CurvePoint, sizeof(keep)); uint8_t keepN[CHANNELSUSED + 1]; memcpy(keepN, CurvePointCount, sizeof(keepN));
    record(2016); MaxRangeNarrow = 1; SaveModelExtension();
    CHECK(card.size() == 2016 + 3 + MODEL_EXT2_LEN && seekWriteFails == 0 && FileCheckSum == 0 && card[2019] == 0x5A && card[2020] == 0xC5);
    legacyLoad(); CHECK(CurveN(5) == 5 && CurveN(11) == 5);
    MaxRangeNarrow = 0; ReadModelExtension();
    CHECK(MaxRangeNarrow == 1 && memcmp(keep, CurvePoint, sizeof(keep)) == 0 && memcmp(keepN, CurvePointCount, sizeof(keepN)) == 0 && FileCheckSum == 0);
    // (c) a byte of it wrong: the five of old stand (the sampling), nothing else
    card[2019 + 2 + CHANNELSUSED + 7] ^= 0x10; legacyLoad(); uint8_t sampled[5][CHANNELSUSED + 1][CURVE_POINTS_MAX]; memcpy(sampled, CurvePoint, sizeof(sampled));
    ReadModelExtension(); CHECK(CurveN(5) == 5 && CurveN(11) == 5 && memcmp(sampled, CurvePoint, sizeof(sampled)) == 0 && MaxRangeNarrow == 1);
    card[2019 + 2 + CHANNELSUSED + 7] ^= 0x10; ReadModelExtension(); CHECK(memcmp(keep, CurvePoint, sizeof(keep)) == 0);
    card[2019 + 2 + 5] = 6; legacyLoad(); ReadModelExtension(); CHECK(CurveN(5) == 5);   // (a count that is not 3 5 7 9: the block is not ours; ReadOneModel's five of old first, as legacyLoad does)
    card[2019 + 2 + 5] = 7; card[2019 + MODEL_EXT2_LEN - 1] ^= 1; legacyLoad(); ReadModelExtension(); CHECK(CurveN(5) == 5); card[2019 + MODEL_EXT2_LEN - 1] ^= 1;
    memcpy(CurvePoint, keep, sizeof(keep)); memcpy(CurvePointCount, keepN, sizeof(keepN)); ReadModelExtension(); CHECK(CurveN(5) == 7 && CurveN(11) == 9);
    // (d) a .MOD too short for the block (an old one): nothing read; a record from before B113: nothing
    record(2016); card.resize(2019); card[2016] = 0x5A; card[2017] = 0xC3; card[2018] = 1; legacyLoad(); MaxRangeNarrow = 0; ReadModelExtension(); CHECK(MaxRangeNarrow == 1 && CurveN(5) == 5);
    record(2016); MaxRangeNarrow = 1; ReadModelExtension(); CHECK(MaxRangeNarrow == 0 && CurveN(5) == 5);
    // (e) back to five on every channel with the block there: it is rewritten (never a stale count), in models.dat too
    memcpy(CurvePoint, keep, sizeof(keep)); memcpy(CurvePointCount, keepN, sizeof(keepN));
    record(512 + 5 * 3072); StartLocation = 512 + 3 * 3072; SDCardAddress = StartLocation + 2016; MaxRangeNarrow = 0; SaveModelExtension();
    CHECK(card[SDCardAddress + 3] == 0x5A && card[SDCardAddress + 4] == 0xC5 && seekWriteFails == 0 && card.size() == 512 + 5 * 3072);
    CHECK(SDCardAddress + 3 + MODEL_EXT2_LEN <= StartLocation + 3072);   // (inside the slot)
    for (int c = 0; c < CHANNELSUSED; ++c) { CurvePointCount[c] = 5; for (int b = 1; b <= 4; ++b) randomCurve(b, c, 5); }
    SaveModelExtension(); legacyLoad(); CurvePointCount[5] = 7; ReadModelExtension(); CHECK(CurveN(5) == 5 && CurveN(11) == 5);
    // ---- 5. the curve page: the boxes and the radios for each count and shape
    ChanneltoSet = 1; Bank = 1; MaxRangeNarrow = 0;
    struct Want { int n, type, boxes; const char *first, *last; } wants[] = { {3, STRAIGHTLINES, 3, "n1", "n5"}, {5, STRAIGHTLINES, 5, "n1", "n5"}, {5, EXPONENTIALCURVES, 3, "n1", "n5"}, {7, SMOOTHEDCURVES, 7, "n1", "n5"}, {7, EXPONENTIALCURVES, 3, "n1", "n5"}, {9, STRAIGHTLINES, 9, "m1", "m9"}, {9, EXPONENTIALCURVES, 3, "n1", "n5"} };
    for (const Want &w : wants) {
        CurvePointCount[0] = (uint8_t) w.n; CurveSetStraight(1, 0, 20, 160); InterpolationTypes[1][0] = (uint8_t) w.type;
        stream.clear(); CurveLayoutShow();
        CHECK(commands(stream, "vis ") == 18 && commands(stream, "pt") == 4);
        int shown = 0; for (const char *nm : {"n1", "n2", "n3", "n4", "n5", "k2", "k3", "k5", "k6", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9"}) if (has(stream, std::string("vis ") + nm + ",1")) ++shown;
        CHECK(shown == w.boxes);
        char c[40]; snprintf(c, sizeof(c), "%s.val=%d", w.first, CurveMicros(20)); CHECK(has(stream, c));
        snprintf(c, sizeof(c), "%s.val=%d", w.last, CurveMicros(160)); CHECK(has(stream, c));
        snprintf(c, sizeof(c), "pt%d.val=1", w.n); CHECK(has(stream, c));
        if (w.type == EXPONENTIALCURVES) { snprintf(c, sizeof(c), "n3.val=%d", CurveMicros(CurvePoint[1][0][CurveMid(w.n)])); CHECK(has(stream, c) && has(stream, "vis n2,0") && has(stream, "vis n4,0")); }
        if (w.n == 7 && w.type != EXPONENTIALCURVES) { snprintf(c, sizeof(c), "k2.val=%d", CurveMicros(CurvePoint[1][0][1])); CHECK(has(stream, c) && has(stream, "vis n2,0") && has(stream, "vis k6,1")); }
        if (w.n == 9 && w.type != EXPONENTIALCURVES) { snprintf(c, sizeof(c), "m5.val=%d", CurveMicros(CurvePoint[1][0][4])); CHECK(has(stream, c) && has(stream, "vis n1,0")); }
    }
    // the dots shown and the point stepping, for each count and shape
    for (int n : {3, 5, 7, 9}) {
        CurvePointCount[0] = (uint8_t) n;
        InterpolationTypes[1][0] = STRAIGHTLINES; int shown = 0; for (int k = 0; k < 9; ++k) if (CurveDotShown((uint8_t) k)) ++shown; CHECK(shown == n);
        InterpolationTypes[1][0] = EXPONENTIALCURVES; shown = 0; for (int k = 0; k < 9; ++k) if (CurveDotShown((uint8_t) k)) ++shown; CHECK(shown == 3 && CurveDotShown(0) && CurveDotShown(CurveMid(n)) && CurveDotShown(n - 1));
        CurrentPoint = 2; CheckInvisiblePoint(); CHECK(CurrentPoint == (n == 3 ? 2 : CurveMid(n) + 1));
        CurrentPoint = n; CheckInvisiblePoint(); CHECK(CurrentPoint == n);
        CurrentPoint = 12; CheckInvisiblePoint(); CHECK(CurrentPoint == 1);
    }
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = (PROGRAM.replace('@DEFS@', DEFS).replace('@MAP@', TEENSY_MAP).replace('@INLINES@', INLINES)
        .replace('@CURVEN@', lift('include/Utilities.h', 'uint8_t CurveN(uint8_t ch)'))
        .replace('@CURVEX@', lift('include/Utilities.h', 'uint16_t CurveX(uint8_t in, uint8_t k, uint8_t n)'))
        .replace('@LEGACY@', lift('include/Utilities.h', 'void CurveLegacyFive(uint8_t b, uint8_t ch, uint8_t *five)'))
        .replace('@STRAIGHT@', lift('include/Utilities.h', 'void CurveSetStraight(uint8_t b, uint8_t ch, uint8_t lo, uint8_t hi)'))
        .replace('@MAPWITHEXPO@', lift('include/Utilities.h', 'FASTRUN float MapWithExponential('))
        .replace('@NEWINTERP@', lift('src/main.cpp', 'uint16_t CatmullSplineInterpolation(') + lift('src/main.cpp', 'uint16_t StraightLineInterpolation(') + lift('src/main.cpp', 'uint16_t ExponentialInterpolation('))
        .replace('@NEWRATES@', lift('include/DualRates.h', 'float CalculateRate(') + lift('include/DualRates.h', 'float UseFullRate(') + lift('include/DualRates.h', 'void GetCurveDots('))
        .replace('@RANGEDEG@', lift('src/main.cpp', 'FLASHMEM static uint8_t RangeDegrees('))
        .replace('@RESAMPLE@', lift('src/main.cpp', 'FLASHMEM static void CurveResample('))
        .replace('@DOTSHOWN@', lift('src/main.cpp', 'bool CurveDotShown(uint8_t k)'))
        .replace('@INVISIBLE@', lift('src/main.cpp', 'void CheckInvisiblePoint()'))
        .replace('@CHOSEN@', lift('src/main.cpp', 'FLASHMEM void CurvePointsChosen(uint8_t n)'))
        .replace('@OLD@', OLD if HAVE_OLD else '#define NO_OLD 1\n')
        .replace('@GRAPHCMD@', lift('src/main.cpp', 'FLASHMEM static void GraphCmd('))
        .replace('@LAYOUT@', lift('src/main.cpp', 'FLASHMEM void CurveLayoutShow()'))
        .replace('@EXT@', lift('include/SDcard.h', 'static uint8_t Ext2Sum(') + lift('include/SDcard.h', 'void ReadModelExtension()') + lift('include/SDcard.h', 'void SaveModelExtension()')))
LIB = os.path.join(TC, '.pio', 'libdeps', 'teensy41', 'InterpolationLib', 'src')
if not os.path.isdir(LIB): sys.exit('InterpolationLib not found at ' + LIB + ' (build the Teensy once)')
with tempfile.TemporaryDirectory() as d:
    stub = os.path.join(d, 'stub'); os.makedirs(stub)
    for n in ('Arduino.h', 'WProgram.h'): open(os.path.join(stub, n), 'w').write('#pragma once\n#include <cstdint>\n#include <cmath>\n#include <cstdlib>\n')
    cpp = os.path.join(d, 't.cpp'); exe = os.path.join(d, 't')
    open(cpp, 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-Wall', '-Wno-unused-variable', '-Wno-unused-but-set-variable', '-Wno-unused-function', '-I', LIB, '-I', stub, '-o', exe, cpp, os.path.join(LIB, 'InterpolationLib.cpp')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode:
        print(r.stdout[-6000:]); sys.exit('the curve points code does not compile on the host')
    r = subprocess.run([exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout.strip())
    check(r.returncode == 0, 'the curve points on the host')
# ---- as source
sd = src('include/SDcard.h'); fg = src('include/FlightGuard.h'); mx = src('include/Mixes.h'); cal = src('include/Calibrate.h'); dr = src('include/DualRates.h')
check('CurvePoint[j][i][4] = SDRead8BITS(SDCardAddress);' in sd and 'CurvePoint[j][i][0] = SDRead8BITS(SDCardAddress);' in sd, 'a model read: the five of old into points 4 .. 0, then its extension')
check('CurveLegacyFive(j, i, five);' in sd and 'SDUpdate8BITS(SDCardAddress, five[4]);' in sd and 'SDUpdate8BITS(SDCardAddress, five[0]);' in sd, 'a model saved: the five of old as a sampling, for any firmware')
check("CurvePointCount[c] = 5; // B118" in sd, "a model read: five points until its own extension says otherwise")
check('CurveLegacyFive(j, i, five);' in fg and 'Fp(0x5EC5);' in fg and 'if (CurveN(i) != 5)' in fg, "the fingerprint: the five of old as ever, the other counts folded in only when in use")
check('CurveMicros(CurvePoint[Bank][Slave][0])' in mx and 'CurveMicros(CurvePoint[Bank][Slave][CurveN(Slave) - 1])' in mx, "a mix stops at the slave's curve ends")
check('CurveSetStraight(Bank, i, 0, 180);' in cal, 'the calibration runs on a straight 0 .. 180 curve')
check('const uint8_t n = CurveN(OutputChannel);' in dr and 'CurveDotsN = n;' in dr, 'the rates scale every point of the curve')
for name in ('MinDegrees[', 'MidLowDegrees[', 'CentreDegrees[', 'MidHiDegrees[', 'MaxDegrees[', 'PointsCount'):
    check(name not in main and all(name not in src(h) for h in ('include/1Definitions.h', 'include/Utilities.h', 'include/SDcard.h', 'include/FlightGuard.h', 'include/Mixes.h', 'include/Calibrate.h', 'include/DualRates.h', 'include/RF_Adjust.h')), 'the five of old are gone from the code: %s' % name)
mp = lift('src/main.cpp', 'void MovePoint()')
check('if (!CurveDotShown(k))' in mp and 'const int d = abs(XtouchPlace - (int)xPoints[k]);' in mp and 'uint8_t &deg = CurvePoint[Bank][ch][best];' in mp, 'a touch moves the nearest point shown')
wnc = lift('src/main.cpp', 'void WriteNewCurve()')
check('for (uint8_t k = 0; k < CURVE_POINTS_MAX; ++k)' in wnc and 'CurvePoint[p][ChanneltoSet - 1][k] = CurvePoint[Bank][ChanneltoSet - 1][k];' in wnc, 'Copy to all banks copies every point')
uit = lift('src/main.cpp', 'FASTRUN void updateInterpolationTypes()')
check('{"lpt", "pt3", "lpt3", "pt5", "lpt5", "pt7", "lpt7", "pt9", "lpt9"}' in uit and 'InterpolationTypes[Bank][ChanneltoSet - 1] != EXPONENTIALCURVES' in uit, 'the Points row shows with Straight and Smooth')
check(int(re.search(r'#define TXVERSION_EXTRA "B(\d+)', defs).group(1)) >= 118, 'B118 or later')
print('%d source checks, %d failed' % (checks, fails))
sys.exit(1 if fails else 0)
