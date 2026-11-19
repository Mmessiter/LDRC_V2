#!/usr/bin/env python3
"""R10-B exp 1: RfSaveFirst reads QuestionClosedItself AFTER GetSaveOrDiscard has sent the question's way back (which waits 20 ms,
flying the model). A box put up from inside THAT wait (the link found lost with the motor switch on) is answered by the pilot:
its GetYesOrNo sets QuestionClosedItself = false - and "Save now?", which this board had closed by itself (the screen silent),
comes back as the pilot's DISCARD."""
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
static bool armedX = false, firedX = false;
static void lostInWayBack() { if (!armedX || firedX || ModalWaits || questionsClosed != 1) return; firedX = true; motorOffAtUs = nowUs + 3000000; tapAt(4500, "yes"); LinkLostNow(); }
'''
SCENES = r'''
    // "Save now?" waits; the screen's loop stands still for 5.5 s (from 1.0 s after the question came up): the question is closed by this
    // board as "silent" at about 4.5 s. In the 20 ms behind its way back the link is found lost with the motor switch on: the motor box.
    // The screen wakes; the pilot switches the motor off and presses that box's OK.
    for (int withBox = 0; withBox < 2; ++withBox)
    {
        more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(50); savesRun = pagesLeft = 0; edited = true;
        stallAtUs = nowUs + 1005000; stallLenMs = 5500; sendDataHook = stallWhenDue; CurrentView = RXSETUPVIEW1;
        armedX = withBox != 0; firedX = false; flyHook = lostInWayBack;
        const uint64_t t0 = nowUs;
        const bool discard = RfSaveFirst("page RXOptionsView", "The edited PIDs are", theSave, theLeave, &edited); sendDataHook = nullptr; flyHook = nullptr; armedX = false;
        say("X1 (%s). 'Save now?' closed by this board (silent %d, closed %d) after %.2f s; the motor box came up in the way back's wait: %d;\n    RfSaveFirst says %s; QuestionClosedItself now %d; the save ran %d time(s)\n",
            withBox ? "with the box" : "no box", questionsSilent, questionsClosed, (nowUs - t0) / 1e6, (int) firedX, discard ? "DISCARD (the caller throws the edits away and leaves the page)" : "keep the page", (int) QuestionClosedItself, savesRun);
        CHECK(questionsSilent >= 1);
        if (withBox) CHECK(firedX);
        CHECK(!discard);        // what should hold: a question closed by this board is never the pilot's Discard
        loopFor(8000);
    }
    // ... and the same for the other askers: HOW A QUESTION ENDED is what its asker is told - not how a box put up in its way back's wait ended.
    // A question and a message box, each closed by this board for the screen's silence, the motor box answered by the pilot in the way back's wait
    for (int asker = 0; asker < 2; ++asker)
    {
        more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(50);
        stallAtUs = nowUs + 1005000; stallLenMs = 5500; sendDataHook = stallWhenDue; CurrentView = RXSETUPVIEW1;
        armedX = true; firedX = false; flyHook = lostInWayBack;
        bool yes = false;
        if (asker == 0) yes = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?");
        else MsgBox((char *) "page RXOptionsView", (char *) "Not saved.");
        sendDataHook = nullptr; flyHook = nullptr; armedX = false;
        say("X2 (%s). closed by this board for the screen's silence, the motor box answered in its way back's wait (%d): answered %d; 'closed by itself' %d, 'overtaken' %d\n",
            asker ? "a message box" : "a question", (int) firedX, (int) yes, (int) QuestionClosedItself, (int) QuestionOvertaken);
        CHECK(firedX && !yes && questionsSilent >= 1);
        CHECK(QuestionClosedItself && !QuestionOvertaken);       // this question's own: closed by the board, and no page came over it before its way back
        loopFor(8000);
    }
'''
sys.exit(lib.build_run('closeditself', SCENES, extra=EXTRA, sanitize=False))
