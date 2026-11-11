// B196 (Malcolm, 8 Nov 2026: "Please do all five"): CHECK MY SETUP, page 86 (RFCheckView, from Guide & checks: 16 MB
// screens). One press reads the flight controller and lists what is unfinished or odd, in plain words, each with a button
// to the page that puts it right; a red mark stops it arming, an amber one is worth a look. What it reads, byte for byte
// release/4.6.0 src/main/msp/msp.c:
//  - 101 (status): the flight controller's OWN reasons it will not arm (runtime_config.h, 27 flags; the words are the
//    menu's arming line's, RF_FcSetup.h ArmWhy) - the governor with no RPM signal, the level never calibrated, a restart
//    owed, no ESC protocol ... - and whether it says it is armed.
//  - 34 (the switches): an arm switch at all; on this model's arming channel; its zone clear of 988 us and up to 2012 us
//    (the Switches page's own rule, RF_Switches.h SwArmOk); a rescue mode (146, the bank it is on) with no switch to start it.
//  - 32 (battery): no capacity (no "% left"); no voltage measured. 70 (black box memory): 80 % full or more.
//  - 131 (motor) with 142 (governor mode): a gear ratio missing or backwards (the phone's gear.js verdict: rotor : motor,
//    the rotor's number the smaller - the Goblin's 10:1 of 2 Sep 2026 held the governor at minimum).
//  - 108 (the level): tilted more than 45 degrees - if it stands level, its mounting is wrong (the Direction check).
// The model must be connected (the backup's stand-in is never asked: these are the flight controller's own answers).
// Nothing is written, except Restart when the flight controller itself says one is owed (68, after a question).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_CHECK_H
#define RF_CHECK_H

// The pages a row's button - or a guide step (RF_Guide.h) - opens (RF_Tools.h RfOpenPage)
enum { RFO_NONE = 0, RFO_CALIBRATE, RFO_BASICS, RFO_BATTERY, RFO_BLACKBOX, RFO_SWITCHES, RFO_FILTERS, RFO_RESTART, RFO_DIRECTION, RFO_SETTINGS, RFO_RESCUE,
       RFO_SERVOS, RFO_TRAVEL, RFO_GOVERNOR, RFO_GOVGLOBAL, RFO_RATES, RFO_BEEPER, RFO_CHECK, RFO_BACKUP };
static const char CkFixWords[11][14] PROGMEM = {"", "Calibrate ...", "Basics ...", "Battery ...", "Black box ...", "Switches ...", "Filters ...", "Restart", "Direction ...", "Settings ...", "Rescue ..."};
struct CkRow { uint8_t sev; uint8_t fix; char text[52]; };   // sev: 0 red (stops arming), 1 amber (a look), 2 green (all well)
static const int CK_MAX = 16, CK_ROWS = 6;
DMAMEM static CkRow CkRows[CK_MAX];
static int CkN = 0, CkFirst = 0;
enum { CK_IDLE = 0, CK_STATUS, CK_MODES, CK_MAP, CK_RESCUE, CK_BATTERY, CK_MEMORY, CK_MOTOR, CK_GOV, CK_LEVEL, CK_RESTARTING, CK_RESTART_ASK };   // (B210: CK_MAP, the channel map)
static int CkStep = CK_IDLE, CkReq = 0, CkTries = 0;
static uint32_t CkAskedAt = 0, CkWaitUntil = 0;
static bool CkDone = false, CkArmFlag8 = false;
static uint8_t CkStatus[40], CkModes[96], CkBattery[40], CkMemory[16], CkMotor[32], CkGov[48], CkLevel[8];
static int CkStatusN = 0, CkModesN = 0, CkRescueMode = -1, CkBatteryN = 0, CkMemoryN = 0, CkMotorN = 0, CkGovN = 0, CkLevelN = 0;

FLASHMEM static void CkAdd(uint8_t sev, uint8_t fix, const char *text)
{
    if (CkN >= CK_MAX) return;
    CkRows[CkN].sev = sev; CkRows[CkN].fix = fix;
    snprintf(CkRows[CkN].text, sizeof(CkRows[CkN].text), "%s", text);
    ++CkN;
}
FLASHMEM static uint8_t CkFixOfFlag(int bit) // the page that puts a flight controller's reason right (0: none - a switch, a wait)
{
    switch (bit)
    {
    case 4: case 10: return RFO_SWITCHES;        // the failsafe test switch on; the pre-arm switch off
    case 5: case 6: case 24: return RFO_BASICS;  // the governor / no RPM signal / no ESC protocol: poles, telemetry, ESC signal
    case 8: return RFO_DIRECTION;                // tilted too far: if it stands level, the mounting
    case 20: return RFO_FILTERS;                 // the RPM filter with no RPM signal
    case 21: return RFO_RESTART;                 // a restart owed
    case 23: return RFO_CALIBRATE;               // the level never calibrated
    default: return RFO_NONE;
    }
}
FLASHMEM static void CkFindings() // the rows, from what was read
{
    CkN = 0; CkArmFlag8 = false;
    char t[80];
    // 1. the flight controller's own word: armed, and why it will not arm (most critical first)
    if (CkStatusN >= 21)
    {
        if (CkStatus[6] & 1) CkAdd(0, RFO_NONE, "The flight controller says it is ARMED");
        uint32_t f = RdU32(CkStatus, 17);
        const int cnt = CkStatus[16];
        if (cnt >= 1 && cnt <= 26 && (f & (1UL << (cnt - 1)))) { f &= ~(1UL << (cnt - 1)); f |= 1UL << 26; }   // (the arm switch is always its last flag: RF_FcSetup.h ArmTick)
        f &= 0x07FFFFFFUL;
        for (int i = 0; i < 27; ++i)
        {
            if (!(f & (1UL << i))) continue;
            if (i == 8) CkArmFlag8 = true;
            CkAdd(0, CkFixOfFlag(i), ArmWhy[i]);
        }
    }
    else CkAdd(1, RFO_NONE, "Its reasons not to arm were not read");
    // 2. the switches: an arm switch, on this model's arming channel, its zone right; rescue with a switch
    if (CkModesN >= 4)
    {
        bool arm = false, rescueSwitch = false;
        const int ac = SwArmChannel();
        for (int i = 0; i + 3 < CkModesN; i += 4)
        {
            SwSlot s; s.perm = CkModes[i]; s.aux = CkModes[i + 1]; s.lo = (int16_t)SwUs(CkModes[i + 2]); s.hi = (int16_t)SwUs(CkModes[i + 3]);
            if (!SwUsed(s)) continue;
            if (s.perm == 53) rescueSwitch = true;
            if (s.perm != 0) continue;
            arm = true;
            if (ac && RfAuxCh(s.aux) != ac) { snprintf(t, sizeof(t), "Arm switch on channel %d: the safety drives %d", RfAuxCh(s.aux), ac); CkAdd(0, RFO_SWITCHES, t); }   // (B210: by the map)
            else if (s.lo <= 988) CkAdd(0, RFO_SWITCHES, "Arm zone reaches 988 us: arms, safety ON");
            else if (s.hi < 2012) CkAdd(0, RFO_SWITCHES, "Arm zone ends below 2012 us: may not arm");
        }
        if (!arm) CkAdd(0, RFO_SWITCHES, "Rotorflight has no arm switch");
        if (CkRescueMode > 0 && !rescueSwitch) CkAdd(1, RFO_SWITCHES, "Rescue is on, but no switch starts it");
    }
    // 3. the battery
    if (CkBatteryN >= 5)
    {
        if (RdU16(CkBattery, 0) == 0) CkAdd(1, RFO_BATTERY, "Battery capacity not set: no % left");
        if (CkBattery[3] == 0) CkAdd(1, RFO_BATTERY, "Battery voltage is not measured");
    }
    // 4. the black box memory
    if (CkMemoryN >= 13 && (CkMemory[0] & 2))
    {
        const uint32_t total = RdU32(CkMemory, 5), used = RdU32(CkMemory, 9);
        if (total > 0 && used <= total && (uint64_t)used * 100 >= (uint64_t)total * 80)
        {
            snprintf(t, sizeof(t), "Black box %lu%% full", (unsigned long)((uint64_t)used * 100 / total));
            CkAdd(1, RFO_BLACKBOX, t);
        }
    }
    // 5. the gear ratios (the governor's head speed comes from them)
    if (CkMotorN >= 29)
    {
        const uint16_t mr = RdU16(CkMotor, 21), mm = RdU16(CkMotor, 23), tr = RdU16(CkMotor, 25), tt = RdU16(CkMotor, 27);
        const bool gov = CkGovN >= 1 && CkGov[0] >= 1;
        if (!mr || !mm) CkAdd(1, RFO_BASICS, "Main gear ratio is not set");
        else if (mr > mm) { snprintf(t, sizeof(t), "Main gear ratio backwards (%u : %u)", mr, mm); CkAdd(gov ? 0 : 1, RFO_BASICS, t); }
        if (tr && tt && tr > tt) { snprintf(t, sizeof(t), "Tail gear ratio backwards (%u : %u)", tr, tt); CkAdd(1, RFO_BASICS, t); }
    }
    // 6. the level: tilted far - if it stands level, its mounting (not said again when the flight controller says it)
    if (CkLevelN >= 4 && !CkArmFlag8)
    {
        const int roll = RdS16(CkLevel, 0) / 10, pitch = RdS16(CkLevel, 2) / 10;
        const int worst = abs(roll) > abs(pitch) ? abs(roll) : abs(pitch);
        if (worst > 45) { snprintf(t, sizeof(t), "Tilted %d\xB0: if it stands level, check it", worst); CkAdd(1, RFO_DIRECTION, t); }
    }
    bool red = false;
    for (int i = 0; i < CkN; ++i) if (CkRows[i].sev == 0) red = true;
    if (!CkN) CkAdd(2, RFO_DIRECTION, "Nothing found. A new model: Direction check");
    else if (!red) CkAdd(2, RFO_NONE, "Nothing stops it arming");
}
FLASHMEM static void CkShow()
{
    if (CurrentView != CHECKVIEW) return;
    char b[60];
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)((BoundFlag && ModelMatched) ? "Connected" : "No model"));
    int red = 0, amber = 0;
    for (int i = 0; i < CkN; ++i) { if (CkRows[i].sev == 0) ++red; else if (CkRows[i].sev == 1) ++amber; }
    if (!CkDone) snprintf(b, sizeof(b), "Reading the flight controller ...");
    else if (!red && !amber) snprintf(b, sizeof(b), "All well, as far as this can tell");
    else snprintf(b, sizeof(b), "%d stop%s it arming, %d worth a look", red, red == 1 ? "s" : "", amber);
    SendText((char *)"hd", b);
    for (int r = 0; r < CK_ROWS; ++r)
    {
        const int i = CkFirst + r;
        char n[8], c[40];
        snprintf(n, sizeof(n), "r%d", r);
        const bool on = CkDone && i < CkN;
        SendText(n, (char *)(on ? CkRows[i].text : ""));
        snprintf(c, sizeof(c), "vis mk%d,%d", r, on ? 1 : 0); SendCommand(c);
        if (on) { snprintf(c, sizeof(c), "mk%d.bco=%u", r, CkRows[i].sev == 0 ? 63488u : CkRows[i].sev == 1 ? 64512u : 2016u); SendCommand(c); }
        snprintf(n, sizeof(n), "f%d", r);
        const bool fix = on && CkRows[i].fix != RFO_NONE;
        if (fix) SendText(n, (char *)CkFixWords[CkRows[i].fix]);
        snprintf(c, sizeof(c), "vis f%d,%d", r, fix ? 1 : 0); SendCommand(c);
    }
    snprintf(b, sizeof(b), "vis bP,%d", CkDone && CkFirst > 0 ? 1 : 0); SendCommand(b);
    snprintf(b, sizeof(b), "vis bN,%d", CkDone && CkFirst + CK_ROWS < CkN ? 1 : 0); SendCommand(b);
}
FLASHMEM static bool CkAsk(uint8_t fn) // one read at a time, never on top of another request
{
    if (!RfPipeFree()) return false;
    CkReq = MspAsk(fn, nullptr, 0); CkAskedAt = millis();
    return true;
}
static const uint8_t CkFnOf[] = {0, 101, 34, 64, 146, 32, 70, 131, 142, 108};
FLASHMEM static void CkBegin()
{
    CkN = 0; CkFirst = 0; CkDone = false; CkTries = 0;
    CkStatusN = CkModesN = CkBatteryN = CkMemoryN = CkMotorN = CkGovN = CkLevelN = 0; CkRescueMode = -1;
    CkStep = CK_STATUS; CkReq = 0; CkWaitUntil = millis();
    FsBusy("Reading the flight controller ...");
    CkShow();
}
FLASHMEM static void CkTake(bool ok) // the answer to the step in hand, kept; on to the next
{
    uint8_t *dst = nullptr; int *dn = nullptr; int max = 0;
    switch (CkStep)
    {
    case CK_STATUS: dst = CkStatus; dn = &CkStatusN; max = sizeof(CkStatus); break;
    case CK_MODES: dst = CkModes; dn = &CkModesN; max = sizeof(CkModes); break;
    case CK_BATTERY: dst = CkBattery; dn = &CkBatteryN; max = sizeof(CkBattery); break;
    case CK_MEMORY: dst = CkMemory; dn = &CkMemoryN; max = sizeof(CkMemory); break;
    case CK_MOTOR: dst = CkMotor; dn = &CkMotorN; max = sizeof(CkMotor); break;
    case CK_GOV: dst = CkGov; dn = &CkGovN; max = sizeof(CkGov); break;
    case CK_LEVEL: dst = CkLevel; dn = &CkLevelN; max = sizeof(CkLevel); break;
    default: break;
    }
    if (CkStep == CK_MAP) { uint8_t m[16]; if (!ok || !RfMapTake(m, PipeReplyBytes(m, sizeof(m)))) RfMapLen = 0; }   // (B210: none read = the default)
    else if (ok && CkStep == CK_RESCUE) { uint8_t b[32]; if (PipeReplyBytes(b, sizeof(b)) >= 1) CkRescueMode = b[0]; }
    else if (ok && dst) *dn = PipeReplyBytes(dst, max);
    CkTries = 0;
    ++CkStep;
    if (CkStep > CK_LEVEL)
    {
        CkStep = CK_IDLE; CkDone = true;
        CkFindings();
        FsBusy("");
        CkShow();
    }
}
FLASHMEM static void CheckPoll()
{
    if (CurrentView != CHECKVIEW) return;   // (the screen gone dark, or a message box: it carries on where it was when the page is back; OK ends it)
    if (CkStep == CK_RESTART_ASK)
    { // the restart, asked when nothing else waits on the pipe
        if (!RfPipeFree()) return;
        MspAsk(68, nullptr, 0);
        CkStep = CK_RESTARTING; CkWaitUntil = millis() + 5000;
        return;
    }
    if (CkStep == CK_RESTARTING)
    { // a restart asked: a breath, then the check again
        if ((int32_t)(millis() - CkWaitUntil) < 0) return;
        CkBegin();
        return;
    }
    if (CkStep == CK_IDLE) return;
    if (!(BoundFlag && ModelMatched) || PipeState != 2)
    { // the model went: what was read is shown, the rest said
        CkStep = CK_IDLE; CkDone = true; CkFindings(); FsBusy(""); CkShow();
        return;
    }
    if (!CkReq) { if ((int32_t)(millis() - CkWaitUntil) >= 0) CkAsk(CkFnOf[CkStep]); return; }
    if (PipeReplyReady(CkReq))
    {
        const bool ok = PipeRepCode == 200;
        CkReq = 0;
        if (!ok && PipeRepCode >= 500 && ++CkTries < 2) { CkWaitUntil = millis() + 400; return; }   // (the receiver busy - "try again": once more, a moment later, as the backup does)
        CkTake(ok);
        return;
    }
    if ((uint32_t)(millis() - CkAskedAt) > 4000)
    { // no answer: once more, then on without it
        CkReq = 0;
        if (++CkTries >= 2) CkTake(false);
    }
}
// ---- the page
FLASHMEM static bool CkModelThere(const char *page)
{
    char why[120];
    if (!(BoundFlag && ModelMatched)) { PlaySound(WHAHWHAHMSG); MsgBox((char *)page, (char *)"Connect the model first: the check\r\nreads its flight controller."); return false; }
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why))) { PlaySound(WHAHWHAHMSG); MsgBox((char *)page, why); return false; }
    return true;
}
FLASHMEM void CheckStart() // from Guide & checks (or a guide step)
{
    if (BakJob != BAK_JOB_NONE) return;
    if (!CkModelThere(CurrentView == GUIDEVIEW ? "page RFGuideView" : "page RFToolsView")) { RfToolsRedraw(); return; }
    UndoNewVisit();
    SendCommand((char *)"page RFCheckView");
    CurrentView = CHECKVIEW;
    CkBegin();
}
FLASHMEM void CheckShowAgain(bool again) // back from a page a row's button opened: checked again (again false: it would not open)
{
    SendCommand((char *)"page RFCheckView");
    CurrentView = CHECKVIEW;
    UndoNewVisit();
    if (again && BoundFlag && ModelMatched && PipeState == 2) CkBegin(); else { CkDone = true; CkShow(); }
}
FLASHMEM void CheckAgain() { if (CkStep == CK_IDLE && CurrentView == CHECKVIEW) { if (CkModelThere("page RFCheckView")) CkBegin(); else CkShow(); } }   // 244
FLASHMEM void CheckPrev() { if (CkFirst >= CK_ROWS) CkFirst -= CK_ROWS; else CkFirst = 0; CkShow(); }                                                          // 246
FLASHMEM void CheckNext() { if (CkFirst + CK_ROWS < CkN) CkFirst += CK_ROWS; CkShow(); }                                                                     // 247
FLASHMEM void EndCheckView() // 245: OK - back to where it was opened from
{
    if (CkStep == CK_RESTART_ASK) return;   // (the restart the pilot said yes to is asked a moment from now: then OK)
    if (CkStep != CK_IDLE && CkStep != CK_RESTARTING) FsBusy("");
    CkStep = CK_IDLE;
    RfBackHome();
}
FLASHMEM void CheckFixTapped() // 243: a row's button (the row in the event's top byte, 1-6)
{
    const int r = (int)ScreenEventArg - 1;
    if (CkStep != CK_IDLE || r < 0 || r >= CK_ROWS || CkFirst + r >= CkN) return;
    const uint8_t fix = CkRows[CkFirst + r].fix;
    if (fix == RFO_RESTART)
    {
        if (FsRefused("page RFCheckView", true)) { CkShow(); return; }
        if (!GetConfirmation((char *)"page RFCheckView", (char *)"Restart the flight controller now?\r\n(It takes a few seconds; the model\r\nstays connected.)")) { CkShow(); return; }
        CkShow();
        FsBusy("Restarting the flight controller ...");
        CkStep = CK_RESTART_ASK;
        return;
    }
    RfOpenFrom(CHECKVIEW, fix);
}
#endif // RF_CHECK_H
