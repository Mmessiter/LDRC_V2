#!/usr/bin/env python3
"""Reviewer B (15th review): the Rescue page's two SWITCHES after a save that FAILS.
The fourteenth review's cure makes RescueFail draw NOTHING of the page (RfKeepTyped: RescueShow returns at once). The two switches (tn0 Enable rescue,
tn1 Flip) are SWITCH parts on the screen: the screen flips them at the touch and THEN prints the code; this board keeps their state in hand
(RescueMode, RescueFlip) and the gather takes THAT - it never asks the screen. A tap whose code this board does not obey (a press belongs to its page:
made as the failure's box was on its way to the screen) leaves the screen's switch flipped and the state in hand as it was. The old draw put the
switch back as in hand; the new one leaves it. Save again then writes what is in hand - not what the page shows.
The REAL RescueFail, RescuePoll, SaveRescue, RescueModeTapped, the gathers and shows, MsgBox, GetYesOrNo over the pretend screen and a pretend pipe."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES = m.release(open(os.environ['RB_RESCUE_H'], encoding='utf-8', errors='replace').read() if os.environ.get('RB_RESCUE_H') else m.src('include/RF_Rescue.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
def block(text, a, b): return text[text.index(a):text.index(b)]
REAL = (lib.LEAVE + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)')
        + block(RES, 'static const int RESCUE_BYTES = 28;', 'FLASHMEM void RescueBankChanged()')
        + m.lift(RES, 'FLASHMEM void RescuePoll()') + m.lift(RES, 'FLASHMEM static void RescueRead()')
        + m.lift(RES, 'FLASHMEM void RescueWasEdited()') + line(RES, 'static int RescueModeWhenOn = 1;') + m.lift(RES, 'FLASHMEM void RescueModeTapped()')
        + m.lift(RES, 'FLASHMEM void RescueFlipTapped()') + m.lift(RES, 'FLASHMEM void SaveRescue()'))
EXTRA = r'''
static uint8_t fcRescue[28]; static int mspFn[64], mspN = 0; static uint8_t mspData[64][40]; static uint64_t mspAt[64]; static int failFn = -1, failAfterMs = 150, failOnce = 0;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 64) { mspFn[mspN] = fn; memset(mspData[mspN], 0, 40); if (data && len > 0) memcpy(mspData[mspN], data, (size_t) len); mspAt[mspN] = nowUs; ++mspN; } return mspN; }
char PipeRepBody[64] = ""; int PipeRepCode = 200; static int lastReq = 0;
static bool PipeReplyReady(int req)
{
    if (!(req >= 1 && req <= mspN)) return false;
    const bool fails = mspFn[req - 1] == failFn;
    if (nowUs - mspAt[req - 1] < (uint64_t) (fails ? failAfterMs : 150) * 1000) return false;
    PipeRepCode = fails ? 503 : 200; if (fails) snprintf(PipeRepBody, sizeof PipeRepBody, "the receiver did not answer");
    if (!fails && mspFn[req - 1] == 147 && lastReq != req) memcpy(fcRescue, mspData[req - 1], 28);   // (a write that worked: the flight controller has it)
    lastReq = req;
    return true;
}
static bool PipeReplyLate() { return false; }
static int PipeReplyBytes(uint8_t *b, int n) { memset(b, 0, (size_t) n); memcpy(b, fcRescue, 28); return 28; }
static void RfSavedThenLeave(int) {}
static bool ModelSeemsArmed(char *, size_t) { return false; }
static bool RfPipeBlocked(char *, size_t) { return false; }
''' + REAL + r'''
static void rsTap(const char *button)   // the screen's own doing at the touch: a SWITCH part flips itself, then its code is printed
{
    Page &pg = screen.pages["RescueView"];
    if (screen.page != "RescueView") return;
    if (!strcmp(button, "tn0")) pg.boxes["tn0"].val = pg.boxes["tn0"].val ? 0 : 1;
    if (!strcmp(button, "tn1")) pg.boxes["tn1"].val = pg.boxes["tn1"].val ? 0 : 1;
}
static void my24(int n) { if (n == 170) SaveRescue(); else if (n == 171) RescueModeTapped(); else if (n == 172) RescueFlipTapped(); else if (n == 173) RescueWasEdited(); else more24(n); }
static void addRescue()
{
    Page b; b.id = 58;
    for (const char *t : { "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "tn8", "tn9", "tn10", "tn11", "tn12", "busy", "t11", "t9" }) b.boxes[t] = { true, 0, "" };
    b.boxes["tn0"] = { false, 0, "" }; b.boxes["tn1"] = { false, 0, "" };
    b.buttons["Save"] = { 0x00, 170, 0x00, 0x00 }; b.buttons["tn0"] = { 0x00, 171, 0x00, 0x00 }; b.buttons["tn1"] = { 0x00, 172, 0x00, 0x00 }; b.buttons["edited"] = { 0x00, 173, 0x00, 0x00 };
    screen.pages["RescueView"] = b; screen.pages0 = screen.pages;
    memset(fcRescue, 0, sizeof fcRescue); fcRescue[0] = 0; fcRescue[1] = 0; fcRescue[2] = 50; fcRescue[3] = 40; fcRescue[4] = 5; fcRescue[5] = 10; fcRescue[6] = 100; fcRescue[7] = 5;
    WrU16(fcRescue, 8, 650); WrU16(fcRescue, 10, 450); WrU16(fcRescue, 12, 350); WrU16(fcRescue, 24, 250); WrU16(fcRescue, 26, 2000);
    RescueHave = false; Rescue_Was_Edited = false; RescueStep = RSC_IDLE; RescueMode = RescueFlip = 0; RescueModeWhenOn = 1; mspN = 0; failFn = -1; lastReq = 0;
    BoundFlag = ModelMatched = false; extra24 = my24; tapScript = rsTap;
}
static void loopPolls(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { LoopPass(); RescuePoll(); nowUs += 500; } }
'''
SCENES = r'''
    for (int late : { 0, 1 })
    {
        more(); addRescue(); screen.latencyUs = late ? 150000 : 1500;                  // a screen 150 ms behind - or a quick one
        SendCommand((char *) "page RescueView"); CurrentView = RESCUEVIEW; RescueRead(); loopPolls(1500);
        Page &pg = screen.pages["RescueView"];
        CHECK(RescueHave && RescueStep == RSC_IDLE && pg.boxes["tn0"].val == 0 && pg.boxes["tn2"].txt == "65");
        // he types the pull-up collective: 60, and presses Save. The store behind the write fails 400 ms on.
        pg.boxes["tn2"].txt = "60"; tapAt(5, "edited"); loopPolls(100);
        failFn = 250; failAfterMs = 400; tapAt(5, "Save"); loopPolls(300 + (late ? 400 : 0));
        CHECK(RescueStep != RSC_IDLE);
        // WHILE IT RUNS he turns "Enable rescue" ON - his finger lands as the failure's box is on its way to the screen: 20 ms after its page command
        // left this board (the screen still shows the Rescue page: it flips the switch, and prints the code)
        screen.tapAfterPageUs = late ? 20000 : 600; screen.tapAfterPageButton = "tn0";
        tapAt(1500 + (late ? 600 : 0), "yes");                                        // (the failure's box is answered)
        const int stale0 = stale;
        loopPolls(4000);
        say("R%d. the screen %u ms behind: a save that fails, 'Enable rescue' tapped ON as the failure's box came - the screen's switch shows %ld, in hand RescueMode %d; stale presses not obeyed %d; page %s\n",
            late, (unsigned) (screen.latencyUs / 1000), pg.boxes["tn0"].val, RescueMode, stale - stale0, screen.page.c_str());
        CHECK(RescueStep == RSC_IDLE && screen.page == "RescueView" && Rescue_Was_Edited);
        CHECK((pg.boxes["tn0"].val != 0) == (RescueMode != 0));                        // WHAT SHOULD HOLD: the page shows what is in hand
        // Save again: what is written is what is IN HAND - is it what the page shows as Save is pressed?
        const long shownAtPress = pg.boxes["tn0"].val;
        failFn = -1; const int at = mspN; tapAt(5, "Save"); loopPolls(3000);
        int wrote = -1; for (int i = at; i < mspN; ++i) if (mspFn[i] == 147) wrote = mspData[i][0];
        say("     Save again, pressed with the page showing 'Enable rescue' %s - written to the flight controller: rescue mode %d (%s); the flight controller now has %d; the page then shows %s\n", shownAtPress ? "ON" : "off", wrote, wrote ? "on" : "OFF", (int) fcRescue[0], pg.boxes["tn0"].val ? "ON" : "off");
        CHECK(wrote >= 0 && (wrote != 0) == (shownAtPress != 0));                      // WHAT SHOULD HOLD: Save writes what the page showed as it was pressed
    }
    tapScript = nullptr;
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('rescue_switch', SCENES, extra=EXTRA, more_defines=('RESCUEVIEW', 'RESCUE2VIEW', 'BEEPCOMPLETE')))
