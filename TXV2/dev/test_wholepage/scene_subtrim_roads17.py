#!/usr/bin/env python3
"""Reviewer A (17th review): the Sub-trim rule after the sixteenth review's cures B5 and B6 - two roads round them.
 P1. B5 BY THE PURGE. Reviewer B's Z1 exactly (first visit since the board started, the first "done" lost; OK; "-" 15 ms on, as the page goes)
     - but the "-" burst is already in this board's kept queue when OK is served: the board was away from the wire for 45 ms (a card write, a
     model's connection ...) and its next send read both frames in (GetReturnCode -> StashPendingEventBytes: the page is up, both are kept).
     OK is served from the queue, its page command PURGES the "-" (Nextion.h PurgeKeptPresses: NoteStalePress - and no SubTrimWordLetGo):
     the burst teaches nothing. "Sub trim" again, OK as the page comes up: left at once, the page showing the finger's number.
 P0. the control: the same without the 45 ms (Z1 as the suite has it): the burst is let go at the marker's rule, and teaches.
 Q1. B6 ON THE ROAD THAT IS NOT FRESH. Reviewer B's Y1 exactly up to "the count stands at its most" (three "done"s lost, OK twice past two
     seconds) - then NOT another model, but a change that is not taken (the page one touch ahead: a burst lost on the same wire - item 19a),
     its putting-right unread in a screen that stands still for three seconds, a finger on OK as it wakes: ONE stall, OK leaves on the clock,
     the page showing the number that was not taken. (SubTrimAskedAgain is begun afresh by a FRESH writing-out only.)
 Q0. the control: the same with the count at 0: OK clicks once more and stays.
The REAL Trims.h, Nextion.h and main.cpp's own lines over scene_subtrim's pretend page (as scene_subtrim_doors16.py builds it)."""
import os, sys
TW = os.path.dirname(os.path.abspath(__file__))   # (taken into the suite: this file's own folder)
sys.path.insert(0, TW)
import lib
import scene_subtrim as base
EXTRA = base.EXTRA + r'''
static int oksServed = 0, oksLeft = 0;
static void myOk(int n) { if (n != 21) return; ++oksServed; if (CurrentView != SUBTRIMVIEW) return; EndSubTrimView(); if (CurrentView != SUBTRIMVIEW) ++oksLeft; }
static bool donesLost = false;
static bool loseDone() { return donesLost; }
static long shownAtPress = -99; static int okPressesOnPage = 0, watchCh = 14;   // what the page showed on the watched channel AS OK WAS PRESSED (in the screen's own time)
static void zTap(const char *button) { if (!strcmp(button, "ok")) { if (screen.page == "SubTrimView") { shownAtPress = B(boxOf(watchCh)); ++okPressesOnPage; } return; } stTap(button); }
static int runZ1(bool boardAway)
{
    more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0; watchCh = 14;
    SubTrimSaysDone = false; SubTrimShown = false; SubTrimAsked = SubTrimDone = 0;      // (as the storms begin a first visit)
    screen.realUart = true; screen.shoutForm = 198;
    screen.latencyUs = 24000; screen.roundUs = 0;
    for (int i = 0; i < 16; ++i) SubTrims[i] = 127; SubTrims[13] = (uint8_t) (127 - 96);
    donesLost = true; doneLostNow = loseDone; tapScript = zTap; okPressesOnPage = 0;
    SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
    stLoop(700);
    if (SubTrimSaysDone || !pageIsModel()) { printf("setup: not a first visit\n"); return -1; }
    tapCh(5, 14); stLoop(200);
    const int stale0 = stale, let0 = wordsLetGo;
    tapAt(5, "ok"); tapAt(20, "minus");                                           // OK; and "-" as the page is going
    if (boardAway)
    {   // THE BOARD IS AWAY FROM THE WIRE FOR 45 ms (a card write: tens of milliseconds - FlightGuard.h's own words), and its next send reads the wire in
        nowUs += 45000;
        StashPendingEventBytes();                                                 // (Nextion.h GetReturnCode, behind every SendCommand / SendText / SendValue)
        say("    (the board away for 45 ms, then a send: frames kept in its queue %d)\n", (int) PendingCount);
    }
    stLoop(320);
    const int leftFirst = oksLeft; const bool heardYet = SubTrimSaysDone;
    say("%s first visit, the first 'done' lost: OK left the page %d time(s) (the model's channel 14: %d); a '-' as it went: the screen's box holds %d; presses let go as stale %d, told to Trims.h (SubTrimWordLetGo) %d; this board knows of a page that says 'done': %d\n",
        boardAway ? "P1." : "P0.", leftFirst, trim(14), shown(14), stale - stale0, wordsLetGo - let0, (int) heardYet);
    donesLost = false;                                                             // (from here nothing is lost)
    SendCommand((char *) "page SubTrimView");                                       // "Sub trim" pressed again
    uint64_t loadEnd = 0; for (auto &c : screen.cmds) if (c.second == "page SubTrimView") loadEnd = c.first + screen.loadUs;
    if (!loadEnd) loadEnd = screen.busyUntil;
    SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
    screen.taps.insert({ loadEnd + 300, "ok" });                                   // his finger on OK three tenths of a millisecond after the page is up
    shownAtPress = -99; stLoop(700); const long shownAtOk = shownAtPress;
    say("    the page put up again, OK as it came up: served %d, left %d in all; AS THAT OK WAS PRESSED the page showed %ld on channel 14 - the model saved has %d\n", oksServed, oksLeft, shownAtOk, trim(14));
    const bool holds = oksLeft == leftFirst || shownAtOk == trim(14);              // WHAT SHOULD HOLD: OK leaves only with the page showing what is saved
    screen.realUart = false;
    extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr; doneLostNow = nullptr;
    return holds ? 1 : 0;
}
static int runY(bool countSpent)
{
    more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0; watchCh = 1;
    tapScript = zTap; okPressesOnPage = 0;
    openSubTrim(); screen.latencyUs = 20000;
    if (!(SubTrimSaysDone && SubTrimShown && pageIsModel() && SubTrimAskedAgain == 0)) { printf("setup: the page is not up\n"); return -1; }
    doneLostNow = loseDone;
    if (countSpent)
    {   // reviewer B's Y1, word for word: a writing-out whose "done" is lost, OK twice past the two seconds (each clicks once more; those "done"s lost too)
        donesLost = true;
        SubTrimPageOut(false); stLoop(300);
        tapAt(2100, "ok"); stLoop(2300);
        tapAt(2100, "ok"); stLoop(2300);
        if (!(oksLeft == 0 && SubTrimAskedAgain == SUBTRIM_ASK_AGAIN_MOST && pageIsModel())) { printf("setup: the count is not spent\n"); return -1; }
    }
    const int served0 = oksServed;
    // the wire that lost the "done"s loses one touch's burst (item 19a: the page stands one touch ahead - known, and put right at the next touch there)
    tapAt(10, "plus!"); stLoop(200);
    donesLost = false;                                                             // (from here NOTHING is lost any more)
    const int ahead = shown(1);
    tapAt(10, "plus"); stLoop(11);                                                 // the next "+": it starts from a number the model has not got - NOT TAKEN, its putting-right goes out at once ...
    screen.stall(nowUs, 3000, false, 30000);                                       // ... and lies unread: the screen stands still for three seconds (its WiFi, its card)
    const int pageDuring = shown(1), model = trim(1);
    tapAt(3005, "ok");                                                             // his finger on OK as it wakes
    long shownAtOk = -99; int leftAt = -1;
    { const uint64_t until = nowUs + 3400000; while (nowUs < until) { LoopPass(); SubTrimPoll(); if (oksServed == served0 + 1 && shownAtOk == -99) { shownAtOk = shownAtPress; leftAt = oksLeft; } nowUs += 500; } }
    say("%s the count of clicks once more at %d; the page one touch ahead (%d, the model has %d: a burst lost - 19a); '+' again: NOT TAKEN (the page shows %d, the model has %d), the screen still for 3 s, OK as it wakes: "
        "served %d, LEFT the page %d time(s); as that OK was pressed the page showed %ld; saved %d; two seconds on the page shows %d\n",
        countSpent ? "Q1." : "Q0.", countSpent ? (int) SUBTRIM_ASK_AGAIN_MOST : 0, ahead, model, pageDuring, model, oksServed - served0, oksLeft, shownAtOk, trim(1), shown(1));
    const bool holds = oksLeft == 0 || shownAtOk == trim(1);                        // WHAT SHOULD HOLD: OK leaves only with the page showing what is saved
    extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr; doneLostNow = nullptr;
    return holds ? 1 : 0;
}
'''
SCENES = r'''
    { const int p0 = runZ1(false); CHECK(p0 == 1); }     // the control: the suite's Z1 - cured
    { const int p1 = runZ1(true); CHECK(p1 == 1); }      // B5 by the purge
    { const int q0 = runY(false); CHECK(q0 == 1); }      // the control: the count at 0 - OK stays
    { const int q1 = runY(true); CHECK(q1 == 1); }       // B6 on the road that is not fresh
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('subtrim_roads17', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',)))
