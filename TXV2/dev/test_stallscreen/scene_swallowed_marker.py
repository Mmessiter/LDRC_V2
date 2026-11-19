#!/usr/bin/env python3
"""EXP C1 (review 10, reviewer A): A PAGE THAT TAKES A FIFTH OF A SECOND TO COME UP, ON A SCREEN UP TO 1.11.197.
Its other core says "the loop is silent ... last command 2xx ms ago: page <name>" - in pieces. The page's load ends INSIDE that line: the loop's
core writes the page command's second marker and the page's number BETWEEN two pieces of the line. The transmitter is back in its main loop by
then (it has nothing more to send), and the main loop's reader (GetTextIn) takes the whole lump - the line's first piece, the two replies, the
line's rest - as ONE bare word: TrailingReplies looks for reply frames at the END of what was read, and these stand in the MIDDLE.
What is counted: the second marker never noted (the page "not known to be up"), a tap made on the new page 300 ms after it came up, and when the
page's buttons work again.

(The tenth review, reviewer A's experiment: 22 of 4000 such loads lost the marker on a screen of 1.11.197 - the new page's buttons deaf for a second
and a half, a tap let go without a word. THE CURE: Nextion.h TrailingReplies finds a marker's frame wherever it stands in what was read.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static std::string clean(const std::string &s) { std::string o; char b[8]; for (unsigned char c : s) { if (c >= 32 && c < 127) o += (char) c; else { snprintf(b, sizeof b, "<%02X>", c); o += b; } } return o; }
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 2000;
    for (int form : { 197, 198 })
    {
        long lost = 0, tapsDead = 0, tapsSilent = 0, tapsObeyedLater = 0, shouts = 0, cuts = 0, loads = 0, logJunk = 0; uint64_t deadUsMax = 0, deadUsSum = 0; int shown = 0;
        for (int trial = 0; trial < N; ++trial)
        {
            more(); xs = 31000 + trial; screen.realUart = true; screen.shoutForm = form; screen.upMs = 4000 + xr(15000000);
            screen.latencyUs = 200 + xr(4000); screen.loadUs = 60000;
            tapAt(5, "setup"); loopFor(900); CHECK(ScreenSaysMarks && ScreenPageId == 9 && screen.page == "RXOptionsView");   // the screen has said its markers: one that is late from here on is OWED
            // the next page takes 200 to 252 ms to come up (a page with a picture); the watch on the other core speaks 200 to 250 ms into the silence
            screen.costSeed = 1000 + trial * 7; screen.loadUs = 200000 + xr(52000); ++loads;
            const int stale0 = stale; const unsigned let0 = LoadPrintsLetGo; const size_t ob0 = obeyed.size(), log0 = screenLogLines.size(); const int nm0 = noMarks;
            LeaveQuick();                                                            // "page FrontView" - and back to the main loop (the board has nothing more to say)
            const uint64_t sent = nowUs;
            loopFor(280);                                                            // the page is up by now
            shouts += screen.realShouts; cuts += screen.shoutCuts > 0;
            const bool markerLost = ScreenMarkAwaited != 0;
            if (!markerLost) continue;
            ++lost;
            for (size_t i = log0; i < screenLogLines.size(); ++i) { bool junk = false; for (unsigned char c : screenLogLines[i]) if (c < 32 || c >= 127) junk = true; if (junk) ++logJunk; }
            if (++shown <= 2)
            {
                printf("   [1.11.%d] trial %d: the page took %u us to come up; 280 ms after the page command its second marker is still awaited (%08lx); the page's number: %u\n      what the main loop took for ONE line: %s\n",
                       form, trial, screen.loadUs, (unsigned long) ScreenMarkAwaited, (unsigned) ScreenPageId, log0 < screenLogLines.size() ? clean(screenLogLines[log0]).c_str() : "(none)");
            }
            // the pilot taps a button of the page he now sees
            tapAt(20, "setup"); loopFor(200);
            if (obeyed.size() == ob0) { ++tapsDead; if (stale == stale0 && LoadPrintsLetGo == let0 + 1) ++tapsSilent; }
            // ... and when do the buttons work again?
            uint64_t worksAt = 0;
            for (int k = 0; k < 400 && !worksAt; ++k) { loopFor(10); if (!ScreenMarkAwaited) worksAt = nowUs; }
            if (worksAt) { const uint64_t d = worksAt - sent; deadUsSum += d; if (d > deadUsMax) deadUsMax = d; }
            tapAt(20, "setup"); loopFor(900); if (obeyed.size() == ob0 + 1 && screen.page == "RXOptionsView") ++tapsObeyedLater;
            if (shown <= 2) printf("      a tap on the new page 300 ms after it came up: obeyed %d, said in the log %d, let go without a word %u; 'the marker never came' %d; the buttons work again %.0f ms after the page command; a tap then: obeyed %d\n",
                                   (int) (obeyed.size() > ob0 + (worksAt ? 1 : 0)), stale - stale0, (unsigned) (LoadPrintsLetGo - let0), noMarks - nm0, worksAt ? (double) (worksAt - sent) / 1000.0 : -1.0, (int) (obeyed.size() == ob0 + 1));
        }
        printf("C1 [a screen of 1.11.%d]: %ld page loads of 200 to 252 ms; lines said %ld (the loop's own writes inside one: %ld); THE PAGE'S SECOND MARKER LOST %ld times (%.1f %% of these loads)\n", form, loads, shouts, cuts, lost, 100.0 * lost / loads);
        if (lost) printf("      a tap on the new page meanwhile: not obeyed %ld of %ld, of them WITHOUT A WORD %ld; the buttons dead for %.0f ms on average, %.0f ms at most; a tap after that obeyed %ld of %ld; log lines with bytes of the replies in them %ld\n",
                         tapsDead, lost, tapsSilent, (double) deadUsSum / lost / 1000.0, (double) deadUsMax / 1000.0, tapsObeyedLater, lost, logJunk);
        CHECK(lost == 0 && loads == N);                                              // (both screens: no marker is lost inside the line)
        if (form == 197) CHECK(cuts > 0);                                            // (... and the scene is the one meant: the loop's own writes did go out inside a line)
    }
'''
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '2000'
    sys.exit(lib.build_run('c1', SCENES, EXTRA, args=['--x', nn], sanitize='--san' in sys.argv, timeout=3600))
