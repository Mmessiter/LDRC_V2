// B196 (Malcolm, 8 Nov 2026: "Are there more features we could add to the 16m version that might make Rotorflight
// configuration simpler for users?" ... "Please do all five in whichever order is optimal for you. Take your time! Plan to
// maximise the odds that the first test reveals no problems and it all still installs on 4m devices."):
// GUIDE & CHECKS, page 85 (RFToolsView), from the Rotorflight menu's "Guide & checks ..." - shown on a 16 MB screen only (the
// menu's own script hides it on a 4 MB one, where "Command line ..." keeps its place). Its buttons: New helicopter guide
// (RF_Guide.h), Check my setup (RF_Check.h), Direction check (RF_Direction.h), What changed? (RF_Changes.h), Undo the last
// save (RF_Undo.h, with the line under it saying what it would undo), Command line (the screen's own, as on the menu).
// THE WAY BACK: a page opened from the guide or from Check my setup comes back there - every Rotorflight page's OK ends in
// RotorFlightStart, whose first look (RfHomeBack) is the place it was opened from (two deep: the guide, then a check's row).
// A refusal that kept the page from opening puts its opener back at once (RfOpenFrom).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_TOOLS_H
#define RF_TOOLS_H

static_assert(TOOLSVIEW > BEEPERVIEW && GUIDEVIEW < 90, "Help's way back keeps a page only below view 90 (main.cpp, 'Returned from help')");
static uint8_t RfHome[2];
static uint8_t RfHomeN = 0;
static bool RfOpening = false;   // a page is being opened from the guide or the check (RfOpenFrom)

FLASHMEM static void ToolsShow()
{
    if (CurrentView != TOOLSVIEW) return;
    char b[96];
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)((BoundFlag && ModelMatched) ? "Connected" : "No model"));
    UndoLine(b, sizeof(b));
    SendText((char *)"tU", b);
}
FLASHMEM static void ToolsShowAgain()
{
    UndoNewVisit();
    SendCommand((char *)"page RFToolsView");
    CurrentView = TOOLSVIEW;
    ToolsShow();
}
FLASHMEM void RfToolsRedraw() // the tools' page in view drawn again (after a message box: it reloads the page)
{
    switch (CurrentView)
    {
    case TOOLSVIEW: ToolsShow(); break;
    case GUIDEVIEW: GdShow(); break;
    case CHECKVIEW: CkShow(); break;
    case DIRVIEW: DrShow(); break;
    case CHANGESVIEW: ChgShow(); break;
    default: break;
    }
}
FLASHMEM static void RfShowHome(uint8_t v, bool cameBack) // cameBack: from the page it opened (the guide ticks it, the check runs again)
{
    if (v == GUIDEVIEW) GuideShowAgain(cameBack);
    else if (v == CHECKVIEW) CheckShowAgain(cameBack);
    else ToolsShowAgain();
}
FLASHMEM bool RfHomeBack() // RotorFlightStart's first look: true = a page opened from the guide or the check went back there
{
    if (RfOpening) return true;   // (a page refusing as it opens: its opener puts itself back - RfOpenFrom - nothing ticked)
    if (!RfHomeN) return false;
    if (CurrentView == RXSETUPVIEW || CurrentView == FRONTVIEW || CurrentView == ROTORFLIGHTVIEW || CurrentView == TOOLSVIEW) { RfHomeN = 0; return false; }   // (a fresh way in: the menu)
    RfShowHome(RfHome[--RfHomeN], true);
    return true;
}
FLASHMEM void RfBackHome() // the tools' own pages' OK: where they were opened from (the guide, the check), else Guide & checks
{
    if (RfHomeN) { RfShowHome(RfHome[--RfHomeN], true); return; }
    ToolsShowAgain();
}
FLASHMEM static void RfOpenPage(uint8_t id)
{
    switch (id)
    {
    case RFO_CALIBRATE: StartCalibrateView(); break;
    case RFO_BASICS: StartBasicsView(); break;
    case RFO_BATTERY: StartBatteryView(); break;
    case RFO_BLACKBOX: StartBlackboxView(); break;
    case RFO_SWITCHES: StartJobsView(); break;
    case RFO_FILTERS: StartFilterView(); break;
    case RFO_DIRECTION: DirStart(); break;
    case RFO_SETTINGS: StartRFSettingsView(); break;
    case RFO_RESCUE: StartRescueView(); break;
    case RFO_SERVOS: StartServoView(); break;
    case RFO_TRAVEL: StartTravelView(); break;
    case RFO_GOVERNOR: Start_RF_Governor(); break;
    case RFO_GOVGLOBAL: Start_Gov_Global(); break;
    case RFO_RATES: StartRFRatesView(); break;
    case RFO_BEEPER: StartBeeperView(); break;
    case RFO_CHECK: CheckStart(); break;
    case RFO_BACKUP: StartBackupView(); break;
    default: break;
    }
}
FLASHMEM void RfOpenFrom(uint8_t from, uint8_t id) // a page opened from the guide or the check: its OK comes back here
{
    if (id == RFO_NONE || RfHomeN >= 2) return;
    const uint8_t n0 = RfHomeN;
    RfHome[RfHomeN++] = from;
    const int before = CurrentView;
    RfOpening = true;
    RfOpenPage(id);
    RfOpening = false;
    if (CurrentView == before)
    { // it would not open (it said why, and its message box went back to some other page): the opener again, as it was -
      // the step not ticked, the check not run again (review, 8 Nov: a refused step was ticked, so a new heli could show
      // "Every step done" with the direction check never run)
        RfHomeN = n0;
        RfShowHome(from, false);
    }
}
// ---- the page
FLASHMEM void StartToolsView() // 236: the Rotorflight menu's "Guide & checks ..."
{
    if (!ScreenIsBig())
    { // (the menu hides the button on a 4 MB screen: this is for an older screen that has the page but not the answer)
        MsgBox((char *)"page RFView", (char *)"Guide & checks needs the 16 MB screen.");
        return;
    }
    RfHomeN = 0;
    UndoNewVisit();
    SendCommand((char *)"page RFToolsView");
    CurrentView = TOOLSVIEW;
    ToolsShow();
}
FLASHMEM void EndToolsView() // 237: OK
{
    if (BakJob != BAK_JOB_NONE) return;   // (an undo is being written: wait for it)
    RfHomeN = 0;
    RotorFlightStart();
}
FLASHMEM void ToolsGuide() { if (BakJob == BAK_JOB_NONE) { RfHomeN = 0; GuideStart(); } }       // 238
FLASHMEM void ToolsCheck() { if (BakJob == BAK_JOB_NONE) { RfHomeN = 0; CheckStart(); } }       // 239
FLASHMEM void ToolsDirection() { if (BakJob == BAK_JOB_NONE) { RfHomeN = 0; DirStart(); } }     // 240
FLASHMEM static void ToolsUndoDone(int job, const char *verdict)
{
    (void)job;
    char m[200];
    if (!BakFails)
    {
        if (BakWritten) snprintf(m, sizeof(m), "Put back as it was before the save:\r\n%d written, read back the same.", BakWritten);
        else snprintf(m, sizeof(m), "Nothing to put back: the flight\r\ncontroller has those values already.");
        UndoUsed();
    }
    else snprintf(m, sizeof(m), "Not all put back:\r\n%.150s", verdict);
    RfBoxOrQuiet("page RFToolsView", m);
    ToolsShow();
}
FLASHMEM void ToolsUndo() // 242: Undo the last save
{
    if (BakJob != BAK_JOB_NONE) return;
    char q[220];
    if (!UndoOffered())
    {
        if (UndoBad && strcmp(UndoModel, ModelName) == 0) snprintf(q, sizeof(q), "The last save (%.40s) cannot be\r\nundone here: %.60s.", UndoWhat, UndoBadWhy);
        else snprintf(q, sizeof(q), "Nothing to undo yet: the next\r\nRotorflight save can be undone here.");
        MsgBox((char *)"page RFToolsView", q);
        ToolsShow();
        return;
    }
    if (FsRefused("page RFToolsView", true)) { ToolsShow(); return; }
    char age[16];
    UndoAge(age, sizeof(age));
    snprintf(q, sizeof(q), "Put back %.40s\r\nas it was before the save (%s)?", UndoWhat, age);
    if (!GetConfirmation((char *)"page RFToolsView", q)) { ToolsShow(); return; }
    BakToolPage = "page RFToolsView";
    BakToolDone = ToolsUndoDone;
    ToolsShow();
    if (!UndoStart()) ToolsShow();   // (refused: it said why)
}
FLASHMEM void ToolsPoll() // every pass: the tools' pages, and Undo's read before a word save
{
    UndoPreTick();
    CheckPoll();
    DirectionPoll();
}
#endif // RF_TOOLS_H
