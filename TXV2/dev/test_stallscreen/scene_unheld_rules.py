#!/usr/bin/env python3
"""EXP D/T (review 12, reviewer A): TWO MORE RULES NO TEST HOLDS ANY MORE (my break-it round, mut/list1: A9 and A11 MISSED).
 D. "A WORD THAT WAS OPEN WHEN THIS WAIT BEGAN IS OPEN FOR ALL OF IT" (Nextion.h CollectReply, doubtAtEntry - the tenth review's cure). Since the
    eleventh review's cure a text box waits such a word out, so its get begins with a word open only when the wait has given up (2.5 s of words).
    Here: words every 300 ms for 2.4 s; the wait gives up, the box is asked; the screen's loop stands still until 0.9 s after the last word; the
    rest of a cut line - it begins with p - and the box's answer then come out together. What should hold: NOT BELIEVED (no answer).
    With doubtAtEntry taken out the box's text is handed back as "age RXOptionsViewp3.70".
 T. "THE ANSWER IS OURS - no nested drain may take it" (B189; NextionGetPending in ScreenSettles): a model connected, its telemetry written to the
    screen from inside the waits (every write ends in a drain of the wire). The settling look in front of a save's boxes (RfGatherStart) and the one
    in front of a text box (GetText's wait) must still get their answer.
(The reviewer's own scenes, taken as they came.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static std::string clean(const std::string &s) { std::string o; char b[8]; for (unsigned char c : s) { if (c >= 32 && c < 127) o += (char) c; else { snprintf(b, sizeof b, "<%02X>", c); o += b; } } return o; }
static int teles = 0; static void teleEvery() { ++teles; SendText((char *) "StillConnected", (char *) "Amps 12.3"); waitHook = teleEvery; }   // the model's telemetry, written at the end of every wait that flies it
static void open9() { more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900); for (auto *pp : { &screen.pages, &screen.pages0 }) (*pp)["RXOptionsView"].boxes["t10"].txt = "3.70"; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false; }
'''
SCENES = r'''
    // D. a word open when the box's get begins; the answer comes more than half a second after that word, with a line's rest glued in front of it
    {
        open9();
        for (int w = 0; w < 9; ++w) screen.emit(nowUs + 2000 + (uint64_t) w * 300000, by9("UKRULES"));   // a word with no end every 300 ms, the last 2.4 s from now
        screen.stall(nowUs + 2450000, 850, false);                                                       // the screen's loop stands still from 2.45 s to 3.3 s ...
        screen.emit(nowUs + 2450000 + 850000 - 250, by9("page RXOptionsView"));                           // ... and the rest of a line of its other core comes out as it wakes
        loopFor(100); CHECK(WordMayBeOpen());
        const uint32_t lost0 = BoxesLost; const uint64_t t0 = nowUs; textDoubted = 0;
        char tx[40] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        printf("D. the box (it holds \"3.70\") asked when the wait gave up, its answer 0.9 s behind the last word with a line's rest in front: GetText gave %u chars \"%s\" after %llu ms; lost %d, not believed %d\n",
               (unsigned) k, clean(tx).c_str(), (unsigned long long) ((nowUs - t0) / 1000), (int) (BoxesLost - lost0), textDoubted);
        CHECK(k == 0 && !tx[0] && BoxesLost == lost0 + 1 && textDoubted == 1);
        loopFor(4000);
    }
    // T. telemetry written from inside the waits: the settling looks still get their answers
    {
        open9(); teles = 0; waitHook = teleEvery;
        RfGatherStart();
        printf("T1. a save's settling look with telemetry written in its waits (%d writes): settled %d, owed %d\n", teles, (int) NextionSettledOk, (int) ScreenAnswerOwed);
        CHECK(NextionSettledOk && !ScreenAnswerOwed && teles >= 1);
        waitHook = nullptr; loopFor(3000);
        open9(); screen.emit(nowUs + 2000, by9("UKRULES")); loopFor(100); CHECK(WordMayBeOpen());
        teles = 0; waitHook = teleEvery; const uint32_t lost0 = BoxesLost;
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1); waitHook = nullptr;
        printf("T2. a text box behind a word, telemetry written in its waits (%d writes): GetText gave %u chars \"%s\"; lost %d, owed %d\n", teles, (unsigned) k, tx, (int) (BoxesLost - lost0), (int) ScreenAnswerOwed);
        CHECK(k == 4 && !strcmp(tx, "3.70") && BoxesLost == lost0 && !ScreenAnswerOwed && teles >= 3);
        loopFor(3000);
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('unheld_rules', SCENES, EXTRA, sanitize=False))
