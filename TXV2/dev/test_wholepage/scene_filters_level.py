#!/usr/bin/env python3
"""E2: the Rotorflight "word pages" read their text boxes through a helper (FieldNumber / FieldTenths: GetText, a number, a clamp).
NO ANSWER ("") becomes the clamp of 0 there - and three saves send it to the flight controller with no look at "was every box
answered?" (SaveFilters, SaveLevelTrims, SaveBlackbox); seven OK routines put it back on the page as if typed.
Real routines: FieldNumber, FieldTenths, WrU16 (RF_Rescue.h); the Filters page's own block and SaveFilters (RF_Filters.h);
CalGather, CalShow, CalHead, SaveLevelTrims, EndCalibrateView, CalSaveNow (RF_FcSetup.h); RfSaveFirst (RF_SaveNow.h);
GetSaveOrDiscard (Utilities.h); RfFieldsMissed (Nextion.h) - over test_noanswer's pretend screen."""
import re, sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES, FLT, FCS, SRV, SNOW = (m.release(m.src('include/' + f)) for f in ('RF_Rescue.h', 'RF_Filters.h', 'RF_FcSetup.h', 'RF_Servos.h', 'RF_SaveNow.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
def block(text, a, b): return text[text.index(a):text.index(b)]
REAL = (line(RES, 'FLASHMEM static uint16_t RdU16(') + m.lift(RES, 'FLASHMEM static void WrU16(') + line(SRV, 'FLASHMEM static int RdS16(')
        + m.lift(RES, 'FLASHMEM static long FieldNumber(') + m.lift(RES, 'FLASHMEM static int FieldTenths(')
        + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)') + m.lift(m.UTIL, 'bool GetSaveOrDiscard(char *goback, char *Prompt)')
        + m.lift(SNOW, 'void RfSavedThenLeave(int view)') + m.lift(SNOW, 'bool RfSaveFirst(')
        + 'static void FltShow();\n' + block(FLT, 'static const int FLT_BYTES = 27;', 'FLASHMEM static void FltFail(') + m.lift(FLT, 'FLASHMEM void SaveFilters()')
        + m.lift(FCS, 'FLASHMEM static void FsBusy(') + m.lift(FCS, 'FLASHMEM static void WrS16(') + line(FCS, 'FLASHMEM static void FsTenths(') + m.lift(FCS, 'FLASHMEM static void FsShowKeepingTyped(')
        + block(FCS, 'static uint8_t CalRaw[8], CalWant[8];', 'FLASHMEM static void CalHead()') + m.lift(FCS, 'FLASHMEM static void CalHead()')
        + 'static void CalShowLevel() {}\n' + m.lift(FCS, 'FLASHMEM static void CalShow()') + m.lift(FCS, 'FLASHMEM static void CalGather()')
        + m.lift(FCS, 'FLASHMEM void SaveLevelTrims()') + 'void SaveLevelTrims();\n' + line(FCS, 'FLASHMEM static void CalSaveNow()') + m.lift(FCS, 'FLASHMEM void EndCalibrateView()'))
EXTRA = r'''
// ---- what the lifted pages are given
static uint8_t msp[8][40]; static int mspFn[8], mspLen[8], mspN = 0;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 8) { mspFn[mspN] = fn; mspLen[mspN] = len; if (data && len > 0) memcpy(msp[mspN], data, (size_t) len); ++mspN; } return 1; }
static bool ModelSeemsArmed(char *, size_t) { return false; } static bool RfPipeBlocked(char *, size_t) { return false; }
static bool FsRefused(const char *, bool) { return false; }
static int rfMenus = 0; static void RotorFlightStart() { ++rfMenus; }
int RfLeaveView = 0; void (*RfLeaveFn)() = nullptr;
char PipeRepBody[8] = ""; int PipeRepCode = 0;
''' + REAL + r'''
static void my24(int n) { if (n == 200) SaveFilters(); else if (n == 201) EndCalibrateView(); else if (n == 202) SaveLevelTrims(); else more24(n); }
static void addWordPages()
{
    Page f; f.id = 64;
    for (const char *t : { "tn1", "tn2", "tn4", "tn5", "tn7", "tn8", "tn9", "tn10", "busy", "t11", "t9" }) f.boxes[t] = { true, 0, "" };
    for (const char *v : { "tn0", "tn3", "tn6" }) f.boxes[v] = { false, 1, "" };
    f.boxes["tn2"].txt = "125"; f.boxes["tn5"].txt = "20"; f.boxes["tn7"].txt = "4"; f.boxes["tn8"].txt = "2.5"; f.boxes["tn9"].txt = "20"; f.boxes["tn10"].txt = "250";
    f.buttons["Save"] = { 0x00, 200, 0x00, 0x00 }; f.numberBoxes = { "tn9box" };
    screen.pages["FilterView"] = f;
    Page l; l.id = 74;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "busy", "t11", "t9" }) l.boxes[t] = { true, 0, "" };
    l.boxes["tn2"].txt = "1.5"; l.boxes["tn3"].txt = "-2.0"; l.buttons["OK"] = { 0x00, 201, 0x00, 0x00 }; l.buttons["Save"] = { 0x00, 202, 0x00, 0x00 };
    screen.pages["LevelView"] = l; screen.pages0 = screen.pages;
    FltHave = true; Flt_Was_Edited = true; FeatWant = FeatRaw = FEAT_DYN_NOTCH | FEAT_RPM_FILTER; memset(FltWant, 0, sizeof FltWant);
    FltWant[1] = 1; WrU16(FltWant, 2, 125); FltWant[25] = 0; FltWant[26] = 20; FltWant[19] = 4; FltWant[20] = 25; WrU16(FltWant, 21, 20); WrU16(FltWant, 23, 250); memcpy(FltRaw, FltWant, sizeof FltRaw);
    CalHave = true; Cal_Was_Edited = true; WrS16(CalWant, 0, 15); WrS16(CalWant, 2, -20); memcpy(CalRaw, CalWant, sizeof CalRaw); CalStep = CAL_IDLE; mspN = 0; rfMenus = 0;
}
static void sayFilters(const uint8_t *b) { say("lowpass 1 %u Hz, RPM filter min %u Hz, dynamic notches %u, Q %u.%u, %u to %u Hz", (unsigned) RdU16(b, 2), (unsigned) b[26], (unsigned) b[19], (unsigned) (b[20] / 10), (unsigned) (b[20] % 10), (unsigned) RdU16(b, 21), (unsigned) RdU16(b, 23)); }
'''
SCENES = r'''
    // (a) THE FILTERS PAGE, as the flight controller has it: lowpass 125 Hz, RPM filter 20 Hz, 4 dynamic notches, Q 2.5, 20 to 250 Hz.
    //     The pilot types 150 for the lowpass and presses Save - with nothing in the way: what the page holds is written
    more(); addWordPages(); extra24 = my24; SendCommand((char *) "page FilterView"); CurrentView = FILTERVIEW; loopFor(600);
    screen.pages["FilterView"].boxes["tn2"].txt = "150"; tapAt(5, "Save"); loopFor(4000);
    CHECK(mspN == 1 && mspFn[0] == 93 && RdU16(msp[0], 2) == 150 && msp[0][26] == 20 && msp[0][19] == 4 && msp[0][20] == 25 && RdU16(msp[0], 21) == 20 && RdU16(msp[0], 23) == 250 && boxesLostTold == 0);
    say("E2a. Filters, Save with nothing in the way: written to the flight controller: "); sayFilters(msp[0]); say("\n");
    //     ... Save, and 130 ms later a touch on one of the page's number boxes (the screen's keyboard comes up by itself)
    more(); addWordPages(); extra24 = my24; SendCommand((char *) "page FilterView"); CurrentView = FILTERVIEW; loopFor(600);
    screen.pages["FilterView"].boxes["tn2"].txt = "150"; tapAt(5, "Save"); tapAt(135, "tn9box"); loopFor(5000);
    say("E2a. Filters, Save and a touch on a number box 130 ms later: keyboards %d, boxes refused as off the page %d, the pilot told %d; MSP writes %d", screen.keyboards, offPage, boxesLostTold, mspN);
    if (mspN) { say(" (function %d): ", mspFn[0]); sayFilters(msp[0]); } say("\n");
    CHECK(mspN == 0);   // (what should hold: with a box unanswered NOTHING is written)
    //     ... one "sendme" answer lost at the first box (the screen has said its page before)
    more(); addWordPages(); extra24 = my24; SendCommand((char *) "page FilterView"); CurrentView = FILTERVIEW; loopFor(600); { char t[8]; GetText((char *) "tn1", t, sizeof t); } loopFor(50);
    screen.pages["FilterView"].boxes["tn2"].txt = "150"; screen.muteSendme = 1; tapAt(5, "Save"); loopFor(5000);
    say("E2a. Filters, Save with one 'sendme' answer lost: page unsaid %d, the pilot told %d; MSP writes %d", pageUnsaid, boxesLostTold, mspN);
    if (mspN) { say(" (function %d): ", mspFn[0]); sayFilters(msp[0]); } say("\n");
    CHECK(mspN == 0);
    //     ... and WHAT THE PAGE HOLDS AFTER SUCH A REFUSAL: the box "the screen did not answer ... Please press Save again" is answered.
    //     IN HAND is what was in hand before that Save - not what "no answer" made of the fields. ON THE PAGE is still WHAT THE PILOT
    //     TYPED (the tenth review: the page was drawn afresh from what was in hand - his 150 gone, and "Save again" saved the old 125):
    //     the next Save writes what the page shows, his 150
    more(); addWordPages(); extra24 = my24; SendCommand((char *) "page FilterView"); CurrentView = FILTERVIEW; loopFor(600); { char t[8]; GetText((char *) "tn1", t, sizeof t); } loopFor(50);
    screen.pages["FilterView"].boxes["tn2"].txt = "150"; screen.muteSendme = 1; tapAt(5, "Save"); tapAt(3500, "yes"); loopFor(6000);
    CHECK(mspN == 0 && RdU16(FltWant, 2) == 125 && FltWant[26] == 20 && FltWant[19] == 4 && FltWant[20] == 25 && RdU16(FltWant, 21) == 20 && RdU16(FltWant, 23) == 250);
    CHECK(screen.page == "FilterView" && screen.pages["FilterView"].boxes["tn2"].txt == "150" && screen.pages["FilterView"].boxes["tn10"].txt == "250" && screen.pages["FilterView"].boxes["tn5"].txt == "20" && screen.pages["FilterView"].boxes["tn8"].txt == "2.5");
    tapAt(5, "Save"); loopFor(4000); CHECK(mspN == 1 && RdU16(msp[0], 2) == 150 && msp[0][26] == 20 && msp[0][19] == 4 && msp[0][20] == 25 && RdU16(msp[0], 21) == 20 && RdU16(msp[0], 23) == 250);
    // (b) THE LEVEL PAGE: trims pitch 1.5, roll -2.0 in the flight controller; the pilot types 2.5 for the pitch and presses OK. One
    //     "sendme" answer is lost at the first box. "The edited level trims are not saved. Save now?" - Save.
    more(); addWordPages(); extra24 = my24; SendCommand((char *) "page LevelView"); CurrentView = LEVELVIEW; loopFor(600); { char t[8]; GetText((char *) "tn0", t, sizeof t); } loopFor(50);
    screen.pages["LevelView"].boxes["tn2"].txt = "2.5"; screen.muteSendme = 1; tapAt(5, "OK"); tapAt(3000, "yes"); loopFor(7000);
    say("E2b. Level, OK with one 'sendme' lost, then Save at the question: the pilot told %d; MSP writes %d", boxesLostTold, mspN);
    if (mspN) say(" (function %d): pitch %d, roll %d tenths of a degree", mspFn[0], RdS16(msp[0], 0), RdS16(msp[0], 2));
    say("; the page's boxes now: pitch '%s', roll '%s'; page %s\n", screen.pages["LevelView"].boxes["tn2"].txt.c_str(), screen.pages["LevelView"].boxes["tn3"].txt.c_str(), screen.page.c_str());
    CHECK(mspN == 0 && screen.pages["LevelView"].boxes["tn2"].txt == "2.5");
'''
sys.exit(lib.build_run('filters_level', SCENES, extra=EXTRA, more_defines=('FILTERVIEW', 'FILTER2VIEW', 'LEVELVIEW')))
