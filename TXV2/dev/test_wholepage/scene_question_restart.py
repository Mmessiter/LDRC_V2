#!/usr/bin/env python3
"""R10-B exp 9: A QUESTION WAITS; THE SCREEN STARTS AGAIN AND EVERY SIGN OF IT IS LOST (no power-on bytes, no word). It comes back on the
question's page as the card has it and frames nothing. The pilot presses Yes on it. What must hold: that Yes is not this question's
answer; the restart is found by asking; the question is closed as "No"; "Save now?" closed so is neither Save nor Discard."""
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
    for (int kind = 0; kind < 2; ++kind)
        for (uint64_t boot : { 1200000ull, 3000000ull })
        {
            more(); screen.restartReason = 5; screen.bootRecord = ""; screen.powerOnUs = boot; screen.restartPowerOnBytes = false; screen.restartSaysWord = false;
            tapAt(5, "setup"); loopFor(900); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(60); savesRun = pagesLeft = 0; edited = true; CurrentView = RXSETUPVIEW1;
            tapAt(700, "#restart"); tapAt((uint32_t) (boot / 1000) + 2500, "yes"); tapAt((uint32_t) (boot / 1000) + 3200, "yes");
            const uint64_t t0 = nowUs; bool answer = false, discard = false;
            if (kind == 0) answer = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?\r\nThis cannot be undone.");
            else discard = RfSaveFirst("page RXOptionsView", "The edited PIDs are", theSave, theLeave, &edited);
            const double took = (nowUs - t0) / 1e6;
            loopFor(9000);
            say("R%d. %s; the screen restarts unseen 0.7 s on (a start of %.1f s) and the pilot presses Yes on what it then shows: %s after %.1f s; closed %d (silent %d); ghosts %d;\n    restart found by asking %d, the front page afresh %d (reason %d); the save ran %d; closed by the board %d; page now %s, view %u\n",
                kind, kind ? "'Save now?'" : "a question", boot / 1e6, kind ? (discard ? "DISCARD" : "the page stays") : (answer ? "YES" : "No"), took, questionsClosed, questionsSilent, (int) ghosts.size(),
                restartsFoundByAsking, restartsHandled, lastRestartReason, savesRun, (int) QuestionClosedItself, screen.page.c_str(), (unsigned) CurrentView);
            CHECK(!answer && !discard && savesRun == 0);
            CHECK(restartsHandled == 1 && screen.page == "FrontView" && CurrentView == FRONTVIEW && !ScreenRestartSeen && !ScreenAnswerOwed);
        }
'''
sys.exit(lib.build_run('question_restart', SCENES, extra=EXTRA, sanitize=False))
