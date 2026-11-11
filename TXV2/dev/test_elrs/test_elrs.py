#!/usr/bin/env python3
"""Host test of the ELRS module's CRSF code (ElrsCrsf.h, phase 1: the bench test; Malcolm, 11 Nov 2026: "My vote is for
ELRS, internally, switchable, and by serial link"). The block between ELRS-CRSF-BEGIN/END is lifted out and compiled on
the Mac; every frame it builds is checked against an independent packer written here in Python, and every frame it must
read is built here in Python - so the two sides cannot share a mistake. Then main.cpp is read: the driver runs only in
test builds (-DELRS_TEST), so a release is not changed by any of this.
   python3 dev/test_elrs/test_elrs.py"""
import os, random, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
hdr = src('include/ElrsCrsf.h')
i = hdr.index('// ELRS-CRSF-BEGIN'); j = hdr.index('// ELRS-CRSF-END')
BLOCK = hdr[i:j]

# ---------------------------------------------------------------- the Python side: independent of the C++
def crc8(data):
    c = 0
    for x in data:
        c ^= x
        for _ in range(8):
            c = ((c << 1) ^ 0xD5) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c
def ticks(us):   # the receiver's rc11bit, in Python (C++ division truncates toward zero)
    num = (us - 1500) * 819
    q = abs(num) // 500
    v = (q if num >= 0 else -q) + 992
    return max(172, min(1811, v))
def rc_frame(us):
    bits = 0
    for c, u in enumerate(us): bits |= (ticks(u) & 0x7FF) << (11 * c)
    payload = bits.to_bytes(22, 'little')
    body = bytes([0x16]) + payload
    return bytes([0xEE, 24]) + body + bytes([crc8(body)])
def frame(start, ftype, payload):
    body = bytes([ftype]) + bytes(payload)
    return bytes([start, len(body) + 1]) + body + bytes([crc8(body)])
def be(v, n): return (v & ((1 << (8 * n)) - 1)).to_bytes(n, 'big')

random.seed(11112026)
cases = []
for _ in range(200): cases.append([random.randint(400, 2600) for _ in range(16)])
cases.insert(0, [1500] * 16)
cases.insert(1, [500, 2500, 988, 2012, 1000, 2000, 1499, 1501] * 2)

link = frame(0xC8, 0x14, [45, 52, 98, 9, 1, 7, 3, 61, 100, 7])
batt = frame(0xC8, 0x08, list(be(81, 2) + be(123, 2) + be(1350, 3)) + [77])
rpm = frame(0xC8, 0x0C, [1] + list(be(1850, 3)) + list(be(-5, 3)))
rpm_neg = frame(0xC8, 0x0C, [1] + list(be(-1234, 3)))
temp = frame(0xC8, 0x0D, [0] + list(be(-123, 2)))
mode = frame(0xC8, 0x21, list(b'ANGLE\0'))
longmode = frame(0xC8, 0x21, list(b'A_VERY_LONG_FLIGHT_MODE_NAME\0'))
att = frame(0xC8, 0x1E, list(be(-100, 2) + be(200, 2) + be(-300, 2)))
timing = frame(0xC8, 0x3A, [0xEA, 0xEE, 0x10] + list(be(40000, 4)) + list(be(-1234, 4)))      # 4 ms, -123.4 us
timing_bad_sub = frame(0xC8, 0x3A, [0xEA, 0xEE, 0x11] + list(be(20000, 4)) + list(be(0, 4)))
timing_silly = frame(0xC8, 0x3A, [0xEA, 0xEE, 0x10] + list(be(3000000, 4)) + list(be(0, 4)))  # 300 ms: not believed
unknown = frame(0xEA, 0x29, [1, 2, 3])
bad = bytearray(link); bad[-1] ^= 0x55

def carr(b): return '{' + ','.join(str(x) for x in b) + '}'
PROG = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
''' + BLOCK + r'''
using namespace ElrsCrsf;
static void feedAll(Parser &p, Telemetry &t, const uint8_t *b, unsigned n, uint32_t now) { for (unsigned i = 0; i < n; ++i) p.feed(b[i], t, now); }
int main() {
    // the CRC: CRC-8/DVB-S2's published check value, "123456789" -> 0xBC
    CHECK(crc8((const uint8_t *)"123456789", 9) == 0xBC);
    // the conversion: the receiver's own figures
    CHECK(usToTicks(1500) == 992); CHECK(usToTicks(1000) == 173); CHECK(usToTicks(2000) == 1811);
    CHECK(usToTicks(500) == 172); CHECK(usToTicks(2500) == 1811); CHECK(usToTicks(988) == 172); CHECK(usToTicks(0) == 172);
    // channel frames: byte for byte as the Python packer has them
    static const uint16_t cases[][16] = {''' + ','.join(carr(c) for c in cases) + r'''};
    static const uint8_t want[][26] = {''' + ','.join(carr(rc_frame(c)) for c in cases) + r'''};
    int same = 0;
    for (unsigned k = 0; k < sizeof(cases) / sizeof(cases[0]); ++k) {
        uint8_t f[RC_FRAME_LEN]; buildRcFrame(cases[k], f);
        if (!memcmp(f, want[k], RC_FRAME_LEN)) ++same;
    }
    CHECK(same == (int)(sizeof(cases) / sizeof(cases[0])));
    printf("PASS %d channel frames byte for byte as an independent packer builds them\n", same);
    // the module's frames, built in Python
    static const uint8_t link[] = ''' + carr(link) + r''', batt[] = ''' + carr(batt) + r''', rpm[] = ''' + carr(rpm) + r''', rpmneg[] = ''' + carr(rpm_neg) + r''',
        temp[] = ''' + carr(temp) + r''', mode[] = ''' + carr(mode) + r''', longmode[] = ''' + carr(longmode) + r''', att[] = ''' + carr(att) + r''',
        timing[] = ''' + carr(timing) + r''', timingBadSub[] = ''' + carr(timing_bad_sub) + r''', timingSilly[] = ''' + carr(timing_silly) + r''',
        unknown[] = ''' + carr(unknown) + r''', bad[] = ''' + carr(bad) + r''';
    {   Parser p; Telemetry t;
        feedAll(p, t, link, sizeof link, 1000);
        CHECK(t.framesOk == 1 && t.linkMs == 1000);
        CHECK(t.upRssi1 == -45 && t.upRssi2 == -52 && t.upLq == 98 && t.upSnr == 9 && t.antenna == 1 && t.rfMode == 7 && t.txPower == 3);
        CHECK(t.downRssi == -61 && t.downLq == 100 && t.downSnr == 7);
        printf("PASS link statistics: LQ 98%%, RSSI -45/-52 dBm, power code 3 (100 mW), down -61 dBm 100%%\n"); }
    {   Parser p; Telemetry t;
        feedAll(p, t, batt, sizeof batt, 5); feedAll(p, t, rpm, sizeof rpm, 6); feedAll(p, t, temp, sizeof temp, 7);
        feedAll(p, t, mode, sizeof mode, 8); feedAll(p, t, att, sizeof att, 9);
        CHECK(t.battDeciVolts == 81 && t.battDeciAmps == 123 && t.battMah == 1350 && t.battPct == 77 && t.battMs == 5);
        CHECK(t.rpm == 1850 && t.rpmMs == 6);
        CHECK(t.tempDeciC == -123 && t.tempMs == 7);
        CHECK(!strcmp(t.flightMode, "ANGLE"));
        CHECK(t.pitch == -100 && t.roll == 200 && t.yaw == -300);
        CHECK(t.framesOk == 5 && t.badCrc == 0);
        feedAll(p, t, rpmneg, sizeof rpmneg, 10); CHECK(t.rpm == -1234);
        feedAll(p, t, longmode, sizeof longmode, 11); CHECK(strlen(t.flightMode) == 15 && !strncmp(t.flightMode, "A_VERY_LONG_FLI", 15));
        printf("PASS battery 8.1 V 12.3 A 1350 mAh 77%%, rpm 1850 (and -1234), -12.3 C, ANGLE, attitude, a long mode name cut to 15\n"); }
    {   Parser p; Telemetry t;
        feedAll(p, t, timing, sizeof timing, 2000);
        CHECK(t.intervalTenthsUs == 40000 && t.offsetTenthsUs == -1234 && t.timingMs == 2000);
        CHECK(sendPeriodUs(t, 2500) == 4000);                 // the module's 4 ms
        CHECK(sendPeriodUs(t, 2000 + 999) == 4000);
        CHECK(sendPeriodUs(t, 2000 + 1000) == DEFAULT_PERIOD_US);   // stale after a second: the default
        Telemetry u; CHECK(sendPeriodUs(u, 5) == DEFAULT_PERIOD_US);   // never told: the default
        Parser q; Telemetry v; feedAll(q, v, timingBadSub, sizeof timingBadSub, 3000);
        CHECK(v.timingMs == 0 && v.framesOk == 1);            // another subcommand: not our timing
        Parser r; Telemetry w; feedAll(r, w, timingSilly, sizeof timingSilly, 4000);
        CHECK(w.timingMs == 4000 && sendPeriodUs(w, 4001) == DEFAULT_PERIOD_US);   // 300 ms: not believed
        printf("PASS timing: 4 ms and -123.4 us read; stale, missing or silly intervals fall back to 4 ms\n"); }
    {   Parser p; Telemetry t;
        // noise, a frame cut in two, a bad CRC, an impossible length, then a good frame - one byte at a time
        static const uint8_t noise[] = {0x00, 0xFF, 0x13, 0x37};
        feedAll(p, t, noise, sizeof noise, 1);
        feedAll(p, t, link, 7, 2); feedAll(p, t, link + 7, sizeof link - 7, 3);
        CHECK(t.framesOk == 1 && t.linkMs == 3);
        feedAll(p, t, bad, sizeof bad, 4);
        CHECK(t.badCrc == 1 && t.framesOk == 1 && t.linkMs == 3);
        static const uint8_t badLen[] = {0xC8, 63};
        feedAll(p, t, badLen, sizeof badLen, 5); CHECK(t.badLength == 1);
        static const uint8_t badLen2[] = {0xC8, 1};
        feedAll(p, t, badLen2, sizeof badLen2, 5); CHECK(t.badLength == 2);
        feedAll(p, t, unknown, sizeof unknown, 6); CHECK(t.framesOk == 2 && t.unknownType == 1);
        feedAll(p, t, batt, sizeof batt, 7); CHECK(t.framesOk == 3 && t.battMs == 7);
        printf("PASS a stream: noise skipped, a frame in two pieces, a bad CRC and impossible lengths refused, frames after them read\n"); }
    {   // our own frames, read back by the same parser (as the module's would read them: start 0xEE, the CRC)
        Parser p; Telemetry t; uint8_t f[RC_FRAME_LEN]; const uint16_t us[16] = {1500,1500,1500,1500,1000,2000,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500};
        buildRcFrame(us, f); feedAll(p, t, f, sizeof f, 1);
        CHECK(t.framesOk == 1 && t.badCrc == 0 && t.badLength == 0);   // (a channel frame is not one the handset decodes: unknownType counts it)
        printf("PASS our channel frame is a whole, good CRSF frame\n"); }
    printf("%d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
problems = []
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 't.cpp'), 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-fsanitize=address,undefined',
                        '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[:4000]); print('FAILED to compile'); sys.exit(1)
    r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    if r.returncode: problems.append('the host checks failed')
# the driver only in test builds; releases untouched
main = src('src/main.cpp')
if not re.search(r'#ifdef ELRS_TEST\s*\n\s*#include "ElrsCrsf.h"', main): problems.append('main.cpp: ElrsCrsf.h must be included only under #ifdef ELRS_TEST')
if not re.search(r'#ifdef ELRS_TEST\s*\n\s*if \(CurrentMode == NORMAL\)\s*\n\s*ElrsTestTick\(\);', main): problems.append('main.cpp: ElrsTestTick() must run only under #ifdef ELRS_TEST, in NORMAL mode')
if 'ElrsTestTick' in hdr[:i] or 'Serial6' in BLOCK: problems.append('ElrsCrsf.h: the hardware must stay outside the tested block')
if '#ifdef ELRS_TEST' not in hdr[j:]: problems.append('ElrsCrsf.h: the driver must be under #ifdef ELRS_TEST')
# EASILY REMOVED (Malcolm, 11 Nov 2026): every mention of ELRS outside ElrsCrsf.h sits inside #ifdef ELRS_TEST, so the
# whole thing comes out with this file, ElrsCrsf.h and those blocks. Each one is listed, and any other is a failure.
touch = []
for root, _, files in os.walk(TC):
    if os.sep + '.pio' in root: continue
    for fn in files:
        if not fn.endswith(('.h', '.cpp', '.ino', '.c')) or fn == 'ElrsCrsf.h': continue
        path = os.path.join(root, fn); lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
        depth = 0; guard = []
        for n, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith('#if'): guard.append('ELRS_TEST' in s)
            elif s.startswith('#endif') and guard: guard.pop()
            if re.search(r'elrs', line, re.I):
                rel = os.path.relpath(path, TC)
                if any(guard): touch.append(f'{rel}:{n}')
                else: problems.append(f'{rel}:{n} mentions ELRS outside #ifdef ELRS_TEST: {s[:80]}')
print('PASS the ELRS lines outside ElrsCrsf.h, all inside #ifdef ELRS_TEST:', ', '.join(touch) if touch else 'none')
if problems:
    for p in problems: print('FAIL', p)
    print('FAILED'); sys.exit(1)
print('PASS main.cpp: the driver is in test builds only (-DELRS_TEST); a release is unchanged')
print('ALL PASS')
