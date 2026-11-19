#!/usr/bin/env python3
"""THE SCREEN SHOWS THE FRONT PAGE AND THIS BOARD BELIEVES ANOTHER PAGE (the author's, 15 Nov 2026, after the tenth review; released code
had it). The front page is put up from INSIDE a wait that flies the model - the model connects, the power button while connected, the
motor box - and that wait may be the one behind another page's own page command: the pilot touched a button in the moment his model
connected. The opening work went on: its values were written onto the front page, and it set the page this board believes to its own.
The screen showed a front page nobody kept up to date. Now the main loop sees it by the page's number (main.cpp ScreenKeepUp, Nextion.h
SCREEN_FRONT_PAGE) and draws the front page afresh.
  O1  Model options opened, the front page put up in the wait behind its page command
  O2  a page the screen's card has not got, asked for from the front page: the screen stays where it was, and says so
  O3  nothing of the kind in a page opened and left in the ordinary way, in a box answered, under a keyboard, in a screen that stalls"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
SCENES = r'''
    // O1
    more(); loopFor(300); BoundFlag = ModelMatched = true;
    waitsSeen = 0; powerAtWait = 1; flyHook = PowerButtonInWait;        // (the front page from inside the first wait that flies the model: the page command's own)
    tapAt(5, "setup"); loopFor(900); flyHook = nullptr;
    say("O1. 'setup' tapped, and the front page put up again from inside the wait behind \"page RXOptionsView\": the screen shows %s; this board believes view %u (front %u);\n    found by the main loop %d time(s); the front page's own text written last: '%s'; reasons logged %d\n",
        screen.page.c_str(), (unsigned) CurrentView, (unsigned) FRONTVIEW, frontBeliefs, screen.keptTxt["FrontView.t0"].c_str(), (int) frontReasons.size());
    CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW && frontBeliefs == 1);
    CHECK(frontReasons.size() == 1 && frontReasons[0].find("the screen showed the front page under another page's work") == 0);
    CHECK(screen.keptTxt["FrontView.t0"] == "Model" && !ScreenMarkAwaited && !ScreenAnswerOwed && restartsHandled == 0);
    tapAt(5, "setup"); loopFor(900);                                     // ... and the button he presses next opens its page
    CHECK(screen.page == "RXOptionsView" && CurrentView == RXSETUPVIEW1 && frontBeliefs == 1 && GetValue((char *) "n3") == 5);
    // O2. a page the card has not got: the screen stays on the front page and says its number behind the markers
    more(); loopFor(300);
    SendCommand((char *) "page NoSuchView"); CurrentView = RXSETUPVIEW1; SendValue((char *) "n3", 5);     // (an opening work, as it goes on)
    loopFor(900);
    say("O2. a page the card has not got, asked for from the front page: the screen shows %s; this board believes view %u; found %d time(s)\n", screen.page.c_str(), (unsigned) CurrentView, frontBeliefs);
    CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW && frontBeliefs == 1 && frontReasons.size() == 1);
    // O3. the ordinary: open, read, a question answered, a keyboard up and down, leave; and the same with the screen standing still for a second in the middle
    for (int stall = 0; stall < 2; ++stall)
    {
        more(); screen.realUart = true; loopFor(300);
        tapAt(5, "setup"); loopFor(900);
        CHECK(screen.page == "RXOptionsView" && CurrentView == RXSETUPVIEW1);
        if (stall) { screen.stall(nowUs + 100, 1000, true); loopFor(2500); }      // (the screen's loop stands still for a second, and says so)
        tapAt(1500, "yes"); CHECK(GetConfirmation((char *) "page RXOptionsView", (char *) "Sure?")); loopFor(500);
        tapAt(5, "n3box"); loopFor(600); tapAt(5, "kbOK"); loopFor(600);
        tapAt(5, "OK"); loopFor(3000);
        say("O3 (%s). opened, a question, a keyboard, OK: the screen shows %s, view %u; found %d time(s); reasons %d\n", stall ? "a stall of a second" : "no stall", screen.page.c_str(), (unsigned) CurrentView, frontBeliefs, (int) frontReasons.size());
        CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW && frontBeliefs == 0 && frontReasons.empty() && saves.size() == 1);
    }
'''
sys.exit(lib.build_run('front_page', SCENES, sanitize=False))
