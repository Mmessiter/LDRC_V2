#!/usr/bin/env python3
"""The receiver's dead-block checks (src/MspFc.h), lifted and compiled on the Mac: ratesBlockDead (0.9.909), pidBlockDead
and govProfileDead (0.9.912, the review the day after Mehul's RAW 420 took off with no aileron). A block that would leave an
axis with no response, a gain beyond Rotorflight's range, a head speed that is none or a max throttle that never spools is
refused by /api/msp (409) and by the transmitter's word path (TxParams.h applyWriteToScratch) alike.
   python3 dev/deadblock_test.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, 'src', 'MspFc.h'), encoding='utf-8', errors='replace').read()

def lift(head):
    i = SRC.find(head)
    if i < 0: raise SystemExit('cannot find ' + head)
    j = SRC.find('\n}\n', i)
    return SRC[i:j + 3]

PRE = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
'''
MAIN = r'''
static void w16(uint8_t* b, int o, unsigned v) { b[o] = (uint8_t)(v & 0xFF); b[o + 1] = (uint8_t)(v >> 8); }
static bool has(const char* s, const char* w) { return strstr(s, w) != nullptr; }
int main() {
    char why[48];
    // ---- PIDs: 17 words - P I D F per axis, boost x3, HSI x2
    uint8_t p[34]; memset(p, 0, sizeof p);
    const unsigned good[12] = { 50, 100, 20, 80,  50, 100, 20, 80,  80, 120, 40, 0 };   // a plausible tune: yaw F 0 is fine with P and I set
    for (int i = 0; i < 12; ++i) w16(p, i * 2, good[i]);
    CHECK(!pidBlockDead(p, 34, why, sizeof why));
    CHECK(!pidBlockDead(p, 24, why, sizeof why));                       // the shortest block Rotorflight reads
    CHECK(!pidBlockDead(p, 10, why, sizeof why));                       // too short to judge: the length rule refuses it elsewhere
    w16(p, 0, 0); w16(p, 2, 0); w16(p, 6, 0);                            // roll P I F 0
    CHECK(pidBlockDead(p, 34, why, sizeof why)); CHECK(has(why, "Roll P, I and F gains to 0"));
    for (int i = 0; i < 12; ++i) w16(p, i * 2, good[i]);
    w16(p, 8, 0); w16(p, 10, 0); w16(p, 14, 0);                          // pitch
    CHECK(pidBlockDead(p, 34, why, sizeof why)); CHECK(has(why, "Pitch"));
    for (int i = 0; i < 12; ++i) w16(p, i * 2, good[i]);
    w16(p, 16, 0); w16(p, 18, 0);                                        // yaw P I 0 (F already 0)
    CHECK(pidBlockDead(p, 34, why, sizeof why)); CHECK(has(why, "Yaw"));
    for (int i = 0; i < 12; ++i) w16(p, i * 2, good[i]);
    w16(p, 0, 0); w16(p, 2, 0);                                          // roll P I 0 but F 80: still a response
    CHECK(!pidBlockDead(p, 34, why, sizeof why));
    w16(p, 0, 65535);                                                    // a word from a reply that never came
    CHECK(pidBlockDead(p, 34, why, sizeof why)); CHECK(has(why, "Roll P gain to 65535"));
    w16(p, 0, 4095);                                                     // the same after the pipe's 12-bit mask
    CHECK(pidBlockDead(p, 34, why, sizeof why)); CHECK(has(why, "4095"));
    w16(p, 0, 1000); CHECK(!pidBlockDead(p, 34, why, sizeof why));      // Rotorflight's own maximum
    w16(p, 0, 1001); CHECK(pidBlockDead(p, 34, why, sizeof why));
    w16(p, 0, 50); w16(p, 22, 1001);                                     // yaw F beyond the range
    CHECK(pidBlockDead(p, 34, why, sizeof why)); CHECK(has(why, "Yaw F gain to 1001"));
    w16(p, 22, 0); w16(p, 24, 65535);                                    // boost words are not judged (0..255 on the page; Rotorflight keeps a byte)
    CHECK(!pidBlockDead(p, 34, why, sizeof why));

    // ---- governor profile: head speed u16, then gain P I D F tta_gain tta_limit yaw cyclic collective max_throttle, min_throttle ...
    uint8_t g[17]; memset(g, 0, sizeof g);
    w16(g, 0, 2100); g[2] = 50; g[3] = 40; g[4] = 50; g[5] = 0; g[6] = 100; g[12] = 100; g[13] = 10;
    CHECK(!govProfileDead(g, 17, why, sizeof why));
    CHECK(!govProfileDead(g, 13, why, sizeof why));
    CHECK(!govProfileDead(g, 12, why, sizeof why));                     // too short to judge
    w16(g, 0, 0);     CHECK(govProfileDead(g, 17, why, sizeof why)); CHECK(has(why, "head speed to 0"));
    w16(g, 0, 65535); CHECK(govProfileDead(g, 17, why, sizeof why)); CHECK(has(why, "head speed to 65535"));
    w16(g, 0, 99);    CHECK(govProfileDead(g, 17, why, sizeof why));
    w16(g, 0, 100);   CHECK(!govProfileDead(g, 17, why, sizeof why));
    w16(g, 0, 50000); CHECK(!govProfileDead(g, 17, why, sizeof why));
    w16(g, 0, 50001); CHECK(govProfileDead(g, 17, why, sizeof why));
    w16(g, 0, 2100); g[12] = 0;   CHECK(govProfileDead(g, 17, why, sizeof why)); CHECK(has(why, "max throttle to 0"));
    g[12] = 9;   CHECK(govProfileDead(g, 17, why, sizeof why));
    g[12] = 10;  CHECK(!govProfileDead(g, 17, why, sizeof why));
    g[12] = 255; CHECK(!govProfileDead(g, 17, why, sizeof why));         // 255 from a missed reply: the transmitter refuses that itself (B156); here it is a number

    // ---- rates (0.9.909) still as it was
    uint8_t r[37]; memset(r, 0, sizeof r); r[0] = 6;
    for (int a = 0; a < 4; ++a) { r[1 + 6 * a] = 50; r[2 + 6 * a] = 40; r[3 + 6 * a] = 12; }
    CHECK(!ratesBlockDead(r, 37, why, sizeof why));
    r[1] = 0; CHECK(ratesBlockDead(r, 37, why, sizeof why)); CHECK(has(why, "Roll rate to 0"));

    printf("deadblock_test: %d checks, %d failed\n", checks, fails);
    if (fails == 0) printf("ALL PASS\n");
    return fails ? 1 : 0;
}
'''

def main():
    body = lift('inline bool ratesBlockDead(') + lift('inline bool pidBlockDead(') + lift('inline bool govProfileDead(')
    d = tempfile.mkdtemp()
    cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(PRE + body + MAIN)
    r = subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wno-unused-function', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-3000:] + '\ncompile failed')
    return subprocess.run([os.path.join(d, 't')]).returncode

if __name__ == '__main__': sys.exit(main())
