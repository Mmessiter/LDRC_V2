#!/usr/bin/env python3
"""A READ THAT FAILS LEAVES NOTHING IN HAND - AND THE PAGE IS LEFT (B211, the fifteenth review; reviewer B's experiment, adopted. Released code had it.)
RescueHave (as BasHave, FltHave, TravHave, ServoHave) was set by the first read that worked and never cleared: a later read that FAILED - another
bank's, another model's - left the page up with the numbers of the read before and Save open: one edit, Save, and bank 1's rescue went into bank 2,
"Saved, and read back the same.". Now: nothing is in hand while a read runs (and, here, from the moment the bank switch moves); a page whose read
failed is left for the menu behind its box (RF_SaveNow.h RfLeaveNotRead); where the menu will not open, the page is put up again, empty.
The REAL StartRescueView, RescueFail, RescuePoll, RescueBankChanged, SaveRescue, RfLeaveNotRead, the gathers and shows, MsgBox, GetYesOrNo over the
pretend screen and a pretend pipe (a flight controller with two banks). RB_RESCUE_H: another RF_Rescue.h to lift from."""
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
        + m.lift(RES, 'FLASHMEM void RescuePoll()') + m.lift(RES, 'FLASHMEM static void RescueRead()') + m.lift(RES, 'FLASHMEM void StartRescueView()')
        + m.lift(RES, 'FLASHMEM void RescueBankChanged()') + m.lift(RES, 'FLASHMEM void RescueWasEdited()') + line(RES, 'static int RescueModeWhenOn = 1;')
        + m.lift(RES, 'FLASHMEM void RescueModeTapped()') + m.lift(RES, 'FLASHMEM void SaveRescue()'))
EXTRA = r'''
static uint8_t fcR[2][28]; static int fcBank = 0;
static int mspFn[96], mspN = 0; static uint8_t mspData[96][40]; static uint64_t mspAt[96]; static int failFn = -1, lastReq = 0;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 96) { mspFn[mspN] = fn; memset(mspData[mspN], 0, 40); if (data && len > 0) memcpy(mspData[mspN], data, (size_t) len); mspAt[mspN] = nowUs; ++mspN; } return mspN; }
char PipeRepBody[64] = ""; int PipeRepCode = 200;
static bool PipeReplyReady(int req)
{
    if (!(req >= 1 && req <= mspN)) return false;
    const int fn = mspFn[req - 1]; const bool fails = fn == failFn;
    if (nowUs - mspAt[req - 1] < 150000) return false;
    PipeRepCode = fails ? 503 : 200; if (fails) snprintf(PipeRepBody, sizeof PipeRepBody, "the receiver did not answer");
    if (!fails && lastReq != req)
    {
        if (fn == 210) fcBank = mspData[req - 1][0] & 1;                       // the bank chosen
        if (fn == 147) memcpy(fcR[fcBank], mspData[req - 1], 28);              // a write that worked: into the bank the flight controller is on
    }
    lastReq = req;
    return true;
}
static bool PipeReplyLate() { return false; }
static int PipeReplyBytes(uint8_t *b, int n) { memset(b, 0, (size_t) n); memcpy(b, fcR[fcBank], 28); return 28; }
static void RfSavedThenLeave(int) {}
static bool ModelSeemsArmed(char *, size_t) { return false; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
''' + REAL + r'''
static void my24(int n) { if (n == 170) SaveRescue(); else if (n == 173) RescueWasEdited(); else more24(n); }
static void addRescue()
{
    Page b; b.id = 58;
    for (const char *t : { "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "tn8", "tn9", "tn10", "tn11", "tn12", "busy", "t11", "t9" }) b.boxes[t] = { true, 0, "" };
    b.boxes["tn0"] = { false, 0, "" }; b.boxes["tn1"] = { false, 0, "" };
    b.buttons["Save"] = { 0x00, 170, 0x00, 0x00 }; b.buttons["edited"] = { 0x00, 173, 0x00, 0x00 };
    screen.pages["RescueView"] = b; { Page rf; rf.id = 44; screen.pages["RFView"] = rf; } screen.pages0 = screen.pages;
    for (int k = 0; k < 2; ++k)
    {   // bank 1: rescue ON, a pull-up of 65 %, climb 45 %, hover 35 %. Bank 2 (a 3D bank, say): rescue OFF, 30 / 25 / 20 %
        memset(fcR[k], 0, 28); fcR[k][0] = k ? 0 : 1; fcR[k][1] = 0; fcR[k][2] = 50; fcR[k][3] = 40; fcR[k][4] = 5; fcR[k][5] = 10; fcR[k][6] = 100; fcR[k][7] = 5;
        WrU16(fcR[k], 8, k ? 300 : 650); WrU16(fcR[k], 10, k ? 250 : 450); WrU16(fcR[k], 12, k ? 200 : 350); WrU16(fcR[k], 24, 250); WrU16(fcR[k], 26, 2000);
    }
    RescueHave = false; Rescue_Was_Edited = false; RescueStep = RSC_IDLE; RescueMode = RescueFlip = 0; mspN = 0; failFn = -1; lastReq = 0; fcBank = 0;
    BoundFlag = ModelMatched = false; extra24 = my24; Bank = 1;
}
static void loopPolls(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { LoopPass(); RescuePoll(); nowUs += 500; } }
'''
SCENES = r'''
    more(); addRescue();
    // S0. bank 1: the Rescue page is opened and read - as on any day
    Bank = 1; StartRescueView(); CHECK(!RescueHave);                                // (nothing is in hand while a read runs)
    loopPolls(1500);
    Page &pg = screen.pages["RescueView"];
    CHECK(RescueHave && RescueStep == RSC_IDLE && pg.boxes["tn2"].txt == "65" && pg.boxes["tn0"].val == 1 && menuOpened == 0 && screen.page == "RescueView");
    // S1. he leaves it (OK: the menu), flips the bank switch to bank 2, and opens the Rescue page again. THIS read fails (the receiver does not answer)
    SendCommand((char *) "page RFView"); CurrentView = ROTORFLIGHTVIEW; loopPolls(300);
    const int odd0 = screen.oddCommands, loads0 = screen.loads;
    Bank = 2; failFn = 146; tapAt(900, "yes"); StartRescueView(); CHECK(!RescueHave);
    loopPolls(3000);
    CHECK(screen.oddCommands == odd0 && screen.loads == loads0 + 4);                          // the page, the box, the box's way back - THE MENU - and the menu's own page command: no other page, none the screen has not got
    say("S1. bank 2's read failed (its box answered): the screen shows %s, this board is on view %d (the menu opened %d time(s)); RescueHave %d\n", screen.page.c_str(), (int) CurrentView, menuOpened, (int) RescueHave);
    CHECK(RescueStep == RSC_IDLE && !RescueHave && screen.page == "RFView" && CurrentView == ROTORFLIGHTVIEW && menuOpened == 1);   // THE PAGE IS LEFT: its box, then the menu
    failFn = -1; { const int n0 = mspN; SaveRescue(); loopPolls(500); CHECK(mspN == n0); }                                         // (a Save from anywhere asks nothing: nothing is in hand)
    CHECK(fcR[1][0] == 0 && RdU16(fcR[1], 8) == 300 && RdU16(fcR[1], 10) == 250 && RdU16(fcR[1], 12) == 200);                    // bank 2 is as it was
    // S2. THE MENU WILL NOT OPEN (the motor switch is on - RotorFlightStart does nothing): the page is put up again, EMPTY: nothing of bank 1's on it,
    //     nothing in hand, and its Save writes nothing
    menuShut = true; menuOpened = 0; Bank = 2; failFn = 146; tapAt(900, "yes"); StartRescueView(); loopPolls(3000);
say("S2. the same with the menu shut: the screen shows %s, view %d; the page says '%s' and '%s'; RescueHave %d\n", screen.page.c_str(), (int) CurrentView, pg.boxes["t9"].txt.c_str(), pg.boxes["busy"].txt.c_str(), (int) RescueHave);
    CHECK(!RescueHave && RescueStep == RSC_IDLE && screen.page == "RescueView" && CurrentView == RESCUEVIEW && menuOpened == 0);
    CHECK(pg.boxes["busy"].txt == "NOT READ. Safety on, motor off - then OK." && pg.boxes["t9"].txt == "Bank 2");   // (a standing line: whatever the screen still shows there is not in hand)
    failFn = -1; pg.boxes["tn3"].txt = "0.7"; tapAt(5, "edited"); loopPolls(100); tapAt(5, "Save"); loopPolls(2000);
    { int wrote = 0; for (int i = 0; i < mspN; ++i) wrote += mspFn[i] == 147; CHECK(wrote == 0); }
    CHECK(fcR[1][0] == 0 && RdU16(fcR[1], 8) == 300 && RdU16(fcR[1], 10) == 250 && RdU16(fcR[1], 12) == 200);
    menuShut = false;
    // S3. THE BANK SWITCH MOVES UNDER THE OPEN PAGE: what is in hand is the OLD bank's from that moment - a switch and Save tapped before the new bank
    //     has been read (the read begins four tenths of a second on) write nothing. Then the new bank's numbers.
    Bank = 1; StartRescueView(); loopPolls(1500); CHECK(RescueHave && pg.boxes["tn2"].txt == "65" && pg.boxes["tn0"].val == 1);
    PreviousBank = 1; Bank = 2; RescueBankChanged();
    CHECK(!RescueHave && RescueRereadWanted);
    { const int n0 = mspN; RescueModeTapped(); SaveRescue(); loopPolls(100); CHECK(mspN == n0); }
    loopPolls(1800);
    say("S3. the bank switch moved under the page: now it shows the pull-up collective '%s', 'Enable rescue' %ld (bank 2 has 30 and off); RescueHave %d\n", pg.boxes["tn2"].txt.c_str(), pg.boxes["tn0"].val, (int) RescueHave);
    CHECK(RescueHave && pg.boxes["tn2"].txt == "30" && pg.boxes["tn0"].val == 0 && !Rescue_Was_Edited && RescueMode == 0);
    CHECK(fcR[1][0] == 0 && RdU16(fcR[1], 8) == 300 && fcR[0][0] == 1 && RdU16(fcR[0], 8) == 650);
    // S4. ... and when the new bank's read FAILS, the page is left too
    menuOpened = 0; PreviousBank = 2; Bank = 1; failFn = 146; tapAt(1500, "yes"); RescueBankChanged(); loopPolls(3500);
    CHECK(!RescueHave && RescueStep == RSC_IDLE && screen.page == "RFView" && CurrentView == ROTORFLIGHTVIEW && menuOpened == 1);
    failFn = -1;
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('stale_block', SCENES, extra=EXTRA, more_defines=('RESCUEVIEW', 'RESCUE2VIEW', 'BEEPCOMPLETE')))
