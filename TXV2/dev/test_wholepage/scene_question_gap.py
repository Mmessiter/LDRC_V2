#!/usr/bin/env python3
"""R10-B exp 11: A PAGE PUT UP IN THE 20 ms BETWEEN A QUESTION'S OWN PAGE COMMAND AND THE START OF ITS WAIT. GetYesOrNo takes "the page
command that put this question up" as the last one sent WHEN ITS WAIT BEGINS - but MsgBox / GetConfirmation send the box's page command
first, and that command's own 20 ms wait flies the model and looks at the power button (ModalWaits is still 0 there): the front page
goes up over the box, GetYesOrNo then takes THE FRONT PAGE'S command for its own - and waits, unseen, for an answer nobody can give.

(The tenth review's experiment, as reviewer B wrote it. THE CURE: the question knows the count its own page command WILL have before
it sends it (Utilities.h NextPageMark); a page command sent behind it has overtaken the question: closed at once, "No", and no way
back sent over the page that came.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
SCENES = r'''
    more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(60);
    waitsSeen = 0; powerAtWait = 1; flyHook = PowerButtonInWait;                 // (the power button, pressed while connected, seen in the first wait: the box's own page command's)
    boxSpins = 400000 - 40000;                                                   // (the test gives a box nobody answers up after some 20 s)
    { const uint64_t t0 = nowUs; gapWatch = true; lastRadioUs = nowUs;
      MsgBox((char *) "page RXOptionsView", (char *) "Not saved: each cell's voltages must rise."); flyHook = nullptr;
      say("K1. the front page put up in the wait of the box's own page command: the box waited %.1f s (given up by the test: %s); closed by the board %d; while it waited the screen showed %s; page said %u times\n",
          (nowUs - t0) / 1e6, Confirmed[0] == 'T' ? "yes" : "no", questionsClosed, screen.log.size() >= 2 ? screen.log[screen.log.size() - 2].c_str() : "?", (unsigned) ScreenPageSaidCount);
      for (auto &l : screen.log) say("   [%s]", l.c_str()); say("\n");
      CHECK(nowUs - t0 < 5000000);   // what should hold: a question that is not on the screen is closed at once (the switches are not read while it waits)
      CHECK(questionsClosed == 1 && QuestionOvertaken && Confirmed[0] == 'N');
      loopFor(1500);
      say("    ... 1.5 s on: the screen shows %s, this board believes view %u (the front page is %u)\n", screen.page.c_str(), (unsigned) CurrentView, (unsigned) FRONTVIEW);
      CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW);   // ... and its way back is not sent over the page that came
    }
'''
sys.exit(lib.build_run('question_gap', SCENES, sanitize=False))
