#!/usr/bin/env python3
"""Reviewer A (17): THE LOG after the sixteenth review's cure "the forced writing is the 24 short lines only" (LogFiles.h DeferredFullOnly).
The REAL LogFiles.h (KeepScreenNote, LogScreenLine, ScreenDyingWords, DeferLogText, FlushDeferredLog) and main.cpp's own once-a-second lines, in the
harness's namespace "kept" (a card that is a text).
 L1. ONE LONG FLIGHT: the screen restarts in it (its record and its dying words: more lines than there are places), this release's notes past their
     budget, and the link's own lines until the store of 24 is full - THREE forced writings. Then the quiet moment by main.cpp's own road.
     Held: every line written ONCE; the forced writings short; both counts of "not kept" right, each said once; nothing left behind.
 L2. the second screen restart of one flight: how much of its record is kept now that the forced writing no longer empties the sixteen places."""
import os, sys
TW = os.path.dirname(os.path.abspath(__file__))   # (taken into the suite: this file's own folder)
sys.path.insert(0, TW)
import lib
m = lib.m
LOGF = m.release(m.src('include/LogFiles.h'))
EXTRA = 'namespace kept {\n' + m.lift(LOGF, 'FLASHMEM void LogScreenLine(const char *t)') + m.lift(LOGF, 'FLASHMEM bool ScreenDyingWords(const char *t)') + '}\n'
SCENES = r"""
    {
        kept::reset(); logLines.clear(); kept::flies = true; mayFly = true; kept::BoundFlag = kept::ModelMatched = true;
        // the screen restarts in flight: its dying words (3 lines kept of them), its record in ten lines a second and more apart
        kept::ScreenDyingWords("Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).\r\nPC      : 0x4037a1b2  PS      : 0x00060034\r\nBacktrace: 0x4037a1af:0x3fcf1230 0x42012345:0x3fcf1250\r\n");
        for (int i = 0; i < 20; ++i) { char b[80]; snprintf(b, sizeof b, "LDRCLOG record line %02d of the screen's restart", i); nowUs += 1100000; kept::LogScreenLine(b); }
        const int held0 = kept::ScreenLinesHeldN, notHeld0 = kept::ScreenLinesNotHeld;
        size_t forcedBytes[3] = { 0, 0, 0 }; int forced = 0, notesAsked = 0, b47 = 0;
        // notes of this release (twelve different ones each round: eight have a place), and the link's own lines until the store is written - three times
        for (int round = 0; round < 3; ++round)
        {
            for (int i = 0; i < 12; ++i) { char b[60]; snprintf(b, sizeof b, "Late %d ms: get r%dn%d.txt", 450 + i, round, i); kept::KeepScreenNote(b, false); ++notesAsked; }
            const int opens0 = kept::cardOpens; const size_t bytes0 = kept::cardText.size();
            while (kept::cardOpens == opens0 && b47 < 400) { char b[24]; snprintf(b, sizeof b, "Gap: %d", 40 + b47); kept::DeferLogText(b, true); ++b47; }
            forcedBytes[round] = kept::cardText.size() - bytes0; ++forced;
        }
        const std::vector<std::string> inFlight = kept::lines();
        int screenInFlight = 0, noteCountLines = 0; for (auto &l : inFlight) { if (l.find("Screen") != std::string::npos && l.find("notes about") == std::string::npos) ++screenInFlight; if (l.find("more notes about the screen were not kept") != std::string::npos) ++noteCountLines; }
        say("L1. in flight: %d of the screen's lines held (%d found no place); three forced writings of %u, %u and %u bytes, %d lines in all - of the screen's own among them: %d; 'N more notes ... not kept' said %d times; still held %d\n",
            held0, notHeld0, (unsigned) forcedBytes[0], (unsigned) forcedBytes[1], (unsigned) forcedBytes[2], (int) inFlight.size(), screenInFlight, noteCountLines, (int) kept::ScreenLinesHeldN);
        CHECK(held0 == 23 && notHeld0 == 0);                                                         // (3 dying + 20 record lines = 23: 28 places since the seventeenth review - it was sixteen, and 7 found none)
        CHECK(forcedBytes[0] < 1300 && forcedBytes[1] < 1300 && forcedBytes[2] < 1300);               // the forced writing is short, every time
        CHECK(screenInFlight == 0 && kept::ScreenLinesHeldN == 23 && kept::ScreenLinesNotHeld == 0);   // nothing of the screen's own was written in the air; nothing of it was let go
        CHECK(noteCountLines == 3);                                                                  // each forced writing says its own count of notes, once
        for (auto &l : inFlight) if (l.find("more notes about the screen were not kept") != std::string::npos) CHECK(l == "               - 4 more notes about the screen were not kept B211");
        // THE QUIET MOMENT, by main.cpp's own road: the model gone, nothing may fly, the once-a-second round
        kept::flies = false; mayFly = false; kept::BoundFlag = kept::ModelMatched = false;
        const size_t bytes1 = kept::cardText.size(); const int opens1 = kept::cardOpens;
        kept::onceASecond(); kept::onceASecond(); kept::onceASecond();
        const std::vector<std::string> all = kept::lines();
        int screenLines = 0, twice = 0, lineCount = 0; for (size_t i = 0; i < all.size(); ++i) { const bool scr = all[i].find("Screen") != std::string::npos && all[i].find("notes about") == std::string::npos; if (scr) ++screenLines; if (all[i].find("more lines of the screen's own were not kept") != std::string::npos) ++lineCount;
            if (scr) for (size_t j = 0; j < i; ++j) if (all[j] == all[i]) ++twice; }
        say("    the quiet moment (main.cpp's once-a-second round, three times): the card opened %d time(s), %u bytes; of the screen's own on the card %d, written twice %d; '7 more lines ... not kept' said %d time(s); left held %d, counted %d, in the store %d\n",
            kept::cardOpens - opens1, (unsigned) (kept::cardText.size() - bytes1), screenLines, twice, lineCount, (int) kept::ScreenLinesHeldN, (int) kept::ScreenLinesNotHeld, (int) kept::DeferredLogN);
        CHECK(kept::cardOpens - opens1 == 1 && screenLines == 23 && twice == 0 && lineCount == 0 && kept::ScreenLinesHeldN == 0 && kept::ScreenLinesNotHeld == 0 && kept::DeferredLogN == 0);
        { bool found = false; for (auto &l : all) if (l.find("more lines of the screen's own were not kept") != std::string::npos) found = true; CHECK(!found); }   // (every line found its place: no count is said)
        // every note asked for is on the card or counted: 3 rounds x (8 kept + 4 counted)
        int notesOnCard = 0; for (auto &l : all) if (l.find("Late ") != std::string::npos) ++notesOnCard;
        say("    notes: asked %d, on the card %d, counted as not kept %d\n", notesAsked, notesOnCard, 3 * 4);
        CHECK(notesOnCard == 24 && notesAsked == 36);
        // and the link's own lines: every one, once
        int gaps = 0; for (auto &l : all) if (l.find("Gap: ") != std::string::npos) ++gaps;
        CHECK(gaps == b47);
    }
    // L1b (the eighteenth review, reviewer A's finding 6: with 28 places nothing overflowed here any more, and no run held this). MORE LINES THAN PLACES:
    // the count of those that found none SURVIVES A FORCED WRITING in the air, and is said ONCE at the quiet moment.
    {
        kept::reset(); logLines.clear(); kept::flies = true; mayFly = true; kept::BoundFlag = kept::ModelMatched = true;
        kept::ScreenDyingWords("Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).\r\nPC      : 0x4037a1b2  PS      : 0x00060034\r\nBacktrace: 0x4037a1af:0x3fcf1230 0x42012345:0x3fcf1250\r\n");
        for (int i = 0; i < 32; ++i) { char b[80]; snprintf(b, sizeof b, "LDRCLOG record line %02d of a long restart", i); nowUs += 1100000; kept::LogScreenLine(b); }
        const int held0 = kept::ScreenLinesHeldN, notHeld0 = kept::ScreenLinesNotHeld;
        { const int opens0 = kept::cardOpens; int g = 0; while (kept::cardOpens == opens0 && g < 400) { char b[24]; snprintf(b, sizeof b, "Gap: %d", 40 + g); kept::DeferLogText(b, true); ++g; } }   // one forced writing in the air
        const int heldAir = kept::ScreenLinesHeldN, notHeldAir = kept::ScreenLinesNotHeld;
        kept::flies = false; mayFly = false; kept::BoundFlag = kept::ModelMatched = false;
        kept::onceASecond(); kept::onceASecond();
        const std::vector<std::string> all = kept::lines();
        int said = 0; for (auto &l : all) if (l == "               - 7 more lines of the screen's own were not kept B211") ++said;
        say("L1b. 35 lines for 28 places: held %d, found no place %d; behind a forced writing in the air: held %d, counted %d; at the quiet moment the count said %d time(s), left held %d, counted %d\n",
            held0, notHeld0, heldAir, notHeldAir, said, (int) kept::ScreenLinesHeldN, (int) kept::ScreenLinesNotHeld);
        CHECK(held0 == 28 && notHeld0 == 7 && heldAir == 28 && notHeldAir == 7);
        CHECK(said == 1 && kept::ScreenLinesHeldN == 0 && kept::ScreenLinesNotHeld == 0);
    }
    // L2. the SECOND restart of the screen in one flight
    {
        kept::reset(); logLines.clear(); kept::flies = true; mayFly = true; kept::BoundFlag = kept::ModelMatched = true;
        for (int restart = 0; restart < 2; ++restart)
        {
            kept::ScreenDyingWords("Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).\r\nPC      : 0x4037a1b2  PS      : 0x00060034\r\nBacktrace: 0x4037a1af:0x3fcf1230 0x42012345:0x3fcf1250\r\n");
            for (int i = 0; i < 9; ++i) { char b[80]; snprintf(b, sizeof b, "LDRCLOG restart %d record line %d", restart + 1, i); nowUs += 1100000; kept::LogScreenLine(b); }
            for (int k = 0; k < 30; ++k) { char b[24]; snprintf(b, sizeof b, "Gap: %d", 1000 * restart + k); kept::DeferLogText(b, true); }      // (the link's own lines between the two: the store is written once in flight)
        }
        const int heldSecond = [] { int n = 0; for (int i = 0; i < kept::ScreenLinesHeldN; ++i) if (strstr(kept::ScreenLinesHeld[i], "restart 2") || (i >= 12 && strstr(kept::ScreenLinesHeld[i], "Screen said"))) ++n; return n; }();
        say("L2. two restarts of the screen in one flight (twelve lines each), the store of 24 written in between: held %d of 24, counted as not kept %d; of the SECOND restart's twelve lines held: %d\n", (int) kept::ScreenLinesHeldN, (int) kept::ScreenLinesNotHeld, heldSecond);
        CHECK(kept::ScreenLinesHeldN == 24 && kept::ScreenLinesNotHeld == 0 && heldSecond == 12);   // (it was: 16 held, 8 counted as not kept - 4 of the second restart's twelve)
    }
    mayFly = false; kept::flies = false; CurrentView = FRONTVIEW;
"""
if __name__ == '__main__':
    sys.exit(lib.build_run('log_held_lines', SCENES, extra=EXTRA, args=['--show']))
