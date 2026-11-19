#!/usr/bin/env python3
"""EXP P (review 12, reviewer A): THE PATHS OF THE TEXT BOX'S WAIT THAT NO SCENE REACHES (my break-it round, mut/list1: A1, A2, A4, A5 all MISSED).
 P1. the page goes DURING the wait (the power button's front page, from the wait's own radio turn): the box has no answer AT ONCE - counted
     (BoxesLost), said (NextionTextMissed), the box never asked, no further waiting.
 P2. the screen STARTS AGAIN during the wait: the same.
 P3. the settling look is not answered (the screen's loop stands still for 1.5 s): owed - the box has no answer, counted and said, not asked.
 P4. a word of the screen's own comes out WITH the settling answer (2 ms and more in front of it): another half second is waited, the screen asked
     again, and the box is then TAKEN (not asked with the word open, and refused).
 P7. (the thirteenth review, reviewer A's 9b) a word of the screen's own stands on the wire right BEHIND the settling answer: it was read in behind the
     wait - and the box asked all the same, to be refused ("press Save again"). The wait's own read takes it in: another turn, and the box is TAKEN.
What should hold is CHECKed: on the code as it stands every check passes; with a rule taken out one of them fails (the reviewer's own scenes, taken
as they came; P5, P6 and P7 are the author's)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static bool pFront = false; static void pFrontHook() { if (!pFront || NextionGetPending || ModalWaits) return; pFront = false; SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; }   // (main.cpp CheckPowerOffButton's part that matters)
static void open9() { more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900); for (auto *pp : { &screen.pages, &screen.pages0 }) (*pp)["RXOptionsView"].boxes["t10"].txt = "3.70"; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false; }
static bool p7Planted = false;
static void p7Plant()   // the settling look has gone out and the screen has not handled it yet: its loop will say a word of its own right behind the answer, in the same pass
{
    if (p7Planted || screen.cmds.empty() || screen.cmds.back().second != "sendme") return;
    for (auto &c : screen.cmds) if (c.second.rfind("get ", 0) == 0) return;   // (not the "sendme" that goes out with the box's own get)
    p7Planted = true;
    screen.later.insert({ screen.cmds.back().first + 1, by9("UKRULES") });      // (into its port right behind the look's answer)
}
static void wordNow9() { screen.emit(nowUs + 2000, by9("UKRULES")); loopFor(100); }   // a bare word of the screen's own, read by the main loop a tenth of a second ago
'''
SCENES = r'''
    // P1. the page goes during the wait
    {
        open9(); wordNow9(); CHECK(WordMayBeOpen());
        const uint32_t lost0 = BoxesLost; const int off0 = screen.offPageAnswers; const uint64_t t0 = nowUs;
        pFront = true; flyHook = pFrontHook;
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1); flyHook = nullptr;
        const uint64_t took = nowUs - t0; const bool counted = BoxesLost == lost0 + 1, said = NextionTextMissed;
        loopFor(1500);                                 // (what was sent is handled by the screen)
        say("P1. the front page put up from inside the wait: GetText gave %u chars \"%s\" after %llu ms; counted %d, said %d; the front page asked for the box %d time(s)\n", (unsigned) k, tx, (unsigned long long) (took / 1000), (int) counted, (int) said, screen.offPageAnswers - off0);
        CHECK(k == 0 && !tx[0]);
        CHECK(counted);                                // counted
        CHECK(said);                                   // said
        CHECK(screen.offPageAnswers == off0);          // the box was never asked of the front page
        CHECK(took < 250000);                          // ... and the wait did not go on
    }
    // P2. the screen starts again during the wait (its power-on bytes come in)
    {
        open9(); wordNow9(); CHECK(WordMayBeOpen());
        const uint32_t lost0 = BoxesLost; const int gets0 = screen.gets; const uint64_t t0 = nowUs;
        screen.emit(nowUs + 60000, { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF });
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("P2. the screen's power-on bytes read inside the wait: GetText gave %u chars after %llu ms; restart noted %d; counted %d, said %d, the box asked %d time(s)\n", (unsigned) k, (unsigned long long) ((nowUs - t0) / 1000), (int) ScreenRestartSeen, (int) (BoxesLost - lost0), (int) NextionTextMissed, screen.gets - gets0);
        CHECK(k == 0 && ScreenRestartSeen && BoxesLost == lost0 + 1 && NextionTextMissed && screen.gets == gets0 && nowUs - t0 < 250000);
    }
    // P3. the settling look not answered: owed
    {
        open9(); wordNow9();
        const uint32_t lost0 = BoxesLost; const int gets0 = screen.gets; const uint64_t t0 = nowUs;
        screen.stall(nowUs + 300000, 1500, false);     // the screen's loop stands still from 0.3 s on, for a second and a half
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("P3. the settling look unanswered for a second: GetText gave %u chars after %llu ms; owed %d; counted %d, said %d, the box asked %d time(s)\n", (unsigned) k, (unsigned long long) ((nowUs - t0) / 1000), (int) ScreenAnswerOwed, (int) (BoxesLost - lost0), (int) NextionTextMissed, screen.gets - gets0);
        CHECK(k == 0 && ScreenAnswerOwed && BoxesLost == lost0 + 1 && NextionTextMissed);
        CHECK(screen.gets == gets0);                   // nothing is asked of a screen that owes an answer
        CHECK(nowUs - t0 < 1700000);
        loopFor(4000); CHECK(!ScreenAnswerOwed);
    }
    // P4. a word comes out with the settling answer, 3 ms in front of it
    {
        open9(); wordNow9();
        { const char *w = "UKRULES"; for (auto *pp : { &screen.pages, &screen.pages0 }) { (*pp)["RXOptionsView"].buttons["poke"] = std::vector<uint8_t>(w, w + 7); (*pp)["RXOptionsView"].raw.insert("poke"); } }
        screen.tapInLoadFallsThrough = true;
        screen.stall(nowUs + 380000, 150, false, 3000);   // the loop stands still from 0.38 s to 0.53 s - across the moment the settling look is asked; 3 ms of its pass are left when it wakes ...
        tapAt(450, "poke");                               // ... in which its own page says its word
        const uint32_t lost0 = BoxesLost; const int gets0 = screen.gets; const uint64_t t0 = nowUs; textDoubted = 0;
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("P4. a word 3 ms in front of the settling answer: GetText gave %u chars \"%s\" after %llu ms; counted %d, not believed %d, the box asked %d time(s)\n", (unsigned) k, tx, (unsigned long long) ((nowUs - t0) / 1000), (int) (BoxesLost - lost0), textDoubted, screen.gets - gets0);
        CHECK(k == 4 && !strcmp(tx, "3.70") && BoxesLost == lost0 && !NextionTextMissed);   // TAKEN
        CHECK(textDoubted == 0 && screen.gets == gets0 + 1);
        CHECK(nowUs - t0 > 900000 && nowUs - t0 < 1400000);                                // (the second half second was waited)
        loopFor(1500);
    }
    // P5 (the author's, for the reviewer's C6: WORD_SETTLE_MS - 50 ms passed every test). The settling look is answered LATE: the screen's loop
    //     stands still from 0.35 s to 0.95 s, the look is asked at half a second and answered 0.45 s behind that - inside its second. The box is
    //     then TAKEN (a look given up after a twentieth of a second made "press Save again" of every stall)
    {
        open9(); wordNow9();
        const uint32_t lost0 = BoxesLost; const int gets0 = screen.gets; const uint64_t t0 = nowUs; textDoubted = 0;
        screen.stall(nowUs + 350000, 600, false);
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("P5. the settling look answered 0.45 s late: GetText gave %u chars \"%s\" after %llu ms; counted %d, owed %d, the box asked %d time(s)\n", (unsigned) k, tx, (unsigned long long) ((nowUs - t0) / 1000), (int) (BoxesLost - lost0), (int) ScreenAnswerOwed, screen.gets - gets0);
        CHECK(k == 4 && !strcmp(tx, "3.70") && BoxesLost == lost0 && !NextionTextMissed && !ScreenAnswerOwed);
        CHECK(textDoubted == 0 && screen.gets == gets0 + 1);
        CHECK(nowUs - t0 > 850000 && nowUs - t0 < 1300000);
        loopFor(1500);
    }
    // P6 (the author's, for the reviewer's "the wait's break"): the settling look finds ANOTHER PAGE on the screen - its keyboard, opened by a touch
    //     on a field while the word was waited out. The box has no answer at once, counted and said - and is NOT ASKED of the keyboard's page (it
    //     was: the way out of the wait went round the look at "has the page gone?")
    {
        open9(); wordNow9();
        const uint32_t lost0 = BoxesLost; const int gets0 = screen.gets, off0 = screen.offPageAnswers; const uint64_t t0 = nowUs;
        tapAt(200, "n4box");                              // (a touch on a number field, 0.2 s into the wait: the screen puts its keyboard up by itself)
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("P6. the keyboard came up inside the wait: GetText gave %u chars after %llu ms; counted %d, said %d, the box asked %d time(s), of another page %d\n", (unsigned) k, (unsigned long long) ((nowUs - t0) / 1000), (int) (BoxesLost - lost0), (int) NextionTextMissed, screen.gets - gets0, screen.offPageAnswers - off0);
        CHECK(k == 0 && !tx[0] && BoxesLost == lost0 + 1 && NextionTextMissed && PageChangedUnderGet);
        CHECK(screen.gets == gets0 && screen.offPageAnswers == off0);
        CHECK(nowUs - t0 < 700000);
        loopFor(1500);
    }
    // P6b (the thirteenth review, reviewer A's 9c). ... the same while THE PAGE'S OWN NUMBER IS NOT KNOWN (the page has only just been put up: its number
    //     is learned from the first answer that is not a keyboard's). The keyboard's page is "another page" then too: the box is not asked of it
    //     (it was - to be refused by its own look at the page, a question and its wait later)
    {
        open9(); wordNow9(); ScreenPageId = 0xFF; ScreenPageIdDue = true;
        const uint32_t lost0 = BoxesLost; const int gets0 = screen.gets, off0 = screen.offPageAnswers; const uint64_t t0 = nowUs;
        tapAt(200, "n4box");
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("P6b. ... the page's own number not yet known: GetText gave %u chars after %llu ms; counted %d, said %d, the box asked %d time(s), of another page %d\n", (unsigned) k, (unsigned long long) ((nowUs - t0) / 1000), (int) (BoxesLost - lost0), (int) NextionTextMissed, screen.gets - gets0, screen.offPageAnswers - off0);
        CHECK(k == 0 && !tx[0] && BoxesLost == lost0 + 1 && NextionTextMissed && PageChangedUnderGet);
        CHECK(screen.gets == gets0 && screen.offPageAnswers == off0);
        CHECK(nowUs - t0 < 700000);
        loopFor(1500);
    }
    // P7 (the thirteenth review, reviewer A's 9b). A word of the screen's own - the touch on a background, "UKRULES" - written by its loop right BEHIND the settling
    //     answer, in the same pass: it stands on the wire as the look comes back. The wait's own read takes it in, another half second is waited, the screen asked
    //     again, and the box is TAKEN. (It was read in BEHIND the wait and the box asked all the same - with that word open: not believed, "press Save again".)
    {
        open9(); wordNow9(); screen.latencyUs = 20300;    // (the look is answered a fifth of a millisecond into this board's radio turn between two of its waits of 20 ms: answer and word are both there when it looks again)
        const uint32_t lost0 = BoxesLost; const int gets0 = screen.gets; const uint64_t t0 = nowUs; textDoubted = 0;
        p7Planted = false; flyHook = p7Plant;
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1); flyHook = nullptr;
        say("P7. a word right behind the settling answer: GetText gave %u chars \"%s\" after %llu ms; planted %d; counted %d, not believed %d, the box asked %d time(s)\n", (unsigned) k, tx, (unsigned long long) ((nowUs - t0) / 1000), (int) p7Planted, (int) (BoxesLost - lost0), textDoubted, screen.gets - gets0);
        CHECK(p7Planted);
        CHECK(k == 4 && !strcmp(tx, "3.70") && BoxesLost == lost0 && !NextionTextMissed);   // TAKEN
        CHECK(textDoubted == 0 && screen.gets == gets0 + 1);
        CHECK(nowUs - t0 > 900000 && nowUs - t0 < 1500000);                                // (the second half second was waited)
        loopFor(1500);
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('wait_paths', SCENES, EXTRA, sanitize=False))
