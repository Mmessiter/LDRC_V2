#!/usr/bin/env python3
"""E1: the motor switch's box goes back with a bare "page FrontView" and this board goes on believing the page it was on.
On the Models page its twice-a-second look at the lists is then answered by the FRONT page (0 for a box it has not got)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
SCENES = r'''
    // (a) the Models page, model 4 in use; the link is lost with the motor switch on; the pilot switches off, presses OK
    more(); BoundFlag = ModelMatched = true; tapAt(5, "models"); loopForModels(2000);
    CHECK(CurrentView == MODELSVIEW && ModelNumber == 4 && screen.page == "ModelsView" && modelsRead.empty());
    motorOffAtUs = nowUs + 2000000; tapAt(3500, "yes"); LinkLostNow();
    say("E1a. after the motor box: the screen shows %s, this board believes view %u (MODELSVIEW is %u); model %u\n", screen.page.c_str(), (unsigned) CurrentView, (unsigned) MODELSVIEW, (unsigned) ModelNumber);
    { const int off0 = screen.offPageAnswers; loopForModels(3000);
      say("E1a. three seconds on: model %u, models read from the card:", (unsigned) ModelNumber); for (int x : modelsRead) say(" %d", x);
      say("; answers given for boxes the showing page has not got: %d; restart noted %d; boxes lost told %d\n", screen.offPageAnswers - off0, (int) ScreenRestartSeen, boxesLostTold); }
    CHECK(ModelNumber == 4 && modelsRead.empty());   // (what should hold: no model loaded by itself)
    // (b) the Dual-rates page: its look at the eight channel boxes, every 600 ms
    more(); BoundFlag = ModelMatched = true; SendCommand((char *) "page DualRatesView"); CurrentView = DUALRATESVIEW; loopFor(600);
    motorOffAtUs = nowUs + 2000000; tapAt(3500, "yes"); LinkLostNow();
    { static uint32_t pollMs = 500000; for (int i = 0; i < 4; ++i) { pollMs += 700; loopFor(700); CheckDualRatesScreen(pollMs); }
      say("E1b. Dual rates after the motor box: the screen shows %s, view %u; channels", screen.page.c_str(), (unsigned) CurrentView); for (int i = 0; i < 8; ++i) say(" %u", (unsigned) DualRateChannels[i]); say(" (were 1 2 4 0 0 0 0 0)\n"); }
    CHECK(DualRateChannels[0] == 1 && DualRateChannels[1] == 2 && DualRateChannels[2] == 4);
    // (c) (the eleventh review, reviewer A's low 5) the Dual-rates page's look with the page's number NOT YET KNOWN and the screen on the FRONT page
    //     (the opening work overtaken by it), whose own boxes of those names hold other numbers: the number is learned WITH the first answer - and
    //     is looked at AGAIN behind it. Nothing is taken
    more(); BoundFlag = ModelMatched = true; SendCommand((char *) "page DualRatesView"); CurrentView = DUALRATESVIEW; loopFor(600);
    { uint8_t was[8]; memcpy(was, DualRateChannels, 8);
      for (const char *b : { "n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7" }) screen.pages["FrontView"].boxes[b] = { false, 9, "" };
      screen.page = "FrontView"; ScreenPageId = 0xFF; ScreenPageIdDue = true;
      static uint32_t pollMs2 = 900000; pollMs2 += 700; CheckDualRatesScreen(pollMs2);
      say("E1c. Dual rates' look, the page's number not known and the screen on the front page (its boxes of those names hold 9): the page's number learned: %u; channels", (unsigned) ScreenPageId);
      for (int i = 0; i < 8; ++i) say(" %u", (unsigned) DualRateChannels[i]); say("\n");
      CHECK(ScreenPageId == 13);                                                 // (the scene is the one meant: the front page's number was learned with the answer)
      CHECK(!memcmp(was, DualRateChannels, 8)); }
    // (d) (the twelfth review, both reviewers: no test held it) ... and while a page's marker is still awaited the page is not known to be up:
    //     NOTHING is asked, nothing counted as lost, nothing taken (the Models page's twin: scene_small_rules M2). The page's own boxes hold other
    //     channels here - asked, they would be taken
    more(); BoundFlag = ModelMatched = true; SendCommand((char *) "page DualRatesView"); CurrentView = DUALRATESVIEW; loopFor(600);
    { uint8_t was[8]; memcpy(was, DualRateChannels, 8);
      for (const char *b : { "n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7" }) screen.pages["DualRatesView"].boxes[b] = { false, 9, "" };
      const int g0 = screen.gets; const uint32_t lost0 = BoxesLost;
      ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | ScreenMarkCount; ScreenMarkAskedMs = millis();
      static uint32_t pollMs3 = 1300000; pollMs3 += 700; CheckDualRatesScreen(pollMs3); ScreenMarkAwaited = 0;
      say("E1d. Dual rates' look while a page's marker is awaited: boxes asked %d, counted as lost %u; channels", screen.gets - g0, (unsigned) (BoxesLost - lost0));
      for (int i = 0; i < 8; ++i) say(" %u", (unsigned) DualRateChannels[i]); say("\n");
      CHECK(screen.gets == g0 && BoxesLost == lost0 && !memcmp(was, DualRateChannels, 8));
      // ... and with no marker awaited the same look takes them (the scene is the one meant)
      pollMs3 += 700; CheckDualRatesScreen(pollMs3);
      CHECK(screen.gets > g0 && DualRateChannels[0] == 9); }
'''
import sys
sys.exit(lib.build_run('motorbox_view', SCENES))
