#!/usr/bin/env python3
"""R10-B exp 8: WHAT THE LOG SAYS after a button's work lost a box (LogFiles.h NoteBoxesLost, the REAL one): it names BoxLostName - which
Nextion.h BoxWasLost writes over at EVERY box with no answer, the ones not asked for after the first among them - and says "what the
page held from there on was NOT taken". Model options' OK, the motor channel's box (n1, the eighth of eleven) unanswered."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
SCENES = r'''
    more(); tapAt(5, "setup"); loopFor(800);
    // (an earlier button's work lost three boxes of its own: they are no part of what this one's line counts)
    screen.mute.insert("n3"); tapAt(5, "OK"); loopFor(4000); screen.mute.clear(); logLines.clear(); const uint32_t lostEarlier = BoxesLost; tapAt(5, "setup"); loopFor(800);
    { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["n1"].val = 7; }   // (typed: trim step 9 - the second box read; motor channel 7 - the eighth)
    screen.mute.insert("n1"); tapAt(5, "OK"); loopFor(4000);
    real::NoteBoxesLost();                                                                          // (what CheckForNextionButtonPress calls at the end of that work)
    say("L1. Model options' OK, the motor channel's box (n1) unanswered: trim step %u (typed 9, it was 5: nothing of the page is taken); the name kept: '%s'; the log:\n", (unsigned) TrimMultiplier, BoxLostName);
    for (auto &l : logLines) say("    [%s]\n", l.c_str());
    CHECK(TrimMultiplier == 5 && boxesLostTold == 2 && lostEarlier >= 2);
    CHECK(!strcmp(BoxLostName, "n1"));      // what should hold: the line names the box that had no answer - the first, where "from there on" begins
    { char want[40]; snprintf(want, sizeof want, "(%lu such from there on)", (unsigned long) (BoxesLost - lostEarlier));
      // (the twelfth review: the line said "No answer from the screen for box X" also of boxes that were never ASKED - it says what is known now)
      bool counted = false; for (auto &l : logLines) counted |= l.find("Box 'n1' has no answer from the screen, or could not be asked") == 0 && l.find(want) != std::string::npos && l.find("No answer from the screen for") == std::string::npos;
      CHECK(counted && BoxesLost - lostEarlier >= 2 && BoxesLost - lostEarlier <= 11); }   // ... and counts THIS work's unanswered boxes - not every one since the power came on
'''
sys.exit(lib.build_run('logline', SCENES, sanitize=False))
