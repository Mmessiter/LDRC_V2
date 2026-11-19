#!/usr/bin/env python3
"""GATHERS THE CHECK COULD NOT SEE (the twelfth review, reviewer B's finding 6; 15 Nov 2026): routines of the older pages that asked several boxes
through a helper, or in a word's handler, and took those that answered.
 F1 "FailSAVE": the sixteen failsafe boxes - one unanswered, and the MIXTURE was sent to the receiver as the failsafe set. Whole, or NOTHING IS SENT.
 F2 the failsafe page's way out (SaveFailSafeChannels): whole - and the page's list of what was changed is not cleared, the page not left.
 F3 "RXBAT": eight boxes that are two choices (the receiver's cells; the transmitter's own battery) - all asked before either is taken.
 F4 the bank names (BankNamesFromPage: EndBankNames and "Listen"): whole.
 F5 "Listen" itself (the thirteenth review: no scene ran it): the names said from the main loop, one in 1.2 s, nothing waits; the page left - no more is
    said, and none when the page is come back to.
The REAL FailSafeSetFromPage, SaveFailSafeChannels, BankNameFromPage, BankNamesFromPage, ListenToBanks, BankListenPoll and main.cpp's own lines for the
two words run over the pretend screen."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
MAINC = m.MAIN_CPP
def block(head):
    i = MAINC.index(head); d = 0; j = MAINC.index('{', i)
    for k in range(j, len(MAINC)):
        if MAINC[k] == '{': d += 1
        elif MAINC[k] == '}':
            d -= 1
            if d == 0: return MAINC[i:k + 1]
    raise SystemExit('no block ' + head)
FS, RB = block('if (InStrng(FailSAVE, TextIn) > 0)'), block('if (InStrng(RXBAT, TextIn) > 0)')
mc = re.sub(r'//[^\n]*', '', MAINC); bad = []
if not re.search(r'if \(CurrentView == FAILSAFE_VIEW\)\s*\{\s*if \(!SaveFailSafeChannels\(\)\)\s*return;\s*\}', mc):
    bad.append('main.cpp StartModelSetup: the failsafe page is not left when its set could not be taken whole')
if not re.search(r'void EndBankNames\(\)\s*\{\s*if \(!BankNamesFromPage\(\)\)\s*return;\s*SaveOneModel\(ModelNumber\);\s*StartModelSetup\(\);\s*\}', mc):
    bad.append('main.cpp EndBankNames: the names whole (BankNamesFromPage), or nothing saved and the page not left')
if not re.search(r'void ListenToBanks\(\)\s*\{\s*if \(!BankNamesFromPage\(\)\)\s*return;', mc) or 'DelayWithDog' in m.lift(MAINC, 'void ListenToBanks()'):
    bad.append('main.cpp ListenToBanks: the names whole first - and no wait in it')
if len(re.findall(r'\bBankListenPoll\(\);', mc)) != 1:
    bad.append('main.cpp: the main loop calls BankListenPoll() once')
for b in bad: print('FAIL: ' + b)
if bad: sys.exit(1)
EXTRA = r'''
static bool FailSafeChannel[17]; static uint8_t RXCellCount = 3; static bool TXLiPo = false; static int allSaved = 0; static void SaveAllParameters() { ++allSaved; }
#define FAILSAFE_SETTINGS 1
''' + m.lift(MAINC, 'FLASHMEM static bool FailSafeSetFromPage()') + m.lift(MAINC, 'bool SaveFailSafeChannels()') + r'''   // (BankNamesFromPage is in test_noanswer's own lifts)
static void olderWord()   // src/main.cpp ButtonWasPressed's own lines for "FailSAVE" and "RXBAT"
{
    char FailSAVE[] = "FailSAVE", RXBAT[] = "RXBAT", pFailSafe[] = "page FailSafeView", NotConnected[] = "Not connected", ProgressStart[] = "vis Progress,1", ProgressEnd[] = "vis Progress,0", Progress[] = "Progress";
    char r2s[] = "r2s", r3s[] = "r3s", r4s[] = "r4s", r5s[] = "r5s", r6s[] = "r6s", r12s[] = "r12s", r0[] = "r0", r1[] = "r1";
    ''' + FS + '\n    ' + RB + r'''
}
static bool olderWords(const char *w) { if (strncmp(w, "FailSAVE", 8) && strncmp(w, "RXBAT", 5)) return false; olderWord(); return true; }
static void addOlder()
{
    Page f; f.id = 61; for (int i = 1; i <= 16; ++i) { char n[8]; snprintf(n, sizeof n, "fs%d", i); f.boxes[n] = { false, 0, "" }; }
    f.boxes["Progress"] = { false, 0, "" }; f.boxes["change"] = { true, 0, "XX:fs3 fs9" };
    { const char *w = "FailSAVE"; f.buttons["send"] = std::vector<uint8_t>(w, w + 8); }
    screen.pages["FailSafeView"] = f;
    Page b; b.id = 62; for (const char *n : { "r2s", "r3s", "r4s", "r5s", "r6s", "r12s", "r0", "r1" }) b.boxes[n] = { false, 0, "" };
    { const char *w = "RXBAT"; b.buttons["cells"] = std::vector<uint8_t>(w, w + 5); }
    screen.pages["BatteryView"] = b;
    screen.pages0 = screen.pages;
    for (bool &x : FailSafeChannel) x = false; RXCellCount = 3; TXLiPo = false; allSaved = 0; queued.clear(); wordHook = olderWords;
}
static bool failsafeIs(std::initializer_list<int> on) { for (int i = 0; i < 16; ++i) { bool want = false; for (int k : on) want |= k == i + 1; if (FailSafeChannel[i] != want) return false; } return true; }
'''
SCENES = r'''
    // F1. "FailSAVE": channels 3 and 9 ticked on the page; every box answers - the set is taken and sent. Then channel 12 ticked too and ONE BOX UNANSWERED
    //     (each in turn): the set stays as it was, and NOTHING is sent to the receiver
    more(); addOlder(); SendCommand((char *) "page FailSafeView"); CurrentView = 61; loopFor(600); BoundFlag = ModelMatched = true;
    { Page &pg = screen.pages["FailSafeView"]; pg.boxes["fs3"].val = 1; pg.boxes["fs9"].val = 1;
      tapAt(5, "send"); loopFor(2500);
      say("F1. 'FailSAVE', every box answered: channels 3 and 9 %d; sent to the receiver %d time(s)\n", (int) failsafeIs({ 3, 9 }), (int) queued.size());
      CHECK(failsafeIs({ 3, 9 }) && queued.size() == 1 && queued[0] == FAILSAFE_SETTINGS && boxesLostTold == 0);
      pg.boxes["fs12"].val = 1; pg.boxes["fs3"].val = 0;
      for (const char *lost : { "fs1", "fs3", "fs12", "fs16" })
      {
          queued.clear(); const int told0 = boxesLostTold; screen.mute.insert(lost); tapAt(5, "send"); loopFor(4000); screen.mute.clear(); loopFor(3000);
          say("F1 (%s unanswered): the set still channels 3 and 9: %d; sent %d; told %d\n", lost, (int) failsafeIs({ 3, 9 }), (int) queued.size(), boxesLostTold - told0);
          CHECK(failsafeIs({ 3, 9 }) && queued.empty() && boxesLostTold - told0 == 1);      // (it was: the mixture sent - channel 12 on and channel 3 still on, say)
      }
      tapAt(5, "send"); loopFor(2500); CHECK(failsafeIs({ 9, 12 }) && queued.size() == 1); }
    // F2. the page's way out: the changed boxes (its list: fs3 and fs9) - one unanswered: nothing taken, false, and the list is NOT cleared
    more(); addOlder(); SendCommand((char *) "page FailSafeView"); CurrentView = 61; loopFor(600);
    { Page &pg = screen.pages["FailSafeView"]; pg.boxes["fs3"].val = 1; pg.boxes["fs9"].val = 1;
      strcpy(TextIn, "XXXXfs3 fs9"); screen.mute.insert("fs9"); BoxesLostAtWork = BoxesLost; const bool ok = SaveFailSafeChannels(); screen.mute.clear(); loopFor(3000);
      say("F2. the failsafe page's way out, fs9 unanswered: taken %d; the set untouched %d; the page's list '%s'\n", (int) ok, (int) failsafeIs({}), pg.boxes["change"].txt.c_str());
      CHECK(!ok && failsafeIs({}) && pg.boxes["change"].txt == "XX:fs3 fs9");
      strcpy(TextIn, "XXXXfs3 fs9"); BoxesLostAtWork = BoxesLost; CHECK(SaveFailSafeChannels() && failsafeIs({ 3, 9 })); loopFor(200); CHECK(pg.boxes["change"].txt == "XX:"); }
    // F3. "RXBAT": 4 cells and LiPo chosen on the page (it was 3 cells, LiFe); one of the eight boxes unanswered - each in turn: NEITHER choice is taken, nothing saved
    for (const char *lost : { "", "r2s", "r4s", "r12s", "r0", "r1" })
    {
        more(); addOlder(); SendCommand((char *) "page BatteryView"); CurrentView = 62; loopFor(600);
        Page &pg = screen.pages["BatteryView"]; pg.boxes["r4s"].val = 1; pg.boxes["r1"].val = 1;
        const int told0 = boxesLostTold; if (*lost) screen.mute.insert(lost);
        tapAt(5, "cells"); loopFor(4000); screen.mute.clear(); loopFor(3000);
        say("F3 (%s). cells %u, LiPo %d, saved %d, told %d\n", *lost ? lost : "every box answered", (unsigned) RXCellCount, (int) TXLiPo, allSaved, boxesLostTold - told0);
        if (*lost) CHECK(RXCellCount == 3 && !TXLiPo && allSaved == 0 && boxesLostTold - told0 == 1);   // (it was: the cells taken and the battery kind not, or the other way round - and saved)
        else CHECK(RXCellCount == 4 && TXLiPo && allSaved == 1 && boxesLostTold == told0);
    }
    // F4. the bank names: six boxes (11 .. 16 on the page; 0 1 2 3 32 33 in hand) - one unanswered, each in turn: none is taken
    for (int lost = 0; lost <= 6; ++lost)
    {
        more(); addOlder(); SendCommand((char *) "page BankNameView"); CurrentView = BANKSNAMESVIEW; loopFor(600);
        static const uint8_t b0[6] = { 0, 1, 2, 3, 32, 33 }; memcpy(BanksInUse, b0, 6);
        if (lost) { char n[8]; snprintf(n, sizeof n, "BK%d", lost); screen.mute.insert(n); }
        BoxesLostAtWork = BoxesLost; const bool ok = BankNamesFromPage(); screen.mute.clear(); loopFor(3000);
        if (lost) CHECK(!ok && !memcmp(BanksInUse, b0, 6));                                 // (it was: those in front of it taken, and saved)
        else CHECK(ok && BanksInUse[0] == 11 && BanksInUse[5] == 16);
    }
    // F5. "Listen": six names, every box answering - the button's work asks the six boxes and WAITS FOR NOTHING (it said each name with a wait of 1.2 s
    //     behind it: seven seconds with no switch read); the main loop says them, one in 1.2 s
    more(); addOlder(); SendCommand((char *) "page BankNameView"); CurrentView = BANKSNAMESVIEW; loopFor(600);
    { const int s0 = soundsPlayed; const uint64_t t0 = nowUs; BoxesLostAtWork = BoxesLost; ListenToBanks(); const uint64_t work = nowUs - t0;
      uint64_t at[8] = { 0 }; int n = 0;
      for (int ms = 0; ms < 9000; ms += 5) { const int before = soundsPlayed; BankListenPoll(); if (soundsPlayed != before && n < 8) at[n++] = nowUs - t0 - work; nowUs += 5000; }
      say("F5. 'Listen', six names: the button's work took %.0f ms; names said %d, at %.1f %.1f %.1f %.1f %.1f %.1f s\n", work / 1e3, soundsPlayed - s0, at[0] / 1e6, at[1] / 1e6, at[2] / 1e6, at[3] / 1e6, at[4] / 1e6, at[5] / 1e6);
      CHECK(work < 1000000 && soundsPlayed - s0 == 6 && n == 6);
      for (int i = 0; i < 6; ++i) CHECK(at[i] + 20000 >= (uint64_t) i * 1200000 && at[i] <= (uint64_t) i * 1200000 + 40000);
      // ... a box unanswered: nothing is taken, and nothing said
      const int s1 = soundsPlayed; screen.mute.insert("BK3"); BoxesLostAtWork = BoxesLost; ListenToBanks(); screen.mute.clear(); loopFor(3000);
      for (int ms = 0; ms < 3000; ms += 5) { BankListenPoll(); nowUs += 5000; }
      CHECK(soundsPlayed == s1);
      // ... the page left while the names are said (two have been): no more - and NONE when the page is come back to (the saying is over, not held)
      const int s2 = soundsPlayed; BoxesLostAtWork = BoxesLost; ListenToBanks();
      for (int ms = 0; ms < 1500; ms += 5) { BankListenPoll(); nowUs += 5000; }
      CHECK(soundsPlayed - s2 == 2);
      CurrentView = FRONTVIEW; for (int ms = 0; ms < 3000; ms += 5) { BankListenPoll(); nowUs += 5000; }
      CHECK(soundsPlayed - s2 == 2);
      CurrentView = BANKSNAMESVIEW; for (int ms = 0; ms < 8000; ms += 5) { BankListenPoll(); nowUs += 5000; }
      say("F5. the page left after two names, and come back to: %d names said in all\n", soundsPlayed - s2);
      CHECK(soundsPlayed - s2 == 2); }
    wordHook = nullptr;
'''
sys.exit(lib.build_run('older_gathers', SCENES, extra=EXTRA, more_defines=('FAILSAFE_VIEW',)))   # (ListenToBanks and BankListenPoll are in test_noanswer's own lifts)
