#!/usr/bin/env python3
"""THE REAL SCREEN'S LINE, AS ITS PORT REALLY CARRIES IT, UNDER THE REAL READERS - storms (the ninth review, reviewer A).
A stall of the screen's loop is planted while boxes are being read; its other core says so 185 to 250 ms into the silence - in
pieces (a screen up to 1.11.197) or in one piece with a newline (from 1.11.198); the loop wakes at a random moment, often inside
that line, and answers. Counted: boxes handed back with a WRONG value - not "no answer": a wrong one.
  1. a save as the Rotorflight pages do it: twelve text boxes     2. six number boxes     3. Model options' OK
  4. the Models page, its two lists asked for twice a second, the pilot turning the list now and then
  5. a text box asked while its page is still coming up (a load of a fifth of a second: the line ends "... page <name>")
     - 7 and 19 wrong texts in 4000 such trials, before."""
import sys
import lib
EXTRA = r'''
struct Box9 { const char *name; const char *text; };
static const Box9 rateBoxes9[] = { { "t10", "3.70" }, { "t12", "95" }, { "tr1", "1.80" }, { "tr2", "0.65" }, { "tr3", "240" }, { "tr4", "12.5" }, { "tr5", "-3.5" }, { "tr6", "100" }, { "tr7", "0" }, { "tr8", "45" }, { "tr9", "7" }, { "tr10", "360" } };
static void ratesPage9() { Page &p = screen.pages["RXOptionsView"]; for (auto &b : rateBoxes9) p.boxes[b.name] = { true, 0, b.text }; }
static long wrongText9 = 0, wrongNum9 = 0, lostBox9 = 0, okBox9 = 0, cuts9 = 0, shouts9 = 0, holds9 = 0;
static void tellWrong9(const char *what, const char *box, const char *got, const char *want)
{
    static int told = 0; if (++told > 12) return;
    printf("   WRONG %s: box %s holds \"%s\", handed back \"%s\" (not flagged)\n      the line was: %s\n      stall %u us, the line after %u us, its core held %u us, wake round %u us\n", what, box, want, got, screen.lastShout.c_str(), stallUs9, shoutAfterUs9, holdUs9, wakeRoundUs9);
}
static void readText9(const Box9 &b)
{
    char t[24] = "x"; const uint32_t lost0 = BoxesLost; NextionTextMissed = false;
    GetText((char *) b.name, t, sizeof(t) - 1);
    if (BoxesLost != lost0 || NextionTextMissed) { ++lostBox9; return; }
    if (strcmp(t, b.text)) { ++wrongText9; tellWrong9("TEXT", b.name, t, b.text); } else ++okBox9;
}
static void readNum9(const char *name, uint32_t want)
{
    const uint32_t lost0 = BoxesLost; const uint32_t v = GetValue((char *) name);
    if (BoxesLost != lost0 || v == 65535) { ++lostBox9; return; }
    if (v != want) { ++wrongNum9; char g[16], w[16]; snprintf(g, sizeof g, "%u", (unsigned) v); snprintf(w, sizeof w, "%u", (unsigned) want); tellWrong9("NUMBER", name, g, w); } else ++okBox9;
}
static void tally9() { shouts9 += screen.realShouts; cuts9 += screen.shoutCuts > 0; holds9 += (screen.realShouts && holdUs9); }
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 250;
    for (int form : { 197, 198 })
    {
        // 1. A SAVE AS THE ROTORFLIGHT PAGES DO IT (RF_Rates.h SendEditedRates): a wait, "Sending ...", the look before the boxes, then every text box
        long lostAll = 0, okAll = 0;
        for (int mode = 0; mode < 3; ++mode)
        {
            wrongText9 = wrongNum9 = lostBox9 = okBox9 = cuts9 = shouts9 = holds9 = 0;
            for (int i = 0; i < N; ++i)
            {
                more(); screen.realUart = true; screen.shoutForm = form; tapAt(5, "setup"); loopFor(800); ratesPage9();
                draw9(mode); plantAt9 = getsAsked9() + 1 + (int) rnd9(12); flyHook = plant9;
                DelayWithDog(100); SendText((char *) "change", (char *) "Sending edited rates ..."); RfGatherStart();
                for (auto &b : rateBoxes9) readText9(b);
                flyHook = nullptr; tally9(); loopFor(300);
            }
            say("1. a screen of 1.11.%d, a save of twelve text boxes, a stall planted (%s): %d trials, lines %ld (the loop's own writes inside one %ld, its core held %ld); boxes right %ld, no answer %ld, WRONG TEXT %ld\n",
                form, mode == 0 ? "the loop wakes near the line" : mode == 1 ? "anywhere" : "the loop wakes inside the line", N, shouts9, cuts9, holds9, okBox9, lostBox9, wrongText9);
            CHECK(wrongText9 == 0 && shouts9 > N / 2 && okBox9 > 0);
            lostAll += lostBox9; okAll += okBox9;
        }
        CHECK(okAll > 0);                                                            // (15 Nov 2026: a line costs the text box it comes inside the wait of - and the boxes behind it - on a screen of either age.
                                                                                     //  One from 1.11.198 on was "whole" by its newline and cost next to nothing; but the newline was taken from the bytes, and
                                                                                     //  the bytes of a FIELD screen's reply made one: dev/test_noanswer 9d)
        // 2. NUMBER BOXES the same way
        for (int mode = 0; mode < 3; mode += 2)
        {
            wrongText9 = wrongNum9 = lostBox9 = okBox9 = cuts9 = shouts9 = holds9 = 0;
            for (int i = 0; i < N; ++i)
            {
                more(); screen.realUart = true; screen.shoutForm = form; tapAt(5, "setup"); loopFor(800);
                draw9(mode); plantAt9 = getsAsked9() + 1 + (int) rnd9(6); flyHook = plant9;
                DelayWithDog(100); SendText((char *) "change", (char *) "Sending ..."); RfGatherStart();
                readNum9("n3", 5); readNum9("n0", 1000); readNum9("n2", 3); readNum9("n1", 5); readNum9("n4", 6); readNum9("c0", 1);
                flyHook = nullptr; tally9(); loopFor(300);
            }
            say("2. a screen of 1.11.%d, six number boxes (%s): %d trials, lines %ld (cut %ld, held %ld); right %ld, no answer %ld, WRONG NUMBER %ld\n", form, mode == 0 ? "near" : "inside", N, shouts9, cuts9, holds9, okBox9, lostBox9, wrongNum9);
            CHECK(wrongNum9 == 0 && shouts9 > N / 2 && okBox9 > lostBox9 * 10);
        }
        // 3. MODEL OPTIONS' OK (the REAL ReadRXOptionsView / RXOptionsViewEnd: numbers and two texts): all of the page is taken, or none of it
        {
            long bad = 0, savesAll = 0, taken = 0; shouts9 = cuts9 = holds9 = 0;
            for (int i = 0; i < N; ++i)
            {
                more(); screen.realUart = true; screen.shoutForm = form; tapAt(5, "setup"); loopFor(800);
                { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["t10"].txt = "3.70"; p.boxes["t12"].txt = "95"; p.boxes["n1"].val = 7; p.boxes["n4"].val = 8; p.boxes["c0"].val = 0; }
                draw9(i % 3); plantAt9 = getsAsked9() + 1 + (int) rnd9(11); flyHook = plant9;
                tapAt(5, "OK"); loopFor(7000); flyHook = nullptr; tally9();
                const bool typed = TrimMultiplier == 9 && StopFlyingVoltsPerCell > 3.69f && StopFlyingVoltsPerCell < 3.71f && Max_Safe_Amps == 95 && MotorChannel == 6 && TimerStartTime == 480 && !UseMotorKill;
                savesAll += (long) saves.size(); taken += typed;
                if (!typed && !sameAsAtFirst()) { ++bad; if (bad <= 6) printf("   3: WRONG after OK: trim step %u, stop flying %.2f V, most amps %d, motor channel %u, timer %u s (the line: %s)\n", (unsigned) TrimMultiplier, StopFlyingVoltsPerCell, Max_Safe_Amps, (unsigned) MotorChannel, (unsigned) TimerStartTime, screen.lastShout.c_str()); }
            }
            say("3. a screen of 1.11.%d, Model options' OK under a planted stall: %d trials, lines %ld (cut %ld, held %ld), saves %ld, all of the page taken %ld times; part of it taken: %ld\n", form, N, shouts9, cuts9, holds9, savesAll, taken, bad);
            CHECK(bad == 0 && savesAll == N && taken > N / 2);
        }
        // 4. THE MODELS PAGE (the REAL CheckModelName + ScreenSessionCheck), stalls at random moments; the pilot turns the list (a real change)
        for (int kind = 0; kind < 3; ++kind)
        {
            const int M = N / 3 + 1; long loaded = 0, fileMoved = 0, falseRestarts = 0, turnsTaken = 0, turns = 0, shoutsAll = 0;
            for (int i = 0; i < M; ++i)
            {
                more(); screen.realUart = true; screen.shoutForm = form; screen.latencyUs = 300 + rnd9(4000); tapAt(5, "models"); loopForModels(1500 + rnd9(700));
                int want = 4; bool moved = false, wrong = false; const uint64_t end = nowUs + 14000000ull;
                uint64_t nextStall = nowUs + rnd9(600000), nextTurn = nowUs + 2000000 + rnd9(6000000);
                flyHook = stallDue9;
                while (nowUs < end)
                {
                    if (nowUs >= nextStall && !stallAt9)
                    {
                        draw9(kind == 0 ? 0 : kind == 1 ? 2 : 1); if (kind == 2 && rnd9(2)) stallUs9 = 1900000 + rnd9(3000000);   // (kind 2: also stalls longer than a question's two seconds)
                        stallAt9 = nowUs + rnd9(500000); nextStall = nowUs + 1500000 + stallUs9 + rnd9(2500000);
                    }
                    if (nowUs >= nextTurn) { nextTurn = UINT64_MAX; want = 6; screen.pages["ModelsView"].boxes["MMems"].val = 5; ++turns; }   // the pilot turns the list to model 6
                    stallDue9(); loopForModels(3);
                    if (FileNumberInView != 2) moved = true;
                    if (ModelNumber != 4 && ModelNumber != (unsigned) want) wrong = true;
                    for (int r : modelsRead) if (r != want) wrong = true;
                }
                flyHook = nullptr; stallAt9 = 0; loopForModels(6000);                  // (the last stall's answers come, and are let go)
                if (wrong) { ++loaded; if (loaded <= 3) { printf("   a model nobody chose: model %u, read", (unsigned) ModelNumber); for (int r : modelsRead) printf(" %d", r); printf(" (the line: %s)\n", screen.lastShout.c_str()); } }
                if (moved) ++fileMoved;
                if (restartsHandled || ScreenRestartSeen || restartsFoundByAsking) { ++falseRestarts; if (falseRestarts <= 3) printf("   a restart 'found' (reason %d) on a screen that never restarted; the line: %s\n", (int) lastRestartReason, screen.lastShout.c_str()); }
                if (want == 6 && ModelNumber == 6) ++turnsTaken;
                shoutsAll += screen.realShouts;
            }
            say("4. a screen of 1.11.%d, the Models page, stalls %s: %d trials; lines %ld; a model nobody chose %ld; the files' row moved %ld; restarts 'found' on a screen that never restarted %ld; the pilot's turn of the list taken %ld of %ld\n",
                form, kind == 0 ? "that end near the line" : kind == 1 ? "that end inside the line" : "of any length (half of them over two seconds)", M, shoutsAll, loaded, fileMoved, falseRestarts, turnsTaken, turns);
            CHECK(loaded == 0 && fileMoved == 0 && falseRestarts == 0 && turnsTaken == turns && turns > M / 2 && shoutsAll > M);
        }
    }
    // 5. A TEXT BOX ASKED WHILE ITS PAGE IS STILL COMING UP, the load a fifth of a second - so the other core says "... last command 2xx ms ago: page
    //    <name>" - ending at a random moment near that line: the page command's second marker and the page's number are written by the loop's core while
    //    the line may still be going out (a screen up to 1.11.197: in pieces)
    {
        static const unsigned long ups[] = { 4321, 23456, 81234, 381234, 981234, 1381234, 4381234, 9381234, 14381234 };
        const int K = N * 8;
        for (int hold = 0; hold < 2; ++hold)
        {
            long wrong = 0, lost = 0, right = 0, cuts = 0, pTail = 0;
            for (int i = 0; i < K; ++i)
            {
                more(); screen.realUart = true; screen.autoLoadShout = false;
                const uint32_t shoutAfter = 180000 + rnd9(25000), loadUs = shoutAfter - 800 + rnd9(3200);
                screen.loadUs = loadUs; screen.roundUs = rnd9(3) ? 0 : rnd9(1500); screen.upMs = (uint32_t) (ups[rnd9(9)] + rnd9(9000));
                SendCommand((char *) "page RXOptionsView"); CurrentView = RXSETUPVIEW1;
                screen.run(nowUs); CHECK(screen.lastCmd.rfind("page ", 0) == 0);
                static const char *const busy[] = { "handle", "handle", "handle", "sd", "sd", "bg", "draw", "present", "wb", "copy", "rest" };   // (where a loading page spends its time)
                const std::string s = screen.shoutText(200 + rnd9(12), screen.lastCmdAt + (195 + rnd9(15)) * 1000, rnd9(5) ? "loopTask" : "IDLE1", "-", busy[rnd9(11)]);
                screen.lastShout = s; screen.shoutBegin(screen.lastCmdAt + shoutAfter, s, hold && rnd9(4) == 0 ? 1500 + rnd9(3000) : 0);
                if (s.size() > 128 && s[128] == 'p') ++pTail;
                OptionsBoxes();
                char t[24] = "x"; const uint32_t lost0 = BoxesLost; NextionTextMissed = false;
                GetText((char *) "t10", t, sizeof(t) - 1);
                if (BoxesLost != lost0 || NextionTextMissed) ++lost;
                else if (strcmp(t, "3.50")) { ++wrong; if (wrong <= 5) printf("   WRONG: box t10 holds \"3.50\", GetText gave \"%s\" (not flagged)\n      the line: %s\n", t, s.c_str()); }
                else ++right;
                cuts += screen.shoutCuts > 0;
            }
            say("5. a text box asked as its page comes up (a load of about 0.2 s, ending near the line%s): %d trials; lines whose byte 128 is 'p': %ld; the loop's writes fell inside the line %ld times; right %ld, no answer %ld, WRONG TEXT %ld\n",
                hold ? "; its core held now and then" : "", K, pTail, cuts, right, lost, wrong);
            CHECK(wrong == 0 && cuts > K / 20 && right + lost == K && pTail > K / 200);   // (the line whose second piece begins with the p of "page ..." was really among them.
                                                                                           //  15 Nov 2026: "right > 0" stood here - three in a thousand were "right" because a reply's byte 0A behind the line's first
                                                                                           //  piece had ended the line as if whole; run six times as long, one of those handed back "EL": dev/test_noanswer 9d)
        }
    }
'''
if __name__ == '__main__':
    args = ['--x', sys.argv[sys.argv.index('--n') + 1]] if '--n' in sys.argv else (['--show'] if '--show' in sys.argv else [])
    sys.exit(lib.build_run('storms', SCENES, EXTRA, args=args, sanitize='--fast' not in sys.argv, timeout=3600))
