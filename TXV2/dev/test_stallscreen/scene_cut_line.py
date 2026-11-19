#!/usr/bin/env python3
"""THE SCREEN'S LINE IN TWO PARTS (the ninth review, reviewer A). The real screen's other core writes "the loop is silent" in pieces
(128 bytes, then some 27 every 300 us); a hold of that core between two pieces, or a reply of the loop's core written between
them, leaves the line's TAIL to begin a frame of its own. A tail that begins with p - "page RXOptionsView" - was read as the head
of a text reply: the box's text handed back as "age RXOptionsViewp3.70", a number made of it: 0.
Here the bytes are said by hand (the pretend screen deaf) and the REAL GetText / GetValue read them."""
import sys
import lib
SCENES = r'''
    const std::string shout = "LDRCLOG core 1 (the loop's) silent for 213 ms at 81234 ms: task 'IDLE1' on it, part '-', loop at 'sd', last command 213 ms ago: page RXOptionsView";
    const std::string head = shout.substr(0, 128), tail = shout.substr(128);
    CHECK(shout.size() == 146 && tail == "page RXOptionsView");
    auto quiet = []() { more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true; NextionTextMissed = false; };
    // A. a TEXT box asked; the line's first piece; 2.5 ms of nothing (its core held); its tail; then the screen's loop wakes: the answer, the page's number
    {
        quiet(); const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, by9(head.c_str())); screen.emit(t0 + 128 * 11 + 2500, by9(tail.c_str())); screen.emit(t0 + 90000, cat9({ by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("A. text box t10 (it holds 3.70), the line in two parts 2.5 ms apart, the tail beginning 'p': GetText gave %u chars \"%s\", missed %d, not believed %d\n", (unsigned) k, tx, (int) NextionTextMissed, textDoubted);
        CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1 && ScreenAnswerOwed && PageChangedUnderGet);
    }
    // B. the line in one piece (a screen up to 1.11.197: no end), the answer 90 ms behind it: a text is not believed for half a second ...
    {
        quiet(); const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, by9(shout.c_str())); screen.emit(t0 + 90000, cat9({ by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1);
    }
    //    ... and 600 ms behind it, the same (the tenth review: HALF A SECOND IS A TIME, NOT A BOUND - a word that opened inside this box's own wait
    //    is open for the whole of it; the line's rest, held back for longer than half a second, came out with the answer and was read as its text)
    {
        quiet(); const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, by9(shout.c_str())); screen.emit(t0 + 600000, cat9({ by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1);
    }
    //    ... its tail, beginning with p, 600 ms behind its head and the answer glued behind the tail (what the tenth review ran): not believed
    {
        quiet(); const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, by9(head.c_str())); screen.emit(t0 + 600000, cat9({ by9(tail.c_str()), by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1);
    }
    //    ... the line's head read by the MAIN LOOP; a text box asked for 300 ms later - inside the half second. (The eleventh review: that box was
    //    asked at once, and refused - a save lost to every stall of a quarter to two thirds of a second.) THE WORD IS WAITED OUT: the box is asked
    //    only when the half second is over and the screen has answered "sendme" - not before - and of a screen whose loop is running it gets
    //    its own text
    {
        more(); tapAt(5, "setup"); loopFor(800); NextionTextMissed = false; screen.pages["RXOptionsView"].boxes["t10"].txt = "3.70";   // (the screen answers for itself here)
        screen.emit(nowUs + 2000, by9(head.c_str())); loopFor(300);
        CHECK(WordMayBeOpen());
        const uint64_t t0 = nowUs; const int gets0 = screen.gets;
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("A4. the line's head read by the main loop, a text box asked for 300 ms later: GetText gave %u chars \"%s\" after %llu ms; missed %d, not believed %d\n",
            (unsigned) k, tx, (unsigned long long) ((nowUs - t0) / 1000), (int) NextionTextMissed, textDoubted);
        CHECK(k == 4 && !strcmp(tx, "3.70") && !NextionTextMissed && textDoubted == 0);
        CHECK(nowUs - t0 >= 190000 && nowUs - t0 < 600000);                          // (the rest of the half second was waited for - and no longer than that and the two answers)
        CHECK(screen.gets == gets0 + 1);                                             // (ONE ask of the box)
    }
    //    ... and WORDS THAT KEEP COMING (one every 300 ms, for two and a half seconds): the wait gives up after two and a half seconds, the box is
    //    asked with a word still open - and its answer is not believed: a word open when a get's wait begins is open for all of it (the tenth
    //    review's rule, CollectReply)
    {
        more(); tapAt(5, "setup"); loopFor(800); NextionTextMissed = false; screen.pages["RXOptionsView"].boxes["t10"].txt = "3.70";
        for (int w = 0; w < 9; ++w) screen.emit(nowUs + 2000 + (uint64_t) w * 300000, by9("UKRULES"));   // (the last of them 2.4 s from now: still open when the wait gives up)
        loopFor(100); CHECK(WordMayBeOpen());
        const uint64_t t0 = nowUs;
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("A5. a word with no end every 300 ms: GetText gave %u chars \"%s\" after %llu ms; missed %d, not believed %d\n", (unsigned) k, tx, (unsigned long long) ((nowUs - t0) / 1000), (int) NextionTextMissed, textDoubted);
        CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1);
        CHECK(nowUs - t0 >= 2400000 && nowUs - t0 < 3600000);                        // (two and a half seconds of waiting, then the one ask)
        loopFor(4000);
    }
    //    ... and a box asked for 600 ms AFTER a line that the main loop read (nothing was waiting then): the word is over - and UNSETTLED (the twelfth
    //    review: no "sendme" answered behind its half second yet). The screen is asked "sendme" first; with its answer the text is read
    {
        quiet(); screen.emit(nowUs + 2000, by9(shout.c_str())); loopFor(600);
        CHECK(WordOpenMs != 0 && !WordMayBeOpen() && WordSettledFor != WordOpenMs);
        screen.emit(nowUs + 60000, PAGE9); screen.emit(nowUs + 200000, cat9({ by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 4 && !strcmp(tx, "3.70") && textDoubted == 0 && !NextionTextMissed && WordSettledFor == WordOpenMs);
    }
    //    ... and from a screen of 1.11.198 on (one piece, a newline at its end): THE SAME (15 Nov 2026 - the answer right behind it was read: "a line that
    //    ends with a newline is whole". But the newline was taken from the bytes, and a reply's own byte 0A behind a FIELD screen's line made such an end:
    //    dev/test_noanswer 9d). The line that comes inside the box's own wait costs that box; one the main loop read before is waited out, and the box taken
    {
        quiet(); const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, cat9({ by9("LDRCLOG core 1 (the loop's) silent for 213 ms: task IDLE1, part -, at sd, cmd 213 ms ago: page RXOptionsView\n"), by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 0 && !tx[0] && textDoubted == 1 && NextionTextMissed);
    }
    {
        quiet(); screen.emit(nowUs + 2000, by9("LDRCLOG core 1 (the loop's) silent for 213 ms: task IDLE1, part -, at sd, cmd 213 ms ago: page RXOptionsView\n")); loopFor(100);
        CHECK(WordOpenMs != 0 && WordMayBeOpen());
        screen.emit(nowUs + 460000, PAGE9); screen.emit(nowUs + 600000, cat9({ by9("p3.70"), END9, PAGE9 }));   // (the look's answer behind the half second; then the box's)
        char tx[24] = "x"; const uint64_t t0 = nowUs; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 4 && !strcmp(tx, "3.70") && textDoubted == 0 && !NextionTextMissed && WordSettledFor == WordOpenMs && nowUs - t0 > 380000);
    }
    // C. no pause, but a REPLY OF THE LOOP'S CORE between the two pieces: a page command's second marker and the page's number were still owed
    //    when the text box was asked. Then the tail, then the answer. (Wrong before the eighth review's cures too.)
    {
        quiet();
        ScreenMarkCount = 77; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 77; ScreenMarkOldPage = false; ScreenMarkAskedMs = millis(); ScreenPageId = 0xFF; ScreenPageIdDue = false;
        const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, cat9({ by9(head.c_str()), { 'q', 77, 0, 0x45, 0x4C }, END9, PAGE9, by9(tail.c_str()) })); screen.emit(t0 + 30000, cat9({ by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        say("C. the page's marker and number written between the line's pieces: GetText gave %u chars \"%s\", missed %d, marker awaited %d, page id %u\n", (unsigned) k, tx, (int) NextionTextMissed, ScreenMarkAwaited != 0, (unsigned) ScreenPageId);
        CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1 && !ScreenMarkAwaited && ScreenPageId == 9);
    }
    // D. a NUMBER box under A's bytes: the tail that begins as a text reply does is let go when it has stood quiet, and the number is read
    //    (it was lost: "no answer" after two seconds)
    {
        quiet(); const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, by9(head.c_str())); screen.emit(t0 + 128 * 11 + 2500, by9(tail.c_str())); screen.emit(t0 + 90000, cat9({ { 'q', 9, 0, 0, 0 }, END9, PAGE9 }));
        const uint64_t g0 = nowUs; const uint32_t v = GetValue((char *) "n3");
        CHECK(v == 9 && !NextionTextMissed && nowUs - g0 < 500000 && !ScreenAnswerOwed);
    }
    // E. the tail begins with f (66 is the page's number's first byte): "...loop at 'wi" | "fi', last command ..." - and with q
    for (const char *cutAt : { "fi', last", "quiet', loop" })
    {
        const std::string s2 = "LDRCLOG core 1 (the loop's) silent for 213 ms at 81234 ms: task 'loopTask' on it, part 'quiet', loop at 'wifi', last command 310 ms ago: sendme";
        const size_t cut = s2.find(cutAt); CHECK(cut != std::string::npos);
        quiet(); const uint64_t t0 = nowUs + 60000 + 213000;
        screen.emit(t0, by9(s2.substr(0, cut).c_str())); screen.emit(t0 + cut * 11 + 2500, by9(s2.substr(cut).c_str())); screen.emit(t0 + 90000, cat9({ { 'q', 9, 0, 0, 0 }, END9, PAGE9 }));
        const uint64_t g0 = nowUs; const uint32_t v = GetValue((char *) "n3");
        CHECK(v == 9 && !NextionTextMissed && nowUs - g0 < 500000);
    }
    //    ... the tail that begins with f, come between a box's answer and its page's number: let go when it has stood quiet - the page's number
    //    behind it is read (held open, it took the page's number: "the screen did not say its page", no answer)
    {
        quiet(); const uint64_t t0 = nowUs + 60000;
        screen.emit(t0, cat9({ { 'q', 9, 0, 0, 0 }, END9 })); screen.emit(t0 + 1000, by9("fi', last command 310 ms ago: sendme")); screen.emit(t0 + 6000, PAGE9);
        CHECK(GetValue((char *) "n3") == 9 && !NextionTextMissed && pageUnsaid == 0 && !ScreenAnswerOwed);
    }
    // F. a bare word, 3 ms, a NUMBER's answer - while the collector is away flying the model (its turn every 20 ms; a turn of 1 ms, and of 4):
    //    both may land in one turn, glued - the number is read all the same (B162's rule). (A TEXT behind a word with no end is never believed.)
    for (int away = 0; away < 2; ++away)
    {
        int lost = 0, all = 0, wrong = 0;
        for (uint32_t at = 60000; at < 80000; at += 250)
        {
            quiet(); static bool slow; slow = away != 0; flyHook = []() { if (slow && NextionGetPending) nowUs += 3000; };
            const uint64_t t0 = nowUs + at; screen.emit(t0, by9("LDRCAWAKE")); screen.emit(t0 + 3000, cat9({ { 'q', 5, 0, 0, 0 }, END9, PAGE9 }));
            const uint32_t v = GetValue((char *) "n3"); flyHook = nullptr; ++all; if (v == 65535) ++lost; else if (v != 5) ++wrong;
        }
        say("F. a word, 3 ms, a number's answer; the radio's turn takes %s: lost %d of %d, wrong %d\n", away ? "4 ms" : "1 ms", lost, all, wrong);
        CHECK(all == 80 && lost == 0 && wrong == 0);
    }
    // G. a bare text that ends q and two more bytes, with a page's number glued behind it, met while a NUMBER is awaited: the four bytes behind
    //    that q are no number a box holds - it was handed back as 157693728 - and the real answer, which comes next, is the answer
    {
        quiet(); const uint64_t t0 = nowUs + 60000;
        screen.emit(t0, cat9({ by9("LDRCLOG core 1 (the loop's) silent for 213 ms at 81234 ms: task 'loopTask' on it, part '-', loop at 'serial', last command 216 ms ago: ldrcreq 7"), PAGE9 }));
        screen.emit(t0 + 30000, cat9({ { 'q', 5, 0, 0, 0 }, END9, PAGE9 }));
        const uint32_t v = GetValue((char *) "n3");
        say("G. a word ending \"q 7\" with a page's number glued behind it, then the real answer 5: GetValue gave %u\n", (unsigned) v);
        CHECK(v == 5 && !NextionTextMissed);
    }
    //    ... a return code glued behind a word ending q and three bytes is no number either. (A number BELOW ZERO glued behind a word with no
    //    pause at all is still lost - its own FF bytes end the frame early: no answer, never a wrong number. With a pause it is read.)
    {
        quiet(); const uint64_t t0 = nowUs + 60000;
        screen.emit(t0, cat9({ by9("LDRCLOG the heap: freq 12"), { 0x01 }, END9 })); screen.emit(t0 + 30000, cat9({ { 'q', 5, 0, 0, 0 }, END9, PAGE9 }));
        CHECK(GetValue((char *) "n3") == 5);
        quiet(); screen.emit(nowUs + 60000, cat9({ by9("UKRULES"), { 'q', 0xFE, 0xFF, 0xFF, 0xFF }, END9, PAGE9 }));
        CHECK(GetValue((char *) "n2") == 65535 && NextionTextMissed && ScreenAnswerOwed);
        quiet(); screen.emit(nowUs + 60000, by9("UKRULES")); screen.emit(nowUs + 63000, cat9({ { 'q', 0xFE, 0xFF, 0xFF, 0xFF }, END9, PAGE9 }));
        CHECK(GetValue((char *) "n2") == 0xFFFFFFFEu && !NextionTextMissed);
    }
    // I. A WORD CUT TWICE, both tails beginning with p: the first tail stands quiet and is let go - and NOTED: the second, with the answer glued
    //    to it, is not believed
    {
        quiet(); const uint64_t t0 = nowUs + 60000;
        screen.emit(t0, by9("page RX")); screen.emit(t0 + 5000, cat9({ by9("pOptionsView"), by9("p3.70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1);
    }
    //    ... and a tail that begins with p and STANDS OPEN WHEN A WAIT ENDS is noted too (the next box's wait would meet its other half)
    {
        //    (the wait begins on a whole millisecond and the bytes come 1.2 ms before its end: they stand open, quiet for less than 2 ms, when the
        //     time is over - the wait reads on until they have stood quiet for 2 ms, and ends)
        auto lastMoment = [](const std::vector<uint8_t> &b, uint8_t expected) { nowUs = (nowUs / 1000 + 1) * 1000; uint16_t k = 0; NextionReplyWaitMs = 30; screen.emit(nowUs + 28800, b); const uint64_t t0 = nowUs;
                                                                                 CollectReply(expected, k); NextionReplyWaitMs = 100; return (int) k * 1000 + (int) ((nowUs - t0) / 1000); };
        quiet(); CHECK(WordOpenMs == 0);
        { const int r = lastMoment(by9("page RX"), 'q'); CHECK(r % 1000 >= 30 && r % 1000 <= 32 && WordOpenMs != 0); }
        quiet(); { const int r = lastMoment(by9("quiet', loop at 'sd'"), 0x66); CHECK(r % 1000 >= 30 && WordOpenMs != 0); }
        //    ... one that TRICKLES in across the wait's end (a byte a millisecond: never quiet for two): the wait gives up 50 ms beyond its time
        //    with the tail open - noted there
        quiet(); { nowUs = (nowUs / 1000 + 1) * 1000; const uint64_t t0 = nowUs; const char *w = "page RXOptionsView and what the screen's loop was doing when it stood still, said slowly";
                   for (int i = 0; w[i]; ++i) screen.emit(t0 + 25000 + (uint64_t) i * 1000, { (uint8_t) w[i] });
                   uint16_t k = 0; NextionReplyWaitMs = 30; CollectReply('q', k); NextionReplyWaitMs = 100;
                   CHECK(k > 40 && nowUs - t0 >= 80000 && nowUs - t0 < 83000 && WordOpenMs != 0 && PendingCount == 0); }
        quiet(); { const int r = lastMoment({ 'q', 5, 0 }, 'q'); CHECK(r / 1000 == 3 && r % 1000 >= 30 && WordOpenMs == 0); }   // (half a value reply is no word)
        quiet(); { const int r = lastMoment({ 0x66 }, 0x66); CHECK(r / 1000 == 1 && WordOpenMs == 0); }                          // (nor is half a page's number)
    }
    // J. A TEXT REPLY IN TWO PIECES, 3 ms apart. A screen that frames writes a reply in one piece: this is no reply - no answer. A screen that
    //    has never framed (an older one) is read as it always was: the reply is waited for, and read whole
    {
        quiet(); const uint64_t t0 = nowUs + 60000;
        screen.emit(t0, by9("p3.")); screen.emit(t0 + 3000, cat9({ by9("70"), END9, PAGE9 }));
        char tx[24] = "x"; const uint16_t k = GetText((char *) "t10", tx, sizeof(tx) - 1);
        CHECK(k == 0 && !tx[0] && NextionTextMissed);
        quiet(); ScreenFramesBursts = false; const uint64_t t1 = nowUs + 60000;
        screen.emit(t1, by9("p3.")); screen.emit(t1 + 3000, cat9({ by9("70"), END9, PAGE9 }));
        char ty[24] = "x"; const uint16_t k2 = GetText((char *) "t10", ty, sizeof(ty) - 1);
        CHECK(k2 == 4 && !strcmp(ty, "3.70") && !NextionTextMissed);
    }
    // K. A BURST WHOSE LENGTH IS DAMAGED (60000 bytes declared; the screen frames 4000 at most): it never completed - at once, and the answer
    //    that comes 5 ms behind it is read (the length was followed: the answer was taken for the burst's bytes). And a burst that TRICKLES
    //    in - a byte every 15 ms - is read for a tenth of a second, no longer (it was read for as long as bytes came, the model not flown)
    {
        quiet(); const uint64_t t0 = nowUs + 60000;
        screen.emit(t0, { 0x7E, 0x7E, 0x60, 0xEA }); screen.emit(t0 + 5000, cat9({ { 'q', 9, 0, 0, 0 }, END9, PAGE9 }));
        CHECK(GetValue((char *) "n3") == 9 && ghosts.size() == 1);
        quiet(); ghosts.clear(); const uint64_t t1 = nowUs + 1000;
        screen.emit(t1, { 0x7E, 0x7E, 0xB8, 0x0B }); for (int i = 0; i < 100; ++i) screen.emit(t1 + 100 + (uint64_t) i * 15000, { (uint8_t) ('a' + i % 26) });
        nowUs = t1 + 200; const uint64_t g0 = nowUs; GetButtonPress();
        say("K. a burst that trickles in: read for %.0f ms\n", (nowUs - g0) / 1000.0);
        CHECK(nowUs - g0 < 200000 && nowUs - g0 > 80000 && ghosts.size() == 1);
    }
    // H. the same second half read by the MAIN LOOP (no get waits), the line cut before "FrontView": the word alone, with no number, from a
    //    screen that says its session's number is a QUESTION - the screen is asked, and it is the same screen: no restart, no front page
    {
        more(); tapAt(5, "setup"); loopFor(800); ghosts.clear();
        screen.emit(nowUs + 1000, by9("LDRCLOG core 1 (the loop's) silent for 213 ms at 81234 ms: task 'IDLE1' on it, part '-', loop at 'sd', last command 213 ms ago: page ")); screen.emit(nowUs + 5000, by9("FrontView"));
        loopFor(400);
        say("H. the loop reads a line cut before \"FrontView\": restart noted %d, answered %d, found by asking %d, owed caught up %d, page %s\n", (int) ScreenRestartSeen, restartsHandled, restartsFoundByAsking, owedCaughtUp, screen.page.c_str());
        CHECK(!ScreenRestartSeen && restartsHandled == 0 && restartsFoundByAsking == 0 && owedCaughtUp == 1 && CurrentView == RXSETUPVIEW1 && screen.page == "RXOptionsView" && screenLogLines.size() == 1);
    }
    //    ... and a screen that HAS started again and says its word alone (an older one; its power-on bytes lost): asked, it no longer knows its
    //    session's number - the front page afresh
    {
        more(); screen.restartReason = -1; screen.restartPowerOnBytes = false; screen.bootRecord = ""; tapAt(5, "setup"); loopFor(800); CHECK(ScreenSaidSession);
        tapAt(5, "#restart"); loopFor(6000);
        CHECK(screen.restarts == 1 && restartsHandled == 1 && lastRestartReason == -3 && restartsFoundByAsking == 1 && !ScreenRestartSeen && CurrentView == FRONTVIEW && screen.page == "FrontView");
    }
    //    ... its word alone read WHILE AN ANSWER IS OWED AND THE NUMBER HAS ALREADY COME BACK (this pass has not looked yet): that number says
    //    nothing about what came after - the screen is asked afresh, and found to have started again
    {
        more(); tapAt(5, "setup"); loopFor(800); CHECK(ScreenSaidSession);
        holdCatchUp = true; ScreenAnswerOwed = true; ScreenOwedSinceMs = millis(); ScreenEchoToldMs = 0; ScreenSaidEcho = false; ScreenEchoTell(); loopFor(50);
        CHECK(ScreenAnswerOwed && ScreenSaidEcho && ScreenSessionSaidN != ScreenEchoSessionN);        // (said back, the session's number in front of it)
        screen.sys.clear(); screen.emit(nowUs + 1000, by9("FrontView")); loopFor(20);                // (... then it started again, and says its word alone)
        CHECK(ScreenAnswerOwed && !ScreenSaidEcho && !ScreenRestartSeen);
        holdCatchUp = false; loopFor(400);
        CHECK(restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3 && CurrentView == FRONTVIEW);
    }
    //    ... A SCREEN THAT HAS STARTED AGAIN WITH EVERY SIGN LOST (no power-on bytes, no word): its buttons come unframed and are not obeyed -
    //    they were dead until this board was switched off and on. The first of them now makes this board ask: the front page afresh, and
    //    the buttons work again
    {
        more(); screen.restartPowerOnBytes = false; screen.restartSaysWord = false; screen.bootRecord = ""; tapAt(5, "setup"); loopFor(800);
        tapAt(5, "#restart"); loopFor(5000); CHECK(screen.restarts == 1 && !ScreenRestartSeen && restartsHandled == 0 && CurrentView == RXSETUPVIEW1);   // (nothing noticed)
        tapAt(5, "OK"); loopFor(600);                                              // (the card's page: its OK comes unframed - not obeyed, and the screen is asked)
        CHECK(count(obeyed, 39) == 0 && saves.empty() && !ghosts.empty() && restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3 && CurrentView == FRONTVIEW && screen.page == "FrontView");
        tapAt(5, "setup"); loopFor(800); CHECK(count(obeyed, 1077) == 2 && screen.page == "RXOptionsView");   // (its buttons work again)
    }
    //    ... and an unframed frame from the SAME screen (a split tail) costs one asking: no restart, nothing drawn afresh
    {
        more(); tapAt(5, "setup"); loopFor(800); ghosts.clear();
        screen.emit(nowUs + 1000, { 0xA7, 0x00, 0x00, 0x00 }); loopFor(300);
        CHECK(ghosts.size() == 1 && count(obeyed, 39) == 0 && restartsHandled == 0 && restartsFoundByAsking == 0 && owedCaughtUp == 1 && CurrentView == RXSETUPVIEW1);
    }
    //    ... its word alone BEHIND its power-on bytes is the restart's own (nothing to ask)
    {
        more(); screen.restartReason = -1; screen.bootRecord = ""; tapAt(5, "setup"); loopFor(800);
        tapAt(5, "#restart"); loopFor(6000);
        CHECK(screen.restarts == 1 && restartsHandled == 1 && lastRestartReason == -1 && restartsFoundByAsking == 0 && CurrentView == FRONTVIEW);
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('cut_line', SCENES))
