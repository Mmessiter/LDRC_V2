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
        + line(FLT, 'FLASHMEM void FilterWasEdited()') + m.lift(FLT, 'FLASHMEM static bool FltEdited()') + line(FLT, 'FLASHMEM void FilterDynNotchEnableTapped()') + m.lift(FCS, 'FLASHMEM static void FsBusy(') + m.lift(FCS, 'FLASHMEM static void WrS16(') + line(FCS, 'FLASHMEM static void FsTenths(') + m.lift(FCS, 'FLASHMEM static void FsShowKeepingTyped(')
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
static void my24(int n) { if (n == 101) FilterDynNotchEnableTapped(); else if (n == 200) SaveFilters(); else if (n == 201) EndCalibrateView(); else if (n == 202) SaveLevelTrims(); else more24(n); }
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
    // THE FILTERS PAGE: the dynamic filter is ON in the flight controller (its Enable, tn6, is a SWITCH on the screen: the screen flips it at the
    // touch, then prints the code - the screen's src/main.cpp 3183, 3225). The pilot taps it OFF. The tap's gather loses a box (one "which page?"
    // answer lost): "the tap does nothing" (RF_Filters.h FltEdited) - but the screen's switch HAS flipped.
    more(); addWordPages(); extra24 = my24; SendCommand((char *) "page FilterView"); CurrentView = FILTERVIEW; loopFor(600); { char t[8]; GetText((char *) "tn1", t, sizeof t); } loopFor(50);
    Flt_Was_Edited = false; screen.pages["FilterView"].buttons["DynEnable"] = { 0x00, 101, 0x00, 0x00 };
    screen.pages["FilterView"].boxes["tn6"].val = 0;                      // (the screen's own flip, at the touch)
    screen.muteSendme = 1; tapAt(5, "DynEnable"); loopFor(4000);
    say("W1. the dynamic filter's Enable tapped OFF, the tap's gather lost a box: the screen's switch shows %ld; in hand: dynamic filter %s; the page edited: %d; the pilot told (a sound, a log line) %d\n",
        screen.pages["FilterView"].boxes["tn6"].val, DynNotchOn() ? "ON" : "off", (int) Flt_Was_Edited, boxesLostTold);
    CHECK(boxesLostTold == 1);
    CHECK((screen.pages["FilterView"].boxes["tn6"].val != 0) == DynNotchOn());   // what should hold: the page shows what is in hand
'''
sys.exit(lib.build_run('switchflip', SCENES, extra=EXTRA, more_defines=('FILTERVIEW', 'FILTER2VIEW', 'LEVELVIEW')))
