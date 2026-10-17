#!/usr/bin/env python3
"""Host test of B115 and screen 1.11.81: the curve page's three switches (Straight, Smooth, Exponential).
Malcolm, 17 Oct 2026: "after selecting Straight, I cannot afterwards select Smooth or Exponential. If I do it just reverts
to Straight." Two faults, one on each board:
  - the screen's emulator flipped a switch at the LIFT, after the press event had run: page 21's switches clear the other
    two in their press event ("if(Smooth.val==1)"), which saw the old value - so two stayed on (1.11.81: a switch, dual-state
    button, checkbox or radio changes as the finger lands, as a Nextion's does, then the press event runs);
  - the main board read the three switches and let the LAST one asked (Lines) win when two were on, and a read that failed
    (65535) counted as on (B115: the tapped switch is the one now on that is not the type already chosen).
The main board's "Exrite" block is lifted out of main.cpp's screen handler and compiled on the Mac over a fake screen; the
screen's main.cpp and page 21 are checked as source.
   python3 dev/test_curve_type/test_curve_type.py
TXV1B_TC (the TransmitterCode folder) and V2_SCREEN (the screen's project) point the test elsewhere (mutation runs)."""
import json, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.environ.get('TXV1B_TC', os.path.join(ROOT, 'TransmitterCode'))
SCREEN = os.environ.get('V2_SCREEN', os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator'))
checks = fails = 0
def check(c, what):
    global checks, fails
    checks += 1
    if not c:
        fails += 1
        print('FAIL:', what)
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()

# ---------------------------------------------------------------- the main board: the Exrite block, lifted and run
main = src('src/main.cpp')
lines = main.split('\n')
start = next(i for i, l in enumerate(lines) if l.strip() == 'if (InStrng(Exrite, TextIn) > 0)')
indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
end = next(j for j in range(start + 2, len(lines)) if lines[j] == indent + '}')
body = '\n'.join(lines[start + 2:end])
defs = src('include/1Definitions.h')
types = '\n'.join(l for l in defs.split('\n') if re.match(r'#define (STRAIGHTLINES|SMOOTHEDCURVES|EXPONENTIALCURVES) ', l))
assert types.count('#define') == 3, types

PROGRAM = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
@TYPES@
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static std::map<std::string, long> values;
static uint32_t GetValue(char *n) { return values.count(n) ? (uint32_t) values[n] : 65535; }   // a box that did not answer: GetValue's 65535
uint8_t InterpolationTypes[5][17], Exponential[5][17];
int Bank = 1, ChanneltoSet = 1;
static int cleared = 0, drawn = 0;
static void ClearText() { ++cleared; }
static void DisplayCurveAndServoPos() { ++drawn; }
static void Exrite()
{
    char ExpR[] = "Exp"; char Smooth[] = "Smooth"; char Lines[] = "Lines"; char Expo[] = "Expo";
@BODY@
}
// a tap: the three switches as the screen now has them (Lines, Smooth, Exp = STRAIGHTLINES, SMOOTHEDCURVES, EXPONENTIALCURVES), the expo number
static int tap(int from, long l, long s, long e, long expo = 0)
{
    values.clear(); values["Lines"] = l; values["Smooth"] = s; values["Exp"] = e; values["Expo"] = expo;
    InterpolationTypes[Bank][ChanneltoSet - 1] = (uint8_t) from; Exrite(); return InterpolationTypes[Bank][ChanneltoSet - 1];
}
int main()
{
    // 1. a screen that clears the other two (1.11.81): the one switch on is the type
    for (int from = 0; from < 3; ++from) for (int to = 0; to < 3; ++to) CHECK(tap(from, to == 0, to == 1, to == 2) == to);
    // 2. the chosen one tapped off - none on: the type stays (the main board then sends its switch back on)
    for (int from = 0; from < 3; ++from) CHECK(tap(from, 0, 0, 0) == from);
    // 3. an older screen: the old one still on beside the tapped one - the tapped one wins, whichever is asked last
    for (int from = 0; from < 3; ++from) for (int to = 0; to < 3; ++to) if (to != from) CHECK(tap(from, from == 0 || to == 0, from == 1 || to == 1, from == 2 || to == 2) == to);
    // 4. the fault Malcolm saw: Straight on, Smooth tapped (both on) - Smooth; then Exponential tapped (Smooth and Exp on) - Exponential
    CHECK(tap(0, 1, 1, 0) == 1); CHECK(tap(1, 0, 1, 1) == 2); CHECK(tap(0, 1, 0, 1) == 2);
    // 5. reads that failed (65535) are not "on"
    for (int from = 0; from < 3; ++from) { values.clear(); values["Expo"] = 0; InterpolationTypes[1][0] = (uint8_t) from; Exrite(); CHECK(InterpolationTypes[1][0] == from); }
    CHECK(tap(0, 65535, 1, 65535) == 1);
    CHECK(tap(2, 65535, 65535, 65535) == 2);
    CHECK(tap(0, 1, 65535, 65535) == 0);
    // 6. the expo: the number shown (-50 to 150) plus 50; a read that failed leaves it
    Exponential[1][0] = 77; tap(0, 1, 0, 0, -50); CHECK(Exponential[1][0] == 0);
    tap(0, 1, 0, 0, 0); CHECK(Exponential[1][0] == 50);
    tap(0, 1, 0, 0, 150); CHECK(Exponential[1][0] == 200);
    tap(0, 1, 0, 0, -14); CHECK(Exponential[1][0] == 36);
    values.clear(); values["Lines"] = 1; InterpolationTypes[1][0] = 0; Exrite(); CHECK(Exponential[1][0] == 36);
    // 7. every tap redraws the curve (and so the switches, updateInterpolationTypes) and lets the screen's text go
    const int d = drawn, c = cleared; tap(0, 0, 1, 0); CHECK(drawn == d + 1 && cleared == c + 1);
    // 8. the bank and channel being set, no other
    InterpolationTypes[1][0] = 0; Exponential[1][0] = 36; Bank = 3; ChanneltoSet = 7; Exponential[3][6] = 0;
    CHECK(tap(0, 0, 1, 0, 10) == 1 && Exponential[3][6] == 60 && InterpolationTypes[1][0] == 0 && Exponential[1][0] == 36);
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = PROGRAM.replace('@TYPES@', types).replace('@BODY@', body)
with tempfile.TemporaryDirectory() as d:
    cpp = os.path.join(d, 't.cpp'); exe = os.path.join(d, 't')
    open(cpp, 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-o', exe, cpp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode:
        print(r.stdout); sys.exit('the lifted block does not compile')
    r = subprocess.run([exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout.strip())
    check(r.returncode == 0, 'the Exrite block')

# ---------------------------------------------------------------- the main board, as source
check(all(('GetValue(%s) == 1' % n) in body for n in ('Lines', 'Smooth', 'ExpR')), 'a switch is on only when it reads 1 (65535 is a read that failed)')
check('if (Ex != 65535)' in body, 'a failed read of the expo leaves it')
check(int(re.search(r'#define TXVERSION_EXTRA "B(\d+)', defs).group(1)) >= 115, 'B115 or later')

# ---------------------------------------------------------------- the screen: a switch changes as the finger lands, then its press event runs
sm = open(os.path.join(SCREEN, 'src', 'main.cpp'), encoding='utf-8', errors='replace').read()
ver = re.search(r'#define SCREEN_VERSION "(\d+)\.(\d+)\.(\d+)"', sm)
check(ver is not None and tuple(int(x) for x in ver.groups()) >= (1, 11, 81), 'screen 1.11.81 or later')
i = sm.index('down = true; held = hit(x[0], y[0]);')
j = sm.index('} else if (up) {', i)
press = sm[i:j]
flip = 'if (flips) c.val = c.type == "radio" ? 1 : !c.val;'
check('const bool flips = c.type == "dual-state button" || c.type == "checkbox" || c.type == "switch" || c.type == "radio";' in press, 'the four kinds that change under the finger')
check(flip in press and press.index(flip) < press.index('runScript(c.evPress, c.name);'), 'the change comes BEFORE the press event runs')
check(flip in press and press.index(flip) < press.index('redraw(c);') and '|| flips) redraw(c);' in press, 'drawn as it lands')
k = sm.index('runScript(evRel, nm);', j)
lift_ = sm[j:k]
check('c.val = !c.val' not in lift_ and 'c.val = 1;' not in lift_, 'nothing changes again at the lift')
check('keepTouched(c);' in lift_, "the value kept at the lift (the page comes back with it)")
check('if (press && (c->type == "dual-state button" || c->type == "checkbox" || c->type == "switch" || c->type == "radio")) { c->val = c->type == "radio" ? 1 : !c->val;' in sm, "the main board's click: as a finger, at the press")
check('c->type == "dual-state button" && !press' not in sm, 'no flip at a click release')

# ---------------------------------------------------------------- page 21: its switches clear the other two in their press event, the lift tells the main board
p21 = json.load(open(os.path.join(SCREEN, 'sd', 'hmi', 'pages', '21.json')))
by = {c['n']: c for c in p21['comps']}
for n, (a, b) in (('Lines', ('Smooth', 'Exp')), ('Smooth', ('Lines', 'Exp')), ('Exp', ('Lines', 'Smooth'))):
    c = by.get(n); ev = (c or {}).get('ev', {})
    check(c is not None and c['t'] == 'switch' and ev.get('p') == 'if(%s.val==1)\n{\n  %s.val=0\n  %s.val=0\n}' % (n, a, b) and ev.get('r') == 'print "Exrite"', '%s: on, the other two off, then Exrite' % n)
# every press event that reads its own value sees the NEW value since 1.11.81: these are the ones that do (a new one wants a look)
found = set()
for f in os.listdir(os.path.join(SCREEN, 'sd', 'hmi', 'pages')):
    if not f.endswith('.json'): continue
    pg = json.load(open(os.path.join(SCREEN, 'sd', 'hmi', 'pages', f)))
    for c in pg.get('comps', []):
        if c.get('t') in ('switch', 'dual-state button', 'checkbox', 'radio') and (c['n'] + '.val') in ((c.get('ev') or {}).get('p') or ''):
            found.add((int(f[:-5]), c['n']))
known = {(13, 'fm1'), (13, 'fm2'), (13, 'fm3'), (13, 'fm4'), (21, 'Lines'), (21, 'Smooth'), (21, 'Exp')}
check(found == known, 'the press events that read their own value: %s' % sorted(found ^ known))

print('%d source checks, %d failed' % (checks, fails))
sys.exit(1 if fails else 0)
