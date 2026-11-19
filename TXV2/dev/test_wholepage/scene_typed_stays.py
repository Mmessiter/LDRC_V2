#!/usr/bin/env python3
"""WHAT THE PILOT TYPED STAYS ON THE PAGE - where no gather stands in front of a box (the eleventh review, reviewer B's experiment 2; 15 Nov 2026).
These pages take their typed fields only when they gather (at Save). A routine that puts up a box BEFORE any gather - the Save's own guard
"Model is armed: the safety is off. Safety on first.", Calibrate's "Is the model level and perfectly still?", the black box's "Erase every
flight log ...?" - drew the page afresh from what was IN HAND when the box had gone: the numbers he had just typed were written over with the
old ones; he put the safety on, pressed Save again, and the OLD values were written - "Saved". (The tenth review's cure, FsShowKeepingTyped,
had been given to the Black box's and the Level page's Save only.)
 B  the Battery page: 12 cells, 5000 mAh, warning 3.60 V typed; Save with the safety off (the box, answered); the safety on, Save again
 C  the Level page: trims typed; Calibrate - refused (armed) / asked and answered No / asked and answered Yes
 X  the Black box page: the seconds typed; Erase - refused / asked and answered No / asked and answered Yes
What must hold each time: what he typed is still on the page, and the Save that follows writes it.
The REAL SaveBattery, BatShow, BatHead, BatGather, FsRefused, CalibrateNow, CalShow, CalGather, SaveLevelTrims, BlackboxErase, BbShow, BbGather,
SaveBlackbox, FsShowKeepingTyped (RF_FcSetup.h), RfFieldsMissed (Nextion.h), MsgBox and GetConfirmation over the pretend screen."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES, FCS, SRV = (m.release(m.src('include/' + f)) for f in ('RF_Rescue.h', 'RF_FcSetup.h', 'RF_Servos.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
def block(text, a, b): return text[text.index(a):text.index(b)]
REAL = (line(RES, 'FLASHMEM static uint16_t RdU16(') + m.lift(RES, 'FLASHMEM static void WrU16(') + line(SRV, 'FLASHMEM static int RdS16(')
        + m.lift(RES, 'FLASHMEM static long FieldNumber(') + m.lift(RES, 'FLASHMEM static int FieldTenths(')
        + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)')
        + block(FCS, 'FLASHMEM static void FsBusy(', 'FLASHMEM static void FsFail(')            # FsBusy, FsNum, FsHundredths, FsTenths, FsShowKeepingTyped, FsVis, FieldHundredths, WrS16, RdU32
        + m.lift(FCS, 'FLASHMEM static bool FsRefused(')                                         # the REAL guard every save and action passes
        + block(FCS, 'static const int BAT_BYTES = 15;', 'FLASHMEM static void BatFail(') + m.lift(FCS, 'FLASHMEM void SaveBattery()')
        + block(FCS, 'static uint8_t BbRaw[16], BbWant[16];', 'FLASHMEM static void BbFail(') + line(FCS, 'FLASHMEM void BlackboxWasEdited()')
        + m.lift(FCS, 'FLASHMEM void SaveBlackbox()') + m.lift(FCS, 'FLASHMEM void BlackboxErase()')
        + block(FCS, 'static uint8_t CalRaw[8], CalWant[8];', 'FLASHMEM static void CalHead()') + m.lift(FCS, 'FLASHMEM static void CalHead()')
        + 'static void CalShowLevel() {}\n' + m.lift(FCS, 'FLASHMEM static void CalShow()') + m.lift(FCS, 'FLASHMEM static void CalGather()')
        + m.lift(FCS, 'FLASHMEM void CalibrateNow()') + m.lift(FCS, 'FLASHMEM void SaveLevelTrims()'))
EXTRA = r'''
static uint8_t msp[8][40]; static int mspFn[8], mspLen[8], mspN = 0;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 8) { mspFn[mspN] = fn; mspLen[mspN] = len; memset(msp[mspN], 0, 40); if (data && len > 0) memcpy(msp[mspN], data, (size_t) len); ++mspN; } return 1; }
static bool safetyOff = false;   // (Parameters.h ModelSeemsArmed: a Rotorflight model with the safety switch off)
static bool ModelSeemsArmed(char *why, size_t n) { if (!safetyOff) return false; snprintf(why, n, "Model is armed: the safety is off.\r\nSafety on first."); return true; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static void FsFail(const char *, const char *) {}
char PipeRepBody[8] = ""; int PipeRepCode = 0;
''' + REAL + r'''
static void my7(int n) { if (n == 2) Confirmed[0] = 'N'; else more7(n); }   // (the question's No)
static void my24(int n) { if (n == 157) SaveBattery(); else if (n == 160) CalibrateNow(); else if (n == 161) SaveLevelTrims(); else if (n == 162) BlackboxErase(); else if (n == 163) SaveBlackbox(); else more24(n); }
static void addPages3()
{
    Page b; b.id = 72;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "busy", "t11", "t9" }) b.boxes[t] = { true, 0, "" };
    b.buttons["Save"] = { 0x00, 157, 0x00, 0x00 };
    screen.pages["BatteryView"] = b;
    Page l; l.id = 74;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "busy", "t11", "t9" }) l.boxes[t] = { true, 0, "" };
    l.buttons["Calibrate"] = { 0x00, 160, 0x00, 0x00 }; l.buttons["Save"] = { 0x00, 161, 0x00, 0x00 };
    screen.pages["LevelView"] = l;
    Page x; x.id = 73;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "tn5", "tn6", "busy", "t11", "t9" }) x.boxes[t] = { true, 0, "" };
    x.boxes["tn4"] = { false, 0, "" };
    x.buttons["Erase"] = { 0x00, 162, 0x00, 0x00 }; x.buttons["Save"] = { 0x00, 163, 0x00, 0x00 };
    screen.pages["BlackboxView"] = x; screen.pages0 = screen.pages;
    // the flight controller's battery setup: 6 cells, 2200 mAh, full 4.20, warning 3.50, empty 3.30, highest 4.30
    memset(BatWant, 0, sizeof BatWant); BatWant[2] = 6; WrU16(BatWant, 0, 2200); WrU16(BatWant, 9, 420); WrU16(BatWant, 11, 350); WrU16(BatWant, 5, 330); WrU16(BatWant, 7, 430);
    memcpy(BatRaw, BatWant, sizeof BatRaw); BatHave = true; Bat_Was_Edited = false; BatStep = BAT_IDLE; BatN = 27; VmN = CmN = 0;
    // its level trims: roll 1.5, pitch -2.0 degrees
    CalHave = true; Cal_Was_Edited = false; WrS16(CalWant, 0, 15); WrS16(CalWant, 2, -20); memcpy(CalRaw, CalWant, sizeof CalRaw); CalStep = CAL_IDLE;
    // its black box: to the FC's memory, whenever armed, 1 in 8, 10 s on after disarming
    memset(BbWant, 0, sizeof BbWant); BbWant[0] = 1; BbWant[1] = 1; BbWant[2] = 2; BbWant[3] = 8; BbWant[11] = 0; BbWant[12] = 10; memcpy(BbRaw, BbWant, sizeof BbRaw); BbHave = true; Bb_Was_Edited = false; BbStep = BB_IDLE;
    BbMemN = 13; BbMem[0] = 3;   // (a memory chip there is, and it can be erased)
    screen.pages["PopupView"].buttons["no"] = { 0x82, 0x00, 0x00, 0x00 };   // (the question's No)
    mspN = 0; safetyOff = false; BoundFlag = ModelMatched = true; extra24 = my24; extra7 = my7;
}
static const char *box(const char *page, const char *name) { return screen.pages[page].boxes[name].txt.c_str(); }
'''
SCENES = r'''
    // B. THE BATTERY PAGE. The pilot changes the pack: 12 cells, 5000 mAh, warning at 3.60 V - and presses Save with the safety switch off.
    more(); addPages3(); SendCommand((char *) "page BatteryView"); CurrentView = BATTERYVIEW; BatHead(); BatShow(); loopFor(600); { char t[8]; GetText((char *) "t9", t, sizeof t); } loopFor(50);
    { Page &pg = screen.pages["BatteryView"];
      CHECK(pg.boxes["tn0"].txt == "6" && pg.boxes["tn1"].txt == "2200" && pg.boxes["tn5"].txt == "3.50");
      pg.boxes["tn0"].txt = "12"; pg.boxes["tn1"].txt = "5000"; pg.boxes["tn5"].txt = "3.60"; Bat_Was_Edited = true;
      safetyOff = true; tapAt(5, "Save"); tapAt(2500, "yes"); loopFor(5000);
      say("B1. typed 12 cells, 5000 mAh, warning 3.60; Save with the safety off -> the box (answered): MSP writes %d; page %s; THE PAGE NOW SHOWS cells '%s', capacity '%s', warning '%s'\n",
          mspN, screen.page.c_str(), pg.boxes["tn0"].txt.c_str(), pg.boxes["tn1"].txt.c_str(), pg.boxes["tn5"].txt.c_str());
      CHECK(mspN == 0 && screen.page == "BatteryView");
      CHECK(pg.boxes["tn0"].txt == "12" && pg.boxes["tn1"].txt == "5000" && pg.boxes["tn5"].txt == "3.60");     // what he typed is still on the page ...
      CHECK(pg.boxes["tn2"].txt.size() > 0);                                                                     // (... and what is not typed was drawn again: the voltage source's word)
      safetyOff = false; tapAt(5, "Save"); loopFor(4000);
      say("B2. safety on, Save again: MSP writes %d", mspN); if (mspN) say(" (function %d): cells %u, capacity %u mAh, warning %u.%02u V", mspFn[0], (unsigned) msp[0][2], (unsigned) RdU16(msp[0], 0), (unsigned) (RdU16(msp[0], 11) / 100), (unsigned) (RdU16(msp[0], 11) % 100)); say("\n");
      CHECK(mspN == 1 && mspFn[0] == 33 && msp[0][2] == 12 && RdU16(msp[0], 0) == 5000 && RdU16(msp[0], 11) == 360); }   // ... and "Save again" saves it
    // C. THE LEVEL PAGE. He types the trims 2.5 and -1.0 and presses Calibrate: (0) refused - the safety is off; (1) asked, and answered No;
    //    (2) asked, and answered Yes. Each time the trims he typed are still there, and Save writes them.
    for (int how = 0; how < 3; ++how)
    {
        more(); addPages3(); SendCommand((char *) "page LevelView"); CurrentView = LEVELVIEW; CalHead(); CalShow(); loopFor(600); { char t[8]; GetText((char *) "tn0", t, sizeof t); } loopFor(50);
        Page &pg = screen.pages["LevelView"];
        CHECK(pg.boxes["tn2"].txt == "1.5" && pg.boxes["tn3"].txt == "-2.0");
        pg.boxes["tn2"].txt = "2.5"; pg.boxes["tn3"].txt = "-1.0"; Cal_Was_Edited = true;
        safetyOff = how == 0; tapAt(5, "Calibrate"); tapAt(2500, how == 1 ? "no" : "yes"); loopFor(5000); safetyOff = false;
        say("C%d. the trims 2.5 and -1.0 typed; Calibrate %s: MSP asks %d%s; the page now shows '%s' and '%s'\n", how, how == 0 ? "refused (the safety is off)" : how == 1 ? "asked - No" : "asked - Yes",
            mspN, mspN ? (mspFn[0] == 205 ? " (the calibration)" : " (?)") : "", pg.boxes["tn2"].txt.c_str(), pg.boxes["tn3"].txt.c_str());
        CHECK(mspN == (how == 2 ? 1 : 0) && (how != 2 || mspFn[0] == 205) && screen.page == "LevelView");
        CHECK(pg.boxes["tn2"].txt == "2.5" && pg.boxes["tn3"].txt == "-1.0");
        CalStep = CAL_IDLE; mspN = 0; tapAt(5, "Save"); loopFor(4000);
        say("    ... Save: MSP asks %d (function %d); in hand %d and %d; page %s; edited %d\n", mspN, mspN ? mspFn[0] : -1, RdS16(CalWant, 0), RdS16(CalWant, 2), screen.page.c_str(), (int) Cal_Was_Edited);
        CHECK(mspN == 1 && RdS16(CalWant, 0) == 25 && RdS16(CalWant, 2) == -10);
    }
    // X. THE BLACK BOX PAGE. He types 45 for the seconds and presses Erase: (0) refused; (1) asked, and answered No; (2) asked, and answered Yes
    for (int how = 0; how < 3; ++how)
    {
        more(); addPages3(); SendCommand((char *) "page BlackboxView"); CurrentView = BLACKBOXVIEW; BbHead(); BbShow(); loopFor(600); { char t[8]; GetText((char *) "t9", t, sizeof t); } loopFor(50);
        Page &pg = screen.pages["BlackboxView"];
        CHECK(pg.boxes["tn3"].txt == "10");
        pg.boxes["tn3"].txt = "45"; Bb_Was_Edited = true;
        safetyOff = how == 0; tapAt(5, "Erase"); tapAt(2500, how == 1 ? "no" : "yes"); loopFor(5000); safetyOff = false;
        say("X%d. 45 s typed; Erase %s: MSP asks %d%s; the page now shows '%s'\n", how, how == 0 ? "refused (the safety is off)" : how == 1 ? "asked - No" : "asked - Yes", mspN, mspN ? (mspFn[0] == 72 ? " (the erase)" : " (?)") : "", pg.boxes["tn3"].txt.c_str());
        CHECK(mspN == (how == 2 ? 1 : 0) && (how != 2 || mspFn[0] == 72) && screen.page == "BlackboxView");
        CHECK(pg.boxes["tn3"].txt == "45");
        BbStep = BB_IDLE; mspN = 0; tapAt(5, "Save"); loopFor(4000);
        say("    ... Save: MSP asks %d (function %d, byte 11 = %u); in hand %u s; page %s\n", mspN, mspN ? mspFn[0] : -1, mspN ? (unsigned) msp[0][11] : 0u, (unsigned) BbWant[12], screen.page.c_str());
        CHECK(mspN == 1 && mspFn[0] == 81 && msp[0][11] == 45);
    }
    BoundFlag = ModelMatched = false;
'''
sys.exit(lib.build_run('typed_stays', SCENES, extra=EXTRA, more_defines=('BATTERYVIEW', 'BATSENSORSVIEW', 'LEVELVIEW', 'BLACKBOXVIEW')))
