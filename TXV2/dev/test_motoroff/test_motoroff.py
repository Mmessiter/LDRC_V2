#!/usr/bin/env python3
"""Host test of B129 (Malcolm, 19 Oct 2026: "the value which is usually attributed to motor off of -67 is not in helpful
units! ... change this to microseconds"). MotorOffMicros and MotorOffFromMicros are lifted out of Utilities.h with
IntoHigherRes and run on the Mac with the Teensy's rounding map: the byte 0..180 is 500..2500 microseconds (-67 was 30 =
833), every byte comes back from its microseconds unchanged, and anything typed outside 500..2500 lands on an end. Then
the Model options page as source: it sends microseconds and reads them back, a comms error keeps the old byte; the screen's
page says microseconds; the help too.
   python3 dev/test_motoroff/test_motoroff.py"""
import json, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
util = src('include/Utilities.h'); menu = src('include/MenuOptions.h'); defs1 = src('include/1Definitions.h')
DEFS = '\n'.join(l for l in defs1.split('\n') if re.match(r'#define (MINMICROS|MAXMICROS) ', l)) + '\n'
assert DEFS.count('#define') == 2, DEFS
FUNCS = '\n'.join(l for l in util.split('\n') if re.match(r'(uint16_t IntoHigherRes\(uint8_t LowRes\)|uint16_t MotorOffMicros\(\)|uint8_t MotorOffFromMicros\(int32_t us\))', l))
i = util.index('uint16_t IntoHigherRes(uint8_t LowRes)'); IHR = util[i:util.index('\n}\n', i) + 3]
PROG = r'''
#include <cstdio>
#include <cstdint>
#include <type_traits>
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
''' + DEFS + 'static uint8_t MotorChannelZero = 30;\n' + IHR + '\n'.join(l for l in util.split('\n') if l.startswith('uint16_t MotorOffMicros()') or l.startswith('uint8_t MotorOffFromMicros(int32_t us)')) + r'''
int main() {
    MotorChannelZero = 30; CHECK(MotorOffMicros() == 833);          // the old -67
    MotorChannelZero = 15; CHECK(MotorOffMicros() == 667);          // the Havok's -83
    MotorChannelZero = 0; CHECK(MotorOffMicros() == 500);
    MotorChannelZero = 180; CHECK(MotorOffMicros() == 2500);
    CHECK(MotorOffFromMicros(833) == 30 && MotorOffFromMicros(667) == 15 && MotorOffFromMicros(500) == 0 && MotorOffFromMicros(2500) == 180);
    for (int d = 0; d <= 180; ++d) { MotorChannelZero = (uint8_t) d; CHECK(MotorOffFromMicros(MotorOffMicros()) == d); }   // every byte comes back
    CHECK(MotorOffFromMicros(-67) == 0 && MotorOffFromMicros(0) == 0 && MotorOffFromMicros(499) == 0);              // the old units typed by habit: the low end, never full throttle
    CHECK(MotorOffFromMicros(2501) == 180 && MotorOffFromMicros(9999) == 180);
    CHECK(MotorOffFromMicros(1000) == 45 && MotorOffFromMicros(1500) == 90 && MotorOffFromMicros(2000) == 135);
    printf("test_motoroff: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 't.cpp'), 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-Wall', '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    bad = r.returncode != 0
fl = 0; flfail = False
def check(ok, what):
    global fl, flfail
    fl += 1
    if not ok: flfail = True; print('FAIL:', what)
check('SendValue(Mvalue, MotorOffMicros());' in menu, 'the page shows microseconds')
check('MotorChannelZero = MotorOffFromMicros(mv);' in menu and 'if (mv != 65535)' in menu and 'map(constrain(mv, -100, 100)' not in menu, 'the page reads microseconds back; a comms error keeps the old byte')
help_t = open(os.path.join(ROOT, 'Help files for SD', 'RXSETUP1.TXT')).read()
check('microseconds' in help_t and '833 is the default' in help_t and '-67 is the default' not in help_t, 'RXSETUP1.TXT says microseconds and 833')
P = os.path.join(ROOT, '..', 'ESP32-board2', 'board4', 'nextion-emulator', 'sd', 'hmi', 'pages', '9.json')
if os.path.exists(P):
    pg = json.load(open(P)); by = {c['n']: c for c in pg['comps']}
    check(pg['name'] == 'RXOptionsView' and by['t5']['txt'] == 'Motor off, us (usually 833)' and by['n0']['t'] == 'number', "page 9: the label says us and 833 (the longer words were cut at the column's end), the box is n0")
else:
    print('(ESP32-board2 is not here: the page not checked)')
print('flow and page: %d checks%s' % (fl, ', FAILED' if flfail else ''))
sys.exit(1 if (bad or flfail) else 0)
