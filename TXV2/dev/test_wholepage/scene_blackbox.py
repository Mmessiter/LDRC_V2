#!/usr/bin/env python3
"""THE BLACK BOX PAGE: WHAT THE PILOT TYPED STAYS ON THE PAGE (the tenth review's finding 4 and its low 6, on the page its own
experiments did not reach; 15 Nov 2026). The page has one typed number (tn3, the seconds a recording runs on after disarming) and
a switch the screen flips by itself at the touch (tn4, "roll over when full").
 - Save with a box unanswered: "The screen did not answer ... Please press Save again" - the page was then drawn afresh from what
   was IN HAND, the typed number gone, and Save again saved the old one. Now what was typed stays, and Save again saves it.
 - Save refused before anything is read (the model seems armed, say): the same.
 - The roll switch tapped and the tap's gather loses a box: nothing is taken - and the screen's own switch, which turned under
   the finger, is drawn back as it is in hand; the typed number stays.
The REAL BbGather, BbShow, BbHead, SaveBlackbox, BlackboxRollTapped, FsNum, FsShowKeepingTyped (RF_FcSetup.h), FieldNumber
(RF_Rescue.h) and RfFieldsMissed (Nextion.h) over the pretend screen."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES, FCS = (m.release(m.src('include/' + f)) for f in ('RF_Rescue.h', 'RF_FcSetup.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
def block(text, a, b): return text[text.index(a):text.index(b)]
REAL = (line(RES, 'FLASHMEM static uint16_t RdU16(') + m.lift(RES, 'FLASHMEM static void WrU16(') + line(FCS, 'FLASHMEM static uint32_t RdU32(')
        + m.lift(RES, 'FLASHMEM static long FieldNumber(') + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)')
        + m.lift(FCS, 'FLASHMEM static void FsBusy(') + line(FCS, 'FLASHMEM static void FsNum(') + m.lift(FCS, 'FLASHMEM static void FsShowKeepingTyped(')
        + block(FCS, 'static uint8_t BbRaw[16], BbWant[16];', 'FLASHMEM static void BbFail(')
        + line(FCS, 'FLASHMEM void BlackboxWasEdited()') + m.lift(FCS, 'FLASHMEM void BlackboxRollTapped()') + m.lift(FCS, 'FLASHMEM void SaveBlackbox()'))
EXTRA = r'''
// ---- what the lifted page is given
static uint8_t msp[8][40]; static int mspFn[8], mspLen[8], mspN = 0;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 8) { mspFn[mspN] = fn; mspLen[mspN] = len; if (data && len > 0) memcpy(msp[mspN], data, (size_t) len); ++mspN; } return 1; }
static bool refuseNow = false;
static bool FsRefused(const char *page, bool) { if (!refuseNow) return false; MsgBox((char *) page, (char *) "Not while the model is armed."); return true; }   // (the guard every save passes: here, by hand)
''' + REAL + r'''
static void my24(int n) { if (n == 200) SaveBlackbox(); else if (n == 101) BlackboxRollTapped(); else more24(n); }
static void addBlackbox()
{
    Page b; b.id = 73;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "tn5", "tn6", "busy", "t11", "t9" }) b.boxes[t] = { true, 0, "" };
    b.boxes["tn4"] = { false, 0, "" };
    b.buttons["Save"] = { 0x00, 200, 0x00, 0x00 }; b.buttons["Roll"] = { 0x00, 101, 0x00, 0x00 };
    screen.pages["BlackboxView"] = b; screen.pages0 = screen.pages;
    memset(BbWant, 0, sizeof BbWant); BbWant[0] = 1; BbWant[1] = 1; BbWant[2] = 2; BbWant[3] = 8; BbWant[11] = 0; BbWant[12] = 10;   // to the FC's memory, whenever armed, 1 in 8, no roll-over, 10 s on
    memcpy(BbRaw, BbWant, sizeof BbRaw); BbHave = true; Bb_Was_Edited = true; BbStep = BB_IDLE; mspN = 0; refuseNow = false; extra24 = my24;
}
static void openBlackbox()
{
    SendCommand((char *) "page BlackboxView"); CurrentView = BLACKBOXVIEW; BbHead(); BbShow(); loopFor(600); { char t[8]; GetText((char *) "t9", t, sizeof t); } loopFor(50);
}
static const char *shown() { return screen.pages["BlackboxView"].boxes["tn3"].txt.c_str(); }
'''
SCENES = r'''
    // (0) nothing in the way: 45 typed for the seconds, Save: written
    more(); addBlackbox(); openBlackbox(); CHECK(!strcmp(shown(), "10"));
    screen.pages["BlackboxView"].boxes["tn3"].txt = "45"; tapAt(5, "Save"); loopFor(3000);
    CHECK(mspN == 1 && mspFn[0] == 81 && msp[0][11] == 45 && boxesLostTold == 0);
    // (1) Save with one "which page?" answer lost: refused, the box answered - the page still shows 45; Save again saves 45
    more(); addBlackbox(); openBlackbox(); screen.pages["BlackboxView"].boxes["tn3"].txt = "45";
    screen.muteSendme = 1; tapAt(5, "Save"); tapAt(3500, "yes"); loopFor(6000);
    say("X1. the black box page, 45 typed, Save with a box unanswered: MSP writes %d; in hand %u s; the page now shows '%s'; told %d; page %s\n", mspN, (unsigned) BbWant[12], shown(), boxesLostTold, screen.page.c_str());
    CHECK(mspN == 0 && BbWant[12] == 10 && boxesLostTold == 1 && screen.page == "BlackboxView");
    CHECK(!strcmp(shown(), "45"));                                               // what he typed is still there ...
    tapAt(5, "Save"); loopFor(4000);
    say("X1. ... Save again: MSP writes %d, the seconds written %u\n", mspN, mspN ? (unsigned) msp[0][11] : 0u);
    CHECK(mspN == 1 && msp[0][11] == 45);                                        // ... and "Save again" saves it
    // (2) Save refused before anything is read (a box says why): the same
    more(); addBlackbox(); openBlackbox(); screen.pages["BlackboxView"].boxes["tn3"].txt = "45";
    refuseNow = true; tapAt(5, "Save"); tapAt(2500, "yes"); loopFor(5000); refuseNow = false;
    say("X2. ... Save refused with a box: MSP writes %d; the page now shows '%s'\n", mspN, shown());
    CHECK(mspN == 0 && !strcmp(shown(), "45") && screen.page == "BlackboxView");
    tapAt(5, "Save"); loopFor(4000); CHECK(mspN == 1 && msp[0][11] == 45);
    // (3) the roll-over switch tapped ON (the screen flips its own switch at the touch), the tap's gather loses a box: nothing taken, the screen's
    //     switch drawn back as it is in hand - and the number he had typed is left alone
    more(); addBlackbox(); openBlackbox(); Bb_Was_Edited = false; screen.pages["BlackboxView"].boxes["tn3"].txt = "45";
    screen.pages["BlackboxView"].boxes["tn4"].val = 1;                           // (the screen's own flip, at the touch)
    screen.muteSendme = 1; tapAt(5, "Roll"); loopFor(4000);
    say("X3. the roll-over switch tapped, the tap's gather lost a box: the screen's switch shows %ld; in hand %u; edited %d; the seconds box shows '%s'; told %d\n",
        screen.pages["BlackboxView"].boxes["tn4"].val, (unsigned) BbWant[11], (int) Bb_Was_Edited, shown(), boxesLostTold);
    CHECK(boxesLostTold == 1 && BbWant[11] == 0 && !Bb_Was_Edited);
    CHECK(screen.pages["BlackboxView"].boxes["tn4"].val == 0);                   // the page shows what is in hand
    CHECK(!strcmp(shown(), "45"));                                               // ... and what was typed
    // ... and with nothing in the way the tap is taken: the switch on, the typed number gathered with it
    more(); addBlackbox(); openBlackbox(); Bb_Was_Edited = false; screen.pages["BlackboxView"].boxes["tn3"].txt = "45"; screen.pages["BlackboxView"].boxes["tn4"].val = 1;
    tapAt(5, "Roll"); loopFor(3000);
    CHECK(BbWant[11] == 1 && BbWant[12] == 45 && Bb_Was_Edited && screen.pages["BlackboxView"].boxes["tn4"].val == 1 && boxesLostTold == 0);
'''
sys.exit(lib.build_run('blackbox', SCENES, extra=EXTRA, more_defines=('BLACKBOXVIEW',)))
