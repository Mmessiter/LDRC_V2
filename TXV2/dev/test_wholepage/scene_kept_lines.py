#!/usr/bin/env python3
"""THE LINES KEPT FOR A QUIET MOMENT (the fourteenth review: reviewer A's 4, reviewer B's A5 and B2; 16 Nov 2026). The REAL LogFiles.h - KeepScreenNote,
LogFrontPageReason, DeferLogText, FlushDeferredLog, ScreenLineOut (dev/test_stalepress's namespace "kept": a card that is a text) and, here, the REAL
LogScreenLine and ScreenDyingWords in front of them.
 K1 THE RESTART'S TWO LINES TOGETHER, OR NEITHER: five reasons kept, then the screen restarts - its first line took the sixth place and the line with
    the CAUSE found none (reviewer A's run).
 K2 THE SAME NOTE AGAIN BEHIND A WRITING IS KEPT: the same box unanswered at 10, 11, 12 and 13 o'clock left ONE line (reviewer B's run).
 K3 THE SCREEN'S OWN LINES WAIT FOR A QUIET MOMENT: "LDRCLOG ..." and the screen's dying words went to the card at once, part by part, whatever flew.
    While the model may fly: no card write; held WHOLE with their time; written with the kept lines; what finds no place is counted. On the ground:
    at once, as ever."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
LOGF = m.release(m.src('include/LogFiles.h'))
EXTRA = 'namespace kept {\n' + m.lift(LOGF, 'FLASHMEM void LogScreenLine(const char *t)') + m.lift(LOGF, 'FLASHMEM bool ScreenDyingWords(const char *t)') + '}\n'
SCENES = r"""
    // K1. five reasons, then the screen restarts (the model may fly all the while)
    {
        kept::reset(); mayFly = true;
        for (int pg = 20; pg < 25; ++pg) { CurrentView = (uint8_t) pg; kept::LogFrontPageReason("the motor switch went on", "motor switch on", nullptr); }
        CurrentView = 31;
        kept::LogFrontPageReason("the screen restarted (rst=4: a PANIC (a core dump should be on it))", "screen restart", "Screen restart 1: rst=4 PANIC");
        kept::FlushDeferredLog();
        std::vector<std::string> l = kept::lines();
        bool restartLine = false, causeLine = false; for (auto &x : l) { if (x.find("-> front: screen restart") != std::string::npos) restartLine = true; if (x.find("rst=4 PANIC") != std::string::npos) causeLine = true; }
        say("K1. five front-page reasons and then a restart in one flight: %d lines on the card; the restart's first line kept: %d; its cause kept: %d; the last line [%s]\n", (int) l.size(), (int) restartLine, (int) causeLine, l.empty() ? "" : l.back().c_str());
        CHECK(restartLine == causeLine && !restartLine && l.size() == 6 && l[5] == "               - 2 more notes about the screen were not kept B211");   // (five reasons, and the count: never the half that says nothing)
        kept::reset();                                                                       // ... and with four before it both are kept, in their order
        for (int pg = 20; pg < 24; ++pg) { CurrentView = (uint8_t) pg; kept::LogFrontPageReason("the motor switch went on", "motor switch on", nullptr); }
        CurrentView = 31; kept::LogFrontPageReason("x", "screen restart", "Screen restart 1: rst=4 PANIC"); kept::FlushDeferredLog();
        l = kept::lines(); CHECK(l.size() == 6 && l[4] == "12.34.56 - Page 31 -> front: screen restart" && l[5] == "12.34.56 - Screen restart 1: rst=4 PANIC");
        kept::reset();                                                                       // a reason of ONE line still takes the sixth place
        for (int pg = 20; pg < 26; ++pg) { CurrentView = (uint8_t) pg; kept::LogFrontPageReason("the motor switch went on", "motor switch on", nullptr); }
        kept::FlushDeferredLog(); CHECK(kept::lines().size() == 6);
    }
    // K2. the same note before and after a writing: each is an event of its own
    {
        kept::reset(); mayFly = true;
        for (int hour = 10; hour <= 13; ++hour) { kept::KeepScreenNote("Box unanswered: t10", false); kept::FlushDeferredLog(); }
        kept::KeepScreenNote("No page marker from the screen", false); kept::FlushDeferredLog(); kept::KeepScreenNote("No page marker from the screen", false); kept::FlushDeferredLog();
        say("K2. the same note at 10, 11, 12 and 13 o'clock and another twice, the kept lines written behind each: %d lines on the card, opened %d times\n", (int) kept::lines().size(), kept::cardOpens);
        CHECK(kept::lines().size() == 6 && kept::cardOpens == 6);
        kept::reset();                                                                       // ... and between two writings, the same line twice running is still kept once and takes one place
        for (int i = 0; i < 30; ++i) kept::KeepScreenNote("No page marker from the screen", false);
        kept::DeferLogText("Motor On", true); kept::DeferLogText("Motor On", true); kept::FlushDeferredLog(); CHECK(kept::lines().size() == 2);
        kept::reset();                                                                       // the store full (24): written at once, and the line that filled it is kept behind that writing - once
        for (int i = 0; i < 24; ++i) { char b[24]; snprintf(b, sizeof b, "Bank %d", i); kept::DeferLogText(b, true); }
        CHECK(kept::cardOpens == 0); kept::DeferLogText("Motor Off", true); kept::DeferLogText("Motor Off", true); CHECK(kept::cardOpens == 1 && kept::DeferredLogN == 1 && kept::lines().size() == 24);
        kept::FlushDeferredLog(); CHECK(kept::lines().size() == 25 && kept::lines().back() == "12.34.56 - Motor Off");
    }
    // K3. the screen's own lines
    {
        const char *rec[] = { "LDRCLOG core 1 (the loop's) silent for 213 ms: play 0,7,0 - the page was FrontView, the last command t0.txt=\"12.3V\" (it took 3 ms), the card busy 0 ms, heap 81234 free",
                              "LDRCLOG before the restart: page 13 FrontView, loop 2 ms, wifi off, card idle", "LDRCLOG heap check: 3 blocks, all sound" };
        kept::reset(); mayFly = true; logLines.clear();
        for (const char *r : rec) kept::LogScreenLine(r);
        CHECK(kept::cardOpens == 0 && kept::cardText.empty() && logLines.empty() && kept::ScreenLinesHeldN == 3);     // THE MODEL MAY FLY: nothing goes to the card
        CHECK(kept::ScreenDyingWords("Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).\r\nPC      : 0x4037a1b2  PS      : 0x00060034\r\nBacktrace: 0x4037a1af:0x3fcf1230 0x42012345:0x3fcf1250\r\n"));
        CHECK(kept::cardOpens == 0 && logLines.empty() && kept::ScreenLinesHeldN == 6);
        kept::KeepScreenNote("Box unanswered: t10", false);
        mayFly = false; kept::FlushDeferredLog();                                            // the quiet moment
        std::vector<std::string> l = kept::lines();
        say("K3. three lines of the screen's and its dying words while the model may fly: the card opened %d time(s) at the quiet moment, %d lines; the first whole: %d\n", kept::cardOpens, (int) l.size(), (int) (l.size() > 1 && l[1] == std::string("12.34.56 - Screen: ") + (rec[0] + 8)));
        CHECK(kept::cardOpens == 1 && l.size() == 7 && l[0] == "12.34.56 - Box unanswered: t10" && l[1] == std::string("12.34.56 - Screen: ") + (rec[0] + 8) && l[2] == std::string("12.34.56 - Screen: ") + (rec[1] + 8) && l[3] == std::string("12.34.56 - Screen: ") + (rec[2] + 8));
        CHECK(l[4] == "12.34.56 - Screen said: Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1)." && l[5].find("Screen said: PC      : 0x4037a1b2") != std::string::npos && l[6].find("Screen said: Backtrace: 0x4037a1af") != std::string::npos);
        CHECK(kept::ScreenLinesHeldN == 0 && kept::DeferredLogN == 0);
        kept::FlushDeferredLog(); CHECK(kept::cardOpens == 1);                                // (nothing more to write: the card is not opened)
        // ... a long one in two lines; and with NOTHING ELSE kept, the held lines are still written
        kept::reset(); mayFly = true;
        { std::string big = "LDRCLOG "; for (int i = 0; i < 300; ++i) big += (char) ('a' + i % 26); kept::LogScreenLine(big.c_str()); }
        CHECK(kept::ScreenLinesHeldN == 2 && kept::DeferredLogN == 0); mayFly = false; kept::FlushDeferredLog();
        l = kept::lines(); CHECK(kept::cardOpens == 1 && l.size() == 2 && l[0].find("12.34.56 - Screen: abcdefghij") == 0 && l[0].size() == 11 + 180 && l[1].find("12.34.56 - Screen (cont): ") == 0 && l[1].size() == 11 + 15 + 128);
        // ... more than there are places for: counted, and the count said
        kept::reset(); mayFly = true;
        for (int i = 0; i < 40; ++i) { char b[60]; snprintf(b, sizeof b, "LDRCLOG line %d of the screen's record", i); nowUs += 1100000; kept::LogScreenLine(b); }   // (a second and more apart: LogScreenLine's own limit - eight in a run - does not count them out)
        mayFly = false; kept::FlushDeferredLog(); l = kept::lines();
        say("K3. forty lines of the screen's in one flight: %d on the card, the last [%s]\n", (int) l.size(), l.empty() ? "" : l.back().c_str());
        CHECK(kept::cardOpens == 1 && l.size() == 29 && l[0] == "12.34.56 - Screen: line 0 of the screen's record" && l[27] == "12.34.56 - Screen: line 27 of the screen's record" && l[28] == "               - 12 more lines of the screen's own were not kept B211");   // (sixteen places: the fifteenth review)
        // (the fifteenth review, reviewer A's X15: nothing held it) ... SAID ONCE: the next writing - one line held in a later flight - does not say the count again
        mayFly = true; nowUs += 3000000; kept::LogScreenLine("LDRCLOG one line of a later flight"); mayFly = false; kept::FlushDeferredLog(); l = kept::lines();
        CHECK(kept::cardOpens == 2 && l.size() == 30 && l[29] == "12.34.56 - Screen: one line of a later flight" && kept::ScreenLinesNotHeld == 0);
        kept::FlushDeferredLog(); CHECK(kept::cardOpens == 2 && kept::lines().size() == 30);                                                         // (and with nothing held, nothing is written)
        // ON THE GROUND: at once, as ever (LogText)
        kept::reset(); mayFly = false; logLines.clear(); nowUs += 2000000;
        kept::LogScreenLine(rec[1]); CHECK(logLines.size() == 1 && logLines[0] == std::string("Screen: ") + (rec[1] + 8) && kept::ScreenLinesHeldN == 0 && kept::cardText.empty());
        CHECK(kept::ScreenDyingWords("CORRUPT HEAP: Bad head at 0x3fcf1234. Expected 0xabba1234 got 0x00000000\r\n") && logLines.size() == 2 && logLines[1].find("Screen said: CORRUPT HEAP") == 0);
    }
    mayFly = false; CurrentView = FRONTVIEW;
"""
if __name__ == '__main__':
    sys.exit(lib.build_run('kept_lines', SCENES, extra=EXTRA))
