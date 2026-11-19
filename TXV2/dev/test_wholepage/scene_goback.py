#!/usr/bin/env python3
"""E6: a question is closed as "No" because another page was put up over it from inside its wait - here the model CONNECTS while
"No model is connected. Switch it on, then press Save." waits (main.cpp BindNow: the front page by itself). The question's own
way back is still sent afterwards: the screen ends on the page the question came from, this board believes the front page."""
import sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static uint64_t connectAtUs = 0; static bool connected = false;
static void ModelConnects() { if (connected || nowUs < connectAtUs) return; connected = true; GotoFrontView(); }   // (main.cpp BindNow, not on the front page: LogFrontPageReason and GotoFrontView)
'''
SCENES = r'''
    more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true;   // (the radio is being tried: the wait sends packets)
    connectAtUs = nowUs + 2500000; connected = false; sendDataHook = ModelConnects;
    MsgBox((char *) "page RXOptionsView", (char *) "No model is connected.\r\nSwitch it on, then press Save."); sendDataHook = nullptr; loopFor(500);
    say("E6. the model connects under a waiting box: the box closed %d time(s) (another page over it: %d); the screen now shows %s, this board believes view %u (the front page is %u, the page of the box %u)\n",
        questionsClosed, questionsOvertaken, screen.page.c_str(), (unsigned) CurrentView, (unsigned) FRONTVIEW, (unsigned) RXSETUPVIEW1);
    CHECK(questionsOvertaken == 1);
    CHECK((screen.page == "FrontView") == (CurrentView == FRONTVIEW));          // (what should hold: the screen shows the page this board believes)
'''
sys.exit(lib.build_run('goback', SCENES, extra=EXTRA, sanitize=False))
