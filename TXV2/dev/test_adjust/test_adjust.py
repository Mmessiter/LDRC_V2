#!/usr/bin/env python3
"""Host test of the in-flight adjustments model (B72): include/RF_Adjust.h compiled on the Mac, against the phone page's
own model (RXV2 data/rotorflight-adjustments.html, lines <-> rows <-> lines) run in node on the same random sets: the
rows must agree in kind, setting, channel, positions and values; the lines written back must agree byte for byte; the
bank regions and each row's bank must agree. Then the transmitter's own rules: the Setting order, the step rounding.
   python3 dev/test_adjust/test_adjust.py"""
import json, os, random, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Adjust.h')
PAGE = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/RXV2/data/rotorflight-adjustments.html')
html = open(PAGE).read()
a = html.index('// ---------------- model'); b = html.index('// ---------------- page')
jsmodel = html[a:b]

# ---- the vectors: random line sets, some grouped switch positions, knobs, nudges, blanks, a bank line
random.seed(8)
def stepb(us): st = round((us - 1500) / 5); st = max(-125, min(125, st)); return st + 256 if st < 0 else st
def line(fn, ena, enaLo, enaHi, adj, a1Lo, a1Hi, a2Lo, a2Hi, mn, mx, stp):
    return [fn, ena, stepb(enaLo), stepb(enaHi), adj, stepb(a1Lo), stepb(a1Hi), stepb(a2Lo), stepb(a2Hi), mn & 255, mn >> 8, mx & 255, mx >> 8, stp]
def blank(): return line(0, 0, 1500, 1500, 0, 1500, 1500, 1500, 1500, 0, 0, 0)
def us5(lo, hi): return random.randrange(lo, hi + 1, 5)
vectors = []
for v in range(40):
    L = []
    # a bank line: the OLD form (one line per position, B74-B76 and the phone page before 0.9.879: applied once only) on AUX1
    # (ch 0) giving banks 1..3 or 1..4; Rotorflight's own form, a line 1..6 or 1..4 over a travel; or none
    kind = v % 5
    if kind == 0:
        for p, (lo, hi) in enumerate([(875, 1300), (1300, 1700), (1700, 2125)]): L.append(line(2, 0, lo, hi, 0, lo, hi, 1500, 1500, p + 1, p + 1, 0))
    elif kind == 1:
        L.append(line(2, 0, 875, 2125, 0, 875, 2125, 1500, 1500, 1, 6, 0))
    elif kind == 2:
        for p, (lo, hi) in enumerate([(875, 1040), (1040, 1290), (1290, 1735), (1735, 2125)]): L.append(line(2, 0, lo, hi, 0, lo, hi, 1500, 1500, p + 1, p + 1, 0))   # the test flight controller's, 8 Oct
    elif kind == 3:
        L.append(line(2, 0, 875, 2125, 0, 1060, 1845, 1500, 1500, 1, 4, 0))
    while len(L) < random.randrange(1, 40):
        fn = random.choice([14, 18, 22, 8, 48, 80, 33, 5])
        adj = random.randrange(1, 12)
        r = random.random()
        conds = [None, None, (3, 1000, 1200)]
        if kind == 0: conds += [(0, 875, 1300), (0, 1300, 1700), (0, 1700, 2125)]
        if kind == 2: conds += [(0, 875, 1040), (0, 1040, 1290), (0, 1290, 1735), (0, 1735, 2125)]
        if kind == 3: conds += [(0, 875, 1190), (0, 1190, 1455), (0, 1455, 1715), (0, 1715, 2125)]
        cond = random.choice(conds)
        if r < 0.25:   # a switch of the OLD form: 2 to 5 positions, one fixed value each, maybe held by a condition
            n = random.choice([2, 2, 3, 3, 4, 5]); t = sorted(set(us5(900, 2100) for _ in range(n - 1)))
            while len(t) < n - 1: t = sorted(set(t + [us5(900, 2100)]))
            edges = [875] + t + [2125]
            vals = [random.randrange(0, 300) for _ in range(n)]
            for p in range(n):
                lo, hi = edges[p], edges[p + 1]
                e = cond if cond else (adj, lo, hi)
                L.append(line(fn, e[0], e[1], e[2], adj, lo, hi, 1500, 1500, vals[p], vals[p], 0))
        elif r < 0.45:  # a switch of Rotorflight's own form: 2 to 6 whole numbers over a travel
            lo = us5(875, 1400); hi = us5(lo + 5, 2125); mn = random.randrange(0, 200); mx = mn + random.randrange(1, 6)
            e = cond if cond else (adj, 875, 2125)
            L.append(line(fn, e[0], e[1], e[2], adj, lo, hi, 1500, 1500, mn, mx, 0))
        elif r < 0.55:  # one fixed value on its own (a configurator line): kept as it is
            lo = us5(875, 1400); hi = us5(lo + 5, 2125); mn = random.randrange(0, 200)
            e = cond if cond else (adj, lo, hi)
            L.append(line(fn, e[0], e[1], e[2], adj, lo, hi, 1500, 1500, mn, mn, 0))
        elif r < 0.75:  # a knob
            lo = us5(875, 1400); hi = us5(lo + 5, 2125); mn = random.randrange(0, 200); mx = mn + random.randrange(6, 200)
            e = cond if cond else (adj, 875, 2125)
            L.append(line(fn, e[0], e[1], e[2], adj, lo, hi, 1500, 1500, mn, mx, 0))
        else:          # a nudge
            t0 = us5(900, 1400); t1 = us5(t0 + 5, 2100)
            e = cond if cond else (adj, 875, 2125)
            L.append(line(fn, e[0], e[1], e[2], adj, 875, t0, t1, 2125, random.randrange(0, 50), random.randrange(100, 300), random.randrange(1, 5)))
    L = L[:42]
    while len(L) < 42: L.append(blank())
    vectors.append(''.join('%02X' % x for l in L for x in l))

# ---- the phone page's answers
node = r'''
const LDRC = { BANKS_MAX: 6 };
''' + jsmodel + r'''
const hexToBytes = h => { const o = new Uint8Array(h.length / 2); for (let i = 0; i < o.length; i++) o[i] = parseInt(h.substr(i * 2, 2), 16); return o; };
const out = [];
for (const hex of JSON.parse(process.argv[2])) {
    const rows = linesToRows(parseLines(hexToBytes(hex)));
    const L = rowsToLines(rows);
    let back = ''; for (let i = 0; i < L.length; i++) back += Array.from(encodeLine(i, L[i]).slice(1), x => x.toString(16).padStart(2, '0').toUpperCase()).join('');
    const br = bankRegions(rows);
    out.push({ rows: rows.map(r => ({ kind: r.kind, fn: r.fn, ch: r.ch, t: r.t || [], values: r.values || [], n: r.n || 0, lo: r.lo, hi: r.hi, min: r.min, max: r.max, stp: r.stp || 0, legacy: r.legacy ? 1 : 0, bank: condToBank(r.cond, br) })),
               back, br: br ? { ch: br.ch, regions: br.regions } : null, problem: rowsProblem(rows, null) });
}
console.log(JSON.stringify(out));
'''
d = tempfile.mkdtemp(); js = os.path.join(d, 'm.js'); open(js, 'w').write(node)
r = subprocess.run(['node', js, json.dumps(vectors)], capture_output=True, text=True)
if r.returncode: print(r.stderr[:2000]); sys.exit(1)
expected = json.loads(r.stdout)

# ---- the transmitter's model on the same sets
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#define FLASHMEM
#define DMAMEM
#define PROGMEM
#include <cmath>
#include <string>
#include <vector>
''' + open(HDR).read().split('// ---------------------------------------------------------------- the page')[0].replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + '\n#endif\n' + r'''
static int checks = 0, fails = 0;
#define CHECK(c, what) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL vector %d: %s\n", vi, what); } } while (0)
static void hexToBytes(const char *h, uint8_t *o, int &n) { n = 0; while (h[0] && h[1]) { char t[3] = {h[0], h[1], 0}; o[n++] = (uint8_t) strtol(t, nullptr, 16); h += 2; } }
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "r"); char *buf = (char *) malloc(4000000); size_t len = fread(buf, 1, 4000000, f); buf[len] = 0; fclose(f);
    // one vector per line: hex | expected back hex | rows "kind,fn,ch,bank,n,t...,v..." ; | br "ch:lo1-hi1,..."
    int vi = 0; char *line = strtok(buf, "\n");
    while (line) {
        ++vi;
        char *hex = line, *back = strchr(line, '|'); *back++ = 0; char *rows = strchr(back, '|'); *rows++ = 0; char *br = strchr(rows, '|'); *br++ = 0; char *prob = strchr(br, '|'); *prob++ = 0;
        uint8_t b[600]; int n; hexToBytes(hex, b, n);
        AdjLine L[ADJ_MAX]; const int nl = AdjParseLines(b, n, L);
        AdjRow R[ADJ_MAX]; const int nr = AdjLinesToRows(L, nl, R);
        AdjLine W[ADJ_MAX]; AdjRowsToLines(R, nr, W);
        std::string out; char t[4];
        for (int i = 0; i < ADJ_MAX; ++i) { uint8_t e[15]; AdjEncodeLine(i, W[i], e); for (int k = 1; k < 15; ++k) { snprintf(t, sizeof t, "%02X", e[k]); out += t; } }
        CHECK(out == back, "the lines written back differ from the phone page's");
        if (out != back) { size_t d = 0; while (d < out.size() && d < strlen(back) && out[d] == back[d]) ++d; fprintf(stderr, "   line %zu: transmitter %s\n   line %zu: phone       %.28s\n", d / 28, out.substr(d / 28 * 28, 28).c_str(), d / 28, back + d / 28 * 28); }
        { char why[240]; CHECK(AdjRowsProblem(R, nr, why, sizeof(why)) == (prob[0] == '1'), "whether the rows can be saved differs from the phone page's"); }
        AdjBanks bk; AdjBankRegions(R, nr, bk);
        // rows
        int er = 0; char *p = rows;
        while (*p) {
            int kind, fn, ch, bank, cnt; int used = 0;
            if (sscanf(p, "%d,%d,%d,%d,%d%n", &kind, &fn, &ch, &bank, &cnt, &used) < 5) break;
            p += used;
            if (er < nr) {
                const AdjRow &r = R[er];
                CHECK(r.kind == kind && r.fn == fn && r.ch == ch, "a row's kind, setting or channel differs");
                if (kind != 2) CHECK(AdjCondToBank(r, bk) == bank, "a row's bank differs");   // (a nudge: the phone page shows no bank for it and keeps its enable as read; the transmitter reads the bank off that enable)
                else { int bb = AdjCondToBank(r, bk); CHECK(bb == 0 || (bk.have && r.ena == bk.ch), "a nudge's bank comes only from the bank channel"); }
                int vals[12]; int nv = 0; while (*p == ',' && nv < 12) { p++; vals[nv++] = atoi(p); while (*p && *p != ',' && *p != ';') ++p; }
                if (kind == 0) { CHECK(r.n == cnt, "a switch's positions differ"); CHECK(r.lo == vals[0] && r.hi == vals[1], "a switch's ends differ"); CHECK((r.legacy ? 1 : 0) == vals[2], "a switch's legacy flag differs"); bool same = true; for (int k = 0; k < cnt && k < ADJ_POS_MAX; ++k) if (r.v[k] != vals[3 + k]) same = false; CHECK(same, "a switch's values differ"); }
                else if (kind == 1) { CHECK(r.lo == vals[0] && r.hi == vals[1] && r.v[0] == vals[2] && r.v[1] == vals[3], "a knob's travel or values differ"); }
                else { CHECK(r.t[0] == vals[0] && r.t[1] == vals[1] && r.v[0] == vals[2] && r.v[1] == vals[3] && r.stp == vals[4], "a nudge differs"); }
            }
            ++er;
            if (*p == ';') ++p;
        }
        CHECK(er == nr, "the number of rows differs");
        // bank regions
        if (br[0] == '-') CHECK(!bk.have, "the phone finds no bank line, the transmitter does");
        else {
            int ch = atoi(br); CHECK(bk.have && bk.ch == ch, "the bank channel differs");
            char *q = strchr(br, ':'); if (q) { ++q; while (*q) { int v, lo, hi; int used = 0; if (sscanf(q, "%d=%d-%d%n", &v, &lo, &hi, &used) < 3) break; q += used; CHECK(v >= 1 && v <= 6 && bk.lo[v] == lo && bk.hi[v] == hi, "a bank's region differs"); if (*q == ',') ++q; } }
        }
        line = strtok(nullptr, "\n");
    }
    // the Setting order: rates and PIDs first, then the rest, wrapping both ways
    vi = 0;
    CHECK(AdjFnAt(0) == 5 && AdjFnAt(20) == 25 && AdjFnAt(21) == 3 && AdjFnAt(22) == 4 && AdjFnAt(23) == 26 && AdjFnAt(78) == 81 && AdjIdxOf(14) == 9 && AdjIdxOf(22) == 17 && AdjIdxOf(3) == 21 && AdjIdxOf(81) == 78, "the picker's order: rates and PIDs first, then the rest");
    CHECK(AdjStep(1500) == 0 && AdjStep(1505) == 1 && AdjStep(1495) == 255 && AdjStep(875) == 131 && AdjStep(2125) == 125 && AdjStep(1502) == 0 && AdjStep(1503) == 1 && AdjStep(1497) == 255 && AdjStep(1498) == 0, "the step rounding");
    CHECK(AdjUs(131) == 875 && AdjUs(125) == 2125 && AdjUs(0) == 1500, "steps to microseconds");
    // Rotorflight's even divisions (rc_adjustments.c): 4 banks over 988..2012 change at 1159, 1500 and 1841; Black Thunder 2's
    // channel 7 (1062, 1295, 1500, 1847 us) over its own ends 1062..1847 changes at 1193, 1455 and 1716 - each bank in its own zone
    { int t[6]; CHECK(AdjThresholds(988, 2012, 4, t) == 3 && t[0] == 1159 && t[1] == 1500 && t[2] == 1842, "the thresholds of 4 banks over 988..2012");
      CHECK(AdjThresholds(1062, 1847, 4, t) == 3 && t[0] == 1193 && t[1] == 1455 && t[2] == 1717, "the thresholds of 4 banks over 1062..1847");
      CHECK(AdjThresholds(988, 2012, 2, t) == 1 && t[0] == 1500, "two positions change half way");
      CHECK(AdjThresholds(1500, 1500, 3, t) == 0 && AdjThresholds(988, 2012, 1, t) == 0, "no thresholds without a travel or a second position"); }
    CHECK(AdjSwitchValue(40, 60, 3, 1) == 50 && AdjSwitchValue(1, 4, 4, 2) == 3 && AdjSwitchValue(0, 1, 2, 1) == 1 && AdjSwitchValue(10, 11, 3, 1) == 11 && AdjSwitchValue(7, 7, 1, 0) == 7, "the values between the ends");
    { int16_t lo, hi; int t2[1] = {1500}; AdjFitEnds(t2, 2, lo, hi); CHECK(lo == 1000 && hi == 2000, "two old positions divided at 1500: ends 1000..2000");
      int t3[1] = {1000}; AdjFitEnds(t3, 2, lo, hi); CHECK(lo == 875 && hi == 1125, "two old positions divided at 1000: ends as wide as the travel allows");
      int t4[3] = {1040, 1290, 1735}; AdjFitEnds(t4, 4, lo, hi); int tt[6]; AdjThresholds(lo, hi, 4, tt);
      CHECK(lo == 875 && hi == 1910 && tt[0] == 1048 && tt[1] == 1393 && tt[2] == 1738, "four old positions: the outer divisions nearly kept (the travel's floor moved one), the middle one evened between them"); }
    { uint8_t rfn; int off, by, side; CHECK(AdjValueSource(14, rfn, off, by, side) && rfn == 112 && off == 8 && by == 2 && side == 1, "Pitch P gain reads bytes 8-9 of the PIDs");
      CHECK(AdjValueSource(18, rfn, off, by, side) && rfn == 112 && off == 0, "Roll P gain reads bytes 0-1");
      CHECK(AdjValueSource(8, rfn, off, by, side) && rfn == 111 && off == 7 && side == 2, "Pitch Rate reads byte 7 of the rates");
      CHECK(AdjValueSource(80, rfn, off, by, side) && rfn == 148 && off == 0 && by == 2, "Governor headspeed reads bytes 0-1 of the governor profile");
      CHECK(!AdjValueSource(3, rfn, off, by, side), "no source for the Led profile"); }
    printf("test_adjust: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
lines = []
for hex, e in zip(vectors, expected):
    rows = []
    for r in e['rows']:
        kind = {'switch': 0, 'knob': 1, 'nudge': 2}[r['kind']]
        if kind == 0: vals = [r['lo'], r['hi'], r['legacy']] + list(r['values']); cnt = r['n']
        elif kind == 1: vals = [r['lo'], r['hi'], r['min'], r['max']]; cnt = 2
        else: vals = [r['t'][0], r['t'][1], r['min'], r['max'], r['stp']]; cnt = 2
        rows.append(','.join(str(x) for x in [kind, r['fn'], r['ch'], r['bank'], cnt] + vals))
    br = '-' if not e['br'] else '%d:%s' % (e['br']['ch'], ','.join('%s=%d-%d' % (v, lo, hi) for v, (lo, hi) in sorted(e['br']['regions'].items(), key=lambda kv: int(kv[0]))))
    lines.append('%s|%s|%s|%s|%d' % (hex, e['back'], ';'.join(rows), br, 1 if e['problem'] else 0))
vec = os.path.join(d, 'vectors.txt'); open(vec, 'w').write('\n'.join(lines) + '\n')
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't'), vec]).returncode)
