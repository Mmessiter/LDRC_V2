#!/usr/bin/env python3
"""THE TRAVEL PAGES' CONTROL DIRECTION SWITCHES AFTER A SAVE THAT FAILS - and a READ that fails (B211, the fifteenth review; reviewer B's experiment, adopted).
The fourteenth review's cure makes TravFail draw the page under "keep what was typed" (RfKeepTyped). TravShowPage1 then still puts the directions IN
HAND back to what the save had gathered (TravRevAil = TravInWant[1][0] < 0 ...) - and no longer writes the screen's three switches (tn6, tn7, tn8;
page 3: tn0, the tail's). A direction switch tapped WHILE THE SAVE RUNS (the tap is served: TravelAilTapped has no "not while a save runs") is then
shown on the page and gone in hand. Save again writes the direction in hand - not the one the page shows.
The REAL TravFail, TravelPoll, SaveTravel, TravelAilTapped, the gathers and shows, MsgBox, GetConfirmation, GetYesOrNo over the pretend screen and a
pretend pipe. RB_TRAVEL_H: another RF_Travel.h to lift from (the one the fourteenth review saw)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES = m.release(m.src('include/RF_Rescue.h'))
TRV = m.release(open(os.environ['RB_TRAVEL_H'], encoding='utf-8', errors='replace').read() if os.environ.get('RB_TRAVEL_H') else m.src('include/RF_Travel.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
def block(text, a, b): return text[text.index(a):text.index(b)]
REAL = (lib.LEAVE + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)') + m.lift(RES, 'FLASHMEM static long FieldNumber(')
        + 'void EndTravelView(); void StartTravel3View();\n'
        + block(TRV, 'static const int CFG_BYTES = 21;', 'FLASHMEM void StartTravelView()')
        + line(TRV, 'FLASHMEM void TravelWasEdited()') + line(TRV, 'FLASHMEM void TravelAilTapped()') + line(TRV, 'FLASHMEM void TravelEleTapped()')
        + line(TRV, 'FLASHMEM void TravelCollTapped()') + m.lift(TRV, 'FLASHMEM void SaveTravel()')
        + 'void EndTravelView() {} void StartTravel3View() {}\n')
EXTRA = r'''
static uint8_t fcCfg[21]; static int16_t fcIn[5][3];
static int mspFn[96], mspN = 0; static uint8_t mspData[96][40]; static uint64_t mspAt[96]; static int failFn = -1, failAfterMs = 150, lastReq = 0, curReq = 0;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 96) { mspFn[mspN] = fn; memset(mspData[mspN], 0, 40); if (data && len > 0) memcpy(mspData[mspN], data, (size_t) len); mspAt[mspN] = nowUs; ++mspN; } return mspN; }
char PipeRepBody[64] = ""; int PipeRepCode = 200;
static int16_t s16(const uint8_t *b, int o) { const int v = b[o] | (b[o + 1] << 8); return (int16_t) (v > 32767 ? v - 65536 : v); }
static bool PipeReplyReady(int req)
{
    if (!(req >= 1 && req <= mspN)) return false;
    const int fn = mspFn[req - 1]; const bool fails = fn == failFn;
    if (nowUs - mspAt[req - 1] < (uint64_t) (fails ? failAfterMs : 120) * 1000) return false;
    PipeRepCode = fails ? 503 : 200; if (fails) snprintf(PipeRepBody, sizeof PipeRepBody, "the receiver did not answer");
    if (!fails && lastReq != req)
    {   // (a write that worked: the flight controller has it)
        if (fn == 43) memcpy(fcCfg, mspData[req - 1], 21);
        if (fn == 171) { const int i = mspData[req - 1][0]; if (i >= 1 && i <= 4) { fcIn[i][0] = s16(mspData[req - 1], 1); fcIn[i][1] = s16(mspData[req - 1], 3); fcIn[i][2] = s16(mspData[req - 1], 5); } }
    }
    lastReq = req; curReq = req;
    return true;
}
static bool PipeReplyLate() { return false; }
static int PipeReplyBytes(uint8_t *b, int n)
{
    memset(b, 0, (size_t) n);
    const int fn = curReq ? mspFn[curReq - 1] : 0;
    if (fn == 42) { memcpy(b, fcCfg, 21); return 21; }
    if (fn == 174) { const int i = mspData[curReq - 1][0]; for (int k = 0; k < 3; ++k) { const uint16_t u = (uint16_t) fcIn[i][k]; b[k * 2] = (uint8_t) (u & 0xFF); b[k * 2 + 1] = (uint8_t) (u >> 8); } return 6; }
    return 0;
}
static bool BakOffline() { return false; }
static void RfSavedThenLeave(int) {}
static bool ModelSeemsArmed(char *, size_t) { return false; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
''' + REAL + r'''
static void trTap(const char *button)   // the screen's own doing at the touch: a SWITCH part flips itself, then its code is printed
{
    if (screen.page != "TravelView") return;
    Page &pg = screen.pages["TravelView"];
    for (const char *s : { "tn6", "tn7", "tn8" }) if (!strcmp(button, s)) pg.boxes[s].val = pg.boxes[s].val ? 0 : 1;
}
static void my24(int n) { if (n == 170) SaveTravel(); else if (n == 171) TravelAilTapped(); else if (n == 172) TravelEleTapped(); else if (n == 174) TravelCollTapped(); else if (n == 173) TravelWasEdited(); else more24(n); }
static void addTravel()
{
    Page b; b.id = 62;
    for (const char *t : { "i0", "i1", "tn9", "tn10", "tn11", "busy", "t11", "t9" }) b.boxes[t] = { true, 0, "" };
    for (const char *v : { "tn6", "tn7", "tn8" }) b.boxes[v] = { false, 0, "" };
    b.buttons["Save"] = { 0x00, 170, 0x00, 0x00 }; b.buttons["tn6"] = { 0x00, 171, 0x00, 0x00 }; b.buttons["tn7"] = { 0x00, 172, 0x00, 0x00 }; b.buttons["tn8"] = { 0x00, 174, 0x00, 0x00 }; b.buttons["edited"] = { 0x00, 173, 0x00, 0x00 };
    screen.pages["TravelView"] = b; { Page rf; rf.id = 44; screen.pages["RFView"] = rf; } screen.pages0 = screen.pages;
    memset(fcCfg, 0, sizeof fcCfg); fcCfg[5] = 2;                                   // CCPM 120
    for (int i = 1; i <= 4; ++i) { fcIn[i][0] = 800; fcIn[i][1] = -1000; fcIn[i][2] = 1000; }   // every direction: normal (rates above 0)
    TravHave = false; Trav_Was_Edited = false; TravStep = TRV_IDLE; mspN = 0; failFn = -1; lastReq = curReq = 0; BenchHeld = false;
    BoundFlag = ModelMatched = false; extra24 = my24; tapScript = trTap;
}
static void loopPolls(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { LoopPass(); TravelPoll(); nowUs += 500; } }
'''
SCENES = r'''
    more(); addTravel();
    SendCommand((char *) "page TravelView"); CurrentView = TRAVELVIEW; TravRead(); loopPolls(2000);
    Page &pg = screen.pages["TravelView"];
    CHECK(TravHave && TravStep == TRV_IDLE && pg.boxes["tn6"].val == 0 && !TravRevAil && pg.boxes["tn9"].txt == "0.0");
    // he types a swash trim, 1.5, and presses Save (and Yes to "Save the travel extents?"). The store behind the writes fails.
    pg.boxes["tn9"].txt = "1.5"; tapAt(5, "edited"); loopPolls(100);
    failFn = 250; failAfterMs = 700; tapAt(5, "Save"); tapAt(500, "yes"); loopPolls(1000);
    CHECK(TravStep != TRV_IDLE);                                                      // (the save runs)
    // WHILE IT RUNS he turns the aileron's control direction over (the switch tn6): the tap is served - on the screen and in hand
    tapAt(5, "tn6"); loopPolls(150);
    say("T1. the Travel page, a save running: the aileron direction switch tapped - the screen shows %ld, in hand TravRevAil %d\n", pg.boxes["tn6"].val, TravRevAil);
    CHECK(pg.boxes["tn6"].val == 1 && TravRevAil == 1 && TravStep != TRV_IDLE);
    // ... the save fails, its box is answered
    tapAt(1500, "yes"); loopPolls(4000);
    say("    the save failed (its box answered): the screen's switch shows %ld, in hand TravRevAil %d; page %s, still edited %d\n", pg.boxes["tn6"].val, TravRevAil, screen.page.c_str(), (int) Trav_Was_Edited);
    CHECK(TravStep == TRV_IDLE && screen.page == "TravelView" && Trav_Was_Edited);
    CHECK((pg.boxes["tn6"].val != 0) == (TravRevAil != 0));                            // WHAT SHOULD HOLD: the page shows what is in hand
    // Save again (and Yes): the aileron's direction as it is written to the flight controller - and as the page showed it when Save was pressed
    const long shownAtPress = pg.boxes["tn6"].val;
    failFn = -1; const int at = mspN; tapAt(5, "Save"); tapAt(500, "yes"); loopPolls(6000);
    int rate = 0; bool wrote = false; for (int i = at; i < mspN; ++i) if (mspFn[i] == 171 && mspData[i][0] == 1) { rate = s16(mspData[i], 1); wrote = true; }
    say("    Save again, pressed with the page showing the aileron direction %s: written to the flight controller: aileron rate %d (%s); the page then shows %s\n",
        shownAtPress ? "REVERSED" : "normal", rate, rate < 0 ? "reversed" : "NORMAL", pg.boxes["tn6"].val ? "reversed" : "normal");
    CHECK(wrote && (rate < 0) == (shownAtPress != 0));                                // WHAT SHOULD HOLD: Save writes the direction the page showed as it was pressed
    CHECK(shownAtPress == 1 && rate == -800 && TravRevAil == 1 && pg.boxes["tn6"].val == 1 && fcIn[1][0] == -800 && pg.boxes["tn9"].txt == "1.5");   // (the tap made while the save ran STANDS - and what was typed)
    // T2. A TAP THAT IS NOT OBEYED (made as the failure's box came up: its page had gone) turns the screen's switch and nothing in hand: behind the box the
    //     switches are written AS THEY ARE IN HAND - the page shows what Save will write
    pg.boxes["tn10"].txt = "2.5"; tapAt(5, "edited"); loopPolls(100);
    failFn = 250; failAfterMs = 700; tapAt(5, "Save"); tapAt(500, "yes"); loopPolls(1000); CHECK(TravStep != TRV_IDLE);
    pg.boxes["tn7"].val = 1; pg.boxes["tn8"].val = 1;                                 // (elevator and collective turned on the screen by taps this board never obeys)
    tapAt(1500, "yes"); loopPolls(4000);
    say("T2. two switches turned by taps that were not obeyed, the save failed: the screen shows elevator %ld, collective %ld - in hand %d, %d; aileron still %ld / %d\n", pg.boxes["tn7"].val, pg.boxes["tn8"].val, TravRevEle, TravRevColl, pg.boxes["tn6"].val, TravRevAil);
    CHECK(TravStep == TRV_IDLE && screen.page == "TravelView" && pg.boxes["tn7"].val == 0 && pg.boxes["tn8"].val == 0 && !TravRevEle && !TravRevColl && pg.boxes["tn6"].val == 1 && TravRevAil == 1 && pg.boxes["tn10"].txt == "2.5");
    failFn = -1; tapAt(5, "Save"); tapAt(500, "yes"); loopPolls(6000); CHECK(fcIn[1][0] == -800 && fcIn[2][0] > 0 && fcIn[4][0] > 0 && !Trav_Was_Edited);
    // T3. A READ ENDS ON ANOTHER PAGE THAN THE FIRST (pages 2 and 4 show no switch): the four directions in hand are the flight controller's all the same -
    //     their gathers sign the calibrations by what is in hand, which was the LAST VISIT'S (another model's) when a read ended there
    CurrentView = TRAVEL2VIEW; TravRevAil = 0; TravRevEle = 1; TravRevColl = 1; TravRevYaw = 1;      // (what an earlier visit left in hand; the flight controller: aileron reversed, the rest normal)
    TravRead(); CHECK(!TravHave); loopPolls(2000);
    say("T3. a read ended on page 2: in hand aileron %d, elevator %d, collective %d, yaw %d (the flight controller: 1, 0, 0, 0)\n", TravRevAil, TravRevEle, TravRevColl, TravRevYaw);
    CHECK(TravHave && TravRevAil == 1 && TravRevEle == 0 && TravRevColl == 0 && TravRevYaw == 0);
    CurrentView = TRAVELVIEW;
    // T3b. PAGE 3's switch (the tail's direction), by the page's own draw: under the keep what is in hand STAYS and the switch is written from it; without
    //      the keep what is in hand is the block's (the break-it round's second look: a text check alone held page 3)
    {
        Page p3; p3.id = 63; for (const char *t : { "i0", "ltn1", "ltn3", "ltn4", "tn1", "tn2", "tn3", "tn4", "tn5", "busy", "t11", "t9" }) p3.boxes[t] = { true, 0, "" };
        p3.boxes["tn0"] = { false, 0, "" }; screen.pages["Travel3View"] = p3; screen.pages0 = screen.pages;
        SendCommand((char *) "page Travel3View"); CurrentView = TRAVEL3VIEW; loopPolls(400);
        Page &g3 = screen.pages["Travel3View"];
        TravRevYaw = 1; CHECK(TravInWant[3][0] >= 0);                                 // (tapped while a save ran: reversed in hand - the block, as gathered, says normal)
        RfKeepTyped = true; TravShowPage3(); RfKeepTyped = false; loopPolls(100);
        CHECK(TravRevYaw == 1 && g3.boxes["tn0"].val == 1);                           // under the keep: in hand stays, and the switch shows it
        g3.boxes["tn0"].val = 0; RfKeepTyped = true; TravShowPage3(); RfKeepTyped = false; loopPolls(100);
        CHECK(TravRevYaw == 1 && g3.boxes["tn0"].val == 1);                           // (a switch the screen turned by a tap not obeyed: put back as it is in hand)
        TravShowPage3(); loopPolls(100); CHECK(TravRevYaw == 0 && g3.boxes["tn0"].val == 0);   // without it: the block's
        SendCommand((char *) "page TravelView"); CurrentView = TRAVELVIEW; loopPolls(400);
    }
    // T4. A READ THAT FAILS LEAVES NOTHING IN HAND, AND THE PAGE IS LEFT - its box, then the menu (released code: the page stayed, Save open on the read before)
    menuOpened = 0; failFn = 42; failAfterMs = 150; tapAt(900, "yes"); SendCommand((char *) "page TravelView"); CurrentView = TRAVELVIEW; TravRead(); CHECK(!TravHave); loopPolls(3000);
    say("T4. a read failed: the screen shows %s, view %d, the menu opened %d time(s), TravHave %d\n", screen.page.c_str(), (int) CurrentView, menuOpened, (int) TravHave);
    CHECK(!TravHave && TravStep == TRV_IDLE && screen.page == "RFView" && CurrentView == ROTORFLIGHTVIEW && menuOpened == 1);
    failFn = -1; { const int n0 = mspN; SaveTravel(); loopPolls(500); CHECK(mspN == n0 && fcIn[1][0] == -800); }
    // ... and where the menu will not open, the page again - saying that it was not read
    menuShut = true; menuOpened = 0; failFn = 42; tapAt(900, "yes"); SendCommand((char *) "page TravelView"); CurrentView = TRAVELVIEW; TravRead(); loopPolls(3000);
    CHECK(!TravHave && screen.page == "TravelView" && CurrentView == TRAVELVIEW && menuOpened == 0 && pg.boxes["busy"].txt == "NOT READ. Safety on, motor off - then OK.");
    failFn = -1; { const int n0 = mspN; SaveTravel(); loopPolls(500); CHECK(mspN == n0); } menuShut = false;
    tapScript = nullptr;
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('travel_dir', SCENES, extra=EXTRA, more_defines=('TRAVELVIEW', 'TRAVEL2VIEW', 'TRAVEL3VIEW', 'TRAVEL4VIEW', 'BEEPCOMPLETE')))
