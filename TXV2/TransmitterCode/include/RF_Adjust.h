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
// travel lo..hi mapped to min..max), a SWITCH (one value per position, the dividers between them; several lines, one per
// position), or a NUDGE (step up above a divider, down below another). A row may hold only in one BANK: the condition
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
static const int ADJ_POS_MAX = 6;   // positions a switch row may hold (a line each)
struct AdjRow
{
    uint8_t kind, fn, ch;          // ch: Rotorflight's AUX index 0.. (channel = ch + 6)
    uint8_t n;                     // switch: positions (t[0..n-2] the dividers, v[0..n-1] the values); nudge: 2 dividers in t
    int16_t t[ADJ_POS_MAX];        // dividers [us]; knob: unused (lo, hi below)
    int32_t v[ADJ_POS_MAX];        // switch: the value of each position; knob/nudge: v[0] min, v[1] max
    int16_t lo, hi;                // knob: the travel that maps to min..max
    uint8_t stp;                   // nudge: the step
    bool cond;                     // held by a condition (ena/enaLo/enaHi) rather than its own position
    uint8_t ena; int16_t enaLo, enaHi;
};
static inline int AdjUs(uint8_t b) { return 1500 + 5 * (b > 127 ? (int)b - 256 : (int)b); }
FLASHMEM static inline uint8_t AdjStep(int us) // microseconds -> Rotorflight's signed 5 us step (rounded as Math.round: half up)
{
    int st = (int)floorf((float)(us - 1500) / 5.0f + 0.5f);
    if (st < -125) st = -125;
    if (st > 125) st = 125;
    return (uint8_t)(st < 0 ? st + 256 : st);
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
FLASHMEM static int AdjLinesToRows(const AdjLine *L, int n, AdjRow *R) // the phone page's linesToRows
{
    bool used[ADJ_MAX] = {false};
    int nr = 0;
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
        { // a switch position: every line with the same setting, switch and condition that is also a fixed value
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
            r.kind = AK_SWITCH; r.fn = l.fn; r.ch = l.adj; r.n = 0;
            for (int a = 0; a < g; ++a)
            {
                used[idx[a]] = true;
                if (r.n < ADJ_POS_MAX) { if (a > 0) r.t[r.n - 1] = L[idx[a]].a1Lo; r.v[r.n] = L[idx[a]].min; ++r.n; }
            }
            r.cond = !noCond; if (r.cond) { r.ena = l.ena; r.enaLo = l.enaLo; r.enaHi = l.enaHi; }
            ++nr; continue;
        }
        used[i] = true;
        r.kind = AK_KNOB; r.fn = l.fn; r.ch = l.adj; r.n = 2; r.lo = l.a1Lo; r.hi = l.a1Hi; r.v[0] = l.min; r.v[1] = l.max;
        r.cond = !noCond; if (r.cond) { r.ena = l.ena; r.enaLo = l.enaLo; r.enaHi = l.enaHi; }
        ++nr;
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
        if (r.kind == AK_SWITCH)
        {
            for (int p = 0; p < r.n && k < ADJ_MAX; ++p)
            {
                const int lo = p == 0 ? ADJ_RMIN : r.t[p - 1], hi = p == r.n - 1 ? ADJ_RMAX : r.t[p];
                AdjLine &l = L[k++];
                l.fn = r.fn; l.adj = r.ch; l.a1Lo = (int16_t)lo; l.a1Hi = (int16_t)hi; l.a2Lo = 1500; l.a2Hi = 1500;
                if (r.cond) { l.ena = r.ena; l.enaLo = r.enaLo; l.enaHi = r.enaHi; } else { l.ena = r.ch; l.enaLo = (int16_t)lo; l.enaHi = (int16_t)hi; }
                l.min = (uint16_t)r.v[p]; l.max = (uint16_t)r.v[p]; l.stp = 0;
            }
        }
        else if (r.kind == AK_KNOB)
        {
            if (k >= ADJ_MAX) break;
            AdjLine &l = L[k++];
            l.fn = r.fn; l.adj = r.ch; l.a1Lo = r.lo; l.a1Hi = r.hi; l.a2Lo = 1500; l.a2Hi = 1500;
            if (r.cond) { l.ena = r.ena; l.enaLo = r.enaLo; l.enaHi = r.enaHi; } else { l.ena = r.ch; l.enaLo = ADJ_RMIN; l.enaHi = ADJ_RMAX; }
            l.min = (uint16_t)r.v[0]; l.max = (uint16_t)r.v[1]; l.stp = 0;
        }
        else
        {
            if (k >= ADJ_MAX) break;
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
// Which channel range means "bank N"? Off the PID-bank row (fn 2): a knob maps lo..hi to min..max linearly (Rotorflight
// rounds), a switch gives one region per position. regions[v] = {lo, hi} for v 1..6, lo == hi == 0 when none.
struct AdjBanks { bool have; uint8_t ch; int16_t lo[7], hi[7]; };
FLASHMEM static void AdjBankRegions(const AdjRow *R, int nr, AdjBanks &out)
{
    memset(&out, 0, sizeof(out));
    const AdjRow *b = nullptr;
    for (int i = 0; i < nr; ++i) if (R[i].fn == 2 && R[i].kind != AK_NUDGE) { b = &R[i]; break; }
    if (!b) return;
    out.have = true; out.ch = b->ch;
    if (b->kind == AK_SWITCH)
    {
        for (int p = 0; p < b->n; ++p)
        {
            const int lo = p == 0 ? ADJ_RMIN : b->t[p - 1], hi = p == b->n - 1 ? ADJ_RMAX : b->t[p];
            const int32_t v = b->v[p];
            if (v >= 1 && v <= 6) { out.lo[v] = (int16_t)lo; out.hi[v] = (int16_t)hi; }
        }
        return;
    }
    const int32_t n = b->v[1] - b->v[0];
    if (n <= 0) { out.have = false; return; }
    for (int32_t v = b->v[0]; v <= b->v[1]; ++v)
    { // value v is chosen where round(min + (u - lo) * n / (hi - lo)) == v
        if (v < 1 || v > 6) continue;
        const float f0 = ((float)v - 0.5f - (float)b->v[0]) / (float)n, f1 = ((float)v + 0.5f - (float)b->v[0]) / (float)n;
        const float span = (float)(b->hi - b->lo);
        int lo = (int)(floorf(((float)b->lo + f0 * span) / 5.0f + 0.5f) * 5), hi = (int)(floorf(((float)b->lo + f1 * span) / 5.0f + 0.5f) * 5);
        if (lo < b->lo) lo = b->lo;
        if (hi > b->hi) hi = b->hi;
        out.lo[v] = (int16_t)(v == b->v[0] ? ADJ_RMIN : lo); out.hi[v] = (int16_t)(v == b->v[1] ? ADJ_RMAX : hi);
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
FLASHMEM static int AdjLinesUsed(int exceptRow) // how many of the 42 lines the rows would take
{
    int k = 0;
    for (int i = 0; i < AdjN; ++i) { if (i == exceptRow || !AdjRows[i].fn) continue; k += AdjRows[i].kind == AK_SWITCH ? AdjRows[i].n : 1; }
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
    const int n = r.kind == AK_SWITCH ? r.n : 3;
    for (int k = 0; k < n - 1; ++k) if (us < r.t[k]) return k;
    return n - 1;
}
static int AdjLiveCh = -1, AdjLiveUs = -1;   // what the marker and the line last showed (AdjShow forgets them: the row may have changed)
FLASHMEM static void AdjLive() // the chosen channel's position, from this transmitter's own output: the bar's marker and the line under it
{
    if (!AdjN) { if (AdjLiveCh != -1) { AdjLiveCh = -1; AdjText("tn8", ""); } return; }
    const AdjRow &r = AdjRows[AdjAt];
    const int ch = r.ch + 6;   // 1-based channel
    const int us = (ch >= 1 && ch <= CHANNELSUSED) ? AdjFcUs(SendBuffer[ch - 1]) : -1;
    if (ch == AdjLiveCh && us == AdjLiveUs) return;
    AdjLiveCh = ch; AdjLiveUs = us;
    char c[24], b[64];
    snprintf(c, sizeof(c), "bar.mk=%d", us); SendCommand(c);
    const int k = us >= 0 ? AdjRegionOf(r, us) : -1;   // (B76, Malcolm: "nothing more than position: 988 us")
    if (k < 0) snprintf(b, sizeof(b), "Channel %d: ?", ch);
    else if (r.kind == AK_SWITCH) snprintf(b, sizeof(b), "Position %d: %d us", k + 1, us);
    else if (r.kind == AK_KNOB)
    {
        if (k != 1) snprintf(b, sizeof(b), "Outside the knob's travel: %d us", us);
        else { const long span = r.hi > r.lo ? r.hi - r.lo : 1; const long v = r.v[0] + ((r.v[1] - r.v[0]) * (long)(us - r.lo) + span / 2) / span; snprintf(b, sizeof(b), "Knob %d us: %ld", us, v); }
    }
    else snprintf(b, sizeof(b), "%s: %d us", k == 0 ? "Stepping down" : k == 2 ? "Stepping up" : "Holding", us);
    AdjText("tn8", b);
}
static void AdjGather();
static void AdjEdited();
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
    if (r.kind == AK_SWITCH) snprintf(b, sizeof(b), "Switch, %d positions", r.n); else snprintf(b, sizeof(b), "%s", r.kind == AK_KNOB ? "Knob" : "Step up / down");
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
    {
        SendCommand((char *)"bar.kind=0"); snprintf(b, sizeof(b), "bar.n=%d", r.n); SendCommand(b);
        for (int k = 0; k + 1 < r.n && k < 5; ++k) { snprintf(b, sizeof(b), "bar.d%d=%d", k, r.t[k]); SendCommand(b); }
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
        const int k = AdjRegionOf(r, tap);
        if (r.kind == AK_SWITCH) { if (k >= 0 && k < r.n && k < ADJ_POS_MAX) { char nm[8]; snprintf(nm, sizeof(nm), "tp%d", k); AdjClickBox(nm); } }
        else if (r.kind == AK_KNOB) { if (k == 1) AdjClickBox(tap < (r.lo + r.hi) / 2 ? "tk0" : "tk1"); }
        else { if (k != 1) AdjClickBox("ts0"); else AdjClickBox(tap < (r.t[0] + r.t[1]) / 2 ? "ts1" : "ts2"); }
        return;
    }
    int d[5];
    const int nd = r.kind == AK_SWITCH ? r.n - 1 : 2;
    for (int k = 0; k < nd && k < 5; ++k) { char n[10]; snprintf(n, sizeof(n), "bar.d%d", k); const int v = GetOtherValue((char *)n); d[k] = (v >= ADJ_RMIN && v <= ADJ_RMAX) ? v : -1; }
    bool changed = false;
    for (int k = 0; k < nd && k < 5; ++k)
    {
        if (d[k] < 0) continue;
        int16_t &slot = r.kind == AK_KNOB ? (k == 0 ? r.lo : r.hi) : r.t[k];
        if (slot != d[k]) { slot = (int16_t)d[k]; changed = true; }
    }
    if (!changed) return;
    AdjEdited();
    AdjShow();
}
FLASHMEM static void AdjGather() // the typed values of the row showing
{
    if (!AdjN || CurrentView != ADJUSTVIEW) return;
    AdjRow &r = AdjRows[AdjAt];
    if (r.kind == AK_KNOB) { r.v[0] = FieldNumber("tk0", 0, 65535); r.v[1] = FieldNumber("tk1", 0, 65535); }
    else if (r.kind == AK_SWITCH) { for (int k = 0; k < r.n && k < ADJ_POS_MAX; ++k) { char nm[8]; snprintf(nm, sizeof(nm), "tp%d", k); r.v[k] = FieldNumber(nm, 0, 65535); } }
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
// A knob that gives a few whole numbers - the bank switches above all (1 to 4 across the travel) - is really a set of
// zones: Rotorflight rounds the knob's position to the nearest number, so it changes at thresholds. Shown as a switch
// with one zone per number and the blobs at those thresholds (Malcolm, 8 Oct: "The blobs are at the extreme ends, but
// they should mark the thresholds between zones"). Saved as a switch - one line per zone - which Rotorflight treats the same.
FLASHMEM static void AdjKnobToZones(AdjRow &r)
{
    if (r.kind != AK_KNOB || r.v[1] <= r.v[0] || r.v[1] - r.v[0] > ADJ_POS_MAX - 1 || r.v[0] < 0) return;
    const int32_t mn = r.v[0], mx = r.v[1];
    const int n = (int)(mx - mn) + 1;
    const float span = (float)(r.hi - r.lo);
    int16_t t[ADJ_POS_MAX];
    for (int k = 0; k + 1 < n; ++k)
    { // the threshold before the number mn + k + 1
        const float f = ((float)(k + 1) - 0.5f) / (float)(mx - mn);
        int us = (int)(floorf(((float)r.lo + f * span) / 5.0f + 0.5f) * 5);
        if (us <= ADJ_RMIN) us = ADJ_RMIN + 5;
        if (us >= ADJ_RMAX) us = ADJ_RMAX - 5;
        t[k] = (int16_t)us;
    }
    r.kind = AK_SWITCH; r.n = (uint8_t)n;
    for (int k = 0; k < n; ++k) { r.v[k] = mn + k; if (k + 1 < n) r.t[k] = t[k]; }
}
FLASHMEM static void AdjTakeRows(const uint8_t *b, int n) // the 52 image -> rows in page units
{
    AdjLine L[ADJ_MAX];
    const int nl = AdjParseLines(b, n, L);
    for (int i = 0; i < ADJ_MAX; ++i) { if (i < nl) AdjAsRead[i] = L[i]; else AdjBlank(AdjAsRead[i]); }
    AdjN = AdjLinesToRows(L, nl, AdjRows);
    for (int i = 0; i < AdjN; ++i)
    {
        const int sc = AdjFnScale(AdjRows[i].fn);
        if (sc != 1) for (int k = 0; k < ADJ_POS_MAX; ++k) AdjRows[i].v[k] *= sc;
        AdjKnobToZones(AdjRows[i]);
    }
    AdjBankRegions(AdjRows, AdjN, AdjBk);
    if (AdjAt >= AdjN) AdjAt = AdjN ? AdjN - 1 : 0;
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
    return AdjRowsToLines(R, AdjN, L);
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
        AdjHave = true; Adj_Was_Edited = false; AdjStep_ = ADJ_IDLE;
        AdjBusy(""); AdjHead(); AdjShow();
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
        Adj_Was_Edited = false; AdjStep_ = ADJ_IDLE;
        AdjHead(); AdjShow();
        AdjBusy(same ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
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
    if (!(BoundFlag && ModelMatched)) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page RFView", (char *)"Adjustments need the model connected,\r\nwith the USB cable from the receiver\r\nto the flight controller."); return; }
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page AdjustView");
    CurrentView = ADJUSTVIEW;
    Adj_Was_Edited = false; AdjHave = false; AdjN = 0; AdjAt = 0; AdjNowKnown = false; AdjNowRow = -1;
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
    AdjRows[AdjAt].fn = fn;
    for (int k = 0; k < ADJ_POS_MAX; ++k) AdjRows[AdjAt].v[k] = 0;   // (the present value seeds them, when it can be read)
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
    AdjEdited(); AdjShow();
}
FLASHMEM void AdjustChannelNext() { AdjChannel(1); }
FLASHMEM void AdjustChannelPrev() { AdjChannel(-1); }
FLASHMEM void AdjustKindTapped() // Knob -> Switch 2 -> Switch 3 -> Step up/down -> Knob, keeping what values it can
{
    if (!AdjN) return;
    AdjGather();
    AdjRow &r = AdjRows[AdjAt];
    const bool isBank = r.fn == 1 || r.fn == 2;
    int32_t lo = r.v[0], hi = r.v[0];
    const int nv = r.kind == AK_SWITCH ? r.n : 2;
    for (int k = 0; k < nv && k < ADJ_POS_MAX; ++k) { if (r.v[k] < lo) lo = r.v[k]; if (r.v[k] > hi) hi = r.v[k]; }
    if (r.kind == AK_KNOB) { r.kind = AK_SWITCH; r.n = 2; r.t[0] = 1500; r.v[0] = isBank ? 1 : lo; r.v[1] = isBank ? 2 : hi; }
    else if (r.kind == AK_SWITCH && r.n == 2) { r.kind = AK_SWITCH; r.n = 3; r.t[0] = 1290; r.t[1] = 1710; r.v[2] = isBank ? 3 : hi; r.v[1] = isBank ? 2 : (lo + hi) / 2; r.v[0] = isBank ? 1 : lo; }
    else if (r.kind == AK_SWITCH) { r.kind = AK_NUDGE; r.n = 2; r.t[0] = 1300; r.t[1] = 1700; r.stp = 1; r.v[0] = lo; r.v[1] = hi > lo ? hi : lo + 10; }
    else { r.kind = AK_KNOB; r.n = 2; r.lo = ADJ_RMIN; r.hi = ADJ_RMAX; r.v[0] = isBank ? 1 : lo; r.v[1] = isBank ? 6 : (hi > lo ? hi : lo); }
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
        MsgBox((char *)"page AdjustView", (char *)"No bank switch is set up here: add a\r\n'PID bank switch (1 to 6)' adjustment\r\nfirst, with one value per position.\r\nUntil then every adjustment holds in\r\nevery bank.");
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
    if (AdjN >= ADJ_MAX || AdjLinesUsed(-1) >= ADJ_MAX) { MsgBox((char *)"page AdjustView", (char *)"No room: Rotorflight holds 42 lines\r\n(a switch takes one per position)."); AdjHead(); AdjShow(); return; }
    const int at = AdjN ? AdjAt + 1 : 0;
    for (int i = AdjN; i > at; --i) AdjRows[i] = AdjRows[i - 1];
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
    for (int i = AdjAt; i + 1 < AdjN; ++i) AdjRows[i] = AdjRows[i + 1];
    --AdjN;
    if (AdjAt >= AdjN) AdjAt = AdjN ? AdjN - 1 : 0;
    AdjBankRegions(AdjRows, AdjN, AdjBk);
    AdjEdited(); AdjHead(); AdjShow(); AdjAskNow();
}

#endif
