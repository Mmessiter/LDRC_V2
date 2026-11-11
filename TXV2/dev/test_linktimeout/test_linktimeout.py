#!/usr/bin/env python3
"""Host test of B208 (Malcolm, 11 Nov 2026: "let's put both timeouts to 3 seconds. A gap of over 3 seconds is very
unlikely and remains a problem. Under three seconds and recovery is immediate."). BOTH = the transmitter's
RED_LED_ON_TIME (the red LED, "disconnected", and - with the motor switch on - the box that stops it sending) and the
Version 2 receiver's hold (OUTPUT_FAILSAFE_MS: the last positions go on to the flight controller as live ones).
CheckGap is lifted out of transceiver.h and run on the Mac with a clock of its own: a gap of up to 3000 ms ends by
itself, with no red LED and so no box; one millisecond more and the model is called lost, once. The two timeouts are
EQUAL (the receiver's is read from its source when that is on this Mac): were this one the shorter, the transmitter
would stop sending while the model still flew on its held sticks and listened. And the help says three seconds.
   python3 dev/test_linktimeout/test_linktimeout.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
defs1 = src('include/1Definitions.h'); trx = src('include/transceiver.h')
m = re.search(r'^#define RED_LED_ON_TIME (\d+)\b', defs1, re.M)
assert m, 'RED_LED_ON_TIME not found in 1Definitions.h'
RED = int(m.group(1))
i = trx.index('void CheckGap()'); CHECKGAP = trx[i:trx.index('\n}\n', i) + 3]
assert 'RED_LED_ON_TIME' in CHECKGAP, 'CheckGap no longer compares with RED_LED_ON_TIME'
PROG = r'''
#include <cstdio>
#include <cstdint>
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
#define RED_LED_ON_TIME ''' + str(RED) + r'''
static uint32_t Clock = 0;
static uint32_t millis() { return Clock; }
static uint32_t GapStart = 0;
static bool GapStartedDisarmed = false, GapStartedUnlinked = false, RotorFlight_V = true, Armed = true, LedWasGreen = true, LedWasRed = false;
static uint8_t ArmingChannel = 5;
static int Reds = 0;
static void RedLedOn() { ++Reds; LedWasRed = true; LedWasGreen = false; }   // (as main.cpp's: the model is called lost)
''' + CHECKGAP + r'''
static void Fail(uint32_t at) { Clock = at; CheckGap(); }                // a packet that failed all its retries, at this time
static void Good() { GapStart = 0; }                                     // an acknowledged packet ends the gap (SuccessfulPacket)
int main() {
    // A gap of just under three seconds: packets fail every 5 ms, and the model is never called lost.
    const uint32_t T0 = 100000;
    for (uint32_t t = T0; t <= T0 + 3000; t += 5) Fail(t);
    CHECK(Reds == 0);                                   // 3000 ms exactly: not yet
    CHECK(!LedWasRed && LedWasGreen);
    CHECK(GapStart == T0);                              // the gap is counted from its FIRST failed packet
    Good();                                             // the link is back by itself: nothing was shown, nothing stopped
    CHECK(Reds == 0 && GapStart == 0);
    // The old two seconds would have called it lost here.
    for (uint32_t t = 200000; t <= 200000 + 2500; t += 5) Fail(t);
    CHECK(Reds == 0);
    Good();
    // Over three seconds: lost, once.
    for (uint32_t t = 300000; t <= 300000 + 3000; t += 5) Fail(t);
    CHECK(Reds == 0);
    Fail(300000 + 3001);
    CHECK(Reds == 1 && LedWasRed);
    for (uint32_t t = 300000 + 3005; t <= 300000 + 9000; t += 5) Fail(t);
    CHECK(Reds == 1);                                   // (the blinking LED is the main loop's, not this)
    // A gap begun before the clock wraps (49.7 days) is timed the same.
    LedWasRed = false; LedWasGreen = true; Reds = 0; GapStart = 0;
    const uint32_t W = 0xFFFFFC00u;                     // 1024 ms before the wrap
    Fail(W); Fail(W + 2999); CHECK(Reds == 0);
    Fail(W + 3000); CHECK(Reds == 0);
    Fail(W + 3001); CHECK(Reds == 1);
    printf("test_linktimeout: %d checks, %d failures\n", checks, fails);
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
n = 0; nf = 0
def check(ok, what):
    global n, nf
    n += 1
    if not ok: nf += 1; print('FAIL: ' + what, file=sys.stderr)
check(RED == 3000, f'RED_LED_ON_TIME is {RED}, not the 3000 Malcolm asked for')
# The receiver's hold, when its source is on this Mac (the public snapshot of it is next to this project's own).
RX = [os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/RXV2/src/1Defs.h'), os.path.join(os.path.dirname(ROOT), 'RXV2', 'src', '1Defs.h')]
rx = next((p for p in RX if os.path.exists(p)), None)
if rx:
    mm = re.search(r'^constexpr uint32_t OUTPUT_FAILSAFE_MS\s*=\s*(\d+);', open(rx, encoding='utf-8', errors='replace').read(), re.M)
    check(bool(mm), "the receiver's OUTPUT_FAILSAFE_MS was not found in " + rx)
    if mm: check(int(mm.group(1)) == RED, f"the receiver holds for {mm.group(1)} ms and the transmitter gives up at {RED} ms: the two must be equal")
else:
    print("  (the receiver's source is not on this computer: its hold was not compared)")
helpdir = os.path.join(ROOT, 'Help files for SD')
fs = open(os.path.join(helpdir, 'FAILSAFE.TXT'), encoding='utf-8', errors='replace').read()
fr = open(os.path.join(helpdir, 'FRONT.TXT'), encoding='utf-8', errors='replace').read()
check('under three seconds changes nothing' in fs and 'After about three seconds' in fs, 'FAILSAFE.TXT does not say three seconds')
check('hears nothing for about one and a half' not in fs, 'FAILSAFE.TXT still gives one and a half seconds as the rule')
check('(no answer from the model for three seconds)' in fr, 'FRONT.TXT does not say when a link counts as lost')
for name, text in (('FAILSAFE.TXT', fs), ('FRONT.TXT', fr)):
    long = [l for l in text.split('\n') if len(l) > 65]
    check(not long, f'{name}: a line is wider than the help page ({long[:1]})')
print(f'test_linktimeout (sources): {n} checks, {nf} failures')
sys.exit(1 if (bad or nf) else 0)
