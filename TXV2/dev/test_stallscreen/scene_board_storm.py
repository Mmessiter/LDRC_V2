#!/usr/bin/env python3
"""EXP B1 (review 10, reviewer A): the storm's second pass WITHOUT any restart of the screen - is a healthy screen ever declared restarted
(reason -3, or any), is a press ever obeyed on the wrong page, is the model changed? With more in it than scene 21 has: page commands of the
board's own from the main loop, the screen's bare words with no end at random moments, and longer stalls.

(The tenth review, reviewer A's experiment. Run twice here: with the screen having said a marker before the storm begins - and COLD, as a
trial of dev/test_stalepress's own storm begins: there the reviewer found 102 presses obeyed on the wrong page in 20000 trials, and Model
options' zeros saved once - "a screen that has never said a marker" lasted until the LAST page command's second marker was read, and a
late marker was given up meanwhile. Any of this board's numbers said back ends that state now: Nextion.h TakeScreenMark.
What is not counted against the model: a box asked for while the screen's own keyboard was up whose "which page?" was answered after the
keyboard had gone - the 0 said under the keyboard is taken. Known, and the screen's to cure: from 1.11.198 on a "which page?" right behind a
box's get says the page that get was ANSWERED on. The pretend screen counts it; every other trial here is such a screen, and has none.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
static long xFalseRestarts = 0, xWrong = 0, xChanged = 0, xOwedLeft = 0, xMarkLeft = 0, xDeadEnd = 0, xTrials = 0, xAutoPages = 0, xWords = 0, xObeyed = 0, xStale = 0, xSaves = 0, xOks = 0, xAsked3 = 0, xKnown7 = 0;
static void xStory(const char *why, int trial)
{
    static int told = 0; if (++told > 4) return;
    printf("---- trial %d: %s\n", trial, why);
    std::vector<std::string> all = story; all.insert(all.end(), screen.events.begin(), screen.events.end());
    std::sort(all.begin(), all.end(), [](const std::string &a, const std::string &b) { return atof(a.c_str()) < atof(b.c_str()); });
    for (auto &l : all) printf("      %s\n", l.c_str());
}
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 400;
  for (int coldPass = 0; coldPass < 2; ++coldPass)
  {
    const bool cold = coldPass != 0;
    xFalseRestarts = xWrong = xChanged = xOwedLeft = xMarkLeft = xDeadEnd = xTrials = xAutoPages = xWords = xObeyed = xStale = xSaves = xOks = xKnown7 = 0;
    static const char *const names[] = { "setup", "OK", "leave", "read", "readtext", "busywrite", "two", "bg", "pipe", "OK", "setup", "leave", "switch3", "row3", "OK", "Help", "name", "picture",
                                         "n3box", "n4box", "kbOK", "kbOK", "n3box", "OK" };
    static const char *const bare[] = { "UKRULES", "TIME=1731652000", "ldrcpipe=2", "LDRCAWAKE", "ldrcpipe=0" };
    for (int trial = 0; trial < N; ++trial)
    {
        more(); xs = 9000 + trial; ++xTrials;
        screen.realUart = true; screen.shoutForm = (trial & 1) ? 198 : 197; screen.upMs = 4000 + xr(15000000); stormLongest = (trial % 4 == 3) ? 12000 : 4000; stormSeed = 500 + trial;
        screen.latencyUs = 200 + xr(3) * xr(30000); screen.loadUs = xr(4) ? xr(320000) : 0; screen.tapInLoadFallsThrough = xr(2) != 0; screen.roundUs = xr(3) ? 0 : xr(80000);
        {
            Page &d = screen.pages0["RXOptionsView"]; d.boxes["c1"].val = 0; d.boxes["n3"].val = 0; d.boxes["t10"].txt = "3.80"; d.boxes["t12"].txt = "0"; d.boxes["n0"].val = 0; d.boxes["n2"].val = 0;
            d.boxes["c0"].val = 0; d.boxes["n1"].val = 16; d.boxes["c2"].val = 0; d.boxes["c3"].val = 0; d.boxes["n4"].val = 5;
        }
        if (!cold) { LeaveQuick(); loopFor(900); CHECK(ScreenSaysMarks); }   // (as after the board's own start: its front page's marker has come)
        stormTele = xr(2) != 0; flyHook = stormHook; gapWatch = true; lastRadioUs = nowUs;
        uint32_t at = 5;
        for (int k = 0; k < 30; ++k) { at += xr(4) ? 3 + xr(700) : 3 + xr(40); tapAt(at, names[xr(24)]); }
        // the screen's own bare words, at random moments (written by its loop's core when their time has come)
        for (int k = 0; k < 6; ++k) { const char *wd = bare[xr(5)]; screen.later.insert({ nowUs + (uint64_t) xr(at + 2000) * 1000, std::vector<uint8_t>(wd, wd + strlen(wd)) }); ++xWords; }
        const uint64_t stallsEnd = nowUs + (uint64_t) (at + 3000) * 1000, until = stallsEnd + 40000000ull;
        stormNextStall = nowUs + 200000 + stormRnd(1500000);
        uint64_t nextAuto = nowUs + 300000 + xr(3000000);
        while (nowUs < until)
        {
            if (nowUs < stallsEnd) stormStallDue(); else stormNextStall = UINT64_MAX;
            if (nowUs < stallsEnd && nowUs >= nextAuto) { nextAuto = nowUs + 500000 + xr(4000000); if (CurrentView != FRONTVIEW || xr(3) == 0) { GotoFrontView(); ++xAutoPages; tell("(the board goes to its front page by itself)"); } }
            loopFor(3);
        }
        stormNextStall = UINT64_MAX; flyHook = nullptr;
        int switchOks = 0; for (auto &wd : words) switchOks += wd == "SwitchesView1";
        xObeyed += (long) obeyed.size() + switchOks; xStale += stale; xSaves += (long) saves.size(); xOks += count(obeyed, 39) + switchOks;
        const bool falseRestart = restartsHandled || restartsFoundByAsking || ScreenRestartSeen;
        if (falseRestart) { ++xFalseRestarts; char b[120]; snprintf(b, sizeof b, "A RESTART 'FOUND' (handled %d, by asking %d, seen %d, reason %d) on a screen that never restarted", restartsHandled, restartsFoundByAsking, (int) ScreenRestartSeen, lastRestartReason); xStory(b, trial); }
        if (wrongPage) { ++xWrong; xStory("a press obeyed on the wrong page", trial); }
        if (screen.known7) ++xKnown7;
        if (frontBeliefs) { ++xChanged; xStory("the main loop found 'the screen shows the front page, this board believes another' - in a storm where no page is overtaken", trial); }
        if (screen.known7 && screen.shoutForm >= 198) { ++xChanged; xStory("a box read as the keyboard closed was taken - on a screen from 1.11.198 on, which says the keyboard's page for it", trial); }
        if ((!screen.known7 && (!sameAsAtFirst() || !switchesAsAtFirst())) || (int) saves.size() != count(obeyed, 39) + switchOks)
        {
            ++xChanged; char b[200]; snprintf(b, sizeof b, "THE MODEL CHANGED (model same %d, switches same %d), or saves %d != OKs %d + %d: motor switch %d, stop flying %.2f, trim step %u, six banks %d, timer %u", (int) sameAsAtFirst(), (int) switchesAsAtFirst(), (int) saves.size(), count(obeyed, 39), switchOks, UseMotorKill, StopFlyingVoltsPerCell, TrimMultiplier, SixBanks, TimerStartTime);
            xStory(b, trial);
        }
        if (ScreenAnswerOwed) { ++xOwedLeft; xStory("an answer still owed 40 s after the last stall", trial); }
        if (ScreenMarkAwaited) { ++xMarkLeft; xStory("a marker still awaited 40 s after the last stall", trial); }
        // the buttons at the end: a tap on the page showing must be obeyed
        {
            const size_t before = obeyed.size() + words.size();
            const std::string pg = screen.page;
            if (!screen.keyboardOver.empty()) { tapAt(5, "kbOK"); loopFor(600); }
            if (screen.page == "FrontView") { tapAt(5, "setup"); loopFor(900); if (obeyed.size() + words.size() == before) { ++xDeadEnd; xStory("the front page's button is dead at the end", trial); } }
            else if (screen.page == "RXOptionsView") { tapAt(5, "leave"); loopFor(900); if (obeyed.size() + words.size() == before) { ++xDeadEnd; xStory("Model options' button is dead at the end", trial); } }
        }
    }
    printf("B2 (%s): %ld trials: false restarts %ld, wrong page %ld, model changed %ld, owed left %ld, marker left %ld, buttons dead at the end %ld | obeyed %ld, not obeyed %ld, saves %ld = OKs %ld, the board's own page commands %ld, bare words %ld; trials with a box read as the keyboard closed (known) %ld\n",
           cold ? "the screen has not yet said a marker" : "the screen has said a marker", xTrials, xFalseRestarts, xWrong, xChanged, xOwedLeft, xMarkLeft, xDeadEnd, xObeyed, xStale, xSaves, xOks, xAutoPages, xWords, xKnown7);
    CHECK(xFalseRestarts == 0); CHECK(xWrong == 0); CHECK(xChanged == 0); CHECK(xOwedLeft == 0); CHECK(xMarkLeft == 0); CHECK(xDeadEnd == 0);
    CHECK(xTrials == N && xObeyed > N && xAutoPages > N / 2 && xKnown7 < N / 50);   // (the storm did what it is for; and the known thing stays rare)
  }
'''
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '1500'
    sys.exit(lib.build_run('b2', SCENES, EXTRA, args=['--x', nn], sanitize='--san' in sys.argv, timeout=3600))
