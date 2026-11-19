#!/usr/bin/env python3
"""Reviewer B (16th review): the Sub-trim page - "can OK still leave on the clock with the page showing what the model has not got? Find another way."
 Y1. THE COUNT OF "CLICKS ONCE MORE" IS NOT BEGUN AFRESH BY A FRESH WRITING-OUT (another model read under the open page: SubTrimPageOut(true)).
     Two "done"s lost on the wire, OK pressed twice past the two seconds (the page is right: only its "done"s were lost) - SubTrimAskedAgain stands
     at its most. He stays on the page. Then another model is read under the page while the screen stands still for three seconds (the brief's own
     case), a finger on OK as it wakes: ONE stall is enough now - OK leaves on the clock, the page still showing the model before.
     (With the count begun afresh in SubTrimPageOut(fresh) the same press clicks once more and stays.)
The REAL Trims.h and main.cpp's own lines over scene_subtrim's pretend page (as scene_subtrim_doors.py builds it)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_subtrim as base
EXTRA = base.EXTRA + r'''
static int oksServed = 0, oksLeft = 0;
static void myOk(int n) { if (n != 21) return; ++oksServed; if (CurrentView != SUBTRIMVIEW) return; EndSubTrimView(); if (CurrentView != SUBTRIMVIEW) ++oksLeft; }
static bool donesLost = false;
static bool loseDone() { return donesLost; }
static long shownAtPress14 = -99; static int okPressesOnPage = 0;   // what the page showed on channel 14 AS OK WAS PRESSED (in the screen's own time, as the storms' book takes it)
static void zTap(const char *button) { if (!strcmp(button, "ok")) { if (screen.page == "SubTrimView") { shownAtPress14 = B(boxOf(14)); ++okPressesOnPage; } return; } stTap(button); }
'''
SCENES = r'''
    {
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0;
        openSubTrim(); screen.latencyUs = 20000;
        CHECK(SubTrimSaysDone && SubTrimShown && pageIsModel() && SubTrimAskedAgain == 0);
        // a change taken while the last click's "done" is lost: the page is written out when he has paused - and THAT "done" is lost too
        doneLostNow = loseDone; donesLost = true;
        SubTrimPageOut(false); stLoop(300);                                           // (a writing-out of this board's - a settle pass; its "done" never heard)
        CHECK(pageIsModel() && SubTrimDone != SubTrimAsked);
        { const uint16_t askedBefore = SubTrimAsked;                                    // (the author's, behind reviewer A's remark of the seventeenth review: nothing held the TWO seconds)
          tapAt(1300, "ok"); stLoop(1500);                                              // OK a second and a half behind the click, its "done" not heard: it STAYS - and clicks nothing yet
          CHECK(CurrentView == SUBTRIMVIEW && SubTrimAsked == askedBefore && SubTrimAskedAgain == 0 && oksLeft == 0); }
        tapAt(2100, "ok"); stLoop(2300);                                              // OK past the two seconds: clicked once more (its "done" lost again), the page stays
        tapAt(2100, "ok"); stLoop(2300);                                              // ... and once more
        say("Y1. two 'done's lost, OK twice past the two seconds: served %d, left %d; the count of clicks once more stands at %d (the most is %d); the page is right: %d\n", oksServed, oksLeft, (int) SubTrimAskedAgain, (int) SUBTRIM_ASK_AGAIN_MOST, (int) pageIsModel());
        CHECK(oksLeft == 0 && SubTrimAskedAgain == SUBTRIM_ASK_AGAIN_MOST && pageIsModel());
        donesLost = false;                                                            // (from here nothing is lost any more)
        // he stays on the page. Another model is read under it - while the screen stands still for three seconds; his finger on OK as it wakes
        screen.stall(nowUs, 3000, false, 30000);
        for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + 10 + i);          // the other model's sub trims
        freshOut();                                                                   // main.cpp UpdateButtonLabels: the page written out, fresh - unread in the still screen's queue
        const int pageDuring = shown(1), model = trim(1);
        tapAt(3005, "ok");
        long shownAtOk = -99; { const uint64_t until = nowUs + 3400000; while (nowUs < until) { LoopPass(); SubTrimPoll(); if (oksServed == 3 && shownAtOk == -99) shownAtOk = shown(1); nowUs += 500; } }
        say("    another model read under the still screen (the page showed %d on channel 1, the new model has %d); OK as it woke: served %d, LEFT the page %d time(s) - as that OK was served the page showed %ld; saved %d\n",
            pageDuring, model, oksServed, oksLeft, shownAtOk, trim(1));
        CHECK(oksLeft == 0 || shownAtOk == trim(1));                                   // WHAT SHOULD HOLD: OK leaves only with the page showing what is saved
        extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr; doneLostNow = nullptr;
    }
    // Y0 (the control): the same model read under the still screen and the same OK as it wakes - with the count at 0: OK clicks once more and STAYS
    {
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0;
        openSubTrim(); screen.latencyUs = 20000;
        CHECK(SubTrimSaysDone && SubTrimShown && pageIsModel() && SubTrimAskedAgain == 0);
        screen.stall(nowUs, 3000, false, 30000);
        for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + 10 + i);
        freshOut();
        tapAt(3005, "ok");
        long shownAtOk = -99; { const uint64_t until = nowUs + 3400000; while (nowUs < until) { LoopPass(); SubTrimPoll(); if (oksServed == 1 && shownAtOk == -99) shownAtOk = shown(1); nowUs += 500; } }
        say("Y0. the control (the count at 0): OK as the screen woke: served %d, left %d (the page showed %ld then); two seconds on the page shows %d, the model has %d\n", oksServed, oksLeft, shownAtOk, shown(1), trim(1));
        CHECK(oksLeft == 0 && shown(1) == trim(1));
        extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr; doneLostNow = nullptr;
    }
    // Z1 (found by the storm with reviewer B's mix, seed 77123456, trial 130377 = seed 77253833; made a scene here):
    //    THE FIRST VISITS SINCE THIS BOARD STARTED, the page's first "done" never heard (SubTrimSaysDone false). OK - obeyed, the page was the model's -
    //    and "-" 15 ms on, as the page is going (the screen is 24 ms behind): the screen's box of channel 14 keeps the finger's number; its burst reaches
    //    this board on ANOTHER page and counts for nothing (SubTrimWordLetGo: "another page") - not even for "this page file says done".
    //    "Sub trim" pressed again; his finger on OK as the page comes up, a round in front of the sixteen writes behind the page command:
    //    nothing has been heard yet, so OK is obeyed at once - the page showing the finger's number, the model saved without it.
    {
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0;
        SubTrimSaysDone = false; SubTrimShown = false; SubTrimAsked = SubTrimDone = 0;      // (as the storms begin a first visit)
        screen.realUart = true; screen.shoutForm = 198;                                 // (as the storms set the pretend screen: every command it handles takes its time)
        screen.latencyUs = 24000; screen.roundUs = 0;
        for (int i = 0; i < 16; ++i) SubTrims[i] = 127; SubTrims[13] = (uint8_t) (127 - 96);
        donesLost = true; doneLostNow = loseDone; tapScript = zTap; okPressesOnPage = 0;
        SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
        stLoop(700);
        CHECK(!SubTrimSaysDone && pageIsModel());
        tapCh(5, 14); stLoop(200);
        tapAt(5, "ok"); tapAt(20, "minus"); stLoop(320);                              // OK; and "-" as the page is going
        const int leftFirst = oksLeft; const bool heardYet = SubTrimSaysDone;
        say("Z1. first visit, the first 'done' lost: OK left the page %d time(s) (the model's channel 14: %d); a '-' as it went: the screen's box of channel 14 now holds %d; this board has heard of a page that says 'done': %d\n", leftFirst, trim(14), shown(14), (int) heardYet);
        CHECK(leftFirst == 1 && trim(14) == -96 && shown(14) == -97);
        donesLost = false;                                                             // (from here nothing is lost)
        SendCommand((char *) "page SubTrimView");                                       // "Sub trim" pressed again
        uint64_t loadEnd = 0; for (auto &c : screen.cmds) if (c.second == "page SubTrimView") loadEnd = c.first + screen.loadUs;
        if (!loadEnd) loadEnd = screen.busyUntil;
        SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
        screen.taps.insert({ loadEnd + 300, "ok" });                                   // his finger on OK three tenths of a millisecond after the page is up - the screen is still at the first of the commands behind its page command
        shownAtPress14 = -99; stLoop(700); const long shownAtOk = shownAtPress14;
        say("    the page put up again, OK as it came up: OK pressed on the page %d time(s) in all, served %d, left %d; AS THAT OK WAS PRESSED the page showed %ld on channel 14 - the model saved has %d\n", okPressesOnPage, oksServed, oksLeft, shownAtOk, trim(14));
        say("    (debug) the screen's page %s, taps on nothing %d, this board's view %u, load %u us, round %u us, a marker awaited %u, presses let go as the old page's %d\n", screen.page.c_str(), (int) screen.tapsOnNothing, (unsigned) CurrentView, (unsigned) screen.loadUs, (unsigned) screen.roundUs, (unsigned) ScreenMarkAwaited, stale);
        CHECK(oksLeft == leftFirst || shownAtOk == trim(14));                          // WHAT SHOULD HOLD: OK leaves only with the page showing what is saved
        screen.realUart = false;
        extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr; doneLostNow = nullptr;
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('subtrim_doors16', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',)))
