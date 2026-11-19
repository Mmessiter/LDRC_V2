#!/usr/bin/env python3
"""Reviewer B (15th review): the Sub-trim page - two narrow doors by which OK saves what the page did not show.
 X1. THE FIRST VISIT SINCE THIS BOARD STARTED, the page's first "done" never heard: SubTrimSaysDone is still false, so EndSubTrimView's second rule
     ("OK before the page has said this board's last click done stays") is not asked. A touch (not taken: nothing is, before a "done"), then OK twice
     150 ms apart on a screen 300 ms behind: the first OK writes the page out and stays; the second saves and leaves - pressed while the page still
     showed the touch's number.
 X2. THE PAGE'S MARKERS LOST ON THE WIRE (the page is up, its "done" heard: SubTrimShown): until this board has found the marker lost (1.5 s and a
     round trip) every press is let go as "the old page's" - a touch's burst too. That burst REACHED this board, and nothing is owed for it: the page
     shows the touch, the model has not got it, and OK saves and leaves.
The REAL Trims.h and main.cpp's own lines over scene_subtrim's pretend page."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_subtrim as base
EXTRA = base.EXTRA + r'''
static int oksServed = 0, oksLeft = 0; static long shownAtLeave = 0; static int savedThen = 0;
static void myOk(int n) { if (n != 21) return; ++oksServed; if (CurrentView != SUBTRIMVIEW) return; EndSubTrimView(); if (CurrentView != SUBTRIMVIEW) ++oksLeft; }
static bool firstDoneLost = false; static int donesSeen = 0;
static bool loseFirstDone() { return firstDoneLost && donesSeen++ == 0; }
'''
SCENES = r'''
    // X1. the first visit since this board started; the page's first "done" is never heard
    {
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true;
        CHECK(!SubTrimSaysDone);                                                   // (nothing has said "done" yet in this program's life)
        screen.latencyUs = 300000; firstDoneLost = true; donesSeen = 0; doneLostNow = loseFirstDone;
        B("n00") = 0;
        SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
        stLoop(900);                                                                // the page is up, its boxes written - its "done" lost on the way
        CHECK(!SubTrimSaysDone && shown(1) == 0 && trim(1) == 0);
        tapAt(5, "plus"); stLoop(40);                                               // "+" on channel 1: the page shows 1
        const int pageAfterTouch = shown(1);
        tapAt(5, "ok"); tapAt(155, "ok");                                           // OK, and OK again 150 ms on (the screen is 300 ms behind: the putting-right has not landed)
        long shownAtSecondOk = -99; { const uint64_t until = nowUs + 400000; while (nowUs < until) { LoopPass(); SubTrimPoll(); if (nowUs >= until - 245000 && shownAtSecondOk == -99) shownAtSecondOk = shown(1); nowUs += 500; } }
        stLoop(1500);
        say("X1. first visit, the first 'done' lost: '+' made the page show %d (the model has %d); OK twice 150 ms apart: served %d, left the page %d time(s); as the second OK was pressed the page showed %ld; the model saved has %d\n",
            pageAfterTouch, trim(1), oksServed, oksLeft, shownAtSecondOk, trim(1));
        CHECK(pageAfterTouch == 1 && trim(1) == 0);
        CHECK(oksLeft == 0 || shownAtSecondOk == trim(1));                           // WHAT SHOULD HOLD: OK leaves only with the page showing what is saved
        doneLostNow = nullptr; firstDoneLost = false; extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr;
    }
    // X2. the page's two markers lost on the wire (the screen is asked for them by name: "get ldrcsync" - both answers lost; the page comes up all the same)
    {
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0;
        openSubTrim();                                                              // a first visit, all well: the screen says markers, and "done"
        CHECK(SubTrimSaysDone && SubTrimShown && pageIsModel());
        // Help and its way back (main.cpp "GOTO:"): the page command's two markers never reach this board
        CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); stLoop(600);
        screen.sysMute.insert("ldrcsync");
        SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack();
        stLoop(400); screen.sysMute.clear();                                         // (the page is up; from here the screen answers everything again)
        const bool shownThen = SubTrimShown; const uint32_t awaited = ScreenMarkAwaited; const int stale0 = stale;
        tapAt(5, "plus"); stLoop(300);                                              // "+" on channel 1, half a second after the page came back
        say("X2. the page back from Help, its markers lost: 'done' heard %d (SubTrimShown), a marker still awaited %d; '+' made the page show %d - the model has %d; presses let go as the old page's %d; a writing-out owed %d\n",
            (int) shownThen, awaited != 0, shown(1), trim(1), stale - stale0, (int) SubTrimSettleDue);
        stLoop(4000);                                                                // (the marker is found lost; nothing more happens)
        const int pageBefore = shown(1), modelBefore = trim(1);
        tapAt(5, "ok"); stLoop(800);
        say("    four quiet seconds on the page shows %d, the model has %d; OK: served %d, left the page %d - saved with %d on channel 1\n", pageBefore, modelBefore, oksServed, oksLeft, trim(1));
        CHECK(pageBefore == modelBefore);                                             // WHAT SHOULD HOLD: a burst this board itself let go is owed a writing-out (as one not kept for want of room is)
        CHECK(oksLeft == 0 || pageBefore == trim(1));
        extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr;
    }

    // X3. A SCREEN WHOSE LOOP STANDS STILL FOR THREE SECONDS with a putting-right unread in its queue - and OK pressed as it wakes (the real screen,
    //     when the silence was in another job than its serial one, prints what a finger did BEFORE it reads the commands: the pretend screen's wakeRound)
    {
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0;
        openSubTrim(); screen.latencyUs = 20000;
        tapAt(5, "plus!"); stLoop(150);                                               // "+" never heard: the page shows 1, the model has 0 (known: 19a)
        tapAt(5, "plus"); stLoop(12);                                                 // "+" again: 1 -> 2, not taken - its putting-right is on its way to the screen
        screen.stall(nowUs, 3000, false, 30000);                                      // ... which stands still from now, three seconds
        const int pageDuring = shown(1);
        tapAt(3005, "ok");                                                            // his finger is on OK as the screen wakes (it still shows 2): the touch is seen in the round before the commands are read
        long shownAtOk = -99; { const uint64_t until = nowUs + 3400000; while (nowUs < until) { LoopPass(); SubTrimPoll(); if (oksServed && shownAtOk == -99) shownAtOk = shown(1); nowUs += 500; } }
        say("X3. a putting-right in the queue of a screen that stands still 3 s; OK pressed on it (it showed %d; the model has %d): OK served %d, left the page %d - as OK was served the page showed %ld, saved %d\n",
            pageDuring, trim(1), oksServed, oksLeft, shownAtOk, trim(1));
        CHECK(oksLeft == 0 || shownAtOk == trim(1));                                   // WHAT SHOULD HOLD: OK leaves only with the page showing what is saved
        extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr;
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('subtrim_doors', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',), sanitize=True, timeout=1200))
