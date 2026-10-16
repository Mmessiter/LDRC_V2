// B104 (Malcolm, 16 Oct 2026: "The one of these that strikes me as most useful at the field is the sliders for adjusting
// settings ... Let's implement it!"): EASY TUNING on the transmitter, the phone app's page (RXV2 data/rotorflight-easy.html)
// with its sliders and its sums line for line, over the Bluetooth pipe (page 81, EasyView, hmi/easy_pages.py):
//   Start: one slider for the governor's spool-up time, startup time and handover throttle (MSP 142/143 bytes 3-4, 1-2 and
//     19: the same for every bank). Its save restarts the flight controller (68), as the phone's does: they apply at boot.
//     The switch under it turns on PID spool-up in every bank (MSP 148/149 byte 15 bit 4, each bank chosen with 210, the
//     transmitter's bank chosen again after).
//   Agility and Stick feel: the full-stick rate and the expo of roll, pitch and yaw in the rates bank in use (MSP 111/204;
//     the Rotorflight, Actual and Quickrates types - the others are left to the Rates page, as on the phone).
//   Cyclic and Tail: softer or sharper, P I D F of roll and pitch (or of yaw) times 0.7 to 1.3 in the PID bank in use (112/202).
// Every slider is RELATIVE: its centre is the model's numbers at its last backup - the transmitter's own backup on the card
// (RF_Backup.h BakBlock); with none, the numbers the page opened with. Each part is written, stored (250) and read back.
// Two things the phone did that neither does now (RXV2 0.9.894): a slider that was not moved never rewrites its numbers
// through the slider's 5 % grid (moving Cyclic used to round the tail's gains too, and the tick the start settings), and a
// governor mode or throttle type outside Rotorflight's lists is never written back (B103). Like the transmitter's other
// pages it edits the banks the transmitter is on, and only while the flight controller is on them too (B102). It needs the
// model: as on the phone, the backup is the sliders' centre, not a stand-in for the model.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_EASY_H
#define RF_EASY_H

// ---------------------------------------------------------------- the phone's sums (rotorflight-easy.html, app.js)
// JavaScript's Math.round is floor(x + 0.5): so here too, or a half would round the other way and the two would disagree.
FLASHMEM static long EzRound(double x) { const double y = x + 0.5; long t = (long)y; if ((double)t > y) --t; return t; }
FLASHMEM static long EzClamp(long v, long lo, long hi) { return v < lo ? lo : v > hi ? hi : v; }
FLASHMEM static int EzClamp5(double x) { return (int)EzClamp(EzRound(x / 5) * 5, 0, 100); }
// The sliders stand on steps of 5, so the phone's Math.pow(2, (v - 50) / 50) takes 21 values, and its Math.log2 is only ever
// rounded to a step: both are the phone's own numbers here, printed by node (no pow and log2 on the Teensy: their tables
// would take 5 kB of RAM1). EZ_TWO[v / 5] = 2^((v - 50) / 50); the steps' boundaries EZ_TH[m - 1] = 2^((2m - 21) / 20).
static const double EZ_TWO[21] PROGMEM = {0.50000000000000000, 0.53588673126814657, 0.57434917749851744, 0.61557220667245816, 0.65975395538644710,
    0.70710678118654746, 0.75785828325519899, 0.81225239635623558, 0.87055056329612412, 0.93303299153680741, 1.0000000000000000,
    1.0717734625362931, 1.1486983549970351, 1.2311444133449163, 1.3195079107728942, 1.4142135623730951, 1.5157165665103980,
    1.6245047927124709, 1.7411011265922482, 1.8660659830736148, 2.0000000000000000};
static const double EZ_TH[20] PROGMEM = {0.51763246192068879, 0.55478473603392253, 0.59460355750136051, 0.63728031365963100, 0.68302012837719772,
    0.73204284797281272, 0.78458409789675077, 0.84089641525371461, 0.90125046261083019, 0.96593632892484549, 1.0352649238413776,
    1.1095694720678451, 1.1892071150027210, 1.2745606273192620, 1.3660402567543954, 1.4640856959456254, 1.5691681957935015,
    1.6817928305074292, 1.8025009252216604, 1.9318726578496910};
// What Agility and Stick feel move, by rates type (app.js feelModel): ROTORFLIGHT (6) the rate byte, 5 deg/s a step;
// ACTUAL (4) and QUICKRATES (5) the max rate byte, 10 deg/s a step, the centre sensitivity kept in proportion; the expo
// byte after the rate's. Betaflight, Raceflight and KISS are not covered: their full-stick rate is a sum of two numbers.
struct EzFeel { int rateSlot, sc, centreSlot, expoSlot; };
FLASHMEM static bool EzFeelModel(uint8_t t, EzFeel &m)
{
    if (t == 6) { m.rateSlot = 0; m.sc = 5; m.centreSlot = -1; m.expoSlot = 1; return true; }
    if (t == 4 || t == 5) { m.rateSlot = 2; m.sc = 10; m.centreSlot = 0; m.expoSlot = 1; return true; }
    return false;
}
FLASHMEM static int EzRateOf(const uint8_t *b, int ax) { EzFeel m; return EzFeelModel(b[0], m) ? b[1 + ax * 6 + m.rateSlot] * m.sc : -1; }
FLASHMEM static int EzExpoOf(const uint8_t *b, int ax) { EzFeel m; return EzFeelModel(b[0], m) ? b[1 + ax * 6 + m.expoSlot] : -1; }
FLASHMEM static void EzSetRate(uint8_t *b, int ax, int rate)
{
    EzFeel m;
    if (!EzFeelModel(b[0], m)) return;
    const int o = 1 + ax * 6, was = b[o + m.rateSlot];
    const int now = (int)EzClamp(EzRound((double)rate / m.sc), 0, 255);
    if (m.centreSlot >= 0 && was > 0) b[o + m.centreSlot] = (uint8_t)EzClamp(EzRound((double)b[o + m.centreSlot] * now / was), 0, 255);
    b[o + m.rateSlot] = (uint8_t)now;
}
FLASHMEM static void EzSetExpo(uint8_t *b, int ax, int expo) { EzFeel m; if (EzFeelModel(b[0], m)) b[1 + ax * 6 + m.expoSlot] = (uint8_t)EzClamp(expo, 0, 100); }
// Relative slider maths: 50 is the centre, the ends are half and double (v: 0, 5 ... 100)
FLASHMEM static double EzRelScale(double base, int v) { return base * EZ_TWO[EzClamp(v / 5, 0, 20)]; }
FLASHMEM static int EzRelPos(double base, double val) // round((50 + 50 log2(val / base)) / 5) * 5, from 0 to 100
{
    if (!(base > 0 && val > 0)) return 50;
    const double r = val / base;
    int k = 0;
    for (int j = 1; j <= 20; ++j)
        if (r >= EZ_TH[j - 1]) k = j;
    return k * 5;
}
// ---------------------------------------------------------------- what was read, and the sliders' centres
static const int EZ_GOV_MIN = 42, EZ_RATES_MIN = 25, EZ_PID_MIN = 34;
DMAMEM static uint8_t EzGov[64], EzRates[48], EzPid[48], EzOut[64];
static int EzGovN = 0, EzRatesN = 0, EzPidN = 0, EzOutN = 0;
static double EzBaseSpool = 0, EzBaseStart = 0;               // Start's centre: spool-up and startup time (s) ...
static int EzBaseHand = 0, EzBaseRp = 0, EzBaseYaw = 0, EzBaseExpo = 0;   // ... and handover (%); Agility's (deg/s), Stick feel's
static uint16_t EzBasePid[12];                                 // Cyclic's and Tail's centre: P I D F of roll, pitch and yaw
static bool EzBackupCentre = false;                            // every centre is the backup's (else the opening numbers: said)
static int EzPos[5] = {50, 50, 50, 0, 0};                      // Start, Agility, Stick feel 0..100; Cyclic, Tail -30..30 (%)
static bool EzMoved[5] = {false, false, false, false, false};   // moved since the read: only these rewrite their numbers
static bool EzSpool = true, EzSpoolTouched = false;            // the phone's tick "Also switch on PID spool-up", on at first
static bool EzHave = false, EzRatesFeel = false, Ez_Was_Edited = false;
enum { EZ_IDLE = 0, EZ_R_STATUS, EZ_R_GOV, EZ_R_RATES, EZ_R_PID,
       EZ_S_STATUS, EZ_S_PID, EZ_S_PID_STORE, EZ_S_PID_BACK, EZ_S_RATES, EZ_S_RATES_STORE, EZ_S_RATES_BACK,
       EZ_S_WALK_SEL, EZ_S_WALK_READ, EZ_S_WALK_WRITE, EZ_S_WALK_HOME,
       EZ_S_GOV, EZ_S_GOV_STORE, EZ_S_REBOOT, EZ_S_WAIT, EZ_S_GOV_BACK, EZ_S_STORE, EZ_PUT_BACK };
enum { EZ_P_PID = 0, EZ_P_RATES, EZ_P_WALK, EZ_P_GOV, EZ_P_STORE, EZ_P_END };   // the parts of a save, in the phone's order
enum { EZ_FEEL = 1, EZ_AGILITY = 2, EZ_START = 4 };
static int EzStep = EZ_IDLE, EzReq = 0, EzTries = 0, EzBoot = 0, EzWalk = 0, EzPidBanks = 6, EzSpoolOn = 0, EzDone = 0, EzBad = 0;
static uint32_t EzWaitUntil = 0, EzMsgUntil = 0;
static uint8_t EzLastFn = 0, EzLastData[64];
static int EzLastLen = 0;
static bool EzQuiet = false, EzRereadWanted = false, EzWalked = false, EzGone = false;
static char EzFailMsg[180];

FLASHMEM static int EzU16(const uint8_t *b, int o) { return b[o] | (b[o + 1] << 8); }
FLASHMEM static int EzPidWord(int i) { return EzU16(EzPid, i * 2); }
FLASHMEM static int EzTxBank() { return Bank >= 1 && Bank <= 6 ? Bank - 1 : 0; }
FLASHMEM static int EzTxRate() { return DualRateInUse >= 1 && DualRateInUse <= 6 ? DualRateInUse - 1 : 0; }

// ---------------------------------------------------------------- the sliders (app startNums, feelRate, nudgedWords ...)
struct EzStartN { int spool, hand, start; };
FLASHMEM static EzStartN EzStartNums(int v)
{
    const double k = EZ_TWO[20 - EzClamp(v / 5, 0, 20)];   // Math.pow(2, (50 - v) / 50)
    EzStartN n;
    n.spool = (int)EzRound(EzBaseSpool * k); if (n.spool < 1) n.spool = 1;
    n.hand = (int)EzClamp(EzRound(EzBaseHand + (v - 50) * 0.3), 10, 50);
    n.start = (int)EzRound(EzBaseStart * k); if (n.start < 1) n.start = 1;
    return n;
}
FLASHMEM static int EzStartFeel(double spool) // clamp5(50 - 50 log2(spool / centre))
{
    if (!(EzBaseSpool > 0 && spool > 0)) return 50;
    const double r = spool / EzBaseSpool;
    int k = 0;
    for (int j = 1; j <= 20 && r <= EZ_TH[20 - j]; ++j) k = j;
    return k * 5;
}
FLASHMEM static int EzRateStep() { EzFeel m; return (EzRatesN && EzFeelModel(EzRates[0], m)) ? m.sc : 5; }
FLASHMEM static int EzR5(double x) { const int st = EzRateStep(); const long r = EzRound(x / st) * st; return (int)(r > st ? r : st); }
FLASHMEM static int EzAgileRp(int v) { return EzR5(EzRelScale(EzBaseRp, v)); }
FLASHMEM static int EzAgileYaw(int v) { return EzR5(EzRelScale(EzBaseYaw, v)); }
FLASHMEM static int EzExpoAt(int v) { return (int)EzClamp(EzRound(EzBaseExpo - (v - 50) * 0.7), 0, 100); }
FLASHMEM static int EzExpoFeel(int e) { return EzClamp5(50 + (EzBaseExpo - e) / 0.7); }
FLASHMEM static int EzNudgePos(bool tail) // where the bank's gains sit against the centre: the slider's resting place
{
    double sum = 0;
    int n = 0;
    for (int i = tail ? 8 : 0; i < (tail ? 12 : 8); ++i)
        if (EzBasePid[i] > 0) { sum += (double)EzPidWord(i) / EzBasePid[i]; ++n; }
    return n ? (int)EzClamp(EzRound((sum / n - 1) * 100 / 5) * 5, -30, 30) : 0;
}
FLASHMEM static int EzBaseWord(int i) { return EzBasePid[i] ? EzBasePid[i] : EzPidWord(i); }
FLASHMEM static int EzNudged(int i) // word i (0-11: P I D F of roll, pitch, yaw) at its slider's place
{
    const double f = 1 + (i < 8 ? EzPos[3] : EzPos[4]) / 100.0;
    return (int)EzClamp(EzRound(EzBaseWord(i) * f), 0, 1000);
}
// The bytes each part writes: what was read, with the moved sliders' bytes changed and nothing else
FLASHMEM static void EzPidBytes(uint8_t *b)
{
    memcpy(b, EzPid, (size_t)EzPidN);
    for (int i = 0; i < 12; ++i)
    {
        if (!EzMoved[i < 8 ? 3 : 4]) continue;
        const int w = EzNudged(i);
        b[i * 2] = (uint8_t)w; b[i * 2 + 1] = (uint8_t)(w >> 8);
    }
}
FLASHMEM static void EzRatesBytes(uint8_t *b)
{
    memcpy(b, EzRates, (size_t)EzRatesN);
    const int rp = EzAgileRp(EzPos[1]), yaw = EzAgileYaw(EzPos[1]), e = EzExpoAt(EzPos[2]);
    for (int ax = 0; ax < 3; ++ax)
    {
        if (EzMoved[1]) EzSetRate(b, ax, ax == 2 ? yaw : rp);
        if (EzMoved[2]) EzSetExpo(b, ax, e);
    }
}
FLASHMEM static void EzGovBytes(uint8_t *b)
{
    memcpy(b, EzGov, (size_t)EzGovN);
    if (!EzMoved[0]) return;
    const EzStartN n = EzStartNums(EzPos[0]);
    const int st = n.start * 10, sp = n.spool * 10;
    b[1] = (uint8_t)st; b[2] = (uint8_t)(st >> 8); b[3] = (uint8_t)sp; b[4] = (uint8_t)(sp >> 8); b[19] = (uint8_t)n.hand;
}
FLASHMEM static bool EzNeedPid() { return EzMoved[3] || EzMoved[4]; }
FLASHMEM static bool EzNeedRates() { return EzRatesFeel && (EzMoved[1] || EzMoved[2]); }
FLASHMEM static bool EzNeedGov() { return EzMoved[0]; }
FLASHMEM static bool EzNeedWalk() { return EzSpool && (EzMoved[0] || EzSpoolTouched); }   // (the phone: whenever its Start changed, with the tick on)
FLASHMEM static bool EzAnything() { return EzNeedPid() || EzNeedRates() || EzNeedGov() || EzNeedWalk(); }
bool EasyHoldsBanks() { return EzStep != EZ_IDLE && EzStep < EZ_S_GOV; }   // Switches.h: the bank switch held while the banks are read, written or walked

// ---------------------------------------------------------------- the page
FLASHMEM static void EzBusy(const char *msg)
{
    if (CurrentView != EASYVIEW) return;
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg) SendText((char *)"busy", (char *)msg);
}
FLASHMEM static void EzEndHint(char *out, size_t n, int v, int lo, int hi)
{
    if (v <= lo || v >= hi) strncat(out, PSTR(" At the end of its travel: a backup re-centres it."), n - strlen(out) - 1);
}
FLASHMEM static void EzNoteFor(int k) // the numbers a slider gives (the phone's line under each slider)
{
    char m[230];
    m[0] = 0;
    if (k == 0)
    {
        const EzStartN s = EzStartNums(EzPos[0]);
        snprintf(m, sizeof(m), PSTR("Full head speed in about %d s (spool-up %d, handover %d %%, startup %d)."), s.spool, s.spool, s.hand, s.start);
        EzEndHint(m, sizeof(m), EzPos[0], 0, 100);
    }
    else if (k == 1)
    {
        snprintf(m, sizeof(m), PSTR("Roll and pitch %d deg/s, yaw %d deg/s at full stick."), EzAgileRp(EzPos[1]), EzAgileYaw(EzPos[1]));
        EzEndHint(m, sizeof(m), EzPos[1], 0, 100);
    }
    else if (k == 2)
    {
        snprintf(m, sizeof(m), PSTR("Expo %d on roll, pitch and yaw."), EzExpoAt(EzPos[2]));
        EzEndHint(m, sizeof(m), EzPos[2], 0, 100);
    }
    else
    {
        const bool tail = k == 4;
        const int pct = EzPos[k];
        if (pct == 0)
            snprintf(m, sizeof(m), "%s", EzBackupCentre ? PSTR("Back at the last backup's numbers.") : PSTR("Back at the numbers it opened with."));
        else
        {
            static const char *const axis[3] = {"roll", "pitch", "yaw"};
            int n = snprintf(m, sizeof(m), PSTR("%s gains %s%d %%:"), tail ? "Tail" : "Cyclic", pct > 0 ? "+" : "", pct);
            for (int a = tail ? 2 : 0; a < (tail ? 3 : 2) && n < (int)sizeof(m); ++a)
            {
                const int p = a * 4, d = a * 4 + 2;   // (P and D of the axis: words 0 and 2 of its four)
                n += snprintf(m + n, sizeof(m) - n, PSTR("%s %s P %d->%d, D %d->%d"), a == (tail ? 2 : 0) ? "" : ";", axis[a], EzBaseWord(p), EzNudged(p), EzBaseWord(d), EzNudged(d));
            }
            if (pct <= -30 || pct >= 30) { strncat(m, ".", sizeof(m) - strlen(m) - 1); EzEndHint(m, sizeof(m), pct, -30, 30); }   // (two lines at most: the hint instead of "I and F likewise")
            else strncat(m, PSTR(" (I and F likewise)."), sizeof(m) - strlen(m) - 1);
        }
    }
    SendText((char *)"note", m);
}
FLASHMEM static void EzShowSliders()
{
    char nm[8], c[16];
    for (int k = 0; k < 5; ++k)
    {
        snprintf(nm, sizeof(nm), "s%d", k);
        SendValue(nm, k < 3 ? EzPos[k] / 5 : (EzPos[k] + 30) / 5);
    }
    SendValue((char *)"sw", EzSpool ? 1 : 0);
    static const char *const agile[8] = {"lA", "lE", "s1", "s2", "e1L", "e1R", "e2L", "e2R"};   // (rates types the sliders do not cover: their rows go)
    for (const char *n : agile) { snprintf(c, sizeof(c), "vis %s,%d", n, EzRatesFeel ? 1 : 0); SendCommand(c); }
}
FLASHMEM static void EzHead()
{
    SendText((char *)"t11", ModelName);
    ShowRFBank();
    ShowRFRate();
    SendCommand((char *)(Ez_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void EzOpeningNote() // what the page says when it has the bank's numbers
{
    if (!EzRatesFeel)
        SendText((char *)"note", (char *)PSTR("This bank uses the Betaflight, Raceflight or KISS rates type, which the sliders do not cover: use the Rates page."));
    else if (!EzBackupCentre)
        SendText((char *)"note", (char *)PSTR("Not in a backup yet, so the sliders are centred on the numbers the page opened with. A backup sets their centre."));
    else
        SendText((char *)"note", (char *)"");
}
FLASHMEM static void EzShowAll() { EzHead(); EzShowSliders(); }   // (after a box: the page as it was)
FLASHMEM static void EzEdited() { if (!Ez_Was_Edited) { Ez_Was_Edited = true; SendCommand((char *)"vis b3,1"); } }

// The sliders' places from what the flight controller holds (the phone's reflect). fresh: the centres too - from the
// backup when it has the bank's numbers, else from these (kept after a save, so a slider still shows how far it has come).
FLASHMEM static void EzReflect(bool fresh)
{
    EzFeel m;
    EzRatesFeel = EzFeelModel(EzRates[0], m);
    if (fresh)
    {
        uint8_t b[64];
        int n = 0;
        bool file = BakHaveFile();
        if (file && BakBlock(142, -1, b, sizeof(b), n) && n >= EZ_GOV_MIN) { EzBaseSpool = EzU16(b, 3) / 10.0; EzBaseHand = b[19]; EzBaseStart = EzU16(b, 1) / 10.0; }
        else { EzBaseSpool = EzU16(EzGov, 3) / 10.0; EzBaseHand = EzGov[19]; EzBaseStart = EzU16(EzGov, 1) / 10.0; file = false; }
        if (EzRatesFeel)
        {
            if (file && BakBlock(111, EzTxRate(), b, sizeof(b), n) && n >= EZ_RATES_MIN && EzFeelModel(b[0], m)) { EzBaseRp = EzRateOf(b, 0); EzBaseYaw = EzRateOf(b, 2); EzBaseExpo = EzExpoOf(b, 0); }
            else { EzBaseRp = EzRateOf(EzRates, 0); EzBaseYaw = EzRateOf(EzRates, 2); EzBaseExpo = EzExpoOf(EzRates, 0); file = false; }
        }
        if (file && BakBlock(112, EzTxBank(), b, sizeof(b), n) && n >= 24) { for (int i = 0; i < 12; ++i) EzBasePid[i] = (uint16_t)EzU16(b, i * 2); }
        else { for (int i = 0; i < 12; ++i) EzBasePid[i] = (uint16_t)EzPidWord(i); file = false; }
        EzBackupCentre = file;
    }
    EzPos[0] = EzStartFeel(EzU16(EzGov, 3) / 10.0);
    if (EzRatesFeel) { EzPos[1] = EzRelPos(EzBaseRp, EzRateOf(EzRates, 0)); EzPos[2] = EzExpoFeel(EzExpoOf(EzRates, 0)); }
    EzPos[3] = EzNudgePos(false);
    EzPos[4] = EzNudgePos(true);
    for (bool &mv : EzMoved) mv = false;
    EzSpoolTouched = false;
    Ez_Was_Edited = false;
}

// ---------------------------------------------------------------- the pipe
FLASHMEM static void EzAsk(uint8_t fn, const uint8_t *data, int len, int next)
{
    EzLastFn = fn; EzLastLen = len > (int)sizeof(EzLastData) ? (int)sizeof(EzLastData) : len;
    if (data && EzLastLen > 0) memcpy(EzLastData, data, (size_t)EzLastLen);
    EzReq = MspAsk(fn, data, len); EzStep = next; EzTries = 0;
}
FLASHMEM static void EzSelect(int bank, int next) { uint8_t d = (uint8_t)(bank & 0x7F); EzAsk(210, &d, 1, next); }   // a PID bank
FLASHMEM static void EzRead()
{
    EzHave = false; EzRereadWanted = false;
    BlockBankChanges = true;
    char m[56];
    snprintf(m, sizeof(m), PSTR("Reading bank %d from the flight controller ..."), Bank);
    EzBusy(m);
    EzAsk(101, nullptr, 0, EZ_R_STATUS);
}
FLASHMEM static void EzReadFail(const char *what, bool reply) // a read that failed: said, and back to the menu (nothing to slide)
{
    char m[180];
    if (reply) snprintf(m, sizeof(m), "%s:\r\n%.110s", what, PipeRepCode ? PipeRepBody : PSTR("the screen could not ask (no Bluetooth)"));
    else snprintf(m, sizeof(m), "%s", what);
    EzStep = EZ_IDLE; BlockBankChanges = false; EzBusy("");
    if (CurrentView != EASYVIEW) return;
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)"page EasyView", m);
    RotorFlightStart();
}
FLASHMEM static void EzWords(char *out, size_t n, int mask) // "Feel, Agility, Start"
{
    static const char *const w[3] = {"Feel", "Agility", "Start"};
    out[0] = 0;
    for (int i = 0; i < 3; ++i)
        if (mask & (1 << i)) { if (out[0]) strncat(out, ", ", n - strlen(out) - 1); strncat(out, w[i], n - strlen(out) - 1); }
}
FLASHMEM static void EzFinish(const char *box) // the end of a save: a box when something is wrong, else the good word for a moment
{
    EzStep = EZ_IDLE; BlockBankChanges = false;
    const bool quiet = EzQuiet;
    EzQuiet = false;
    EzBusy("");
    if (quiet || CurrentView != EASYVIEW) return;
    if (box)
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page EasyView", (char *)box);
        EzShowAll();
        if (EzRereadWanted) EzRead();   // (the bank switch moved meanwhile)
        return;
    }
    char d[40], m[150];
    EzWords(d, sizeof(d), EzDone);
    const char *s = EzSpoolOn == 1 ? "" : "s";
    if (d[0] && EzSpoolOn > 0) snprintf(m, sizeof(m), PSTR("Saved, and read back the same: %s.\r\nPID spool-up switched on in %d bank%s."), d, EzSpoolOn, s);
    else if (d[0]) snprintf(m, sizeof(m), PSTR("Saved, and read back the same: %s.%s"), d, EzWalked ? PSTR("\r\nPID spool-up was on in every bank already.") : "");
    else if (EzSpoolOn > 0) snprintf(m, sizeof(m), PSTR("PID spool-up switched on in %d bank%s, and stored."), EzSpoolOn, s);
    else snprintf(m, sizeof(m), PSTR("PID spool-up was on in every bank already."));
    EzShowAll();
    EzOpeningNote();
    EzBusy(m);
    EzMsgUntil = millis() + 4000;
    PlaySound(BEEPCOMPLETE);
    if (EzRereadWanted) { EzMsgUntil = 0; EzRead(); return; }
    RfSavedThenLeave(EASYVIEW);   // B102: OK's "Save now?" closes the page once saved
}
FLASHMEM static void EzFail(const char *what) // a save that stopped part way: the transmitter's bank chosen again first if the walk had left it
{
    char d[40];
    EzWords(d, sizeof(d), EzDone);
    snprintf(EzFailMsg, sizeof(EzFailMsg), PSTR("%s%s%sNot saved: %s:\r\n%.60s\r\nOpen PIDs, Rates and Governor\r\nto see what it holds."), d[0] ? "Saved: " : "", d, d[0] ? ".\r\n" : "", what,
             PipeRepCode ? PipeRepBody : PSTR("the screen could not ask (no Bluetooth)"));
    if (EzStep >= EZ_S_WALK_SEL && EzStep <= EZ_S_WALK_WRITE) { EzBusy(PSTR("Choosing the transmitter's bank again ...")); EzSelect(EzTxBank(), EZ_PUT_BACK); return; }
    EzFinish(EzFailMsg);
}
// One part of a save after another: Feel, Agility, PID spool-up in every bank, Start (the phone's order); then the verdict
FLASHMEM static void EzPart(int p)
{
    for (; p < EZ_P_END; ++p)
    {
        if (p == EZ_P_PID && EzNeedPid()) { EzPidBytes(EzOut); EzOutN = EzPidN; EzBusy(PSTR("Writing the PIDs ...")); EzAsk(202, EzOut, EzOutN, EZ_S_PID); return; }
        if (p == EZ_P_RATES && EzNeedRates()) { EzRatesBytes(EzOut); EzOutN = EzRatesN; EzBusy(PSTR("Writing the rates ...")); EzAsk(204, EzOut, EzOutN, EZ_S_RATES); return; }
        if (p == EZ_P_WALK && EzNeedWalk()) { EzWalk = 0; EzBusy(PSTR("Switching on PID spool-up in every bank ...")); EzSelect(0, EZ_S_WALK_SEL); return; }
        if (p == EZ_P_GOV && EzNeedGov())
        {
            BlockBankChanges = false;   // (the governor's settings are the same for every bank: the bank switch is free again)
            EzGovBytes(EzOut); EzOutN = EzGovN;
            EzBusy(PSTR("Writing the start settings ..."));
            EzAsk(143, EzOut, EzOutN, EZ_S_GOV);
            return;
        }
        if (p == EZ_P_STORE && EzNeedWalk() && !EzNeedGov()) { EzAsk(250, nullptr, 0, EZ_S_STORE); return; }   // (the tick alone: stored; no restart for it)
    }
    EzReflect(false);   // the sliders where the numbers now are, the centres kept
    if (EzBad || EzGone)
    {
        char bad[40], good[40], m[180];
        EzWords(bad, sizeof(bad), EzBad);
        EzWords(good, sizeof(good), EzDone);
        if (EzGone) snprintf(m, sizeof(m), PSTR("Start was written and stored, but the\r\nflight controller has not come back\r\nfrom its restart. Check it, then\r\nlook at Governor (global).%s%s%s"), good[0] ? PSTR("\r\nRead back the same: ") : "", good, good[0] ? "." : "");
        else snprintf(m, sizeof(m), PSTR("Saved, but read back DIFFERENT:\r\n%s. Open that page and check.%s%s%s"), bad, good[0] ? PSTR("\r\nRead back the same: ") : "", good, good[0] ? "." : "");
        EzFinish(m);
        return;
    }
    EzFinish(nullptr);
}
FLASHMEM static void EzNextBank() // the walk: the next bank, or the transmitter's again at the end
{
    if (++EzWalk < EzPidBanks) { EzSelect(EzWalk, EZ_S_WALK_SEL); return; }
    EzSelect(EzTxBank(), EZ_S_WALK_HOME);
}
FLASHMEM void EasyPoll()
{
    if (CurrentView != EASYVIEW)
    {
        if (EzStep == EZ_IDLE) { EzMsgUntil = 0; return; }
        if (EzStep >= EZ_S_WALK_SEL && EzStep <= EZ_S_WALK_WRITE) { EzQuiet = true; EzSelect(EzTxBank(), EZ_PUT_BACK); }   // (the page left mid-walk: the bank chosen again, quietly)
        else if (EzStep != EZ_PUT_BACK) { EzStep = EZ_IDLE; BlockBankChanges = false; return; }   // (anything else simply stops)
    }
    if (EzMsgUntil && (int32_t)(millis() - EzMsgUntil) >= 0) { EzMsgUntil = 0; EzBusy(""); }
    if (EzStep == EZ_IDLE) return;
    if (EzStep == EZ_S_WAIT)
    { // the restart: the flight controller is asked until it answers (7 s first, then every 3 s, three times: the phone's)
        if ((int32_t)(millis() - EzWaitUntil) < 0) return;
        EzBusy(PSTR("Reading the start settings back ..."));
        EzReq = MspAsk(142, nullptr, 0); EzStep = EZ_S_GOV_BACK;
        return;
    }
    if (!PipeReplyReady(EzReq))
    {
        if (!PipeReplyLate()) return;
        PipeRepCode = 1; snprintf(PipeRepBody, sizeof(PipeRepBody), PSTR("no answer in 9 s"));   // (what the box quotes)
        if (EzStep == EZ_S_GOV_BACK && ++EzBoot < 3) { EzWaitUntil = millis() + 3000; EzStep = EZ_S_WAIT; return; }
        if (EzStep <= EZ_R_PID) { EzReadFail(PSTR("No answer from the flight controller"), false); return; }
        if (EzStep == EZ_PUT_BACK) { EzFinish(EzFailMsg[0] ? EzFailMsg : nullptr); return; }
        EzFail("no answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    if ((PipeRepCode == 503 || PipeRepCode == 504) && EzTries < 5 && EzStep != EZ_S_GOV_BACK)
    { // the receiver was busy with the transmitter's own traffic: the same request once more
        ++EzTries;
        EzReq = MspAsk(EzLastFn, EzLastLen ? EzLastData : nullptr, EzLastLen);
        return;
    }
    uint8_t b[64];
    const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
    switch (EzStep)
    {
    // ---- the read: where the flight controller is, then the governor, the rates and the PIDs
    case EZ_R_STATUS:
    case EZ_S_STATUS:
    {
        if (n < 26) { if (EzStep == EZ_R_STATUS) EzReadFail(PSTR("Could not read where the flight controller is"), true); else EzFail(PSTR("could not read where the flight controller is")); return; }
        FcPidBank = (b[23] & 0x0F) + 1; FcRateBank = (b[25] & 0x0F) + 1;
        EzPidBanks = n > 24 && b[24] >= 1 && b[24] <= 8 ? b[24] : 6;
        const bool save = EzStep == EZ_S_STATUS;
        const bool pid = !save || EzNeedPid() || EzNeedWalk(), rate = !save || EzNeedRates();
        if ((pid && FcPidBank != Bank) || (rate && FcRateBank != DualRateInUse))
        { // B102: the transmitter's banks only
            const bool r = !(pid && FcPidBank != Bank);
            char m[180];
            snprintf(m, sizeof(m), PSTR("%sthe flight controller is on\r\n%s %d, the transmitter on %s %d.\r\nCheck the %s switch's set-up.%s"), save ? "Not saved: " : "", r ? "rates" : "bank",
                     r ? FcRateBank : FcPidBank, r ? "rates" : "bank", r ? DualRateInUse : Bank, r ? "rates" : "bank", save ? PSTR("\r\nNothing was written.") : "");
            if (save) EzFinish(m);
            else { m[0] = (char)toupper(m[0]); EzReadFail(m, false); }
            return;
        }
        if (save) { EzPart(EZ_P_PID); return; }
        EzAsk(142, nullptr, 0, EZ_R_GOV);
        return;
    }
    case EZ_R_GOV:
        if (n < EZ_GOV_MIN) { EzReadFail(PSTR("Could not read the governor"), true); return; }
        EzGovN = n < (int)sizeof(EzGov) ? n : (int)sizeof(EzGov); memcpy(EzGov, b, (size_t)EzGovN);
        EzAsk(111, nullptr, 0, EZ_R_RATES);
        return;
    case EZ_R_RATES:
        if (n < EZ_RATES_MIN) { EzReadFail(PSTR("Could not read the rates"), true); return; }
        EzRatesN = n < (int)sizeof(EzRates) ? n : (int)sizeof(EzRates); memcpy(EzRates, b, (size_t)EzRatesN);   // (Rotorflight 4.6: 37)
        EzAsk(112, nullptr, 0, EZ_R_PID);
        return;
    case EZ_R_PID:
        if (n < EZ_PID_MIN) { EzReadFail(PSTR("Could not read the PIDs"), true); return; }
        EzPidN = n < (int)sizeof(EzPid) ? n : (int)sizeof(EzPid); memcpy(EzPid, b, (size_t)EzPidN);   // (34)
        EzReflect(true);
        EzHave = true; EzStep = EZ_IDLE; BlockBankChanges = false;
        EzBusy("");
        EzShowAll();
        EzOpeningNote();
        if (EzRereadWanted) EzRead();   // (the rates switch moved meanwhile)
        return;
    // ---- Feel: the PIDs written, stored, read back
    case EZ_S_PID:
        if (!ok) { EzFail("Feel (the PIDs)"); return; }
        EzAsk(250, nullptr, 0, EZ_S_PID_STORE);
        return;
    case EZ_S_PID_STORE:
        if (!ok) { EzFail(PSTR("Feel (not stored)")); return; }
        EzAsk(112, nullptr, 0, EZ_S_PID_BACK);
        return;
    case EZ_S_PID_BACK:
        if (!ok) { EzFail(PSTR("Feel (not read back)")); return; }
        if (n >= EZ_PID_MIN && memcmp(b, EzOut, EZ_PID_MIN) == 0) { memcpy(EzPid, EzOut, (size_t)EzPidN); EzDone |= EZ_FEEL; } else EzBad |= EZ_FEEL;
        EzPart(EZ_P_RATES);
        return;
    // ---- Agility and Stick feel: the rates, likewise
    case EZ_S_RATES:
        if (!ok) { EzFail(PSTR("Agility (the rates)")); return; }
        EzAsk(250, nullptr, 0, EZ_S_RATES_STORE);
        return;
    case EZ_S_RATES_STORE:
        if (!ok) { EzFail(PSTR("Agility (not stored)")); return; }
        EzAsk(111, nullptr, 0, EZ_S_RATES_BACK);
        return;
    case EZ_S_RATES_BACK:
        if (!ok) { EzFail(PSTR("Agility (not read back)")); return; }
        if (n >= EzRatesN && memcmp(b, EzOut, (size_t)EzRatesN) == 0) { memcpy(EzRates, EzOut, (size_t)EzRatesN); EzDone |= EZ_AGILITY; } else EzBad |= EZ_AGILITY;
        EzPart(EZ_P_WALK);
        return;
    // ---- PID spool-up in every bank: each bank chosen, its governor read and, without the flag, written with it
    case EZ_S_WALK_SEL:
        if (!ok) { EzFail(PSTR("PID spool-up (could not choose a bank)")); return; }
        EzAsk(148, nullptr, 0, EZ_S_WALK_READ);
        return;
    case EZ_S_WALK_READ:
        if (!ok) { EzFail(PSTR("PID spool-up (could not read a bank)")); return; }
        if (n < 17 || (b[15] & 0x10)) { EzNextBank(); return; }   // (already on, or not a governor the walk knows: as the phone)
        b[15] |= 0x10;
        EzAsk(149, b, n, EZ_S_WALK_WRITE);
        return;
    case EZ_S_WALK_WRITE:
        if (!ok) { EzFail(PSTR("PID spool-up (not written)")); return; }
        ++EzSpoolOn;
        EzNextBank();
        return;
    case EZ_S_WALK_HOME:
        if (!ok) { EzFail(PSTR("could not choose the transmitter's bank again")); return; }
        EzWalked = true;
        EzPart(EZ_P_GOV);
        return;
    // ---- Start: the governor written, stored, the flight controller restarted, and read back once it is back
    case EZ_S_GOV:
        if (!ok) { EzFail(PSTR("Start (the governor)")); return; }
        EzAsk(250, nullptr, 0, EZ_S_GOV_STORE);
        return;
    case EZ_S_GOV_STORE:
        if (!ok) { EzFail(PSTR("Start (not stored)")); return; }
        EzBusy(PSTR("Restarting the flight controller to apply the start settings ..."));
        EzAsk(68, nullptr, 0, EZ_S_REBOOT);
        return;
    case EZ_S_REBOOT:
        if (!ok) { EzFail(PSTR("Start (not restarted)")); return; }
        EzBoot = 0; EzWaitUntil = millis() + 7000; EzStep = EZ_S_WAIT;
        return;
    case EZ_S_GOV_BACK:
        if (!ok || n < EZ_GOV_MIN)
        {
            if (++EzBoot < 3) { EzWaitUntil = millis() + 3000; EzStep = EZ_S_WAIT; return; }
            EzGone = true;   // (written and stored, but the flight controller did not come back to be asked)
            EzPart(EZ_P_END);
            return;
        }
        if (memcmp(b, EzOut, EZ_GOV_MIN) == 0) { memcpy(EzGov, EzOut, (size_t)EzGovN); EzDone |= EZ_START; } else EzBad |= EZ_START;
        EzPart(EZ_P_STORE);
        return;
    case EZ_S_STORE:
        if (!ok) { EzFail(PSTR("PID spool-up (not stored)")); return; }
        EzPart(EZ_P_END);
        return;
    case EZ_PUT_BACK:   // (after a failure part way through the walk, or the page left: the box, if any, now)
        EzFinish(EzQuiet ? nullptr : EzFailMsg);
        return;
    default:
        EzStep = EZ_IDLE; BlockBankChanges = false;
        return;
    }
}

// ---------------------------------------------------------------- the buttons
FLASHMEM void StartEasyView() // the menu's Easy tuning ...
{
    char why[150];
    if (!(BoundFlag && ModelMatched))
        snprintf(why, sizeof(why), PSTR("Easy tuning needs the model connected:\r\nits sliders start from the model's\r\nown numbers. Without it: PIDs,\r\nRates and Governor (from the backup)."));
    else if (!ModelSeemsArmed(why, sizeof(why)) && !RfPipeBlocked(why, sizeof(why)))
        why[0] = 0;
    if (why[0])
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page EasyView");
    CurrentView = EASYVIEW;
    Ez_Was_Edited = false; EzHave = false; EzSpool = true; EzSpoolTouched = false; EzMsgUntil = 0; EzQuiet = false;
    for (bool &mv : EzMoved) mv = false;
    EzHead();
    SendText((char *)"note", (char *)"");
    EzRead();
}
void SaveEasy();
FLASHMEM static void EzSaveNow() { EzShowAll(); SaveEasy(); }   // B102: OK's "Save now?" (the page shown again, then saved)
FLASHMEM void EndEasyView() // OK
{
    if (EzStep != EZ_IDLE) return;   // (a read or a save runs: wait for it)
    if (Ez_Was_Edited && EzHave && EzAnything())
        if (!RfSaveFirst("page EasyView", PSTR("The slider changes are"), EzSaveNow, EndEasyView, &Ez_Was_Edited)) return;   // B102
    Ez_Was_Edited = false; EzHave = false; EzMsgUntil = 0;
    RotorFlightStart();
}
FLASHMEM static void EzSlider(int k) // a slider moved (each step while it is dragged, and when it is let go)
{
    if (CurrentView != EASYVIEW || !EzHave || EzStep != EZ_IDLE) return;
    if ((k == 1 || k == 2) && !EzRatesFeel) return;
    char nm[8];
    snprintf(nm, sizeof(nm), "s%d", k);
    const uint32_t v = GetValue(nm);
    if (v > 20) return;   // (65535: the screen did not answer)
    const int pos = k < 3 ? (int)v * 5 : (int)EzClamp((long)v * 5 - 30, -30, 30);
    if (pos != EzPos[k]) { EzPos[k] = pos; EzMoved[k] = true; EzEdited(); }
    if (EzMsgUntil) { EzMsgUntil = 0; EzBusy(""); }
    EzNoteFor(k);
}
FLASHMEM void EasyStartMoved() { EzSlider(0); }
FLASHMEM void EasyAgilityMoved() { EzSlider(1); }
FLASHMEM void EasyStickFeelMoved() { EzSlider(2); }
FLASHMEM void EasyCyclicMoved() { EzSlider(3); }
FLASHMEM void EasyTailMoved() { EzSlider(4); }
FLASHMEM void EasySpoolTapped() // the switch: PID spool-up in every bank
{
    if (CurrentView != EASYVIEW || !EzHave || EzStep != EZ_IDLE) { SendValue((char *)"sw", EzSpool ? 1 : 0); return; }
    const uint32_t v = GetValue((char *)"sw");
    if (v > 1) return;
    EzSpool = v == 1;
    EzSpoolTouched = true;
    EzEdited();
    EzNoteFor(0);   // (the phone: the tick shows the start numbers too)
}
FLASHMEM void SaveEasy()
{
    if (CurrentView != EASYVIEW || !EzHave || EzStep != EZ_IDLE) return;
    char why[180];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page EasyView", why);
        EzShowAll();
        return;
    }
    if (!EzAnything()) { MsgBox((char *)"page EasyView", (char *)PSTR("Nothing has changed.")); EzShowAll(); return; }
    if (EzNeedGov() && (EzGov[0] > 4 || EzGov[28] > 2))
    { // B103: never write back a governor mode or throttle type outside Rotorflight's lists
        if (EzGov[0] > 4) snprintf(why, sizeof(why), PSTR("Not saved: Governor mode is %u.\r\nIt must be 0 - 4: put it right on\r\nthe Governor (global) page first."), EzGov[0]);
        else snprintf(why, sizeof(why), PSTR("Not saved: Throttle type is %u.\r\nIt must be 0 - 2: put it right on\r\nthe Governor (global) page first."), EzGov[28]);
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page EasyView", why);
        EzShowAll();
        return;
    }
    char q[180];
    int n = snprintf(q, sizeof(q), PSTR("Write to the flight controller?"));
    if (EzNeedPid()) n += snprintf(q + n, sizeof(q) - n, PSTR("\r\nFeel (PIDs, bank %d)"), Bank);
    if (EzNeedRates()) n += snprintf(q + n, sizeof(q) - n, PSTR("\r\nAgility (rates, rate %d)"), DualRateInUse);
    if (EzNeedGov()) n += snprintf(q + n, sizeof(q) - n, PSTR("\r\nStart (governor): it then restarts,\r\nso blades off."));
    if (EzNeedWalk()) n += snprintf(q + n, sizeof(q) - n, PSTR("\r\nPID spool-up on in every bank."));
    if (!GetConfirmation((char *)"page EasyView", q)) { EzShowAll(); return; }
    EzShowAll();
    EzDone = EzBad = 0; EzSpoolOn = 0; EzFailMsg[0] = 0; EzQuiet = false; EzRereadWanted = false; EzWalked = false; EzGone = false;
    BlockBankChanges = true;
    EzBusy(PSTR("Asking which bank the flight controller is on ..."));
    EzAsk(101, nullptr, 0, EZ_S_STATUS);
}
FLASHMEM void EasyBankChanged() // from Switches.h: the bank or the rates bank changed - that bank's numbers, the edits let go
{
    if (CurrentView != EASYVIEW) return;
    ShowRFBank();
    ShowRFRate();
    if (EzStep != EZ_IDLE) { EzRereadWanted = true; return; }
    if (Ez_Was_Edited)
        MsgBox((char *)"page EasyView", (char *)PSTR("The sliders were moved but not saved.\r\n(Too late now: the bank changed.)\r\nThey show the new bank's numbers."));
    Ez_Was_Edited = false;
    EzHead();
    EzRead();
}
#endif // RF_EASY_H
