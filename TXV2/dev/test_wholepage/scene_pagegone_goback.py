#!/usr/bin/env python3
"""R10-B exp 6: THE PAGE IS TAKEN AWAY UNDER A SAVE (the power button's way to the front page, from inside the save's wait - or the motor
box, which now ends on the front page as this board's page): the save's boxes have no answer, and the save says so with a box
(RfFieldsMissed -> MsgBox) - whose WAY BACK puts the save's own page up again. The screen then shows that page; this board believes
the front page. (The ninth review's cure covers a question another page came OVER; this is a box put up AFTER the page was changed.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
EXTRA = m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)') + r'''
static int boxUpsNow() { int k = 0; for (auto &l : screen.log) k += l == "page PopupView"; return k; }   // (how often a question's page was put up, by the screen's own account)
#define boxUps boxUpsNow()
'''
SCENES = r'''
    more(); for (int i = 0; i < 9; ++i) { char n[8]; snprintf(n, sizeof n, "pid%d", i); screen.pages["RXOptionsView"].boxes[n] = { false, 40 + i, "" }; }
    tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; powerAtWait = 1; flyHook = PowerButtonInWait;
    { uint32_t pid[9]; tapAt(3000, "yes"); const int boxUps0 = boxUps;
      SendText((char *) "change", (char *) "Sending edited PIDs ..."); DelayWithDog(100); RfGatherStart();          // RF_PIDs.h SendEditedPIDs
      for (int i = 0; i < 9; ++i) { char n[8]; snprintf(n, sizeof n, "pid%d", i); pid[i] = GetValue(n); } flyHook = nullptr;
      const bool refused = RfFieldsMissed("page RXOptionsView");
      loopFor(1500);
      say("G1. a save; the power button in its first wait (the front page from inside it); the save's boxes unanswered: refused %d (the box 'did not answer' came and was answered);\n    the screen now shows %s, this board believes view %u (the front page is %u, the save's page %u); the page's number this board holds: %u\n",
          (int) refused, screen.page.c_str(), (unsigned) CurrentView, (unsigned) FRONTVIEW, (unsigned) RXSETUPVIEW1, (unsigned) ScreenPageId);
      CHECK(refused && pid[0] == 65535);
      CHECK((screen.page == "FrontView") == (CurrentView == FRONTVIEW));            // what should hold: the screen shows the page this board believes
      CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW && boxUps == boxUps0); }   // ... the front page; and no box was put up over it
    // ... AND THE NEXT BUTTON'S WORK IS ITS OWN: "this board left the page under the work" is forgotten at the main loop's next look for a press. A save
    // on the page again, one box unanswered and no page taken away: the box "The screen did not answer ..." DOES come, and is answered
    tapAt(5, "setup"); loopFor(800);
    { screen.mute.insert("pid3"); const int boxUps1 = boxUps; uint32_t pid[9]; tapAt(4000, "yes");
      RfGatherStart(); for (int i = 0; i < 9; ++i) { char n[8]; snprintf(n, sizeof n, "pid%d", i); pid[i] = GetValue(n); }
      const bool refused = RfFieldsMissed("page RXOptionsView"); screen.mute.clear(); loopFor(1000);
      say("G2. the next save, a box unanswered and the page still there: refused %d, boxes put up %d; the screen shows %s\n", (int) refused, boxUps - boxUps1, screen.page.c_str());
      CHECK(refused && pid[3] == 65535 && boxUps == boxUps1 + 1 && screen.page == "RXOptionsView" && CurrentView == RXSETUPVIEW1); }
'''
sys.exit(lib.build_run('pagegone_goback', SCENES, extra=EXTRA, sanitize=False))
