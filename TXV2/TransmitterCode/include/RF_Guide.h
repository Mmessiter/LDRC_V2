// B196 (Malcolm, 8 Nov 2026: "Please do all five"): THE NEW HELICOPTER GUIDE, page 89 (RFGuideView, from Guide & checks:
// 16 MB screens). Every setup step in the order Rotorflight's own setup takes them, over the pages this transmitter already
// has: a step opens its page, the page's OK comes back here (RF_Tools.h, the home the page was opened from) and the step is
// ticked. "Next step" opens the first one not ticked; its one line says what the step is for. The ticks are kept per model on
// the card (/rfbak/<model>.rfg), so the guide can be left and taken up again; Start again clears them.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_GUIDE_H
#define RF_GUIDE_H

struct GdStep { char name[20]; char hint[84]; uint8_t open; };   // (in the table, in flash)
static const GdStep GdSteps[] PROGMEM = {
    {"Direction check", "Is the flight controller the right way round? Tilt and turn the model: it says.", RFO_DIRECTION},
    {"Calibrate level", "Stand the model level and calibrate: self-level and rescue need it.", RFO_CALIBRATE},
    {"Model basics", "Rotor direction, tail and swash type. Next >: motor poles, gear ratios, ESC.", RFO_BASICS},
    {"Battery", "Cells and capacity, and where the voltage is measured.", RFO_BATTERY},
    {"Servos", "Centre each servo, and set its direction.", RFO_SERVOS},
    {"Travel extents", "Level the swash; the collective and cyclic limits.", RFO_TRAVEL},
    {"Switches & knobs", "Arm, the banks, rescue, and the knobs.", RFO_SWITCHES},
    {"Governor (global)", "The governor's mode and its timings.", RFO_GOVGLOBAL},
    {"Governor", "The head speed, bank by bank.", RFO_GOVERNOR},
    {"Rates", "How fast it rolls, flips and turns.", RFO_RATES},
    {"Rescue", "The safety net: what it does on its switch.", RFO_RESCUE},
    {"Filters", "Usually right as they are: a look.", RFO_FILTERS},
    {"Beeper & name", "Its name, and what it beeps for.", RFO_BEEPER},
    {"Black box", "What it records, and how often.", RFO_BLACKBOX},
    {"Check my setup", "Anything unfinished or odd, listed.", RFO_CHECK},
    {"Back up", "A copy of this setup on the card.", RFO_BACKUP}};
static const int GD_STEPS = sizeof(GdSteps) / sizeof(GdSteps[0]), GD_ROWS = 8;
static uint16_t GdDone = 0;          // a bit a step, for GdModel
static char GdModel[32] = "";
static int GdPage = 0, GdOpen = -1;  // the half of the list showing; the step whose page is open (-1: none)

FLASHMEM static void GdPath(char *out, size_t n)
{
    BakPath(out, n, ModelName);
    char *dot = strrchr(out, '.');
    if (dot) snprintf(dot, n - (size_t)(dot - out), ".rfg");
}
FLASHMEM static void GdLoad() // this model's ticks from the card
{
    if (strcmp(GdModel, ModelName) == 0) return;
    snprintf(GdModel, sizeof(GdModel), "%s", ModelName);
    GdDone = 0;
    char p[48], t[24] = "";
    GdPath(p, sizeof(p));
    File f = SD.open(p, FILE_READ);
    if (!f) return;
    const int n = f.read(t, sizeof(t) - 1);
    f.close();
    t[n > 0 ? n : 0] = 0;
    if (strncmp(t, "done=", 5) == 0) GdDone = (uint16_t)strtoul(t + 5, nullptr, 16);
}
FLASHMEM static void GdSave()
{
    if (!SD.exists(BAK_DIR)) SD.mkdir(BAK_DIR);
    char p[48], t[24];
    GdPath(p, sizeof(p));
    SD.remove(p);
    File f = SD.open(p, FILE_WRITE);
    if (!f) return;
    snprintf(t, sizeof(t), "done=%04X\n", (unsigned)GdDone);
    f.write(t, strlen(t));
    f.close();
}
FLASHMEM static int GdNextStep() { for (int i = 0; i < GD_STEPS; ++i) if (!(GdDone & (1u << i))) return i; return -1; }
FLASHMEM static int GdDoneCount() { int n = 0; for (int i = 0; i < GD_STEPS; ++i) if (GdDone & (1u << i)) ++n; return n; }
FLASHMEM static void GdShow()
{
    if (CurrentView != GUIDEVIEW) return;
    char b[120], n[8], c[40];
    SendText((char *)"t11", ModelName);
    snprintf(b, sizeof(b), "%d of %d done", GdDoneCount(), GD_STEPS);
    SendText((char *)"t9", b);
    for (int r = 0; r < GD_ROWS; ++r)
    {
        const int i = GdPage * GD_ROWS + r;
        snprintf(n, sizeof(n), "g%d", r);
        if (i < GD_STEPS) { snprintf(b, sizeof(b), "%d. %s", i + 1, GdSteps[i].name); SendText(n, b); }
        else SendText(n, (char *)"");
        snprintf(c, sizeof(c), "vis g%d,%d", r, i < GD_STEPS ? 1 : 0); SendCommand(c);
        const bool done = i < GD_STEPS && (GdDone & (1u << i));
        snprintf(c, sizeof(c), "k%d.bco=%u", r, done ? 2016u : 33808u); SendCommand(c);
        snprintf(n, sizeof(n), "k%d", r);
        SendText(n, (char *)(done ? "OK" : ""));
    }
    const int nx = GdNextStep();
    if (nx < 0)
    {
        SendText((char *)"nx", (char *)"Every step done");
        SendText((char *)"hn", (char *)"Fly it gently first. Check my setup and Back up again after any change.");
        SendCommand((char *)"vis bG,0");
    }
    else
    {
        snprintf(b, sizeof(b), "Next: %d. %s", nx + 1, GdSteps[nx].name);
        SendText((char *)"nx", b);
        SendText((char *)"hn", (char *)GdSteps[nx].hint);
        snprintf(b, sizeof(b), "Go to step %d ...", nx + 1);
        SendText((char *)"bG", b);
        SendCommand((char *)"vis bG,1");
    }
    SendText((char *)"bPg", (char *)(GdPage ? "< Steps 1 - 8" : "Steps 9 - 16 >"));
}
FLASHMEM static void GdOpenStep(int s)
{
    if (s < 0 || s >= GD_STEPS) return;
    GdOpen = s;
    RfOpenFrom(GUIDEVIEW, GdSteps[s].open);
    if (CurrentView == GUIDEVIEW) GdOpen = -1;   // (the page would not open: it said why, the guide is back)
}
FLASHMEM void GuideStart() // 238: Guide & checks' "New helicopter guide ..."
{
    if (BakJob != BAK_JOB_NONE) return;
    if (!CkModelThere("page RFToolsView")) { RfToolsRedraw(); return; }
    GdLoad();
    GdOpen = -1;
    const int nx = GdNextStep();
    GdPage = nx >= GD_ROWS ? 1 : 0;
    UndoNewVisit();
    SendCommand((char *)"page RFGuideView");
    CurrentView = GUIDEVIEW;
    GdShow();
}
FLASHMEM void GuideShowAgain(bool tick) // back from a step's page: that step ticked (tick false: its page would not open)
{
    GdLoad();
    if (tick && GdOpen >= 0 && GdOpen < GD_STEPS && !(GdDone & (1u << GdOpen))) { GdDone |= (uint16_t)(1u << GdOpen); GdSave(); }
    GdOpen = -1;
    const int nx = GdNextStep();
    if (nx >= 0) GdPage = nx >= GD_ROWS ? 1 : 0;
    UndoNewVisit();
    SendCommand((char *)"page RFGuideView");
    CurrentView = GUIDEVIEW;
    GdShow();
}
FLASHMEM void GuideStepTapped() { const int r = (int)ScreenEventArg - 1; if (r >= 0 && r < GD_ROWS) GdOpenStep(GdPage * GD_ROWS + r); }   // 256: a step (the row in the top byte, 1-8)
FLASHMEM void GuideNextTapped() { GdOpenStep(GdNextStep()); }                                                                          // 257: Go to step N ...
FLASHMEM void GuidePageTapped() { GdPage = GdPage ? 0 : 1; GdShow(); }                                                                 // 258: Steps 9 - 16 > / < Steps 1 - 8
FLASHMEM void GuideRestart() // 259: Start again
{
    if (!GetConfirmation((char *)"page RFGuideView", (char *)"Start the guide again?\r\n(The ticks go; nothing in the model\r\nchanges.)")) { GdShow(); return; }
    GdDone = 0; GdSave(); GdPage = 0;
    GdShow();
}
FLASHMEM void EndGuideView() { GdOpen = -1; RfBackHome(); }   // 260: OK - back to Guide & checks
#endif // RF_GUIDE_H
