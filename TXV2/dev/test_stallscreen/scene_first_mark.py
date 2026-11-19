#!/usr/bin/env python3
"""EXP B4 (the tenth review, reviewer A): the first page command of a trial, nothing else going on: its second marker not read in 900 ms - 3 times in
20000, the marker swallowed inside the screen's line (scene_swallowed_marker). What must hold: after the first page command the screen is known
to say markers, every time."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static std::string clean(const std::string &s) { std::string o; char b[8]; for (unsigned char c : s) { if (c >= 32 && c < 127) o += (char) c; else { snprintf(b, sizeof b, "<%02X>", c); o += b; } } return o; }
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 400; int shown = 0; long bad = 0;
    for (int trial = 0; trial < N; ++trial)
    {
        more(); xs = 9000 + trial;
        screen.realUart = true; screen.shoutForm = (trial & 1) ? 198 : 197; screen.upMs = 4000 + xr(15000000); stormLongest = (trial % 4 == 3) ? 12000 : 4000; stormSeed = 500 + trial;
        screen.latencyUs = 200 + xr(3) * xr(30000); screen.loadUs = xr(4) ? xr(320000) : 0; screen.tapInLoadFallsThrough = xr(2) != 0; screen.roundUs = xr(3) ? 0 : xr(80000);
        LeaveQuick(); loopFor(900);
        if (!ScreenSaysMarks)
        {
            ++bad;
            if (++shown <= 3)
            {
                printf("---- trial %d: form %d, latency %u us, load %u us, round %u us; marker awaited %08lx, old page %d, misses %d, owed %d, word open %lu ms ago, page id %u, shouts %d (pieces %d, cuts %d)\n      the line: %s\n", trial, screen.shoutForm, screen.latencyUs, screen.loadUs, screen.roundUs,
                       (unsigned long) ScreenMarkAwaited, (int) ScreenMarkOldPage, (int) ScreenMarkMisses, (int) ScreenAnswerOwed, WordOpenMs ? (unsigned long) (millis() - WordOpenMs) : 0ul, (unsigned) ScreenPageId, screen.realShouts, screen.shoutPieces, screen.shoutCuts, clean(screen.lastShout).c_str());
                for (auto &g : ghosts) printf("      ghost: %s\n", clean(g).c_str());
                for (auto &l : logLines) printf("      log: %s\n", clean(l).c_str());
                for (auto &l : screenLogLines) printf("      screen line: %s\n", clean(l).c_str());
                for (auto &wd : words) printf("      word: %s\n", clean(wd).c_str());
                std::vector<std::string> all = story; all.insert(all.end(), screen.events.begin(), screen.events.end());
                std::sort(all.begin(), all.end(), [](const std::string &a, const std::string &b) { return atof(a.c_str()) < atof(b.c_str()); });
                for (auto &l : all) printf("      %s\n", clean(l).c_str());
                loopFor(3000);
                printf("      three seconds on: says marks %d, marker awaited %08lx, 'never came' %d, owed %d, caught up %d, page id %u\n", (int) ScreenSaysMarks, (unsigned long) ScreenMarkAwaited, noMarks, (int) ScreenAnswerOwed, owedCaughtUp, (unsigned) ScreenPageId);
            }
        }
    }
    printf("B4: %d trials, the first page command's second marker not read in 900 ms: %ld\n", N, bad);
    CHECK(bad == 0);
'''
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '3000'
    sys.exit(lib.build_run('b4', SCENES, EXTRA, args=['--x', nn], sanitize=False, timeout=3600))
