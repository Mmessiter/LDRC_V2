#!/usr/bin/env python3
"""Reviewer A (18): THE LINE FOR THE LOG BEHIND AN OWN WORD (Nextion.h OwnWordCut -> LogFiles.h LogScreenLine, the seventeenth review's cure) - with the REAL
LogScreenLine and the REAL ScreenLineOut behind it (the harness's namespace "kept": a card that is a text), the REAL OwnWordCut and main.cpp's own lines.
The suite's scene (scene_log_behind_word.py D4) stands in for LogScreenLine and asks only "was it handed on at least once".
 R1. ON THE GROUND: TIME= / UKRULES / ldrcpipe=N + a line for the log: in the log ONCE, the card not opened by anything else, THE WORD IN FRONT LEFT WHOLE for its own lines.
 R2. WHILE THE MODEL MAY FLY: the same - HELD (one place taken), nothing written to the card; at the quiet moment (main.cpp's once-a-second road) on the card once.
 R3. LogScreenLine's own limit (eight in a run with no second's pause) counts these too.
 R4. a tail with BOTH the dying words and a line for the log, in either order: what reaches the log?
 R5. a tail that is NOT the screen's line: a late text reply whose box's text holds "LDRCLOG " - what does it cost?
 R6. WHILE THE SCREEN'S RESTART IS NOTED (ScreenRestartSeen): the REAL TextInIsGenuine in front of OwnWordCut, as main.cpp ButtonWasPressed has it - is the line logged?
 R7. two lines for the log glued behind one word: both in the log?"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree)
TW = os.path.join(ROOT, 'dev', 'test_wholepage')
sys.path.insert(0, TW)
import lib
import scene_own_words as ow
m = lib.m
LOGF = m.release(m.src('include/LogFiles.h'))
STAND = 'static void LogScreenLine(const char *t) { xSaid.push_back(std::string("log:") + t); }'
assert ow.EXTRA.count(STAND) == 1
EXTRA = ow.EXTRA.replace(STAND, 'namespace kept {\n' + m.lift(LOGF, 'FLASHMEM void LogScreenLine(const char *t)') + '}\n'
                         'static void LogScreenLine(const char *t) { xSaid.push_back(std::string("log:") + t); kept::LogScreenLine(t); }   // (the REAL one: on the ground LogText - the harness\'s logLines; in flight held)\n') + r'''
static int nLog() { int n = 0; for (auto &s : xSaid) if (s.rfind("log:", 0) == 0) ++n; return n; }
static bool xWhole(const char *t)   // src/main.cpp ButtonWasPressed's head (the REAL TextInIsGenuine first), then its own-words block
{
    memset(TextIn, 0, 400); memcpy(TextIn, t, strlen(t)); TextInFramed = false; TextInLen = (uint16_t) strlen(t); xSaid.clear();
    if (!TextInIsGenuine()) { memset(TextIn, 0, 8); return true; }   // ("ClearText(); return;")
    return xOwnWords();
}
'''
SCENES = r'''
    more(); ScreenFramesBursts = true; BoundFlag = ModelMatched = false; ScreenRestartSeen = false;
    const std::string line = "LDRCLOG core 1 (the loop's) silent for 213 ms: task loopTask, part web, at wifi, cmd 310 ms ago: Progress.val=5\n";
    // R1. on the ground
    for (const char *head : { "TIME=1731672000", "UKRULES", "ldrcpipe=2" })
    {
        kept::reset(); kept::flies = false; mayFly = false; nowUs += 3000000; const size_t l0 = logLines.size(); const std::string t = std::string(head) + line;
        const bool answered = xText(t.c_str());
        printf("R1. on the ground, '%s' + a line for the log: handed to LogScreenLine %d time(s); lines in the log %d [%s]; answered in the own-words block %d; left for the word's own lines: '%s'; held %d, the card opened %d\n",
               head, nLog(), (int) (logLines.size() - l0), logLines.size() > l0 ? logLines.back().c_str() : "", (int) answered, TextIn, (int) kept::ScreenLinesHeldN, kept::cardOpens);
        CHECK(nLog() == 1 && logLines.size() - l0 == 1 && !answered && !strcmp(TextIn, head) && kept::ScreenLinesHeldN == 0 && kept::cardOpens == 0);
        CHECK(logLines.back().find("Screen: core 1 (the loop's) silent for 213 ms") == 0 || logLines.back().find("Screen: core 1") != std::string::npos);
    }
    // R2. while the model may fly: held, not written; at the quiet moment written once
    {
        kept::reset(); kept::flies = true; mayFly = true; kept::BoundFlag = kept::ModelMatched = true; const size_t l0 = logLines.size(); int handed = 0;
        for (const char *head : { "TIME=1731672000", "UKRULES", "ldrcpipe=2" }) { nowUs += 3000000; const std::string t = std::string(head) + line; const bool answered = xText(t.c_str()); handed += nLog(); CHECK(!answered && !strcmp(TextIn, head)); }
        printf("R2. while the model may fly, the three words each with a line behind: handed on %d times; written at once %d; HELD %d; the card opened %d time(s), %u bytes on it\n", handed, (int) (logLines.size() - l0), (int) kept::ScreenLinesHeldN, kept::cardOpens, (unsigned) kept::cardText.size());
        CHECK(handed == 3 && logLines.size() == l0 && kept::ScreenLinesHeldN == 3 && kept::cardOpens == 0 && kept::cardText.empty());
        kept::flies = false; mayFly = false; kept::BoundFlag = kept::ModelMatched = false; kept::onceASecond(); kept::onceASecond();
        const std::vector<std::string> all = kept::lines(); int scr = 0; for (auto &l : all) if (l.find("Screen: core 1") != std::string::npos) ++scr;
        printf("    the quiet moment (main.cpp's once-a-second road, twice): the card opened %d time(s); of the screen's lines on it %d; left held %d\n", kept::cardOpens, scr, (int) kept::ScreenLinesHeldN);
        CHECK(kept::cardOpens == 1 && scr == 3 && kept::ScreenLinesHeldN == 0);
    }
    // R3. the limit of eight in a run
    {
        kept::reset(); kept::flies = false; mayFly = false; nowUs += 3000000; const size_t l0 = logLines.size();
        for (int i = 0; i < 12; ++i) { nowUs += 20000; char b[120]; snprintf(b, sizeof b, "TIME=17316720%02dLDRCLOG line %d of twelve in a quarter second\n", i, i); xText(b); }
        printf("R3. twelve lines behind TIME= in a quarter second: %d in the log (LogScreenLine's own limit: eight in a run)\n", (int) (logLines.size() - l0));
        CHECK(logLines.size() - l0 == 8);
    }
    // R4. both in one tail
    {
        kept::reset(); nowUs += 3000000; size_t l0 = logLines.size();
        const std::string a = std::string("TIME=1731672000") + "Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).\r\nBacktrace: 0x4037a1af:0x3fcf1230\r\n" + line;
        xText(a.c_str()); printf("R4. TIME= + the dying words + a line for the log: %d line(s) in the log:", (int) (logLines.size() - l0)); for (size_t i = l0; i < logLines.size(); ++i) printf(" [%.90s]", logLines[i].c_str()); printf("\n");
        int dying = 0; for (size_t i = l0; i < logLines.size(); ++i) if (logLines[i].find("Guru Meditation") != std::string::npos) ++dying;
        printf("    ... of the dying words in it: %d line(s) (WHAT SHOULD HOLD: the panic handler's line is kept)\n", dying);
        const int dyingFirst = dying;
        nowUs += 3000000; l0 = logLines.size();
        const std::string b = std::string("TIME=1731672000") + line + "Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).\r\n";
        xText(b.c_str()); printf("    TIME= + a line for the log + the dying words: %d line(s) in the log:", (int) (logLines.size() - l0)); for (size_t i = l0; i < logLines.size(); ++i) printf(" [%.200s]", logLines[i].c_str()); printf("\n");
        if (dyingFirst < 1) printf("   (KNOWN, left for the next release - the eighteenth review, reviewer A's finding 2: the dying words IN FRONT of a line for the log, behind an own word, are not logged)\n");
    }
    // R5. a tail that is not the screen's line
    {
        kept::reset(); nowUs += 3000000; const size_t l0 = logLines.size();
        const bool answered = xText("TIME=1731672000pLDRCLOG is my model's name\xFF\xFF\xFF");
        printf("R5. TIME= + a late text reply whose box holds 'LDRCLOG is my model's name': %d line(s) in the log%s%s%s; the word left '%s' (answered here %d)\n", (int) (logLines.size() - l0), logLines.size() > l0 ? " [" : "", logLines.size() > l0 ? logLines.back().c_str() : "", logLines.size() > l0 ? "]" : "", TextIn, (int) answered);
        CHECK(!answered && !strcmp(TextIn, "TIME=1731672000"));
    }
    // R6. while the screen's restart is noted
    {
        int logged = 0, tried = 0;
        for (const char *head : { "", "TIME=1731672000", "UKRULES", "ldrcpipe=0" })
        {
            kept::reset(); nowUs += 3000000; ScreenRestartSeen = true; const size_t l0 = logLines.size(); const std::string t = std::string(head) + line;
            const bool gone = xWhole(t.c_str()); const int n = (int) (logLines.size() - l0); ScreenRestartSeen = false;
            printf("R6. THE SCREEN'S RESTART NOTED, '%s' + a line for the log: lines in the log %d (handed on %d)\n", head, n, nLog());
            ++tried; if (n) ++logged;
        }
        printf("R6. while the restart is noted: the line reached the log in %d of %d (WHAT SHOULD HOLD: 4 of 4 - it is the screen's own record of its restart that comes then)\n", logged, tried);
        if (logged != tried) printf("   (KNOWN, left for the next release - the same finding: while the screen's restart is noted a text that begins with an own word is refused whole, in front of this cure)\n");
        // the control: no restart noted - all four
        int ok = 0; for (const char *head : { "", "TIME=1731672000", "UKRULES", "ldrcpipe=0" }) { kept::reset(); nowUs += 3000000; const size_t l0 = logLines.size(); const std::string t = std::string(head) + line; xWhole(t.c_str()); if (logLines.size() > l0) ++ok; }
        printf("    (the control, no restart noted: %d of 4)\n", ok); CHECK(ok == 4);
        // ... and the dying words behind the same words while the restart is noted (the sixteenth review's 8d)
        int dy = 0; for (const char *head : { "TIME=1731672000", "UKRULES", "ldrcpipe=0" }) { kept::reset(); nowUs += 3000000; ScreenRestartSeen = true; const size_t l0 = logLines.size(); const std::string t = std::string(head) + "Guru Meditation Error: Core  1 panic'ed (LoadProhibited)."; xWhole(t.c_str()); if (logLines.size() > l0) ++dy; ScreenRestartSeen = false; }
        printf("    the dying words behind the three words while a restart is noted: in the log %d of 3\n", dy);
    }
    // R7. two lines behind one word
    {
        kept::reset(); nowUs += 3000000; const size_t l0 = logLines.size();
        xText("TIME=1731672000LDRCLOG record part one\nLDRCLOG record part two\n");
        printf("R7. TIME= + two lines for the log: %d line(s) in the log:", (int) (logLines.size() - l0)); for (size_t i = l0; i < logLines.size(); ++i) printf(" [%s]", logLines[i].c_str()); printf("\n");
        bool both = false; for (size_t i = l0; i < logLines.size(); ++i) if (logLines[i].find("part one") != std::string::npos && logLines[i].find("part two") != std::string::npos) both = true;
        int two = 0; for (size_t i = l0; i < logLines.size(); ++i) if (logLines[i].find("part two") != std::string::npos) ++two;
        CHECK(two >= 1);
    }
    mayFly = false; kept::flies = false;
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('log_behind_word18', SCENES, extra=EXTRA, args=['--show']))
