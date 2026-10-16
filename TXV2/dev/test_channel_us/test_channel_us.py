#!/usr/bin/env python3
"""Host test of B109: the Channels page's numbers (each channel's microseconds beside its bar, screen 1.11.80), and B110:
the curve page's Input, Output and points in microseconds (StickMicros, ShowGraphMicros, DisplayCurve).
ShowChannelMicros and Force_ReDisplay (main.cpp) and RcPut (RF_Rates.h) are lifted out by name and compiled on the Mac
over a fake of the screen's wire (its room) and the clock: every box filled on opening, whole commands only and never
more than there is room for, a stick's noise not shown, a move shown at once, a small change once it has stood half a
second, no channel left waiting when room is short. Then the call site (the Channels page only, after the bars) and,
when ESP32-board2 is here, the page file (the boxes by their buttons, the bars' middle where it was) and the screen's
button alignment (the right-hand column's words start at the left).
   python3 dev/test_channel_us/test_channel_us.py"""
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
main = src('src/main.cpp')
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
#define MINMICROS 500
#define MAXMICROS 2500
#define constrain(a, l, h) ((a) < (l) ? (l) : ((a) > (h) ? (h) : (a)))
static uint16_t ChannelMin[CHANNELSUSED + 1], ChannelCentre[CHANNELSUSED + 1], ChannelMax[CHANNELSUSED + 1];
''' + statics + '\n' + lift('include/RF_Rates.h', 'FLASHMEM bool RcPut(const char *c) //') + lift('src/main.cpp', 'FLASHMEM bool UsSteadyChange(') + lift('src/main.cpp', 'FLASHMEM void ShowChannelMicros()') + lift('src/main.cpp', 'void Force_ReDisplay()') + lift('src/main.cpp', 'FLASHMEM int StickMicros(') + lift('src/main.cpp', 'FLASHMEM void ShowGraphMicros(') + r'''
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
check('const int InputUs = StickMicros(InputDevice, InputAmount);' in sp and 'InputAmount = (InputUs - 1500) / 5;' in sp, 'the stick line placed from the same input as the number')
check('ShowGraphMicros(InputUs, SendBuffer[ChanneltoSet - 1]);' in sp, 'Output is what the channel sends')
check('map(SendBuffer' not in sp and 'SendValue(ChannelInput' not in sp and 'SendValue(ChannelOutput' not in sp, 'no percentages left on the curve page')
dc = lift('src/main.cpp', 'FASTRUN void DisplayCurve()')
for n, deg in (('n1', 'MinDegrees'), ('n2', 'MidLowDegrees'), ('n3', 'CentreDegrees'), ('n4', 'MidHiDegrees'), ('n5', 'MaxDegrees')):
    check('sprintf(tempCmd, "%s.val=%%d", IntoHigherRes(%s[Bank][ChanneltoSet - 1]));' % (n, deg) in dc, '%s: the point in microseconds' % n)
check('DegsToPercent' not in dc, 'no point in per cent')
dcs = lift('src/main.cpp', 'FASTRUN void DisplayCurveAndServoPos()')
check(re.search(r'GraphShown\[i\] = 0;', dcs) is not None and dcs.index('GraphShown') < dcs.index('ShowServoPos();'), 'the curve page opened: Input and Output shown afresh')
help_c = open(os.path.join(ROOT, 'Help files for SD', 'CURVES.TXT')).read()
check("'Input'" in help_c and "'Output'" in help_c and 'microseconds' in help_c and '-100 to 100' not in help_c, 'CURVES.TXT speaks of microseconds')
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
