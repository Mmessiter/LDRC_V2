#!/usr/bin/env python3
"""Reviewer A (17): Nextion.h OwnWordCut now hands what it cuts away to LogFiles.h ScreenDyingWords (the sixteenth review's 8d).
The REAL lines of main.cpp (the own-words block), the REAL OwnWordCut and ScreenDyingWords - as dev/test_wholepage/scene_dying_behind_word.py builds them.
 D1. the panic handler's line behind TIME= / UKRULES / ldrcpipe=N: in the log ONCE (not twice), and THE WORD IN FRONT IS LEFT AS IT WAS for the lines that act on it.
 D2. the whole panic text (several lines) behind TIME=: how many lines, and are they the ones kept when it comes alone?
 D3. A TAIL THAT IS NOT THE SCREEN'S DYING WORDS: a late text reply glued behind TIME= whose box's text holds "Backtrace:" or "Core dump" - what does it cost?
 D4. THE SIBLING THAT WAS NOT CURED: a line for the log ("LDRCLOG ...") glued behind TIME= / UKRULES / ldrcpipe=N. The released code (HEAD) looked for
     "LDRCLOG " ANYWHERE in the text, first; OwnWordCut (B211, the eleventh review) cuts it away in front of that look: no line in the log."""
import os, sys
TW = os.path.dirname(os.path.abspath(__file__))   # (taken into the suite: this file's own folder)
sys.path.insert(0, TW)
import lib
import scene_own_words as ow
SCENES = r'''
    more(); ScreenFramesBursts = true; BoundFlag = ModelMatched = false;
    const char *dying = "Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).";
    // D1
    for (const char *head : { "TIME=1731672000", "UKRULES", "ldrcpipe=2" })
    {
        nowUs += 3000000; const size_t l0 = logLines.size(); std::string t = std::string(head) + dying;
        const bool answered = xText(t.c_str());
        say("D1. '%s' + the panic line: answered in the own-words block %d; lines in the log %d [%s]; left for the lines that act on the word: '%s'\n", head, (int) answered, (int) (logLines.size() - l0), logLines.size() > l0 ? logLines.back().c_str() : "", TextIn);
        CHECK(logLines.size() - l0 == 1);                    // once
        CHECK(!answered && !strcmp(TextIn, head));           // the word in front goes on to its own lines, whole and alone
    }
    // D2. the whole panic text
    {
        const char *panic = "Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).\r\nCore  1 register dump:\r\nPC      : 0x4037a1b2  PS      : 0x00060034  A0      : 0x8201f2a4\r\nEXCVADDR: 0x00000000  LBEG    : 0x400570e8\r\nBacktrace: 0x4037a1af:0x3fcf1230 0x42012345:0x3fcf1250\r\n";
        nowUs += 3000000; size_t l0 = logLines.size(); xText(panic); const size_t alone = logLines.size() - l0;
        nowUs += 3000000; l0 = logLines.size(); const std::string t = std::string("TIME=1731672000") + panic; const bool answered = xText(t.c_str()); const size_t behind = logLines.size() - l0;
        say("D2. the whole panic text: alone %d lines in the log; behind TIME=: %d lines, the word left '%s' (answered here %d)\n", (int) alone, (int) behind, TextIn, (int) answered);
        CHECK(alone == behind && behind >= 3 && !strcmp(TextIn, "TIME=1731672000"));
    }
    // D3. a tail that is NOT the screen's dying words: a late text reply (p, the box's text, FF FF FF) - the box holds such a word
    {
        struct { const char *tail; const char *what; } tails[] = {
            { "pBacktrace: of my model\xFF\xFF\xFF", "a late text reply, the box holds 'Backtrace: of my model'" },
            { "pCore dump\xFF\xFF\xFF", "a late text reply, the box holds 'Core dump'" },
            { "pMark 2\xFF\xFF\xFF", "a late text reply, the box holds 'Mark 2' (no such word)" } };
        for (auto &q : tails)
        {
            nowUs += 3000000; const size_t l0 = logLines.size(); const std::string t = std::string("TIME=1731672000") + q.tail; const bool answered = xText(t.c_str());
            say("D3. TIME= + %s: lines in the log %d%s%s%s; the word left '%s' (answered here %d)\n", q.what, (int) (logLines.size() - l0), logLines.size() > l0 ? " [" : "", logLines.size() > l0 ? logLines.back().c_str() : "", logLines.size() > l0 ? "]" : "", TextIn, (int) answered);
            CHECK(!answered && !strcmp(TextIn, "TIME=1731672000"));
        }
    }
    // D4. the sibling: a line for the log glued behind the same three words
    {
        int lost = 0, tried = 0;
        for (const char *head : { "", "TIME=1731672000", "UKRULES", "ldrcpipe=2" })
        {
            nowUs += 3000000; const std::string line = "LDRCLOG core 1 (the loop's) silent for 213 ms: task loopTask, part web, at wifi, cmd 310 ms ago: Progress.val=5\n"; const std::string t = std::string(head) + line;
            const bool answered = xText(t.c_str()); bool logged = false; for (auto &s : xSaid) if (s.rfind("log:", 0) == 0) logged = true;
            say("D4. '%s' + a line for the log: answered in the own-words block %d; handed to LogScreenLine %d; left: '%.30s'\n", head, (int) answered, (int) logged, TextIn);
            ++tried; if (!logged) ++lost;
        }
        say("D4. a line for the log behind one of the screen's own words: NOT in the log in %d of %d (HEAD: 0 - it looked for \"LDRCLOG \" anywhere, first)\n", lost, tried);
        CHECK(lost == 0);
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('log_behind_word', SCENES, extra=ow.EXTRA, args=['--show']))
