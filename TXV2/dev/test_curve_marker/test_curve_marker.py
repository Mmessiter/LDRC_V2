#!/usr/bin/env python3
"""Host test of B117: the curve page's stick marker moves without redrawing the curve.
Malcolm, 17 Oct 2026: "as I move the stick the line moves in occasional jumps". Every move used to be a full redraw
(1.5 kB of commands and a flash of black); now GraphMarkerMove paints the old marker's column black, puts back what lay
there (the reference lines' pixels, the curve's segments through it, the dots they pass through) and draws the marker at
its new place. Two things are proved here, on the Mac, with the real functions lifted out of main.cpp:
  1. DisplayCurve sends exactly the byte stream it sent before (the old DisplayCurve from git HEAD, compiled beside it):
     the curve's segments now come from CurveSegments, shared with the marker mover.
  2. Moving the marker leaves the picture pixel for pixel as a fresh full draw with the marker there would, on a software
     screen that paints the commands (fill, draw, line, cirs) - over every kind of curve, at the edges, through the
     reference lines and the dots, in single pixels and in jumps.
   python3 dev/test_curve_marker/test_curve_marker.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.environ.get('TXV1B_TC', os.path.join(ROOT, 'TransmitterCode'))
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
main = src('src/main.cpp'); defs = src('include/1Definitions.h')
# the DisplayCurve before B117 (commit b53b522, B116): compiled beside the new one, it must send the same bytes
OLD_COMMIT = 'b53b522'
r = subprocess.run(['git', 'show', OLD_COMMIT + ':TransmitterCode/src/main.cpp'], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
old_main = r.stdout if r.returncode == 0 else ''
HAVE_OLD = 'adaptiveStep = 12;' in old_main and 'FASTRUN void DisplayCurve()' in old_main
if HAVE_OLD:
    old_dc = lift_from(old_main, 'FASTRUN void DisplayCurve()', OLD_COMMIT).replace('FASTRUN void DisplayCurve()', 'FASTRUN void DisplayCurveOld()', 1)
else:
    print('NOTE: commit %s is not in this repository: the byte-for-byte comparison with the old DisplayCurve is skipped' % OLD_COMMIT)
    old_dc = 'static void DisplayCurveOld() { DisplayCurve(); }\n#define NO_OLD_DISPLAYCURVE 1\n'
DEFS = '\n'.join(l for l in defs.split('\n') if re.match(r'#define (BOXLEFT|BOXTOP|BOXWIDTH|BOXHEIGHT|BOXBOTTOM|BOXRIGHT|GRAPH_MARKER_FIRST|GRAPH_MARKER_LAST|GRAPH_MARKER_TOP|GRAPH_MARKER_BOTTOM|NO_MARKER|CURVE_SEGMENTS_MAX|CURVE_POINTS_MAX|STRAIGHTLINES|SMOOTHEDCURVES|EXPONENTIALCURVES|White|Black)\b', l)) + '\n'
assert DEFS.count('#define') == 18, DEFS
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
// the screen's wire: everything DisplayCurve and the marker send, in order
static std::string stream;
struct FakeSerial { void print(const char *s) { stream += s; } } NEXTION;
static void SendCommand(char *c) { stream += c; stream += "\xFF\xFF\xFF"; }
static void SendOtherValue(char *, int) {}
static void DelayWithDog(int) {}
static void ClearText() {}
static void updateInterpolationTypes() {}
uint8_t InterpolationTypes[5][17], Exponential[5][17];
uint8_t MinDegrees[5][17], MidLowDegrees[5][17], CentreDegrees[5][17], MidHiDegrees[5][17], MaxDegrees[5][17];   // (the five of old, for the old DisplayCurve)
uint8_t CurvePointCount[17], CurvePoint[5][17][CURVE_POINTS_MAX];                                                   // (B118)
uint8_t CurveDotsN = 5;
int Bank = 1, ChanneltoSet = 1;
uint8_t CurrentPoint = 1;
double PointsCount = 5;
double xPoints[CURVE_POINTS_MAX], yPoints[CURVE_POINTS_MAX];
bool CurveDotShown(uint8_t k);
void CurveLayoutShow();
@CURVEN@
uint8_t CurveMid(uint8_t n) { return (n - 1) / 2; }
@DOTSHOWN@
uint16_t ForeGroundColour = 65535, HighlightColour = 65504, SpecialColour = 63488;
uint16_t SavedLineX = 12345;
static uint16_t CurveMicros(uint8_t deg) { return map(deg, 0, 180, 500, 2500); }
uint8_t CurveSegments(int16_t *x1, int16_t *y1, int16_t *x2, int16_t *y2);
FASTRUN void DisplayCurve();
@MAPWITHEXPO@
@CHECKINVISIBLE@
@GETDOTS@
@OLD@
@SEGMENTS@
@NEWDC@
@GRAPHCMD@
@MOVER@
@LAYOUT@
// a software screen that paints the commands as the glass does (deterministic, inclusive ends)
static const int W = 480, H = 480;
static uint16_t fb[H][W];
static void px(int x, int y, uint16_t c) { if (x >= 0 && x < W && y >= 0 && y < H) fb[y][x] = c; }
static void paintLine(int x1, int y1, int x2, int y2, uint16_t c)
{
    int dx = abs(x2 - x1), sx = x1 < x2 ? 1 : -1, dy = -abs(y2 - y1), sy = y1 < y2 ? 1 : -1, err = dx + dy;
    for (;;) { px(x1, y1, c); if (x1 == x2 && y1 == y2) break; const int e2 = 2 * err; if (e2 >= dy) { err += dy; x1 += sx; } if (e2 <= dx) { err += dx; y1 += sy; } }
}
static int painted = 0;
static void paint(const std::string &s)
{
    size_t at = 0;
    while (at < s.size()) {
        size_t end = s.find("\xFF\xFF\xFF", at); if (end == std::string::npos) end = s.size();
        std::string cmd = s.substr(at, end - at); at = end + 3;
        char verb[16] = {0}; int a[6] = {0};
        const int n = sscanf(cmd.c_str(), "%15s %d,%d,%d,%d,%d", verb, &a[0], &a[1], &a[2], &a[3], &a[4]) - 1;
        if (!strcmp(verb, "fill") && n >= 5) { for (int y = a[1]; y < a[1] + a[3]; ++y) for (int x = a[0]; x < a[0] + a[2]; ++x) px(x, y, (uint16_t) a[4]); ++painted; }
        else if (!strcmp(verb, "draw") && n >= 5) { paintLine(a[0], a[1], a[2], a[1], a[4]); paintLine(a[0], a[3], a[2], a[3], a[4]); paintLine(a[0], a[1], a[0], a[3], a[4]); paintLine(a[2], a[1], a[2], a[3], a[4]); ++painted; }
        else if (!strcmp(verb, "line") && n >= 5) { paintLine(a[0], a[1], a[2], a[3], (uint16_t) a[4]); ++painted; }
        else if (!strcmp(verb, "cirs") && n >= 4) { for (int dy = -a[2]; dy <= a[2]; ++dy) { const int dx = (int) floor(sqrt((double) (a[2] * a[2] - dy * dy))); for (int x = a[0] - dx; x <= a[0] + dx; ++x) px(x, a[1] + dy, (uint16_t) a[3]); } ++painted; }
    }
}
static int commandsIn(const std::string &s) { int n = 0; size_t at = 0; while ((at = s.find("\xFF\xFF\xFF", at)) != std::string::npos) { ++n; at += 3; } return n; }
static void setCurve(int type, const int *deg, int expo, int point)
{ // five points, in both the old arrays (for the old DisplayCurve) and the new (B118)
    InterpolationTypes[1][0] = (uint8_t) type; Exponential[1][0] = (uint8_t) expo; CurrentPoint = (uint8_t) point;
    MinDegrees[1][0] = deg[0]; MidLowDegrees[1][0] = deg[1]; CentreDegrees[1][0] = deg[2]; MidHiDegrees[1][0] = deg[3]; MaxDegrees[1][0] = deg[4];
    CurvePointCount[0] = 5; for (int k = 0; k < 5; ++k) CurvePoint[1][0][k] = (uint8_t) deg[k];
}
static void setCurveN(int type, int n, const int *deg5, int expo, int point)
{ // n points (3, 5, 7 or 9) along the five-point set's shape, with a wiggle on the in-between ones
    InterpolationTypes[1][0] = (uint8_t) type; Exponential[1][0] = (uint8_t) expo; CurrentPoint = (uint8_t) point;
    CurvePointCount[0] = (uint8_t) n;
    for (int k = 0; k < n; ++k) {
        const double f = (double) k / (n - 1) * 4; const int i = (int) f; const double r = f - i;
        int d = i >= 4 ? deg5[4] : (int) (deg5[i] + (deg5[i + 1] - deg5[i]) * r + 0.5);
        if (k != 0 && k != n - 1 && k != (n - 1) / 2) d += (k % 2 ? 7 : -9);
        CurvePoint[1][0][k] = (uint8_t) (d < 0 ? 0 : d > 180 ? 180 : d);
    }
}
static std::string drawing(const std::string &s)
{ // only what paints: fill, draw, line, cirs (the numbers and the boxes' vis differ since B118, by design)
    std::string out; size_t at = 0;
    while (at < s.size()) {
        size_t end = s.find("\xFF\xFF\xFF", at); if (end == std::string::npos) end = s.size();
        const std::string cmd = s.substr(at, end - at); at = end + 3;
        if (cmd.rfind("fill ", 0) == 0 || cmd.rfind("draw ", 0) == 0 || cmd.rfind("line ", 0) == 0 || cmd.rfind("cirs ", 0) == 0) out += cmd + "\xFF\xFF\xFF";
    }
    return out;
}
static std::string withoutCurveLines(const std::string &s)
{ // the drawing less the curve's own lines (ForeGroundColour)
    std::string out; size_t at = 0; char want[24]; snprintf(want, sizeof(want), ",%u", (unsigned) ForeGroundColour);
    while (at < s.size()) {
        size_t end = s.find("\xFF\xFF\xFF", at); if (end == std::string::npos) end = s.size();
        const std::string cmd = s.substr(at, end - at); at = end + 3;
        if (cmd.rfind("line ", 0) == 0 && cmd.size() > strlen(want) && cmd.compare(cmd.size() - strlen(want), strlen(want), want) == 0) continue;
        out += cmd + "\xFF\xFF\xFF";
    }
    return out;
}
static bool throughEveryPoint(const std::string &s, int npts)
{ // (B122) every point of the curve is an end of one of its lines, and no line spans more than 12 pixels across
    GetDotPositions();
    bool ok = true;
    for (int k = 0; k < npts; ++k) {
        char a[40], b[40]; snprintf(a, sizeof(a), "line %d,%d,", (int) xPoints[k], (int) yPoints[k]); snprintf(b, sizeof(b), ",%d,%d,%u\xFF", (int) xPoints[k], (int) yPoints[k], (unsigned) ForeGroundColour);
        if (s.find(a) == std::string::npos && s.find(b) == std::string::npos) ok = false;
    }
    size_t at = 0;
    while ((at = s.find("line ", at)) != std::string::npos) { int x1, y1, x2, y2; unsigned c; if (sscanf(s.c_str() + at, "line %d,%d,%d,%d,%u", &x1, &y1, &x2, &y2, &c) == 5 && c == ForeGroundColour && abs(x2 - x1) > 12) ok = false; at += 5; }
    return ok;
}
static uint16_t fresh[H][W];
static void fullWithMarker(int x)
{ // a fresh full draw with the marker at x, into fresh[][]
    memset(fb, 0x55, sizeof(fb)); stream.clear(); DisplayCurve(); GraphMarkerMove(NO_MARKER, (uint16_t) x); paint(stream); memcpy(fresh, fb, sizeof(fb));
}
int main()
{
    static const int SETS[][5] = {{30, 60, 90, 120, 150}, {0, 45, 90, 135, 180}, {180, 135, 90, 45, 0}, {90, 90, 90, 90, 90}, {10, 100, 20, 170, 60}, {0, 0, 0, 0, 0}, {180, 180, 180, 180, 180}, {60, 75, 95, 110, 140}};
    static const int EXPOS[] = {0, 30, 50, 80, 100, 150, 200};
    // 1. the new DisplayCurve sends the very bytes the old one sent
    int same = 0, differ = 0; size_t fullBytes = 0;
    for (int type = 0; type < 3; ++type) for (int s = 0; s < 8; ++s) for (int e = 0; e < 7; ++e) for (int point = 1; point <= 5; ++point) {
        if (type != EXPONENTIALCURVES && e > 1) continue;   // the expo only shapes an exponential curve
        setCurve(type, SETS[s], EXPOS[e], point); const uint8_t cp = CurrentPoint;
        stream.clear(); DisplayCurveOld(); std::string before = drawing(stream); const uint8_t cpOld = CurrentPoint;
        CurrentPoint = cp; stream.clear(); DisplayCurve(); std::string now = drawing(stream);
        if (type == SMOOTHEDCURVES) {   // (B122) the smooth curve's own lines are sampled differently now - through every point; the rest must still match
            CHECK(throughEveryPoint(now, 5)); before = withoutCurveLines(before); now = withoutCurveLines(now);
        }
        if (before == now && cpOld == CurrentPoint) ++same; else { ++differ; if (differ < 3) fprintf(stderr, "differs: type %d set %d expo %d point %d\n", type, s, EXPOS[e], point); }
        if (now.size() > fullBytes) fullBytes = now.size();
    }
#ifdef NO_OLD_DISPLAYCURVE
    printf("full redraws: the largest %zu bytes (no old DisplayCurve to compare with)\n", fullBytes);
#else
    printf("full redraws compared: %d the same, %d different; the largest %zu bytes\n", same, differ, fullBytes);
    CHECK(differ == 0 && same > 300);
#endif
    // 2. moving the marker: the picture is what a fresh full draw with the marker there would be
    static const int PATH[] = {37, 38, 40, 44, 125, 129, 121, 215, 216, 214, 215, 305, 301, 309, 394, 393, 394, 100, 37, 394, 215, 50, 51, 52, 53, 300, 299, 115, 135, 205, 225, 295, 315, 38, 37, 213, 217, 123, 127, 303, 307, 390, 60};
    const int pathLen = sizeof(PATH) / sizeof(PATH[0]);
    long badPixels = 0, moves = 0; size_t moveBytes = 0; int moveCmds = 0;
    unsigned seed = 12345;
    static const int COUNTS[4] = {5, 3, 7, 9};
    for (int ci = 0; ci < 4; ++ci) for (int type = 0; type < 3; ++type) for (int s = 0; s < 8; ++s) for (int e = 0; e < 7; e += 3) for (int point = 1; point <= COUNTS[ci]; point += 2) {
        if (type != EXPONENTIALCURVES && e > 0) continue;
        if (ci > 0 && (s % 2 || e > 0)) continue;   // (the other counts on half the sets: enough, and quick)
        const int npts = COUNTS[ci];
        if (npts == 5) setCurve(type, SETS[s], EXPOS[e], point); else setCurveN(type, npts, SETS[s], EXPOS[e], point);
        if (type == EXPONENTIALCURVES && !(point == 1 || point == npts || point == (npts + 1) / 2)) continue;
        memset(fb, 0x55, sizeof(fb)); stream.clear(); DisplayCurve(); paint(stream);   // the page as drawn, no marker yet
        CHECK(SavedLineX == NO_MARKER);
        uint16_t at = NO_MARKER;
        for (int k = 0; k < pathLen + 40; ++k) {
            int x; if (k < pathLen) x = PATH[k]; else { seed = seed * 1103515245u + 12345u; x = GRAPH_MARKER_FIRST + (int) ((seed >> 8) % (GRAPH_MARKER_LAST - GRAPH_MARKER_FIRST + 1)); }
            for (int k = 0; k < CURVE_POINTS_MAX; ++k) { xPoints[k] = 300 + 400 * k; yPoints[k] = 500 + 200 * k; }   // (B120) the flying maths used to leave stick readings here between moves
            stream.clear(); GraphMarkerMove(at, (uint16_t) x); paint(stream); ++moves;
            if (stream.size() > moveBytes) moveBytes = stream.size();
            if (commandsIn(stream) > moveCmds) moveCmds = commandsIn(stream);
            if (at == NO_MARKER) CHECK(commandsIn(stream) == 1);   // the first marker: one line, nothing to put back
            at = (uint16_t) x;
            uint16_t keep[H][W]; memcpy(keep, fb, sizeof(fb));
            CurrentPoint = (uint8_t) point; fullWithMarker(x);   // (the same curve: a fresh full draw with the marker there)
            memcpy(fb, keep, sizeof(fb));
            for (int y = 0; y < H; ++y) for (int xx = 0; xx < W; ++xx) if (fb[y][xx] != fresh[y][xx]) ++badPixels;
            if (badPixels && moves < 3) { fprintf(stderr, "pixels differ after a move to %d (type %d set %d expo %d point %d)\n", x, type, s, EXPOS[e], point); }
        }
    }
    printf("marker moves: %ld, pixels wrong: %ld; the biggest move %zu bytes in %d commands (3, 5, 7 and 9 points)\n", moves, badPixels, moveBytes, moveCmds);
    CHECK(badPixels == 0 && moves > 1000);
    CHECK(moveBytes < 520 && moveCmds <= 16);
    CHECK(moveBytes * 3 < fullBytes);   // a move is a fraction of a full redraw
    // 2a. (B122) a smooth curve of any count runs through every one of its points
    for (int ci = 0; ci < 4; ++ci) for (int s = 0; s < 8; ++s) {
        if (COUNTS[ci] == 5) setCurve(SMOOTHEDCURVES, SETS[s], 30, 1); else setCurveN(SMOOTHEDCURVES, COUNTS[ci], SETS[s], 30, 1);
        stream.clear(); DisplayCurve(); CHECK(throughEveryPoint(drawing(stream), COUNTS[ci]));
    }
    // 2b. (B119) the vertical reference line stands at the box's centre whatever the count (it stood at the third point)
    for (int ci = 0; ci < 4; ++ci) for (int type = 0; type < 3; ++type) {
        if (COUNTS[ci] == 5) setCurve(type, SETS[1], 30, 1); else setCurveN(type, COUNTS[ci], SETS[1], 30, 1);
        stream.clear(); DisplayCurve();
        char want[48]; snprintf(want, sizeof(want), "line 215,35,215,395,%u", (unsigned) SpecialColour);
        CHECK(stream.find(std::string(want) + "\xFF\xFF\xFF") != std::string::npos);
        int refLines = 0; size_t at = 0; while ((at = stream.find("line ", at)) != std::string::npos) { int x1, y1, x2, y2; unsigned c; if (sscanf(stream.c_str() + at, "line %d,%d,%d,%d,%u", &x1, &y1, &x2, &y2, &c) == 5 && c == SpecialColour && x1 == x2) ++refLines; at += 5; }
        CHECK(refLines == 1);   // (one upright reference line, and only at the centre)
    }
    // 3. no marker to put back, nowhere to draw one: nothing sent
    stream.clear(); GraphMarkerMove(NO_MARKER, NO_MARKER); CHECK(stream.empty());
    stream.clear(); GraphMarkerMove(12345, 12345); CHECK(stream.empty());
    stream.clear(); GraphMarkerMove(36, 36); CHECK(stream.empty());   // (outside the marker's columns, as 395 is)
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = (PROGRAM.replace('@DEFS@', DEFS).replace('@MAP@', TEENSY_MAP)
        .replace('@MAPWITHEXPO@', lift('include/Utilities.h', 'FASTRUN float MapWithExponential('))
        .replace('@CURVEN@', lift('include/Utilities.h', 'uint8_t CurveN(uint8_t ch)'))
        .replace('@DOTSHOWN@', lift('src/main.cpp', 'bool CurveDotShown(uint8_t k)'))
        .replace('@LAYOUT@', lift('src/main.cpp', 'FLASHMEM void CurveLayoutShow()'))
        .replace('@CHECKINVISIBLE@', lift('src/main.cpp', 'void CheckInvisiblePoint()'))
        .replace('@GETDOTS@', lift('src/main.cpp', 'FASTRUN void GetDotPositions()'))
        .replace('@OLD@', old_dc)
        .replace('@SEGMENTS@', lift('src/main.cpp', 'FLASHMEM uint8_t CurveSegments('))
        .replace('@NEWDC@', lift('src/main.cpp', 'FASTRUN void DisplayCurve()'))
        .replace('@GRAPHCMD@', lift('src/main.cpp', 'FLASHMEM static void GraphCmd('))
        .replace('@MOVER@', lift('src/main.cpp', 'FLASHMEM void GraphMarkerMove(')))
LIB = os.path.join(TC, '.pio', 'libdeps', 'teensy41', 'InterpolationLib', 'src')
if not os.path.isdir(LIB): sys.exit('InterpolationLib not found at ' + LIB + ' (build the Teensy once)')
with tempfile.TemporaryDirectory() as d:
    stub = os.path.join(d, 'stub'); os.makedirs(stub)
    for n in ('Arduino.h', 'WProgram.h'): open(os.path.join(stub, n), 'w').write('#pragma once\n#include <cstdint>\n#include <cmath>\n#include <cstdlib>\n')
    cpp = os.path.join(d, 't.cpp'); exe = os.path.join(d, 't')
    open(cpp, 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-Wall', '-Wno-unused-variable', '-Wno-unused-but-set-variable', '-I', LIB, '-I', stub, '-o', exe, cpp, os.path.join(LIB, 'InterpolationLib.cpp')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode:
        print(r.stdout[-6000:]); sys.exit('the curve code does not compile on the host')
    r = subprocess.run([exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout.strip())
    check(r.returncode == 0, 'the curve page on the software screen')

# ---- as source
sp = lift('src/main.cpp', 'FASTRUN void ShowServoPos()')
check('GraphMarkerMove(SavedLineX, StickPosition);' in sp and 'DisplayCurve();' not in sp and 'DrawLine(StickPosition' not in sp, 'ShowServoPos moves the marker, never redraws the curve')
check('MinimumDistance = 2;' in sp and 'map(InputUs, 1000, 2000, GRAPH_MARKER_FIRST, GRAPH_MARKER_LAST + 1)' in sp, "the marker's column by the microsecond, moved for a couple of pixels")
dcs = lift('src/main.cpp', 'FASTRUN void DisplayCurveAndServoPos()')
check('DisplayCurve();' in dcs and dcs.index('DisplayCurve();') < dcs.index('ShowServoPos();'), 'DisplayCurveAndServoPos draws the curve, then the marker')
dc = lift('src/main.cpp', 'FASTRUN void DisplayCurve()')
check('SavedLineX = NO_MARKER;' in dc and 'CurveSegments(sx1, sy1, sx2, sy2)' in dc and 'adaptiveStep' not in dc, 'DisplayCurve: the segments from CurveSegments, and no marker on the glass after it')
check(int(re.search(r'#define TXVERSION_EXTRA "B(\d+)', defs).group(1)) >= 117, 'B117 or later')
csi = lift('src/main.cpp', 'uint16_t CatmullSplineInterpolation(')
check('xPoints[k] =' not in csi and 'yPoints[k] =' not in csi and 'CatmullSpline(xPoints' not in csi and 'double xs[CURVE_POINTS_MAX], ys[CURVE_POINTS_MAX];' in csi, 'the smooth maths has arrays of its own (B120): the curve page keeps its dots')
gmm = lift('src/main.cpp', 'FLASHMEM void GraphMarkerMove(')
check(gmm.index('GetDotPositions();') < gmm.index('if (From >= GRAPH_MARKER_FIRST'), 'the marker mover takes the dots afresh')
CORE = os.path.expanduser('~/.platformio/packages/framework-arduinoteensy/cores/teensy4/wiring.h')
if os.path.exists(CORE):
    core = open(CORE).read()
    check('num += in_range / 2;' in core and 'if (in_range == 0) return out_min + out_range / 2;' in core, "the test's map() is the Teensy core's (rounding)")
print('%d source checks, %d failed' % (checks, fails))
sys.exit(1 if fails else 0)
