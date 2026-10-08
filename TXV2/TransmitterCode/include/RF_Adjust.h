// B72: IN-FLIGHT ADJUSTMENTS (the configurator's Adjustments tab) on the transmitter, over the Bluetooth pipe, WITH THE
// USB-C CABLE from the receiver to the flight controller (Malcolm, 8 Oct 2026: "is it possible to add in those functions
// which require the USB connection? ... We can have a USB cable connecting to the flight controller! We don't have to
// live without it"). Rotorflight 4.6 cannot send its adjustments list (MSP 52, 42 lines of 14 bytes = 588 bytes) over
// the receiver's CRSF link - the reply overflows the flight controller's 320-byte buffer and wipes its telemetry setup -
// so the receiver refuses 52 unless its USB line to the flight controller is open; over the cable it is the
// configurator's own channel. The pipe carries 52's reply whole (1176 hex characters of the 1500 the screen relays).
//
// THE MODEL is the phone page's (RXV2 data/rotorflight-adjustments.html, "DOM-free, unit-tested"), ported line for line:
// a LINE is Rotorflight's own record (function, enable channel and range, adjustment channel, two ranges, min, max,
// step; positions in microseconds, stored as signed 5 us steps around 1500); a ROW is what the pilot sees - a KNOB (its
// travel lo..hi mapped to min..max), a SWITCH (B83: ONE line too - its ends lo..hi mapped evenly onto the first and last
// values, as Rotorflight does; one line per position was applied once only), or a NUDGE (step up above a divider, down
// below another). A row may hold only in one BANK: the condition
// on the channel the PID-bank line uses, as that line divides it. Lines <-> rows round-trip byte for byte (tested on
// the Mac: dev/test_adjust). Values of the three "top rotation speed (Rate)" settings are shown x5 (Rotorflight stores
// them /5 for the rates type the Rates page uses; x10 for the older types), as the phone page shows them.
//
// THE PAGE (screen card page 67 AdjustView, hmi/adjust_pages.py): one adjustment at a time - Setting (< >), Channel
// (< >), Kind (Knob / Switch, 2 positions / Switch, 3 positions / Step up and down), In bank (Any / 1..6), then the
// values the kind needs, "Now" (the setting's present value in the bank in use, read when a row is added or its
// setting changed), and the channel's live position from this transmitter's own output. Save writes all 42 lines
// (53, one each, 503/504 answered again up to five times), stores (250), reads back (52) and compares.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_ADJUST_H
#define RF_ADJUST_H

static const int ADJ_MAX = 42;
static const int ADJ_RMIN = 875, ADJ_RMAX = 2125;
static const int ADJ_NAMES = 82;
// Rotorflight's adjustment functions, 0..81, as the configurator names them (the phone page's LABELS)
static const char *const AdjNames[ADJ_NAMES] PROGMEM = {
    "(nothing)", "Rates bank switch (1 to 6)", "PID bank switch (1 to 6)", "Led profile", "Battery profile",
    "Pitch rate curve shape (Shape)", "Roll rate curve shape (Shape)", "Yaw rate curve shape (Shape)",
    "Pitch top rotation speed (Rate)", "Roll top rotation speed (Rate)", "Yaw top rotation speed (Rate)",
    "Pitch expo", "Roll expo", "Yaw expo",
    "Pitch P gain", "Pitch I gain", "Pitch D gain", "Pitch F gain", "Roll P gain", "Roll I gain", "Roll D gain", "Roll F gain",
    "Yaw P gain", "Yaw I gain", "Yaw D gain", "Yaw F gain", "Yaw clockwise gain", "Yaw anticlockwise gain",
    "Yaw cyclic feedforward", "Yaw collective feedforward", "Yaw collective dynamic", "Yaw collective decay", "Pitch collective feedforward",
    "Pitch gyro cutoff", "Roll gyro cutoff", "Yaw gyro cutoff", "Pitch d-term cutoff", "Roll d-term cutoff", "Yaw d-term cutoff",
    "Rescue climb collective", "Rescue hover collective", "Rescue hover altitude", "Rescue altitude P gain", "Rescue altitude I gain", "Rescue altitude D gain",
    "Angle level gain", "Horizon level gain", "Acro trainer gain",
    "Governor gain", "Governor P gain", "Governor I gain", "Governor D gain", "Governor F gain", "Governor tail torque assist gain",
    "Governor cyclic feedforward", "Governor collective feedforward",
    "Pitch B gain", "Roll B gain", "Yaw B gain", "Pitch O gain", "Roll O gain",
    "Cross coupling gain", "Cross coupling ratio", "Cross coupling cutoff", "Level trim pitch", "Level trim roll",
    "Inertia precomp gain", "Inertia precomp cutoff",
    "Pitch setpoint boost gain", "Roll setpoint boost gain", "Yaw setpoint boost gain", "Collective setpoint boost gain",
    "Yaw dynamic ceiling gain", "Yaw dynamic deadband gain", "Yaw dynamic deadband filter", "Yaw precomp cutoff",
    "Governor idle throttle", "Governor auto throttle", "Governor max throttle", "Governor min throttle", "Governor headspeed", "Governor yaw feedforward"};
// The order the Setting steps through: rates and PIDs first (the phone page's BASIC set), then the rest
static const uint8_t ADJ_FIRST = 5, ADJ_LAST_BASIC = 25;
// The order the picker page lists them in (hmi/adjust_pages.py ORDER must agree): 5..25, then 3, 4, 26..81
FLASHMEM static const uint8_t *AdjOrder(int &n)
{
    static uint8_t seq[ADJ_NAMES];
    static int cnt = 0;
    if (!cnt) { for (int f = ADJ_FIRST; f <= ADJ_LAST_BASIC; ++f) seq[cnt++] = (uint8_t)f; seq[cnt++] = 3; seq[cnt++] = 4; for (int f = ADJ_LAST_BASIC + 1; f < ADJ_NAMES; ++f) seq[cnt++] = (uint8_t)f; }
    n = cnt;
    return seq;
}
FLASHMEM static int AdjIdxOf(uint8_t fn) { int n; const uint8_t *seq = AdjOrder(n); for (int i = 0; i < n; ++i) if (seq[i] == fn) return i; return 0; }
FLASHMEM static uint8_t AdjFnAt(int idx) { int n; const uint8_t *seq = AdjOrder(n); return (idx >= 0 && idx < n) ? seq[idx] : seq[0]; }

struct AdjLine { uint8_t fn, ena, adj, stp; int16_t enaLo, enaHi, a1Lo, a1Hi, a2Lo, a2Hi; uint16_t min, max; };
enum { AK_SWITCH = 0, AK_KNOB = 1, AK_NUDGE = 2 };
static const int ADJ_POS_MAX = 6;   // positions a switch row may hold
// B83: ONE Rotorflight line per switch. A line whose value is a single number ("set 3 when the switch is here") is applied
// ONCE: rc_adjustments.c (4.6.0) keeps the value each line last applied and applies again only when the value the channel
// maps to differs - a fixed value never differs - until the flight controller reboots or saves. So a switch made of one
// such line per position (B74-B76 wrote the bank switch that way) worked the first time each position was visited and
// then jammed (Malcolm, 8 Oct: "the first three bank changes work, after that nothing changes"; the receiver's log showed
// it had done nothing). Rotorflight's own switch is one line: the travel lo..hi mapped evenly onto the values
// first..last, rounded to whole numbers, which fires at every change. A switch row is now that one line: its ENDS lo/hi
// (the switch's first and last positions), its first and last values, the positions between evenly spaced. Lines of the
// old form are gathered into a row (legacy) with the ends fitted to the old dividers, to be saved in the new form.
struct AdjRow
{
    uint8_t kind, fn, ch;          // ch: Rotorflight's AUX index 0.. (channel = ch + 6)
    uint8_t n;                     // switch: positions (v[0..n-1] the values, the ends lo/hi); nudge: 2 dividers in t
    int16_t t[ADJ_POS_MAX];        // nudge: dividers [us]; switch/knob: unused
    int32_t v[ADJ_POS_MAX];        // switch: the value of each position (the ends as given, the rest evenly between); knob/nudge: v[0] min, v[1] max
    int16_t lo, hi;                // switch/knob: the travel that maps to the values
    uint8_t stp;                   // nudge: the step
    bool cond;                     // held by a condition (ena/enaLo/enaHi) rather than its own position
    uint8_t ena; int16_t enaLo, enaHi;
    bool legacy;                   // read in the old one-line-per-position form: to be saved in the new
};
static inline int AdjUs(uint8_t b) { return 1500 + 5 * (b > 127 ? (int)b - 256 : (int)b); }
FLASHMEM static inline uint8_t AdjStep(int us) // microseconds -> Rotorflight's signed 5 us step (rounded as Math.round: half up)
{
    int st = (int)floorf((float)(us - 1500) / 5.0f + 0.5f);
    if (st < -125) st = -125;
    if (st > 125) st = 125;
    return (uint8_t)(st < 0 ? st + 256 : st);
}
FLASHMEM static inline int AdjUs5(long us) { return (int)(floorf((float)us / 5.0f + 0.5f) * 5); }   // to the nearest 5 us (Math.round)
// Where Rotorflight changes to value q (1..n-1) on a switch of n positions over lo..hi: the first u with
// floor(((u - lo) * (n - 1) + floor(W / 2)) / W) == q (rc_adjustments.c, integer arithmetic). t[0..n-2]; how many
FLASHMEM static int AdjThresholds(int lo, int hi, int n, int *t)
{
    const long W = hi - lo;
    if (n < 2 || W <= 0) return 0;
    for (int q = 1; q < n; ++q) { const long num = q * W - W / 2; t[q - 1] = (int)(lo + (num + (n - 1) - 1) / (n - 1)); }
    return n - 1;
}
// The position Rotorflight picks for a channel value on a switch of n positions over lo..hi: 1..n, or 0 when the value is
// beyond the switch's reach - rc_adjustments.c recomputes only within (lo - margin, hi + margin), margin = max(5, W/(2(n-1))),
// and leaves the setting as it was outside that
FLASHMEM static int AdjZoneOf(int lo, int hi, int n, int u)
{
    const int W = hi - lo;
    if (n < 2 || W <= 0) return 0;
    int margin = W / (2 * (n - 1));
    if (margin < 5) margin = 5;
    if (!(u > lo - margin && u < hi + margin)) return 0;
    int t[ADJ_POS_MAX]; const int nt = AdjThresholds(lo, hi, n, t);
    int z = 1;
    for (int k = 0; k < nt; ++k) if (u >= t[k]) z = k + 2;
    return z;
}
// The ends lo..hi that give each of n rising values its own position, with the most room to spare: a search over every
// travel in 5 us steps (the transmitter's banks are seldom evenly spaced: Black Thunder 2's channel 7 is 988, 1091, 1500,
// 2012 us, which no "ends at the first and last value" can divide). False when no travel does. Room = the least distance
// from any value to the nearest division or edge of the reach.
FLASHMEM static bool AdjBestEnds(const int *vals, int n, int16_t &lo, int16_t &hi, int &room)
{
    int bestLo = 0, bestHi = 0, best = -1;
    for (int W = 5 * (n - 1); W <= ADJ_RMAX - ADJ_RMIN; W += 5)
    {
        int margin = W / (2 * (n - 1));
        if (margin < 5) margin = 5;
        int t[ADJ_POS_MAX];
        for (int l = ADJ_RMIN; l + W <= ADJ_RMAX; l += 5)
        {
            const int h = l + W;
            const int nt = AdjThresholds(l, h, n, t);
            int rm = 100000;
            bool ok = true;
            for (int b = 1; b <= n && ok; ++b)
            {
                const int u = vals[b];
                const int zlo = b == 1 ? l - margin + 1 : t[b - 2], zhi = b == n ? h + margin - 1 : t[b - 1] - 1;   // the value must sit in [zlo, zhi]
                if (u < zlo || u > zhi) { ok = false; break; }
                const int d = u - zlo < zhi - u ? u - zlo : zhi - u;
                if (d < rm) rm = d;
            }
            (void)nt;
            if (ok && rm > best) { best = rm; bestLo = l; bestHi = h; }
        }
    }
    if (best < 0) return false;
    lo = (int16_t)bestLo; hi = (int16_t)bestHi; room = best;
    return true;
}
FLASHMEM static int32_t AdjSwitchValue(int32_t first, int32_t last, int n, int k) // the value at position k: the ends as given, the rest evenly between
{
    if (n <= 1) return first;
    const float v = (float)first + (float)(last - first) * (float)k / (float)(n - 1);
    return (int32_t)floorf(v + 0.5f);
}
FLASHMEM static void AdjFitEnds(const int *t, int n, int16_t &lo, int16_t &hi) // the old dividers of n positions -> ends whose even divisions come nearest
{
    long l, h;
    if (n <= 2) { const long m = t[0]; long W = 1000; if (2 * (m - ADJ_RMIN) < W) W = 2 * (m - ADJ_RMIN); if (2 * (ADJ_RMAX - m) < W) W = 2 * (ADJ_RMAX - m); l = m - W / 2; h = m + W / 2; }
    else { const long W = (long)floorf((float)(t[n - 2] - t[0]) * (float)(n - 1) / (float)(n - 2) + 0.5f); l = t[0] - (long)floorf((float)W / (float)(2 * (n - 1)) + 0.5f); h = l + W; }
    if (l < ADJ_RMIN) l = ADJ_RMIN;
    if (h > ADJ_RMAX) h = ADJ_RMAX;
    lo = (int16_t)AdjUs5(l); hi = (int16_t)AdjUs5(h);
    if (hi < lo + 5) hi = (int16_t)(lo + 5);
}
FLASHMEM static int AdjParseLines(const uint8_t *b, int n, AdjLine *L) // 42 x 14 bytes -> lines; how many
{
    int k = 0;
    for (int i = 0; i < ADJ_MAX && (i + 1) * 14 <= n; ++i)
    {
        const uint8_t *o = b + i * 14;
        AdjLine &l = L[k++];
        l.fn = o[0]; l.ena = o[1]; l.enaLo = (int16_t)AdjUs(o[2]); l.enaHi = (int16_t)AdjUs(o[3]); l.adj = o[4];
        l.a1Lo = (int16_t)AdjUs(o[5]); l.a1Hi = (int16_t)AdjUs(o[6]); l.a2Lo = (int16_t)AdjUs(o[7]); l.a2Hi = (int16_t)AdjUs(o[8]);
        l.min = (uint16_t)(o[9] | (o[10] << 8)); l.max = (uint16_t)(o[11] | (o[12] << 8)); l.stp = o[13];
    }
    return k;
}
FLASHMEM static bool AdjSelfEna(const AdjLine &l) { return l.ena == l.adj && l.enaLo == l.a1Lo && l.enaHi == l.a1Hi; }
struct AdjBanks { bool have; uint8_t ch; int16_t lo[7], hi[7]; };
static void AdjBankRegions(const AdjRow *R, int nr, AdjBanks &out);
static void AdjBankToCond(AdjRow &r, int v, const AdjBanks &br);
FLASHMEM static int AdjLinesToRows(const AdjLine *L, int n, AdjRow *R) // the phone page's linesToRows
{
    bool used[ADJ_MAX] = {false};
    int nr = 0;
    int legacyBank = -1;                         // the PID-bank row read in the old form, if any
    int16_t oldLo[ADJ_POS_MAX], oldHi[ADJ_POS_MAX]; int32_t oldV[ADJ_POS_MAX]; int oldN = 0;   // its old regions, by value
    for (int i = 0; i < n && nr < ADJ_MAX; ++i)
    {
        const AdjLine &l = L[i];
        if (used[i] || l.fn == 0) continue;
        AdjRow &r = R[nr];
        memset(&r, 0, sizeof(r));
        if (l.stp > 0)
        {
            used[i] = true;
            r.kind = AK_NUDGE; r.fn = l.fn; r.ch = l.adj; r.n = 2; r.t[0] = l.a1Hi; r.t[1] = l.a2Lo; r.v[0] = l.min; r.v[1] = l.max; r.stp = l.stp;
            r.cond = true; r.ena = l.ena; r.enaLo = l.enaLo; r.enaHi = l.enaHi;   // (a nudge keeps its enable as read)
            ++nr; continue;
        }
        const bool selfEna = AdjSelfEna(l);
        const bool noCond = selfEna || (l.enaLo <= ADJ_RMIN && l.enaHi >= ADJ_RMAX);
        if (l.min == l.max)
        { // the old form: every line with the same setting, switch and condition that is also a fixed value
            int idx[ADJ_MAX]; int g = 0;
            for (int j = 0; j < n; ++j)
            {
                const AdjLine &m = L[j];
                if (used[j]) continue;
                const bool same = m.fn == l.fn && m.adj == l.adj && m.stp == 0 && m.min == m.max && AdjSelfEna(m) == selfEna &&
                                  (selfEna || (m.ena == l.ena && m.enaLo == l.enaLo && m.enaHi == l.enaHi));
                if (same) idx[g++] = j;
            }
            // sort by a1Lo
            for (int a = 1; a < g; ++a) { int x = idx[a]; int b2 = a - 1; while (b2 >= 0 && L[idx[b2]].a1Lo > L[x].a1Lo) { idx[b2 + 1] = idx[b2]; --b2; } idx[b2 + 1] = x; }
            for (int a = 0; a < g; ++a) used[idx[a]] = true;
            if (g == 1)
            { // one fixed value: kept as it is
                r.kind = AK_KNOB; r.fn = l.fn; r.ch = l.adj; r.n = 2; r.lo = l.a1Lo; r.hi = l.a1Hi; r.v[0] = l.min; r.v[1] = l.max;
                r.cond = !noCond; if (r.cond) { r.ena = l.ena; r.enaLo = l.enaLo; r.enaHi = l.enaHi; }
                ++nr; continue;
            }
            int t[ADJ_MAX]; int32_t vals[ADJ_MAX];
            for (int a = 0; a < g; ++a) { vals[a] = L[idx[a]].min; if (a > 0) t[a - 1] = L[idx[a]].a1Lo; }
            const int np = g > ADJ_POS_MAX ? ADJ_POS_MAX : g;
            r.kind = AK_SWITCH; r.fn = l.fn; r.ch = l.adj; r.n = (uint8_t)np; r.legacy = true;
            AdjFitEnds(t, np, r.lo, r.hi);
            for (int k = 0; k < np; ++k) r.v[k] = AdjSwitchValue(vals[0], vals[np - 1], np, k);
            r.cond = !noCond; if (r.cond) { r.ena = l.ena; r.enaLo = l.enaLo; r.enaHi = l.enaHi; }
            if (l.fn == 2 && legacyBank < 0)
            {
                legacyBank = nr; oldN = np;
                for (int k = 0; k < np; ++k) { oldLo[k] = (int16_t)(k == 0 ? ADJ_RMIN : t[k - 1]); oldHi[k] = (int16_t)(k == np - 1 ? ADJ_RMAX : t[k]); oldV[k] = vals[k]; }
            }
            ++nr; continue;
        }
        used[i] = true;
        const int np = (int)l.max - (int)l.min + 1;
        if (np >= 2 && np <= ADJ_POS_MAX)
        {
            r.kind = AK_SWITCH; r.fn = l.fn; r.ch = l.adj; r.n = (uint8_t)np; r.lo = l.a1Lo; r.hi = l.a1Hi;
            for (int k = 0; k < np; ++k) r.v[k] = (int32_t)l.min + k;
        }
        else
        {
            r.kind = AK_KNOB; r.fn = l.fn; r.ch = l.adj; r.n = 2; r.lo = l.a1Lo; r.hi = l.a1Hi; r.v[0] = l.min; r.v[1] = l.max;
        }
        r.cond = !noCond; if (r.cond) { r.ena = l.ena; r.enaLo = l.enaLo; r.enaHi = l.enaHi; }
        ++nr;
    }
    // a bank line of the old form divided the channel differently: the rows held in a bank move to its new divisions
    if (legacyBank >= 0)
    {
        AdjBanks br; AdjBankRegions(R, nr, br);
        const AdjRow &b = R[legacyBank];
        for (int i = 0; i < nr; ++i)
        {
            AdjRow &r = R[i];
            if (i == legacyBank || !r.cond || r.ena != b.ch) continue;
            for (int k = 0; k < oldN; ++k)
                if (abs(oldLo[k] - r.enaLo) <= 5 && abs(oldHi[k] - r.enaHi) <= 5)
                {
                    const int32_t v = oldV[k];
                    if (v >= 1 && v <= 6 && br.have && (br.lo[v] || br.hi[v])) AdjBankToCond(r, (int)v, br);
                    break;
                }
        }
    }
    return nr;
}
FLASHMEM static void AdjBlank(AdjLine &l) { l.fn = 0; l.ena = 0; l.enaLo = 1500; l.enaHi = 1500; l.adj = 0; l.a1Lo = 1500; l.a1Hi = 1500; l.a2Lo = 1500; l.a2Hi = 1500; l.min = 0; l.max = 0; l.stp = 0; }
FLASHMEM static int AdjRowsToLines(const AdjRow *R, int nr, AdjLine *L) // the phone page's rowsToLines: always 42 (the rest blank)
{
    int k = 0;
    for (int i = 0; i < nr; ++i)
    {
        const AdjRow &r = R[i];
        if (!r.fn) continue;
        if (k >= ADJ_MAX) break;
        if (r.kind == AK_SWITCH || r.kind == AK_KNOB)
        {
            AdjLine &l = L[k++];
            l.fn = r.fn; l.adj = r.ch; l.a1Lo = r.lo; l.a1Hi = r.hi; l.a2Lo = 1500; l.a2Hi = 1500;
            if (r.cond) { l.ena = r.ena; l.enaLo = r.enaLo; l.enaHi = r.enaHi; } else { l.ena = r.ch; l.enaLo = ADJ_RMIN; l.enaHi = ADJ_RMAX; }
            const int last = r.kind == AK_SWITCH ? (r.n > 0 ? r.n - 1 : 0) : 1;
            l.min = (uint16_t)r.v[0]; l.max = (uint16_t)r.v[last]; l.stp = 0;
        }
        else
        {
            AdjLine &l = L[k++];
            l.fn = r.fn; l.adj = r.ch; l.a1Lo = ADJ_RMIN; l.a1Hi = r.t[0]; l.a2Lo = r.t[1]; l.a2Hi = ADJ_RMAX;
            l.ena = r.cond ? r.ena : r.ch; l.enaLo = r.cond ? r.enaLo : (int16_t)ADJ_RMIN; l.enaHi = r.cond ? r.enaHi : (int16_t)ADJ_RMAX;
            l.min = (uint16_t)r.v[0]; l.max = (uint16_t)r.v[1]; l.stp = r.stp < 1 ? 1 : r.stp;
        }
    }
    while (k < ADJ_MAX) AdjBlank(L[k++]);
    return ADJ_MAX;
}
FLASHMEM static void AdjEncodeLine(int i, const AdjLine &l, uint8_t *b) // 15 bytes for 53
{
    b[0] = (uint8_t)i; b[1] = l.fn; b[2] = l.ena; b[3] = AdjStep(l.enaLo); b[4] = AdjStep(l.enaHi); b[5] = l.adj;
    b[6] = AdjStep(l.a1Lo); b[7] = AdjStep(l.a1Hi); b[8] = AdjStep(l.a2Lo); b[9] = AdjStep(l.a2Hi);
    b[10] = (uint8_t)l.min; b[11] = (uint8_t)(l.min >> 8); b[12] = (uint8_t)l.max; b[13] = (uint8_t)(l.max >> 8); b[14] = l.stp;
}
FLASHMEM static bool AdjSameLine(const AdjLine &a, const AdjLine &b)
{
    return a.fn == b.fn && a.ena == b.ena && a.adj == b.adj && a.stp == b.stp && a.enaLo == b.enaLo && a.enaHi == b.enaHi &&
           a.a1Lo == b.a1Lo && a.a1Hi == b.a1Hi && a.a2Lo == b.a2Lo && a.a2Hi == b.a2Hi && a.min == b.min && a.max == b.max;
}
FLASHMEM static void AdjRowMinMax(const AdjRow &r, int32_t &mn, int32_t &mx) { mn = r.v[0]; mx = r.kind == AK_SWITCH ? r.v[r.n > 0 ? r.n - 1 : 0] : r.v[1]; }
// Which channel range means "bank N"? Off the PID-bank row (fn 2): lo..hi maps to the first..last value linearly
// (Rotorflight rounds). regions[v] = {lo, hi} for v 1..6, lo == hi == 0 when none.
FLASHMEM static void AdjBankRegions(const AdjRow *R, int nr, AdjBanks &out)
{
    memset(&out, 0, sizeof(out));
    const AdjRow *b = nullptr;
    for (int i = 0; i < nr; ++i) if (R[i].fn == 2 && R[i].kind != AK_NUDGE) { b = &R[i]; break; }
    if (!b) return;
    out.have = true; out.ch = b->ch;
    int32_t mn, mx; AdjRowMinMax(*b, mn, mx);
    const int32_t n = mx - mn;
    if (n <= 0) { out.have = false; return; }
    for (int32_t v = mn; v <= mx; ++v)
    { // value v is chosen where round(min + (u - lo) * n / (hi - lo)) == v
        if (v < 1 || v > 6) continue;
        const float f0 = ((float)v - 0.5f - (float)mn) / (float)n, f1 = ((float)v + 0.5f - (float)mn) / (float)n;
        const float span = (float)(b->hi - b->lo);
        int lo = (int)(floorf(((float)b->lo + f0 * span) / 5.0f + 0.5f) * 5), hi = (int)(floorf(((float)b->lo + f1 * span) / 5.0f + 0.5f) * 5);
        if (lo < b->lo) lo = b->lo;
        if (hi > b->hi) hi = b->hi;
        out.lo[v] = (int16_t)(v == mn ? ADJ_RMIN : lo); out.hi[v] = (int16_t)(v == mx ? ADJ_RMAX : hi);
    }
}
FLASHMEM static int AdjCondToBank(const AdjRow &r, const AdjBanks &br) // 0 any, 1..6, -1 some other condition
{
    if (!r.cond || !br.have || r.ena != br.ch) return 0;
    for (int v = 1; v <= 6; ++v)
        if ((br.lo[v] || br.hi[v]) && abs(br.lo[v] - r.enaLo) <= 5 && abs(br.hi[v] - r.enaHi) <= 5) return v;
    return -1;
}
FLASHMEM static void AdjBankToCond(AdjRow &r, int v, const AdjBanks &br)
{
    if (v < 1 || v > 6 || !br.have || !(br.lo[v] || br.hi[v])) { r.cond = false; r.ena = 0; r.enaLo = 0; r.enaHi = 0; return; }
    r.cond = true; r.ena = br.ch; r.enaLo = br.lo[v]; r.enaHi = br.hi[v];
}
// What stops a set of rows being saved (the phone page's rowsProblem): the words into buf, false when nothing does
FLASHMEM static bool AdjRowsProblem(const AdjRow *R, int nr, char *buf, size_t len)
{
    for (int i = 0; i < nr; ++i)
    {
        const AdjRow &r = R[i];
        if (!r.fn) continue;
        const char *name = AdjNames[r.fn < ADJ_NAMES ? r.fn : 0];
        if (r.kind == AK_SWITCH)
        {
            if (r.v[r.n > 0 ? r.n - 1 : 0] <= r.v[0]) { snprintf(buf, len, "%d. %s:\r\nthe last position's value must be above\r\nthe first's (Rotorflight counts low to high:\r\nreverse the channel if the switch goes the\r\nother way).", i + 1, name); return true; }
        }
        else if (r.kind == AK_KNOB)
        {
            if (r.v[1] <= r.v[0]) { snprintf(buf, len, "%d. %s:\r\nthe value at the right end must be above\r\nthe one at the left (Rotorflight counts low\r\nto high: reverse the channel if the knob\r\ngoes the other way).", i + 1, name); return true; }
        }
    }
    return false;
}
// Where a setting's present value can be read: the function, the byte, how many bytes, and which bank (1 PID, 2 rates); false = unknown
FLASHMEM static bool AdjValueSource(uint8_t fn, uint8_t &rfn, int &off, int &bytes, int &side)
{
    static const uint8_t A[3] = {1, 0, 2};   // adjustment order pitch, roll, yaw -> axis roll 0, pitch 1, yaw 2
    if (fn >= 5 && fn <= 13) { const int k = (fn - 5) % 3, sub = fn <= 7 ? 2 : fn <= 10 ? 0 : 1; rfn = 111; off = 1 + A[k] * 6 + sub; bytes = 1; side = 2; return true; }
    if (fn >= 14 && fn <= 25) { const int g = (fn - 14) / 4, t = (fn - 14) % 4; rfn = 112; off = (A[g] * 4 + t) * 2; bytes = 2; side = 1; return true; }
    struct S { uint8_t fn, rfn, off, bytes, side; };
    static const S tab[] = {
        {26, 94, 20, 1, 1}, {27, 94, 21, 1, 1}, {28, 94, 23, 1, 1}, {29, 94, 24, 1, 1}, {32, 94, 27, 1, 1},
        {33, 94, 11, 1, 1}, {34, 94, 10, 1, 1}, {35, 94, 12, 1, 1}, {36, 94, 14, 1, 1}, {37, 94, 13, 1, 1}, {38, 94, 15, 1, 1},
        {39, 146, 10, 2, 1}, {40, 146, 12, 2, 1}, {41, 146, 14, 2, 1}, {42, 146, 16, 2, 1}, {43, 146, 18, 2, 1}, {44, 146, 20, 2, 1},
        {45, 94, 28, 1, 1}, {46, 94, 30, 1, 1}, {47, 94, 31, 1, 1},
        {48, 148, 2, 1, 1}, {49, 148, 3, 1, 1}, {50, 148, 4, 1, 1}, {51, 148, 5, 1, 1}, {52, 148, 6, 1, 1}, {53, 148, 7, 1, 1}, {54, 148, 10, 1, 1}, {55, 148, 11, 1, 1},
        {56, 112, 26, 2, 1}, {57, 112, 24, 2, 1}, {58, 112, 28, 2, 1}, {59, 112, 32, 2, 1}, {60, 112, 30, 2, 1},
        {61, 94, 33, 1, 1}, {62, 94, 34, 1, 1}, {63, 94, 35, 1, 1}, {66, 94, 41, 1, 1}, {67, 94, 42, 1, 1},
        {68, 111, 27, 1, 2}, {69, 111, 25, 1, 2}, {70, 111, 29, 1, 2}, {71, 111, 31, 1, 2}, {72, 111, 33, 1, 2}, {73, 111, 34, 1, 2}, {74, 111, 35, 1, 2}, {75, 94, 22, 1, 1},
        {78, 148, 12, 1, 1}, {79, 148, 13, 1, 1}, {80, 148, 0, 2, 1}, {81, 148, 9, 1, 1}};
    for (const S &s : tab) if (s.fn == fn) { rfn = s.rfn; off = s.off; bytes = s.bytes; side = s.side; return true; }
    return false;
}
static int AdjScale = 5;                                     // the rates type: Rate = stored x5 (type 6), x10 before
FLASHMEM static int AdjFnScale(uint8_t fn) { return (fn >= 8 && fn <= 10) ? AdjScale : 1; }

// ---------------------------------------------------------------- the page
DMAMEM static AdjRow AdjRows[ADJ_MAX];   // what the pilot sees and edits, values in page units (the Rate settings x5)
static int AdjN = 0, AdjAt = 0;
DMAMEM static AdjLine AdjWritten[ADJ_MAX]; // the lines of the last save, to read back against
DMAMEM static AdjLine AdjAsRead[ADJ_MAX];  // the lines as the flight controller had them: a save writes only the lines that differ (each write holds the receiver up for most of a second)
static bool AdjHave = false, Adj_Was_Edited = false;
static AdjBanks AdjBk;
enum { ADJ_IDLE = 0, ADJ_READ_RATES, ADJ_READ, ADJ_WRITE, ADJ_STORE, ADJ_VERIFY, ADJ_NOW_STATUS, ADJ_NOW_READ };
static int AdjStep_ = ADJ_IDLE, AdjReq = 0, AdjTries = 0, AdjLineAt = 0;
static uint32_t AdjMsgUntil = 0, AdjLiveMs = 0;
static bool AdjNowKnown = false; static int32_t AdjNow = 0; static uint8_t AdjNowFn = 0; static int AdjNowRow = -1;
static uint8_t AdjNowRfn = 0; static int AdjNowOff = 0, AdjNowBytes = 0, AdjNowSide = 0, AdjNowBank = 0;
DMAMEM static uint8_t AdjImg[600];       // the 52 image as it comes (588 bytes)
static char AdjTakeNote[120];            // what the read found to put right (B83): said once the rows are shown

FLASHMEM static void AdjBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg) SendText((char *)"busy", (char *)msg);
}
static void AdjText(const char *name, const char *t) { SendText((char *)name, (char *)t); }
static void AdjNum(const char *name, long v) { char b[16]; snprintf(b, sizeof(b), "%ld", v); SendText((char *)name, b); }
static void AdjVis(const char *name, bool on) { char c[24]; snprintf(c, sizeof(c), "vis %s,%d", name, on ? 1 : 0); SendCommand(c); }
FLASHMEM static void AdjHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"USB cable");
    SendCommand((char *)(Adj_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void AdjTitle()
{
    char b[48];
    if (AdjN) snprintf(b, sizeof(b), "Adjustment %d of %d", AdjAt + 1, AdjN);
    else snprintf(b, sizeof(b), "Adjustments: none yet");
    SendText((char *)"t0", b);
}
FLASHMEM static int AdjLinesUsed(int exceptRow) // how many of the 42 lines the rows would take (one each, B83)
{
    int k = 0;
    for (int i = 0; i < AdjN; ++i) { if (i == exceptRow || !AdjRows[i].fn) continue; k += 1; }
    return k;
}
// This transmitter's output for a channel, as the flight controller sees it: the receiver makes CRSF of it (819/500 per
// microsecond about 1500, clamped to 172..1811) and Rotorflight makes microseconds of that again (988..2012)
FLASHMEM static int AdjFcUs(uint16_t txUs)
{
    long v = 1500 + ((long)txUs - 1500) * 819L * 5L / (500L * 8L);
    if (v < 988) v = 988;
    if (v > 2012) v = 2012;
    return (int)v;
}
FLASHMEM static int AdjRegionOf(const AdjRow &r, int us) // which region of the row's bar the channel is in (0..), -1 for none
{
    if (r.kind == AK_KNOB) return us < r.lo ? 0 : us > r.hi ? 2 : 1;
    if (r.kind == AK_SWITCH) return AdjZoneOf(r.lo, r.hi, r.n, us) - 1;   // the position Rotorflight picks (-1: beyond the switch's reach)
    for (int k = 0; k < 2; ++k) if (us < r.t[k]) return k;
    return 2;
}
// ---- the bank switch and THIS transmitter's banks (B83). The bank channel of a Version 1/2 model is usually not a switch
// at all: its curve is flat in each bank at a value of that bank's own (Black Thunder 2's channel 7: 13, 54, 90 and 151
// degrees in banks 1 to 4), so the flight controller can only follow the banks if Rotorflight's even divisions of the
// bank line's travel put each bank's value in its own zone. The transmitter knows those values - computed from the
// model (the bank's curve, trims, reversal; mixes left out), and measured from its own output whenever a bank is in
// use on this page - and fits the bank line's ends to them: lo = bank 1's value, hi = the last bank's. A bank line that
// already puts every bank in its own zone is left as it is.
static int16_t AdjSeenUs[BANKS_USED + 1][CHANNELSUSED];   // the channel's output seen in each bank on this page (-1 = not yet)
FLASHMEM static void AdjSeenClear() { for (int b = 0; b <= BANKS_USED; ++b) for (int c = 0; c < CHANNELSUSED; ++c) AdjSeenUs[b][c] = -1; }
extern uint16_t (*Interpolate[3])(uint16_t InputValue, uint16_t InputChannel, uint16_t OutputChannel);
FLASHMEM static int AdjTxBankUs(int ch0, int bank) // this transmitter's output on channel ch0 (0-based) in a bank, as the flight controller sees it; -1 if unknown
{
    if (ch0 < 0 || ch0 >= CHANNELSUSED || bank < 1 || bank > BANKS_USED) return -1;
    if (AdjSeenUs[bank][ch0] >= 0) return AdjSeenUs[bank][ch0];                  // measured beats computed
    const uint8_t saved = Bank;
    Bank = (uint8_t)bank;
    const int src = ChannelOutPut[ch0] < CHANNELSUSED ? ChannelOutPut[ch0] : ch0;   // the output may be re-routed from another channel's computation
    GetCurveDots(src, DualRateValue);
    const uint8_t it = InterpolationTypes[Bank][src] < 3 ? InterpolationTypes[Bank][src] : 0;
    int v = (int)Interpolate[it](InputsBuffer[src], InPutStick[src], src);
    v += (SubTrims[src] - 127) * 5 + GetTrimAmount(InPutStick[src]);
    Bank = saved;
    GetCurveDots(src, DualRateValue);   // (the curve dots are a global: put the bank in use back)
    if (v < MINMICROS) v = MINMICROS;
    if (v > MAXMICROS) v = MAXMICROS;
    if (ReversedChannelBITS & (1 << ch0)) v = MAXMICROS - (v - MINMICROS);
    return AdjFcUs((uint16_t)v);
}
// How many banks the channel tells apart, rising from bank 1 (their values into vals[1..]); 1 = none
FLASHMEM static int AdjBankValues(int ch0, int *vals)
{
    for (int b = 1; b <= BANKS_USED; ++b) vals[b] = AdjTxBankUs(ch0, b);
    int n = 1;
    while (n < BANKS_USED && vals[n + 1] > vals[n]) ++n;
    return n;
}
// The bank line's ends for this transmitter: the travel whose even divisions give each bank its own zone with the most room
// (AdjBestEnds), n = how many banks the channel tells apart (rising from bank 1); false, with the reason, when it cannot.
FLASHMEM static bool AdjBankFit(int ch0, int16_t &lo, int16_t &hi, int &n, char *why, size_t len)
{
    int vals[BANKS_USED + 1];
    n = AdjBankValues(ch0, vals);
    if (n < 2) { snprintf(why, len, "Channel %d has no value of its own in each bank of this transmitter (bank 1 %d us, bank 2 %d us): the flight controller cannot tell the banks apart on it.", ch0 + 1, vals[1], vals[2]); return false; }
    int room = 0;
    if (!AdjBestEnds(vals, n, lo, hi, room))
    {
        char v[40] = ""; for (int b = 1; b <= n; ++b) { char one[10]; snprintf(one, sizeof(one), "%s%d", b > 1 ? ", " : "", vals[b]); strncat(v, one, sizeof(v) - strlen(v) - 1); }
        snprintf(why, len, "This transmitter's bank values on channel %d (%s us) cannot all be told apart by Rotorflight's even spacing: space them more evenly in Model setup.", ch0 + 1, v);
        return false;
    }
    if (n < BANKS_USED) snprintf(why, len, "Banks 1 to %d; bank %d has no value of its own on channel %d (%d us).", n, n + 1, ch0 + 1, vals[n + 1]);
    else why[0] = 0;
    return true;
}
FLASHMEM static bool AdjBankRowRight(const AdjRow &r) // does the bank line as it is give every bank of this transmitter its own zone?
{
    int vals[BANKS_USED + 1];
    const int n = AdjBankValues(r.ch + 5, vals);
    if (n < 2 || r.kind != AK_SWITCH || r.n < n || r.v[0] != 1) return false;
    for (int b = 1; b <= n; ++b) if (AdjZoneOf(r.lo, r.hi, r.n, vals[b]) != b) return false;
    return true;
}
static bool AdjBankFitted[ADJ_MAX];   // the row's ends are this transmitter's (no handles to drag)
static char AdjBankWhy[200];           // what the last fit of the row showing said
// The rows held in a bank follow the bank line when it changes: their conditions re-made from the new divisions
FLASHMEM static void AdjRebank(const AdjBanks &before)
{
    AdjBanks after; AdjBankRegions(AdjRows, AdjN, after);
    for (int i = 0; i < AdjN; ++i)
    {
        AdjRow &r = AdjRows[i];
        if (r.fn <= 2 || !r.cond || !before.have || r.ena != before.ch) continue;
        int v = 0;
        for (int b = 1; b <= 6; ++b) if ((before.lo[b] || before.hi[b]) && abs(before.lo[b] - r.enaLo) <= 5 && abs(before.hi[b] - r.enaHi) <= 5) { v = b; break; }
        if (v && after.have && (after.lo[v] || after.hi[v])) AdjBankToCond(r, v, after);
    }
    AdjBk = after;
}
FLASHMEM static bool AdjFitBankRow(int i) // a bank row's ends from this transmitter's banks; true if it changed the row
{
    AdjRow &r = AdjRows[i];
    if (r.fn != 1 && r.fn != 2) { AdjBankFitted[i] = false; return false; }
    int16_t lo, hi; int n;
    if (!AdjBankFit(r.ch + 5, lo, hi, n, AdjBankWhy, sizeof(AdjBankWhy))) { AdjBankFitted[i] = false; return false; }
    AdjBankFitted[i] = true;
    if (r.kind == AK_SWITCH && r.n == n && r.lo == lo && r.hi == hi && r.v[0] == 1 && r.v[n - 1] == n) return false;
    AdjBanks before; AdjBankRegions(AdjRows, AdjN, before);
    r.kind = AK_SWITCH; r.n = (uint8_t)n; r.lo = lo; r.hi = hi;
    for (int k = 0; k < n; ++k) r.v[k] = k + 1;
    if (r.fn == 2) AdjRebank(before); else AdjBankRegions(AdjRows, AdjN, AdjBk);
    return true;
}
static void AdjGather();
static void AdjEdited();
static void AdjShow();
static int AdjLiveCh = -1, AdjLiveUs = -1;   // what the marker and the line last showed (AdjShow forgets them: the row may have changed)
FLASHMEM static void AdjLive() // the chosen channel's position, from this transmitter's own output: the bar's marker and the line under it
{
    if (!AdjN) { if (AdjLiveCh != -1) { AdjLiveCh = -1; AdjText("tn8", ""); } return; }
    const AdjRow &r = AdjRows[AdjAt];
    const int ch = r.ch + 6;   // 1-based channel
    const int us = (ch >= 1 && ch <= CHANNELSUSED) ? AdjFcUs(SendBuffer[ch - 1]) : -1;
    if (Bank >= 1 && Bank <= BANKS_USED && (BoundFlag && ModelMatched))
    { // what this transmitter sends in the bank in use, for the bank line's fit (measured beats computed)
        bool fresh = false;   // (the bank channel of the row showing: a stick moving is not news)
        for (int c = 0; c < CHANNELSUSED; ++c) { const int v = AdjFcUs(SendBuffer[c]); if (AdjSeenUs[Bank][c] != v) { AdjSeenUs[Bank][c] = (int16_t)v; if (c == ch - 1) fresh = true; } }
        if (fresh && (r.fn == 1 || r.fn == 2) && AdjStep_ == ADJ_IDLE)
        {
            const bool wasRight = AdjBankFitted[AdjAt];
            AdjBankFitted[AdjAt] = AdjBankRowRight(r);
            if (!AdjBankFitted[AdjAt] && AdjFitBankRow(AdjAt))
            { // a bank seen for the first time shows the line as it is cannot follow this transmitter: the ends re-fitted
                AdjEdited(); AdjShow();
                AdjBusy("The bank switch did not follow this transmitter's banks: matched - press Save"); AdjMsgUntil = millis() + 6000;
                return;
            }
            if (wasRight != AdjBankFitted[AdjAt]) { AdjShow(); return; }
        }
    }
    if (ch == AdjLiveCh && us == AdjLiveUs) return;
    AdjLiveCh = ch; AdjLiveUs = us;
    char c[24], b[64];
    snprintf(c, sizeof(c), "bar.mk=%d", us); SendCommand(c);
    const int k = us >= 0 ? AdjRegionOf(r, us) : -1;   // (B76, Malcolm: "nothing more than position: 988 us")
    if (k < 0) snprintf(b, sizeof(b), "Channel %d: ?", ch);
    else if (r.kind == AK_SWITCH && (r.fn == 1 || r.fn == 2))
    { // the bank switch: this transmitter's bank, and the bank Rotorflight picks from the channel
        if (k + 1 == Bank) snprintf(b, sizeof(b), "Bank %d: %d us", Bank, us);
        else if (k < 0) snprintf(b, sizeof(b), "Bank %d: %d us - beyond the switch's reach: no change", Bank, us);
        else snprintf(b, sizeof(b), "Bank %d: %d us - the flight controller would pick bank %d", Bank, us, k + 1);
    }
    else if (r.kind == AK_SWITCH && k < 0) snprintf(b, sizeof(b), "Beyond the switch's reach (no change): %d us", us);
    else if (r.kind == AK_SWITCH) snprintf(b, sizeof(b), "Position %d: %d us", k + 1, us);
    else if (r.kind == AK_KNOB)
    {
        if (k != 1) snprintf(b, sizeof(b), "Outside the knob's travel: %d us", us);
        else { const long span = r.hi > r.lo ? r.hi - r.lo : 1; const long v = r.v[0] + ((r.v[1] - r.v[0]) * (long)(us - r.lo) + span / 2) / span; snprintf(b, sizeof(b), "Knob %d us: %ld", us, v); }
    }
    else snprintf(b, sizeof(b), "%s: %d us", k == 0 ? "Stepping down" : k == 2 ? "Stepping up" : "Holding", us);
    AdjText("tn8", b);
}
FLASHMEM static void AdjShowNow() {}   // (B75: the setting's present value is no longer shown - it only seeds a new row; Malcolm found "Now: ?" mysterious)
FLASHMEM static void AdjShow()
{
    AdjBankRegions(AdjRows, AdjN, AdjBk);   // (the bank line may just have been edited)
    AdjTitle();
    if (!AdjN)
    {
        AdjText("tn0", (char *)"(none yet: press Add)"); AdjText("tn3", (char *)""); AdjText("tn2", (char *)""); AdjText("tn1", (char *)"");
        AdjText("tn8", (char *)"");
        SendCommand((char *)"bar.n=1"); SendCommand((char *)"bar.kind=0"); SendCommand((char *)"bar.mk=-1"); AdjText("bar", (char *)"");
        return;
    }
    const AdjRow &r = AdjRows[AdjAt];
    char b[48];
    AdjText("tn0", AdjNames[r.fn < ADJ_NAMES ? r.fn : 0]);
    const int bank = AdjCondToBank(r, AdjBk);
    if (bank > 0) snprintf(b, sizeof(b), "in bank %d", bank); else snprintf(b, sizeof(b), "%s", bank < 0 ? "in bank ?" : "in any bank");
    AdjText("tn3", b);
    AdjVis("tn3", r.fn > 2);   // (B76, Malcolm: a bank switch IS the bank - no bank box for it)
    if (r.kind == AK_SWITCH && (r.fn == 1 || r.fn == 2) && AdjBankFitted[AdjAt]) snprintf(b, sizeof(b), "Banks 1 to %d of this transmitter", r.n);
    else if (r.kind == AK_SWITCH) snprintf(b, sizeof(b), "Switch, %d positions", r.n); else snprintf(b, sizeof(b), "%s", r.kind == AK_KNOB ? "Knob" : "Step up / down");
    AdjText("tn2", b);
    const int ch = r.ch + 6;
    snprintf(b, sizeof(b), "Channel %d: %s", ch, (ch >= 1 && ch <= CHANNELSUSED) ? ChannelNames[ch - 1] : "?");
    AdjText("tn1", b);
    // the bar: its kind, its zones and their dividers, the values in them; and the boxes the keypad edits, out of sight
    char labels[160] = "";
    if (r.kind == AK_KNOB)
    {
        SendCommand((char *)"bar.kind=1"); SendCommand((char *)"bar.n=3");
        snprintf(b, sizeof(b), "bar.d0=%d", r.lo); SendCommand(b); snprintf(b, sizeof(b), "bar.d1=%d", r.hi); SendCommand(b);
        snprintf(labels, sizeof(labels), "|%ld to %ld|", (long)r.v[0], (long)r.v[1]);
        AdjNum("tk0", r.v[0]); AdjNum("tk1", r.v[1]);
    }
    else if (r.kind == AK_SWITCH)
    { // kind 3: round handles on the ENDS, the zones between them Rotorflight's even divisions; kind 4 the same with no handles (the ends are this transmitter's banks)
        SendCommand((char *)(AdjBankFitted[AdjAt] && (r.fn == 1 || r.fn == 2) ? "bar.kind=4" : "bar.kind=3")); snprintf(b, sizeof(b), "bar.n=%d", r.n); SendCommand(b);
        snprintf(b, sizeof(b), "bar.d0=%d", r.lo); SendCommand(b); snprintf(b, sizeof(b), "bar.d1=%d", r.hi); SendCommand(b);
        for (int k = 0; k < r.n && k < ADJ_POS_MAX; ++k) { char one[20]; snprintf(one, sizeof(one), "%s%ld", k ? "|" : "", (long)r.v[k]); strncat(labels, one, sizeof(labels) - strlen(labels) - 1); char nm[8]; snprintf(nm, sizeof(nm), "tp%d", k); AdjNum(nm, r.v[k]); }
    }
    else
    {
        SendCommand((char *)"bar.kind=2"); SendCommand((char *)"bar.n=3");
        snprintf(b, sizeof(b), "bar.d0=%d", r.t[0]); SendCommand(b); snprintf(b, sizeof(b), "bar.d1=%d", r.t[1]); SendCommand(b);
        snprintf(labels, sizeof(labels), "down %d|%ld to %ld|up %d", r.stp, (long)r.v[0], (long)r.v[1], r.stp);
        AdjNum("ts0", r.stp); AdjNum("ts1", r.v[0]); AdjNum("ts2", r.v[1]);
    }
    AdjText("bar", labels);
    // the hint under the bar, for the kind (B83)
    if (r.kind == AK_SWITCH && (r.fn == 1 || r.fn == 2)) AdjText("hint", AdjBankFitted[AdjAt] ? "Every bank of this transmitter has its own zone: nothing to drag." : "No travel gives every bank its own zone: tap the kind box for why.");
    else if (r.kind == AK_SWITCH) AdjText("hint", "Tap the first or last zone to type its value. Drag the round ends.");
    else if (r.kind == AK_KNOB) AdjText("hint", "Tap the knob's zone to type its values. Drag the round ends.");
    else AdjText("hint", "Tap a zone to type its value. Drag the round dividers.");
    AdjLiveCh = -1;   // (the line under the bar is worded from the row: said again)
    AdjLive();
}
// The bar was touched (the screen's release event): a TAP on a zone opens the keypad for that zone's value (the box the
// keypad edits is clicked, as a finger would); a DRAG moved a divider: the dividers as the screen now has them, into the row
FLASHMEM static void AdjClickBox(const char *box) { char c[24]; snprintf(c, sizeof(c), "click %s,0", box); SendCommand(c); }
// A handle of the bar was dragged (the screen's release event): the dividers as the screen now has them, into the row
FLASHMEM void AdjustBarMoved()
{
    if (!AdjN || AdjStep_ != ADJ_IDLE) return;
    AdjGather();
    AdjRow &r = AdjRows[AdjAt];
    const int tap = GetOtherValue((char *)"bar.tap");
    if (tap >= ADJ_RMIN && tap <= ADJ_RMAX)
    { // a tap: which zone, which value
        int k = AdjRegionOf(r, tap);
        if (r.kind == AK_SWITCH)
        { // the first and last positions take a value; the rest are evenly between (Rotorflight's own spacing)
            if (r.fn == 1 || r.fn == 2) return;   // (a bank switch counts its banks: nothing to type, and nothing to say - Malcolm, B85)
            if (k < 0) k = tap < (r.lo + r.hi) / 2 ? 0 : r.n - 1;   // (beyond the reach: the nearer end)
            if (k == 0) AdjClickBox("tp0");
            else if (k == r.n - 1 && k < ADJ_POS_MAX) { char nm[8]; snprintf(nm, sizeof(nm), "tp%d", k); AdjClickBox(nm); }
            else { AdjBusy("Type the first and last positions: Rotorflight spaces the rest evenly"); AdjMsgUntil = millis() + 3000; }
        }
        else if (r.kind == AK_KNOB) { if (k == 1) AdjClickBox(tap < (r.lo + r.hi) / 2 ? "tk0" : "tk1"); }
        else { if (k != 1) AdjClickBox("ts0"); else AdjClickBox(tap < (r.t[0] + r.t[1]) / 2 ? "ts1" : "ts2"); }
        return;
    }
    int d[2];
    for (int k = 0; k < 2; ++k) { char n[10]; snprintf(n, sizeof(n), "bar.d%d", k); const int v = GetOtherValue((char *)n); d[k] = (v >= ADJ_RMIN && v <= ADJ_RMAX) ? v : -1; }
    AdjBanks before; AdjBankRegions(AdjRows, AdjN, before);
    bool changed = false;
    for (int k = 0; k < 2; ++k)
    {
        if (d[k] < 0) continue;
        int16_t &slot = r.kind == AK_NUDGE ? r.t[k] : (k == 0 ? r.lo : r.hi);   // a switch's or knob's ends; a nudge's two dividers
        if (slot != d[k]) { slot = (int16_t)d[k]; changed = true; }
    }
    if (!changed) return;
    if (r.fn == 2) AdjRebank(before);   // (the rows held in a bank follow the bank line's new divisions)
    AdjEdited();
    AdjShow();
}
FLASHMEM static void AdjGather() // the typed values of the row showing
{
    if (!AdjN || CurrentView != ADJUSTVIEW) return;
    AdjRow &r = AdjRows[AdjAt];
    if (r.kind == AK_KNOB) { r.v[0] = FieldNumber("tk0", 0, 65535); r.v[1] = FieldNumber("tk1", 0, 65535); }
    else if (r.kind == AK_SWITCH)
    { // the first and last positions as typed, the rest evenly between
        if (r.fn != 1 && r.fn != 2 && r.n >= 2 && r.n <= ADJ_POS_MAX)
        {
            char nm[8]; snprintf(nm, sizeof(nm), "tp%d", r.n - 1);
            const int32_t first = FieldNumber("tp0", 0, 65535), last = FieldNumber(nm, 0, 65535);
            for (int k = 0; k < r.n; ++k) r.v[k] = AdjSwitchValue(first, last, r.n, k);
        }
    }
    else { r.stp = (uint8_t)FieldNumber("ts0", 1, 255); r.v[0] = FieldNumber("ts1", 0, 65535); r.v[1] = FieldNumber("ts2", 0, 65535); }
}
// The page is back on the screen - from the keypad, from a question, or just opened (its postinitialize prints "ldrcadj"):
// the values as typed, and the bar drawn again from them
FLASHMEM void AdjustPageBack()
{
    if (CurrentView != ADJUSTVIEW || !AdjHave) return;
    AdjGather();
    AdjHead();
    AdjShow();
}
static void AdjEdited() { Adj_Was_Edited = true; SendCommand((char *)"vis b3,1"); }
FLASHMEM static void AdjFail(const char *what, bool leave)
{
    char msg[200];
    snprintf(msg, sizeof(msg), "%s:\r\n%.150s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    AdjStep_ = ADJ_IDLE;
    AdjBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)(leave ? "page RFView" : "page AdjustView"), msg);
    if (leave) { RotorFlightStart(); return; }
    AdjHead(); AdjShow();
}
struct AdjKindMemo { uint8_t fn, ch, n; int16_t lo, hi; int32_t first, last; };
DMAMEM static AdjKindMemo AdjMemo[ADJ_MAX]; static int AdjMemoN = 0;   // the switches as the pilot had them before a read (a line cannot say how many positions a switch has)
FLASHMEM static void AdjTakeRows(const uint8_t *b, int n) // the 52 image -> rows in page units
{
    AdjLine L[ADJ_MAX];
    const int nl = AdjParseLines(b, n, L);
    for (int i = 0; i < ADJ_MAX; ++i) { if (i < nl) AdjAsRead[i] = L[i]; else AdjBlank(AdjAsRead[i]); }
    AdjMemoN = 0;
    for (int i = 0; i < AdjN && AdjMemoN < ADJ_MAX; ++i)
    { // the switches shown until now, in raw units: a line read back as a knob that matches one is that switch again
        const AdjRow &r = AdjRows[i];
        if (r.kind != AK_SWITCH || !r.fn || r.n < 2) continue;
        const int sc = AdjFnScale(r.fn);
        AdjKindMemo &m = AdjMemo[AdjMemoN++];
        m.fn = r.fn; m.ch = r.ch; m.n = r.n; m.lo = (int16_t)AdjUs(AdjStep(r.lo)); m.hi = (int16_t)AdjUs(AdjStep(r.hi)); m.first = (r.v[0] + sc / 2) / sc; m.last = (r.v[r.n - 1] + sc / 2) / sc;
    }
    AdjN = AdjLinesToRows(L, nl, AdjRows);
    // ONE bank switch and one rates switch (B86): a second line for the same selector fights the first (the phone app's
    // Switches page wrote its own into slot 30 while the transmitter's sat in slot 0 - Malcolm, 8 Oct 23:05). The first
    // is kept, the rest go, to be saved away.
    int dups = 0;
    for (int fn = 1; fn <= 2; ++fn)
    {
        int first = -1;
        for (int i = 0; i < AdjN; ++i)
        {
            if (AdjRows[i].fn != fn || AdjRows[i].kind == AK_NUDGE) continue;
            if (first < 0) { first = i; continue; }
            for (int j = i; j + 1 < AdjN; ++j) AdjRows[j] = AdjRows[j + 1];
            --AdjN; --i; ++dups;
        }
    }
    int legacy = 0;
    for (int i = 0; i < AdjN; ++i)
    {
        AdjRow &r = AdjRows[i];
        if (r.kind == AK_KNOB)
            for (int m = 0; m < AdjMemoN; ++m)
                if (AdjMemo[m].fn == r.fn && AdjMemo[m].ch == r.ch && AdjMemo[m].lo == r.lo && AdjMemo[m].hi == r.hi && AdjMemo[m].first == r.v[0] && AdjMemo[m].last == r.v[1])
                { // the same line: the switch it was, its positions evenly between the ends
                    const int32_t first = r.v[0], last = r.v[1];
                    r.kind = AK_SWITCH; r.n = AdjMemo[m].n;
                    for (int k = 0; k < r.n; ++k) r.v[k] = AdjSwitchValue(first, last, r.n, k);
                    break;
                }
        const int sc = AdjFnScale(r.fn);
        if (sc != 1) for (int k = 0; k < ADJ_POS_MAX; ++k) r.v[k] *= sc;
        if (r.legacy) ++legacy;
    }
    AdjBankRegions(AdjRows, AdjN, AdjBk);
    if (AdjAt >= AdjN) AdjAt = AdjN ? AdjN - 1 : 0;
    // the bank lines against this transmitter's banks: a line that cannot follow them is re-fitted (shown, to be saved)
    bool refit = false;
    for (int i = 0; i < AdjN; ++i)
    {
        AdjRow &r = AdjRows[i];
        if (r.fn != 1 && r.fn != 2) { AdjBankFitted[i] = false; continue; }
        if (AdjBankRowRight(r)) { AdjBankFitted[i] = true; continue; }   // every bank has its own zone: left as it is
        if (AdjFitBankRow(i)) refit = true;
    }
    AdjTakeNote[0] = 0;
    if (dups) snprintf(AdjTakeNote, sizeof(AdjTakeNote), "%d extra bank switch line%s (they fight): removed - press Save", dups, dups == 1 ? "" : "s");
    else if (legacy) snprintf(AdjTakeNote, sizeof(AdjTakeNote), "%d switch%s in the old once-only form: put right, press Save", legacy, legacy == 1 ? "" : "es");
    else if (refit) snprintf(AdjTakeNote, sizeof(AdjTakeNote), "The bank switch did not follow this transmitter's banks: matched - press Save");
}
FLASHMEM static int AdjLinesToWrite(AdjLine *L) // the rows, back in raw units
{
    AdjRow R[ADJ_MAX];
    memcpy(R, AdjRows, sizeof(AdjRow) * (size_t)AdjN);
    for (int i = 0; i < AdjN; ++i)
    {
        const int sc = AdjFnScale(R[i].fn);
        if (sc == 1) continue;
        for (int k = 0; k < ADJ_POS_MAX; ++k) R[i].v[k] = (R[i].v[k] + sc / 2) / sc;
    }
    const int n = AdjRowsToLines(R, AdjN, L);
    for (int i = 0; i < n; ++i)
    { // as the flight controller will hold them (5 us steps), so the read-back compares equal
        AdjLine &l = L[i];
        l.enaLo = (int16_t)AdjUs(AdjStep(l.enaLo)); l.enaHi = (int16_t)AdjUs(AdjStep(l.enaHi));
        l.a1Lo = (int16_t)AdjUs(AdjStep(l.a1Lo)); l.a1Hi = (int16_t)AdjUs(AdjStep(l.a1Hi));
        l.a2Lo = (int16_t)AdjUs(AdjStep(l.a2Lo)); l.a2Hi = (int16_t)AdjUs(AdjStep(l.a2Hi));
    }
    return n;
}
static bool AdjNowAgain = false;   // asked while another read was on its way: asked again when it is done
FLASHMEM static void AdjAskNow() // the setting's present value, from the flight controller's bank in use (never another bank under a live transmitter)
{
    AdjNowKnown = false; AdjNowRow = AdjAt; AdjNowBank = 0;
    AdjShowNow();
    if (!AdjN) return;
    if (AdjStep_ != ADJ_IDLE) { AdjNowAgain = AdjStep_ == ADJ_NOW_STATUS || AdjStep_ == ADJ_NOW_READ; return; }
    AdjNowAgain = false;
    const AdjRow &r = AdjRows[AdjAt];
    AdjNowFn = r.fn;
    if (!AdjValueSource(r.fn, AdjNowRfn, AdjNowOff, AdjNowBytes, AdjNowSide)) return;
    AdjNowBank = AdjCondToBank(r, AdjBk);
    if (AdjNowBank < 0) { AdjNowBank = 0; return; }
    AdjReq = MspAsk(101, nullptr, 0); AdjStep_ = ADJ_NOW_STATUS;
}
FLASHMEM static void AdjRead()
{
    AdjBusy("Reading the adjustments (USB cable) ...");
    AdjReq = MspAsk(111, nullptr, 0); AdjStep_ = ADJ_READ_RATES; AdjTries = 0;
}
FLASHMEM static void AdjWriteLine() // the next line that differs from what the flight controller has; none left: store
{
    while (AdjLineAt < ADJ_MAX && AdjSameLine(AdjWritten[AdjLineAt], AdjAsRead[AdjLineAt])) ++AdjLineAt;
    if (AdjLineAt >= ADJ_MAX)
    {
        AdjBusy("Storing ...");
        AdjReq = MspAsk(250, nullptr, 0); AdjStep_ = ADJ_STORE;
        return;
    }
    uint8_t e[15];
    AdjEncodeLine(AdjLineAt, AdjWritten[AdjLineAt], e);
    char m[48];
    snprintf(m, sizeof(m), "Writing line %d of %d ...", AdjLineAt + 1, ADJ_MAX);
    AdjBusy(m);
    AdjReq = MspAsk(53, e, 15); AdjStep_ = ADJ_WRITE;
}
FLASHMEM void AdjustPoll()
{
    if (CurrentView != ADJUSTVIEW) { AdjStep_ = ADJ_IDLE; AdjMsgUntil = 0; return; }
    if (AdjMsgUntil && (int32_t)(millis() - AdjMsgUntil) >= 0) { AdjMsgUntil = 0; AdjBusy(""); }
    if (AdjStep_ == ADJ_IDLE)
    {
        if ((int32_t)(millis() - AdjLiveMs) >= 300) { AdjLiveMs = millis(); AdjLive(); }
        return;
    }
    if (!PipeReplyReady(AdjReq))
    {
        if (!PipeReplyLate()) return;
        if (AdjStep_ == ADJ_NOW_STATUS || AdjStep_ == ADJ_NOW_READ) { AdjStep_ = ADJ_IDLE; return; }   // (the present value: a nicety, not a failure)
        AdjFail("No answer", AdjStep_ == ADJ_READ || AdjStep_ == ADJ_READ_RATES);
        return;
    }
    const bool ok = PipeRepCode == 200;
    const bool again = (PipeRepCode == 503 || PipeRepCode == 504) && AdjTries < 5;   // the receiver was busy with the transmitter's own traffic: once more
    switch (AdjStep_)
    {
    case ADJ_READ_RATES:
    {
        uint8_t b[64];
        AdjScale = 5;
        if (ok && PipeReplyBytes(b, sizeof(b)) >= 1) AdjScale = b[0] == 6 ? 5 : 10;
        AdjReq = MspAsk(52, nullptr, 0); AdjStep_ = ADJ_READ; AdjTries = 0;
        return;
    }
    case ADJ_READ:
    {
        if (again) { ++AdjTries; AdjReq = MspAsk(52, nullptr, 0); return; }
        if (!ok) { AdjFail("Adjustments need the USB cable from the receiver\r\nto the flight controller", true); return; }
        const int n = PipeReplyBytes(AdjImg, sizeof(AdjImg));
        if (n < 14) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight sends 588)", n); AdjFail("Could not read the adjustments", true); return; }
        AdjTakeRows(AdjImg, n);
        AdjHave = true; Adj_Was_Edited = AdjTakeNote[0] != 0; AdjStep_ = ADJ_IDLE;
        AdjBusy(""); AdjHead(); AdjShow();
        if (AdjTakeNote[0]) { AdjBusy(AdjTakeNote); AdjMsgUntil = millis() + 8000; }
        AdjAskNow();
        return;
    }
    case ADJ_WRITE:
        if (again) { ++AdjTries; AdjWriteLine(); return; }
        if (!ok) { char w[40]; snprintf(w, sizeof(w), "Line %d was not written", AdjLineAt + 1); AdjFail(w, false); return; }
        AdjTries = 0;
        ++AdjLineAt;
        AdjWriteLine();   // (the next line that differs, or the store)
        return;
    case ADJ_STORE:
        if (again) { ++AdjTries; AdjReq = MspAsk(250, nullptr, 0); return; }
        if (!ok) { AdjFail("Not stored", false); return; }
        AdjTries = 0;
        AdjReq = MspAsk(52, nullptr, 0); AdjStep_ = ADJ_VERIFY;
        return;
    case ADJ_VERIFY:
    {
        if (again) { ++AdjTries; AdjReq = MspAsk(52, nullptr, 0); return; }
        if (!ok) { AdjFail("Could not read back", false); return; }
        const int n = PipeReplyBytes(AdjImg, sizeof(AdjImg));
        AdjLine L[ADJ_MAX];
        const int nl = AdjParseLines(AdjImg, n, L);
        bool same = nl == ADJ_MAX;
        for (int i = 0; same && i < nl; ++i) if (!AdjSameLine(L[i], AdjWritten[i])) same = false;
        AdjTakeRows(AdjImg, n);
        Adj_Was_Edited = AdjTakeNote[0] != 0; AdjStep_ = ADJ_IDLE;
        AdjHead(); AdjShow();
        AdjBusy(AdjTakeNote[0] ? AdjTakeNote : same ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
        AdjMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    case ADJ_NOW_STATUS:
    {
        uint8_t b[40];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        AdjStep_ = ADJ_IDLE;
        if (n < 26) return;
        if (AdjNowAgain) { AdjAskNow(); return; }
        const int cur = (AdjNowSide == 2 ? b[25] : b[23]) + 1;
        if (AdjNowBank && AdjNowBank != cur) { AdjShowNow(); return; }   // (another bank's value: not read under a live transmitter)
        AdjNowBank = 0;
        AdjReq = MspAsk(AdjNowRfn, nullptr, 0); AdjStep_ = ADJ_NOW_READ;
        return;
    }
    case ADJ_NOW_READ:
    {
        uint8_t b[128];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        AdjStep_ = ADJ_IDLE;
        if (n < AdjNowOff + AdjNowBytes) { if (AdjNowAgain) AdjAskNow(); return; }
        int32_t v = AdjNowBytes == 2 ? (int32_t)(b[AdjNowOff] | (b[AdjNowOff + 1] << 8)) : (int32_t)b[AdjNowOff];
        v *= AdjFnScale(AdjNowFn);
        AdjNowKnown = true; AdjNow = v;
        if (AdjNowAgain) { AdjAskNow(); return; }   // (the row changed meanwhile: that one's value)
        if (AdjN && AdjNowRow == AdjAt && AdjRows[AdjAt].fn == AdjNowFn)
        { // a row just added, or its setting just changed: its values start from the present one
            AdjRow &r = AdjRows[AdjAt];
            bool blank = true;
            for (int k = 0; k < ADJ_POS_MAX; ++k) if (r.v[k]) blank = false;
            if (blank) { for (int k = 0; k < ADJ_POS_MAX; ++k) r.v[k] = v; AdjShow(); return; }
        }
        AdjShowNow();
        return;
    }
    default:
        AdjStep_ = ADJ_IDLE;
        return;
    }
}
FLASHMEM void StartAdjustView() // the menu's Adjustments ...
{
    char why[120];
    if (!(BoundFlag && ModelMatched) && !BakOffline()) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page RFView", (char *)"Adjustments need the model connected,\r\nwith the USB cable from the receiver\r\nto the flight controller - or a backup\r\nmade with the cable in."); return; }
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page AdjustView");
    CurrentView = ADJUSTVIEW;
    Adj_Was_Edited = false; AdjHave = false; AdjN = 0; AdjAt = 0; AdjNowKnown = false; AdjNowRow = -1;
    AdjSeenClear(); memset(AdjBankFitted, 0, sizeof(AdjBankFitted)); AdjBankWhy[0] = 0; AdjTakeNote[0] = 0; AdjMemoN = 0;
    AdjHead();
    AdjShow();
    AdjRead();
}
FLASHMEM void EndAdjustView() // OK
{
    if (AdjStep_ != ADJ_IDLE && AdjStep_ != ADJ_NOW_STATUS && AdjStep_ != ADJ_NOW_READ) return;   // (a save runs: wait for it)
    if (Adj_Was_Edited)
    {
        AdjGather();
        if (!GetConfirmation((char *)"page AdjustView", (char *)"Discard the edited adjustments?")) { AdjHead(); AdjShow(); return; }
    }
    AdjStep_ = ADJ_IDLE; Adj_Was_Edited = false;
    RotorFlightStart();
}
FLASHMEM void AdjustWasEdited() { AdjEdited(); }
FLASHMEM void SaveAdjustments()
{
    if (!AdjHave || AdjStep_ != ADJ_IDLE) return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why))) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page AdjustView", why); AdjHead(); AdjShow(); return; }
    AdjGather();
    { char problem[240]; if (AdjRowsProblem(AdjRows, AdjN, problem, sizeof(problem))) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page AdjustView", problem); AdjHead(); AdjShow(); return; } }
    AdjLinesToWrite(AdjWritten);
    AdjLineAt = 0; AdjTries = 0;
    AdjWriteLine();
}
FLASHMEM static void AdjMove(int to)
{
    if (!AdjN) return;
    AdjGather();
    if (to < 0) to = 0;
    if (to >= AdjN) to = AdjN - 1;
    AdjAt = to;
    AdjShow();
    AdjAskNow();
}
FLASHMEM void AdjustPrevious() { AdjMove(AdjAt - 1); }
FLASHMEM void AdjustNext() { AdjMove(AdjAt + 1); }
FLASHMEM void AdjustSettingNext() // the setting box tapped: the picker page, a wheel of every setting, the row's own selected
{
    if (!AdjN || AdjStep_ != ADJ_IDLE) return;
    AdjGather();
    SendCommand((char *)"page AdjPickView");
    CurrentView = ADJPICKVIEW;
    SendText((char *)"t11", ModelName);
    SendValue((char *)"list", AdjIdxOf(AdjRows[AdjAt].fn));
}
FLASHMEM static void AdjPickLeave()
{
    SendCommand((char *)"page AdjustView");
    CurrentView = ADJUSTVIEW;
    AdjHead(); AdjShow();
}
FLASHMEM void AdjustPickOk()
{
    const uint8_t fn = AdjFnAt((int)GetValue((char *)"list"));
    AdjPickLeave();
    if (!AdjN || fn == AdjRows[AdjAt].fn || fn < 1 || fn >= ADJ_NAMES) return;
    { AdjBanks before; AdjBankRegions(AdjRows, AdjN, before);
      AdjRows[AdjAt].fn = fn;
      for (int k = 0; k < ADJ_POS_MAX; ++k) AdjRows[AdjAt].v[k] = 0;   // (the present value seeds them, when it can be read)
      if (fn == 1 || fn == 2) { if (!AdjFitBankRow(AdjAt)) { AdjRow &r = AdjRows[AdjAt]; r.kind = AK_SWITCH; r.n = 2; r.lo = 988; r.hi = 2012; r.v[0] = 1; r.v[1] = 2; } }
      if (fn == 2 || before.have) AdjRebank(before); }
    AdjEdited(); AdjShow(); AdjAskNow();
}
FLASHMEM void AdjustPickCancel() { AdjPickLeave(); }
FLASHMEM void AdjustSettingPrev() { AdjustSettingNext(); }   // (B75: both codes open the picker)
FLASHMEM static void AdjChannel(int dir)
{
    if (!AdjN) return;
    AdjGather();
    int ch = AdjRows[AdjAt].ch + dir;            // AUX1..AUX11 = channels 6..16 on this transmitter
    if (ch < 0) ch = CHANNELSUSED - 6;
    if (ch > CHANNELSUSED - 6) ch = 0;
    AdjRows[AdjAt].ch = (uint8_t)ch;
    if (AdjRows[AdjAt].fn == 1 || AdjRows[AdjAt].fn == 2) AdjFitBankRow(AdjAt);
    AdjEdited(); AdjShow();
}
FLASHMEM void AdjustChannelNext() { AdjChannel(1); }
FLASHMEM void AdjustChannelPrev() { AdjChannel(-1); }
FLASHMEM void AdjustKindTapped() // Knob -> Switch 2 -> Switch 3 -> Switch 4 -> Step up/down -> Knob, keeping what values it can; a bank switch: matched to this transmitter again
{
    if (!AdjN) return;
    AdjGather();
    AdjRow &r = AdjRows[AdjAt];
    if (r.fn == 1 || r.fn == 2)
    { // a bank switch: matched to this transmitter's banks again; what could not be matched is said
        if (AdjFitBankRow(AdjAt)) AdjEdited();
        if (!AdjBankFitted[AdjAt]) { MsgBox((char *)"page AdjustView", AdjBankWhy); AdjHead(); }
        AdjShow();
        if (AdjBankFitted[AdjAt]) { AdjBusy(AdjBankWhy[0] ? AdjBankWhy : "Matched to this transmitter's banks"); AdjMsgUntil = millis() + 5000; }
        return;
    }
    int32_t lo = r.v[0], hi = r.v[0];
    const int nv = r.kind == AK_SWITCH ? r.n : 2;
    for (int k = 0; k < nv && k < ADJ_POS_MAX; ++k) { if (r.v[k] < lo) lo = r.v[k]; if (r.v[k] > hi) hi = r.v[k]; }
    if (hi <= lo) hi = lo + 1;
    const bool travelKnown = r.kind != AK_NUDGE && r.hi > r.lo + 5;
    if (r.kind == AK_KNOB) { r.kind = AK_SWITCH; r.n = 2; if (!travelKnown || r.lo < 988) { r.lo = 988; r.hi = 2012; } }
    else if (r.kind == AK_SWITCH && r.n < 4) { r.n = (uint8_t)(r.n + 1); }
    else if (r.kind == AK_SWITCH) { r.kind = AK_NUDGE; r.n = 2; r.t[0] = 1300; r.t[1] = 1700; r.stp = 1; }
    else { r.kind = AK_KNOB; r.n = 2; r.lo = ADJ_RMIN; r.hi = ADJ_RMAX; }
    if (r.kind == AK_SWITCH) for (int k = 0; k < r.n; ++k) r.v[k] = AdjSwitchValue(lo, hi, r.n, k);
    else { r.v[0] = lo; r.v[1] = hi; }
    if (r.kind != AK_NUDGE && !r.cond) { r.ena = 0; r.enaLo = 0; r.enaHi = 0; }
    AdjEdited(); AdjShow();
}
FLASHMEM void AdjustBankTapped() // Any -> 1 -> 2 ... -> Any, among the banks the PID-bank line defines
{
    if (!AdjN) return;
    AdjGather();
    AdjRow &r = AdjRows[AdjAt];
    if (!AdjBk.have)
    {
        MsgBox((char *)"page AdjustView", (char *)"No bank switch is set up here: add a\r\n'PID bank switch (1 to 6)' adjustment\r\nfirst. Until then every adjustment\r\nholds in every bank.");
        AdjHead(); AdjShow(); return;
    }
    int bank = AdjCondToBank(r, AdjBk);
    if (bank < 0) bank = 0;
    for (int tries = 0; tries < 7; ++tries)
    {
        bank = (bank + 1) % 7;
        if (bank == 0 || AdjBk.lo[bank] || AdjBk.hi[bank]) break;
    }
    AdjBankToCond(r, bank, AdjBk);
    if (r.kind == AK_NUDGE && !r.cond) { r.cond = true; r.ena = r.ch; r.enaLo = (int16_t)ADJ_RMIN; r.enaHi = (int16_t)ADJ_RMAX; }
    AdjEdited(); AdjShow(); AdjAskNow();
}
FLASHMEM void AdjustAdd()
{
    if (!AdjHave) return;
    AdjGather();
    if (AdjN >= ADJ_MAX || AdjLinesUsed(-1) >= ADJ_MAX) { MsgBox((char *)"page AdjustView", (char *)"No room: Rotorflight holds 42 adjustments."); AdjHead(); AdjShow(); return; }
    const int at = AdjN ? AdjAt + 1 : 0;
    for (int i = AdjN; i > at; --i) { AdjRows[i] = AdjRows[i - 1]; AdjBankFitted[i] = AdjBankFitted[i - 1]; }
    AdjBankFitted[at] = false;
    AdjRow &r = AdjRows[at];
    memset(&r, 0, sizeof(r));
    r.kind = AK_KNOB; r.fn = 14; r.ch = AdjN ? AdjRows[AdjAt].ch : 1; r.n = 2; r.lo = (int16_t)ADJ_RMIN; r.hi = (int16_t)ADJ_RMAX;
    ++AdjN; AdjAt = at;
    AdjEdited(); AdjShow(); AdjAskNow();
}
FLASHMEM void AdjustRemove()
{
    if (!AdjN) return;
    AdjGather();
    if (!GetConfirmation((char *)"page AdjustView", (char *)"Remove this adjustment?")) { AdjHead(); AdjShow(); return; }
    for (int i = AdjAt; i + 1 < AdjN; ++i) { AdjRows[i] = AdjRows[i + 1]; AdjBankFitted[i] = AdjBankFitted[i + 1]; }
    --AdjN;
    if (AdjAt >= AdjN) AdjAt = AdjN ? AdjN - 1 : 0;
    AdjBankRegions(AdjRows, AdjN, AdjBk);
    AdjEdited(); AdjHead(); AdjShow(); AdjAskNow();
}

#endif
