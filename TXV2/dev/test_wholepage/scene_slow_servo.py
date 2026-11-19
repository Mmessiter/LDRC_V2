#!/usr/bin/env python3
"""THE SLOW-SERVO PAGE'S SPEEDS (the twelfth review, reviewer B's finding 11; 15 Nov 2026): main.cpp ReadSpeedsScreen took the boxes named in the page's
list one by one, "no answer keeps the one in hand", and asked "did this BUTTON's work lose a box?" - while one of its two callers is no button: the
bank switch, from the main loop, where that count is some earlier button's. Its cure for a box unanswered at the bank switch ("the list stays") did
not cure: the page was drawn for the new bank over the edits all the same.
 V1 OK, every box answering: the speeds named in the list are taken, the model saved, the page left, the list cleared.
 V2 OK, one box unanswered: NOTHING is taken, nothing saved, the page not left - and the list stays for his next OK.
 V3 the bank switch on the page: the bank that was left takes its edits, the page shows the new bank's speeds, the list begins again.
 V4 ... one box unanswered: nothing taken - and SAID (it told nobody); the page shows the new bank, the list begins again.
 V5 ... an EARLIER button's work had lost a box: this read counts for itself (it took the earlier loss for its own, and left the list standing).
 V6 SIX BANKS (the author's, found reading the routine): it refused every bank above the fourth ("bk > 3", from the days of four banks) - on a model
    with six, the speeds edited in banks 5 and 6 were never taken: OK saved them as they had been, without a word. And the motor switch's "force a
    bank change" number (254) still takes nothing and asks nothing.
The REAL ReadSpeedsScreen, EndSpeedsScreen, UpdateSpeedScreen (main.cpp), CheckServoSpeeds (SDcard.h) and Switches.h's own lines for the page run
over the pretend screen."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
MAINC = m.MAIN_CPP
SWT = m.release(m.src('include/Switches.h')); SDC = m.release(m.src('include/SDcard.h'))
def block(text, head):
    i = text.index(head); d = 0; j = text.index('{', i)
    for k in range(j, len(text)):
        if text[k] == '{': d += 1
        elif text[k] == '}':
            d -= 1
            if d == 0: return text[i:k + 1]
    raise SystemExit('no block ' + head)
BANKLINES = block(SWT, 'if (CurrentView == SLOWSERVOVIEW)')
mc = re.sub(r'//[^\n]*', '', MAINC)
if not re.search(r'void EndSpeedsScreen\(\)\s*\{\s*if \(!ReadSpeedsScreen\(Bank - 1\)\)\s*return;\s*CheckServoSpeeds\(\);\s*SaveOneModel\(ModelNumber\);\s*StartModelSetup\(\);\s*\}', mc):
    print('FAIL: main.cpp EndSpeedsScreen: the speeds whole (ReadSpeedsScreen), or nothing saved and the page not left'); sys.exit(1)
EXTRA = r'''
static uint8_t ServoSpeed[BANKS_USED + 1][CHANNELSUSED + 1];
static char BankNames[BANK_NAMES_N][16];
static int setups = 0; static void StartModelSetup() { ++setups; }
bool ReadSpeedsScreen(uint8_t bk, bool FromPage = false);
''' + m.lift(SDC, 'void CheckServoSpeeds()') + m.lift(MAINC, 'void UpdateSpeedScreen()') + m.lift(MAINC, 'bool ReadSpeedsScreen(uint8_t bk, bool FromPage)') + m.lift(MAINC, 'void EndSpeedsScreen()') + r'''
static void bankSwitchOnThePage()   // include/Switches.h BankHasChanged's own lines for the Slow-servo page
{
    ''' + BANKLINES + r'''
}
static void addSlow()
{
    Page s; s.id = 64; for (int i = 0; i < 16; ++i) { char n[8]; snprintf(n, sizeof n, "n%d", i); s.boxes[n] = { false, 100, "" }; }
    s.boxes["Progress"] = { false, 0, "" }; s.boxes["change"] = { true, 0, "XX:" }; s.boxes["t14"] = { true, 0, "" };
    screen.pages["SlowServoView"] = s; screen.pages0 = screen.pages;
    for (auto &b : ServoSpeed) for (uint8_t &x : b) x = 100;
    for (int i = 0; i < BANK_NAMES_N; ++i) snprintf(BankNames[i], sizeof BankNames[i], "Bank%d", i);
    setups = 0; saves.clear();
}
static void openSlow(uint8_t bank) { more(); addSlow(); Bank = bank; SendCommand((char *) "page SlowServoView"); CurrentView = SLOWSERVOVIEW; UpdateSpeedScreen(); loopFor(600); BoxesLostAtWork = BoxesLost; }
static void edit(int box, int v) { char n[8]; snprintf(n, sizeof n, "n%d", box); Page &pg = screen.pages["SlowServoView"]; pg.boxes[n].val = v; pg.boxes["change"].txt += n; pg.boxes["change"].txt += " "; }
static bool allFull(uint8_t bank, std::initializer_list<int> but = {}) { for (int i = 0; i < 16; ++i) { bool skip = false; for (int k : but) skip |= k == i; if (!skip && ServoSpeed[bank - 1][i] != 100) return false; } return true; }
static void okPressed() { Page &pg = screen.pages["SlowServoView"]; snprintf(TextIn, 200, "SLOW%s", pg.boxes["change"].txt.c_str()); EndSpeedsScreen(); }   // (the OK's word carries the page's list behind its four letters)
'''
SCENES = r'''
    // V1. OK, every box answering
    openSlow(2); edit(3, 40); edit(7, 60);
    okPressed(); loopFor(600);
    say("V1. OK, every box answering: bank 2 channel 4 speed %u, channel 8 speed %u; saved %d, the page left %d, the page's list '%s'\n", (unsigned) ServoSpeed[1][3], (unsigned) ServoSpeed[1][7], (int) saves.size(), setups, screen.pages["SlowServoView"].boxes["change"].txt.c_str());
    CHECK(ServoSpeed[1][3] == 40 && ServoSpeed[1][7] == 60 && allFull(2, { 3, 7 }) && allFull(1) && allFull(3));
    CHECK(saves.size() == 1 && setups == 1 && screen.pages["SlowServoView"].boxes["change"].txt == "XX:" && boxesLostTold == 0);
    // V2. OK, one box unanswered - each of the two in turn: nothing taken, nothing saved, the page not left, the list stays; then his next OK takes both
    for (const char *lost : { "n3", "n7" })
    {
        openSlow(2); edit(3, 40); edit(7, 60);
        screen.mute.insert(lost); const uint32_t lost0 = BoxesLost; okPressed(); screen.mute.clear(); loopFor(3000);
        say("V2. OK, %s unanswered: bank 2 untouched %d; saved %d, the page left %d, boxes counted %u, the page's list '%s'\n", lost, (int) allFull(2), (int) saves.size(), setups, (unsigned) (BoxesLost - lost0), screen.pages["SlowServoView"].boxes["change"].txt.c_str());
        CHECK(allFull(2) && saves.empty() && setups == 0 && BoxesLost > lost0);                     // (it was: the one that answered taken, the model saved, the page left)
        CHECK(screen.pages["SlowServoView"].boxes["change"].txt == "XX:n3 n7 ");                     // the list stands
        BoxesLostAtWork = BoxesLost; okPressed(); loopFor(600);
        CHECK(ServoSpeed[1][3] == 40 && ServoSpeed[1][7] == 60 && saves.size() == 1 && setups == 1);
    }
    // V3. the bank switch on the page (bank 2 left for bank 3; bank 3's channel 4 is at 30)
    openSlow(2); edit(3, 40); edit(7, 60); ServoSpeed[2][3] = 30;
    { PreviousBank = 2; Bank = 3; const int told0 = boxesLostTold; bankSwitchOnThePage(); loopFor(600);
      Page &pg = screen.pages["SlowServoView"];
      say("V3. the bank switch on the page: bank 2 channel 4 %u, channel 8 %u; the page shows channel 4 at %d (bank 3 has 30), its list '%s'; told %d\n", (unsigned) ServoSpeed[1][3], (unsigned) ServoSpeed[1][7], (int) pg.boxes["n3"].val, pg.boxes["change"].txt.c_str(), boxesLostTold - told0);
      CHECK(ServoSpeed[1][3] == 40 && ServoSpeed[1][7] == 60 && allFull(2, { 3, 7 }) && ServoSpeed[2][3] == 30 && allFull(3, { 3 }));
      CHECK(pg.boxes["n3"].val == 30 && pg.boxes["n7"].val == 100 && pg.boxes["change"].txt == "XX:" && boxesLostTold == told0 && saves.empty()); }
    // V4. ... one box unanswered: nothing taken for the bank that was left, SAID, the page shows the new bank, the list begins again
    openSlow(2); edit(3, 40); edit(7, 60); ServoSpeed[2][3] = 30;
    { PreviousBank = 2; Bank = 3; const int told0 = boxesLostTold; screen.mute.insert("n7"); bankSwitchOnThePage(); screen.mute.clear(); loopFor(3000);
      Page &pg = screen.pages["SlowServoView"];
      say("V4. ... n7 unanswered: bank 2 untouched %d; told %d; the page's list '%s'\n", (int) allFull(2), boxesLostTold - told0, pg.boxes["change"].txt.c_str());
      CHECK(allFull(2) && ServoSpeed[2][3] == 30);                                                   // (it was: channel 4's 40 taken, channel 8's edit dropped)
      CHECK(boxesLostTold == told0 + 1);                                                             // said (it told nobody)
      CHECK(pg.boxes["change"].txt == "XX:"); }
    // V5. ... an EARLIER button's work had lost a box (its count still stands - no button has been pressed since): this read, every box answering,
    //     counts for itself - the edits taken, the list cleared, nothing said
    openSlow(2); edit(3, 40); ServoSpeed[2][3] = 30;
    { ++BoxesLost;                                                                                   // (the earlier loss: BoxesLost != BoxesLostAtWork from here)
      PreviousBank = 2; Bank = 3; const int told0 = boxesLostTold; const bool whole = ReadSpeedsScreen(PreviousBank - 1, true); loopFor(600);
      say("V5. an earlier button had lost a box: this read whole %d, bank 2 channel 4 %u, the page's list '%s'\n", (int) whole, (unsigned) ServoSpeed[1][3], screen.pages["SlowServoView"].boxes["change"].txt.c_str());
      CHECK(whole && ServoSpeed[1][3] == 40 && screen.pages["SlowServoView"].boxes["change"].txt == "XX:" && boxesLostTold == told0); }
    // V6. six banks: OK in bank 5, and in bank 6 - the speeds edited there are taken (they never were)
    for (uint8_t bank : { 5, 6 })
    {
        openSlow(bank); edit(3, 40); edit(15, 25);
        okPressed(); loopFor(600);
        say("V6. OK in bank %u of six: channel 4 speed %u, channel 16 speed %u; saved %d\n", (unsigned) bank, (unsigned) ServoSpeed[bank - 1][3], (unsigned) ServoSpeed[bank - 1][15], (int) saves.size());
        CHECK(ServoSpeed[bank - 1][3] == 40 && ServoSpeed[bank - 1][15] == 25 && allFull(bank, { 3, 15 }) && saves.size() == 1 && setups == 1);
        for (uint8_t other = 1; other <= 6; ++other) if (other != bank) CHECK(allFull(other));
    }
    //     ... and the motor switch's "force a bank change" number (254: bank 253 here), or any bank the table has not got: nothing asked, nothing taken
    openSlow(2); edit(3, 40);
    { const int g0 = screen.gets; uint8_t before[sizeof ServoSpeed]; memcpy(before, ServoSpeed, sizeof ServoSpeed);
      CHECK(ReadSpeedsScreen(253, true) && ReadSpeedsScreen(6, true) && ReadSpeedsScreen(BANKS_USED, false) && screen.gets == g0 && !memcmp(before, ServoSpeed, sizeof ServoSpeed)); }
'''
sys.exit(lib.build_run('slow_servo', SCENES, extra=EXTRA, more_defines=('SLOWSERVOVIEW', 'CHANNELSUSED')))
