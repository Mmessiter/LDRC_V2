#!/usr/bin/env python3
"""R10-B exp 4: TWO QUESTIONS IN ONE BUTTON'S WORK, one "Yes" tap at a random moment, the screen's loop standing still now and then
(0.2 to 5 s, begun at random moments; the real port, a screen of 1.11.197 and one of 1.11.198). What must hold: a Yes is the answer
of the question whose box the screen was SHOWING when the finger came down - never of the other one; and never two answers from one tap."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static uint32_t rsQ = 20261115u; static uint32_t rndQ(uint32_t k) { rsQ = rsQ * 1664525u + 1013904223u; return k ? (rsQ >> 8) % k : 0; }
static uint64_t nextStallQ = UINT64_MAX; static uint32_t longestQ = 5000;
static void stallQ()
{
    if (nowUs < nextStallQ || nowUs < screen.busyUntil) return;
    const uint32_t ms = 200 + rndQ(longestQ - 200);
    nextStallQ = nowUs + (uint64_t) ms * 1000 + 200000 + rndQ(2500000);
    screen.stall(nowUs, ms, true, rndQ(3) ? rndQ(2500) : 0, rndQ(100) < 15 ? 1500 + rndQ(4500) : 0, rndQ(8) == 0);
}
'''
SCENES = r'''
    int wrong = 0, both = 0, a1 = 0, a2 = 0, none = 0, lostYes = 0, trials = 0, closedTot = 0;
    for (int form : { 197, 198 })
        for (int i = 0; i < 700; ++i)
        {
            more(); screen.realUart = true; screen.shoutForm = form; screen.latencyUs = 300 + rndQ(3000); screen.loadUs = 30000 + rndQ(250000);
            tapAt(5, "setup"); loopFor(900); BoundFlag = ModelMatched = true; GetValue((char *) "n4"); loopFor(60);
            const uint64_t t0 = nowUs; const uint32_t tapMs = 100 + rndQ(9000);
            tapAt(tapMs, "yes"); if (rndQ(3) == 0) tapAt(tapMs + 150 + rndQ(300), "yes");            // (sometimes a second tap, a moment later)
            if (rndQ(2)) tapAt(rndQ(6000), "OK");                                                     // (and a tap on the page's own OK, whenever that page shows)
            nextStallQ = nowUs + rndQ(1500000); sendDataHook = stallQ; flyHook = stallQ;
            boxSpins = 400000 - 6000;                                                                  // (a box nobody answers is given up by the test after some 3 s)
            const size_t log0 = screen.log.size();
            const bool q1 = GetConfirmation((char *) "page RXOptionsView", (char *) "Question ONE?");
            const size_t logMid = screen.log.size(); const uint64_t tMid = nowUs;
            boxSpins = 400000 - 6000;
            const bool q2 = GetConfirmation((char *) "page RXOptionsView", (char *) "Question TWO?");
            sendDataHook = nullptr; flyHook = nullptr; nextStallQ = UINT64_MAX;
            // which box was the screen showing when a finger came down on "yes"? the screen's own log: page loads and taps, in order
            int popups = 0, tapsOn1 = 0, tapsOn2 = 0;
            for (size_t k = log0; k < screen.log.size(); ++k)
            {
                const std::string &l = screen.log[k];
                if (l == "page PopupView") ++popups;
                else if (l == "tap yes on PopupView") { if (popups == 1) ++tapsOn1; else if (popups == 2) ++tapsOn2; }
            }
            ++trials; closedTot += questionsClosed;
            if (q1 && q2 && tapsOn1 + tapsOn2 < 2) ++both;
            if ((q1 && !tapsOn1) || (q2 && !tapsOn2)) { ++wrong; if (show && wrong <= 5) { printf("   trial %d (1.11.%d): q1 %d q2 %d, yes taps on box one %d, on box two %d, closed %d\n", i, form, (int) q1, (int) q2, tapsOn1, tapsOn2, questionsClosed); for (auto &s : story) printf("      %s\n", s.c_str()); for (auto &e : screen.events) printf("      %s\n", e.c_str()); } }
            if (q1) ++a1; if (q2) ++a2; if (!q1 && !q2) ++none;
            if ((tapsOn1 && !q1) || (tapsOn2 && !q2)) ++lostYes;
            loopFor(3000);
            if (CurrentView != RXSETUPVIEW1 && CurrentView != FRONTVIEW) ++wrong;
        }
    say("Q. %d trials: question one answered Yes %d, question two %d, neither %d; a Yes with NO finger on that question's box: %d; two answers from one tap: %d;\n   a Yes pressed on a box and not taken (closed by the board, or dropped): %d; questions closed by the board: %d\n", trials, a1, a2, none, wrong, both, lostYes, closedTot);
    CHECK(wrong == 0); CHECK(both == 0);
'''
sys.exit(lib.build_run('twoquestions', SCENES, extra=EXTRA, sanitize=False))
