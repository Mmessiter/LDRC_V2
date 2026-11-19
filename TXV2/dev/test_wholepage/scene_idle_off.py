#!/usr/bin/env python3
"""Reviewer A (18): THE KEPT LINES AT THE IDLE POWER-OFF, BY A RUN (transceiver.h CheckInactivityTimeout, the seventeenth review's cure) - the suite holds this
road by a text check alone (dev/test_poweroff_lines). The REAL CheckInactivityTimeout, lifted, in the harness's namespace "kept" beside the REAL LogFiles.h chain
(KeepScreenNote, LogScreenLine, DeferLogText, FlushDeferredLog; a card that is a text); stand-ins for what else it calls, which write down THE ORDER.
 I1. the time not yet up: nothing happens.
 I2. the time up, A FULL STORE (24 short lines) AND 28 LINES OF THE SCREEN'S OWN HELD (the longest they can be) and both counts of "not kept": what is on the card
     AT THE MOMENT THE POWER IS CUT, in how many openings, how many bytes in the one writing - and the order of the calls.
 I3. called again (the power has not gone yet - the pin is up, the loop runs on): nothing of the kept lines is written twice - and how often is the
     timing report asked for (RELEASED code: PerfWriteReport(true) stands in the same road)?
 I4. nothing kept: the card is not opened.
(What the run cannot say: the card's time for that one writing on the real hardware.)"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree)
sys.path.insert(0, os.path.join(ROOT, 'dev', 'test_wholepage'))
import lib
m = lib.m
LOGF = m.release(m.src('include/LogFiles.h')); TRX = m.release(m.src('include/transceiver.h'))
EXTRA = 'namespace kept {\n' + m.lift(LOGF, 'FLASHMEM void LogScreenLine(const char *t)') + r'''
static uint32_t Inactivity_Timeout = 600000, Inactivity_Start = 0;
static std::vector<std::string> order; static std::string cardAtCut; static int cuts = 0, opensAtCut = 0;
enum { OFF_IDLE_ = 3 };
#define OFF_IDLE kept::OFF_IDLE_
#define POWER_OFF_PIN 5
#ifndef HIGH
#define HIGH 1
#endif
static void NoteWhyOff(uint8_t why) { order.push_back(why == 3 ? "why off: idle" : "why off: ?"); }
static void PerfWriteReport(bool) { order.push_back("the timing report"); }
static void CrumbClear() { order.push_back("the crumb cleared"); }
static void digitalWrite(int pin, int v) { if (pin == POWER_OFF_PIN && v == HIGH) { ++cuts; if (cuts == 1) { cardAtCut = cardText; opensAtCut = cardOpens; } order.push_back("THE POWER IS CUT"); } }
static void FlushDeferredLogReal() { FlushDeferredLog(); }
''' + m.lift(TRX, 'void CheckInactivityTimeout()').replace('FlushDeferredLog();', '{ const int o0 = cardOpens; const size_t b0 = cardText.size(); FlushDeferredLog(); char b[80]; snprintf(b, sizeof b, "the kept lines (%d opening(s) of the card, %u bytes)", cardOpens - o0, (unsigned) (cardText.size() - b0)); order.push_back(b); }') + '}\n'
SCENES = r"""
    {
        // I1. not yet
        kept::reset(); kept::order.clear(); kept::cuts = 0; kept::flies = true; mayFly = true;
        kept::KeepScreenNote("Late 600 ms: get n3.val", false);
        kept::Inactivity_Timeout = 600000; kept::Inactivity_Start = millis(); nowUs += 599000000ull; kept::CheckInactivityTimeout();
        printf("I1. one second before the time is up: calls %d, the power cut %d, the card opened %d\n", (int) kept::order.size(), kept::cuts, kept::cardOpens);
        CHECK(kept::order.empty() && kept::cuts == 0 && kept::cardOpens == 0);
        // I2. the time up - with everything there can be kept
        kept::reset(); kept::order.clear(); kept::cuts = 0; kept::flies = true; mayFly = true; kept::BoundFlag = kept::ModelMatched = false;
        // 28 lines of the screen's own, each as long as a held line can be (two parts of a 360-character line: 14 such lines make 28), and four more that find no place
        for (int i = 0; i < 16; ++i) { std::string l = "LDRCLOG "; char h[40]; snprintf(h, sizeof h, "record %02d: ", i); l += h; while (l.size() < 8 + 345) l += "the page was RFView, the last command t0.txt=12.3V, "; l.resize(8 + 345); nowUs += 1100000; kept::LogScreenLine(l.c_str()); }
        // this release's notes past their budget (eight have a place), then the link's own lines until the store of 24 is full - and not one more (the 25th would force the writing)
        for (int i = 0; i < 12; ++i) { char b[60]; snprintf(b, sizeof b, "Box unanswered: tn%d of the page as it was", i); kept::KeepScreenNote(b, false); }
        int b47 = 0; while (kept::DeferredLogN < 24 && b47 < 100) { char b[40]; snprintf(b, sizeof b, "Gap: %d and a line as long as one can be kept", 40 + b47); kept::DeferLogText(b, true); ++b47; }
        const int short0 = kept::DeferredLogN, held0 = kept::ScreenLinesHeldN, notHeld0 = kept::ScreenLinesNotHeld, notKept0 = kept::ScreenNotesNotKept; const int opens0 = kept::cardOpens;
        size_t longestHeld = 0; for (int i = 0; i < kept::ScreenLinesHeldN; ++i) longestHeld = std::max(longestHeld, strlen(kept::ScreenLinesHeld[i]));
        kept::Inactivity_Start = millis(); nowUs += 601000000ull;
        kept::CheckInactivityTimeout();
        printf("I2. kept as the time ran out: %d short lines in the store of 24, %d of the screen's own held (the longest %u bytes; %d more found no place), %d notes not kept; the card opened before: %d\n", short0, held0, (unsigned) longestHeld, notHeld0, notKept0, opens0);
        printf("    the calls, in their order:"); for (auto &o : kept::order) printf(" [%s]", o.c_str()); printf("\n");
        const std::vector<std::string> all = kept::lines(); int scr = 0, gaps = 0, counts = 0; for (auto &l : all) { if (l.find("Screen") != std::string::npos && l.find("more ") == std::string::npos) ++scr; if (l.find("Gap: ") != std::string::npos) ++gaps; if (l.find(" more ") != std::string::npos) ++counts; }
        printf("    ON THE CARD AS THE POWER WAS CUT: %u bytes in %d opening(s) - %d lines: %d of the screen's own, %d of the link's, %d of the two counts; left in memory: %d short, %d held\n", (unsigned) kept::cardAtCut.size(), kept::opensAtCut - opens0, (int) all.size(), scr, gaps, counts, (int) kept::DeferredLogN, (int) kept::ScreenLinesHeldN);
        CHECK(kept::cuts == 1 && kept::cardAtCut == kept::cardText && kept::opensAtCut - opens0 == 1);            // everything was on the card BEFORE the power was cut, in one opening
        CHECK(short0 == 24 && held0 == 28 && notHeld0 == 4 && scr == 28 && counts == 2 && kept::DeferredLogN == 0 && kept::ScreenLinesHeldN == 0 && kept::ScreenLinesNotHeld == 0);
        CHECK(kept::order.size() == 5 && kept::order[0] == "why off: idle" && kept::order[1].find("the kept lines") == 0 && kept::order[4] == "THE POWER IS CUT");
        // I3. the loop runs on until the power has really gone: the routine is called again and again
        const size_t bytes1 = kept::cardText.size(); const int opens1 = kept::cardOpens;
        for (int i = 0; i < 50; ++i) { nowUs += 5000; kept::CheckInactivityTimeout(); }
        int perfs = 0, whys = 0; for (auto &o : kept::order) { if (o == "the timing report") ++perfs; if (o.find("why off") == 0) ++whys; }
        printf("I3. fifty more passes before the power has gone (the routine does not stop behind the cut; each failed packet comes here again): of the kept lines the card opened %d more time(s), %u more bytes; the power pin put up %d times in all; THE TIMING REPORT (Perf.h PerfWriteReport(true): /PERF.TXT and its dated copy, each removed and written again) asked for %d times in all\n", kept::cardOpens - opens1, (unsigned) (kept::cardText.size() - bytes1), kept::cuts, perfs);
        CHECK(kept::cardOpens == opens1 && kept::cardText.size() == bytes1);
        // I4. nothing kept
        kept::reset(); kept::order.clear(); kept::cuts = 0; kept::Inactivity_Start = millis(); nowUs += 601000000ull; kept::CheckInactivityTimeout();
        printf("I4. nothing kept: the card opened %d time(s); the power cut %d\n", kept::cardOpens, kept::cuts);
        CHECK(kept::cardOpens == 0 && kept::cuts == 1);
    }
    mayFly = false; kept::flies = false;
"""
if __name__ == '__main__':
    sys.exit(lib.build_run('idle_off', SCENES, extra=EXTRA, args=['--show']))
