#!/usr/bin/env python3
"""WHICH OF THE SCREEN'S TWO CORES SPEAKS FIRST AFTER A HOLD OF BOTH (the thirteenth review, reviewer A's finding 4 and his experiment 2; 15 Nov 2026).

"A word with no end is UNSETTLED until the screen has answered 'sendme' behind its half second: what a stall had held back came out IN FRONT OF THAT
ANSWER" (Nextion.h) - that is an order between two cores, and nothing on the wire makes it so. scene_half_second only ever lets the loop wake 0 to
1.8 ms BEHIND the line's rest. Here the loop's wake is placed from 1.8 ms behind the rest to 60 ms BEFORE it: a field screen (1.11.197), its line cut
after the first piece (128 bytes), the rest - "play 0,7,0", which begins with p - and the loop held together for 600 to 1500 ms (a flash operation
holds both), a text box ("3.70") asked 300 to 800 ms behind the read of the first piece, by itself and behind a save's settling look.

 C1 THE SCREEN AS IT IS: its loop, at its first pass after its other core's watch has stood still a quarter second, says a line of its own - "LDRCLOG
    core 0 silent ..." (the screen's src/main.cpp lmLoopPageCheck, at the top of loop(): in front of its serial work, so in front of the look's
    answer). Another bare word with no end: the look is not clean, nothing is settled by it. Whatever the order: NEVER A WRONG TEXT.
 C2 THE SAME WITHOUT THAT LINE (no screen is so - it is here to show what holds C1, and that this scene can see the fault): the loop a tenth of a
    millisecond to 2.5 ms ahead, and the box is handed "lay 0,7,0p3.70".

The REAL GetText, RfGatherStart and readers of Nextion.h run over the pretend screen's port."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static std::string clean(const std::string &s) { std::string o; char b[8]; for (unsigned char c : s) { if (c >= 32 && c < 127) o += (char) c; else { snprintf(b, sizeof b, "<%02X>", c); o += b; } } return o; }
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
static uint32_t hHoldUs = 0; static long hWakeRelTailUs = 0; static std::string hLine; static bool hCore0Line = false;
static uint32_t hStallNow()   // the stall begins NOW; its line a fifth of a second in, the rest held hHoldUs; the loop wakes hWakeRelTailUs behind the rest (negative: before it)
{
    const uint64_t at = nowUs; const uint32_t shoutAfter = 200000 + xr(50000);
    const uint64_t tailAt = at + shoutAfter + 4 + hHoldUs;
    screen.busyUntil = std::max(screen.busyUntil, (uint64_t) ((long long) tailAt + hWakeRelTailUs)); screen.cmdHoldUntil = std::max(screen.cmdHoldUntil, screen.busyUntil);
    screen.lastShout = hLine; screen.shoutBegin(at + shoutAfter, hLine, hHoldUs); ++screen.shouts;
    if (hCore0Line && hHoldUs > 250000)
    {   // the real screen's loop, at its first pass after a hold in which its other core's watch stood still for more than a quarter second (the watch
        // beats every 50 ms, and its beat is older than the hold in either order): "core 0 silent ..." - in front of whatever the loop then answers
        char b[160]; snprintf(b, sizeof b, "LDRCLOG core 0 silent for %u ms at %lu ms: task 'ipc0' on it (the loop goes on)", (unsigned) (hHoldUs / 1000), (unsigned long) 381234 + hHoldUs / 1000);
        screen.later.insert({ screen.cmdHoldUntil, std::vector<uint8_t>(b, b + strlen(b)) });
    }
    return shoutAfter / 1000;
}
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 4;
    screen.shoutForm = 197;
    const std::string line = "LDRCLOG core 1 (the loop's) silent for 213 ms at 381234 ms: task 'IDLE1' on it, part '-', loop at 'sd', last command 45 ms ago: play 0,7,0";
    CHECK(line.size() > 129 && line[128] == 'p' && line.substr(128) == "play 0,7,0");
    for (int own = 1; own >= 0; --own)
    {
        long wrongAll = 0, rightAll = 0, lostAll = 0, cells = 0, wrongCells = 0; std::string example;
        hCore0Line = own != 0;
        for (int gather = 0; gather <= 1; ++gather)
          for (uint32_t holdMs : { 600u, 900u, 1500u })
            for (uint32_t askMs : { 300u, 560u, 800u })
              for (long d : { 1800L, 600L, 100L, 0L, -50L, -100L, -200L, -400L, -700L, -1000L, -1500L, -2500L, -5000L, -20000L, -60000L })
              {
                if (!own && (d > 0 || d < -2500)) continue;                    // (C2: the orders the fault lives in, to show it)
                long wrong = 0;
                for (int i = 0; i < N; ++i)
                {
                    more(); xs = 31000 + holdMs + askMs + i; screen.realUart = true; screen.shoutForm = 197; screen.latencyUs = 300 + xr(2000);
                    tapAt(5, "setup"); loopFor(900); screen.pages["RXOptionsView"].boxes["t10"].txt = "3.70";
                    hHoldUs = holdMs * 1000; hWakeRelTailUs = d; hLine = line;
                    const uint32_t headMs = hStallNow();
                    loopFor(headMs + 5); CHECK(WordOpenMs != 0);
                    loopFor(askMs - 3);
                    char t[24] = "x"; const uint32_t lost0 = BoxesLost; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false;
                    if (gather) { SendText((char *) "change", (char *) "Sending ..."); RfGatherStart(); }
                    GetText((char *) "t10", t, sizeof(t) - 1);
                    if (BoxesLost != lost0 || NextionTextMissed) ++lostAll;
                    else if (strcmp(t, "3.70")) { ++wrong; if (example.empty()) example = t; }
                    else ++rightAll;
                    loopFor(3500);
                }
                ++cells; wrongAll += wrong; wrongCells += wrong != 0;
                if (own) CHECK(wrong == 0);
              }
        say("%s: %ld cells (a box by itself and behind a save's look; the rest held 600 to 1500 ms; the loop from 1.8 ms behind the rest to 60 ms before it): RIGHT %ld, no answer %ld, WRONG %ld in %ld cells%s%s%s\n",
            own ? "C1. the screen as it is (its loop says \"core 0 silent\" first)" : "C2. without the loop's own line", cells, rightAll, lostAll, wrongAll, wrongCells, wrongAll ? " - e.g. \"" : "", wrongAll ? clean(example).c_str() : "", wrongAll ? "\"" : "");
        if (own) CHECK(wrongAll == 0 && rightAll > 0);
        else CHECK(wrongAll > 0 && example == "lay 0,7,0p3.70");                 // (the fault is there to be seen: what holds C1 is the screen's own line)
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('core_order', SCENES, EXTRA, sanitize=False, timeout=3000))
