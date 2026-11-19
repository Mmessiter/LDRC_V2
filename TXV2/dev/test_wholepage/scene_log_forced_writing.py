#!/usr/bin/env python3
"""Reviewer A (16): THE STORE OF KEPT LINES WITH NO SAFETY SWITCH. The REAL LogFiles.h (KeepScreenNote, LogScreenLine, DeferLogText, FlushDeferredLog) in the
harness's namespace "kept" (its LogMustWait() is the flag "flies": here set as FlightGuard.h's would be for a pilot with NO safety switch and a model connected).
 X1. ON THE BENCH, the model connected, the motor switch off: this release's notes and the screen's own lines are KEPT now (they went to the card at once).
     Then the flight: how many of the motor's / the link's own lines (B47) until the store is written IN FLIGHT - and how long is that one writing?
 X2. the same with the code as the fifteenth review saw it would be: the bench lines written at once (flies false on the bench)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (taken into the suite: this file's own tree)
import lib
m = lib.m
LOGF = m.release(m.src('include/LogFiles.h'))
EXTRA = 'namespace kept {\n' + m.lift(LOGF, 'FLASHMEM void LogScreenLine(const char *t)') + m.lift(LOGF, 'FLASHMEM bool ScreenDyingWords(const char *t)') + '}\n'
SCENES = r"""
    for (int asNow = 1; asNow >= 0; --asNow)
    {
        kept::reset(); logLines.clear();
        // THE BENCH: no safety switch, the model connected, the motor switch off. LogMustWait(): now true; as the fifteenth review saw it (RadiosMustBeOff): false
        kept::flies = asNow; mayFly = asNow;
        int benchAtOnce = 0;
        for (int i = 0; i < 12; ++i) { char b[60]; snprintf(b, sizeof b, "Late %d ms: get tn%d.txt", 450 + 13 * i, i); if (kept::LogMustWait()) kept::KeepScreenNote(b, false); else logLines.push_back(b); }   // twelve slow answers on the Rotorflight pages (Nextion.h NoteLateReply: kept while the log must wait - else to the card at once)
        for (int i = 0; i < 20; ++i) { char b[220]; snprintf(b, sizeof b, "LDRCLOG core 1 (the loop's) silent for %d ms: play 0,7,0 - the page was RFView, the last command t0.txt=\"12.3V\" (it took 3 ms), the card busy 0 ms, heap 81234 free, round %d", 213 + i, i); nowUs += 1100000; kept::LogScreenLine(b); }
        benchAtOnce = (int) logLines.size();
        const int heldNotes = kept::DeferredLogN, heldLines = kept::ScreenLinesHeldN, opens0 = kept::cardOpens;
        // THE FLIGHT: the motor switch on (now both rules say "may fly"); the motor's, the bank's and the gaps' lines (LogFiles.h DeferLogText: B47/B48)
        kept::flies = true; mayFly = true;
        int b47 = 0; size_t wrote = 0;
        while (kept::cardOpens == opens0 && b47 < 100) { char b[24]; snprintf(b, sizeof b, "Gap: %d", 40 + b47); kept::DeferLogText(b, true); ++b47; }
        wrote = kept::cardText.size();
        say("X%d. %s: on the bench %d line(s) went to the card at once; kept at take-off: %d notes in the store of 24, %d of the screen's own lines held. IN FLIGHT the store was written at the %dth line of the link's own, in one writing of %u bytes (%d lines)\n",
            asNow ? 1 : 2, asNow ? "as the code is now (LogMustWait)" : "as the fifteenth review saw it (RadiosMustBeOff)", benchAtOnce, heldNotes, heldLines, b47, (unsigned) wrote, (int) kept::lines().size());
        // (THE SIXTEENTH REVIEW'S CURE: the writing forced by the full store is the 24 SHORT lines only - it was 3777 bytes with the screen's own held lines in it;
        //  those stay held, and are written at the quiet moment they wait for)
        if (asNow) { CHECK(heldNotes == 8 && heldLines == 20 && b47 == 17 && wrote < 1300 && kept::ScreenLinesHeldN == 20);   // (28 places since the seventeenth review: all twenty are held)
                     const size_t before = kept::cardText.size(); kept::flies = false; mayFly = false; kept::FlushDeferredLog();
                     say("     ... and at the quiet moment behind the flight: %u bytes more, held lines left %d\n", (unsigned) (kept::cardText.size() - before), (int) kept::ScreenLinesHeldN);
                     CHECK(kept::ScreenLinesHeldN == 0 && kept::cardText.size() > before + 2000); kept::flies = true; mayFly = true; }
        else CHECK(heldNotes == 0 && heldLines == 0 && b47 == 25 && wrote < 1300);
        if (false) { const std::vector<std::string> l = kept::lines(); size_t longest = 0; for (auto &x : l) if (x.size() > longest) longest = x.size(); say("     (the longest line written %u bytes; the last two lines: [%s] [%s])\n", (unsigned) longest, l[l.size() - 2].c_str(), l.back().c_str()); }
    }
    mayFly = false; kept::flies = false; CurrentView = FRONTVIEW;
"""
if __name__ == '__main__':
    sys.exit(lib.build_run('log_forced_writing', SCENES, extra=EXTRA, args=['--show'], label='reviewer A'))
