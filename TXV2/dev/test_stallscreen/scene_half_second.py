#!/usr/bin/env python3
"""EXP H1 (review 10, reviewer A): IS HALF A SECOND RIGHT (WORD_OPEN_MS)? A screen up to 1.11.197 says "the loop is silent" in pieces. Its first
piece (128 bytes) is read, and for half a second no text reply is believed. Here the shouting core is HELD between the first piece and the rest
for H ms (another flash operation of the loop's own job, both cores stalled by it), and the loop answers the text box that was waiting as soon as
both are let go: the line's tail - which begins with p ("... last command 213 ms ago: " | "play 0,7,0") - and the answer "p3.70" come together.
Counted, for each H: the box handed back with a WRONG text (not "no answer").

(The tenth review, reviewer A's experiment: from 520 ms on the box "3.70" came back as "lay 0,7,0p3.70", 300 times of 300. THE CURE: a word
that is open when a get's wait begins, or opens during it, is open for that whole wait - Nextion.h CollectReply.)

H2, H3 (the eleventh review's cure, "a word with no end is waited out before a text box is asked" - Nextion.h GetText): the line's first piece is read
by the main loop, and the box is asked for inside the half second - behind a save's settling wait (H2), and BY ITSELF (H3: a file's name, a model's).
H3 is where the plain cure, "ask when the half second is over", hands back "lay 0,7,0p3.70" (60 of 60 from a hold of 520 ms on): the box is asked
into the stall, and the line's rest and the answer come out together. The screen is asked "sendme" first; the rest comes out with THAT answer.

H4 (the twelfth review, reviewer A's experiment L): the box asked AT ANY TIME behind the word - 510 ms and more behind it, the rest still held, it was
handed "lay 0,7,0p3.70" (100 of 100). The word is UNSETTLED until a "sendme" has been answered behind its half second."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static std::string clean(const std::string &s) { std::string o; char b[8]; for (unsigned char c : s) { if (c >= 32 && c < 127) o += (char) c; else { snprintf(b, sizeof b, "<%02X>", c); o += b; } } return o; }
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
static bool hPlanted = false; static uint32_t hHoldUs = 0, hWakeAfterTailUs = 0; static std::string hLine;
static void hPlant()   // when the text box's get has gone out and the screen has not read it: the stall begins
{
    if (hPlanted) return;
    if (screen.cmds.size() < 2) return;
    const std::string &last = screen.cmds[screen.cmds.size() - 1].second, &prev = screen.cmds[screen.cmds.size() - 2].second;
    if (!(last == "sendme" && prev == "get t10.txt")) return;
    hPlanted = true;
    const uint64_t at = nowUs; const uint32_t shoutAfter = 200000 + xr(50000);
    const uint64_t tailAt = at + shoutAfter + 4 + hHoldUs;                    // (the shouting core goes on H ms after its first piece)
    screen.busyUntil = std::max(screen.busyUntil, tailAt + hWakeAfterTailUs); screen.cmdHoldUntil = std::max(screen.cmdHoldUntil, screen.busyUntil);
    screen.lastShout = hLine; screen.shoutBegin(at + shoutAfter, hLine, hHoldUs); ++screen.shouts;
}
static uint32_t hStallNow()   // H2: the stall begins NOW, no box asked for yet; its line a fifth of a second in, the rest held hHoldUs. The ms until the line's first piece
{
    const uint64_t at = nowUs; const uint32_t shoutAfter = 200000 + xr(50000);
    const uint64_t tailAt = at + shoutAfter + 4 + hHoldUs;
    screen.busyUntil = std::max(screen.busyUntil, tailAt + hWakeAfterTailUs); screen.cmdHoldUntil = std::max(screen.cmdHoldUntil, screen.busyUntil);
    screen.lastShout = hLine; screen.shoutBegin(at + shoutAfter, hLine, hHoldUs); ++screen.shouts;
    return shoutAfter / 1000;
}
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 200;
    // the line, as the screen's watch puts it together - its 129th byte the p of the last command handled, "play 0,7,0" (a sound the board asked for)
    screen.shoutForm = 197;
    const std::string line = "LDRCLOG core 1 (the loop's) silent for 213 ms at 381234 ms: task 'IDLE1' on it, part '-', loop at 'sd', last command 45 ms ago: play 0,7,0";
    CHECK(line.size() > 129 && line[128] == 'p' && line.substr(128) == "play 0,7,0");
    printf("the line (its first piece is 128 bytes; the rest is \"%s\"):\n   %s\n", line.c_str() + 128, line.c_str());
    for (uint32_t holdMs : { 2u, 100u, 300u, 480u, 520u, 600u, 900u, 1500u })
    {
        long wrong = 0, lost = 0, right = 0, doubted0 = 0; std::string example;
        for (int i = 0; i < N; ++i)
        {
            more(); xs = 4400 + i; screen.realUart = true; screen.shoutForm = 197; screen.latencyUs = 300 + xr(2000);
            tapAt(5, "setup"); loopFor(900); screen.pages["RXOptionsView"].boxes["t10"].txt = "3.70";
            hPlanted = false; hHoldUs = holdMs * 1000; hWakeAfterTailUs = xr(1800); hLine = line; flyHook = hPlant; textDoubted = 0;
            char t[24] = "x"; const uint32_t lost0 = BoxesLost; NextionTextMissed = false;
            SendText((char *) "change", (char *) "Sending ..."); RfGatherStart();
            GetText((char *) "t10", t, sizeof(t) - 1); flyHook = nullptr;
            if (BoxesLost != lost0 || NextionTextMissed) ++lost;
            else if (strcmp(t, "3.70")) { ++wrong; if (example.empty()) example = t; }
            else ++right;
            doubted0 += textDoubted;
            loopFor(2500);
        }
        printf("H1: the shouting core held for %4u ms between its first piece and the rest: %d trials; the box (it holds \"3.70\") handed back RIGHT %ld, no answer %ld (not believed: %ld), WRONG %ld%s%s%s\n",
               holdMs, N, right, lost, doubted0, wrong, wrong ? "  e.g. \"" : "", wrong ? clean(example).c_str() : "", wrong ? "\"" : "");
        CHECK(wrong == 0 && right + lost == N);                                      // (never a wrong text, however long the hold)
        if (holdMs >= 100) CHECK(doubted0 == N);                                     // (... and it is said: "not believed", each time)
    }
    // H2 (the eleventh review, 15 Nov 2026: A WORD WITH NO END IS WAITED OUT before a text box is asked - Nextion.h GetText). The line's first piece
    // is read by the MAIN LOOP, no box asked for yet; the stall goes on and the shouting core is held H ms; the save is pressed some time inside
    // the half second. The plain cure - "ask when the half second is over" - asks INTO the stall: the line's rest (it begins with p) and the
    // box's answer come out together, and "lay 0,7,0p3.70" is taken for the box's text. So the screen is asked "sendme" first: what comes out
    // with THAT answer is read in (another half second), and the box is asked of a screen whose loop is running. Never a wrong text.
    for (uint32_t holdMs : { 2u, 300u, 480u, 520u, 600u, 900u, 1500u, 2400u })
    {
        long wrong = 0, lost = 0, right = 0; std::string example; uint64_t longest = 0;
        for (int i = 0; i < N; ++i)
        {
            more(); xs = 8800 + i; screen.realUart = true; screen.shoutForm = 197; screen.latencyUs = 300 + xr(2000);
            tapAt(5, "setup"); loopFor(900); screen.pages["RXOptionsView"].boxes["t10"].txt = "3.70";
            hHoldUs = holdMs * 1000; hWakeAfterTailUs = xr(1800); hLine = line; textDoubted = 0;
            const uint32_t headMs = hStallNow();
            loopFor(headMs + 15 + xr(420));                                          // the main loop reads the line's first piece; the save is pressed up to 0.4 s later
            char t[24] = "x"; const uint32_t lost0 = BoxesLost; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false;
            const uint64_t t0 = nowUs;
            SendText((char *) "change", (char *) "Sending ..."); RfGatherStart();
            GetText((char *) "t10", t, sizeof(t) - 1);
            if (nowUs - t0 > longest) longest = nowUs - t0;
            if (BoxesLost != lost0 || NextionTextMissed) ++lost;
            else if (strcmp(t, "3.70")) { ++wrong; if (example.empty()) example = t; }
            else ++right;
            loopFor(3500);
        }
        printf("H2: the line's first piece read by the main loop, the rest held for %4u ms, the save pressed inside the half second: %d trials; the box handed back RIGHT %ld, no answer %ld, WRONG %ld%s%s%s; the longest the save's first box took: %llu ms\n",
               holdMs, N, right, lost, wrong, wrong ? "  e.g. \"" : "", wrong ? clean(example).c_str() : "", wrong ? "\"" : "", (unsigned long long) (longest / 1000));
        CHECK(wrong == 0 && right + lost == N);                                      // never a wrong text
        if (holdMs <= 2) CHECK(right == N);                                          // ... and with the line out in one go (as it nearly always is) the box is TAKEN
                                                                                     // (the shouting core HELD while the save's "sendme" waits: the line's rest comes out glued in
                                                                                     //  front of that answer, which is then not read - the save is refused, as before this cure)
    }
    // H3 (the same, of A TEXT BOX ASKED BY ITSELF - a file's name, a model's: no gather's settling wait stands in front of it). This is where "ask
    // when the half second is over" goes wrong: the box is asked INTO the stall, and the line's rest and the box's answer come out together -
    // "lay 0,7,0p3.70" for the box's text. With the screen asked "sendme" first (GetText: ScreenSettles) the rest comes out with THAT answer.
    for (uint32_t holdMs : { 2u, 300u, 480u, 520u, 600u, 900u, 1500u, 2400u })
    {
        long wrong = 0, lost = 0, right = 0; std::string example;
        for (int i = 0; i < N; ++i)
        {
            more(); xs = 12100 + i; screen.realUart = true; screen.shoutForm = 197; screen.latencyUs = 300 + xr(2000);
            tapAt(5, "setup"); loopFor(900); screen.pages["RXOptionsView"].boxes["t10"].txt = "3.70";
            hHoldUs = holdMs * 1000; hWakeAfterTailUs = xr(1800); hLine = line; textDoubted = 0;
            const uint32_t headMs = hStallNow();
            loopFor(headMs + 15 + xr(420));
            char t[24] = "x"; const uint32_t lost0 = BoxesLost; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false;
            GetText((char *) "t10", t, sizeof(t) - 1);
            if (BoxesLost != lost0 || NextionTextMissed) ++lost;
            else if (strcmp(t, "3.70")) { ++wrong; if (example.empty()) example = t; }
            else ++right;
            loopFor(3500);
        }
        printf("H3: ... a text box asked by itself inside the half second, the line's rest held for %4u ms: %d trials; RIGHT %ld, no answer %ld, WRONG %ld%s%s%s\n",
               holdMs, N, right, lost, wrong, wrong ? "  e.g. \"" : "", wrong ? clean(example).c_str() : "", wrong ? "\"" : "");
        CHECK(wrong == 0 && right + lost == N);                                      // never a wrong text
        if (holdMs <= 2) CHECK(right == N);
    }
    // H4 (the twelfth review, reviewer A's experiment L - his finding 1): THE BOX ASKED AT ANY TIME. H3 asks inside the half second only, and so could not
    // see it: a box asked 510 ms AND MORE behind the read of the line's first piece - the stall still on, the rest still held - was asked the old way
    // (the "sendme" first only while the half second ran), and was handed "lay 0,7,0p3.70": 100 of 100 for every hold from 600 ms. THE CURE: the word
    // is UNSETTLED until the screen has answered "sendme" behind its half second, and until then every text box settles first.
    // For each hold of the shouting core and each moment the box is asked at (ms behind the read of the first piece): never a wrong text - and
    // where the rest is out before the ask, or in the look that settles, the box is TAKEN (one "sendme" more, not a refusal).
    {
      const int N4 = N < 60 ? N : 60;
      for (uint32_t holdMs : { 100u, 400u, 600u, 900u, 1500u })
        for (uint32_t askMs : { 300u, 480u, 520u, 560u, 800u, 1500u, 2600u })
        {
            long wrong = 0, lost = 0, right = 0; std::string example;
            for (int i = 0; i < N4; ++i)
            {
                more(); xs = 31000 + holdMs + askMs + i; screen.realUart = true; screen.shoutForm = 197; screen.latencyUs = 300 + xr(2000);
                tapAt(5, "setup"); loopFor(900); screen.pages["RXOptionsView"].boxes["t10"].txt = "3.70";
                hHoldUs = holdMs * 1000; hWakeAfterTailUs = xr(1800); hLine = line;
                const uint32_t headMs = hStallNow();
                loopFor(headMs + 5); CHECK(WordOpenMs != 0);                          // the main loop has read the line's first piece ...
                loopFor(askMs - 3);                                                   // ... and the box is asked askMs behind that
                char t[24] = "x"; const uint32_t lost0 = BoxesLost; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false;
                GetText((char *) "t10", t, sizeof(t) - 1);
                if (BoxesLost != lost0 || NextionTextMissed) ++lost;
                else if (strcmp(t, "3.70")) { ++wrong; if (example.empty()) example = t; }
                else ++right;
                loopFor(3500);
            }
            printf("H4: the line's rest held %4u ms; the box asked %4u ms behind the first piece: RIGHT %3ld  no answer %3ld  WRONG %3ld%s%s%s\n",
                   holdMs, askMs, right, lost, wrong, wrong ? "  e.g. \"" : "", wrong ? clean(example).c_str() : "", wrong ? "\"" : "");
            CHECK(wrong == 0 && right + lost == N4);                                  // never a wrong text, whenever it is asked
            if (holdMs <= 400 || askMs >= holdMs + 200) CHECK(right == N4);          // the rest out before the ask (or inside the wait): taken
        }
    }
'''
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '200'
    sys.exit(lib.build_run('h1', SCENES, EXTRA, args=['--x', nn], sanitize=False, timeout=1800))
