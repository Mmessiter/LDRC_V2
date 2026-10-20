#!/usr/bin/env python3
"""Host test of B109: the Channels page's numbers (each channel's microseconds beside its bar, screen 1.11.80), and B110:
the curve page's Input, Output and points in microseconds (StickMicros, ShowGraphMicros, DisplayCurve), and B113: each
model's max range, 500 to 2500 or 945 to 2055 (CurveMicros and the bars over it, the trims' clamp, MaxRangeConvert keeping
every point's microseconds, the Channels page's question, the model's own extension after its checksummed sequence; the
motor's safe value never moves; nothing changes on 500 to 2500).
ShowChannelMicros and Force_ReDisplay (main.cpp) and RcPut (RF_Rates.h) are lifted out by name and compiled on the Mac
over a fake of the screen's wire (its room) and the clock: every box filled on opening, whole commands only and never
more than there is room for, a stick's noise not shown, a move shown at once, a small change once it has stood half a
second, no channel left waiting when room is short. Then the call site (the Channels page only, after the bars) and,
when ESP32-board2 is here, the page file (the boxes by their buttons, the bars' middle where it was) and the screen's
button alignment (the right-hand column's words start at the left).
   python3 dev/test_channel_us/test_channel_us.py"""
import glob, json, os, re, subprocess, sys, tempfile
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
main = src('src/main.cpp')
defs1 = src('include/1Definitions.h')
DEFS = '\n'.join(l for l in defs1.split('\n') if re.match(r'#define (RANGE_NARROW_LO|RANGE_NARROW_HI|TX_EXT_MAGIC|TX_EXT_MAGIC2|TX_EXT_MAGIC3|TX_EXT_MAGIC4|CURVE_POINTS_MAX|CURVE_STORE_MAX|CURVE_UNSET) ', l)) + '\n'
sdc = src('include/SDcard.h')
DEFS += '\n'.join(l for l in sdc.split('\n') if l.startswith('#define MODEL_EXT_OFFSET_B113 ') or l.startswith('#define MODEL_EXT2_')) + '\n'
assert DEFS.count('#define') == 14, DEFS
DEFS += '\n'.join(l for l in defs1.split('\n') if re.match(r'#define (MAXMACROS|BYTESPERMACRO|MACROTRIGGERCHANNEL|MACROMOVECHANNEL|MACROSTARTTIME|MACRODURATION|MACROMOVETOPOSITION|MACRORUNNINGNOW) ', l)) + '\n'
assert DEFS.count('#define') == 22, DEFS
util = src('include/Utilities.h')
INLINES = '#define BANKS_USED 4   // (B130: four banks in this test; six are test_banks\')\n' + '\n'.join(l for l in util.split('\n') if re.match(r'inline uint16_t (RangeLo|RangeHi|CurveMicros)\(', l)) + '\n'
assert INLINES.count('inline') == 3, INLINES
TEENSY_MAP = r'''
// Teensy 4's map() for whole numbers (cores/teensy4/wiring.h): it ROUNDS - (deg x range + 90) / 180 - unlike Arduino's
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
CORE = os.path.expanduser('~/.platformio/packages/framework-arduinoteensy/cores/teensy4/wiring.h')
BANKS_STUB = r'''
// B130 (six banks): the extension functions reach for these; here the model has four banks and no banks file
static bool SixBanks = false, SingleModelFlag = false;
#define TX_EXT_MAGIC7 0xC7
#define TX_EXT_MAGIC8 0xC8
#define BANKS_BLOCK_LEN 582
static uint8_t BanksSlot() { return 1; }
static bool BanksFileRead(uint8_t, uint8_t *, int) { return false; }
static bool BanksFileWrite(uint8_t, const uint8_t *, int) { return true; }
static int BanksBlockBuild(uint8_t *blk) { memset(blk, 0, BANKS_BLOCK_LEN); return BANKS_BLOCK_LEN; }
static bool BanksBlockTake(const uint8_t *, bool) { return false; }
static void BanksFromFour() {}
'''
statics = '\n'.join(l for l in main.split('\n') if re.match(r'static (uint16_t UsShown|uint32_t UsMovedAt|uint8_t UsNext|uint16_t GraphShown|uint32_t GraphMovedAt)\b', l))
assert statics.count('\n') == 4, statics
PROG = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#define FLASHMEM
#define CHANNELSUSED 16
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
struct FakeNextion { int room = 1 << 30; int over = 0; std::string out;
    int availableForWrite() { return room; }
    size_t write(const uint8_t *b, size_t n) { if ((int)n > room) ++over; room -= (int)n; out.append((const char *)b, n); return n; } };
static FakeNextion NEXTION;
static uint32_t nowMs = 1000;
static uint32_t millis() { return nowMs; }
static uint16_t SendBuffer[CHANNELSUSED + 1], ShownBuffer[CHANNELSUSED + 1];
#include <cmath>
#define CURVE_POINTS_MAX 9
#define CURVE_STORE_MAX 13
#define CURVE_UNSET 255
#define MINMICROS 500
#define MAXMICROS 2500
#define constrain(a, l, h) ((a) < (l) ? (l) : ((a) > (h) ? (h) : (a)))
static uint16_t ChannelMin[CHANNELSUSED + 1], ChannelCentre[CHANNELSUSED + 1], ChannelMax[CHANNELSUSED + 1];
#include <map>
static uint8_t CurvePointCount[CHANNELSUSED + 1], CurvePoint[5][CHANNELSUSED + 1][9], CurveStore[5][CHANNELSUSED + 1][13];   // (B118/B121; the defines come later in this program: 9 = CURVE_POINTS_MAX, 13 = CURVE_STORE_MAX)
static uint8_t InPutStick[CHANNELSUSED + 1];
static char ChannelNames[CHANNELSUSED][11];
static char pSticksView[] = "page SticksView";
#define STICKSVIEW 1
static int CurrentView = 0; static uint32_t ModelNumber = 7;
static bool confirmAnswer = true; static int saves = 0, asks = 0, redraws = 0;
static std::vector<std::string> prompts, msgs; static std::map<std::string, int> values;
static bool GetConfirmation(char *, char *p) { ++asks; prompts.push_back(p); return confirmAnswer; }
static void MsgBox(char *, char *p) { msgs.push_back(p); }
static void SaveOneModel(uint32_t) { ++saves; }
static void SendValue(char *n, int v) { values[n] = v; }
static void UpdateModelsNameEveryWhere() {}
static void ClearText() {}
static uint8_t MaxRangeNarrow = 0; static bool MotorEnabled = false;
#define FASTRUN
static uint16_t ChannelMidLow[CHANNELSUSED + 1], ChannelMidHi[CHANNELSUSED + 1], CurveDots[9], PreMixBuffer[CHANNELSUSED + 1]; static uint8_t CurveDotsN = 5;
static uint8_t Exponential[5][CHANNELSUSED + 1], SubTrims[CHANNELSUSED + 1], Bank = 1;
static int trimNow = 0;
static int GetTrimAmount(uint8_t) { return trimNow; }
static uint8_t MacrosBuffer[16][8]; static uint32_t MacroStartTime[16], MacroStopTime[16];
typedef uint8_t u_int8_t;
void MaxRangeShow();
static void UpdateButtonLabels() { ++redraws; MaxRangeShow(); }   // (the real one sends the labels, then the choice)
// the card: models.dat or a .MOD, a byte at a time, with the running checksum as SDcard.h keeps it - and as SdFat behaves:
// a seek BEYOND the file's end fails and the position stays (FatFile::seekSet), a read at the end gives -1 (255), a write
// at the end appends. A write whose seek failed is counted: the firmware must never do one.
static std::vector<uint8_t> card; static long FileCheckSum = 0; static bool DoingCheckSm = false; static int StartLocation = 0, SDCardAddress = 0;
static size_t cardPos = 0; static int seekWriteFails = 0;
struct FakeFile { size_t size() { return card.size(); } };
static FakeFile ModelsFileNumber;
static bool cardSeek(size_t a) { if (a > card.size()) return false; cardPos = a; return true; }
static uint8_t SDRead8BITS(int a) { cardSeek((size_t)a); const uint8_t r = cardPos < card.size() ? card[cardPos++] : 255; if (!DoingCheckSm) FileCheckSum += r * (a + 1); return r; }
static void SDUpdate8BITS(int a, uint8_t v) { if (!cardSeek((size_t)a)) ++seekWriteFails; if (!DoingCheckSm) FileCheckSum += v * (a + 1); if (cardPos >= card.size()) card.resize(cardPos + 1, 0); card[cardPos++] = v; }
''' + statics + '\n' + lift('include/Utilities.h', 'uint8_t CurveN(uint8_t ch)') + 'uint8_t CurveMid(uint8_t n) { return (n - 1) / 2; }\n' + lift('include/Utilities.h', 'uint16_t CurveX(uint8_t in, uint8_t k, uint8_t n)') + lift('include/Utilities.h', 'void CurveLegacyFive(uint8_t b, uint8_t ch, uint8_t *five)') + lift('include/Utilities.h', 'uint8_t CurveStorePos(uint8_t n, uint8_t k)') + lift('include/Utilities.h', 'void CurveStoreSync(uint8_t b, uint8_t ch)') + lift('include/Utilities.h', 'void CurveStoreClear(uint8_t b, uint8_t ch)') + lift('include/Utilities.h', 'void CurveSetStraight(uint8_t b, uint8_t ch, uint8_t lo, uint8_t hi)') + lift('include/SDcard.h', 'static uint8_t Ext2Sum(const uint8_t *p, int n)') + 'static bool CurveCountOk(uint8_t n) { return n == 3 || n == 5 || n == 7 || n == 9; }\n' + lift('include/RF_Rates.h', 'FLASHMEM bool RcPut(const char *c) //') + lift('src/main.cpp', 'FLASHMEM bool UsSteadyChange(') + lift('src/main.cpp', 'FLASHMEM void ShowChannelMicros()') + lift('src/main.cpp', 'void Force_ReDisplay()') + lift('src/main.cpp', 'FLASHMEM int StickMicros(') + lift('src/main.cpp', 'FLASHMEM void ShowGraphMicros(') + DEFS + TEENSY_MAP + INLINES + lift('include/Utilities.h', 'uint8_t IntoLowerRes(uint16_t HiRes)') + lift('include/Utilities.h', 'uint16_t IntoHigherRes(uint8_t LowRes)') + lift('src/main.cpp', 'FLASHMEM static uint8_t RangeDegrees(') + lift('src/main.cpp', 'FLASHMEM void MaxRangeConvert(') + lift('src/main.cpp', 'FLASHMEM void MaxRangeShow()') + lift('src/main.cpp', 'FLASHMEM static void MaxRangeChosen(') + '\n'.join(l for l in main.split('\n') if l.startswith('FLASHMEM void MaxRange') and 'Tapped() {' in l) + '\n' + BANKS_STUB + lift('include/SDcard.h', 'void ReadModelExtension()') + lift('include/SDcard.h', 'void SaveModelExtension()') + lift('include/Utilities.h', 'FASTRUN float MapWithExponential(') + lift('src/main.cpp', 'uint16_t StraightLineInterpolation(') + lift('src/main.cpp', 'uint16_t ExponentialInterpolation(') + lift('src/main.cpp', 'void DoTrimsAndSubtrims()') + lift('include/macros.h', 'void StartMacro(uint8_t m)') + lift('include/macros.h', 'void RunMacro(uint8_t m)') + lift('include/macros.h', 'void StopMacro(uint8_t m)') + lift('include/macros.h', 'void ExecuteMacro()') + r'''
// the commands sent since the last look: "us3=1500" each (anything else is a fault)
static std::vector<std::string> sent() {
    std::vector<std::string> r; std::string &o = NEXTION.out; size_t p = 0;
    while (p < o.size()) {
        size_t e = o.find("\xFF\xFF\xFF", p);
        if (e == std::string::npos) { r.push_back("PARTIAL:" + o.substr(p)); break; }
        std::string c = o.substr(p, e - p); p = e + 3;
        int n = 0; unsigned v = 0; char tail = 0;
        if (sscanf(c.c_str(), "us%d.txt=\"%u\"%c", &n, &v, &tail) == 3 && tail == 0) {}
        if (sscanf(c.c_str(), "us%d.txt=\"%u", &n, &v) == 2 && c == "us" + std::to_string(n) + ".txt=\"" + std::to_string(v) + "\"") r.push_back("us" + std::to_string(n) + "=" + std::to_string(v));
        else r.push_back("BAD:" + c);
    }
    o.clear(); return r;
}
static bool has(const std::vector<std::string> &v, const std::string &s) { for (auto &x : v) if (x == s) return true; return false; }
static void pass(int ms = 25) { nowMs += ms; ShowChannelMicros(); }
static void all(uint16_t us) { for (int i = 0; i < CHANNELSUSED; ++i) SendBuffer[i] = us; }
int main() {
    // 1. the page opens: every box, the channel's own value, once
    for (int i = 0; i < CHANNELSUSED; ++i) SendBuffer[i] = (uint16_t)(1000 + 50 * i);
    Force_ReDisplay(); pass();
    auto s = sent();
    CHECK(s.size() == 16);
    for (int i = 0; i < CHANNELSUSED; ++i) CHECK(has(s, "us" + std::to_string(i + 1) + "=" + std::to_string(1000 + 50 * i)));
    pass(); CHECK(sent().empty());                                   // nothing new: nothing sent
    Force_ReDisplay(); pass(); CHECK(sent().size() == 16);            // the page opened again (Help, a curve): its boxes are empty, all again
    CHECK(ShownBuffer[0] == 242);                                     // (the bars are forced too, as before)
    // 2. a stick's noise: +-1 and +-2 about what is shown, never standing half a second away from it
    for (int k = 0; k < 200; ++k) { SendBuffer[0] = (uint16_t)(1000 + ((k % 4 == 1) ? 1 : (k % 4 == 3) ? -2 : 0)); SendBuffer[1] = (uint16_t)(1050 + (k % 2 ? 2 : 0)); pass(25 + (k % 3 == 0)); }   // (odd and even clocks)
    s = sent(); for (auto &x : s) fprintf(stderr, "  noise shown: %s\n", x.c_str());
    CHECK(s.empty());
    // 3. a move of 3 or more: at once
    SendBuffer[0] = 1000; SendBuffer[1] = 1050; pass(); sent();
    SendBuffer[0] = 1003; pass(); s = sent(); CHECK(s.size() == 1 && has(s, "us1=1003"));
    SendBuffer[2] = 1100 - 3; pass(); s = sent(); CHECK(s.size() == 1 && has(s, "us3=1097"));
    // 4. a small change that stands: shown after half a second, exactly
    SendBuffer[4] = 1201; pass(); CHECK(sent().empty());              // (it has differed since this pass)
    for (int t = 0; t < 400; t += 25) { pass(); }
    pass(75); CHECK(sent().empty());                                  // 475 ms: not yet
    pass(25); s = sent(); CHECK(s.size() == 1 && has(s, "us5=1201")); // 500 ms
    // ... and back to where it was shown, then away again: the half second starts again
    SendBuffer[4] = 1202; pass(300); SendBuffer[4] = 1201; pass(100); SendBuffer[4] = 1202; pass(100); pass(300); pass(150); CHECK(sent().empty());
    pass(50); s = sent(); CHECK(s.size() == 1 && has(s, "us5=1202"));
    // 5. never more than the room: whole commands only, the rest in later passes, nothing lost
    all(1500); Force_ReDisplay(); NEXTION.room = 0; pass(); CHECK(sent().empty());
    int got = 0, passes = 0; std::vector<std::string> every;
    while (got < 16 && passes < 40) { NEXTION.room = 40; pass(); auto r = sent(); got += (int)r.size(); every.insert(every.end(), r.begin(), r.end()); ++passes; }
    CHECK(got == 16); CHECK(NEXTION.over == 0); CHECK(passes == 8);  // (two commands of 18 bytes a pass)
    for (auto &x : every) CHECK(x.rfind("us", 0) == 0);
    for (int i = 1; i <= 16; ++i) CHECK(has(every, "us" + std::to_string(i) + "=1500"));
    NEXTION.room = 1 << 30; pass(); CHECK(sent().empty());
    // 6. room for two a pass while four sticks never stop: a switch on channel 16 is still shown, soon
    SendBuffer[15] = 2000; int seen = -1;
    for (int p = 0; p < 12 && seen < 0; ++p) {
        for (int i = 0; i < 4; ++i) SendBuffer[i] = (uint16_t)(1500 + ((p % 2) ? 40 : -40) + i);
        NEXTION.room = 40; pass();
        auto r = sent(); if (has(r, "us16=2000")) seen = p;
    }
    CHECK(seen >= 0 && seen <= 2); CHECK(NEXTION.over == 0);
    NEXTION.room = 1 << 30; pass(); sent();
    // 7. a channel not worked out yet (0): its box stays empty
    all(0); Force_ReDisplay(); pass(); CHECK(sent().empty());
    SendBuffer[6] = 1500; pass(); s = sent(); CHECK(s.size() == 1 && has(s, "us7=1500"));
    // 8. the widest values (500 and 2500 are the ends)
    SendBuffer[7] = 500; SendBuffer[8] = 2500; pass(); s = sent(); CHECK(has(s, "us8=500") && has(s, "us9=2500"));
    // ---- B110: the curve page ----
    // 9. the stick on 1000 .. 2000: each half by its own calibration (here the low half is shorter than the high)
    ChannelMin[0] = 300; ChannelCentre[0] = 2000; ChannelMax[0] = 3900;
    CHECK(StickMicros(0, 300) == 1000); CHECK(StickMicros(0, 2000) == 1500); CHECK(StickMicros(0, 3900) == 2000);
    CHECK(StickMicros(0, 1150) == 1250);                              // half way down the low half
    CHECK(StickMicros(0, 2950) == 1750);                              // half way up the high half
    CHECK(StickMicros(0, 1999) == 1500 && StickMicros(0, 2001) == 1500);
    CHECK(StickMicros(0, 4090) == 2050);                              // past its calibrated end it goes on ...
    CHECK(StickMicros(0, 0) == 912);
    ChannelMin[1] = 1900; ChannelCentre[1] = 2000; ChannelMax[1] = 2100;
    CHECK(StickMicros(1, 0) == 500 && StickMicros(1, 4095) == 2500); // ... but never off the scale
    ChannelMin[2] = 2000; ChannelCentre[2] = 2000; ChannelMax[2] = 2000;
    CHECK(StickMicros(2, 0) == 1500 && StickMicros(2, 4095) == 1500); // (no calibration: the middle, no division by 0)
    ChannelMin[9] = 500; ChannelCentre[9] = 1500; ChannelMax[9] = 2500; // a switch: ReadThreePositionSwitch gives these three
    CHECK(StickMicros(9, 500) == 1000 && StickMicros(9, 1500) == 1500 && StickMicros(9, 2500) == 2000);
    // 10. Input and Output: both at once on opening, then steadied as the Channels page's numbers
    NEXTION.room = 1 << 30; sent();
    for (int i = 0; i < 2; ++i) { GraphShown[i] = 0; GraphMovedAt[i] = 0; }  // (DisplayCurveAndServoPos)
    nowMs += 40; ShowGraphMicros(1620, 1740);
    { std::string o = NEXTION.out; NEXTION.out.clear();
      CHECK(o == std::string("Input.val=1620\xFF\xFF\xFFOutput.val=1740\xFF\xFF\xFF")); }
    for (int k = 0; k < 100; ++k) { nowMs += 40; ShowGraphMicros((uint16_t)(1620 + (k % 2)), (uint16_t)(1740 - 2 * (k % 2))); }
    CHECK(NEXTION.out.empty());                                       // a stick's noise: nothing
    nowMs += 40; ShowGraphMicros(1630, 1740);
    CHECK(NEXTION.out == std::string("Input.val=1630\xFF\xFF\xFF")); NEXTION.out.clear();
    nowMs += 40; ShowGraphMicros(1631, 1740); CHECK(NEXTION.out.empty());
    for (int k = 0; k < 13; ++k) { nowMs += 40; ShowGraphMicros(1631, 1740); }
    CHECK(NEXTION.out == std::string("Input.val=1631\xFF\xFF\xFF")); NEXTION.out.clear();   // stood half a second
    NEXTION.room = 10; nowMs += 40; ShowGraphMicros(1700, 1800); CHECK(NEXTION.out.empty() && NEXTION.over == 0);   // no room: nothing, not half
    NEXTION.room = 1 << 30; nowMs += 40; ShowGraphMicros(1700, 1800);
    CHECK(NEXTION.out == std::string("Input.val=1700\xFF\xFF\xFFOutput.val=1800\xFF\xFF\xFF")); NEXTION.out.clear();
    // ---- B113: each model's max range ----
    auto setCurve = [](int b, int ch, int a, int bb, int c, int d, int e) { CurvePointCount[ch] = 5; uint8_t *p = CurvePoint[b][ch]; p[0] = a; p[1] = bb; p[2] = c; p[3] = d; p[4] = e; };
    auto is = [](int b, int ch, int a, int bb, int c, int d, int e) { const uint8_t *p = CurvePoint[b][ch]; return p[0] == a && p[1] == bb && p[2] == c && p[3] == d && p[4] == e; };
    auto marks = [](int a, int b) { return values["mr1"] == a && values["mr2"] == b; };
    auto pts = [](int b, int ch, int k) -> uint8_t & { return CurvePoint[b][ch][k]; };
    // 21. 500 to 2500: exactly as before (a curve's microseconds, the bars, the ends)
    MaxRangeNarrow = 0;
    for (int d = 0; d <= 180; ++d) CHECK(CurveMicros((uint8_t)d) == IntoHigherRes((uint8_t)d));
    for (int us = 500; us <= 2500; ++us) CHECK(IntoLowerRes((uint16_t)us) == (uint8_t)map(us, MINMICROS, MAXMICROS, 0, 100));
    CHECK(RangeLo() == 500 && RangeHi() == 2500 && CurveMicros(30) == 833 && CurveMicros(150) == 2167);   // (Teensy rounds: 150 deg is 2167)
    // 22. 945 to 2055: its ends and middle, rising all the way; the bars span it and stop at its ends
    MaxRangeNarrow = 1;
    CHECK(CurveMicros(0) == 945 && CurveMicros(90) == 1500 && CurveMicros(180) == 2055);
    for (int d = 1; d <= 180; ++d) CHECK(CurveMicros((uint8_t)d) > CurveMicros((uint8_t)(d - 1)));
    CHECK(IntoLowerRes(945) == 0 && IntoLowerRes(1500) == 50 && IntoLowerRes(2055) == 100 && IntoLowerRes(833) == 0 && IntoLowerRes(2500) == 100);
    CHECK(IntoHigherRes(30) == 833);                                  // the motor's safe value never moves with the range
    // 23. a change keeps every point's microseconds where the new range has them; beyond it, the edge
    MaxRangeNarrow = 0;
    for (int ch = 0; ch < CHANNELSUSED; ++ch) for (int b = 0; b <= 4; ++b) setCurve(b, ch, 30, 60, 90, 120, 150);
    setCurve(2, 3, 0, 45, 90, 135, 180); setCurve(3, 5, 150, 120, 90, 60, 30); setCurve(4, 9, 70, 80, 95, 100, 110);
    static uint16_t before[5][CHANNELSUSED][5];
    for (int b = 1; b <= 4; ++b) for (int ch = 0; ch < CHANNELSUSED; ++ch) for (int k = 0; k < 5; ++k) before[b][ch][k] = CurveMicros(pts(b, ch, k));
    MaxRangeConvert(1);
    CHECK(MaxRangeNarrow == 1);
    for (int b = 1; b <= 4; ++b) for (int ch = 0; ch < CHANNELSUSED; ++ch) for (int k = 0; k < 5; ++k)
    {
        const int was = before[b][ch][k], now = CurveMicros(pts(b, ch, k));
        if (was < 945) CHECK(now == 945); else if (was > 2055) CHECK(now == 2055); else CHECK(abs(now - was) <= 3);
    }
    CHECK(is(1, 0, 0, 36, 90, 144, 180));                               // 833 1167 1500 1833 2167 -> 945 1167 1500 1833 2055
    CHECK(is(3, 5, 180, 144, 90, 36, 0) && is(2, 3, 0, 9, 90, 171, 180));   // (500 1000 1500 2000 2500 -> 945 1000 1500 2000 2055)
    for (int ch = 0; ch < CHANNELSUSED; ++ch) CHECK(is(0, ch, 30, 60, 90, 120, 150));   // (bank 0 is not a bank)
    for (int b = 1; b <= 4; ++b) for (int ch = 0; ch < CHANNELSUSED; ++ch) for (int k = 0; k < 5; ++k) before[b][ch][k] = CurveMicros(pts(b, ch, k));
    MaxRangeConvert(0);                                                 // and back: kept again, to half a degree of the wider range
    CHECK(MaxRangeNarrow == 0);
    for (int b = 1; b <= 4; ++b) for (int ch = 0; ch < CHANNELSUSED; ++ch) for (int k = 0; k < 5; ++k) CHECK(abs((int)CurveMicros(pts(b, ch, k)) - (int)before[b][ch][k]) <= 6);
    // 24. the Channels page's choice: asked, changed, saved, marked
    for (int ch = 0; ch < CHANNELSUSED; ++ch) for (int b = 1; b <= 4; ++b) setCurve(b, ch, 30, 60, 90, 120, 150);
    confirmAnswer = true; MotorEnabled = false; const int a0 = asks, s0 = saves;
    MaxRangeShow(); CHECK(marks(1, 0));
    MaxRangeNarrowTapped();
    CHECK(MaxRangeNarrow == 1 && asks == a0 + 1 && saves == s0 + 1 && marks(0, 1) && is(1, 0, 0, 36, 90, 144, 180));
    CHECK(prompts.back().find("945 to 2055? Each point keeps its value;") != std::string::npos && prompts.back().find("Check every channel before flying.") != std::string::npos);
    CHECK(msgs.back().find("Done: this model's max range is\r\nnow 945 to 2055.") == 0);
    CHECK(CurrentView == STICKSVIEW && ShownBuffer[0] == 242);          // the page drawn again after the question
    values["mr1"] = 1; values["mr2"] = 0; MaxRangeNarrowTapped();       // the one already chosen: nothing asked, the marks put right
    CHECK(asks == a0 + 1 && saves == s0 + 1 && marks(0, 1));
    confirmAnswer = false; MaxRangeWideTapped();                        // No: nothing
    CHECK(MaxRangeNarrow == 1 && asks == a0 + 2 && saves == s0 + 1 && marks(0, 1) && is(1, 0, 0, 36, 90, 144, 180));
    confirmAnswer = true; MotorEnabled = true; MaxRangeWideTapped();    // the motor live: refused, nothing asked
    CHECK(MaxRangeNarrow == 1 && asks == a0 + 2 && msgs.back().find("Switch the motor off first") == 0);
    MotorEnabled = false; MaxRangeWideTapped();
    CHECK(MaxRangeNarrow == 0 && saves == s0 + 2 && marks(1, 0) && prompts.back().find("500 to 2500? Each point keeps its value:") != std::string::npos);
    CHECK(abs((int)CurveMicros(CurvePoint[1][0][0]) - 945) <= 6 && abs((int)CurveMicros(CurvePoint[1][0][4]) - 2055) <= 6);
    // 25. the model's own extension: right after the checksummed sequence (B114), outside its checksum, never a seek beyond the file
    for (int b = 0; b <= 4; ++b) for (int c = 0; c <= CHANNELSUSED; ++c) { CurveStoreClear(b, c); CurveStoreSync(b, c); }   // (B121: nothing remembered beyond the five of old, as a model just read)
    auto record = [&](size_t len) { card.assign(len, 0); StartLocation = 0; SDCardAddress = (int)len; FileCheckSum = 0; seekWriteFails = 0; };   // (a record's checksum ends at len)
    record(2100);
    MaxRangeNarrow = 0; SaveModelExtension(); CHECK(card.size() == 2100);                  // never set: the file not lengthened
    MaxRangeNarrow = 1; SaveModelExtension();
    CHECK(card.size() == 2103 && card[2100] == 0x5A && card[2101] == 0xC3 && card[2102] == 1 && FileCheckSum == 0 && seekWriteFails == 0);   // an append
    MaxRangeNarrow = 0; ReadModelExtension(); CHECK(MaxRangeNarrow == 1 && FileCheckSum == 0);
    MaxRangeNarrow = 0; SaveModelExtension(); CHECK(card.size() == 2103 && card[2102] == 0 && seekWriteFails == 0);   // there once: kept true
    MaxRangeNarrow = 1; ReadModelExtension(); CHECK(MaxRangeNarrow == 0);
    card[2102] = 1; card[2101] = 0; ReadModelExtension(); CHECK(MaxRangeNarrow == 0);     // one marker wrong: 500 to 2500
    card[2101] = 0xC3; card[2102] = 7; ReadModelExtension(); CHECK(MaxRangeNarrow == 0);  // a value not ours: 500 to 2500
    record(2100); MaxRangeNarrow = 1; ReadModelExtension(); CHECK(MaxRangeNarrow == 0);   // an old record, nothing after it: 500 to 2500 (reads at the end give 255)
    // models.dat: model 3's record, the file holding more; the markers go in the gap after its checksum, the file no longer
    record(512 + 5 * 3072); StartLocation = 512 + 2 * 3072; SDCardAddress = StartLocation + 2016;
    MaxRangeNarrow = 1; SaveModelExtension();
    CHECK(card.size() == 512 + 5 * 3072 && card[SDCardAddress] == 0x5A && card[SDCardAddress + 1] == 0xC3 && card[SDCardAddress + 2] == 1 && seekWriteFails == 0);
    MaxRangeNarrow = 0; ReadModelExtension(); CHECK(MaxRangeNarrow == 1);
    MaxRangeNarrow = 0; SaveModelExtension(); ReadModelExtension(); CHECK(MaxRangeNarrow == 0 && card[SDCardAddress + 2] == 0);
    // B113's place (offset 3064 of the record) is still read, as a fallback, when the file reaches it ...
    record(512 + 5 * 3072); StartLocation = 512 + 2 * 3072; SDCardAddress = StartLocation + 2016;
    card[StartLocation + 3064] = 0x5A; card[StartLocation + 3065] = 0xC3; card[StartLocation + 3066] = 1;
    MaxRangeNarrow = 0; ReadModelExtension(); CHECK(MaxRangeNarrow == 1);
    MaxRangeNarrow = 0; SaveModelExtension(); ReadModelExtension(); CHECK(MaxRangeNarrow == 0);   // ... but what sits after the checksum wins once written (B113's byte still says 1)
    CHECK(card[StartLocation + 3066] == 1 && card[SDCardAddress + 2] == 0);
    // ... and never beyond the file: a .MOD (2019 bytes) with B113's accidental layout - its bytes right after the checksum - reads as narrow
    record(2016); card.resize(2019, 0); card[2016] = 0x5A; card[2017] = 0xC3; card[2018] = 1;
    MaxRangeNarrow = 0; ReadModelExtension(); CHECK(MaxRangeNarrow == 1);
    record(2016); MaxRangeNarrow = 0; ReadModelExtension(); CHECK(MaxRangeNarrow == 0);   // a .MOD too short for B113's place: not looked at
    MaxRangeNarrow = 0;
    // 26. the curves themselves (the flying path): a curve to the top and bottom ends at the range's ends; the middle is 1500
    ChannelMin[0] = 300; ChannelMidLow[0] = 1150; ChannelCentre[0] = 2000; ChannelMidHi[0] = 2950; ChannelMax[0] = 3900;
    const uint8_t full[5] = {0, 45, 90, 135, 180}; for (int k = 0; k < 5; ++k) CurveDots[k] = full[k];
    Exponential[1][0] = 80;                                             // (the curve page's "30")
    for (int narrow = 0; narrow <= 1; ++narrow)
    {
        MaxRangeNarrow = (uint8_t)narrow; const int lo = narrow ? 945 : 500, hi = narrow ? 2055 : 2500;
        CHECK(StraightLineInterpolation(300, 0, 0) == lo && StraightLineInterpolation(2000, 0, 0) == 1500 && StraightLineInterpolation(3900, 0, 0) == hi);
        CHECK(ExponentialInterpolation(300, 0, 0) == lo && ExponentialInterpolation(2000, 0, 0) == 1500 && ExponentialInterpolation(3900, 0, 0) == hi);
        int last = 0; bool rising = true;
        for (int raw = 300; raw <= 3900; raw += 25) { const int v = ExponentialInterpolation((uint16_t)raw, 0, 0); if (v < last) rising = false; last = v; }
        CHECK(rising);
    }
    // ... and on 500 to 2500, a new model's curve gives what it always gave: 833 and 2167 at the ends (IntoHigherRes's numbers)
    MaxRangeNarrow = 0; const uint8_t dflt[5] = {30, 60, 90, 120, 150}; for (int k = 0; k < 5; ++k) CurveDots[k] = dflt[k];
    CHECK(StraightLineInterpolation(300, 0, 0) == IntoHigherRes(30) && StraightLineInterpolation(3900, 0, 0) == IntoHigherRes(150) && StraightLineInterpolation(2950, 0, 0) == IntoHigherRes(120));
    // 27. the trims' clamp: every channel inside the range, whatever trims and subtrims add
    for (int ch = 0; ch < CHANNELSUSED; ++ch) { InPutStick[ch] = 0; SubTrims[ch] = 127; }
    MaxRangeNarrow = 1; SendBuffer[0] = 2055; SendBuffer[1] = 945; SendBuffer[2] = 1600; trimNow = 40; DoTrimsAndSubtrims();
    CHECK(SendBuffer[0] == 2055 && SendBuffer[1] == 985 && SendBuffer[2] == 1640 && PreMixBuffer[0] == 2055);
    SendBuffer[1] = 945; trimNow = -40; DoTrimsAndSubtrims(); CHECK(SendBuffer[1] == 945);
    MaxRangeNarrow = 0; SendBuffer[0] = 2500; SendBuffer[1] = 945; trimNow = 40; DoTrimsAndSubtrims();
    CHECK(SendBuffer[0] == 2500 && SendBuffer[1] == 985);
    SendBuffer[1] = 520; trimNow = -40; DoTrimsAndSubtrims(); CHECK(SendBuffer[1] == 500);
    trimNow = 0;
    // 28. macros: a trigger at the top of the range starts one (2055 when narrow: it waited for 2499 before); its place is a point of the range
    memset(MacrosBuffer, 0, sizeof(MacrosBuffer));
    MacrosBuffer[0][MACROTRIGGERCHANNEL] = 8; MacrosBuffer[0][MACROMOVECHANNEL] = 3; MacrosBuffer[0][MACROMOVETOPOSITION] = 0; MacrosBuffer[0][MACRODURATION] = 50;
    for (int narrow = 0; narrow <= 1; ++narrow)
    {
        MaxRangeNarrow = (uint8_t)narrow; MacrosBuffer[0][MACRORUNNINGNOW] = 0;
        SendBuffer[7] = (uint16_t)(RangeHi() - 2); SendBuffer[2] = 1500; ExecuteMacro(); CHECK(MacrosBuffer[0][MACRORUNNINGNOW] == 0 && SendBuffer[2] == 1500);
        SendBuffer[7] = RangeHi(); ExecuteMacro(); CHECK(MacrosBuffer[0][MACRORUNNINGNOW] != 0 && SendBuffer[2] == RangeLo());
        SendBuffer[7] = 1500; ExecuteMacro(); CHECK(MacrosBuffer[0][MACRORUNNINGNOW] == 0);
    }
    // a range change carries the macros' places with it, as it does the curves' points
    MaxRangeNarrow = 0; MacrosBuffer[1][MACROMOVETOPOSITION] = 60; MacrosBuffer[2][MACROMOVETOPOSITION] = 180; MacrosBuffer[3][MACROMOVETOPOSITION] = 90;
    MaxRangeConvert(1);
    CHECK(MacrosBuffer[0][MACROMOVETOPOSITION] == 0 && MacrosBuffer[1][MACROMOVETOPOSITION] == 36 && MacrosBuffer[2][MACROMOVETOPOSITION] == 180 && MacrosBuffer[3][MACROMOVETOPOSITION] == 90);
    MaxRangeConvert(0);
    CHECK(abs((int)CurveMicros(MacrosBuffer[1][MACROMOVETOPOSITION]) - 1167) <= 6);
    MaxRangeNarrow = 0;
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
# the call: on the Channels page only, after the bars
sp = lift('src/main.cpp', 'FASTRUN void ShowServoPos()')
check(re.search(r'if \(CurrentView == STICKSVIEW\)\s*\n\s*ShowChannelMicros\(\);', sp) is not None, 'ShowServoPos calls ShowChannelMicros on STICKSVIEW only')
check(sp.count('ShowChannelMicros') == 1, 'one call')
check(sp.index('ShowChannelMicros') > sp.rindex('SendValue(Ch_Lables[i]'), 'the numbers after the bars')
check('FLASHMEM void ShowChannelMicros()' in main, 'ShowChannelMicros is FLASHMEM (ITCM is nearly full)')
# B110: the curve page
check('const int InputUs = StickMicros(InputDevice, InputAmount);' in sp and 'map(InputUs, 1000, 2000, GRAPH_MARKER_FIRST, GRAPH_MARKER_LAST + 1)' in sp, 'the stick line placed from the same input as the number (B117: by the microsecond)')
check('ShowGraphMicros(InputUs, SendBuffer[ChanneltoSet - 1]);' in sp, 'Output is what the channel sends')
check('map(SendBuffer' not in sp and 'SendValue(ChannelInput' not in sp and 'SendValue(ChannelOutput' not in sp, 'no percentages left on the curve page')
dc = lift('src/main.cpp', 'FASTRUN void DisplayCurve()')
cls = lift('src/main.cpp', 'FLASHMEM void CurveLayoutShow()')
check('CurveLayoutShow();' in dc and 'snprintf(Cmd, sizeof(Cmd), "%s.val=%d", names[k], CurveMicros(CurvePoint[Bank][ch][idx]));' in cls, 'the points along the top in microseconds (B113: in the max range; B118: for 3, 5, 7 or 9 points)')
check('DegsToPercent' not in dc, 'no point in per cent')
dcs = lift('src/main.cpp', 'FASTRUN void DisplayCurveAndServoPos()')
check(re.search(r'GraphShown\[i\] = 0;', dcs) is not None and dcs.index('GraphShown') < dcs.index('ShowServoPos();'), 'the curve page opened: Input and Output shown afresh')
# B113: each model's max range
sdv = lift('src/main.cpp', 'void SetDefaultValues(bool Calibrating)')
check(all(x in sdv for x in ('CurveSetStraight(j, i, 30, 150);', 'CurvePointCount[i] = 5;', 'MaxRangeNarrow = 0;')), 'a new model: five points, 833 and 2167 ends, 500 to 2500')
check(main.count('CurveMicros(CurveDots[') == 9 and 'IntoHigherRes(CurveDots[' not in main, 'every curve point through CurveMicros (9: B118 loops over the points)')
bw = src('include/BuddyWireless.h')
check(main.count('IntoHigherRes(MotorChannelZero)') == 1 and bw.count('IntoHigherRes(MotorChannelZero)') == 2, "the motor's safe value stays 500 to 2500 (it must never move with the range)")
dts = lift('src/main.cpp', 'void DoTrimsAndSubtrims()')
check('constrain(TrimmedValue, (int)RangeLo(), (int)RangeHi())' in dts, "every channel ends inside the range (the trims' clamp)")
mx = src('include/Mixes.h')
check(mx.count('CurveMicros(CurvePoint[Bank][Slave][0])') == 1 and mx.count('CurveMicros(CurvePoint[Bank][Slave][CurveN(Slave) - 1])') == 1, "a mix stops at its channel's curve ends in the range")
dc2 = lift('src/main.cpp', 'FASTRUN void DisplayCurve()')
check('CurveLayoutShow();' in dc2 and 'IntoHigherRes' not in dc2 and 'IntoHigherRes' not in cls, "the curve page's points in the range")
fg = src('include/FlightGuard.h')
blk2 = fg[fg.index('if (FrontSwitchUnused) // B38'):fg.index('return FingerprintSoFar;')]
check(re.search(r'''if \(MaxRangeNarrow\)[^\n]*\n\s*\{\s*Fp\(0x5EC4\);\s*Fp\(MaxRangeNarrow\);\s*\}\s*\}\s*for \(i = 0; i < CHANNELSUSED; \+\+i\)[^\n]*B118[^\n]*\n\s*if \(CurveN\(i\) != 5\)\s*\{\s*Fp\(0x5EC5\);''', blk2) is not None and blk2.rstrip().endswith('}'), 'the fingerprint: the range folded in, then (B118) a curve of other than five points, only when in use (an update is compared as before)')
rom = src('include/SDcard.h')
r1 = rom[rom.index('bool ReadOneModel(uint32_t Mnum)'):]
check(r1.index('MaxRangeNarrow = 0;') < r1.index('ModelDefined = SDRead8BITS') and 'ReadCheckSum32();\n    ReadModelExtension();' in r1, 'a model read: 500 to 2500 until its own extension says otherwise')
check('SaveCheckSum32(); // Save the Model parametres checksm\n    SaveModelExtension();' in rom, 'a model saved: its extension after the checksum')
mods = glob.glob(os.path.join(TC, 'SD Examples', '*', 'mod', '*.MOD'))
offs = int(re.search(r'#define MODEL_EXT_OFFSET_B113 (\d+)', sdc).group(1))
longest = max(os.path.getsize(m) for m in mods) if mods else 0
check(mods and longest + 500 < offs and offs + 3 <= 3 * 1024, "B113's fallback place lies clear past the sequence (%d bytes the longest example) and inside the record" % longest)
rme, sme = lift('include/SDcard.h', 'void ReadModelExtension()'), lift('include/SDcard.h', 'void SaveModelExtension()')
check('const int a = SDCardAddress;' in rme and 'const int a = SDCardAddress;' in sme and 'StartLocation + MODEL_EXT_OFFSET_B113' in rme and 'MODEL_EXT_OFFSET_B113' not in sme, "B114: the extension written right after the checksum (an append at most); B113's place read only as a fallback")
check('ModelsFileNumber.size() >= b + 3' in rme, 'the fallback never reads beyond the file')
check(re.search(r'RatesCurvesOk,\s*// 218[^\n]*\n\s*MaxRangeWideTapped,\s*// 219[^\n]*\n\s*MaxRangeNarrowTapped,\s*// 220[^\n]*\n\s*CurvePoints3Tapped,\s*// 221[^\n]*\n\s*CurvePoints5Tapped,\s*// 222[^\n]*\n\s*CurvePoints7Tapped,\s*// 223[^\n]*\n\s*CurvePoints9Tapped,\s*// 224[^\n]*\n\s*CurveResetTapped,\s*// 225[^\n]*\n\s*CurveFlatTapped\s*// 226', main) is not None and '#define LASTFUNCTION1 227' in main, 'codes 219 and 220 are the two range choices, 221-224 the points (B118), 225-226 Reset and Flat (B135)')
tb = main[main.index('void (*NumberedFunctions1[LASTFUNCTION1])(){'):]
tb = re.sub(r'//[^\n]*', '', tb[tb.index('){') + 2:tb.index('};')])
check(len([e for e in tb.split(',') if e.strip()]) == int(re.search(r'#define LASTFUNCTION1 (\d+)', main).group(1)), 'the table has exactly LASTFUNCTION1 entries (none missing: a missing one would be called as nothing)')
ubl = lift('src/main.cpp', 'void UpdateButtonLabels()')
blk = ubl[ubl.index('if (CurrentView == STICKSVIEW)'):ubl.index('if (CurrentView == FAILSAFE_VIEW)')]
check(blk.count('MaxRangeShow();') == 1 and blk.index('MaxRangeShow();') > blk.index('SendText(ChannelLabels[i], LabelText);'), "the choice shown whenever the Channels page's labels are")
check('StickEnds' not in main and 'STICK_END' not in main, "B111/B112's stick ends are gone")
adj = lift('include/RF_Adjust.h', 'FLASHMEM static int AdjTxBankUs(')
check('if (v < (int)RangeLo()) v = RangeLo();' in adj and 'if (v > (int)RangeHi()) v = RangeHi();' in adj, "the Adjustments page predicts each bank's value inside the range, as it is sent")
if os.path.exists(CORE):
    core = open(CORE).read()
    check('num += in_range / 2;' in core and 'if (in_range == 0) return out_min + out_range / 2;' in core, "the test's map() is the Teensy core's (rounding)")
help_ch = open(os.path.join(ROOT, 'Help files for SD', 'CHANNELS.TXT')).read()
check('MAX RANGE:' in help_ch and '945 to 2055' in help_ch and '500 to 2500' in help_ch and 'STICK ENDS' not in help_ch and all(len(l) <= 66 for l in help_ch.split('\n')), 'CHANNELS.TXT: the max range')
help_c = open(os.path.join(ROOT, 'Help files for SD', 'CURVES.TXT')).read()
check("'Input'" in help_c and "'Output'" in help_c and 'microseconds' in help_c and '-100 to 100' not in help_c and "model's max range" in help_c, 'CURVES.TXT speaks of microseconds and the max range')
check(all(len(l) <= 66 for l in help_c.split('\n')), 'CURVES.TXT lines no longer than its longest before (66)')
# the page and the screen (ESP32-board2 beside TXV1B)
EMU = os.path.join(ROOT, '..', 'ESP32-board2', 'board4', 'nextion-emulator')
P = os.path.join(EMU, 'sd', 'hmi', 'pages', '26.json')
if os.path.exists(P):
    sys.path.insert(0, os.path.join(EMU, 'hmi'))
    from fontw import width
    pg = json.load(open(P)); comps = pg['comps']; by = {c['n']: c for c in comps}
    check(pg['name'] == 'SticksView', 'page 26 is SticksView')
    check(len({c['i'] for c in comps}) == len(comps), 'component ids unique')
    idx = json.load(open(os.path.join(EMU, 'sd', 'hmi', 'index.json')))
    check([x['n'] for x in idx['pages'] if x['id'] == 26] == [len(comps)], 'index.json counts page 26 right')
    order = [c['n'] for c in comps]
    bars = [by['Ch%d' % i] for i in range(1, 17)]
    for b in bars: check(b['x'] + b['w'] // 2 == 400 and b['w'] == bars[0]['w'] and b['x'] == bars[0]['x'], '%s: the middle line at 400' % b['n'])
    bx0, bx1 = bars[0]['x'], bars[0]['x'] + bars[0]['w']
    def overlap(a, b): return a['x'] < b['x'] + b['w'] and b['x'] < a['x'] + a['w'] and a['y'] < b['y'] + b['h'] and b['y'] < a['y'] + a['h']
    for i in range(1, 17):
        u, s = by.get('us%d' % i), by['Sch%d' % i]
        check(u is not None, 'us%d on the page' % i)
        if u is None: continue
        check(u['t'] == 'text' and u['font'] == s['font'] and u['sta'] == 1 and u['a']['xcen'] == 1, 'us%d: text, the buttons\' font, solid, centred' % i)
        check(u['c']['bco'] == 4426 and u['c']['pco'] == 65535, 'us%d: on the card in the theme\'s colours' % i)
        check(u['y'] == s['y'] and u['h'] == s['h'], 'us%d: level with its button' % i)
        if i % 2: check(u['x'] == s['x'] + s['w'] and u['x'] + u['w'] <= bx0, 'us%d: between its left button and the bars' % i)
        else: check(u['x'] >= bx1 and u['x'] + u['w'] == s['x'], 'us%d: between the bars and its right button' % i)
        check(u['txt'] == '' and u['g'] == 'l', 'us%d: empty until the Teensy writes it' % i)
        check(width(u['font'], '2500') + 8 <= u['w'], 'us%d: 2500 fits with room' % i)
        check(order.index(u['n']) > order.index('card'), 'us%d drawn over the card' % i)
        for c in comps:
            if c['n'] in ('card', 'strip', u['n']) or c['t'] in ('variable', 'audio') or 'x' not in c: continue
            check(not overlap(u, c), 'us%d does not cover %s' % (i, c['n']))
        bar = by['Ch%d' % i]
        check(abs((u['y'] + u['h'] / 2) - (bar['y'] + bar['h'] / 2)) <= 1, 'us%d: centred on its bar' % i)
    for i in range(1, 17): check(by['Sch%d' % i]['a']['xcen'] == (2 if i % 2 else 0), 'Sch%d: words to the %s' % (i, 'right' if i % 2 else 'left'))
    okb = by['b10']
    for k, (code, txt) in enumerate(((219, '500 to 2500'), (220, '945 to 2055')), start=1):
        r, w = by.get('mr%d' % k), by.get('lmr%d' % k)
        ev = 'mr1.val=%d\nmr2.val=%d\nva0.val=%d<<8\nprint va0.val' % (k == 1, k == 2, code)
        check(r is not None and r['t'] == 'radio' and r['g'] == 'g' and r['ev'].get('r') == ev, 'mr%d: a radio button, global, marks itself and sends %d' % (k, code))
        check(w is not None and w['txt'] == txt and w['ev'].get('r') == ev and width(w['font'], txt) <= w['w'], 'its words, the same touch')
    row = [by[n] for n in ('lmr', 'mr1', 'lmr1', 'mr2', 'lmr2') if n in by]
    check(len(row) == 5 and by['lmr']['txt'] == 'Max range:' and not any(n in by for n in ('se1', 'se2', 'lse1', 'lse2', 'lse', 'se')), '"Max range:" and its two choices (the stick ends gone)')
    for i2, a2 in enumerate(row):
        check(a2['y'] >= by['Sch15']['y'] + by['Sch15']['h'] and not overlap(a2, okb) and order.index(a2['n']) > order.index('card'), '%s: bottom left, clear of OK, over the card' % a2['n'])
        for b2 in row[i2 + 1:]: check(not overlap(a2, b2), '%s clear of %s' % (a2['n'], b2['n']))
    p21 = json.load(open(os.path.join(EMU, 'sd', 'hmi', 'pages', '21.json'))); b21 = {c['n']: c for c in p21['comps']}
    check(p21['name'] == 'GraphView' and b21['t1']['txt'] == 'Input' and b21['t2']['txt'] == 'Output', 'the curve page says Input and Output')
    for n in ('Input', 'Output', 'n1', 'n2', 'n3', 'n4', 'n5'):
        check(b21[n]['t'] == 'number' and width(b21[n]['font'], '2500') <= b21[n]['w'] - 2, '%s holds 2500' % n)
    m = open(os.path.join(EMU, 'src', 'main.cpp')).read()
    bt = m[m.index('if (t == "button" || t == "dual-state button") {'):]
    bt = bt[:bt.index('return;')]
    check('c.xcen ? c.xcen : 1' not in bt and 'c.txt, c.xcen,' in bt, 'the screen draws a button\'s words where its own alignment says (0 = left)')
    check('c.xcen = a["xcen"] | ((c.type == "button" || c.type == "dual-state button") ? 1 : 0);' in m, 'a button that gives no alignment is still centred')
else:
    print('(ESP32-board2 is not here: the page and the screen not checked)')
print('page and source: %d checks%s' % (checks, ', FAILED' if fails else ''))
sys.exit(1 if fails else 0)
