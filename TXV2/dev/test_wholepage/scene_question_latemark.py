#!/usr/bin/env python3
"""R10-B exp 10: THE QUESTION'S OWN PAGE MARKER IS LATE (the screen's loop stands still from just before the question's page command, 1.6 to
4 s): the wait goes on, the marker is owed; GetYesOrNo catches up with it from inside its own wait. The pilot's Yes, pressed once
the box is really up, is this question's answer - and the boxes of the work that follows have their answers again."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
SCENES = r'''
    for (int form : { 197, 198 })
        for (uint32_t stallMs : { 1600u, 2200u, 3000u, 4000u })
            for (int oldTap = 0; oldTap < 2; ++oldTap)
            {
                more(); screen.realUart = true; screen.shoutForm = form; tapAt(5, "setup"); loopFor(900); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(60);
                screen.stall(nowUs + 200, stallMs, true);
                if (oldTap) tapAt(stallMs / 2, "OK");                        // (a tap on the page's own OK while the screen stands still: the page it still shows)
                tapAt(stallMs + 1500, "yes"); const uint64_t t0 = nowUs; const int saves0 = (int) saves.size();
                const bool answer = GetConfirmation((char *) "page RXOptionsView", (char *) "Save the travel extents?");
                const bool owedAfter = ScreenAnswerOwed, voidAfter = PageChangedUnderGet; const uint32_t v = GetValue((char *) "n3");
                say("M (1.11.%d, a stall of %.1f s%s): answered %s after %.2f s; closed %d (silent %d); still owed at the answer %d, boxes void %d; the box read behind it %u (5 on the page); OK obeyed %d, saves %d, stale presses %d\n",
                    form, stallMs / 1e3, oldTap ? ", a tap on the old page's OK" : "", answer ? "YES" : "No", (nowUs - t0) / 1e6, questionsClosed, questionsSilent, (int) owedAfter, (int) voidAfter, (unsigned) v, count(obeyed, 39), (int) saves.size() - saves0, stale);
                if (stallMs <= 3000) { CHECK(answer); CHECK(v == 5); }
                CHECK(count(obeyed, 39) == 0 && (int) saves.size() == saves0);   // (the old page's OK is never obeyed under, or behind, the question)
                loopFor(6000);
            }
'''
sys.exit(lib.build_run('question_latemark', SCENES, sanitize=False))
