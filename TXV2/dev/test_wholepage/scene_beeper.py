#!/usr/bin/env python3
"""E3: a page whose SAVE is guarded (RfGatherStart ... RfFieldsMissed) but whose OK is not: Beeper & name (RF_Beeper.h).
OK with unsaved edits gathers the page with no look at "was every box answered?", asks "Save now?", and Save SHOWS what was
gathered before it saves. The save is refused (the same button's work has no answers) - "Please press Save again" - and the
page now holds what no answer made of its boxes. The next Save sends that. (EndTravelView, EndBatteryView, EndFilterView,
EndBlackboxView, EndCalibrateView and EndJobsView are built the same way.)"""
import sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES, BPR, FCS, SNOW = (m.release(m.src('include/' + f)) for f in ('RF_Rescue.h', 'RF_Beeper.h', 'RF_FcSetup.h', 'RF_SaveNow.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
def block(text, a, b): return text[text.index(a):text.index(b)]
REAL = (m.lift(RES, 'FLASHMEM static long FieldNumber(') + line(FCS, 'FLASHMEM static uint32_t RdU32(') + line(FCS, 'FLASHMEM static void FsNum(') + m.lift(FCS, 'FLASHMEM static void FsBusy(')
        + m.lift(FCS, 'FLASHMEM static void FsShowKeepingTyped(')
        + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)') + m.lift(m.UTIL, 'bool GetSaveOrDiscard(char *goback, char *Prompt)')
        + m.lift(SNOW, 'void RfSavedThenLeave(int view)') + m.lift(SNOW, 'bool RfSaveFirst(')
        + block(BPR, 'static const int BP_BYTES = 9;', 'FLASHMEM void BeeperPoll()') + 'void SaveBeeper();\n' + line(BPR, 'FLASHMEM static void BpSaveNow()')
        + m.lift(BPR, 'FLASHMEM void EndBeeperView()') + m.lift(BPR, 'FLASHMEM void SaveBeeper()'))
EXTRA = r'''
static uint8_t msp[8][40]; static int mspFn[8], mspLen[8], mspN = 0;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 8) { mspFn[mspN] = fn; mspLen[mspN] = len; memset(msp[mspN], 0, 40); if (data && len > 0) memcpy(msp[mspN], data, (size_t) len); ++mspN; } return 1; }
static bool refuseNow = false;
static bool FsRefused(const char *page, bool) { if (!refuseNow) return false; MsgBox((char *) page, (char *) "Model is armed: the safety is off.\r\nSafety on first."); return true; }   // (the guard every save passes: here, by hand)
static void FsFail(const char *, const char *) {}
static int rfMenus = 0; static void RotorFlightStart() { ++rfMenus; }
int RfLeaveView = 0; void (*RfLeaveFn)() = nullptr;
''' + REAL + r'''
static void my24(int n) { if (n == 233) EndBeeperView(); else if (n == 234) SaveBeeper(); else more24(n); }
static void addBeeper()
{
    Page b; b.id = 84;
    for (const char *t : { "tn0", "tn1", "busy", "t11", "t9" }) b.boxes[t] = { true, 0, "" };
    for (int k = 1; k <= 10; ++k) { char n[8]; snprintf(n, sizeof n, "sw%d", k); b.boxes[n] = { false, 1, "" }; }
    b.boxes["tn0"].txt = "RAW 420"; b.boxes["tn1"].txt = "3";
    b.buttons["OK"] = { 0x00, 233, 0x00, 0x00 }; b.buttons["Save"] = { 0x00, 234, 0x00, 0x00 };
    screen.pages["BeeperView"] = b; screen.pages0 = screen.pages;
    BpHave = true; Bp_Was_Edited = true; memset(BpWant, 0, sizeof BpWant); BpWant[4] = 3; memcpy(BpRaw, BpWant, sizeof BpRaw); strcpy(BpNameRaw, "RAW 420"); strcpy(BpNameWant, "RAW 420"); BpStep = BP_IDLE; mspN = 0; rfMenus = 0;
}
'''
SCENES = r'''
    // The flight controller holds the name "RAW 420" and beacon tone 3. The pilot types the name "RAW 580" and presses OK.
    // One "sendme" answer is lost at the first box. "The edited beeper and name are not saved. Save now?" - Save.
    // "The screen did not answer for one of the boxes, so NOTHING was sent. Please press Save again." - OK, and Save again.
    more(); addBeeper(); extra24 = my24; SendCommand((char *) "page BeeperView"); CurrentView = BEEPERVIEW; loopFor(600); GetValue((char *) "sw1"); loopFor(50);
    screen.pages["BeeperView"].boxes["tn0"].txt = "RAW 580"; screen.muteSendme = 1;
    tapAt(5, "OK"); tapAt(3000, "yes"); tapAt(6000, "yes"); loopFor(8000);
    say("E3. Beeper, OK with one 'sendme' lost, Save at the question, OK at the refusal: told %d, log lines:", boxesLostTold); for (auto &l : logLines) say(" [%s]", l.c_str());
    say("\n    MSP writes so far %d; the page %s now holds the name '%s' and tone '%s' (the pilot typed 'RAW 580', tone 3)\n", mspN, screen.page.c_str(), screen.pages["BeeperView"].boxes["tn0"].txt.c_str(), screen.pages["BeeperView"].boxes["tn1"].txt.c_str());
    CHECK(mspN == 0);                                                              // (the refusal: nothing was sent - true so far)
    CHECK(!strcmp(BpNameWant, "RAW 420") && BpWant[4] == 3 && !memcmp(BpWant, BpRaw, sizeof BpRaw));   // (... and what the gather writes into is as it was: no part of a page that lost a box is kept)
    CHECK(screen.pages["BeeperView"].boxes["tn0"].txt == "RAW 580");               // (what should hold: the page still has what the pilot typed)
    tapAt(5, "Save"); loopFor(4000);                                               // "Please press Save again"
    say("    Save again: MSP writes %d", mspN); if (mspN) say(" (function %d, %d byte(s): first byte %u = '%s')", mspFn[0], mspLen[0], (unsigned) msp[0][0], (char *) msp[0]); say("\n");
    CHECK(mspN == 1 && mspFn[0] == 11 && !strcmp((char *) msp[0], "RAW 580"));     // (what should hold: the name the pilot typed is what is written)
    // ... the gather by itself (the author's own): the name and the tone typed anew, the page's LAST box with no answer - neither is taken
    more(); addBeeper(); extra24 = my24; SendCommand((char *) "page BeeperView"); CurrentView = BEEPERVIEW; loopFor(600); GetValue((char *) "sw1"); loopFor(50);
    screen.pages["BeeperView"].boxes["tn0"].txt = "RAW 700"; screen.pages["BeeperView"].boxes["tn1"].txt = "5"; screen.mute.insert("sw10");
    { const uint32_t lost0 = BoxesLost; BpGather(); CHECK(BoxesLost != lost0 && !strcmp(BpNameWant, "RAW 420") && BpWant[4] == 3 && !memcmp(BpWant, BpRaw, sizeof BpRaw)); }
    more(); addBeeper(); extra24 = my24; SendCommand((char *) "page BeeperView"); CurrentView = BEEPERVIEW; loopFor(600); GetValue((char *) "sw1"); loopFor(50);
    screen.pages["BeeperView"].boxes["tn0"].txt = "RAW 700"; screen.pages["BeeperView"].boxes["tn1"].txt = "5";
    { const uint32_t lost0 = BoxesLost; BpGather(); CHECK(BoxesLost == lost0 && !strcmp(BpNameWant, "RAW 700") && BpWant[4] == 5); }
    // A SAVE THAT IS REFUSED BEFORE ANYTHING IS READ (the eleventh review, reviewer B's experiment 2): "Model is armed: the safety is off. Safety on
    // first." - the commonest box there is. The page was then drawn afresh from what was IN HAND: the name he had typed, the tone, every switch he
    // had turned - gone; he put the safety on, pressed Save again, and the OLD values were written ("Saved"). What he typed and turned stays now.
    more(); addBeeper(); extra24 = my24; SendCommand((char *) "page BeeperView"); CurrentView = BEEPERVIEW; BpHead(); BpShow(); loopFor(600); GetValue((char *) "sw1"); loopFor(50);
    { Page &pg = screen.pages["BeeperView"];
      pg.boxes["tn0"].txt = "RAW 580"; pg.boxes["tn1"].txt = "5"; pg.boxes["sw1"].val = 0; pg.boxes["sw2"].val = 0; Bp_Was_Edited = true;
      refuseNow = true; tapAt(5, "Save"); tapAt(2500, "yes"); loopFor(5000); refuseNow = false;
      say("E4. Beeper: the name 'RAW 580', tone 5, two beeps turned off; Save refused with a box: MSP writes %d; the page now shows name '%s', tone '%s', switches 1,2 = %ld,%ld\n",
          mspN, pg.boxes["tn0"].txt.c_str(), pg.boxes["tn1"].txt.c_str(), pg.boxes["sw1"].val, pg.boxes["sw2"].val);
      CHECK(mspN == 0 && screen.page == "BeeperView");
      CHECK(pg.boxes["tn0"].txt == "RAW 580" && pg.boxes["tn1"].txt == "5" && pg.boxes["sw1"].val == 0 && pg.boxes["sw2"].val == 0);   // what he typed and turned is still there ...
      CHECK(pg.boxes["sw3"].val == 1);
      tapAt(5, "Save"); loopFor(4000);
      say("E4. ... Save again: MSP writes %d", mspN); if (mspN) say(" (function %d: '%s')", mspFn[0], (char *) msp[0]); say("; in hand: tone %u\n", (unsigned) BpWant[4]);
      CHECK(mspN == 1 && mspFn[0] == 11 && !strcmp((char *) msp[0], "RAW 580") && BpWant[4] == 5);                                     // ... and "Save again" saves it
      CHECK((RdU32(BpWant, 0) & BpFlag(BP_BUZZ[0])) && (RdU32(BpWant, 0) & BpFlag(BP_BUZZ[1])) && !(RdU32(BpWant, 0) & BpFlag(BP_BUZZ[2]))); }   // (the two beeps he turned off are off in what is written)
    // ... and BpShow by itself still draws everything when nothing is being kept (the page after a read)
    more(); addBeeper(); extra24 = my24; SendCommand((char *) "page BeeperView"); CurrentView = BEEPERVIEW; loopFor(600);
    { Page &pg = screen.pages["BeeperView"]; pg.boxes["tn0"].txt = "x"; pg.boxes["tn1"].txt = "9"; pg.boxes["sw1"].val = 0;
      BpShow(); loopFor(300); CHECK(pg.boxes["tn0"].txt == "RAW 420" && pg.boxes["tn1"].txt == "3" && pg.boxes["sw1"].val == 1); }
'''
sys.exit(lib.build_run('beeper', SCENES, extra=EXTRA, more_defines=('BEEPERVIEW',)))
