#!/usr/bin/env python3
"""E5: a question box and a screen that is WELL but busy. The question is closed as "No" once 3.5 s have gone without a "sendme"
answer - but the screen is only asked once a second, the first time a second after the question came up: a loop of the
screen's that stands still for 2.5 s is enough. And for OK's "Save now?" (Save / Discard) "No" is DISCARD: the page's edits
go and the page is left. Real routines: GetYesOrNo, GetConfirmation, GetSaveOrDiscard (Utilities.h), RfSaveFirst (RF_SaveNow.h)."""
import sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
SNOW = m.release(m.src('include/RF_SaveNow.h'))
EXTRA = r'''
int RfLeaveView = 0; void (*RfLeaveFn)() = nullptr;
''' + m.lift(m.UTIL, 'bool GetSaveOrDiscard(char *goback, char *Prompt)') + m.lift(SNOW, 'void RfSavedThenLeave(int view)') + m.lift(SNOW, 'bool RfSaveFirst(') + r'''
static int savesRun = 0, pagesLeft = 0; static bool edited = true;
static void theSave() { ++savesRun; edited = false; } static void theLeave() { ++pagesLeft; }
'''
SCENES = r'''
    for (uint32_t stallMs : { 2400u, 2550u, 2700u, 3400u })
    {
        more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(50);
        stallAtUs = nowUs + 1005000; stallLenMs = stallMs; sendDataHook = stallWhenDue; tapAt(6000, "yes"); const uint64_t t0 = nowUs;
        const bool answer = GetConfirmation((char *) "page RXOptionsView", (char *) "Save the travel extents?"); sendDataHook = nullptr;
        say("E5a. a question; the screen's loop stands still for %.2f s, from 1.0 s after it came up (the pilot's Yes comes at 6 s): answered %s after %.2f s; closed %d (silent %d); owed %d\n",
            stallMs / 1e3, answer ? "YES" : "No", (nowUs - t0) / 1e6, questionsClosed, questionsSilent, (int) ScreenAnswerOwed);
        if (stallMs < 3500) CHECK(answer);   // (the brief's known residual 9: "busy for that long" = 3.5 s)
        loopFor(8000);
    }
    // OK with unsaved edits: "... not saved. Save now?" (Save = Yes, Discard = No). The screen's loop stands still for 2.7 s.
    more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(50); savesRun = pagesLeft = 0; edited = true;
    { stallAtUs = nowUs + 1005000; stallLenMs = 2700; sendDataHook = stallWhenDue; tapAt(6000, "yes"); CurrentView = RXSETUPVIEW1;
      const bool discard = RfSaveFirst("page RXOptionsView", "The edited PIDs are", theSave, theLeave, &edited); sendDataHook = nullptr;
      say("E5b. OK's 'Save now?' under the same 2.7 s: RfSaveFirst says %s; the save ran %d time(s); log:", discard ? "DISCARD (the caller throws the edits away and leaves the page)" : "save", savesRun); for (auto &l : logLines) say(" [%s]", l.c_str()); say("\n");
      CHECK(!discard && savesRun == 1); }
    // (the author's own, 15 Nov 2026) ... and the screen DIES FOR GOOD under "Save now?": the question is closed by this board - which is
    // neither the pilot's Save nor his Discard. Nothing is saved, nothing thrown away, the caller stays on its page; and a Discard
    // the pilot does press is a Discard, as ever
    more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(50); savesRun = pagesLeft = 0; edited = true; holdCatchUp = true;
    { static bool dead; dead = false; sendDataHook = [] { if (!dead && screen.page == "PopupView" && ModalWaits) { dead = true; screen.deaf = true; } }; CurrentView = RXSETUPVIEW1;
      const bool discard = RfSaveFirst("page RXOptionsView", "The edited PIDs are", theSave, theLeave, &edited); sendDataHook = nullptr;
      CHECK(dead && !discard && savesRun == 0 && edited && QuestionClosedItself && !QuestionOvertaken && questionsSilent == 1); }
    more(); tapAt(5, "setup"); loopFor(800); savesRun = pagesLeft = 0; edited = true; boxSpins = 399000;   // (nobody answers: the test's own give-up stands for "Discard")
    { CurrentView = RXSETUPVIEW1; const bool discard = RfSaveFirst("page RXOptionsView", "The edited PIDs are", theSave, theLeave, &edited);
      CHECK(discard && savesRun == 0 && !QuestionClosedItself); }
'''
sys.exit(lib.build_run('question_stall', SCENES, extra=EXTRA, sanitize=False))
